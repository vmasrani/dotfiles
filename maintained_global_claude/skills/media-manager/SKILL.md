---
name: media-manager
description: Manage the Plex media stack — add movies/shows, check downloads, scan Plex, view history, manage subtitles, diagnose issues. Use when the user mentions media, movies, TV shows, downloads, torrents, Plex, or wants to check stack health.
---

# Media Manager

Daily-use management tool for the full Plex media stack. Handles content requests, download monitoring, Plex library management, watch history, subtitles, and diagnostics.

## Configuration

- **Helper script:** `~/tools/media-stack-status`
- **Docker compose:** `/Users/vmasrani/dev/plex/docker-compose.yml`
- **Environment file:** `/Users/vmasrani/dev/plex/.env`
- **NAS mount:** `/Volumes/media`
- **Appdata root:** `/Volumes/media/appdata/`

### Services

| Service | Port | API Version | Auth Method |
|---------|------|-------------|-------------|
| Sonarr | 8989 | v3 | `X-Api-Key` header |
| Radarr | 7878 | v3 | `X-Api-Key` header |
| Prowlarr | 9696 | v1 | `X-Api-Key` header |
| qBittorrent | 8080 | v2 | Cookie (`SID` from `/api/v2/auth/login`) |
| Bazarr | 6767 | — | `X-API-KEY` header |
| Tautulli | 8181 | v2 | `?apikey=` query param |
| Overseerr | 5055 | v1 | `X-Api-Key` header |
| FlareSolverr | 8191 | — | None |
| Plex | 32400 | — | `?X-Plex-Token=` query param |

### Plex

Plex runs **natively on macOS** (not in Docker). Get the token with:

```bash
defaults read com.plexapp.plexmediaserver PlexOnlineToken
```

Library sections:
- **Section 1:** Movies (`/Volumes/media/movies`)
- **Section 2:** TV Shows (`/Volumes/media/tv`)

### Defaults for Adding Content

**Sonarr (TV Shows):**
- Root folder: `/tv` (ID 1)
- Quality profile: `WEB-1080p` (ID 4) — good default for most TV
- Monitor: all seasons
- Series type: `standard`

**Radarr (Movies):**
- Root folder: `/movies` (ID 1)
- Quality profile: `HD Bluray + WEB` (ID 4) — good default for most movies
- Monitor: `movieOnly`
- Minimum availability: `released`

All quality profiles (use if user requests specific quality):
| ID | Sonarr | Radarr |
|----|--------|--------|
| 1 | Any | Any |
| 2 | SD | SD |
| 3 | HD-720p | HD-720p |
| 4 | WEB-1080p | HD Bluray + WEB |
| 5 | Ultra-HD | Ultra-HD |
| 6 | HD - 720p/1080p | HD - 720p/1080p |

### Key Gotchas

- **qBittorrent host is `gluetun`, not `qbittorrent`.** qBit uses `network_mode: "service:gluetun"` — from other containers, reach it at `gluetun:8080`. From the Mac host, `localhost:8080`.
- **Tautulli uses `host.docker.internal`** to reach native Plex on the Mac host.
- **Overseerr API needs Plex OAuth** (impractical from CLI). Use Sonarr/Radarr APIs directly instead.
- **Recyclarr overwrites quality profiles.** Manual changes via API get reverted on next Recyclarr run. For permanent changes, edit `/Volumes/media/appdata/recyclarr/recyclarr.yml`.
- **macOS grep has no `-P` flag.** Use `sed -n 's/pattern/\1/p'` inside containers instead of `grep -oP`.
- **Docker network is named `plex_mediastack`** (compose project prefix + network name).
- **qBit credentials:** `admin` / `mediastack`
- ***arr app credentials:** `vmasrani` / `pass123tochange`

---

## Step 1 — Gather Environment

Always start by running the helper script:

```bash
~/tools/media-stack-status --pretty
```

Returns JSON with: `containers`, `vpn`, `nas`, `api_keys`, `health`, `queues`, `qbittorrent`, `errors`.

Extract the API keys from the result and store them as variables for the rest of the session.

**If the script is missing or fails**, gather manually:

```bash
docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.State}}' | sort
docker exec gluetun wget -qO- https://ipinfo.io 2>/dev/null
mount | grep /Volumes/media
SONARR_KEY=$(docker exec sonarr sed -n 's/.*<ApiKey>\(.*\)<\/ApiKey>.*/\1/p' /config/config.xml)
RADARR_KEY=$(docker exec radarr sed -n 's/.*<ApiKey>\(.*\)<\/ApiKey>.*/\1/p' /config/config.xml)
PROWLARR_KEY=$(docker exec prowlarr sed -n 's/.*<ApiKey>\(.*\)<\/ApiKey>.*/\1/p' /config/config.xml)
```

## Step 2 — Determine Intent

Read the user's message and branch to the appropriate workflow:

| User says something like... | Go to |
|---|---|
| "download X", "get X", "add X", "I want to watch X" | **Add Content** |
| "what's downloading", "check queue", "status" | **Check Queue & Downloads** |
| "can't see X in Plex", "scan Plex", "refresh library" | **Scan Plex Library** |
| "what have I watched", "watch history", "recently watched" | **View Watch History** |
| "subtitles for X", "missing subs" | **Check Subtitles** |
| "cancel X", "remove X", "stop downloading X" | **Remove from Queue** |
| "health", "what's broken", "stack status" | **Health Check & Diagnostics** |
| Troubleshooting (can't download, errors, VPN) | **Health Check & Diagnostics** → **Fix Problems** |

If intent is unclear, present the health summary and ask what they need.

---

## Add Content

### Movies (Radarr)

1. **Search** for the movie:
   ```bash
   curl -s -H "X-Api-Key: $RADARR_KEY" "http://localhost:7878/api/v3/movie/lookup?term=SEARCH_TERM" | python3 -c "
   import sys, json
   for r in json.load(sys.stdin)[:5]:
       print(f\"tmdbId={r['tmdbId']} | {r['title']} ({r.get('year','?')}) | {r.get('status','?')}\")"
   ```

2. **Present results** to user and confirm which one.

3. **Check if already in library:**
   ```bash
   curl -s -H "X-Api-Key: $RADARR_KEY" "http://localhost:7878/api/v3/movie" | python3 -c "
   import sys, json
   movies = json.load(sys.stdin)
   matches = [m for m in movies if m['tmdbId'] == TMDB_ID]
   if matches:
       m = matches[0]
       print(f'Already in library: {m[\"title\"]} — hasFile={m[\"hasFile\"]}, monitored={m[\"monitored\"]}')
   else:
       print('Not in library yet')"
   ```

4. **Add** the movie (use the full lookup result as the POST body, with overrides):
   ```bash
   # First get the full lookup object
   MOVIE_JSON=$(curl -s -H "X-Api-Key: $RADARR_KEY" "http://localhost:7878/api/v3/movie/lookup?term=tmdbId:TMDB_ID")

   # Add it with required fields
   echo "$MOVIE_JSON" | python3 -c "
   import sys, json
   movie = json.load(sys.stdin)[0]
   movie['rootFolderPath'] = '/movies'
   movie['qualityProfileId'] = 4
   movie['monitored'] = True
   movie['minimumAvailability'] = 'released'
   movie['addOptions'] = {'searchForMovie': True}
   print(json.dumps(movie))" | curl -s -X POST -H "X-Api-Key: $RADARR_KEY" -H "Content-Type: application/json" \
     "http://localhost:7878/api/v3/movie" -d @-
   ```
   The `searchForMovie: True` in addOptions triggers an immediate search after adding.

5. **Report** what was added and that a search was triggered.

### TV Shows (Sonarr)

1. **Search** for the show:
   ```bash
   curl -s -H "X-Api-Key: $SONARR_KEY" "http://localhost:8989/api/v3/series/lookup?term=SEARCH_TERM" | python3 -c "
   import sys, json
   for r in json.load(sys.stdin)[:5]:
       print(f\"tvdbId={r['tvdbId']} | {r['title']} ({r.get('year','?')}) | Seasons: {r.get('seasonCount','?')} | {r.get('status','?')}\")"
   ```

2. **Present results** to user and confirm.

3. **Check if already in library:**
   ```bash
   curl -s -H "X-Api-Key: $SONARR_KEY" "http://localhost:8989/api/v3/series" | python3 -c "
   import sys, json
   series = json.load(sys.stdin)
   matches = [s for s in series if s['tvdbId'] == TVDB_ID]
   if matches:
       s = matches[0]
       stats = s.get('statistics', {})
       print(f'Already in library: {s[\"title\"]} — {stats.get(\"episodeFileCount\",0)}/{stats.get(\"episodeCount\",0)} episodes')
   else:
       print('Not in library yet')"
   ```

4. **Add** the show:
   ```bash
   SERIES_JSON=$(curl -s -H "X-Api-Key: $SONARR_KEY" "http://localhost:8989/api/v3/series/lookup?term=tvdbId:TVDB_ID")

   echo "$SERIES_JSON" | python3 -c "
   import sys, json
   series = json.load(sys.stdin)[0]
   series['rootFolderPath'] = '/tv'
   series['qualityProfileId'] = 4
   series['monitored'] = True
   series['seasonFolder'] = True
   series['seriesType'] = 'standard'
   series['addOptions'] = {'searchForMissingEpisodes': True}
   # Monitor all seasons by default
   for s in series.get('seasons', []):
       s['monitored'] = True
   print(json.dumps(series))" | curl -s -X POST -H "X-Api-Key: $SONARR_KEY" -H "Content-Type: application/json" \
     "http://localhost:8989/api/v3/series" -d @-
   ```

5. **Report** what was added. Note that specials (Season 0) are also monitored — mention this in case the user only wants main seasons.

---

## Check Queue & Downloads

Present a combined view of Sonarr queue, Radarr queue, and qBittorrent torrents.

### Sonarr/Radarr Queues

The health script output already contains queue data. For each item, categorize:

- **Healthy** — downloading with active seeds and progress
- **Warning** — slow (< 100 KB/s) or few seeds (< 3)
- **Stalled** — 0 seeds, 0 download speed, no progress
- **Error** — queue item has error status

### Wanted but Not Downloading

```bash
# Sonarr — missing episodes
curl -s -H "X-Api-Key: $SONARR_KEY" "http://localhost:8989/api/v3/wanted/missing?pageSize=20&sortDirection=descending&sortKey=airDateUtc"

# Radarr — missing movies
curl -s -H "X-Api-Key: $RADARR_KEY" "http://localhost:7878/api/v3/wanted/missing?pageSize=20&sortDirection=descending&sortKey=digitalRelease"
```

### qBittorrent Details

```bash
SID=$(curl -s -c - http://localhost:8080/api/v2/auth/login -d 'username=admin&password=mediastack' | grep SID | awk '{print $NF}')
curl -s -b "SID=$SID" "http://localhost:8080/api/v2/torrents/info"
```

Present a structured table: title, status, progress%, seeds, speed, size.

---

## Scan Plex Library

Trigger a scan when content has been imported but isn't showing in Plex.

```bash
PLEX_TOKEN=$(defaults read com.plexapp.plexmediaserver PlexOnlineToken)

# Scan Movies
curl -s "http://localhost:32400/library/sections/1/refresh?X-Plex-Token=$PLEX_TOKEN" -w "HTTP %{http_code}"

# Scan TV Shows
curl -s "http://localhost:32400/library/sections/2/refresh?X-Plex-Token=$PLEX_TOKEN" -w "HTTP %{http_code}"
```

Wait ~15 seconds then verify:

```bash
# Search for specific content in Plex
curl -s "http://localhost:32400/search?query=SEARCH_TERM&X-Plex-Token=$PLEX_TOKEN" | python3 -c "
import sys, xml.etree.ElementTree as ET
tree = ET.parse(sys.stdin)
for item in tree.findall('.//*[@title]'):
    tag = item.tag
    title = item.get('title', '')
    year = item.get('year', '')
    if title:
        print(f'  [{tag}] {title} ({year})')"
```

---

## View Watch History

Use Tautulli to show recent watch activity.

```bash
TAUTULLI_KEY="FROM_HEALTH_SCRIPT"

# Recent watch history (last 10 items)
curl -s "http://localhost:8181/api/v2?apikey=$TAUTULLI_KEY&cmd=get_history&length=10" | python3 -c "
import sys, json
data = json.load(sys.stdin)['response']['data']['data']
for item in data:
    pct = item.get('percent_complete', 0)
    status = 'watched' if pct > 90 else f'{pct}%'
    print(f\"  {item.get('full_title')} — {status} — {item.get('date', '')}\")"
```

Other useful Tautulli commands:
```bash
# Currently watching (active streams)
curl -s "http://localhost:8181/api/v2?apikey=$TAUTULLI_KEY&cmd=get_activity"

# Most watched (stats)
curl -s "http://localhost:8181/api/v2?apikey=$TAUTULLI_KEY&cmd=get_home_stats&stat_id=top_movies&stats_count=10"

# Recently added to Plex
curl -s "http://localhost:8181/api/v2?apikey=$TAUTULLI_KEY&cmd=get_recently_added&count=10"
```

---

## Check Subtitles

Use Bazarr to check subtitle status and trigger downloads.

### Missing Subtitles

```bash
BAZARR_KEY="FROM_HEALTH_SCRIPT"

# Wanted movie subtitles
curl -s -H "X-API-KEY: $BAZARR_KEY" "http://localhost:6767/api/movies/wanted?length=20"

# Wanted episode subtitles
curl -s -H "X-API-KEY: $BAZARR_KEY" "http://localhost:6767/api/episodes/wanted?length=20"
```

### Trigger Subtitle Search

```bash
# Search subtitles for a specific movie (by Radarr ID)
curl -s -X POST -H "X-API-KEY: $BAZARR_KEY" -H "Content-Type: application/json" \
  "http://localhost:6767/api/movies/subtitles" -d '{"radarrId": ID, "language": "en"}'

# Search subtitles for a specific episode (by Sonarr episode ID)
curl -s -X POST -H "X-API-KEY: $BAZARR_KEY" -H "Content-Type: application/json" \
  "http://localhost:6767/api/episodes/subtitles" -d '{"sonarrEpisodeId": ID, "language": "en"}'
```

### Bazarr System Health

```bash
curl -s -H "X-API-KEY: $BAZARR_KEY" "http://localhost:6767/api/system/status"
curl -s -H "X-API-KEY: $BAZARR_KEY" "http://localhost:6767/api/system/health"
```

---

## Remove from Queue

**Always confirm with user before removing.**

### Remove from Sonarr/Radarr (also removes torrent from qBit)

```bash
# Sonarr — use blocklist=false so the release can be re-grabbed
curl -s -X DELETE -H "X-Api-Key: $SONARR_KEY" \
  "http://localhost:8989/api/v3/queue/{id}?removeFromClient=true&blocklist=false"

# Radarr
curl -s -X DELETE -H "X-Api-Key: $RADARR_KEY" \
  "http://localhost:7878/api/v3/queue/{id}?removeFromClient=true&blocklist=false"

# Bulk delete (Sonarr example)
curl -s -X DELETE -H "X-Api-Key: $SONARR_KEY" -H "Content-Type: application/json" \
  "http://localhost:8989/api/v3/queue/bulk?removeFromClient=true&blocklist=false" \
  -d '{"ids":[ID1,ID2,ID3]}'
```

### Manage Torrents Directly in qBittorrent

```bash
SID=$(curl -s -c - http://localhost:8080/api/v2/auth/login -d 'username=admin&password=mediastack' | grep SID | awk '{print $NF}')

# Pause a torrent
curl -s -b "SID=$SID" -X POST "http://localhost:8080/api/v2/torrents/pause" -d "hashes=HASH"

# Resume a torrent
curl -s -b "SID=$SID" -X POST "http://localhost:8080/api/v2/torrents/resume" -d "hashes=HASH"

# Delete a torrent (with files)
curl -s -b "SID=$SID" -X POST "http://localhost:8080/api/v2/torrents/delete" -d "hashes=HASH&deleteFiles=true"

# Set download speed limit (bytes/sec, 0 = unlimited)
curl -s -b "SID=$SID" -X POST "http://localhost:8080/api/v2/transfer/setDownloadLimit" -d "limit=0"

# Get global transfer info
curl -s -b "SID=$SID" "http://localhost:8080/api/v2/transfer/info"
```

---

## Health Check & Diagnostics

### Quick Health Summary

After running the helper script (Step 1), check for these issues in priority order:

#### Critical (blocks everything)
- **NAS unmounted** — `/Volumes/media` not mounted. All containers will malfunction.
- **Docker not running** — can't reach any service.

#### High (blocks downloads)
- **VPN down** — gluetun unhealthy or IP is a residential ISP (not ProtonVPN/Proton AG).
- **qBittorrent unreachable** — auth failure or container stopped. Check `gluetun` health first.
- **Download client errors** — Sonarr/Radarr health API reports `downloadClientUnavailable`.

#### Medium (degrades functionality)
- **Broken indexers** — Prowlarr indexers failing, or Sonarr/Radarr indexer health warnings.
- **Import failures** — queue items stuck with import errors.
- **Subtitle failures** — Bazarr health issues.

Present:
```
Infrastructure: [OK/WARN/CRITICAL]
  NAS:          mounted at /Volumes/media (XXG free)
  VPN:          connected (IP: x.x.x.x, Proton AG, Seattle)
  Containers:   11/11 running
  qBittorrent:  connected (admin@gluetun:8080)

Sonarr:  X in queue (Y ok, Z warnings, W errors)
Radarr:  X in queue (Y ok, Z warnings, W errors)
```

---

## Fix Problems

**Always ask the user before destructive actions.**

### Download Client Auth Failure

1. Test qBit login:
   ```bash
   curl -s -c - http://localhost:8080/api/v2/auth/login -d 'username=admin&password=mediastack'
   ```
2. If auth fails, reset the password:
   - `docker stop qbittorrent`
   - Edit `/Volumes/media/appdata/qbittorrent/qBittorrent/qBittorrent.conf` — delete the `WebUI\Password_PBKDF2` line
   - `docker start qbittorrent`
   - Read temp password: `docker logs qbittorrent --tail 5`
   - Set permanent password via API:
     ```bash
     SID=$(curl -s -c - http://localhost:8080/api/v2/auth/login -d "username=admin&password=TEMPPASS" | grep SID | awk '{print $NF}')
     curl -s -b "SID=$SID" http://localhost:8080/api/v2/app/setPreferences -d 'json={"web_ui_password":"mediastack"}'
     ```

### Dead/Stalled Torrents

1. Remove from *arr queue (see **Remove from Queue** above).
2. Trigger a new search:
   ```bash
   # Sonarr — search entire series
   curl -s -X POST -H "X-Api-Key: $SONARR_KEY" -H "Content-Type: application/json" \
     http://localhost:8989/api/v3/command -d '{"name":"SeriesSearch","seriesId":ID}'

   # Radarr — search specific movie
   curl -s -X POST -H "X-Api-Key: $RADARR_KEY" -H "Content-Type: application/json" \
     http://localhost:7878/api/v3/command -d '{"name":"MoviesSearch","movieIds":[ID]}'
   ```

### Quality Profile Rejections

1. Check what's being rejected:
   ```bash
   curl -s -H "X-Api-Key: $SONARR_KEY" "http://localhost:8989/api/v3/release?seriesId=ID&seasonNumber=N"
   ```
   Look at `rejections` array on each release.
2. If formats are being rejected and no alternatives exist:
   - **Warn:** "Recyclarr manages quality profiles. Manual changes will be overwritten. For permanent changes, edit `/Volumes/media/appdata/recyclarr/recyclarr.yml`."
   - Profile endpoint: `GET/PUT http://localhost:8989/api/v3/qualityprofile/{id}`

### Weak Indexers

1. Check current: `GET http://localhost:9696/api/v1/indexer`
2. List available indexer schemas:
   ```bash
   curl -s -H "X-Api-Key: $PROWLARR_KEY" "http://localhost:9696/api/v1/indexer/schema" | python3 -c "
   import sys,json; [print(s['name']) for s in json.load(sys.stdin) if s.get('protocol')=='torrent']"
   ```
3. Sync indexers to apps:
   ```bash
   curl -s -X POST -H "X-Api-Key: $PROWLARR_KEY" -H "Content-Type: application/json" \
     http://localhost:9696/api/v1/command -d '{"name":"ApplicationIndexerSync"}'
   ```

### Import Failures

1. Check queue item error messages for path issues.
2. Verify download categories exist:
   ```bash
   docker exec qbittorrent ls -la /downloads/complete/tv /downloads/complete/movies
   ```
3. Create missing directories:
   ```bash
   docker exec qbittorrent mkdir -p /downloads/complete/tv /downloads/complete/movies
   ```

### VPN Issues

1. Health: `docker inspect gluetun --format '{{.State.Health.Status}}'`
2. Logs: `docker logs gluetun --tail 30`
3. Restart: `docker restart gluetun`

### Container Management

```bash
# Restart a specific service
docker restart SERVICE_NAME

# View recent logs
docker logs SERVICE_NAME --tail 50

# Restart the entire stack
cd /Users/vmasrani/dev/plex && docker compose restart
```

---

## Verify

After any fix or action, re-run the health script:

```bash
~/tools/media-stack-status --pretty
```

Report:
- What was done and current status
- What remains pending and next steps
- Warnings about Recyclarr overwriting manual quality profile changes
