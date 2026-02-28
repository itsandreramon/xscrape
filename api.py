#!/usr/bin/env python3
"""
Simple HTTP API for xscrape container.
Allows agent to trigger scrapes and retrieve results.
Includes caching to avoid redundant scrapes.
"""

import asyncio
import json
import subprocess
import time
import glob
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import xml.etree.ElementTree as ET

# cache settings
CACHE_TTL_SECONDS = 600  # 10 minutes default
last_scrape_time = 0
last_scrape_params = {}


class XscrapeHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[api] {args[0]}")

    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def get_latest_feed(self):
        """Get the most recently modified feed file"""
        feed_files = list(Path("/data").glob("feed*.xml"))
        if not feed_files:
            return None
        return max(feed_files, key=lambda f: f.stat().st_mtime)

    def do_GET(self):
        global last_scrape_time, last_scrape_params

        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == "/health":
            self.send_json({"status": "ok"})

        elif path == "/scrape":
            # get parameters
            hours = params.get("hours", ["0.5"])[0]
            feed = params.get("feed", ["following-recent"])[0]
            no_reposts = "no_reposts" in params
            force = "force" in params

            # custom TTL - default to hours param (match scrape window)
            hours_float = float(hours)
            ttl_minutes = float(params.get("ttl", [str(hours_float * 60)])[0])
            ttl_seconds = ttl_minutes * 60

            current_params = {"hours": hours, "feed": feed, "no_reposts": no_reposts}
            cache_age = time.time() - last_scrape_time
            latest_feed = self.get_latest_feed()

            # check cache
            if not force and latest_feed and cache_age < ttl_seconds:
                # return cached result
                summary = self.parse_feed(latest_feed)
                self.send_json({
                    "status": "cached",
                    "cache_age_seconds": int(cache_age),
                    "cache_ttl_seconds": int(ttl_seconds),
                    "summary": summary
                })
                return

            # build command
            cmd = [
                "/app/.venv/bin/python", "/app/xscrape.py",
                "--port", "9222",
                "--hours", hours,
                "--feed", feed,
                "--output", "/data/feed.xml"
            ]
            if no_reposts:
                cmd.append("--no-reposts")

            # run scraper
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
                last_scrape_time = time.time()
                last_scrape_params = current_params

                if result.returncode == 0:
                    # read and parse output
                    summary = self.parse_feed("/data/feed.xml")
                    self.send_json({
                        "status": "success",
                        "summary": summary,
                        "output": result.stdout
                    })
                else:
                    self.send_json({
                        "status": "error",
                        "error": result.stderr,
                        "output": result.stdout
                    }, 500)
            except subprocess.TimeoutExpired:
                self.send_json({"status": "error", "error": "timeout"}, 500)
            except Exception as e:
                self.send_json({"status": "error", "error": str(e)}, 500)

        elif path == "/feed":
            # return latest feed xml
            feed_path = self.get_latest_feed()
            if feed_path:
                cache_age = time.time() - last_scrape_time if last_scrape_time > 0 else 0
                summary = self.parse_feed(feed_path)
                self.send_json({
                    "status": "ok",
                    "cache_age_seconds": int(cache_age),
                    "summary": summary
                })
            else:
                self.send_json({"status": "error", "error": "no feed found"}, 404)

        elif path == "/feed/xml":
            # return raw xml
            feed_path = self.get_latest_feed()
            if feed_path:
                self.send_response(200)
                self.send_header("Content-Type", "application/xml")
                self.end_headers()
                self.wfile.write(feed_path.read_bytes())
            else:
                self.send_json({"status": "error", "error": "no feed found"}, 404)

        elif path == "/cache/clear":
            # clear cache (force next scrape to run)
            last_scrape_time = 0
            last_scrape_params = {}
            self.send_json({"status": "ok", "message": "cache cleared"})

        elif path == "/cache/status":
            # show cache status
            latest_feed = self.get_latest_feed()
            cache_age = time.time() - last_scrape_time if last_scrape_time > 0 else None
            self.send_json({
                "status": "ok",
                "has_cache": latest_feed is not None,
                "cache_age_seconds": int(cache_age) if cache_age else None,
                "default_ttl_seconds": CACHE_TTL_SECONDS,
                "last_params": last_scrape_params
            })

        elif path == "/update":
            # pull latest code from git and restart
            try:
                # git pull
                result = subprocess.run(
                    ["git", "-C", "/app/repo", "pull", "--ff-only"],
                    capture_output=True, text=True, timeout=60
                )

                if result.returncode != 0:
                    self.send_json({
                        "status": "error",
                        "error": "git pull failed",
                        "output": result.stderr
                    }, 500)
                    return

                git_output = result.stdout.strip()

                # copy updated files to /app
                import shutil
                files_updated = []
                for py_file in ["xscrape.py", "api.py", "load_cookies.py"]:
                    src = f"/app/repo/{py_file}"
                    dst = f"/app/{py_file}"
                    if Path(src).exists():
                        shutil.copy2(src, dst)
                        files_updated.append(py_file)

                self.send_json({
                    "status": "success",
                    "git_output": git_output,
                    "files_updated": files_updated,
                    "message": "Restart API with /restart to apply changes"
                })

            except Exception as e:
                self.send_json({"status": "error", "error": str(e)}, 500)

        elif path == "/restart":
            # restart the API server
            self.send_json({"status": "ok", "message": "restarting..."})
            # schedule restart after response is sent
            import threading
            def restart():
                import time
                time.sleep(1)
                import os
                os.execv("/app/.venv/bin/python", ["/app/.venv/bin/python", "/app/api.py"])
            threading.Thread(target=restart, daemon=True).start()

        elif path == "/inject-cookies":
            # inject cookies (POST preferred but GET works)
            cookies_path = Path("/data/cookies.json")
            if not cookies_path.exists():
                self.send_json({
                    "status": "error",
                    "error": "cookies.json not found in /data/"
                }, 400)
                return

            cmd = [
                "/app/.venv/bin/python", "/app/load_cookies.py",
                "--port", "9222",
                "--cookies", "/data/cookies.json"
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                self.send_json({"status": "success", "output": result.stdout})
            else:
                self.send_json({"status": "error", "error": result.stderr}, 500)

        else:
            self.send_json({"status": "error", "error": "not found"}, 404)

    def parse_feed(self, path):
        """Parse feed XML and return summary dict"""
        try:
            tree = ET.parse(path)
            root = tree.getroot()

            post_count = int(root.get("post_count", 0))
            author_count = int(root.get("author_count", 0))
            hours = root.get("hours", "?")
            generated = root.get("generated", "")

            # get top authors
            authors = []
            for author_el in root.findall("author"):
                authors.append({
                    "handle": author_el.get("handle"),
                    "name": author_el.get("name"),
                    "post_count": int(author_el.get("post_count", 0))
                })

            # get recent posts (first 10)
            posts = []
            for author_el in root.findall("author"):
                handle = author_el.get("handle")
                for post_el in author_el.findall("post"):
                    content_el = post_el.find("content")
                    metrics_el = post_el.find("metrics")
                    posts.append({
                        "id": post_el.get("id"),
                        "author": handle,
                        "url": post_el.get("url"),
                        "timestamp": post_el.get("timestamp"),
                        "content": content_el.text[:200] if content_el is not None and content_el.text else "",
                        "likes": int(metrics_el.get("likes", 0)) if metrics_el is not None else 0,
                        "reposts": int(metrics_el.get("reposts", 0)) if metrics_el is not None else 0,
                    })

            # sort by timestamp desc, take top 10
            posts.sort(key=lambda p: p["timestamp"], reverse=True)
            posts = posts[:10]

            return {
                "post_count": post_count,
                "author_count": author_count,
                "hours": hours,
                "generated": generated,
                "top_authors": sorted(authors, key=lambda a: a["post_count"], reverse=True)[:5],
                "recent_posts": posts
            }
        except Exception as e:
            return {"error": str(e)}


def main():
    port = 8080
    server = HTTPServer(("0.0.0.0", port), XscrapeHandler)
    print(f"[api] xscrape API server running on port {port}")
    print(f"[api] endpoints:")
    print(f"[api]   GET /health - health check")
    print(f"[api]   GET /scrape?hours=1&feed=following-recent - run scraper (cached)")
    print(f"[api]   GET /scrape?hours=1&force - force fresh scrape")
    print(f"[api]   GET /scrape?hours=1&ttl=5 - custom cache TTL (minutes)")
    print(f"[api]   GET /feed - get latest feed summary")
    print(f"[api]   GET /feed/xml - get raw xml")
    print(f"[api]   GET /cache/status - check cache status")
    print(f"[api]   GET /cache/clear - clear cache")
    print(f"[api]   GET /inject-cookies - inject cookies from /data/cookies.json")
    server.serve_forever()


if __name__ == "__main__":
    main()
