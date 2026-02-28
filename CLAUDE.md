# xscrape

X (Twitter) feed scraper with Docker container for autonomous operation.

## Quick Reference

```bash
# local
./scripts/local-setup.sh

# deploy to VPS
./scripts/deploy.sh root@<VPS_IP>

# inject cookies
./scripts/inject-cookies.sh cookies.json root@<VPS_IP>
```

## API

Base URL: `http://localhost:8080` (local) or `http://<VPS_IP>:8080`

| Endpoint | Description |
|----------|-------------|
| `GET /scrape?hours=N` | Run scraper (cached) |
| `GET /scrape?force` | Force fresh scrape |
| `GET /feed` | Get cached feed summary |
| `GET /feed/xml` | Get raw XML |
| `GET /inject-cookies` | Inject cookies from /data/cookies.json |
| `GET /update` | Pull latest from GitHub + restart |
| `GET /health` | Health check |

## OpenClaw Integration

```bash
# connect container to openclaw network
docker network connect openclaw_default xscrape

# verify
docker exec openclaw-openclaw-gateway-1 curl -s http://xscrape:8080/health
```

## Files

| Path | Description |
|------|-------------|
| `xscrape/` | Python package (scraper, api, cookies) |
| `docker/` | Dockerfile, entrypoint, compose |
| `scripts/` | Setup and deployment scripts |
| `SKILL.md` | OpenClaw skill definition |

## Cookie Refresh

X cookies expire. When scraping fails, re-export from browser:

1. Go to x.com while logged in
2. Export cookies (EditThisCookie extension)
3. Save as `cookies.json`
4. Run `./scripts/inject-cookies.sh cookies.json root@<VPS_IP>`
