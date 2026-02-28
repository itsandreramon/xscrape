#!/usr/bin/env python3
"""
X (Twitter) Following Feed Scraper

Scrolls through your X following feed and collects posts from a configurable
time period, then exports them as XML grouped by author.

This version connects to an existing Chrome browser to avoid detection.
"""

import argparse
import asyncio
import random
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom

from playwright.async_api import async_playwright, Page, TimeoutError as PlaywrightTimeout


@dataclass
class Post:
    """represents a single post/tweet"""
    id: str
    author_handle: str
    author_name: str
    content: str
    timestamp: datetime
    url: str
    likes: int = 0
    reposts: int = 0
    replies: int = 0
    views: int = 0
    is_repost: bool = False
    reposted_by: str | None = None


@dataclass
class FeedScraper:
    """scrapes x following feed with human-like scrolling behavior"""

    hours: int = 2
    headless: bool = False
    output_path: Path = field(default_factory=lambda: Path("dist/feed.xml"))
    user_data_dir: Path | None = None
    slow_mo: int = 50
    debug_port: int = 9222
    feed_mode: str = "following-recent"  # for-you, following-recent, following-popular

    posts: list[Post] = field(default_factory=list)
    seen_ids: set[str] = field(default_factory=set)
    cutoff_time: datetime = field(init=False)

    def __post_init__(self):
        self.cutoff_time = datetime.now(timezone.utc) - timedelta(hours=self.hours)

    async def run(self):
        """main entry point"""
        print(f"starting x feed scraper")
        print(f"collecting posts from the last {self.hours} hours")
        print(f"cutoff time: {self.cutoff_time.isoformat()}")
        print(f"feed mode: {self.feed_mode}")

        # launch chrome with remote debugging
        chrome_process = self._launch_chrome()

        # give chrome time to start
        await asyncio.sleep(2)

        async with async_playwright() as p:
            try:
                # connect to existing chrome
                print(f"connecting to chrome on port {self.debug_port}...")
                browser = await p.chromium.connect_over_cdp(f"http://localhost:{self.debug_port}")

                # get existing context or create new one
                contexts = browser.contexts
                if contexts:
                    context = contexts[0]
                    page = context.pages[0] if context.pages else await context.new_page()
                else:
                    context = await browser.new_context()
                    page = await context.new_page()

                await self._scrape_feed(page)

            except Exception as e:
                print(f"error connecting to chrome: {e}")
                print("\nmake sure chrome was launched with remote debugging enabled")
                print("the script will try to launch it for you, but if it fails,")
                print("run this command manually first:")
                print(f'\n  /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port={self.debug_port} --user-data-dir="{self.user_data_dir or "~/.xscrape-chrome"}"')
                sys.exit(1)

        self._export_xml()
        print(f"\ndone! collected {len(self.posts)} posts from {len(self._get_authors())} authors")
        print(f"output saved to: {self.output_path}")

    def _launch_chrome(self) -> subprocess.Popen | None:
        """launch chrome with remote debugging enabled"""

        user_data = self.user_data_dir or Path.home() / ".xscrape-chrome"
        user_data = Path(user_data).expanduser()
        user_data.mkdir(parents=True, exist_ok=True)

        chrome_paths = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "google-chrome",
            "chromium",
        ]

        chrome_path = None
        for path in chrome_paths:
            if Path(path).exists():
                chrome_path = path
                break

        if not chrome_path:
            print("warning: could not find chrome, please launch it manually with:")
            print(f'  /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port={self.debug_port} --user-data-dir="{user_data}"')
            return None

        args = [
            chrome_path,
            f"--remote-debugging-port={self.debug_port}",
            f"--user-data-dir={user_data}",
        ]

        if self.headless:
            args.append("--headless=new")

        print(f"launching chrome with remote debugging on port {self.debug_port}...")
        try:
            process = subprocess.Popen(
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return process
        except Exception as e:
            print(f"warning: could not launch chrome: {e}")
            return None

    async def _scrape_feed(self, page: Page):
        """navigate to following feed and scroll through posts"""

        # go to home feed
        print("navigating to x.com/home...")
        await page.goto("https://x.com/home", wait_until="domcontentloaded", timeout=60000)

        # check if login is needed
        await self._handle_login_if_needed(page)

        # select feed based on mode
        await self._select_feed_mode(page)

        # wait for feed to load
        await self._wait_for_feed(page)

        # scroll and collect posts
        await self._scroll_and_collect(page)

    async def _select_feed_mode(self, page: Page):
        """select the appropriate feed tab and sort option"""

        if self.feed_mode == "for-you":
            # stay on "for you" tab (default)
            print("using 'for you' feed (default tab)")
            await self._human_delay(1000, 1500)
        elif self.feed_mode.startswith("following"):
            # switch to following tab
            await self._switch_to_following_tab(page)

            # then set sort mode if recent
            if self.feed_mode == "following-recent":
                # try clicking the sparkle icon to toggle to latest
                await self._toggle_timeline_to_latest(page)
            else:  # following-popular
                print("using popular/top sort (default for following)")
        else:
            print(f"unknown feed mode: {self.feed_mode}, using default")

    async def _switch_to_following_tab(self, page: Page):
        """click on the following tab"""

        try:
            # wait for tabs to be visible
            await self._human_delay(1000, 1500)

            # try multiple selectors for the following tab
            selectors = [
                'a[href="/following"]:has-text("Following")',
                '[role="tab"]:has-text("Following")',
                'a:has-text("Following")',
                'span:text("Following")',
            ]

            following_tab = None
            for selector in selectors:
                following_tab = await page.query_selector(selector)
                if following_tab:
                    break

            if following_tab:
                await following_tab.click()
                print("clicked following tab")
                await self._human_delay(1500, 2500)
            else:
                # might already be on following or layout changed
                print("following tab not found, assuming already on following feed")
        except Exception as e:
            print(f"note: couldn't click following tab ({e}), continuing anyway")

    async def _toggle_timeline_to_latest(self, page: Page):
        """toggle timeline from top posts to latest using sparkle icon"""

        try:
            # wait for feed to settle
            await self._human_delay(1000, 1500)

            # the sparkle/stars icon at the top right toggles the sort
            # it's usually in the navigation header area
            # try finding it by aria-label or data-testid

            # first, let's try finding any button with a sparkle/stars icon
            sparkle_selectors = [
                '[aria-label*="Top"]',
                '[aria-label*="Timeline"]',
                '[aria-label*="Latest"]',
                '[data-testid="timelineHeader"] button',
                'header button[aria-haspopup]',
                'nav button[aria-haspopup]',
            ]

            sparkle_button = None
            for selector in sparkle_selectors:
                try:
                    sparkle_button = await page.query_selector(selector)
                    if sparkle_button:
                        # check if it's visible and clickable
                        is_visible = await sparkle_button.is_visible()
                        if is_visible:
                            print(f"found sort button with selector: {selector}")
                            break
                        sparkle_button = None
                except Exception:
                    continue

            if sparkle_button:
                await sparkle_button.click()
                await self._human_delay(500, 800)

                # look for menu items
                menu_selectors = [
                    '[role="menuitem"]:has-text("Latest")',
                    '[role="menuitem"]:has-text("latest")',
                    'text="See latest posts instead"',
                    'text="Latest"',
                    '[data-testid="menuitem"]:has-text("Latest")',
                ]

                for selector in menu_selectors:
                    try:
                        menu_item = await page.query_selector(selector)
                        if menu_item:
                            await menu_item.click()
                            print("switched to latest/chronological sort")
                            await self._human_delay(1000, 1500)
                            return
                    except Exception:
                        continue

                # close menu if we couldn't find the option
                await page.keyboard.press("Escape")
                print("menu opened but 'latest' option not found - may need manual selection")
            else:
                print("sort toggle button not found - x may have changed their ui")
                print("tip: manually click the sparkle icon at top right to switch to 'Latest'")

        except Exception as e:
            print(f"note: couldn't toggle to latest sort ({e})")

    async def _handle_login_if_needed(self, page: Page):
        """detect and wait for manual login if needed"""

        # wait a moment for page to settle
        await self._human_delay(2000, 3000)

        # check for login indicators
        try:
            login_button = await page.query_selector('a[href="/login"]')
            sign_in_text = await page.query_selector('text="Sign in"')

            if login_button or sign_in_text:
                print("\n" + "=" * 50)
                print("LOGIN REQUIRED")
                print("please log in to your x account in the browser window")
                print("the scraper will continue automatically after login")
                print("=" * 50 + "\n")

                # wait for home timeline to appear (indicates successful login)
                await page.wait_for_selector(
                    '[data-testid="primaryColumn"]',
                    timeout=300000  # 5 minutes for manual login
                )
                print("login detected, continuing...")
                await self._human_delay(2000, 3000)
        except PlaywrightTimeout:
            print("login timeout - please try again")
            sys.exit(1)

    async def _wait_for_feed(self, page: Page):
        """wait for the feed timeline to load"""

        print("waiting for feed to load...")
        try:
            await page.wait_for_selector(
                '[data-testid="tweet"]',
                timeout=30000
            )
            await self._human_delay(1000, 2000)
        except PlaywrightTimeout:
            print("warning: couldn't detect tweets, feed might be empty or layout changed")

    async def _scroll_and_collect(self, page: Page):
        """scroll through feed collecting posts until cutoff time"""

        print("\nscrolling through feed...")
        consecutive_old_posts = 0
        max_consecutive_old = 5  # stop after seeing 5 consecutive old posts
        scroll_count = 0

        # human behavior patterns
        last_pause_scroll = 0
        reading_session = 0  # track when human is "reading intensely"

        while consecutive_old_posts < max_consecutive_old:
            scroll_count += 1

            # collect visible posts
            try:
                new_posts, has_old_post = await self._collect_visible_posts(page)
            except Exception:
                # browser was closed
                print("\nbrowser closed, saving collected posts...")
                break

            if has_old_post:
                consecutive_old_posts += 1
            else:
                consecutive_old_posts = 0

            # progress update
            print(f"\rscroll {scroll_count}: {len(self.posts)} posts collected, "
                  f"{len(self.seen_ids)} unique seen", end="", flush=True)

            # human-like scroll patterns with high variance
            # sometimes fast scrolling (skimming), sometimes slow (reading)

            if random.random() < 0.15:
                # fast skim mode - quick scrolls
                scroll_distance = random.randint(500, 900)
                await self._smooth_scroll(page, scroll_distance, speed="fast")
                await self._human_delay(400, 800)
            elif random.random() < 0.2:
                # slow reading mode - small scrolls with long pauses
                scroll_distance = random.randint(150, 350)
                await self._smooth_scroll(page, scroll_distance, speed="slow")
                await self._human_delay(2000, 4500)
            else:
                # normal scrolling with variable distance
                scroll_distance = random.randint(250, 600)
                try:
                    await self._smooth_scroll(page, scroll_distance, speed="normal")
                except Exception:
                    print("\nbrowser closed, saving collected posts...")
                    break
                # variable delay
                await self._human_delay(800, 2200)

            # occasional long pause (checking phone, got distracted, reading a thread)
            if random.random() < 0.08:
                pause_duration = random.choice([
                    (3000, 5000),   # short distraction
                    (5000, 10000),  # medium distraction (checking notification)
                    (10000, 20000), # long pause (reading replies or got distracted)
                ])
                await self._human_delay(*pause_duration)

            # occasional scroll back up (re-reading something interesting)
            if random.random() < 0.07:
                back_scroll = random.randint(80, 250)
                try:
                    await self._smooth_scroll(page, -back_scroll, speed="slow")
                except Exception:
                    break
                await self._human_delay(1500, 3500)  # reading what caught attention
                # then scroll back down past where we were
                forward_scroll = random.randint(back_scroll + 50, back_scroll + 200)
                try:
                    await self._smooth_scroll(page, forward_scroll, speed="normal")
                except Exception:
                    break
                await self._human_delay(500, 1000)

            # occasional rapid multi-scroll (quickly getting past uninteresting content)
            if random.random() < 0.05:
                for _ in range(random.randint(2, 4)):
                    quick_scroll = random.randint(400, 700)
                    try:
                        await self._smooth_scroll(page, quick_scroll, speed="fast")
                    except Exception:
                        break
                    await self._human_delay(200, 500)

            # tiny micro-adjustments (human fine-tuning scroll position)
            if random.random() < 0.12:
                micro = random.randint(-30, 30)
                if micro != 0:
                    try:
                        await page.evaluate(f"window.scrollBy(0, {micro})")
                    except Exception:
                        pass
                    await self._human_delay(100, 300)

        print()  # newline after progress

    async def _smooth_scroll(self, page: Page, distance: int, speed: str = "normal"):
        """perform smooth scroll animation with variable speed"""

        # adjust duration based on speed
        if speed == "fast":
            duration = random.randint(150, 300)
        elif speed == "slow":
            duration = random.randint(500, 900)
        else:  # normal
            duration = random.randint(300, 600)

        # add slight randomness to make it less mechanical
        duration += random.randint(-50, 50)
        duration = max(100, duration)  # ensure minimum

        # smooth scroll using js animation
        await page.evaluate(f"""
            (async () => {{
                const distance = {distance};
                const duration = {duration};
                const start = window.scrollY;
                const startTime = performance.now();

                // use different easing functions for variety
                const easingType = {random.randint(0, 2)};

                function easeInOutQuad(t) {{
                    return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
                }}

                function easeOutCubic(t) {{
                    return 1 - Math.pow(1 - t, 3);
                }}

                function easeInOutSine(t) {{
                    return -(Math.cos(Math.PI * t) - 1) / 2;
                }}

                function ease(t) {{
                    if (easingType === 0) return easeInOutQuad(t);
                    if (easingType === 1) return easeOutCubic(t);
                    return easeInOutSine(t);
                }}

                function step(currentTime) {{
                    const elapsed = currentTime - startTime;
                    const progress = Math.min(elapsed / duration, 1);
                    const eased = ease(progress);
                    window.scrollTo(0, start + distance * eased);
                    if (progress < 1) {{
                        requestAnimationFrame(step);
                    }}
                }}

                requestAnimationFrame(step);

                // wait for animation to complete
                await new Promise(resolve => setTimeout(resolve, duration + 50));
            }})();
        """)

    async def _collect_visible_posts(self, page: Page) -> tuple[int, bool]:
        """collect all visible posts, returns (new_count, found_old_post)"""

        new_count = 0
        found_old = False

        try:
            tweet_elements = await page.query_selector_all('[data-testid="tweet"]')
        except Exception:
            # browser might have been closed
            return 0, True

        for tweet_el in tweet_elements:
            try:
                post = await self._parse_tweet(page, tweet_el)
                if post and post.id not in self.seen_ids:
                    self.seen_ids.add(post.id)

                    # check if post is within our time window
                    if post.timestamp >= self.cutoff_time:
                        self.posts.append(post)
                        new_count += 1
                    else:
                        found_old = True
            except Exception:
                # skip posts that can't be parsed
                continue

        return new_count, found_old

    async def _parse_tweet(self, page: Page, tweet_el) -> Post | None:
        """parse a tweet element into a Post object"""

        try:
            # get tweet link for id extraction
            link_el = await tweet_el.query_selector('a[href*="/status/"]')
            if not link_el:
                return None

            href = await link_el.get_attribute("href")
            if not href:
                return None

            # extract post id from url
            match = re.search(r"/status/(\d+)", href)
            if not match:
                return None
            post_id = match.group(1)

            # check for repost indicator
            repost_el = await tweet_el.query_selector('[data-testid="socialContext"]')
            is_repost = False
            reposted_by = None
            if repost_el:
                repost_text = await repost_el.inner_text()
                if "reposted" in repost_text.lower():
                    is_repost = True
                    reposted_by = repost_text.replace(" reposted", "").strip()

            # get author info
            author_el = await tweet_el.query_selector('[data-testid="User-Name"]')
            if not author_el:
                return None

            author_text = await author_el.inner_text()
            author_lines = author_text.split("\n")
            author_name = author_lines[0] if author_lines else "Unknown"
            author_handle = ""
            for line in author_lines:
                if line.startswith("@"):
                    author_handle = line
                    break

            # get tweet content
            content_el = await tweet_el.query_selector('[data-testid="tweetText"]')
            content = ""
            if content_el:
                content = await content_el.inner_text()

            # get timestamp
            time_el = await tweet_el.query_selector("time")
            timestamp = datetime.now(timezone.utc)
            if time_el:
                datetime_attr = await time_el.get_attribute("datetime")
                if datetime_attr:
                    timestamp = datetime.fromisoformat(datetime_attr.replace("Z", "+00:00"))

            # get engagement metrics
            likes = await self._get_metric(tweet_el, "like")
            reposts = await self._get_metric(tweet_el, "retweet")
            replies = await self._get_metric(tweet_el, "reply")
            views = await self._get_metric(tweet_el, "analytics")

            # construct url
            url = f"https://x.com{href}" if not href.startswith("http") else href

            return Post(
                id=post_id,
                author_handle=author_handle,
                author_name=author_name,
                content=content,
                timestamp=timestamp,
                url=url,
                likes=likes,
                reposts=reposts,
                replies=replies,
                views=views,
                is_repost=is_repost,
                reposted_by=reposted_by,
            )
        except Exception:
            return None

    async def _get_metric(self, tweet_el, metric_name: str) -> int:
        """extract engagement metric from tweet"""

        try:
            el = await tweet_el.query_selector(f'[data-testid="{metric_name}"]')
            if el:
                text = await el.inner_text()
                # handle K, M suffixes
                text = text.strip().upper()
                if not text:
                    return 0
                multiplier = 1
                if text.endswith("K"):
                    multiplier = 1000
                    text = text[:-1]
                elif text.endswith("M"):
                    multiplier = 1000000
                    text = text[:-1]
                try:
                    return int(float(text) * multiplier)
                except ValueError:
                    return 0
        except Exception:
            pass
        return 0

    async def _human_delay(self, min_ms: int, max_ms: int):
        """add human-like variable delay"""
        delay = random.randint(min_ms, max_ms) / 1000
        # add occasional micro-jitter
        if random.random() < 0.3:
            delay += random.uniform(0.05, 0.2)
        await asyncio.sleep(delay)

    def _get_authors(self) -> set[str]:
        """get unique author handles"""
        return {p.author_handle for p in self.posts}

    def _export_xml(self):
        """export posts to xml grouped by author"""

        # group posts by author
        authors: dict[str, list[Post]] = {}
        for post in self.posts:
            key = post.author_handle or "unknown"
            if key not in authors:
                authors[key] = []
            authors[key].append(post)

        # sort posts within each author by timestamp (newest first)
        for posts in authors.values():
            posts.sort(key=lambda p: p.timestamp, reverse=True)

        # build xml
        root = Element("feed")
        root.set("generated", datetime.now(timezone.utc).isoformat())
        root.set("hours", str(self.hours))
        root.set("post_count", str(len(self.posts)))
        root.set("author_count", str(len(authors)))

        # sort authors by post count (most active first)
        sorted_authors = sorted(authors.items(), key=lambda x: len(x[1]), reverse=True)

        for handle, posts in sorted_authors:
            author_el = SubElement(root, "author")
            author_el.set("handle", handle)
            author_el.set("name", posts[0].author_name if posts else "")
            author_el.set("post_count", str(len(posts)))

            for post in posts:
                post_el = SubElement(author_el, "post")
                post_el.set("id", post.id)
                post_el.set("url", post.url)
                post_el.set("timestamp", post.timestamp.isoformat())

                if post.is_repost and post.reposted_by:
                    post_el.set("is_repost", "true")
                    post_el.set("reposted_by", post.reposted_by)

                content_el = SubElement(post_el, "content")
                content_el.text = post.content

                metrics_el = SubElement(post_el, "metrics")
                metrics_el.set("likes", str(post.likes))
                metrics_el.set("reposts", str(post.reposts))
                metrics_el.set("replies", str(post.replies))
                metrics_el.set("views", str(post.views))

        # prettify and save
        xml_str = tostring(root, encoding="unicode")
        pretty_xml = minidom.parseString(xml_str).toprettyxml(indent="  ")

        # remove extra blank lines that minidom adds
        lines = [line for line in pretty_xml.split("\n") if line.strip()]
        pretty_xml = "\n".join(lines)

        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        # handle duplicate filenames by adding number suffix
        final_path = self._get_unique_path(self.output_path)
        final_path.write_text(pretty_xml, encoding="utf-8")
        self.output_path = final_path  # update for reporting

    def _get_unique_path(self, path: Path) -> Path:
        """get unique file path by adding number suffix if file exists"""

        if not path.exists():
            return path

        stem = path.stem
        suffix = path.suffix
        parent = path.parent

        counter = 1
        while True:
            new_path = parent / f"{stem}_{counter}{suffix}"
            if not new_path.exists():
                return new_path
            counter += 1


def parse_args():
    """parse command line arguments"""

    parser = argparse.ArgumentParser(
        description="Scrape your X following feed and export to XML",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # scrape following feed (recent/chronological)
  %(prog)s --feed for-you           # scrape "for you" algorithmic feed
  %(prog)s --feed following-popular # scrape following feed sorted by popularity
  %(prog)s --hours 12               # scrape last 12 hours
  %(prog)s --headless               # run without browser window
  %(prog)s -o my_feed.xml           # custom output file
  %(prog)s --profile ~/.xscrape     # use persistent chrome profile

This script launches your real Chrome browser with remote debugging to avoid
bot detection. Your existing Chrome sessions and extensions will be available.
        """
    )

    parser.add_argument(
        "--hours", "-H",
        type=int,
        default=2,
        help="number of hours to look back (default: 2)"
    )

    parser.add_argument(
        "--headless",
        action="store_true",
        help="run browser in headless mode (no visible window)"
    )

    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path("dist/feed.xml"),
        help="output xml file path (default: dist/feed.xml)"
    )

    parser.add_argument(
        "--profile", "-p",
        type=Path,
        default=None,
        help="chrome user data directory for persistent login (default: ~/.xscrape-chrome)"
    )

    parser.add_argument(
        "--slow-mo",
        type=int,
        default=50,
        help="base slowdown in ms for browser actions (default: 50)"
    )

    parser.add_argument(
        "--port",
        type=int,
        default=9222,
        help="chrome remote debugging port (default: 9222)"
    )

    parser.add_argument(
        "--feed", "-f",
        choices=["for-you", "following-recent", "following-popular"],
        default="following-recent",
        help="feed mode: for-you (algorithm), following-recent (chronological), following-popular (top posts) (default: following-recent)"
    )

    return parser.parse_args()


async def main():
    args = parse_args()

    scraper = FeedScraper(
        hours=args.hours,
        headless=args.headless,
        output_path=args.output,
        user_data_dir=args.profile,
        slow_mo=args.slow_mo,
        debug_port=args.port,
        feed_mode=args.feed,
    )

    await scraper.run()


if __name__ == "__main__":
    asyncio.run(main())
