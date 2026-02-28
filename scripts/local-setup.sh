#!/bin/bash
# Build and run xscrape container locally
set -e

cd "$(dirname "$0")/.."

# check for .env
if [ ! -f docker/.env ]; then
    echo "error: docker/.env not found"
    echo "create it with:"
    echo "  GITHUB_TOKEN=ghp_xxx"
    echo "  VNC_PASSWORD=xscrape"
    exit 1
fi

# load token from .env
source docker/.env

# stop existing container
docker rm -f xscrape 2>/dev/null || true

# build
echo "building container..."
docker build \
    --build-arg GITHUB_TOKEN="$GITHUB_TOKEN" \
    -t xscrape \
    -f docker/Dockerfile .

# run
echo "starting container..."
docker run -d \
    --name xscrape \
    --env-file docker/.env \
    -p 8080:8080 \
    -p 6080:6080 \
    -p 9222:9222 \
    -v xscrape-data:/data \
    xscrape

# wait for startup
echo "waiting for startup..."
sleep 8

# inject cookies if available
if [ -f cookies.json ]; then
    echo "injecting cookies..."
    docker cp cookies.json xscrape:/data/
    curl -s http://localhost:8080/inject-cookies
    echo ""
fi

# verify
echo ""
echo "verifying..."
curl -s http://localhost:8080/health
echo ""

echo ""
echo "xscrape ready!"
echo "  API: http://localhost:8080"
echo "  VNC: http://localhost:6080/vnc.html"
