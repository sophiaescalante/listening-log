import os
import sqlite3
import time

import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("LASTFM_API_KEY")
USER = os.getenv("LASTFM_USER")
DB_PATH = "data/raw/cache.db"
URL = "https://ws.audioscrobbler.com/2.0/"


def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS scrobbles (
            uts         INTEGER,
            artist      TEXT,
            artist_mbid TEXT,
            track       TEXT,
            album       TEXT,
            PRIMARY KEY (uts, artist, track)
        )
        """
    )
    return conn


def fetch_page(page, since):
    params = {
        "method": "user.getrecenttracks",
        "user": USER,
        "api_key": API_KEY,
        "format": "json",
        "limit": 200,
        "page": page,
    }
    if since:
        params["from"] = since + 1  # only plays newer than what we have
    r = requests.get(URL, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        raise RuntimeError(data.get("message", "Last.fm error"))
    return data["recenttracks"]


def main():
    conn = get_db()
    since = conn.execute("SELECT MAX(uts) FROM scrobbles").fetchone()[0]

    page, total_pages, fetched, added = 1, 1, 0, 0
    while page <= total_pages:
        recent = fetch_page(page, since)
        total_pages = int(recent["@attr"]["totalPages"])
        tracks = recent.get("track", [])
        if isinstance(tracks, dict):  # Last.fm returns a bare dict for 1 track
            tracks = [tracks]
        for t in tracks:
            if t.get("@attr", {}).get("nowplaying"):
                continue  # still playing, no timestamp yet
            fetched += 1
            cur = conn.execute(
                "INSERT OR IGNORE INTO scrobbles VALUES (?, ?, ?, ?, ?)",
                (int(t["date"]["uts"]), t["artist"]["#text"],
                 t["artist"].get("mbid", ""), t["name"],
                 t.get("album", {}).get("#text", "")),
            )
            added += cur.rowcount
        page += 1
        time.sleep(0.25)
    conn.commit()

    total = conn.execute("SELECT COUNT(*) FROM scrobbles").fetchone()[0]
    print(f"Fetched {fetched} scrobbles, {added} new. Database now has {total}.")
    conn.close()


if __name__ == "__main__":
    main()