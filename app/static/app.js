let allAccounts = [];
let activeFilter = "ALL";
let currentDetailAccount = null;

// Initialize on DOM load
document.addEventListener("DOMContentLoaded", () => {
  initApp();
  setupEventListeners();
});

async function initApp() {
  await Promise.all([checkAiHealth(), loadStats(), loadAccounts()]);
}

function setupEventListeners() {
  // Filter buttons
  document.querySelectorAll(".filter-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      activeFilter = btn.dataset.filter;
      renderAccountsTable();
    });
  });

  // Stat card clicks also filter
  document.querySelectorAll(".stat-card").forEach(card => {
    card.addEventListener("click", () => {
      const filter = card.dataset.filter;
      if (filter) {
        document.querySelectorAll(".filter-btn").forEach(b => {
          b.classList.toggle("active", b.dataset.filter === filter);
        });
        activeFilter = filter;
        renderAccountsTable();
      }
    });
  });

  // Search input
  const searchInput = document.getElementById("searchInput");
  if (searchInput) {
    searchInput.addEventListener("input", () => renderAccountsTable());
  }

  // Close drawer
  const closeBtn = document.getElementById("closeDrawerBtn");
  const overlay = document.getElementById("detailDrawerOverlay");
  if (closeBtn && overlay) {
    closeBtn.addEventListener("click", closeDrawer);
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) closeDrawer();
    });
  }

  // Refresh AI button in drawer
  const refreshBtn = document.getElementById("refreshAiBtn");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", handleRefreshAi);
  }

  // Keyboard shortcut Esc to close
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeDrawer();
  });
}

// 1. AI Health check (Strictly "AI connected" or "AI unavailable", NO model names)
async function checkAiHealth() {
  const badge = document.getElementById("aiStatusBadge");
  const text = document.getElementById("aiStatusText");

  try {
    const res = await fetch("/api/health");
    if (!res.ok) throw new Error("Health check failed");
    const data = await res.json();

    if (data.ai_status === "AI connected") {
      badge.className = "ai-status-pill ai-connected";
      text.textContent = "AI connected";
    } else {
      badge.className = "ai-status-pill ai-unavailable";
      text.textContent = "AI unavailable";
    }
  } catch (err) {
    badge.className = "ai-status-pill ai-unavailable";
    text.textContent = "AI unavailable";
  }
}

// 2. Load Stats
async function loadStats() {
  try {
    const res = await fetch("/api/stats");
    if (res.ok) {
      const data = await res.json();
      document.getElementById("statTotalQualified").textContent = data.total_qualified;
      document.getElementById("statHighPriority").textContent = data.high_priority;
      document.getElementById("statNeedsReview").textContent = data.needs_review;
      document.getElementById("statMonitor").textContent = data.monitor;
    }
  } catch (e) {
    console.error("Failed to load stats", e);
  }
}

// 3. Load Accounts
async function loadAccounts() {
  const tbody = document.getElementById("accountsTableBody");
  try {
    const res = await fetch("/api/accounts");
    if (!res.ok) throw new Error("Failed to fetch accounts");
    allAccounts = await res.json();
    renderAccountsTable();
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="5" class="loading-state">Error loading accounts: ${err.message}</td></tr>`;
  }
}

// 4. Render Table
function renderAccountsTable() {
  const tbody = document.getElementById("accountsTableBody");
  const query = (document.getElementById("searchInput")?.value || "").toLowerCase().trim();

  let filtered = allAccounts.filter(acc => {
    const matchesFilter = activeFilter === "ALL" || acc.priority === activeFilter;
    const matchesQuery = !query || 
      acc.name.toLowerCase().includes(query) || 
      acc.industry.toLowerCase().includes(query) ||
      acc.account_tier.toLowerCase().includes(query);
    return matchesFilter && matchesQuery;
  });

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" class="loading-state">No accounts match the current filter.</td></tr>`;
    return;
  }

  tbody.innerHTML = filtered.map(acc => {
    const badgeClass = getBadgeClass(acc.priority);
    const scoreVal = acc.score.toFixed(1);
    const confVal = Math.round(acc.confidence);

    return `
      <tr onclick="openAccountDetail('${acc.id}')">
        <td>
          <span class="account-cell-title">${escapeHtml(acc.name)}</span>
          <div class="account-cell-sub">
            <span>${escapeHtml(acc.industry)}</span>
            <span class="tier-pill-sm">${escapeHtml(acc.account_tier)}</span>
          </div>
        </td>
        <td>
          <span class="badge ${badgeClass}">${acc.priority}</span>
        </td>
        <td>
          <div class="score-display">
            <span class="score-bold">${scoreVal}</span>
            <span class="score-out">/ 100</span>
          </div>
        </td>
        <td>
          <span class="conf-display">${confVal}%</span>
        </td>
        <td class="text-right">
          <button class="view-btn" onclick="event.stopPropagation(); openAccountDetail('${acc.id}')">
            View Briefing →
          </button>
        </td>
      </tr>
    `;
  }).join("");
}

function getBadgeClass(priority) {
  switch (priority) {
    case "HIGH": return "badge-high";
    case "REVIEW": return "badge-review";
    case "MONITOR": return "badge-monitor";
    case "SUPPRESSED": return "badge-suppressed";
    case "LOW": return "badge-low";
    default: return "badge-low";
  }
}

// 5. Open Detail Drawer
async function openAccountDetail(accountId) {
  const acc = allAccounts.find(a => a.id === accountId);
  if (!acc) return;

  currentDetailAccount = acc;
  const overlay = document.getElementById("detailDrawerOverlay");

  // Populate basic header
  document.getElementById("drawerCompanyName").textContent = acc.name;
  document.getElementById("drawerTier").textContent = acc.account_tier;
  document.getElementById("drawerIndustry").textContent = acc.industry;
  const webLink = document.getElementById("drawerWebsite");
  webLink.href = acc.website;
  webLink.textContent = acc.website.replace("https://", "");

  // Priority & Confidence
  const badgeEl = document.getElementById("drawerPriorityBadge");
  badgeEl.className = `badge ${getBadgeClass(acc.priority)}`;
  badgeEl.textContent = acc.priority;
  document.getElementById("drawerScoreVal").textContent = acc.score.toFixed(1);
  document.getElementById("drawerConfidenceVal").textContent = `${Math.round(acc.confidence)}%`;

  // Guardrail Box
  const guardrailBox = document.getElementById("drawerGuardrailBox");
  if (acc.guardrail && acc.guardrail.triggered) {
    guardrailBox.classList.remove("hidden");
    document.getElementById("guardrailTitle").textContent = `Guardrail Active: ${acc.guardrail.guardrail_type}`;
    document.getElementById("guardrailMessage").textContent = acc.guardrail.warning_message;
  } else {
    guardrailBox.classList.add("hidden");
  }

  // Why Now Bullets
  const whyNowList = document.getElementById("drawerWhyNowList");
  if (acc.explanation && acc.explanation.why_now) {
    whyNowList.innerHTML = acc.explanation.why_now
      .map(bullet => `<li>${escapeHtml(bullet)}</li>`)
      .join("");
  } else {
    whyNowList.innerHTML = `<li>High priority signals identified in account documents.</li>`;
  }

  // Score Breakdown Bars
  const sb = acc.score_breakdown;
  document.getElementById("valRelevance").textContent = sb.relevance_need.toFixed(1);
  document.getElementById("barRelevance").style.width = `${sb.relevance_need}%`;

  document.getElementById("valTiming").textContent = sb.timing_urgency.toFixed(1);
  document.getElementById("barTiming").style.width = `${sb.timing_urgency}%`;
  document.getElementById("valRecencyFactor").textContent = `${sb.recency_factor_applied}x`;

  document.getElementById("valCommercial").textContent = sb.commercial_fit.toFixed(1);
  document.getElementById("barCommercial").style.width = `${sb.commercial_fit}%`;

  // Recommended Action
  document.getElementById("drawerRecommendedAction").textContent = 
    acc.explanation?.recommended_action || "Initiate account discovery.";

  // Conversation Focus & Opener
  document.getElementById("drawerConversationFocus").textContent = 
    acc.explanation?.conversation_focus || "Workflow automation alignment.";
  document.getElementById("drawerSuggestedOpener").textContent = 
    `"${acc.explanation?.suggested_opener || 'Reaching out regarding your operational scaling plans...'}"`;

  // Evidence List
  const evList = document.getElementById("drawerEvidenceList");
  if (acc.documents && acc.documents.length > 0) {
    evList.innerHTML = acc.documents.map(doc => `
      <div class="evidence-item">
        <div class="evidence-header">
          <span class="ev-id-badge">${escapeHtml(doc.id)} · ${escapeHtml(doc.source_type.replace('_', ' '))}</span>
          <span class="ev-date">${escapeHtml(doc.date)}</span>
        </div>
        <div class="ev-title">${escapeHtml(doc.title)}</div>
        <div class="ev-content">${escapeHtml(doc.content)}</div>
      </div>
    `).join("");
  } else {
    evList.innerHTML = `<p class="ev-content">No raw documents recorded.</p>`;
  }

  // Open Drawer
  overlay.classList.remove("hidden");
}

function closeDrawer() {
  const overlay = document.getElementById("detailDrawerOverlay");
  if (overlay) overlay.classList.add("hidden");
}

// 6. Refresh AI Analysis for Single Account
async function handleRefreshAi() {
  if (!currentDetailAccount) return;

  const btn = document.getElementById("refreshAiBtn");
  const btnText = document.getElementById("refreshBtnText");
  btn.classList.add("spinning");
  btnText.textContent = "Analyzing...";

  try {
    const res = await fetch(`/api/accounts/${currentDetailAccount.id}/analyze`, {
      method: "POST"
    });
    if (!res.ok) throw new Error("Re-analysis failed");
    const updatedAccount = await res.json();

    // Update state
    const index = allAccounts.findIndex(a => a.id === updatedAccount.id);
    if (index !== -1) {
      allAccounts[index] = updatedAccount;
    }
    await loadStats();
    renderAccountsTable();
    openAccountDetail(updatedAccount.id);
  } catch (err) {
    alert("AI Analysis Error: " + err.message);
  } finally {
    btn.classList.remove("spinning");
    btnText.textContent = "Refresh AI";
  }
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
