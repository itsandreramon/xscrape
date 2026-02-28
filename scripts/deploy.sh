#!/bin/bash
# Deploy xscrape to VPS
set -e

cd "$(dirname "$0")/.."

VPS_HOST="$1"

if [ -z "$VPS_HOST" ]; then
    echo "usage: $0 <user@host>"
    exit 1
fi
REMOTE_DIR="/root/.openclaw/skills/xscrape"

# check for .env
if [ ! -f docker/.env ]; then
    echo "error: docker/.env not found"
    exit 1
fi

# load token
source docker/.env

echo "deploying to $VPS_HOST..."

# sync repo
echo "syncing files..."
rsync -av --exclude='.venv' --exclude='dist' --exclude='__pycache__' \
    ./ "$VPS_HOST:$REMOTE_DIR/repo/"

# sync .env
rsync -av docker/.env "$VPS_HOST:$REMOTE_DIR/"

# sync cookies if available
if [ -f cookies.json ]; then
    rsync -av cookies.json "$VPS_HOST:$REMOTE_DIR/"
fi

# build and run on VPS
echo "building and starting container..."
ssh "$VPS_HOST" << 'EOF'
cd /root/.openclaw/skills/xscrape/repo

# stop existing
docker rm -f xscrape 2>/dev/null || true

# load env
set -a
source /root/.openclaw/skills/xscrape/.env
set +a

# build
docker build \
    --build-arg GITHUB_TOKEN="$GITHUB_TOKEN" \
    -t xscrape \
    -f docker/Dockerfile .

# run
docker run -d \
    --name xscrape \
    --env-file /root/.openclaw/skills/xscrape/.env \
    -p 8080:8080 \
    -p 6080:6080 \
    -p 9222:9222 \
    -v xscrape-data:/data \
    --restart unless-stopped \
    xscrape

# wait
sleep 8

# inject cookies
if [ -f /root/.openclaw/skills/xscrape/cookies.json ]; then
    docker cp /root/.openclaw/skills/xscrape/cookies.json xscrape:/data/
    curl -s http://localhost:8080/inject-cookies
fi

# verify
curl -s http://localhost:8080/health
EOF

echo ""
echo "deployed!"
echo "  API: http://${VPS_HOST#*@}:8080"
echo "  VNC: http://${VPS_HOST#*@}:6080/vnc.html"
