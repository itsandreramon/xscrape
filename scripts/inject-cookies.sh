#!/bin/bash
# Inject cookies into running container
set -e

COOKIES_FILE="${1:-cookies.json}"
HOST="${2:-localhost}"

if [ ! -f "$COOKIES_FILE" ]; then
    echo "error: $COOKIES_FILE not found"
    echo "usage: $0 [cookies.json] [host]"
    exit 1
fi

if [ "$HOST" = "localhost" ]; then
    docker cp "$COOKIES_FILE" xscrape:/data/
    curl -s http://localhost:8080/inject-cookies
else
    scp "$COOKIES_FILE" "$HOST:/tmp/cookies.json"
    ssh "$HOST" "docker cp /tmp/cookies.json xscrape:/data/ && curl -s http://localhost:8080/inject-cookies"
fi
