#!/usr/bin/env python3
"""
Load X cookies into browser via CDP.

Usage:
1. Export cookies from Mac Chrome using EditThisCookie extension (export as JSON)
2. Save as cookies.json in this directory
3. Run: python load_cookies.py --port 9223

The script will inject all x.com/twitter.com cookies into the browser session.
"""

import argparse
import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright


async def load_cookies(cookies_file: Path, port: int):
    """Load cookies from JSON file into browser via CDP"""

    # read cookies
    if not cookies_file.exists():
        print(f"error: {cookies_file} not found")
        print("\nto export cookies:")
        print("1. install EditThisCookie extension in Chrome")
        print("2. go to x.com while logged in")
        print("3. click extension -> export (copies JSON to clipboard)")
        print("4. paste into cookies.json file")
        return False

    cookies_data = json.loads(cookies_file.read_text())
    print(f"loaded {len(cookies_data)} cookies from {cookies_file}")

    async with async_playwright() as p:
        try:
            print(f"connecting to browser on port {port}...")
            browser = await p.chromium.connect_over_cdp(f"http://localhost:{port}")

            contexts = browser.contexts
            if not contexts:
                print("error: no browser context found")
                return False

            context = contexts[0]

            # convert EditThisCookie format to Playwright format
            playwright_cookies = []
            for cookie in cookies_data:
                pc = {
                    "name": cookie.get("name"),
                    "value": cookie.get("value"),
                    "domain": cookie.get("domain", ".x.com"),
                    "path": cookie.get("path", "/"),
                }

                # handle expiration
                if cookie.get("expirationDate"):
                    pc["expires"] = cookie["expirationDate"]

                # handle secure/httpOnly
                if cookie.get("secure"):
                    pc["secure"] = True
                if cookie.get("httpOnly"):
                    pc["httpOnly"] = True
                if cookie.get("sameSite"):
                    # playwright expects specific casing: Strict, Lax, None
                    same_site = cookie["sameSite"].lower()
                    if same_site == "strict":
                        pc["sameSite"] = "Strict"
                    elif same_site == "lax":
                        pc["sameSite"] = "Lax"
                    elif same_site == "none":
                        pc["sameSite"] = "None"
                    elif same_site == "unspecified" or same_site == "no_restriction":
                        pc["sameSite"] = "None"

                playwright_cookies.append(pc)

            # add cookies to context
            await context.add_cookies(playwright_cookies)
            print(f"injected {len(playwright_cookies)} cookies")

            # navigate to x.com to verify
            page = context.pages[0] if context.pages else await context.new_page()
            print("navigating to x.com to verify login...")
            await page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=30000)

            await asyncio.sleep(3)

            # check if logged in
            login_button = await page.query_selector('a[href="/login"]')
            if login_button:
                print("\nwarning: still showing login page")
                print("cookies may have expired or be invalid")
                return False
            else:
                print("\nsuccess! browser appears to be logged in")
                return True

        except Exception as e:
            print(f"error: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(description="Load X cookies into browser via CDP")
    parser.add_argument(
        "--cookies", "-c",
        type=Path,
        default=Path("cookies.json"),
        help="path to cookies JSON file (default: cookies.json)"
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=9222,
        help="CDP port (default: 9222)"
    )

    args = parser.parse_args()

    success = asyncio.run(load_cookies(args.cookies, args.port))
    exit(0 if success else 1)


if __name__ == "__main__":
    main()
