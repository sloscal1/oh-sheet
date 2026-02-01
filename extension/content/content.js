/**
 * Content script — in-page overlay for rapid card inventory entry.
 *
 * Injected into echomtg.com pages. All UI lives inside a Shadow DOM root
 * to isolate styles from the host page.
 *
 * Flow state machine: login → cache → ready
 */

// ---------------------------------------------------------------------------
// Shadow DOM setup
// ---------------------------------------------------------------------------

const HOST = document.createElement("div");
HOST.id = "echomtg-fast-inventory";
document.body.appendChild(HOST);

const shadow = HOST.attachShadow({ mode: "closed" });

const styleLink = document.createElement("link");
styleLink.rel = "stylesheet";
styleLink.href = chrome.runtime.getURL("content/content.css");
shadow.appendChild(styleLink);

// ---------------------------------------------------------------------------
// Known sets (copied from popup.js)
// ---------------------------------------------------------------------------

const KNOWN_SETS = [
  { code: "FDN", name: "Foundations" },
  { code: "DSK", name: "Duskmourn: House of Horror" },
  { code: "BLB", name: "Bloomburrow" },
  { code: "MH3", name: "Modern Horizons 3" },
  { code: "OTJ", name: "Outlaws of Thunder Junction" },
  { code: "MKM", name: "Murders at Karlov Manor" },
  { code: "LCI", name: "The Lost Caverns of Ixalan" },
  { code: "WOE", name: "Wilds of Eldraine" },
  { code: "LTR", name: "The Lord of the Rings" },
  { code: "MOM", name: "March of the Machine" },
  { code: "ONE", name: "Phyrexia: All Will Be One" },
  { code: "BRO", name: "The Brothers' War" },
  { code: "DMU", name: "Dominaria United" },
  { code: "SNC", name: "Streets of New Capenna" },
  { code: "NEO", name: "Kamigawa: Neon Dynasty" },
  { code: "VOW", name: "Innistrad: Crimson Vow" },
  { code: "MID", name: "Innistrad: Midnight Hunt" },
  { code: "AFR", name: "Adventures in the Forgotten Realms" },
  { code: "STX", name: "Strixhaven" },
  { code: "KHM", name: "Kaldheim" },
  { code: "ZNR", name: "Zendikar Rising" },
  { code: "2XM", name: "Double Masters" },
  { code: "IKO", name: "Ikoria" },
  { code: "THB", name: "Theros Beyond Death" },
  { code: "ELD", name: "Throne of Eldraine" },
  { code: "WAR", name: "War of the Spark" },
  { code: "RNA", name: "Ravnica Allegiance" },
  { code: "GRN", name: "Guilds of Ravnica" },
];

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const RARITY_CODES = { "Mythic Rare": "M", Rare: "R", Uncommon: "U", Common: "C" };

// Flow phases
const PHASE_LOGIN = "login";
const PHASE_CACHE = "cache";
const PHASE_READY = "ready";

// ---------------------------------------------------------------------------
// Build DOM
// ---------------------------------------------------------------------------

function buildUI() {
  const container = document.createElement("div");
  container.innerHTML = `
    <!-- Collapsed tab -->
    <div class="overlay-tab" id="overlay-tab">⚡ Echo</div>

    <!-- Expanded panel -->
    <div class="overlay-panel hidden" id="overlay-panel">
      <div class="overlay-header">
        <span class="overlay-title">⚡ Fast Inventory</span>
        <button class="collapse-btn" id="collapse-btn" title="Collapse (Ctrl+Shift+E)">−</button>
      </div>

      <div class="overlay-body">
        <!-- === Account accordion === -->
        <div class="accordion-section" id="acc-account">
          <div class="accordion-header" id="acc-account-hdr">
            <div class="accordion-header-left">
              <span class="accordion-chevron">▶</span>
              <span class="accordion-title">Account</span>
            </div>
            <span class="accordion-status" id="acc-account-status"></span>
          </div>
          <div class="accordion-body" id="acc-account-body">
            <!-- Login form (shown when logged out) -->
            <div class="login-form" id="login-form">
              <input class="login-input" id="login-email" type="email" placeholder="Email" autocomplete="email">
              <input class="login-input" id="login-password" type="password" placeholder="Password" autocomplete="current-password">
              <div class="login-error hidden" id="login-error"></div>
              <div class="login-row">
                <button class="btn btn-primary" id="login-btn">Login</button>
              </div>
            </div>
            <!-- Logged-in info (shown when logged in) -->
            <div class="logged-in-info hidden" id="logged-in-info">
              <span class="logged-in-user" id="logged-in-user"></span>
              <button class="btn btn-sm btn-danger" id="logout-btn">Logout</button>
            </div>
          </div>
        </div>

        <!-- === Set Cache accordion === -->
        <div class="accordion-section disabled" id="acc-cache">
          <div class="accordion-header" id="acc-cache-hdr">
            <div class="accordion-header-left">
              <span class="accordion-chevron">▶</span>
              <span class="accordion-title">Set Cache</span>
            </div>
            <span class="accordion-status" id="acc-cache-status"></span>
          </div>
          <div class="accordion-body" id="acc-cache-body">
            <input class="set-filter-input" id="set-filter-input" type="text" placeholder="Filter sets...">
            <div class="set-list" id="set-list"></div>
            <div class="cache-actions" id="cache-actions">
              <button class="btn btn-primary btn-sm" id="cache-btn" disabled>Cache Selected (0)</button>
              <button class="btn btn-sm hidden" id="cache-cancel-btn">Cancel</button>
            </div>
            <div class="cache-progress hidden" id="cache-progress">
              <div class="cache-progress-label" id="cache-progress-label"></div>
              <div class="cache-progress-track">
                <div class="cache-progress-fill" id="cache-progress-fill"></div>
              </div>
            </div>
            <div id="cached-data-area">
              <div class="cached-summary" id="cache-summary"></div>
              <div class="cached-set-list" id="cached-set-list"></div>
              <div class="clear-all-row hidden" id="clear-all-area">
                <button class="btn btn-sm btn-danger" id="clear-all-btn">Clear All</button>
              </div>
            </div>
          </div>
        </div>

        <!-- === Inventory section (not collapsible) === -->
        <div class="inventory-section disabled" id="inventory-section">
          <div class="location-bar">
            <label>Loc</label>
            <input class="location-input" id="loc-input" type="text" placeholder="tag">
            <label>Pos</label>
            <input class="position-value" id="pos-input" type="number" min="1" value="1">
            <label>Div</label>
            <input class="divider-input" id="div-input" type="number" min="0" value="50"
                   title="Insert divider every N cards (0 = off)">
          </div>

          <div class="options-bar">
            <label>Foil</label>
            <select class="option-select" id="foil-select">
              <option value="0" selected>Regular</option>
              <option value="1">Foil</option>
            </select>
            <label>Lang</label>
            <select class="option-select" id="lang-select">
              <option value="EN" selected>English</option>
              <option value="JA">Japanese</option>
              <option value="ZHS">Chinese (S)</option>
              <option value="ZHT">Chinese (T)</option>
              <option value="FR">French</option>
              <option value="DE">German</option>
              <option value="IT">Italian</option>
              <option value="KO">Korean</option>
              <option value="PT">Portuguese</option>
              <option value="RU">Russian</option>
              <option value="ES">Spanish</option>
            </select>
          </div>

          <div class="divider-alert hidden" id="divider-alert">
            <span class="divider-alert-icon">📋</span>
            <span class="divider-alert-text" id="divider-alert-text"></span>
          </div>

          <div class="search-container">
            <input class="search-input" id="search-input" type="text"
                   placeholder="Type card name to search...">
          </div>

          <div class="results-list hidden" id="results-list"></div>
        </div>
      </div>

      <div class="status-bar">
        <span class="status-message info" id="status-msg">Ready</span>
        <span class="session-count">Session: <strong id="session-count">0</strong></span>
      </div>
    </div>
  `;
  shadow.appendChild(container);
}

buildUI();

// ---------------------------------------------------------------------------
// DOM refs (inside shadow)
// ---------------------------------------------------------------------------

const $ = (sel) => shadow.querySelector(sel);

const tab = $("#overlay-tab");
const panel = $("#overlay-panel");
const collapseBtn = $("#collapse-btn");

// Accordion sections
const accAccount = $("#acc-account");
const accAccountHdr = $("#acc-account-hdr");
const accAccountStatus = $("#acc-account-status");
const accCache = $("#acc-cache");
const accCacheHdr = $("#acc-cache-hdr");
const accCacheStatus = $("#acc-cache-status");
const inventorySection = $("#inventory-section");

// Login elements
const loginForm = $("#login-form");
const loginEmail = $("#login-email");
const loginPassword = $("#login-password");
const loginError = $("#login-error");
const loginBtn = $("#login-btn");
const loggedInInfo = $("#logged-in-info");
const loggedInUser = $("#logged-in-user");
const logoutBtn = $("#logout-btn");

// Cache elements
const setFilterInput = $("#set-filter-input");
const setListEl = $("#set-list");
const cacheBtn = $("#cache-btn");
const cacheActions = $("#cache-actions");
const cacheCancelBtn = $("#cache-cancel-btn");
const cacheProgress = $("#cache-progress");
const cacheProgressLabel = $("#cache-progress-label");
const cacheProgressFill = $("#cache-progress-fill");
const cacheSummary = $("#cache-summary");
const cachedSetList = $("#cached-set-list");
const clearAllArea = $("#clear-all-area");
const clearAllBtn = $("#clear-all-btn");

// Inventory elements
const locInput = $("#loc-input");
const posInput = $("#pos-input");
const divInput = $("#div-input");
const foilSelect = $("#foil-select");
const langSelect = $("#lang-select");
const dividerAlert = $("#divider-alert");
const dividerAlertText = $("#divider-alert-text");
const searchInput = $("#search-input");
const resultsList = $("#results-list");
const statusMsg = $("#status-msg");
const sessionCountEl = $("#session-count");

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

let expanded = false;
let results = [];
let selectedIndex = -1;
let isAdding = false;
let sessionCount = 0;
let debounceTimer = null;
let hasAuth = false;
let hasCachedSets = false;
let defaultCondition = "NM";
let currentPhase = PHASE_LOGIN;
let echoUser = null;
let cachedSetsMap = new Map(); // code → { set_name, card_count, cached_at }
let cacheCancelled = false;

// ---------------------------------------------------------------------------
// Accordion helpers
// ---------------------------------------------------------------------------

function openAccordion(section) {
  section.classList.add("open");
}

function closeAccordion(section) {
  section.classList.remove("open");
}

function toggleAccordion(section) {
  section.classList.toggle("open");
}

function enableSection(section) {
  section.classList.remove("disabled");
}

function disableSection(section) {
  section.classList.add("disabled");
}

// Accordion header click handlers
accAccountHdr.addEventListener("click", () => {
  toggleAccordion(accAccount);
});

accCacheHdr.addEventListener("click", () => {
  if (!accCache.classList.contains("disabled")) {
    toggleAccordion(accCache);
  }
});

// ---------------------------------------------------------------------------
// Flow state machine
// ---------------------------------------------------------------------------

function setPhase(phase) {
  currentPhase = phase;
  applyPhase();
}

function applyPhase() {
  switch (currentPhase) {
    case PHASE_LOGIN:
      openAccordion(accAccount);
      closeAccordion(accCache);
      disableSection(accCache);
      disableSection(inventorySection);
      searchInput.disabled = true;
      accAccountStatus.textContent = "";
      accAccountStatus.className = "accordion-status";
      accCacheStatus.textContent = "";
      accCacheStatus.className = "accordion-status";
      break;

    case PHASE_CACHE:
      closeAccordion(accAccount);
      enableSection(accCache);
      openAccordion(accCache);
      disableSection(inventorySection);
      searchInput.disabled = true;
      accAccountStatus.textContent = "✓ " + (echoUser || "Logged in");
      accAccountStatus.className = "accordion-status complete";
      updateCacheStatus();
      break;

    case PHASE_READY:
      closeAccordion(accAccount);
      closeAccordion(accCache);
      enableSection(accCache);
      enableSection(inventorySection);
      searchInput.disabled = false;
      accAccountStatus.textContent = "✓ " + (echoUser || "Logged in");
      accAccountStatus.className = "accordion-status complete";
      updateCacheStatus();
      break;
  }
}

function updateCacheStatus() {
  const count = cachedSetsMap.size;
  if (count > 0) {
    const totalCards = Array.from(cachedSetsMap.values()).reduce((s, v) => s + (v.card_count || 0), 0);
    accCacheStatus.textContent = `✓ ${count} set${count !== 1 ? "s" : ""}, ${totalCards.toLocaleString()} cards`;
    accCacheStatus.className = "accordion-status complete";
  } else {
    accCacheStatus.textContent = "No sets cached";
    accCacheStatus.className = "accordion-status";
  }
}

function determinePhase() {
  if (!hasAuth) return PHASE_LOGIN;
  if (!hasCachedSets) return PHASE_CACHE;
  return PHASE_READY;
}

// ---------------------------------------------------------------------------
// Expand / Collapse
// ---------------------------------------------------------------------------

async function expand() {
  expanded = true;
  panel.classList.remove("hidden");
  tab.classList.add("hidden");
  await refreshState();
  if (currentPhase === PHASE_READY) {
    searchInput.focus();
  } else if (currentPhase === PHASE_LOGIN) {
    loginEmail.focus();
  }
}

function collapse() {
  expanded = false;
  panel.classList.add("hidden");
  tab.classList.remove("hidden");
}

function toggle() {
  expanded ? collapse() : expand();
}

tab.addEventListener("click", expand);
collapseBtn.addEventListener("click", collapse);

document.addEventListener("keydown", (e) => {
  if (e.ctrlKey && e.shiftKey && e.key === "E") {
    e.preventDefault();
    toggle();
  }
});

// ---------------------------------------------------------------------------
// Login logic
// ---------------------------------------------------------------------------

loginBtn.addEventListener("click", async () => {
  const email = loginEmail.value.trim();
  const password = loginPassword.value;
  if (!email || !password) return;

  loginBtn.disabled = true;
  loginBtn.textContent = "Logging in...";
  loginError.classList.add("hidden");

  const result = await chrome.runtime.sendMessage({
    type: "LOGIN",
    email,
    password,
  });

  loginBtn.disabled = false;
  loginBtn.textContent = "Login";

  if (result?.ok) {
    echoUser = result.user || email;
    await chrome.storage.local.set({ echoUser });
    hasAuth = true;
    showLoggedInUI();
    await refreshCachedSets();
    setPhase(hasCachedSets ? PHASE_READY : PHASE_CACHE);
    renderSetList();
    if (currentPhase === PHASE_READY) searchInput.focus();
  } else {
    loginError.textContent = result?.error || "Login failed";
    loginError.classList.remove("hidden");
  }
});

logoutBtn.addEventListener("click", async () => {
  await chrome.runtime.sendMessage({ type: "LOGOUT" });
  await chrome.storage.local.remove("echoUser");
  hasAuth = false;
  echoUser = null;
  showLoggedOutUI();
  setPhase(PHASE_LOGIN);
  loginEmail.focus();
});

function showLoggedInUI() {
  loginForm.classList.add("hidden");
  loggedInInfo.classList.remove("hidden");
  loggedInUser.textContent = echoUser || "Authenticated";
}

function showLoggedOutUI() {
  loginForm.classList.remove("hidden");
  loggedInInfo.classList.add("hidden");
  loginEmail.value = "";
  loginPassword.value = "";
  loginError.classList.add("hidden");
}

// ---------------------------------------------------------------------------
// Set list rendering
// ---------------------------------------------------------------------------

function renderSetList(filter = "") {
  const lowerFilter = filter.toLowerCase();
  setListEl.innerHTML = "";

  for (const set of KNOWN_SETS) {
    if (
      lowerFilter &&
      !set.name.toLowerCase().includes(lowerFilter) &&
      !set.code.toLowerCase().includes(lowerFilter)
    ) {
      continue;
    }

    const cached = cachedSetsMap.get(set.code);
    const row = document.createElement("div");
    row.className = "set-row";
    row.innerHTML = `
      <input type="checkbox" data-code="${set.code}">
      <span class="set-name">${escapeHtml(set.name)}</span>
      <span class="set-code">${set.code}</span>
      ${
        cached
          ? `<span class="set-cached">${cached.card_count} cards</span>`
          : `<span class="set-not-cached">—</span>`
      }
    `;
    setListEl.appendChild(row);
  }

  updateCacheButton();
}

function getSelectedSetCodes() {
  return Array.from(setListEl.querySelectorAll('input[type="checkbox"]:checked'))
    .map((cb) => cb.dataset.code);
}

function updateCacheButton() {
  const count = getSelectedSetCodes().length;
  cacheBtn.textContent = `Cache Selected (${count})`;
  cacheBtn.disabled = count === 0;
}

setListEl.addEventListener("change", updateCacheButton);

setFilterInput.addEventListener("input", () => {
  renderSetList(setFilterInput.value);
});

// ---------------------------------------------------------------------------
// Caching logic
// ---------------------------------------------------------------------------

cacheBtn.addEventListener("click", async () => {
  const codes = getSelectedSetCodes();
  if (codes.length === 0) return;

  cacheCancelled = false;
  cacheActions.classList.add("hidden");
  cacheProgress.classList.remove("hidden");
  cacheCancelBtn.classList.remove("hidden");

  const errors = [];
  for (let i = 0; i < codes.length; i++) {
    if (cacheCancelled) break;

    const code = codes[i];
    cacheProgressLabel.textContent = `Caching ${code}... (${i + 1}/${codes.length})`;
    cacheProgressFill.style.width = `${((i + 0.5) / codes.length) * 100}%`;

    try {
      const result = await chrome.runtime.sendMessage({ type: "CACHE_SETS", setCodes: [code] });
      if (result?.ok) {
        const setResult = result.results?.[0];
        if (setResult && !setResult.ok) {
          errors.push(`${code}: ${setResult.error}`);
        }
      } else {
        errors.push(`${code}: ${result?.error || "unknown error"}`);
      }
    } catch (err) {
      errors.push(`${code}: ${err.message}`);
    }

    cacheProgressFill.style.width = `${((i + 1) / codes.length) * 100}%`;
  }

  cacheProgress.classList.add("hidden");
  cacheActions.classList.remove("hidden");

  if (errors.length > 0) {
    cacheProgressLabel.textContent = `Errors: ${errors.join("; ")}`;
    cacheProgressLabel.style.color = "#ef5350";
    cacheProgress.classList.remove("hidden");
    cacheCancelBtn.classList.add("hidden");
    setTimeout(() => {
      cacheProgress.classList.add("hidden");
      cacheProgressLabel.style.color = "";
    }, 5000);
  }

  await refreshCachedSets();
  renderSetList(setFilterInput.value);
  updateCacheStatus();

  // Auto-advance to ready if we now have cached sets
  if (hasCachedSets && currentPhase === PHASE_CACHE) {
    setPhase(PHASE_READY);
    searchInput.focus();
  }
});

cacheCancelBtn.addEventListener("click", () => {
  cacheCancelled = true;
});

// ---------------------------------------------------------------------------
// Cached data display
// ---------------------------------------------------------------------------

async function refreshCachedSets() {
  try {
    const result = await chrome.runtime.sendMessage({ type: "GET_CACHED_SETS" });
    cachedSetsMap.clear();

    if (result?.ok && result.sets) {
      for (const set of result.sets) {
        cachedSetsMap.set(set.set_code, set);
      }
    }
  } catch (err) {
    console.warn("[overlay] refreshCachedSets error:", err);
  }

  hasCachedSets = cachedSetsMap.size > 0;
  renderCachedData();
}

function renderCachedData() {
  const sets = Array.from(cachedSetsMap.values());
  cachedSetList.innerHTML = "";

  if (sets.length === 0) {
    cacheSummary.textContent = "No sets cached";
    clearAllArea.classList.add("hidden");
    return;
  }

  const totalCards = sets.reduce((sum, s) => sum + (s.card_count || 0), 0);
  cacheSummary.innerHTML = `<strong>${sets.length}</strong> set${sets.length !== 1 ? "s" : ""} cached, <strong>${totalCards.toLocaleString()}</strong> cards total`;

  for (const set of sets) {
    const row = document.createElement("div");
    row.className = "cached-set-row";
    const isActive = set.active !== false; // Default to true
    row.innerHTML = `
      <div class="cached-set-info">
        <input type="checkbox" class="set-active-checkbox" 
               data-set-code="${set.set_code}" 
               ${isActive ? 'checked' : ''}>
        <span>${escapeHtml(set.set_name)}</span>
        <span class="set-code">${set.set_code}</span>
        <span class="card-count">${set.card_count}</span>
      </div>
      <button class="btn btn-danger btn-sm" data-clear-code="${set.set_code}">Clear</button>
    `;
    cachedSetList.appendChild(row);
  }

  clearAllArea.classList.remove("hidden");
}

cachedSetList.addEventListener("click", async (e) => {
  const btn = e.target.closest("[data-clear-code]");
  if (btn) {
    const code = btn.dataset.clearCode;
    btn.disabled = true;
    btn.textContent = "...";
    await chrome.runtime.sendMessage({ type: "CLEAR_SET", setCode: code });
    await refreshCachedSets();
    renderSetList(setFilterInput.value);
    updateCacheStatus();

    // If all sets cleared, regress to cache phase
    if (!hasCachedSets && currentPhase === PHASE_READY) {
      setPhase(PHASE_CACHE);
    }
    return;
  }
});

cachedSetList.addEventListener("change", async (e) => {
  if (e.target.classList.contains("set-active-checkbox")) {
    const setCode = e.target.dataset.setCode;
    const isActive = e.target.checked;
    await chrome.runtime.sendMessage({ 
      type: "SET_SET_ACTIVE", 
      setCode, 
      active: isActive 
    });
    // Update the cached sets map to reflect the change
    const cachedSet = cachedSetsMap.get(setCode);
    if (cachedSet) {
      cachedSet.active = isActive;
    }
  }
});

clearAllBtn.addEventListener("click", async () => {
  clearAllBtn.disabled = true;
  clearAllBtn.textContent = "Clearing...";
  await chrome.runtime.sendMessage({ type: "CLEAR_ALL" });
  await refreshCachedSets();
  renderSetList(setFilterInput.value);
  updateCacheStatus();
  clearAllBtn.disabled = false;
  clearAllBtn.textContent = "Clear All";

  if (currentPhase === PHASE_READY) {
    setPhase(PHASE_CACHE);
  }
});

// ---------------------------------------------------------------------------
// Persist controls on change
// ---------------------------------------------------------------------------

locInput.addEventListener("change", () => {
  chrome.runtime.sendMessage({ type: "SET_STATE", key: "locationTag", value: locInput.value });
});
posInput.addEventListener("change", () => {
  chrome.runtime.sendMessage({ type: "SET_STATE", key: "position", value: Number(posInput.value) });
  checkDividerAlert();
});
divInput.addEventListener("change", () => {
  chrome.runtime.sendMessage({ type: "SET_STATE", key: "dividerEvery", value: Number(divInput.value) });
  checkDividerAlert();
});
foilSelect.addEventListener("change", () => {
  chrome.runtime.sendMessage({ type: "SET_STATE", key: "foil", value: Number(foilSelect.value) });
});
langSelect.addEventListener("change", () => {
  chrome.runtime.sendMessage({ type: "SET_STATE", key: "language", value: langSelect.value });
});

// ---------------------------------------------------------------------------
// Initialisation — load persisted state & determine phase
// ---------------------------------------------------------------------------

async function loadState() {
  try {
    // Check auth
    const { echoToken } = await chrome.storage.local.get("echoToken");
    hasAuth = !!echoToken;

    if (hasAuth) {
      const stored = await chrome.storage.local.get("echoUser");
      echoUser = stored.echoUser || "Authenticated";
      showLoggedInUI();
    }

    // Check cached sets
    await refreshCachedSets();

    // Load persisted state
    const stateResult = await chrome.runtime.sendMessage({
      type: "GET_STATE",
      keys: [
        "locationTag",
        "position",
        "dividerEvery",
        "foil",
        "language",
        "defaultCondition",
        "defaultLanguage",
      ],
    });

    if (stateResult?.ok && stateResult.values) {
      const v = stateResult.values;
      if (v.locationTag != null) locInput.value = v.locationTag;
      if (v.position != null) posInput.value = v.position;
      if (v.dividerEvery != null) divInput.value = v.dividerEvery;
      if (v.foil != null) foilSelect.value = String(v.foil);
      if (v.defaultCondition) defaultCondition = v.defaultCondition;
      const lang = v.language || v.defaultLanguage;
      if (lang) langSelect.value = lang;
    }
  } catch (err) {
    console.error("[overlay] Failed to load state:", err);
    statusMsg.textContent = "Failed to connect to extension";
    statusMsg.className = "status-message error";
  }

  // Render set list for cache section
  renderSetList();

  // Set initial phase
  setPhase(determinePhase());
  checkDividerAlert();
}

// ---------------------------------------------------------------------------
// Refresh auth & cache status (called on every expand)
// ---------------------------------------------------------------------------

async function refreshState() {
  try {
    const { echoToken } = await chrome.storage.local.get("echoToken");
    hasAuth = !!echoToken;

    if (hasAuth) {
      const stored = await chrome.storage.local.get("echoUser");
      echoUser = stored.echoUser || "Authenticated";
      showLoggedInUI();
    } else {
      showLoggedOutUI();
    }

    await refreshCachedSets();
    renderSetList(setFilterInput.value);
  } catch (err) {
    console.warn("[overlay] refreshState error:", err);
  }

  setPhase(determinePhase());
}

// ---------------------------------------------------------------------------
// Divider alert
// ---------------------------------------------------------------------------

function checkDividerAlert() {
  const pos = Number(posInput.value) || 0;
  const divEvery = Number(divInput.value) || 0;

  if (divEvery > 0 && pos > 1 && (pos - 1) % divEvery === 0) {
    dividerAlertText.innerHTML =
      `<strong>Insert a divider</strong> — ${pos - 1} cards added (every ${divEvery})`;
    dividerAlert.classList.remove("hidden");
  } else {
    dividerAlert.classList.add("hidden");
  }
}

// ---------------------------------------------------------------------------
// Search
// ---------------------------------------------------------------------------

searchInput.addEventListener("input", () => {
  clearTimeout(debounceTimer);
  const query = searchInput.value.trim();
  if (!query) {
    clearResults();
    return;
  }
  debounceTimer = setTimeout(() => doSearch(query), 100);
});

async function doSearch(query) {
  try {
    // Get active sets before searching
    const activeSetsResult = await chrome.runtime.sendMessage({ 
      type: "GET_ACTIVE_SETS" 
    });
    
    const result = await chrome.runtime.sendMessage({
      type: "SEARCH_CARDS",
      query,
      activeSets: activeSetsResult?.ok ? activeSetsResult.activeSets : [],
    });

    if (result?.ok) {
      results = result.cards || [];
      selectedIndex = results.length > 0 ? 0 : -1;
      renderResults();
      if (results.length === 0) {
        statusMsg.textContent = "No matches";
        statusMsg.className = "status-message info";
      } else {
        statusMsg.textContent = `${results.length} result${results.length !== 1 ? "s" : ""}`;
        statusMsg.className = "status-message info";
      }
    } else {
      statusMsg.textContent = `Search error: ${result?.error || "unknown"}`;
      statusMsg.className = "status-message error";
    }
  } catch (err) {
    statusMsg.textContent = "Search failed — service worker not responding";
    statusMsg.className = "status-message error";
  }
}

function clearResults() {
  results = [];
  selectedIndex = -1;
  resultsList.innerHTML = "";
  resultsList.classList.add("hidden");
}

function renderResults() {
  if (results.length === 0) {
    resultsList.innerHTML = "";
    resultsList.classList.add("hidden");
    return;
  }

  resultsList.classList.remove("hidden");
  resultsList.innerHTML = results
    .map((card, i) => {
      const rarityCode = RARITY_CODES[card.rarity] || "";
      const badges = (card.variant_tags || [])
        .map((tag) => {
          const cls = card.is_foil_variant &&
            tag.toLowerCase().includes("foil")
            ? "badge badge-foil"
            : "badge badge-variant";
          return `<span class="${cls}">${escapeHtml(tag)}</span>`;
        })
        .join("");
      const selected = i === selectedIndex ? " selected" : "";

      return `
        <div class="result-item${selected}" data-index="${i}">
          <div class="result-thumb">
            ${card.image_cropped ? `<img src="${escapeHtml(card.image_cropped)}" alt="">` : ""}
          </div>
          <div class="result-info">
            <div class="result-name">${escapeHtml(card.name)}</div>
            <div class="result-meta">
              ${badges}
              <span>${escapeHtml(card.set_code)} #${card.collectors_number}</span>
              ${rarityCode ? `<span class="rarity-${rarityCode}">${rarityCode}</span>` : ""}
            </div>
          </div>
        </div>
      `;
    })
    .join("");
}

function escapeHtml(str) {
  const el = document.createElement("span");
  el.textContent = str;
  return el.innerHTML;
}

// Click to select and add
resultsList.addEventListener("click", (e) => {
  const item = e.target.closest(".result-item");
  if (!item || isAdding) return;
  const idx = Number(item.dataset.index);
  if (idx >= 0 && idx < results.length) {
    selectedIndex = idx;
    addSelectedCard();
  }
});

// ---------------------------------------------------------------------------
// Keyboard navigation
// ---------------------------------------------------------------------------

searchInput.addEventListener("keydown", (e) => {
  if (results.length === 0) {
    if (e.key === "Escape") {
      if (!searchInput.value) collapse();
      else { searchInput.value = ""; clearResults(); }
      e.preventDefault();
    }
    return;
  }

  switch (e.key) {
    case "ArrowDown":
      e.preventDefault();
      selectedIndex = (selectedIndex + 1) % results.length;
      renderResults();
      scrollSelectedIntoView();
      break;
    case "ArrowUp":
      e.preventDefault();
      selectedIndex = (selectedIndex - 1 + results.length) % results.length;
      renderResults();
      scrollSelectedIntoView();
      break;
    case "Enter":
      e.preventDefault();
      if (selectedIndex >= 0) addSelectedCard();
      break;
    case "Escape":
      e.preventDefault();
      searchInput.value = "";
      clearResults();
      break;
  }
});

function scrollSelectedIntoView() {
  const el = resultsList.querySelector(".selected");
  if (el) el.scrollIntoView({ block: "nearest" });
}

// ---------------------------------------------------------------------------
// Add card
// ---------------------------------------------------------------------------

async function addSelectedCard() {
  if (isAdding || selectedIndex < 0 || selectedIndex >= results.length) return;
  isAdding = true;

  const card = results[selectedIndex];

  const selectedEl = resultsList.querySelector(".selected");
  if (selectedEl) {
    selectedEl.classList.add("adding");
    const label = document.createElement("span");
    label.className = "adding-label";
    label.textContent = "Adding…";
    selectedEl.appendChild(label);
  }

  statusMsg.textContent = "Adding to inventory…";
  statusMsg.className = "status-message pending";
  searchInput.disabled = true;

  const result = await chrome.runtime.sendMessage({
    type: "ADD_CARD",
    emid: card.emid,
    foil: Number(foilSelect.value),
    condition: defaultCondition,
    language: langSelect.value,
    locationTag: locInput.value,
    position: Number(posInput.value),
  });

  isAdding = false;
  searchInput.disabled = false;

  if (result?.ok) {
    sessionCount++;
    sessionCountEl.textContent = sessionCount;

    const noteText = result.noteText || `${locInput.value}p${posInput.value}`;
    statusMsg.textContent = `✓ ${card.name} added → ${noteText}`;
    statusMsg.className = "status-message";

    posInput.value = result.newPosition;
    checkDividerAlert();

    searchInput.value = "";
    clearResults();
    searchInput.focus();
  } else {
    statusMsg.textContent = `✗ Failed to add — ${result?.error || "unknown error"}`;
    statusMsg.className = "status-message error";
    renderResults();
    searchInput.focus();
  }
}

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------

loadState();
