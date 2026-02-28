# xscrape Architecture

## Overview

xscrape is a containerized X (Twitter) feed scraper that runs alongside OpenClaw. It provides an HTTP API for scraping feeds with caching and automatic session management.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ VPS (Tailscale: openclaw)                                                   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ Docker Network: openclaw_default                                        ││
│  │                                                                         ││
│  │  ┌─────────────────────┐         ┌────────────────────────────────────┐ ││
│  │  │ openclaw-gateway    │         │ xscrape                            │ ││
│  │  │                     │  HTTP   │                                    │ ││
│  │  │  Agent/LLM ─────────┼────────▶│  API Server (:8080)                │ ││
│  │  │                     │         │    ├─ /scrape                      │ ││
│  │  │                     │         │    ├─ /feed                        │ ││
│  │  │                     │         │    ├─ /update                      │ ││
│  │  │                     │         │    └─ /cache/*                     │ ││
│  │  │                     │         │           │                        │ ││
│  │  └─────────────────────┘         │           ▼                        │ ││
│  │                                  │  ┌─────────────────────┐           │ ││
│  │                                  │  │ xscrape.py          │           │ ││
│  │                                  │  │ (Playwright/CDP)    │           │ ││
│  │                                  │  └──────────┬──────────┘           │ ││
│  │                                  │             │                      │ ││
│  │                                  │             ▼                      │ ││
│  │                                  │  ┌─────────────────────┐           │ ││
│  │                                  │  │ Chrome + Xvfb       │           │ ││
│  │                                  │  │ - CDP :9222         │           │ ││
│  │                                  │  │ - Stealth flags     │           │ ││
│  │                                  │  │ - Windows UA        │           │ ││
│  │                                  │  └─────────────────────┘           │ ││
│  │                                  │                                    │ ││
│  │                                  └────────────────────────────────────┘ ││
│  │                                               │                         ││
│  └───────────────────────────────────────────────┼─────────────────────────┘│
│                                                  │                          │
│  ┌───────────────────────────────────────────────┼─────────────────────────┐│
│  │ Volumes                                       │                         ││
│  │                                               ▼                         ││
│  │  ┌─────────────────────┐    ┌─────────────────────┐                     ││
│  │  │ xscrape-data        │    │ /opt/xscrape        │                     ││
│  │  │ - cookies.json      │    │ (bind mount)        │                     ││
│  │  │ - feed*.xml         │    │ - *.py files        │                     ││
│  │  │ - chrome-profile/   │    │ - SKILL.md          │                     ││
│  │  └─────────────────────┘    └─────────────────────┘                     ││
│  │                                                                         ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                             │
│  External Access:                                                           │
│  - VNC: http://<ip>:6080/vnc.html (password: xscrape)                       │
│  - API: http://<ip>:8080 (internal: http://xscrape:8080)                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Components

### API Server (api.py)

HTTP server exposing scraper functionality:

| Endpoint | Description |
|----------|-------------|
| `GET /scrape?hours=N` | Run scraper (cached by default) |
| `GET /scrape?force` | Force fresh scrape |
| `GET /feed` | Get latest cached feed |
| `GET /feed/xml` | Get raw XML output |
| `GET /cache/status` | Check cache age |
| `GET /cache/clear` | Clear cache |
| `GET /update` | Pull latest code from GitHub |
| `GET /restart` | Restart API server |
| `GET /inject-cookies` | Inject cookies for auth |
| `GET /health` | Health check |

### Scraper (xscrape.py)

Playwright-based scraper that:
1. Connects to Chrome via CDP
2. Navigates to X feed
3. Scrolls with human-like behavior
4. Parses tweets from DOM
5. Exports XML grouped by author

### Browser (Chrome + Xvfb)

Chrome running in virtual display with stealth flags:
- `--disable-blink-features=AutomationControlled`
- `--user-agent=<Windows Chrome UA>`
- `--remote-debugging-port=9222`

### Cookie Injection (load_cookies.py)

Injects exported browser cookies via CDP to authenticate without logging in on VPS (X detects bot environments during login).

## Data Flow

```
┌─────────┐     ┌─────────┐     ┌──────────┐     ┌────────┐     ┌──────────┐
│  Agent  │────▶│   API   │────▶│ xscrape  │────▶│ Chrome │────▶│  X.com   │
└─────────┘     └─────────┘     └──────────┘     └────────┘     └──────────┘
                    │                                                │
                    │           ┌──────────┐                         │
                    └──────────▶│ feed.xml │◀────────────────────────┘
                                └──────────┘
                                     │
                    ┌────────────────┘
                    ▼
              ┌──────────┐
              │  Agent   │ (formatted summary)
              └──────────┘
```

## Caching

- **TTL**: Matches scrape window (hours=2 → cache 2 hours)
- **Storage**: In-memory timestamp + `/data/feed*.xml`
- **Behavior**: Returns cached results within TTL, scrapes fresh otherwise

## Authentication

X blocks login from bot/VPS environments. Solution:

1. User exports cookies from real browser (EditThisCookie extension)
2. Cookies copied to container `/data/cookies.json`
3. API endpoint injects cookies via CDP
4. Session persists until cookies expire

## Update Mechanism

Agent can trigger self-updates:

```
GET /update  →  git pull from GitHub  →  copy files to /app
GET /restart →  restart API server with new code
```

## File Locations

| Location | Purpose |
|----------|---------|
| `/app/` | Running Python code |
| `/app/repo/` | Git clone for updates |
| `/data/` | Persistent data (cookies, feeds, chrome profile) |
| `/opt/xscrape/` (host) | Bind-mounted source files |

## Ports

| Port | Service | Access |
|------|---------|--------|
| 8080 | API | External + Docker network |
| 6080 | VNC (noVNC) | External |
| 9222 | Chrome CDP | Internal only |
