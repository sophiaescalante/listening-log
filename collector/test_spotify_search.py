from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

load_dotenv()
sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials())

tests = [("Bad Bunny", "Moscow Mule"), ("Feid", "CHORRITO PA LAS ANIMAS"), ("Young Miko", "BIAF <3")]
for artist, track in tests:
    try:
        res = sp.search(q=f"track:{track} artist:{artist}", type="track", limit=1)
        items = res["tracks"]["items"]
        if items:
            t = items[0]
            print("FOUND   ", artist, "-", track, "->", t["id"], "| preview_url:", t.get("preview_url"))
        else:
            print("NO MATCH", artist, "-", track)
    except Exception as e:
        print("ERROR   ", artist, "-", track, "->", e)