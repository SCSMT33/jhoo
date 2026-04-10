"""
jhoo — Rescore recent jobs
Fetches jobs with status 'new' or 'maybe' collected in the last 7 days,
resets their scores, and rescores them using Gemini (Groq fallback).

Usage:
    python rescore.py
"""

import os
import time
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from supabase import create_client

from gemini_scorer import score_job_with_gemini, load_avoid_companies, load_reference_companies

load_dotenv()

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def rescore_recent_jobs():
    print(f"\n{'='*50}")
    print(f"jhoo Rescore - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}")

    avoid_companies = load_avoid_companies()
    reference_companies = load_reference_companies()
    print(f"Loaded {len(avoid_companies)} avoid companies")
    print(f"Loaded reference companies for scoring context")

    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    result = supabase.table("jobs").select("*")\
        .in_("status", ["new", "maybe"])\
        .gte("date_collected", cutoff)\
        .execute()

    jobs = result.data
    total = len(jobs)
    print(f"Found {total} jobs to rescore\n")

    if not jobs:
        print("No recent jobs found with status 'new' or 'maybe'.")
        return

    scored = 0
    skipped = 0

    for i, job in enumerate(jobs):
        title = job.get("title", "Unknown")
        company = job.get("company_name", "Unknown")
        status = job.get("status", "")

        # Defensive skip (should already be filtered, but just in case)
        if status in ("applied", "skipped"):
            print(f"[{i+1}/{total}] {title} @ {company} -> SKIPPED (status={status})")
            skipped += 1
            continue

        print(f"[{i+1}/{total}] {title} @ {company}", end="", flush=True)

        # Reset score fields first
        supabase.table("jobs").update({
            "fit_score": None,
            "scored_at": None,
        }).eq("id", job["id"]).execute()

        # Rescore
        result_data = score_job_with_gemini(job, reference_companies)
        time.sleep(4)

        if result_data:
            score = result_data.get("fit_score", 0)
            print(f" -> Score: {score}/10")
            supabase.table("jobs").update({
                "fit_score": score if score >= 1 else None,
                "score_summary": result_data.get("score_summary", ""),
                "language_flag": result_data.get("language_flag", False),
                "similar_company_flag": result_data.get("similar_company_flag", False),
                "scored_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", job["id"]).execute()
            scored += 1
        else:
            print(f" -> Both Gemini and Groq failed, skipping")
            skipped += 1

    print(f"\n{'='*50}")
    print(f"Done. Rescored: {scored} | Skipped: {skipped}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    rescore_recent_jobs()
