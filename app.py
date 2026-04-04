"""
jhoo — Job Review Web App
Local Flask web app for reviewing scored job postings.

Setup:
    pip install supabase python-dotenv flask

Usage:
    python app.py
    (or double-click run_app.bat)

Keyboard shortcuts (in browser):
    Y = open apply link in browser + mark applied
    N = skip (never show again)
    M = maybe (save for later)
    L = load all scores
"""

import os
import sys
from datetime import datetime, timezone
from dotenv import load_dotenv
from supabase import create_client
from flask import Flask, jsonify, request, render_template_string

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("ERROR: SUPABASE_URL and SUPABASE_KEY must be set in your .env file.")
    sys.exit(1)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>jhoo — Job Hunter</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #1a1a2e; color: #e0e0e0; font-family: 'Segoe UI', sans-serif; height: 100vh; display: flex; flex-direction: column; overflow: hidden; }

  /* Header */
  #header { background: #0f3460; padding: 12px 24px; display: flex; align-items: center; gap: 16px; flex-shrink: 0; }
  #header h1 { font-size: 22px; font-weight: 700; }
  #counter { font-size: 13px; color: #888; }
  #filter-btns { margin-left: auto; display: flex; gap: 6px; }
  .filter-btn { background: #1a1a2e; color: #888; border: 1px solid #333; padding: 5px 13px; border-radius: 4px; cursor: pointer; font-size: 13px; font-family: inherit; font-weight: 600; }
  .filter-btn:hover { border-color: #00d4aa; color: #e0e0e0; }
  .filter-btn.active { background: #00d4aa; color: #1a1a2e; border-color: #00d4aa; }

  /* Score row */
  #score-row { padding: 16px 30px 8px; display: flex; align-items: center; gap: 20px; flex-shrink: 0; }
  #score-badge { font-size: 52px; font-weight: 700; line-height: 1; color: #00d4aa; min-width: 64px; }
  #score-meta { display: flex; flex-direction: column; gap: 4px; }
  #similar-flag { font-size: 12px; font-weight: 700; color: #00d4aa; }
  #score-summary { font-size: 15px; color: #888; max-width: 620px; line-height: 1.4; }

  /* Card */
  #card { background: #16213e; margin: 0 30px; padding: 20px 24px; border-radius: 4px; flex-shrink: 0; }
  #card.similar { background: #1e3a2f; }
  #job-title { font-size: 22px; font-weight: 700; margin-bottom: 4px; }
  #job-company { font-size: 14px; color: #888; margin-bottom: 8px; }
  #job-meta { display: flex; gap: 20px; font-size: 14px; color: #888; align-items: center; }
  #job-salary { color: #00d4aa; font-weight: 700; }
  #job-date { color: #888; }
  #job-date.unknown { color: #555; }
  #apply-link { margin-left: auto; background: #0f3460; color: #00d4aa; border: 1px solid #00d4aa; padding: 4px 14px; border-radius: 4px; font-size: 12px; font-weight: 700; text-decoration: none; cursor: pointer; }
  #apply-link:hover { background: #00d4aa; color: #1a1a2e; }

  /* Company blurb */
  #blurb-wrapper { margin: 10px 30px 0; flex-shrink: 0; }
  #blurb-text { background: #16213e; color: #aaa; font-size: 15px; padding: 12px 18px; border-radius: 4px; line-height: 1.6; font-style: italic; }

  /* Buttons */
  #btn-row { padding: 14px 30px 16px; display: flex; gap: 12px; align-items: center; flex-shrink: 0; }
  .action-btn { font-family: inherit; font-size: 15px; font-weight: 700; border: none; padding: 10px 28px; border-radius: 4px; cursor: pointer; }
  #btn-yes   { background: #00b894; color: white; }
  #btn-maybe { background: #fdcb6e; color: #2d3436; }
  #btn-no    { background: #d63031; color: white; }
  #key-hint  { margin-left: auto; font-size: 11px; color: #555; }

  /* Empty state */
  #empty { display: none; flex: 1; align-items: center; justify-content: center; text-align: center; color: #888; font-size: 16px; line-height: 1.8; }
</style>
</head>
<body>

<div id="header">
  <h1>jhoo</h1>
  <span id="counter"></span>
  <div id="filter-btns">
    <button class="filter-btn active" onclick="setFilter('8plus')">8+</button>
    <button class="filter-btn" onclick="setFilter('7s')">7s</button>
    <button class="filter-btn" onclick="setFilter('6s')">6s</button>
    <button class="filter-btn" onclick="setFilter('5below')">5 &amp; below</button>
  </div>
</div>

<div id="score-row">
  <div id="score-badge">—</div>
  <div id="score-meta">
    <div id="similar-flag"></div>
    <div id="score-summary"></div>
  </div>
</div>

<div id="card">
  <div id="job-title"></div>
  <div id="job-company"></div>
  <div id="job-meta">
    <span id="job-location"></span>
    <span id="job-salary"></span>
    <span id="job-source"></span>
    <span id="job-date"></span>
    <a id="apply-link" href="#" target="_blank" rel="noopener">Open Job</a>
  </div>
</div>

<div id="blurb-wrapper">
  <div id="blurb-text"></div>
</div>

<div id="btn-row">
  <button class="action-btn" id="btn-yes"   onclick="action('applied')">✓  Apply  [Y]</button>
  <button class="action-btn" id="btn-maybe" onclick="action('maybe')">?  Maybe  [M]</button>
  <button class="action-btn" id="btn-no"    onclick="action('skipped')">✕  Skip   [N]</button>
  <span id="key-hint">Y / N / M</span>
</div>

<div id="empty">
  No jobs to review.<br>Run a Cowork session to collect more.
</div>

<script>
let jobs = [];
let idx = 0;

const FILTERS = {
  '8plus':  {min: 8,  max: 10},
  '7s':     {min: 7,  max: 7},
  '6s':     {min: 6,  max: 6},
  '5below': {min: 1,  max: 5},
};

async function setFilter(key) {
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  event.target.classList.add('active');
  const {min, max} = FILTERS[key];
  const res = await fetch(`/api/jobs?min=${min}&max=${max}`);
  jobs = await res.json();
  idx = 0;
  render();
}

function render() {
  const mainEls = ['score-row','card','btn-row'];
  if (idx >= jobs.length) {
    mainEls.forEach(id => document.getElementById(id).style.display = 'none');
    document.getElementById('empty').style.display = 'flex';
    document.getElementById('counter').textContent = 'All done';
    return;
  }
  document.getElementById('empty').style.display = 'none';
  mainEls.forEach(id => document.getElementById(id).style.display = '');
  document.getElementById('score-row').style.display = 'flex';
  document.getElementById('btn-row').style.display = 'flex';

  const job = jobs[idx];
  const score = job.fit_score ?? 0;
  const badge = document.getElementById('score-badge');
  badge.textContent = score;
  badge.style.color = score >= 7 ? '#00d4aa' : score >= 5 ? '#fdcb6e' : '#d63031';

  document.getElementById('similar-flag').textContent = job.similar_company_flag ? '★ Similar to companies you\\'ve liked' : '';
  document.getElementById('score-summary').textContent = job.score_summary || '';

  const card = document.getElementById('card');
  card.className = job.similar_company_flag ? 'similar' : '';

  document.getElementById('job-title').textContent = job.title || 'Unknown title';
  document.getElementById('job-company').textContent = job.company_name || '';
  document.getElementById('job-location').textContent = (job.location || '') + (job.remote_type ? '  •  ' + job.remote_type : '');
  document.getElementById('job-salary').textContent = job.salary || '';
  document.getElementById('job-source').textContent = job.source_site ? 'via ' + job.source_site : '';

  const dateEl = document.getElementById('job-date');
  if (job.date_posted) {
    const d = new Date(job.date_posted);
    dateEl.textContent = 'Posted ' + d.toLocaleDateString('en-US', {month:'short', day:'numeric'});
    dateEl.className = '';
  } else {
    dateEl.textContent = 'Posted: Unknown';
    dateEl.className = 'unknown';
  }

  const applyLink = document.getElementById('apply-link');
  applyLink.href = job.apply_url || '#';

  const blurb = job.company_blurb || '';
  const blurbWrapper = document.getElementById('blurb-wrapper');
  if (blurb) {
    document.getElementById('blurb-text').textContent = blurb;
    blurbWrapper.style.display = '';
  } else {
    blurbWrapper.style.display = 'none';
  }

  document.getElementById('counter').textContent = (idx + 1) + ' of ' + jobs.length + ' jobs';
}

async function action(status) {
  if (idx >= jobs.length) return;
  const job = jobs[idx];
  if (status === 'applied' && job.apply_url) window.open(job.apply_url, '_blank');
  await fetch('/api/jobs/' + job.id + '/status', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({status})
  });
  idx++;
  render();
}

document.addEventListener('keydown', e => {
  if (['INPUT','TEXTAREA'].includes(document.activeElement.tagName)) return;
  if (e.key === 'y' || e.key === 'Y') action('applied');
  if (e.key === 'n' || e.key === 'N') action('skipped');
  if (e.key === 'm' || e.key === 'M') action('maybe');
});

// Load default filter (8+) on startup
(async () => {
  const res = await fetch('/api/jobs?min=8&max=10');
  jobs = await res.json();
  render();
})();
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/api/jobs")
def get_jobs():
    min_score = int(request.args.get("min", 8))
    max_score = int(request.args.get("max", 10))
    query = (supabase.table("jobs").select("*")
             .eq("status", "new")
             .gte("fit_score", min_score)
             .lte("fit_score", max_score)
             .order("fit_score", desc=True)
             .limit(20))
    result = query.execute()
    return jsonify(result.data)


@app.route("/api/jobs/<job_id>/status", methods=["POST"])
def update_status(job_id):
    data = request.get_json()
    status = data.get("status")
    update = {"status": status}
    if status == "applied":
        update["applied_at"] = datetime.now(timezone.utc).isoformat()
    supabase.table("jobs").update(update).eq("id", job_id).execute()
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5007, debug=False)
