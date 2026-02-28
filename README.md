# xscrape

X (Twitter) following feed scraper with human-like scrolling behavior.

## Features

- Scrolls through your X following feed collecting posts
- Configurable time window (default: 24 hours)
- Human-like scrolling with variable jitter
- Exports to XML with posts grouped by author
- Supports headless mode
- Persistent browser profile for saved login

## Requirements

- Python 3.12+
- Playwright

## Installation

```bash
# create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# install dependencies
pip install -r requirements.txt

# install playwright browsers
playwright install chromium
```

## Usage

```bash
# basic usage - scrape last 24 hours
python xscrape.py

# scrape last 12 hours
python xscrape.py --hours 12

# run headless (no browser window)
python xscrape.py --headless

# custom output file
python xscrape.py -o my_feed.xml

# use persistent profile (saves login between runs)
python xscrape.py --profile ~/.xscrape
```

## Options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--hours` | `-H` | 24 | Hours to look back |
| `--headless` | | false | Run without browser window |
| `--output` | `-o` | feed.xml | Output XML file path |
| `--profile` | `-p` | none | Browser profile directory |
| `--slow-mo` | | 50 | Base slowdown in ms |

## Output Format

```xml
<?xml version="1.0" ?>
<feed generated="2024-01-15T12:00:00+00:00" hours="24" post_count="150" author_count="45">
  <author handle="@example" name="Example User" post_count="5">
    <post id="123456789" url="https://x.com/example/status/123456789" timestamp="2024-01-15T11:30:00+00:00">
      <content>Post content here...</content>
      <metrics likes="42" reposts="5" replies="3" views="1200"/>
    </post>
  </author>
</feed>
```

## Notes

- First run will prompt for login (unless using a saved profile)
- The scraper uses variable delays and scroll distances to mimic human behavior
- Stops scrolling after encountering posts older than the configured time window
