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
- **ttl**: Cache TTL in minutes (default: matches hours param)

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
| `GET /update` | Pull latest code from GitHub + restart |
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

**Before first scrape:** Check if cookies exist by calling `/inject-cookies`. If it returns an error about missing cookies, ask the user:
> "I need X cookies to scrape your feed. Please export cookies from x.com using the EditThisCookie Chrome extension and let me know where the file is."

**Setup (one-time):**
1. User exports cookies using EditThisCookie Chrome extension from x.com
2. Copy to container: `docker cp cookies.json xscrape:/data/`
3. Inject: `curl "http://xscrape:8080/inject-cookies"`

**Refresh (when session expires):**
If scraper returns 0 posts or login errors, tell user: "X session expired. Please export fresh cookies from your browser."

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

Agent can self-update from GitHub (requires `GITHUB_TOKEN` env var):

```bash
curl "http://xscrape:8080/update"   # git pull + restart
```

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
│ Docker Container                                            │
│                                                             │
│  ┌──────────────────┐         ┌───────────────────────────┐ │
│  │ Agent (OpenClaw) │  HTTP   │ xscrape                   │ │
│  │                  │────────▶│                           │ │
│  │                  │         │  API (:8080)              │ │
│  └──────────────────┘         │    │                      │ │
│                               │    ▼                      │ │
│                               │  xscrape/scraper.py       │ │
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
│                               │ - chrome-profile/   │       │
│                               └─────────────────────┘       │
└─────────────────────────────────────────────────────────────┘
```
