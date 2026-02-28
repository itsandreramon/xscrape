# xscrape

X (Twitter) feed scraper with Docker container for autonomous operation.

## Quick Start

### 1. Create `.env` file

```bash
cat > docker/.env << 'EOF'
GITHUB_TOKEN=ghp_xxx
EOF
```

### 2. Export X cookies

X blocks login from VPS environments. Export cookies from your browser:

1. Install [EditThisCookie](https://chrome.google.com/webstore/detail/editthiscookie) Chrome extension
2. Go to x.com while logged in
3. Click extension → Export (copies JSON)
4. Save as `cookies.json` in repo root

### 3. Run locally or deploy

```bash
# Local
./scripts/local-setup.sh

# VPS
./scripts/deploy.sh root@<VPS_IP>
```

### 4. Access

| Service | Local | VPS |
|---------|-------|-----|
| API | http://localhost:8080 | http://\<VPS_IP\>:8080 |
| VNC | http://localhost:6080/vnc.html | http://\<VPS_IP\>:6080/vnc.html |

## Scripts

| Script | Description |
|--------|-------------|
| `./scripts/local-setup.sh` | Build and run container locally |
| `./scripts/deploy.sh [host]` | Deploy to VPS |
| `./scripts/inject-cookies.sh [file] [host]` | Inject cookies into running container |

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /scrape?hours=N` | Run scraper (cached by default) |
| `GET /scrape?force` | Force fresh scrape |
| `GET /feed` | Get cached feed summary |
| `GET /feed/xml` | Get raw XML |
| `GET /cache/status` | Check cache age |
| `GET /cache/clear` | Clear cache |
| `GET /update` | Pull latest from GitHub + restart |
| `GET /inject-cookies` | Inject cookies |
| `GET /health` | Health check |

## Scrape Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `hours` | 0.5 | Time window to scrape |
| `feed` | following-recent | `following-recent`, `following-popular`, `for-you` |
| `no_reposts` | false | Exclude retweets |
| `force` | false | Bypass cache |
| `ttl` | (hours value) | Cache TTL in minutes (default: same as hours) |

## Response Format

```json
{
  "status": "success",
  "summary": {
    "post_count": 68,
    "author_count": 12,
    "hours": "2",
    "top_authors": [
      {"handle": "@example", "name": "Example", "post_count": 5}
    ],
    "recent_posts": [
      {
        "author": "@example",
        "content": "Tweet content...",
        "url": "https://x.com/example/status/123",
        "likes": 42,
        "reposts": 5
      }
    ]
  }
}
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GITHUB_TOKEN` | Yes | GitHub PAT for private repo |

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│ Docker Network                                                           │
│                                                                          │
│  ┌──────────────────┐        ┌─────────────────────────────────────────┐ │
│  │ openclaw         │        │ xscrape                                 │ │
│  │ (optional)       │        │                                         │ │
│  │                  │  HTTP  │  ┌─────────────────────────────────┐    │ │
│  │  ┌────────────┐  │        │  │ API :8080                       │    │ │
│  │  │ Agent/LLM  │──┼───────▶│  │  /scrape    - run scraper       │    │ │
│  │  └────────────┘  │        │  │  /feed      - get results       │    │ │
│  │                  │        │  │  /update    - pull + restart    │    │ │
│  └──────────────────┘        │  │  /inject-cookies                │    │ │
│                              │  └──────────────┬──────────────────┘    │ │
│                              │                 │                       │ │
│                              │                 ▼                       │ │
│                              │  ┌─────────────────────────────────┐    │ │
│                              │  │ scraper.py (Playwright)         │    │ │
│                              │  │  - human-like scrolling         │    │ │
│                              │  │  - feed selection               │    │ │
│                              │  │  - post collection              │    │ │
│                              │  └──────────────┬──────────────────┘    │ │
│                              │                 │ CDP                   │ │
│                              │                 ▼                       │ │
│                              │  ┌─────────────────────────────────┐    │ │
│                              │  │ Chrome + Xvfb                   │    │ │
│                              │  │  - stealth flags                │    │ │
│                              │  │  - CDP :9222                    │    │ │
│                              │  │  - VNC :6080                    │    │ │
│                              │  └─────────────────────────────────┘    │ │
│                              │                                         │ │
│                              └────────────────┬────────────────────────┘ │
│                                               │                          │
└───────────────────────────────────────────────┼──────────────────────────┘
                                                │ volume
                                                ▼
                                  ┌───────────────────────────┐
                                  │ /data (xscrape-data)      │
                                  │  ├── cookies.json         │
                                  │  └── feed.xml             │
                                  └───────────────────────────┘
```

## OpenClaw Integration

To use xscrape as an OpenClaw skill:

### 1. Install skill

```bash
# copy skill to openclaw skills directory (mounted into container)
# host path: /root/.openclaw/skills/xscrape/
# container path: /home/node/.openclaw/skills/xscrape/
scp SKILL.md root@<VPS_IP>:/root/.openclaw/skills/xscrape/

# fix permissions for node user (UID 1000)
ssh root@<VPS_IP> "chown -R 1000:1000 /root/.openclaw/skills/xscrape/"
```

### 2. Connect to OpenClaw network

The xscrape container must be on the same Docker network as OpenClaw:

```bash
# connect xscrape to openclaw network
docker network connect openclaw_default xscrape

# verify connectivity
docker exec openclaw-openclaw-gateway-1 curl -s http://xscrape:8080/health
```

### 3. Restart gateway and verify

```bash
cd /opt/openclaw
docker compose restart openclaw-gateway
docker compose run --rm openclaw-cli skills list | grep xscrape
```

The skill should show as `✓ ready`. OpenClaw can now reach the API at `http://xscrape:8080`.

## Files

| Path | Description |
|------|-------------|
| `xscrape/` | Python package (scraper, api, cookies) |
| `docker/` | Dockerfile, entrypoint |
| `scripts/` | Setup and deployment scripts |
| `SKILL.md` | OpenClaw agent skill definition |
