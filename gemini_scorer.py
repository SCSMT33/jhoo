"""
jhoo — Job Scorer
Reads unscored jobs from Supabase, scores each one using Groq,
writes results back. Run this after each Cowork browsing session.

Setup:
    pip install supabase groq python-dotenv

Usage:
    python gemini_scorer.py
"""

import os
import json
import hashlib
import time
from datetime import datetime, timezone
from dotenv import load_dotenv
from supabase import create_client
from groq import Groq

load_dotenv()

# ── CONFIG ──────────────────────────────────────────────────────────────────
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
GROQ_API_KEY = os.environ["GROQ_API_KEY"]

CANDIDATE_PROFILE = """
Name: Chase Anderson
Nationality: American, based in Romania (can work remotely from Europe)
Experience: 11+ years full-cycle B2B SaaS and AI sales

Key strengths:
- Full-cycle enterprise and mid-market AE (prospecting through close)
- SDR hiring, coaching and team management
- GTM strategy and outbound execution for early-stage startups
- Startup zero-to-revenue experience
- Tools: HubSpot, LinkedIn Sales Navigator, Apollo, AI automation

Notable achievements:
- 800%+ ARR growth at Eyeware (eye-tracking SaaS)
- 120% quota attainment, closed AMD as enterprise deal
- Built sales process from scratch at multiple companies
- MBA, Montana USA 2017

Target roles: Account Executive, Sales Manager, Head of Sales, Sales Director,
International Sales Manager, Business Development Manager, Sales Lead

Ideal company: 10-150 person SaaS or AI startup, remote-first, English only,
European HQ or global remote, base salary + commission compensation

Hard requirements:
- Must offer base salary + commission (commission-only = score 0)
- Must be remote or remote-friendly from Romania/Europe
- English must be the working language (French/German/other required = score 0)
- Must NOT require relocation to a specific city
- Must NOT be field sales requiring constant travel
- Company must NOT be based in Africa
"""

HARD_NO_SCORE = 0
HARD_NO_REASONS = [
    "commission only", "commission-only", "no base", "100% commission",
    "french required", "german required", "spanish required",
    "must be based in london", "must relocate", "field sales",
    "must be fluent in french", "must be fluent in german",
]

# ── INIT ─────────────────────────────────────────────────────────────────────
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
client = Groq(api_key=GROQ_API_KEY)


def load_avoid_companies():
    """Load the list of companies to auto-skip."""
    result = supabase.table("companies").select("name").eq("engagement_level", "avoid").execute()
    return {row["name"].lower().strip() for row in result.data}


def load_reference_companies():
    """Load close/target companies as scoring context."""
    result = supabase.table("companies").select("name,industry,size,notes,engagement_level")\
        .in_("engagement_level", ["close", "interview", "target"]).execute()
    lines = []
    for c in result.data:
        lines.append(f"- {c['name']} ({c['engagement_level']}): {c.get('notes','')}")
    return "\n".join(lines)


def is_hard_no(job):
    """Quick string check before sending to Groq — saves API calls."""
    text = (job.get("raw_description", "") + " " + job.get("title", "")).lower()
    for phrase in HARD_NO_REASONS:
        if phrase in text:
            return True, f"Hard filter matched: '{phrase}'"
    return False, None


def score_job_with_gemini(job, reference_companies):
    """Send job to Groq, get back score + summary."""
    prompt = f"""
You are a job fit scorer. Score this job posting for the candidate below.
Return ONLY valid JSON, no markdown, no explanation outside the JSON.

CANDIDATE:
{CANDIDATE_PROFILE}

REFERENCE COMPANIES (companies the candidate got far with — use as similarity guide):
{reference_companies}

JOB POSTING:
Title: {job.get('title', '')}
Company: {job.get('company_name', '')}
Location: {job.get('location', '')}
Salary: {job.get('salary', 'not listed')}
Description:
{job.get('raw_description', '')[:3000]}

SCORING RULES:
- Score 0 if: commission only, non-English required, must relocate, field sales, Africa-based
- Score 1-4 if: poor fit (wrong level, wrong industry, wrong comp model)
- Score 5-6 if: decent fit but missing key criteria
- Score 7-8 if: good fit, matches profile well
- Score 9-10 if: excellent fit, similar to reference companies, right level, right comp

Return this exact JSON:
{{
  "fit_score": <integer 0-10>,
  "score_summary": "<2 sentences max: why it fits or doesn't>",
  "language_flag": <true if non-English language required, else false>,
  "similar_company_flag": <true if similar to reference companies, else false>
}}
"""
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        text = response.choices[0].message.content.strip()
        # Strip markdown fences if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text.strip())
    except Exception as e:
        print(f"  Groq error: {e}")
        return None


def score_unscored_jobs():
    """Main loop — fetch unscored jobs, score them, save back."""
    print(f"\n{'='*50}")
    print(f"jhoo Scorer — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*50}")

    avoid_companies = load_avoid_companies()
    reference_companies = load_reference_companies()
    print(f"Loaded {len(avoid_companies)} avoid companies")
    print(f"Loaded reference companies for scoring context")

    # Fetch unscored jobs
    result = supabase.table("jobs").select("*")\
        .is_("fit_score", "null")\
        .eq("status", "new")\
        .execute()

    jobs = result.data
    print(f"Found {len(jobs)} unscored jobs\n")

    if not jobs:
        print("Nothing to score. Run a Cowork session first.")
        return

    scored = 0
    skipped = 0

    for i, job in enumerate(jobs):
        company_lower = job.get("company_name", "").lower().strip()
        title = job.get("title", "Unknown")
        company = job.get("company_name", "Unknown")

        print(f"[{i+1}/{len(jobs)}] {title} @ {company}")

        # Auto-skip avoid companies
        if company_lower in avoid_companies:
            print(f"  → SKIPPED (avoid list)")
            supabase.table("jobs").update({
                "fit_score": None,
                "score_summary": "Company is on your avoid list — previously rejected or blacklisted.",
                "status": "skipped",
                "scored_at": datetime.now(timezone.utc).isoformat()
            }).eq("id", job["id"]).execute()
            skipped += 1
            continue

        # Hard no check (no Groq call needed)
        hard_no, reason = is_hard_no(job)
        if hard_no:
            print(f"  → HARD NO: {reason}")
            supabase.table("jobs").update({
                "fit_score": None,
                "score_summary": f"Auto-filtered: {reason}",
                "status": "skipped",
                "scored_at": datetime.now(timezone.utc).isoformat()
            }).eq("id", job["id"]).execute()
            skipped += 1
            continue

        # Score with Groq
        result_data = score_job_with_gemini(job, reference_companies)
        time.sleep(5)
        if result_data:
            score = result_data.get("fit_score", 0)
            print(f"  → Score: {score}/10 — {result_data.get('score_summary','')[:80]}")
            supabase.table("jobs").update({
                "fit_score": score if score >= 1 else None,
                "score_summary": result_data.get("score_summary", ""),
                "language_flag": result_data.get("language_flag", False),
                "similar_company_flag": result_data.get("similar_company_flag", False),
                "status": "skipped" if score <= 3 else "new",
                "scored_at": datetime.now(timezone.utc).isoformat()
            }).eq("id", job["id"]).execute()
            scored += 1
        else:
            print(f"  → Groq failed, skipping")

    print(f"\n{'='*50}")
    print(f"Done. Scored: {scored} | Auto-skipped: {skipped}")
    print(f"{'='*50}\n")


if __name__ == "__main__":
    score_unscored_jobs()
