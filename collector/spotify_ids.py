"""Finds Spotify track IDs (for the page's preview player) and remembers them.

Uses Spotify's login-free "client credentials" access, so it can run on GitHub's
robot too. Each run looks up a limited batch; the rest wait for the next run.
"""
import json
import os
import re
import time
import unicodedata

import spotipy
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyClientCredentials

load_dotenv()

IDS_PATH = "data/spotify_ids.json"   # "artist|track" -> Spotify ID ("" = no match found)
MAX_LOOKUPS_PER_RUN = 200
PAUSE = 0.1  # seconds between lookups


def norm(text):
    """Lowercase, no accents, letters and digits only, for forgiving comparisons."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def key_for(artist, track):
    return f"{artist}|{track}".lower()


def load_ids():
    try:
        with open(IDS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_ids(ids):
    os.makedirs(os.path.dirname(IDS_PATH), exist_ok=True)
    with open(IDS_PATH, "w", encoding="utf-8") as f:
        json.dump(ids, f, ensure_ascii=False, indent=0, sort_keys=True)
        f.write("\n")


def make_client():
    if not (os.getenv("SPOTIPY_CLIENT_ID") and os.getenv("SPOTIPY_CLIENT_SECRET")):
        return None
    # No automatic retries: if Spotify says slow down, we stop and resume next run.
    return spotipy.Spotify(auth_manager=SpotifyClientCredentials(),
                           requests_timeout=15, retries=0, status_retries=0)


def best_match(client, artist, track):
    """Spotify ID of the best match, or "" when nothing trustworthy turns up."""
    base = re.split(r"\s+-\s+|\s*[\(\[]", track)[0].strip() or track
    want_artist, want_title = norm(artist), norm(base)
    for title in dict.fromkeys([track, base]):  # full title first, then without "- Radio Edit" etc.
        query = f'track:{title.replace(chr(34), " ")} artist:{artist.replace(chr(34), " ")}'
        found = client.search(q=query, type="track", limit=5)
        for item in found.get("tracks", {}).get("items", []):
            names = [norm(a.get("name", "")) for a in item.get("artists", [])]
            artist_ok = any(n and want_artist and (want_artist in n or n in want_artist) for n in names)
            got_title = norm(item.get("name", ""))
            title_ok = bool(want_title) and (want_title in got_title or got_title in want_title)
            if artist_ok and title_ok:
                return item["id"]
    return ""


def resolve_ids(pairs, client=None, budget=MAX_LOOKUPS_PER_RUN):
    """pairs: [(artist, track), ...] most important first. Returns the full ID table."""
    ids = load_ids()
    todo = [(a, t) for a, t in pairs if key_for(a, t) not in ids]
    if not todo:
        return ids
    client = client or make_client()
    if client is None:
        print(f"Spotify lookup skipped (no credentials); {len(todo)} tracks without a preview player yet.")
        return ids

    done = errors = 0
    for artist, track in todo[:budget]:
        try:
            ids[key_for(artist, track)] = best_match(client, artist, track)
            done += 1
        except spotipy.SpotifyException as e:
            if e.http_status == 429:
                print("Spotify asked us to slow down; will continue on the next run.")
                break
            errors += 1
        except Exception as e:  # network hiccups etc.: skip this one, try the next run
            errors += 1
        if errors >= 3:
            print("Several Spotify errors in a row; stopping early.")
            break
        time.sleep(PAUSE)
    save_ids(ids)
    matched = sum(1 for a, t in todo[:done] if ids.get(key_for(a, t)))
    print(f"Spotify lookups: {done} done ({matched} matched), "
          f"{len(todo) - done} still to do (up to {budget} per run).")
    return ids