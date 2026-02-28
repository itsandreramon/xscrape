#!/bin/bash
set -e

# start xvfb
echo "starting xvfb..."
Xvfb :99 -screen 0 1920x1080x24 -ac &
sleep 2

# start x11vnc (no password - secure via firewall)
echo "starting x11vnc..."
x11vnc -display :99 -rfbport 5900 -shared -forever -nopw -bg
sleep 1

# start novnc/websockify
echo "starting novnc..."
websockify --web /usr/share/novnc/ 6080 localhost:5900 &
sleep 1

# start chrome with stealth flags
echo "starting chrome..."
google-chrome-stable \
    --no-sandbox \
    --disable-blink-features=AutomationControlled \
    --disable-infobars \
    --disable-dev-shm-usage \
    --disable-gpu \
    --lang=en-US \
    --window-size=1920,1080 \
    --remote-debugging-port=9222 \
    --remote-allow-origins=* \
    --user-data-dir=/data/chrome-profile \
    --no-first-run \
    --user-agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36' \
    &

sleep 3

# start api server
echo "starting api server..."
/app/.venv/bin/python -m xscrape.api &
sleep 1

echo "============================================"
echo "xscrape container ready"
echo "  API:  http://localhost:8080"
echo "  CDP:  http://localhost:9222"
echo "  VNC:  http://localhost:6080/vnc.html"
echo "============================================"

# keep container running
tail -f /dev/null
