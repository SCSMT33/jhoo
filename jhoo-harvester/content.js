// jhoo Harvester — content.js
// Silently captures LinkedIn job details as you browse, sends to Supabase on demand.

const SUPABASE_URL = "https://gjdxhacfqyasprdribaj.supabase.co/rest/v1/jobs";
const SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdqZHhoYWNmcXlhc3ByZHJpYmFqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQ4ODk0MzUsImV4cCI6MjA5MDQ2NTQzNX0.jjYUqC8xP-IEPMWY6a5KQXTttJrCqtq0M3A9a_Lfsfs";

let capturedJobs = [];
let harvestBtn = null;
let debounceTimer = null;
let lastCapturedUrl = null;
let observerInstance = null;
let currentUrl = window.location.href;

// ── HASH ──────────────────────────────────────────────────────────────────────
function hashUrl(url) {
  return Math.abs(url.split('').reduce((a, b) => {
    a = ((a << 5) - a) + b.charCodeAt(0);
    return a & a;
  }, 0)).toString();
}

// ── URL ───────────────────────────────────────────────────────────────────────
function getCurrentJobUrl() {
  // 1. Look for an <a> with /jobs/view/ href inside the detail panel
  const detailPanel = document.querySelector(
    ".jobs-search__job-details--wrapper, .jobs-details, .job-details-jobs-unified-top-card__container, [data-view-name='job-details']"
  );
  if (detailPanel) {
    const link = detailPanel.querySelector("a[href*='/jobs/view/']");
    if (link) {
      const m = link.href.match(/\/jobs\/view\/(\d+)/);
      if (m) return `https://www.linkedin.com/jobs/view/${m[1]}/`;
    }
  }

  // 2. Active job card in the left list — data-job-id attribute
  const activeCard = document.querySelector(
    ".job-card-container--active[data-job-id], .jobs-search-results__list-item--active [data-job-id], [data-job-id][aria-selected='true'], .scaffold-layout__list-item.active [data-job-id], .job-card-list__entity-lockup[data-job-id]"
  );
  if (activeCard) {
    const jobId = activeCard.dataset.jobId || activeCard.getAttribute("data-job-id");
    if (jobId) return `https://www.linkedin.com/jobs/view/${jobId}/`;
  }

  // 3. Any element in the left list with data-job-id that is selected/focused
  const anyCard = document.querySelector("[data-job-id]");
  if (anyCard) {
    // Walk up to find the selected card
    const selected = document.querySelector(".jobs-search-results__list-item--active, [aria-selected='true']");
    if (selected) {
      const cardEl = selected.querySelector("[data-job-id]") || selected.closest("[data-job-id]");
      if (cardEl) {
        const jobId = cardEl.dataset.jobId || cardEl.getAttribute("data-job-id");
        if (jobId) return `https://www.linkedin.com/jobs/view/${jobId}/`;
      }
    }
  }

  // 4. URL path for direct /jobs/view/ pages
  const viewMatch = window.location.pathname.match(/\/jobs\/view\/(\d+)/);
  if (viewMatch) return `https://www.linkedin.com/jobs/view/${viewMatch[1]}/`;

  // 5. currentJobId query param (search page)
  const jobId = new URLSearchParams(window.location.search).get("currentJobId");
  if (jobId) return `https://www.linkedin.com/jobs/view/${jobId}/`;

  return null;
}

// ── SELECTORS ─────────────────────────────────────────────────────────────────
function getText(selectors, root = document) {
  for (const sel of selectors) {
    try {
      const el = root.querySelector(sel);
      if (el && el.innerText.trim()) return el.innerText.trim();
    } catch (_) {}
  }
  return "";
}

function extractJob() {
  const applyUrl = getCurrentJobUrl();

  // Can't determine job URL yet — detail panel not ready
  if (!applyUrl) return null;

  // Only skip if this is the exact same job we just captured
  if (applyUrl === lastCapturedUrl) return null;

  const title = getText([
    ".job-details-jobs-unified-top-card__job-title h1",
    ".jobs-unified-top-card__job-title h1",
    ".job-details-jobs-unified-top-card__job-title",
    ".t-24.t-bold",
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

  // Skip if we haven't loaded a real job yet
  if (!title || !company_name) return null;

  // Parse relative posted date
  let date_posted = null;
  const dateEls = document.querySelectorAll(
    ".jobs-unified-top-card__posted-date, .tvm__text, .job-details-jobs-unified-top-card__primary-description-container span"
  );
  for (const el of dateEls) {
    const t = el.innerText.trim();
    const match = t.match(/(\d+)\s*(hour|day|week|month)s?\s*ago/i);
    if (match) {
      const n = parseInt(match[1]);
      const unit = match[2].toLowerCase();
      const ms = { hour: 36e5, day: 864e5, week: 6048e5, month: 2592e6 }[unit] || 0;
      date_posted = new Date(Date.now() - n * ms).toISOString();
      break;
    }
  }

  return { title, company_name, location, raw_description, apply_url: applyUrl, date_posted };
}

// ── CAPTURE ───────────────────────────────────────────────────────────────────
function tryCapture() {
  const job = extractJob();
  if (!job) return;

  capturedJobs.push(job);
  lastCapturedUrl = job.apply_url;
  updateButton();
  flashButton();
  console.log(`[jhoo] Captured #${capturedJobs.length}: ${job.title} @ ${job.company_name}`);
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

function flashButton() {
  if (!harvestBtn) return;
  harvestBtn.style.transition = "background-color 0.3s ease";
  harvestBtn.style.background = "#ef4444";
  setTimeout(() => { harvestBtn.style.background = "#22c55e"; }, 300);

  // Ding using Web Audio API — no external file needed
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.type = "sine";
    osc.frequency.setValueAtTime(1046, ctx.currentTime);       // C6
    gain.gain.setValueAtTime(0.25, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.4);
    osc.start(ctx.currentTime);
    osc.stop(ctx.currentTime + 0.4);
    osc.onended = () => ctx.close();
  } catch (_) {}
}

function setButtonState(text, color, resetAfterMs) {
  if (!harvestBtn) return;
  harvestBtn.textContent = text;
  harvestBtn.style.background = color;
  if (resetAfterMs) {
    setTimeout(() => {
      harvestBtn.style.background = "#22c55e";
      updateButton();
    }, resetAfterMs);
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
      let msg = errText;
      try { msg = JSON.parse(errText).message || errText; } catch (_) {}
      throw new Error(msg);
    }

    const count = capturedJobs.length;
    capturedJobs = [];
    lastCapturedUrl = null;
    setButtonState(`✅ jhoo: ${count} sent!`, "#0f9960", 3000);
  } catch (e) {
    console.error("[jhoo] Harvest failed:", e);
    const msg = (e.message || "Unknown error").slice(0, 80);
    setButtonState(`❌ ${msg}`, "#d63031", 5000);
  }
}

// ── OBSERVER ──────────────────────────────────────────────────────────────────
function startObserver() {
  if (observerInstance) observerInstance.disconnect();

  observerInstance = new MutationObserver(() => {
    // Re-inject harvest button if LinkedIn removed it during page navigation
    if (!document.getElementById("jhoo-harvest-btn")) {
      harvestBtn = createButton();
    }
    // Debounce: wait 1500ms after last mutation before attempting capture
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(tryCapture, 1500);
  });

  observerInstance.observe(document.body, {
    childList: true,
    subtree: true
  });
}

// ── URL WATCHER ───────────────────────────────────────────────────────────────
function watchUrlChanges() {
  setInterval(() => {
    if (window.location.href === currentUrl) return;
    currentUrl = window.location.href;

    // Re-inject button if it was removed by the SPA navigation
    if (!document.getElementById("jhoo-harvest-btn")) {
      harvestBtn = createButton();
    } else {
      harvestBtn = document.getElementById("jhoo-harvest-btn");
    }

    // Restart observer so it is properly attached after DOM changes
    startObserver();
  }, 2000);
}

// ── INIT ──────────────────────────────────────────────────────────────────────
function init() {
  if (document.getElementById("jhoo-harvest-btn")) return;
  harvestBtn = createButton();
  startObserver();
  watchUrlChanges();
  // Attempt initial capture in case a job is already showing
  setTimeout(tryCapture, 2000);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
