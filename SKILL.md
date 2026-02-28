---
name: xscrape
description: "Scrape X (Twitter) feed and return a summary of posts. Uses containerized Chrome with stealth flags and cookie-based auth."
metadata:
  {
    "openclaw":
      {
        "emoji": "🐦"
      }
  }
---

# xscrape — X Feed Scraper

Scrape your X (Twitter) following feed and return a summary of collected posts.

## Quick Start

```bash
# Get feed (uses cache if recent, otherwise scrapes fresh)
curl "http://xscrape:8080/scrape?hours=1"

# Force fresh scrape
curl "http://xscrape:8080/scrape?hours=1&force"

# Get cached results only
curl "http://xscrape:8080/feed"
```

## Parameters

- **hours**: How far back to scrape (default: 0.5 = 30 minutes)
- **feed**: Which feed to scrape
  - `following-recent` (default) — chronological following feed
  - `following-popular` — following feed sorted by engagement
  - `for-you` — algorithmic "For You" feed
- **no_reposts**: Exclude retweets
- **force**: Bypass cache and run fresh scrape
- **ttl**: Cache TTL in minutes (default: 10)

## API Endpoints

Base URL: `http://xscrape:8080`

| Endpoint | Description |
|----------|-------------|
| `GET /scrape?hours=1` | Run scraper (cached by default) |
| `GET /scrape?hours=1&force` | Force fresh scrape |
| `GET /feed` | Get latest feed summary (cached) |
| `GET /feed/xml` | Get raw XML output |
| `GET /cache/status` | Check cache age and status |
| `GET /cache/clear` | Clear cache, force next scrape |
| `GET /update` | Pull latest code from GitHub |
| `GET /restart` | Restart API server (after update) |
| `GET /inject-cookies` | Inject cookies from /data/cookies.json |
| `GET /health` | Health check |

## Caching

- **Default TTL**: Matches scrape window (hours=2 → cache 2 hours)
- **Custom TTL**: `?ttl=30` (minutes)
- **Force refresh**: `?force`
- **Status**: `cached` or `success` in response

When `status: "cached"`, results are from previous scrape. Use `&force` for fresh data.

## Response Format

```json
{
  "status": "success",        // or "cached"
  "cache_age_seconds": 120,   // if cached
  "summary": {
    "post_count": 68,
    "author_count": 12,
    "hours": "1",
    "generated": "2026-02-28T10:49:49Z",
    "top_authors": [
      {"handle": "@visegrad24", "name": "Visegrád 24", "post_count": 15}
    ],
    "recent_posts": [
      {
        "id": "123456",
        "author": "@visegrad24",
        "content": "Tweet content here...",
        "url": "https://x.com/visegrad24/status/123456",
        "timestamp": "2026-02-28T10:48:22+00:00",
        "likes": 47,
        "reposts": 10
      }
    ]
  }
}
```

## Example Summary for User

Format the response like this:

```
📰 X Feed Summary (last 30 minutes)
11 posts from 7 authors

Top authors:
• @visegrad24 (5 posts)
• @DeItaone (2 posts)
• @spectatorindex (1 post)

Recent posts:

1. @visegrad24: "UAE Ministry of Defense has successfully intercepted several Iranian missiles..."
   👍 57 | 🔁 10
   https://x.com/visegrad24/status/123...

2. @WSJ: "Influencers have described propranolol as a magic pill..."
   👍 3 | 🔁 1
   https://x.com/WSJ/status/456...
```

## Session Management

### Cookie-Based Auth

X requires authentication. Cookies are exported from user's browser and injected into the container.

**Setup (one-time):**
1. User exports cookies using EditThisCookie Chrome extension from x.com
2. Copy to container: `docker cp cookies.json xscrape:/data/`
3. Inject: `curl "http://xscrape:8080/inject-cookies"`

**Refresh (when session expires):**
Tell user: "X session expired. Please export fresh cookies from your browser."
Then re-inject via API.

### Check Login Status

If scraper returns 0 posts or login errors, session may have expired.

## Browser Access

| Access | URL | Notes |
|--------|-----|-------|
| VNC | `http://<host>:6080/vnc.html` | Password: `xscrape` |
| CDP | `http://xscrape:9222` | Internal Docker network only |

Use VNC to manually verify browser state or debug issues.

## Container Management

```bash
# Check container status
docker ps | grep xscrape

# View logs
docker logs xscrape --tail 50

# Restart container
docker restart xscrape

# Copy cookies into container
docker cp cookies.json xscrape:/data/
```

## Updating xscrape

### Autonomous Update (via API)
Agent can self-update from GitHub:
```bash
# Pull latest code
curl "http://xscrape:8080/update"

# Restart API to apply changes
curl "http://xscrape:8080/restart"
```

### Manual Update (from Mac)
Python files are mounted from `/opt/xscrape/` on VPS. No rebuild needed for code changes.

```bash
# Sync changes to VPS
rsync -av ~/Base/repositories/xscrape/*.py root@<VPS>:/opt/xscrape/

# Restart API to pick up changes
ssh root@<VPS> "docker exec xscrape pkill -f 'python.*api.py'; \
                docker exec -d xscrape /app/.venv/bin/python /app/api.py"
```

### Full Rebuild (only for Dockerfile/dependency changes)
```bash
rsync -av --exclude='.venv' --exclude='dist' --exclude='__pycache__' \
  ~/Base/repositories/xscrape/ root@<VPS>:/opt/xscrape/

ssh root@<VPS> "cd /opt/xscrape/docker && \
                docker compose down && \
                docker compose build --no-cache && \
                docker compose up -d"

# Re-inject cookies after rebuild
ssh root@<VPS> "docker cp /opt/xscrape/cookies.json xscrape:/data/ && \
                curl -s http://localhost:8080/inject-cookies"
```

### Repository Locations
| Location | Path |
|----------|------|
| Local (Mac) | `~/Base/repositories/xscrape` |
| VPS | `/opt/xscrape` |
| Container | `/app` (code), `/app/repo` (git clone) |
| GitHub | `https://github.com/itsandreramon/xscrape` |

## Troubleshooting

| Issue | Solution |
|-------|----------|
| API not responding | Check `docker ps`, restart if needed |
| 0 posts returned | Session expired, re-inject cookies |
| Scraper times out | Check VNC for browser state |
| "Recent" not found | Feed UI may have changed, check VNC |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Docker Network                                              │
│                                                             │
│  ┌──────────────────┐         ┌───────────────────────────┐ │
│  │ openclaw-gateway │  HTTP   │ xscrape                   │ │
│  │                  │────────▶│                           │ │
│  │  Agent/LLM       │         │  API (:8080)              │ │
│  │                  │         │    │                      │ │
│  └──────────────────┘         │    ▼                      │ │
│                               │  xscrape.py (Playwright)  │ │
│                               │    │                      │ │
│                               │    ▼                      │ │
│                               │  Chrome + Xvfb            │ │
│                               │  - CDP :9222              │ │
│                               │  - VNC :6080              │ │
│                               └───────────────────────────┘ │
│                                          │                  │
│                               ┌──────────▼──────────┐       │
│                               │ /data/              │       │
│                               │ - feed.xml          │       │
│                               │ - cookies.json      │       │
│                               └─────────────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

See `ARCHITECTURE.md` for detailed documentation.
