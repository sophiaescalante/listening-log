import json
import os
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from genres import get_genres, get_origins

DB_PATH = "data/raw/cache.db"
OUT_PATH = "data/weekly/weekly.json"
TIMEZONE = ZoneInfo("America/New_York")  # weeks follow EST clock, not UTC
TOP_N = 10

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


def week_start(played_at):
    """Monday (local time) of the week a play belongs to."""
    utc = datetime.fromisoformat(played_at.replace("Z", "+00:00"))
    local = utc.astimezone(TIMEZONE)
    return (local - timedelta(days=local.weekday())).date()


def longest_loop(plays):
    """Longest run of the same track played back to back."""
    best_track, best_len = None, 0
    run_track, run_len = None, 0
    for p in sorted(plays, key=lambda p: p["played_at"]):
        if p["track_id"] == run_track:
            run_len += 1
        else:
            run_track, run_len = p["track_id"], 1
        if run_len > best_len:
            best_track, best_len = p, run_len
    if best_len < 2:
        return None
    return {"track": best_track["track_name"],
            "artist": best_track["artist_name"],
            "times_in_a_row": best_len}


def summarize(plays):
    total = len(plays)
    tracks = Counter()
    track_info = {}
    artists = Counter()
    genre_plays = Counter()
    origin_plays = Counter()
    known = 0

    for p in plays:
        tracks[p["track_id"]] += 1
        track_info[p["track_id"]] = (p["track_name"], p["artist_name"])
        artists[p["artist_name"]] += 1
        g = genres_for(p["artist_name"])
        if g:
            known += 1
            genre_plays[g[0]] += 1  # primary genre only
        else:
            genre_plays["unknown"] += 1
        o = origins_for(p["artist_name"])
        if o:
            origin_plays[o[0]] += 1

    unique = len(tracks)
    return {
        "total_plays": total,
        "unique_tracks": unique,
        "repeat_rate": round(total / unique, 2) if unique else 0,
        # full track length, so this is an upper bound (skips count in full)
        "approx_minutes": round(sum(p["duration_ms"] for p in plays) / 60000),
        "genre_coverage": round(known / total, 2) if total else 0,
        "genres": [{"name": n, "plays": c} for n, c in genre_plays.most_common()],
        "origins": [{"name": n, "plays": c} for n, c in origin_plays.most_common()],
        "top_artists": [{"name": n, "plays": c}
                        for n, c in artists.most_common(TOP_N)],
        "top_tracks": [{"track": track_info[t][0], "artist": track_info[t][1],
                        "plays": c} for t, c in tracks.most_common(TOP_N)],
        "longest_loop": longest_loop(plays),
    }


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM plays ORDER BY played_at").fetchall()
    conn.close()

    by_week = defaultdict(list)
    for r in rows:
        by_week[week_start(r["played_at"])].append(dict(r))

    weeks = []
    for start in sorted(by_week):
        entry = {"week_start": start.isoformat(),
                 "week_end": (start + timedelta(days=6)).isoformat()}
        entry.update(summarize(by_week[start]))
        weeks.append(entry)

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump({"generated_at": datetime.now(timezone.utc).isoformat(),
                   "timezone": str(TIMEZONE),
                   "weeks": weeks}, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(weeks)} week(s) from {len(rows)} plays to {OUT_PATH}")
    for w in weeks:
        print(f"\nWeek of {w['week_start']}: {w['total_plays']} plays, "
              f"{w['unique_tracks']} unique, repeat rate {w['repeat_rate']}, "
              f"genre coverage {int(w['genre_coverage'] * 100)}%")
        print("  top genres:", ", ".join(
            f"{g['name']} ({g['plays']})" for g in w["genres"][:4]))
        if w["longest_loop"]:
            l = w["longest_loop"]
            print(f"  longest loop: {l['track']} x{l['times_in_a_row']}")


if __name__ == "__main__":
    main()