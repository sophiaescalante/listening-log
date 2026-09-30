from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyOAuth

load_dotenv()

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    scope="user-top-read user-read-recently-played",
))

print("Top artists (last ~6 months):")
for a in sp.current_user_top_artists(limit=5, time_range="medium_term")["items"]:
    print("-", a["name"], "| genres:", a.get("genres", "FIELD MISSING"))

print("\nRecently played:")
for item in sp.current_user_recently_played(limit=5)["items"]:
    t = item["track"]
    print("-", t["name"], "by", t["artists"][0]["name"], "|", item["played_at"])
