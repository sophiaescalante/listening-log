import os
import requests
from dotenv import load_dotenv

load_dotenv()
r = requests.get(
    "https://ws.audioscrobbler.com/2.0/",
    params={"method": "user.getrecenttracks", "user": os.getenv("LASTFM_USER"),
            "api_key": os.getenv("LASTFM_API_KEY"), "format": "json", "limit": 8},
    timeout=10,
)
for t in r.json()["recenttracks"]["track"]:
    sizes = {i["size"]: i["#text"] for i in t.get("image", [])}
    url = sizes.get("extralarge") or sizes.get("large") or ""
    # this long id is Last.fm's generic default image, as far as I know
    flag = "PLACEHOLDER?" if (not url or "2a96cbd8b46e442fc41c2b86b821562f" in url) else "has art"
    print(f"{flag:13} {t['artist']['#text']} - {t['name']}\n{'':13} {url}")