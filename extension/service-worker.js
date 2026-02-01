/**
 * Service worker (background script).
 *
 * Handles all EchoMTG API communication and IndexedDB operations.
 * The content script and popup communicate with this worker exclusively
 * via BrowserAPI.sendMessage / BrowserAPI.onMessage.
 */

import BrowserAPI from "./lib/browser-api.js";
import EchoAPI from "./lib/echo-api.js";
import CardDB from "./lib/card-db.js";

/** Cached token so we don't hit storage on every request. */
let token = null;

// ---------------------------------------------------------------------------
// Initialisation
// ---------------------------------------------------------------------------

/**
 * Reload token from storage on service worker activation (covers restarts).
 */
async function init() {
  token = await EchoAPI.getStoredToken();
  if (token) {
    console.log("[sw] Token restored from storage");
  }
}

init();

// ---------------------------------------------------------------------------
// Message handlers
// ---------------------------------------------------------------------------

BrowserAPI.onMessage(async (message, _sender) => {
  const { type } = message;

  switch (type) {
    case "LOGIN":
      return handleLogin(message);
    case "LOGOUT":
      return handleLogout();
    case "CACHE_SETS":
      return handleCacheSets(message);
    case "SEARCH_CARDS":
      return handleSearchCards(message);
    case "ADD_CARD":
      return handleAddCard(message);
    case "GET_STATE":
      return handleGetState(message);
    case "SET_STATE":
      return handleSetState(message);
    case "GET_CACHED_SETS":
      return handleGetCachedSets();
    case "CLEAR_SET":
      return handleClearSet(message);
    case "CLEAR_ALL":
      return handleClearAll();
    case "GET_ACTIVE_SETS":
      return handleGetActiveSets();
    case "SET_SET_ACTIVE":
      return handleSetSetActive(message);
    default:
      return { error: `Unknown message type: ${type}` };
  }
});

// ---------------------------------------------------------------------------
// Handler implementations
// ---------------------------------------------------------------------------

async function handleLogin({ email, password }) {
  try {
    const result = await EchoAPI.login(email, password);
    token = result.token;
    return { ok: true, user: result.user };
  } catch (err) {
    return { ok: false, error: err.message };
  }
}

async function handleLogout() {
  token = null;
  await EchoAPI.logout();
  return { ok: true };
}

/**
 * Cache one or more sets.
 *
 * Sends progress updates back to the caller via a streaming pattern:
 * since chrome.runtime.sendMessage only supports a single response, we
 * do all work before responding with the final result.
 *
 * @param {object} message - { setCodes: string[] }
 * @returns {{ ok: boolean, results: object[], error?: string }}
 */
async function handleCacheSets({ setCodes }) {
  if (!token) return { ok: false, error: "Not authenticated" };
  if (!setCodes || setCodes.length === 0) {
    return { ok: false, error: "No set codes provided" };
  }

  const results = [];

  for (const setCode of setCodes) {
    try {
      const rawCards = await EchoAPI.getSetAll(setCode, token);
      if (rawCards.length === 0) {
        results.push({ setCode, ok: false, error: "No cards returned" });
        continue;
      }

      // Derive set name from the first card's "set" field
      const setName = rawCards[0]?.set || setCode;
      const count = await CardDB.cacheSet(setCode, setName, rawCards);
      results.push({ setCode, ok: true, cardCount: count });
    } catch (err) {
      results.push({ setCode, ok: false, error: err.message });
    }
  }

  return { ok: true, results };
}

async function handleSearchCards({ query, activeSets }) {
  try {
    const cards = await CardDB.searchCards(query, activeSets);
    return { ok: true, cards };
  } catch (err) {
    return { ok: false, error: err.message };
  }
}

/**
 * Add a card to inventory, then attach a location note.
 *
 * @param {object} message
 * @param {number} message.emid
 * @param {number} message.foil - 0 = regular, 1 = foil
 * @param {string} message.condition - e.g. "NM"
 * @param {string} message.language - e.g. "EN"
 * @param {string} message.locationTag - e.g. "b5r1"
 * @param {number} message.position - current position counter
 */
async function handleAddCard({
  emid,
  foil,
  condition,
  language,
  locationTag,
  position,
}) {
  if (!token) return { ok: false, error: "Not authenticated" };

  try {
    // Step 1: add to inventory
    const addResult = await EchoAPI.addInventoryBatch(
      [{ emid, quantity: 1, foil: foil || 0, condition: condition || "NM", language: language || "EN" }],
      token
    );

    // Step 2: extract the inventory ID from the response
    // The response shape is not fully documented; try common paths.
    const inventoryId =
      addResult?.items?.[0]?.echo_inventory_id ||
      addResult?.items?.[0]?.id ||
      addResult?.inventory_id ||
      addResult?.id ||
      null;

    // Step 3: attach location note if we got an ID
    const noteText = `${locationTag}p${position}`;
    let noteOk = false;

    if (inventoryId) {
      try {
        await EchoAPI.createNote(inventoryId, "inventory", noteText, token);
        noteOk = true;
      } catch (noteErr) {
        console.warn("[sw] Note creation failed:", noteErr.message);
        // Card was added but note failed — still report partial success
      }
    } else {
      console.warn(
        "[sw] Could not extract inventory ID from add response:",
        JSON.stringify(addResult)
      );
    }

    // Step 4: increment position and persist
    const newPosition = position + 1;
    await CardDB.setState("position", newPosition);

    return {
      ok: true,
      inventoryId,
      noteOk,
      noteText,
      newPosition,
    };
  } catch (err) {
    return { ok: false, error: err.message };
  }
}

async function handleGetState({ keys }) {
  try {
    if (Array.isArray(keys)) {
      const values = await CardDB.getStates(keys);
      return { ok: true, values };
    }
    const value = await CardDB.getState(keys);
    return { ok: true, value };
  } catch (err) {
    return { ok: false, error: err.message };
  }
}

async function handleSetState({ key, value }) {
  try {
    await CardDB.setState(key, value);
    return { ok: true };
  } catch (err) {
    return { ok: false, error: err.message };
  }
}

async function handleGetCachedSets() {
  try {
    const sets = await CardDB.getCachedSets();
    return { ok: true, sets };
  } catch (err) {
    return { ok: false, error: err.message };
  }
}

async function handleClearSet({ setCode }) {
  try {
    await CardDB.clearSet(setCode);
    return { ok: true };
  } catch (err) {
    return { ok: false, error: err.message };
  }
}

async function handleClearAll() {
  try {
    await CardDB.clearAll();
    return { ok: true };
  } catch (err) {
    return { ok: false, error: err.message };
  }
}

async function handleGetActiveSets() {
  try {
    const activeSets = await CardDB.getActiveSets();
    return { ok: true, activeSets };
  } catch (err) {
    return { ok: false, error: err.message };
  }
}

async function handleSetSetActive({ setCode, active }) {
  try {
    await CardDB.setSetActive(setCode, active);
    return { ok: true };
  } catch (err) {
    return { ok: false, error: err.message };
  }
}
