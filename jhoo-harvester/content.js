// jhoo Harvester — content.js
// Silently captures LinkedIn job details as you browse, sends to Supabase on demand.

const SUPABASE_URL = "https://gjdxhacfqyasprdribaj.supabase.co/rest/v1/jobs";
const SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdqZHhoYWNmcXlhc3ByZHJpYmFqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQ4ODk0MzUsImV4cCI6MjA5MDQ2NTQzNX0.jjYUqC8xP-IEPMWY6a5KQXTttJrCqtq0M3A9a_Lfsfs";

let capturedJobs = [];
let harvestBtn = null;
let captureTimeout = null;
let lastCapturedUrl = null;

// ── HASH ──────────────────────────────────────────────────────────────────────
function hashUrl(url) {
  return Math.abs(url.split('').reduce((a, b) => {
    a = ((a << 5) - a) + b.charCodeAt(0);
    return a & a;
  }, 0)).toString();
}

// ── SELECTORS ─────────────────────────────────────────────────────────────────
function getText(selectors, root = document) {
  for (const sel of selectors) {
    const el = root.querySelector(sel);
    if (el && el.innerText.trim()) return el.innerText.trim();
  }
  return "";
}

function extractJob() {
  const applyUrl = window.location.href.split('?')[0];

  // Avoid re-capturing the same URL
  if (applyUrl === lastCapturedUrl) return null;

  const title = getText([
    ".job-details-jobs-unified-top-card__job-title h1",
    ".jobs-unified-top-card__job-title h1",
    ".t-24.t-bold.jobs-unified-top-card__job-title",
    "h1.job-title",
    ".job-details-jobs-unified-top-card__job-title",
    "h1"
  ]);

  const company_name = getText([
    ".job-details-jobs-unified-top-card__company-name a",
    ".job-details-jobs-unified-top-card__company-name",
    ".jobs-unified-top-card__company-name a",
    ".jobs-unified-top-card__company-name",
    ".topcard__org-name-link",
    ".topcard__org-name"
  ]);

  const location = getText([
    ".job-details-jobs-unified-top-card__primary-description-container .tvm__text",
    ".jobs-unified-top-card__bullet",
    ".jobs-unified-top-card__workplace-type",
    ".topcard__flavor--bullet",
    ".job-details-jobs-unified-top-card__workplace-type"
  ]);

  const raw_description = getText([
    ".jobs-description-content__text",
    ".jobs-box__html-content",
    ".jobs-description",
    ".description__text",
    "#job-details"
  ]);

  // Try to find a posted date — look for elements mentioning "ago" or a date
  let date_posted = null;
  const allText = document.querySelectorAll(
    ".jobs-unified-top-card__posted-date, .job-details-jobs-unified-top-card__primary-description-container span, .tvm__text"
  );
  for (const el of allText) {
    const t = el.innerText.trim();
    if (/\d+\s*(hour|day|week|month)s?\s*ago/i.test(t) || /posted/i.test(t)) {
      // Parse relative date to ISO
      const now = new Date();
      const match = t.match(/(\d+)\s*(hour|day|week|month)s?\s*ago/i);
      if (match) {
        const n = parseInt(match[1]);
        const unit = match[2].toLowerCase();
        const ms = { hour: 36e5, day: 864e5, week: 6048e5, month: 2592e6 }[unit] || 0;
        date_posted = new Date(now - n * ms).toISOString();
      }
      break;
    }
  }

  if (!title || !applyUrl) return null;

  return { title, company_name, location, raw_description, apply_url: applyUrl, date_posted };
}

// ── CAPTURE ───────────────────────────────────────────────────────────────────
function tryCapture() {
  const job = extractJob();
  if (!job) return;

  // Deduplicate by apply_url within session
  const exists = capturedJobs.some(j => j.apply_url === job.apply_url);
  if (exists) return;

  capturedJobs.push(job);
  lastCapturedUrl = job.apply_url;
  updateButton();
  console.log(`[jhoo] Captured: ${job.title} @ ${job.company_name}`);
}

// ── BUTTON ────────────────────────────────────────────────────────────────────
function createButton() {
  const btn = document.createElement("button");
  btn.id = "jhoo-harvest-btn";
  Object.assign(btn.style, {
    position: "fixed",
    bottom: "24px",
    right: "24px",
    background: "#22c55e",
    color: "white",
    fontWeight: "bold",
    fontSize: "15px",
    padding: "12px 20px",
    borderRadius: "8px",
    border: "none",
    cursor: "pointer",
    zIndex: "99999",
    boxShadow: "0 4px 12px rgba(0,0,0,0.3)",
    fontFamily: "system-ui, sans-serif",
    transition: "background 0.2s"
  });
  btn.textContent = "⚡ jhoo: 0 captured";
  btn.addEventListener("click", harvest);
  document.body.appendChild(btn);
  return btn;
}

function updateButton() {
  if (!harvestBtn) return;
  harvestBtn.textContent = `⚡ jhoo: ${capturedJobs.length} captured`;
}

function setButtonState(text, color, duration) {
  if (!harvestBtn) return;
  harvestBtn.textContent = text;
  harvestBtn.style.background = color;
  if (duration) {
    setTimeout(() => {
      harvestBtn.style.background = "#22c55e";
      updateButton();
    }, duration);
  }
}

// ── HARVEST ───────────────────────────────────────────────────────────────────
async function harvest() {
  if (capturedJobs.length === 0) {
    alert("No jobs captured yet — click some job listings first!");
    return;
  }

  const now = new Date().toISOString();
  const payload = capturedJobs.map(job => ({
    title: job.title,
    company_name: job.company_name,
    location: job.location || "Remote",
    remote_type: "remote",
    raw_description: job.raw_description,
    apply_url: job.apply_url,
    source_site: "linkedin",
    status: "new",
    date_collected: now,
    date_posted: job.date_posted || null,
    posting_hash: hashUrl(job.apply_url)
  }));

  setButtonState("Sending...", "#6c5ce7", null);

  try {
    const resp = await fetch(SUPABASE_URL, {
      method: "POST",
      headers: {
        "apikey": SUPABASE_KEY,
        "Authorization": `Bearer ${SUPABASE_KEY}`,
        "Content-Type": "application/json",
        "Prefer": "resolution=ignore-duplicates"
      },
      body: JSON.stringify(payload)
    });

    if (!resp.ok) {
      const errText = await resp.text();
      console.error("[jhoo] Supabase error:", errText);
      throw new Error(errText);
    }

    const count = capturedJobs.length;
    capturedJobs = [];
    lastCapturedUrl = null;
    setButtonState(`✅ jhoo: ${count} sent!`, "#0f9960", 3000);
  } catch (e) {
    console.error("[jhoo] Harvest failed:", e);
    setButtonState("❌ Error — check console", "#d63031", 3000);
  }
}

// ── OBSERVER ──────────────────────────────────────────────────────────────────
function startObserver() {
  const observer = new MutationObserver(() => {
    // Debounce: wait 1s after last DOM change before capturing
    clearTimeout(captureTimeout);
    captureTimeout = setTimeout(tryCapture, 1000);
  });

  observer.observe(document.body, {
    childList: true,
    subtree: true
  });
}

// ── INIT ──────────────────────────────────────────────────────────────────────
function init() {
  if (document.getElementById("jhoo-harvest-btn")) return;
  harvestBtn = createButton();
  startObserver();
  // Attempt capture on initial page load too
  setTimeout(tryCapture, 1500);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
