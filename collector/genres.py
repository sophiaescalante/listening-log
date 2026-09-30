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
MIN_TAG_COUNT = 20  # ignore tags Last.fm scores below this (0-100)
OVERRIDES_PATH = "data/genre_overrides.json"

# Places, nationalities, languages: useful for the map, not for genres.
# Expand as you spot more.
ORIGIN_TAGS = {
    "german", "germany", "usa", "uk", "american", "british", "australia",
    "australian", "canadian", "canada", "puerto rico", "los angeles",
    "london", "swedish", "sweden", "dutch", "netherlands", "french",
    "france", "danish", "denmark", "spanish", "latin",
}

# Junk that is neither a genre nor a place.
NOISE_TAGS = {
    "seen live", "favorites", "favourites", "favorite", "favourite",
    "male vocalists", "female vocalists", "singer-songwriter",
    "albums i own", "spotify", "00s", "10s", "90s", "80s",
}


def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS raw_tags "
        "(artist TEXT PRIMARY KEY, tags TEXT)"
    )
    return conn


def strip_accents(text):
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def fetch_raw(name):
    """Ask Last.fm for an artist's tags. Returns [[tag, score], ...]."""
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
    return [[t["name"].lower(), int(t["count"])] for t in tags]


def get_raw_tags(artist):
    conn = get_db()
    row = conn.execute(
        "SELECT tags FROM raw_tags WHERE artist = ?", (artist,)
    ).fetchone()
    if row:
        conn.close()
        return json.loads(row[0])

    raw = fetch_raw(artist)
    plain = strip_accents(artist)
    if not raw and plain != artist:
        raw = fetch_raw(plain)

    # Cache misses too, so we never re-query artists with no tags
    conn.execute(
        "INSERT OR REPLACE INTO raw_tags VALUES (?, ?)",
        (artist, json.dumps(raw)),
    )
    conn.commit()
    conn.close()
    return raw


def split_tags(artist, raw):
    genres, origins = [], []
    for name, score in raw:
        if score < MIN_TAG_COUNT or name in NOISE_TAGS or name == artist.lower():
            continue
        bucket = origins if name in ORIGIN_TAGS else genres
        if name not in bucket:
            bucket.append(name)
    return genres[:5], origins[:3]


def load_overrides():
    """Genres you assign by hand, for artists Last.fm has no tags for."""
    try:
        with open(OVERRIDES_PATH) as f:
            return {k.lower(): v for k, v in json.load(f).items()}
    except FileNotFoundError:
        return {}


def get_genres(artist):
    override = load_overrides().get(artist.lower())
    if override:
        return override
    return split_tags(artist, get_raw_tags(artist))[0]

def get_origins(artist):
    return split_tags(artist, get_raw_tags(artist))[1]


if __name__ == "__main__":
    for a in ["Jaden Bojsen", "Keanu Silva", "Crunkz", "Bad Bunny",
              "RÜFÜS DU SOL", "Collem"]:
        print(a, "-> genres:", get_genres(a) or "Unknown",
              "| origin:", get_origins(a) or "-")
