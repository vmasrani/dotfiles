---
name: request
description: "Quick-add movies or TV shows to the media stack. Usage: /request The Sopranos, /request Interstellar, /request batman 4k"
user_invocable: true
---

# Request Media

Fast-path for adding movies/TV shows. Parses the user's request, searches, confirms, and adds with a single command.

## Step 1 — Get API Keys

```bash
SONARR_KEY=$(docker exec sonarr sed -n 's/.*<ApiKey>\(.*\)<\/ApiKey>.*/\1/p' /config/config.xml)
RADARR_KEY=$(docker exec radarr sed -n 's/.*<ApiKey>\(.*\)<\/ApiKey>.*/\1/p' /config/config.xml)
```

## Step 2 — Parse the Request

From the user's arguments, determine:
- **Title** to search for
- **Type**: movie or TV show (if ambiguous, search both and ask)
- **Quality hint**: if user says "4k" or "uhd", use quality profile ID 5 (Ultra-HD). Otherwise use defaults.

Quality profiles:
| ID | Name | Use when |
|----|------|----------|
| 4 | WEB-1080p (Sonarr) / HD Bluray + WEB (Radarr) | Default |
| 5 | Ultra-HD | User says "4k", "uhd", "2160p" |

## Step 3 — Search & Confirm

### Movies
```bash
curl -s -H "X-Api-Key: $RADARR_KEY" "http://localhost:7878/api/v3/movie/lookup?term=SEARCH_TERM" | python3 -c "
import sys, json
for r in json.load(sys.stdin)[:5]:
    print(f\"tmdbId={r['tmdbId']} | {r['title']} ({r.get('year','?')}) | {r.get('status','?')}\")"
```

### TV Shows
```bash
curl -s -H "X-Api-Key: $SONARR_KEY" "http://localhost:8989/api/v3/series/lookup?term=SEARCH_TERM" | python3 -c "
import sys, json
for r in json.load(sys.stdin)[:5]:
    print(f\"tvdbId={r['tvdbId']} | {r['title']} ({r.get('year','?')}) | Seasons: {r.get('seasonCount','?')} | {r.get('status','?')}\")"
```

Present the top results and confirm which one. If only one obvious match, proceed directly.

### Check if already in library

**Movies:**
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

**TV Shows:**
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

If already in library with files, tell the user and stop. If in library but missing files, trigger a search instead.

## Step 4 — Add & Search

### Add Movie
```bash
MOVIE_JSON=$(curl -s -H "X-Api-Key: $RADARR_KEY" "http://localhost:7878/api/v3/movie/lookup?term=tmdbId:TMDB_ID")
echo "$MOVIE_JSON" | python3 -c "
import sys, json
movie = json.load(sys.stdin)[0]
movie['rootFolderPath'] = '/movies'
movie['qualityProfileId'] = QUALITY_ID
movie['monitored'] = True
movie['minimumAvailability'] = 'released'
movie['addOptions'] = {'searchForMovie': True}
print(json.dumps(movie))" | curl -s -X POST -H "X-Api-Key: $RADARR_KEY" -H "Content-Type: application/json" \
  "http://localhost:7878/api/v3/movie" -d @-
```

### Add TV Show
```bash
SERIES_JSON=$(curl -s -H "X-Api-Key: $SONARR_KEY" "http://localhost:8989/api/v3/series/lookup?term=tvdbId:TVDB_ID")
echo "$SERIES_JSON" | python3 -c "
import sys, json
series = json.load(sys.stdin)[0]
series['rootFolderPath'] = '/tv'
series['qualityProfileId'] = QUALITY_ID
series['monitored'] = True
series['seasonFolder'] = True
series['seriesType'] = 'standard'
series['addOptions'] = {'searchForMissingEpisodes': True}
for s in series.get('seasons', []):
    s['monitored'] = True
print(json.dumps(series))" | curl -s -X POST -H "X-Api-Key: $SONARR_KEY" -H "Content-Type: application/json" \
  "http://localhost:8989/api/v3/series" -d @-
```

## Step 5 — Report

Confirm what was added:
- Title, year, type (movie/show)
- Quality profile used
- Number of seasons (if TV)
- "Search triggered — check queue in a few minutes with `/media-manager status`"
