import json
import os
import sqlite3
import time
import unicodedata

import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("LASTFM_API_KEY")
LASTFM_URL = "https://ws.audioscrobbler.com/2.0/"
DB_PATH = "data/raw/cache.db"

# Tags that are places, nationalities, or junk rather than genres.
# Expand this list as you spot more noise.
BLOCKLIST = {
    "seen live", "favorites", "favourites", "favorite", "favourite",
    "usa", "uk", "american", "british", "australia", "australian",
    "canadian", "canada", "puerto rico", "los angeles", "london",
    "male vocalists", "female vocalists", "singer-songwriter",
    "albums i own", "spotify", "00s", "10s", "90s", "80s",
}


def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS artist_tags "
        "(artist TEXT PRIMARY KEY, tags TEXT)"
    )
    return conn


def strip_accents(text):
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def fetch_tags(name):
    """Ask Last.fm for an artist's top tags. Returns [] if none found."""
    r = requests.get(
        LASTFM_URL,
        params={
            "method": "artist.gettoptags",
            "artist": name,
            "api_key": API_KEY,
            "format": "json",
            "autocorrect": 1,
        },
        timeout=10,
    )
    time.sleep(0.25)  # stay polite with Last.fm's rate limits
    data = r.json()
    if "error" in data:
        return []
    tags = data.get("toptags", {}).get("tag", [])
    return [t["name"].lower() for t in tags if int(t["count"]) >= 20]


def clean(tags, artist):
    out = []
    for t in tags:
        if t in BLOCKLIST or t == artist.lower() or t in out:
            continue
        out.append(t)
    return out[:5]


def get_genres(artist):
    conn = get_db()
    row = conn.execute(
        "SELECT tags FROM artist_tags WHERE artist = ?", (artist,)
    ).fetchone()
    if row:
        conn.close()
        return json.loads(row[0])

    tags = fetch_tags(artist)
    plain = strip_accents(artist)
    if not tags and plain != artist:
        tags = fetch_tags(plain)

    genres = clean(tags, artist)
    # Cache misses too, so we never re-query artists with no tags
    conn.execute(
        "INSERT OR REPLACE INTO artist_tags VALUES (?, ?)",
        (artist, json.dumps(genres)),
    )
    conn.commit()
    conn.close()
    return genres


if __name__ == "__main__":
    for a in ["Bad Bunny", "Malcolm Todd", "RÜFÜS DU SOL",
              "Calvin Harris", "Zeds Dead", "Collem", "Wax Motif"]:
        print(a, "->", get_genres(a) or "Unknown")
