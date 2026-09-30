import os
import requests
from dotenv import load_dotenv

load_dotenv()

r = requests.get(
    "https://ws.audioscrobbler.com/2.0/",
    params={
        "method": "user.getrecenttracks",
        "user": os.getenv("LASTFM_USER"),
        "api_key": os.getenv("LASTFM_API_KEY"),
        "format": "json",
        "limit": 10,
    },
    timeout=10,
)
data = r.json()

if "error" in data:
    print("ERROR:", data.get("message"))
else:
    tracks = data["recenttracks"]["track"]
    total = data["recenttracks"]["@attr"]["total"]
    print(f"Total scrobbles on account: {total}\n")
    for t in tracks:
        when = "NOW PLAYING" if t.get("@attr", {}).get("nowplaying") else t["date"]["#text"]
        print(f"- {t['artist']['#text']} - {t['name']} | {when}")