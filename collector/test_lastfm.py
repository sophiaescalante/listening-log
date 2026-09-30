import os
import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("LASTFM_API_KEY")


def top_tags(artist, n=6):
    r = requests.get(
        "https://ws.audioscrobbler.com/2.0/",
        params={
            "method": "artist.gettoptags",
            "artist": artist,
            "api_key": API_KEY,
            "format": "json",
            "autocorrect": 1,
        },
        timeout=10,
    )
    data = r.json()
    if "error" in data:
        return f"ERROR: {data.get('message')}"
    tags = data.get("toptags", {}).get("tag", [])
    return [(t["name"], t["count"]) for t in tags[:n]] or "(no tags)"


for artist in ["RÜFÜS DU SOL", "Rüfüs Du Sol", "RUFUS DU SOL", "Collem", "Wax Motif"]:
    print(artist, "->", top_tags(artist))
