import json
import os
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import groupby
from zoneinfo import ZoneInfo

from genres import get_genres, get_origins

DB_PATH = "data/raw/cache.db"
OUT_DIR = "data/hourly"
TIMEZONE = ZoneInfo("America/New_York")  # hours follow YOUR clock, not UTC

_genre_memo = {}
_origin_memo = {}


def genres_for(artist):
    if artist not in _genre_memo:
        _genre_memo[artist] = get_genres(artist)
    return _genre_memo[artist]


def origins_for(artist):
    if artist not in _origin_memo:
        _origin_memo[artist] = get_origins(artist)
    return _origin_memo[artist]


def hour_key(uts):
    """Local wall-clock hour, like 2026-09-30T19."""
    local = datetime.fromtimestamp(uts, tz=timezone.utc).astimezone(TIMEZONE)
    return local.strftime("%Y-%m-%dT%H")


def track_key(play):
    return (play["artist"].lower(), play["track"].lower())


def load_plays(conn):
    rows = conn.execute(
        "SELECT uts, artist, track FROM scrobbles ORDER BY uts"
    ).fetchall()
    return [{"uts": r[0], "hour": hour_key(r[0]), "artist": r[1], "track": r[2]}
            for r in rows]


def find_loops(plays):
    """Runs of the same track back to back, filed under the hour they began."""
    loops = defaultdict(list)
    start = 0
    for i in range(1, len(plays) + 1):
        if i == len(plays) or track_key(plays[i]) != track_key(plays[start]):
            n = i - start
            if n >= 2:
                p = plays[start]
                loops[p["hour"]].append([p["track"], p["artist"], n])
            start = i
    return loops


def build_hours(plays):
    loops = find_loops(plays)
    hours = {}
    for hour, group in groupby(plays, key=lambda p: p["hour"]):
        group = list(group)
        genres, origins, tracks, shown = Counter(), Counter(), Counter(), {}
        for p in group:
            g = genres_for(p["artist"])
            genres[g[0] if g else "unknown"] += 1  # primary genre only
            o = origins_for(p["artist"])
            if o:
                origins[o[0]] += 1
            k = track_key(p)
            tracks[k] += 1
            shown.setdefault(k, (p["track"], p["artist"]))
        hours[hour] = {
            "n": len(group),
            "g": dict(genres.most_common()),
            "o": dict(origins.most_common()),
            "t": [[shown[k][0], shown[k][1], c] for k, c in tracks.most_common()],
            "l": loops.get(hour, []),
        }
    return hours


def dump(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n"


def write_if_changed(path, text):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            if f.read() == text:
                return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return True


def main():
    conn = sqlite3.connect(DB_PATH)
    plays = load_plays(conn)
    conn.close()

    hours = build_hours(plays)
    by_month = defaultdict(dict)
    for key, rec in hours.items():
        by_month[key[:7]][key] = rec

    months = sorted(by_month)
    changed = 0
    for month in months:
        payload = {"month": month, "hours": by_month[month]}
        if write_if_changed(f"{OUT_DIR}/{month}.json", dump(payload)):
            changed += 1

    index_path = f"{OUT_DIR}/index.json"
    previous = None
    if os.path.exists(index_path):
        try:
            with open(index_path, encoding="utf-8") as f:
                previous = json.load(f).get("months")
        except ValueError:
            previous = None
    if changed or previous != months:
        write_if_changed(index_path, dump({
            "months": months,
            "timezone": str(TIMEZONE),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }))

    status = "Wrote" if changed or previous != months else "No changes to"
    print(f"{status} {len(months)} month file(s): {len(plays)} plays "
          f"in {len(hours)} active hours ({OUT_DIR}/)")


if __name__ == "__main__":
    main()