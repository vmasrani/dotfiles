# YouTube upload setup (optional, one time)

`upload_youtube.py` uploads to **your own channel** with your own Google Cloud OAuth client. Videos are always `private`.

1. Go to <https://console.cloud.google.com/> and create a project (any name).
2. **APIs & Services -> Library** -> search "YouTube Data API v3" -> **Enable**.
3. **APIs & Services -> OAuth consent screen** -> User type **External** -> fill app name + your email -> add your Google
   account under **Test users** -> save.
4. **Publish the consent screen to "In production"** (OAuth consent screen -> *Publish app*). While the app is in "Testing",
   refresh tokens **expire after 7 days** and you will have to re-authorise every week. In production an unverified app shows a
   "Google hasn't verified this app" warning once: click *Advanced -> Go to (app name)*. That is fine for your own account.
5. **APIs & Services -> Credentials -> Create credentials -> OAuth client ID -> Application type: Desktop app.**
   Download the JSON.
6. Save it as `client_secret.json` in the per-user config folder:
   - macOS: `~/Library/Application Support/increments-shorts/client_secret.json`
   - Linux: `~/.config/increments-shorts/client_secret.json`
   - Windows: `%LOCALAPPDATA%\increments-shorts\client_secret.json` (run `uv run scripts/upload_youtube.py auth` once; the error message prints the exact path)
7. `uv run scripts/upload_youtube.py auth` -> a browser opens -> approve -> the token is cached next to the secret.
8. `uv run scripts/upload_youtube.py upload deliverables/<slug>.mp4 --meta deliverables/<slug>.txt --thumbnail deliverables/<slug>-thumbnail.jpg`

Notes:
- Custom thumbnails require the channel to be verified (phone verification in YouTube Studio).
- Default API quota is 10,000 units/day; one upload costs about 1,600, so ~6 uploads per day.
- YouTube **cannot replace a video's file**. To fix a video: upload the new one, then
  `upload_youtube.py delete OLD_VIDEO_ID` (you must type the id back; the agent only runs it after your explicit confirmation).
- Publishing (private -> public) is done by you in Studio. Set **Related video** to the full episode there.
