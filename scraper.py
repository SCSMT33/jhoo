"""
jhoo — Job Scraper
Scrapes job postings from multiple sources and saves new ones to Supabase.
Run this on Computer B after Cowork sessions, or let schedule_setup.bat handle it.

Setup:
    pip install -r requirements.txt

Usage:
    python scraper.py
"""

import os
import re
import hashlib
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from supabase import create_client
import requests
import feedparser

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
ADZUNA_APP_ID = os.environ.get("ADZUNA_APP_ID", "")
ADZUNA_APP_KEY = os.environ.get("ADZUNA_APP_KEY", "")

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


def strip_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&quot;", '"', text)
    return re.sub(r"\s{2,}", " ", text).strip()


def is_skip_title(title: str) -> bool:
    t = title.lower()
    return any(kw in t for kw in SKIP_TITLE_KEYWORDS)


def is_skip_description(description: str) -> bool:
    d = description.lower()
    return any(kw in d for kw in SKIP_DESCRIPTION_KEYWORDS)


def is_skip_location(location: str) -> bool:
    loc = location.lower()
    return any(kw in loc for kw in SKIP_LOCATIONS)


CUTOFF_DAYS = 14


def save_job(title, company_name, location, apply_url, description, source_site, date_posted=None, company_blurb=None):
    """Apply filters and save one job to Supabase. Returns 'saved', 'skipped', or 'error'."""
    if not title or not apply_url:
        return "skipped"
    if is_skip_title(title):
        return "skipped"
    if is_skip_description(description):
        return "skipped"
    if is_skip_location(location):
        return "skipped"

    now = datetime.now(timezone.utc)

    # Date filter: skip jobs older than 14 days (only if date is known)
    if date_posted is not None:
        if (now - date_posted).days > CUTOFF_DAYS:
            return "skipped"
        date_posted_iso = date_posted.isoformat()
    else:
        date_posted_iso = None  # no date available — store NULL, never fabricate

    try:
        supabase.table("jobs").insert({
            "title": title,
            "company_name": company_name,
            "location": location or "Remote",
            "remote_type": "remote",
            "apply_url": apply_url,
            "source_site": source_site,
            "raw_description": description,
            "status": "new",
            "posting_hash": posting_hash(apply_url),
            "date_collected": now.isoformat(),
            "date_posted": date_posted_iso,
            "company_blurb": company_blurb,
        }, upsert=False).execute()
        return "saved"
    except Exception as e:
        err = str(e)
        if "duplicate" in err.lower() or "unique" in err.lower():
            return "skipped"
        print(f"  Save error ({title[:40]}): {e}")
        return "error"


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

            date_posted = None
            if entry.get("published_parsed"):
                import time as _time
                date_posted = datetime.fromtimestamp(_time.mktime(entry.published_parsed), tz=timezone.utc)

            result = save_job(title, company_name, location, apply_url, description, "remotive", date_posted)
            if result == "saved":
                saved += 1
                print(f"  + {title[:60]} @ {company_name}")
            else:
                skipped += 1

    print(f"Remotive RSS: saved {saved}, skipped {skipped}")
    return saved


def scrape_himalayas():
    """Scrape Himalayas API for remote sales jobs."""
    url = "https://himalayas.app/jobs/api?q=sales&limit=100"
    print(f"Fetching: {url}")

    saved = 0
    skipped = 0

    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  Himalayas fetch error: {e}")
        return 0

    jobs = data.get("jobs", [])
    print(f"  Found {len(jobs)} entries")

    for job in jobs:
        title = (job.get("title") or "").strip()
        company_name = (job.get("company", {}).get("name") or "").strip()
        location_parts = job.get("locationRestrictions") or []
        location = ", ".join(location_parts) if location_parts else "Remote"
        apply_url = (job.get("applicationUrl") or "").strip()
        description = job.get("description") or ""
        company_blurb = (job.get("excerpt") or "").strip() or None

        date_posted = None
        raw_date = job.get("pubDate") or job.get("createdAt") or job.get("postedAt") or job.get("publishedAt")
        if raw_date:
            try:
                date_posted = datetime.fromisoformat(str(raw_date).replace("Z", "+00:00"))
            except Exception:
                pass

        result = save_job(title, company_name, location, apply_url, description, "himalayas", date_posted, company_blurb)
        if result == "saved":
            saved += 1
            print(f"  + {title[:60]} @ {company_name}")
        else:
            skipped += 1

    print(f"Himalayas: saved {saved}, skipped {skipped}")
    return saved


def scrape_remoteok():
    """Scrape RemoteOK API for sales jobs."""
    url = "https://remoteok.com/api?tag=sales"
    print(f"Fetching: {url}")

    saved = 0
    skipped = 0

    try:
        resp = requests.get(url, timeout=20, headers={"User-Agent": "jhoo-scraper/1.0"})
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  RemoteOK fetch error: {e}")
        return 0

    # First item is metadata, skip it
    jobs = data[1:] if len(data) > 1 else []
    print(f"  Found {len(jobs)} entries")

    for job in jobs:
        title = (job.get("position") or "").strip()
        company_name = (job.get("company") or "").strip()
        location = (job.get("location") or "Remote").strip()
        apply_url = (job.get("url") or "").strip()
        description = job.get("description") or ""
        company_blurb = strip_html(description)[:300].strip() or None

        date_posted = None
        raw_date = job.get("date") or job.get("epoch")
        if raw_date:
            try:
                if isinstance(raw_date, (int, float)):
                    date_posted = datetime.fromtimestamp(raw_date, tz=timezone.utc)
                else:
                    date_posted = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
            except Exception:
                pass

        result = save_job(title, company_name, location, apply_url, description, "remoteok", date_posted, company_blurb)
        if result == "saved":
            saved += 1
            print(f"  + {title[:60]} @ {company_name}")
        else:
            skipped += 1

    print(f"RemoteOK: saved {saved}, skipped {skipped}")
    return saved


def scrape_adzuna():
    """Scrape Adzuna API across European countries for sales AE jobs."""
    if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:
        print("Adzuna: skipping (ADZUNA_APP_ID / ADZUNA_APP_KEY not set in .env)")
        return 0

    countries = ["gb", "nl", "pl", "at", "ch", "be"]
    saved = 0
    skipped = 0

    for country in countries:
        url = (
            f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
            f"?app_id={ADZUNA_APP_ID}&app_key={ADZUNA_APP_KEY}"
            f"&results_per_page=50&what=sales+account+executive"
            f"&content-type=application/json"
        )
        print(f"Fetching Adzuna [{country.upper()}]: {url[:80]}...")

        try:
            resp = requests.get(url, timeout=20)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"  Adzuna [{country}] fetch error: {e}")
            continue

        jobs = data.get("results", [])
        print(f"  Found {len(jobs)} entries")

        for job in jobs:
            title = (job.get("title") or "").strip()
            company_name = (job.get("company", {}).get("display_name") or "").strip()
            location = (job.get("location", {}).get("display_name") or "").strip()
            apply_url = (job.get("redirect_url") or "").strip()
            description = job.get("description") or ""
            company_blurb = strip_html(description)[:300].strip() or None

            date_posted = None
            raw_date = job.get("created")
            if raw_date:
                try:
                    date_posted = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
                except Exception:
                    pass

            result = save_job(title, company_name, location, apply_url, description, "adzuna", date_posted, company_blurb)
            if result == "saved":
                saved += 1
                print(f"  + {title[:60]} @ {company_name}")
            else:
                skipped += 1

    print(f"Adzuna: saved {saved}, skipped {skipped}")
    return saved


def main():
    print(f"\n{'='*50}")
    print(f"jhoo Scraper - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}\n")

    total = 0
    total += scrape_remotive_rss()
    print()
    total += scrape_himalayas()
    print()
    total += scrape_remoteok()
    print()
    total += scrape_adzuna()

    print(f"\n{'='*50}")
    print(f"Scrape complete. Total new jobs saved: {total}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
