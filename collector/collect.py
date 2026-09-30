import os
import sqlite3
from collections import Counter

import spotipy
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyOAuth

from genres import get_genres

load_dotenv()
DB_PATH = "data/raw/cache.db"


def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS plays (
            played_at   TEXT,
            track_id    TEXT,
            track_name  TEXT,
            artist_id   TEXT,
            artist_name TEXT,
            duration_ms INTEGER,
            PRIMARY KEY (played_at, track_id)
        )
        """
    )
    return conn


def main():
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
        scope="user-top-read user-read-recently-played",
    ))
    conn = get_db()

    items = sp.current_user_recently_played(limit=50)["items"]
    new_artists = []
    added = 0
    for item in items:
        t = item["track"]
        artist = t["artists"][0]
        cur = conn.execute(
            "INSERT OR IGNORE INTO plays VALUES (?, ?, ?, ?, ?, ?)",
            (item["played_at"], t["id"], t["name"],
             artist["id"], artist["name"], t["duration_ms"]),
        )
        if cur.rowcount:
            added += 1
            new_artists.append(artist["name"])
    conn.commit()

    total = conn.execute("SELECT COUNT(*) FROM plays").fetchone()[0]
    print(f"Fetched {len(items)} plays, {added} new. Database now has {total}.")

    # Genre summary of the new plays
    counts = Counter()
    unknown = 0
    for name in new_artists:
        genres = get_genres(name)
        if genres:
            counts.update(genres[:1])  # primary genre only
        else:
            unknown += 1
    if new_artists:
        print("\nPrimary genres in the new plays:")
        for genre, n in counts.most_common(8):
            print(f"  {genre}: {n}")
        print(f"  (no genre found: {unknown} of {len(new_artists)} plays)")
    conn.close()


if __name__ == "__main__":
    main()
