/**
 * EchoMTG API client.
 *
 * Ported from backend/echomtg_sync/api_client.py.
 * Uses RateLimiter for request throttling and BrowserAPI for token storage.
 */

import BrowserAPI from "./browser-api.js";
import RateLimiter from "./rate-limiter.js";

const BASE_URL = "https://api.echomtg.com/api";
const MAX_RETRIES = 3;
const TIMEOUT_MS = 30000;

const limiter = new RateLimiter(2);

/**
 * Internal: make a single fetch with a timeout.
 * @param {string} url
 * @param {RequestInit} opts
 * @returns {Promise<Response>}
 */
function fetchWithTimeout(url, opts) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  return fetch(url, { ...opts, signal: controller.signal }).finally(() =>
    clearTimeout(timer)
  );
}

/**
 * Make an API request with rate-limiting and retry logic.
 *
 * - 429 → exponential back-off (2^attempt seconds)
 * - 500+ → linear retry (1 s wait)
 * - Other errors → throw immediately
 *
 * @param {string} method - HTTP method.
 * @param {string} endpoint - Path relative to BASE_URL (e.g. "/user/auth").
 * @param {object} [options]
 * @param {object} [options.data] - JSON body for POST requests.
 * @param {object} [options.params] - Query-string params for GET requests.
 * @param {string} [options.token] - Bearer token (omit for unauthenticated calls).
 * @returns {Promise<object>} Parsed JSON response.
 */
async function request(method, endpoint, { data, params, token } = {}) {
  let url = `${BASE_URL}${endpoint}`;
  if (params) {
    const qs = new URLSearchParams(params).toString();
    url = `${url}?${qs}`;
  }

  const headers = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
    headers["Content-Type"] = "application/json";
  }

  const fetchOpts = { method, headers };
  if (data !== undefined) {
    fetchOpts.body = JSON.stringify(data);
  }

  for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
    try {
      const response = await limiter.schedule(() =>
        fetchWithTimeout(url, fetchOpts)
      );

      if (response.ok) {
        return response.json();
      }

      if (response.status === 429) {
        const wait = 2 ** attempt * 1000;
        console.warn(`[echo-api] 429 rate-limited, waiting ${wait}ms…`);
        await new Promise((r) => setTimeout(r, wait));
        continue;
      }

      if (response.status >= 500) {
        console.warn(
          `[echo-api] ${response.status} server error, retry ${attempt + 1}/${MAX_RETRIES}`
        );
        await new Promise((r) => setTimeout(r, 1000));
        continue;
      }

      // 4xx (other than 429) — don't retry
      const body = await response.text();
      throw new Error(`HTTP ${response.status}: ${body}`);
    } catch (err) {
      if (err.name === "AbortError") {
        console.warn(
          `[echo-api] timeout, retry ${attempt + 1}/${MAX_RETRIES}`
        );
        await new Promise((r) => setTimeout(r, 1000));
        continue;
      }
      // Re-throw non-retryable errors (e.g. 4xx thrown above)
      if (err.message?.startsWith("HTTP ")) throw err;
      // Network errors — retry
      if (attempt === MAX_RETRIES - 1) throw err;
      console.warn(`[echo-api] network error, retry ${attempt + 1}/${MAX_RETRIES}`);
      await new Promise((r) => setTimeout(r, 1000));
    }
  }

  throw new Error(`Failed after ${MAX_RETRIES} retries: ${endpoint}`);
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

const EchoAPI = {
  /**
   * Authenticate with email/password.
   * Stores the token in BrowserAPI.storage for persistence across service
   * worker restarts.
   *
   * @param {string} email
   * @param {string} password
   * @returns {Promise<{token: string, user: string}>}
   */
  async login(email, password) {
    const data = await request("POST", "/user/auth", {
      data: { email, password },
    });

    const token =
      data.token || data.access_token || data.api_key;
    if (!token) {
      throw new Error("No token in auth response");
    }

    await BrowserAPI.storage.set({ echoToken: token });

    const user =
      data.user || data.email || data.username || email;
    return { token, user };
  },

  /**
   * Load a previously stored token from extension storage.
   * @returns {Promise<string|null>}
   */
  async getStoredToken() {
    const { echoToken } = await BrowserAPI.storage.get("echoToken");
    return echoToken || null;
  },

  /**
   * Clear the stored token (logout).
   */
  async logout() {
    await BrowserAPI.storage.remove("echoToken");
  },

  /**
   * Fetch a page of cards for a set.
   *
   * @param {string} setCode
   * @param {string} token
   * @param {number} [start=0]
   * @param {number} [limit=5000]
   * @returns {Promise<object>}
   */
  async getSet(setCode, token, start = 0, limit = 5000) {
    return request("GET", "/data/set", {
      params: { set_code: setCode, minified: "true", start, limit },
      token,
    });
  },

  /**
   * Fetch all cards in a set, paginating automatically.
   *
   * @param {string} setCode
   * @param {string} token
   * @param {number} [pageSize=100]
   * @returns {Promise<object[]>} Array of card objects.
   */
  async getSetAll(setCode, token, pageSize = 100) {
    const allCards = [];
    let start = 0;

    while (true) {
      const data = await this.getSet(setCode, token, start, pageSize);
      const cards = data?.set?.items || [];
      if (cards.length === 0) break;
      allCards.push(...cards);
      if (cards.length < pageSize) break;
      start += pageSize;
    }

    return allCards;
  },

  /**
   * Add cards to inventory.
   *
   * @param {object[]} items - Array of {emid, quantity, foil, condition, language}.
   * @param {string} token
   * @returns {Promise<object>}
   */
  async addInventoryBatch(items, token) {
    return request("POST", "/inventory/add/batch", { data: items, token });
  },

  /**
   * Create a note on a resource.
   *
   * @param {string|number} targetId
   * @param {string} targetApp - e.g. "inventory"
   * @param {string} noteText
   * @param {string} token
   * @returns {Promise<object>}
   */
  async createNote(targetId, targetApp, noteText, token) {
    return request("POST", "/notes/create", {
      data: { target_id: targetId, target_app: targetApp, note: noteText },
      token,
    });
  },
};

export default EchoAPI;
