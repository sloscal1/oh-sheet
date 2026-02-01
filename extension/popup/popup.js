/**
 * Popup script — settings and cache management.
 */

import BrowserAPI from "../lib/browser-api.js";

// ---------------------------------------------------------------------------
// DOM refs
// ---------------------------------------------------------------------------

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const loginForm = $("#login-form");
const authStatus = $("#auth-status");
const loginError = $("#login-error");
const emailInput = $("#email");
const passwordInput = $("#password");
const loginBtn = $("#login-btn");
const logoutBtn = $("#logout-btn");
const userEmailEl = $("#user-email");

const cacheSection = $("#cache-section");
const setFilterInput = $("#set-filter-input");
const setListEl = $("#set-list");
const cacheBtn = $("#cache-btn");
const cacheProgress = $("#cache-progress");
const cacheProgressLabel = $("#cache-progress-label");
const cacheProgressFill = $("#cache-progress-fill");
const cacheCancelBtn = $("#cache-cancel-btn");
const cacheActions = $("#cache-actions");

const defaultsSection = $("#defaults-section");
const defaultCondition = $("#default-condition");
const defaultLanguage = $("#default-language");

const cachedDataSection = $("#cached-data-section");
const cacheSummary = $("#cache-summary");
const cachedSetList = $("#cached-set-list");
const clearAllArea = $("#clear-all-area");
const clearAllBtn = $("#clear-all-btn");

// ---------------------------------------------------------------------------
// Known set codes (common recent sets — extend as needed)
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
// State
// ---------------------------------------------------------------------------

let isLoggedIn = false;
let cachedSetsMap = new Map(); // code → { set_name, card_count, cached_at }
let cacheCancelled = false;

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------

async function init() {
  try {
    // Check auth
    const token = await getStoredToken();
    if (token) {
      const { echoUser } = await BrowserAPI.storage.get("echoUser");
      showLoggedIn(echoUser || "Authenticated");
    }

    // Load cached sets
    await refreshCachedSets();

    // Load defaults
    const result = await BrowserAPI.sendMessage({
      type: "GET_STATE",
      keys: ["defaultCondition", "defaultLanguage"],
    });
    if (result?.ok && result.values) {
      if (result.values.defaultCondition) {
        defaultCondition.value = result.values.defaultCondition;
      }
      if (result.values.defaultLanguage) {
        defaultLanguage.value = result.values.defaultLanguage;
      }
    }

    // Render set list
    renderSetList();
  } catch (err) {
    console.error("[popup] init error:", err);
    loginError.textContent = "Failed to connect to service worker. Try reloading the extension.";
    loginError.classList.remove("hidden");
  }
}

async function getStoredToken() {
  const { echoToken } = await BrowserAPI.storage.get("echoToken");
  return echoToken || null;
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

function showLoggedIn(user) {
  isLoggedIn = true;
  loginForm.classList.add("hidden");
  authStatus.classList.remove("hidden");
  userEmailEl.textContent = user;
  loginError.classList.add("hidden");

  cacheSection.classList.remove("disabled");
  defaultsSection.classList.remove("disabled");
  cachedDataSection.classList.remove("disabled");
}

function showLoggedOut() {
  isLoggedIn = false;
  loginForm.classList.remove("hidden");
  authStatus.classList.add("hidden");
  loginError.classList.add("hidden");
  emailInput.value = "";
  passwordInput.value = "";

  cacheSection.classList.add("disabled");
  defaultsSection.classList.add("disabled");
  cachedDataSection.classList.add("disabled");
}

loginBtn.addEventListener("click", async () => {
  const email = emailInput.value.trim();
  const password = passwordInput.value;
  if (!email || !password) return;

  loginBtn.disabled = true;
  loginBtn.textContent = "Logging in...";
  loginError.classList.add("hidden");

  const result = await BrowserAPI.sendMessage({
    type: "LOGIN",
    email,
    password,
  });

  loginBtn.disabled = false;
  loginBtn.textContent = "Login";

  if (result?.ok) {
    await BrowserAPI.storage.set({ echoUser: result.user });
    showLoggedIn(result.user);
  } else {
    loginError.textContent = result?.error || "Login failed";
    loginError.classList.remove("hidden");
  }
});

logoutBtn.addEventListener("click", async () => {
  await BrowserAPI.sendMessage({ type: "LOGOUT" });
  await BrowserAPI.storage.remove("echoUser");
  showLoggedOut();
});

// ---------------------------------------------------------------------------
// Set list
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
      <span class="set-name">${set.name}</span>
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
// Caching
// ---------------------------------------------------------------------------

cacheBtn.addEventListener("click", async () => {
  const codes = getSelectedSetCodes();
  if (codes.length === 0) return;

  cacheCancelled = false;
  cacheActions.classList.add("hidden");
  cacheProgress.classList.remove("hidden");

  // Cache sets one by one for progress feedback
  const errors = [];
  for (let i = 0; i < codes.length; i++) {
    if (cacheCancelled) break;

    const code = codes[i];
    cacheProgressLabel.textContent = `Caching ${code}... (${i + 1}/${codes.length})`;
    cacheProgressFill.style.width = `${((i + 0.5) / codes.length) * 100}%`;

    try {
      const result = await BrowserAPI.sendMessage({ type: "CACHE_SETS", setCodes: [code] });
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

  // Show errors if any
  if (errors.length > 0) {
    cacheProgressLabel.textContent = `Errors: ${errors.join("; ")}`;
    cacheProgressLabel.style.color = "#ef5350";
    cacheProgress.classList.remove("hidden");
    // Hide progress bar, just show error
    cacheProgressFill.parentElement.classList.add("hidden");
    cacheCancelBtn.classList.add("hidden");
    setTimeout(() => {
      cacheProgress.classList.add("hidden");
      cacheProgressFill.parentElement.classList.remove("hidden");
      cacheCancelBtn.classList.remove("hidden");
      cacheProgressLabel.style.color = "";
    }, 5000);
  }

  // Refresh UI
  await refreshCachedSets();
  renderSetList(setFilterInput.value);
});

cacheCancelBtn.addEventListener("click", () => {
  cacheCancelled = true;
});

// ---------------------------------------------------------------------------
// Cached data display
// ---------------------------------------------------------------------------

async function refreshCachedSets() {
  const result = await BrowserAPI.sendMessage({ type: "GET_CACHED_SETS" });
  cachedSetsMap.clear();

  if (result?.ok && result.sets) {
    for (const set of result.sets) {
      cachedSetsMap.set(set.set_code, set);
    }
  }

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
        <span>${set.set_name}</span>
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
    await BrowserAPI.sendMessage({ type: "CLEAR_SET", setCode: code });
    await refreshCachedSets();
    renderSetList(setFilterInput.value);
    return;
  }
});

cachedSetList.addEventListener("change", async (e) => {
  if (e.target.classList.contains("set-active-checkbox")) {
    const setCode = e.target.dataset.setCode;
    const isActive = e.target.checked;
    await BrowserAPI.sendMessage({ 
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
  if (!confirm("Clear all cached card data?")) return;
  clearAllBtn.disabled = true;
  clearAllBtn.textContent = "Clearing...";
  await BrowserAPI.sendMessage({ type: "CLEAR_ALL" });
  await refreshCachedSets();
  renderSetList(setFilterInput.value);
  clearAllBtn.disabled = false;
  clearAllBtn.textContent = "Clear All Cache";
});

// ---------------------------------------------------------------------------
// Defaults persistence
// ---------------------------------------------------------------------------

defaultCondition.addEventListener("change", () => {
  BrowserAPI.sendMessage({
    type: "SET_STATE",
    key: "defaultCondition",
    value: defaultCondition.value,
  });
});

defaultLanguage.addEventListener("change", () => {
  BrowserAPI.sendMessage({
    type: "SET_STATE",
    key: "defaultLanguage",
    value: defaultLanguage.value,
  });
});

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------

init();
