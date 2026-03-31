"""
jhoo — Job Scraper
Scrapes job postings from Remotive RSS and saves new ones to Supabase.
Run this on Computer B after Cowork sessions, or let schedule_setup.bat handle it.

Setup:
    pip install -r requirements.txt

Usage:
    python scraper.py
"""

import os
import hashlib
from datetime import datetime, timezone
from dotenv import load_dotenv
from supabase import create_client
import requests
import feedparser

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ── SKIP FILTERS ─────────────────────────────────────────────────────────────
SKIP_TITLE_KEYWORDS = [
    "sdr", "sales development representative", "intern", "junior",
    "graduate", "trainee", "entry level",
]

SKIP_DESCRIPTION_KEYWORDS = [
    "commission only", "no base salary", "commission-only",
    "100% commission-based", "commission-based compensation", "no base pay",
    "uncapped commission", "earn up to", "unlimited earning potential",
    "ote only", "straight commission",
    "french required", "german required", "spanish required",
    "must be based in", "must relocate",
    "field sales",
    "must be fluent in french", "must be fluent in german",
    "deutschkenntnisse", "langue française", "muttersprache",
]

SKIP_LOCATIONS = [
    "nigeria", "kenya", "south africa", "egypt", "morocco", "ghana",
    "ethiopia", "tanzania", "uganda", "senegal", "cameroon",
    "france", "germany", "berlin", "munich", "hamburg", "frankfurt",
]


def posting_hash(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()


def is_skip_title(title: str) -> bool:
    t = title.lower()
    return any(kw in t for kw in SKIP_TITLE_KEYWORDS)


def is_skip_description(description: str) -> bool:
    d = description.lower()
    return any(kw in d for kw in SKIP_DESCRIPTION_KEYWORDS)


def is_skip_location(location: str) -> bool:
    loc = location.lower()
    return any(kw in loc for kw in SKIP_LOCATIONS)


def scrape_remotive_rss():
    """Scrape Remotive RSS feed and save new sales jobs to Supabase."""
    rss_urls = ["https://remotive.com/remote-jobs/sales-business/feed"]

    saved = 0
    skipped = 0

    for rss_url in rss_urls:
        print(f"Fetching: {rss_url}")
        try:
            feed = feedparser.parse(rss_url)
        except Exception as e:
            print(f"  Feed error: {e}")
            continue

        entries = feed.entries
        print(f"  Found {len(entries)} entries")

        for entry in entries:
            title = entry.get("title", "").strip()
            apply_url = entry.get("link", "").strip()
            company_name = entry.get("author", "").strip() or entry.get("tags", [{}])[0].get("term", "") if entry.get("tags") else ""
            location = entry.get("location", "Remote")
            description = entry.get("summary", "") or entry.get("content", [{}])[0].get("value", "") if entry.get("content") else ""

            # Title filter
            if is_skip_title(title):
                skipped += 1
                continue

            # Description filter
            if is_skip_description(description):
                skipped += 1
                continue

            # Location filter
            if is_skip_location(location):
                skipped += 1
                continue

            url_hash = posting_hash(apply_url)

            try:
                supabase.table("jobs").insert({
                    "title": title,
                    "company_name": company_name,
                    "location": location or "Remote",
                    "remote_type": "remote",
                    "apply_url": apply_url,
                    "source_site": "remotive",
                    "raw_description": description,
                    "status": "new",
                    "posting_hash": url_hash,
                    "date_collected": datetime.now(timezone.utc).isoformat(),
                }, upsert=False).execute()
                saved += 1
                print(f"  + {title[:60]} @ {company_name}")
            except Exception as e:
                err = str(e)
                if "duplicate" in err.lower() or "unique" in err.lower():
                    skipped += 1
                else:
                    print(f"  Save error ({title[:40]}): {e}")

    print(f"\nRemotive: saved {saved}, skipped {skipped}")
    return saved


def main():
    print(f"\n{'='*50}")
    print(f"jhoo Scraper — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}\n")

    total = scrape_remotive_rss()

    print(f"\n{'='*50}")
    print(f"Scrape complete. Total new jobs saved: {total}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
