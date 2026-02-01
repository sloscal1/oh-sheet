/**
 * IndexedDB wrapper for the card cache and application state.
 *
 * Database: echomtg_fast_inventory
 *
 * Object stores
 * ─────────────
 *  cards  (keyPath: "emid")
 *    Indexes: by_first_letter, by_set_code, by_name
 *
 *  sets   (keyPath: "set_code")
 *    Cache metadata per set (card count, cached timestamp).
 *
 *  state  (keyPath: "key")
 *    Arbitrary key/value pairs for persisting location, position,
 *    dividerEvery, foil, language, etc.
 */

import { normalizeCardName, extractVariantTags } from "./card-name-utils.js";
import { 
  extractTokens, 
  generateInitials, 
  generateProgressiveInitials, 
  normalizeForSearch,
  detectSearchIntent,
  matchesInitials,
  matchesTokenPrefixes,
  scoreMatch
} from "./search-utils.js";

const DB_NAME = "echomtg_fast_inventory";
const DB_VERSION = 2;

/** @type {IDBDatabase|null} */
let _db = null;

/**
 * Open (or create) the database.  Returns the same instance on subsequent
 * calls within the same execution context.
 *
 * @returns {Promise<IDBDatabase>}
 */
function openDB() {
  if (_db) return Promise.resolve(_db);

  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);

    req.onupgradeneeded = () => {
      const db = req.result;

      if (!db.objectStoreNames.contains("cards")) {
        const cards = db.createObjectStore("cards", { keyPath: "emid" });
        cards.createIndex("by_first_letter", "first_letter", { unique: false });
        cards.createIndex("by_set_code", "set_code", { unique: false });
        cards.createIndex("by_name", "name_lower", { unique: false });
        cards.createIndex("by_initials", "initials", { unique: false });
        cards.createIndex("by_search_normalized", "search_normalized", { unique: false });
      } else {
        // Handle migration from version 1 to 2
        const cards = req.result.transaction(["cards"], "readwrite").objectStore("cards");
        
        // Add new indexes if they don't exist
        if (!cards.indexNames.contains("by_initials")) {
          cards.createIndex("by_initials", "initials", { unique: false });
        }
        if (!cards.indexNames.contains("by_search_normalized")) {
          cards.createIndex("by_search_normalized", "search_normalized", { unique: false });
        }
      }

      if (!db.objectStoreNames.contains("sets")) {
        db.createObjectStore("sets", { keyPath: "set_code" });
      }

      if (!db.objectStoreNames.contains("state")) {
        db.createObjectStore("state", { keyPath: "key" });
      }
    };

    req.onsuccess = () => {
      _db = req.result;
      resolve(_db);
    };
    req.onerror = () => reject(req.error);
  });
}

/**
 * Wrap an IDBRequest in a Promise.
 * @param {IDBRequest} req
 * @returns {Promise<any>}
 */
function promisify(req) {
  return new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

/**
 * Wrap an IDBTransaction's completion in a Promise.
 * @param {IDBTransaction} tx
 * @returns {Promise<void>}
 */
function txComplete(tx) {
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
    tx.onabort = () => reject(tx.error || new Error("Transaction aborted"));
  });
}

// ---------------------------------------------------------------------------
// Card record helpers
// ---------------------------------------------------------------------------

/**
 * Transform a raw API card object into the shape stored in IndexedDB.
 *
 * @param {object} raw - Card object from EchoMTG API (see neo.json for shape).
 * @param {string} setCode - Normalised set code.
 * @param {string} setName - Human-readable set name.
 * @returns {object} Card record.
 */
export function toCardRecord(raw, setCode, setName) {
  const name = (raw.name || "").trim();
  const nameLower = name.toLowerCase();
  const nameNormalized = normalizeCardName(name).toLowerCase();
  const searchNormalized = normalizeForSearch(name);
  const { tags, isFoilVariant } = extractVariantTags(name);

  // Generate search indexes
  const tokens = extractTokens(name);
  const initials = generateInitials(name);
  const progressiveInitials = generateProgressiveInitials(name);

  return {
    emid: raw.emid,
    name,
    name_lower: nameLower,
    name_normalized: nameNormalized,
    search_normalized: searchNormalized,
    first_letter: searchNormalized.charAt(0) || "",
    tokens,
    initials,
    progressive_initials: progressiveInitials,
    set_code: setCode,
    set_name: setName,
    collectors_number: raw.collectors_number,
    rarity: (raw.rarity || "").trim(),
    main_type: (raw.main_type || "").trim(),
    image: raw.image || "",
    image_cropped: raw.image_cropped || "",
    variant_tags: tags,
    is_foil_variant: isFoilVariant,
  };
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

const CardDB = {
  /**
   * Store an array of card records for a set, replacing any previous cache.
   *
   * @param {string} setCode
   * @param {string} setName
   * @param {object[]} rawCards - Raw card objects from the API.
   * @returns {Promise<number>} Number of cards stored.
   */
  async cacheSet(setCode, setName, rawCards) {
    const db = await openDB();
    const tx = db.transaction(["cards", "sets"], "readwrite");
    const cardStore = tx.objectStore("cards");
    const setStore = tx.objectStore("sets");

    for (const raw of rawCards) {
      const record = toCardRecord(raw, setCode, setName);
      cardStore.put(record);
    }

    setStore.put({
      set_code: setCode,
      set_name: setName,
      card_count: rawCards.length,
      cached_at: Date.now(),
      active: true, // Default to active when cached
    });

    await txComplete(tx);
    return rawCards.length;
  },

  /**
   * Remove all cached cards for a set.
   *
   * @param {string} setCode
   * @returns {Promise<void>}
   */
  async clearSet(setCode) {
    const db = await openDB();
    const tx = db.transaction(["cards", "sets"], "readwrite");
    const cardStore = tx.objectStore("cards");
    const setStore = tx.objectStore("sets");

    // Delete cards by set_code index
    const index = cardStore.index("by_set_code");
    const range = IDBKeyRange.only(setCode);
    let cursor = await promisify(index.openCursor(range));
    while (cursor) {
      cursor.delete();
      cursor = await promisify(cursor.continue());
    }

    setStore.delete(setCode);
    await txComplete(tx);
  },

  /**
   * Clear all cached data (cards and sets).
   * @returns {Promise<void>}
   */
  async clearAll() {
    const db = await openDB();
    const tx = db.transaction(["cards", "sets"], "readwrite");
    tx.objectStore("cards").clear();
    tx.objectStore("sets").clear();
    await txComplete(tx);
  },

  /**
   * Set a cached set as active or inactive for searching.
   * @param {string} setCode
   * @param {boolean} active
   * @returns {Promise<void>}
   */
  async setSetActive(setCode, active) {
    const db = await openDB();
    const tx = db.transaction("sets", "readwrite");
    const store = tx.objectStore("sets");
    const existing = await promisify(store.get(setCode));
    if (existing) {
      existing.active = active;
      store.put(existing);
    }
    await txComplete(tx);
  },

  /**
   * Get active set codes for searching.
   * @returns {Promise<string[]>}
   */
  async getActiveSets() {
    const db = await openDB();
    const tx = db.transaction("sets", "readonly");
    const store = tx.objectStore("sets");
    const sets = await promisify(store.getAll());
    return sets
      .filter(set => set.active !== false) // Default to true if not specified
      .map(set => set.set_code);
  },

  /**
   * List cached sets with metadata.
   * @returns {Promise<object[]>}
   */
  async getCachedSets() {
    const db = await openDB();
    const tx = db.transaction("sets", "readonly");
    return promisify(tx.objectStore("sets").getAll());
  },

  /**
   * Advanced multi-strategy card search.
   *
   * Implements multiple search strategies:
   * - Initials search ("SF" → "Stormfighter Falcon")
   * - Space-separated initials ("S F" → "Stormfighter Falcon") 
   * - Multi-token search ("storm fal" → "Stormfighter Falcon")
   * - Prefix search ("sto" → "Stormfighter")
   *
   * @param {string} query - User's search input.
   * @param {string[]} [activeSets] - If provided, only return cards from
   *   these set codes. Empty array means "all cached sets".
   * @param {number} [maxResults=20]
   * @returns {Promise<object[]>} Matching card records sorted by relevance.
   */
  async searchCards(query, activeSets, maxResults = 20) {
    if (!query || !query.trim()) return [];

    const intent = detectSearchIntent(query);
    const setFilter =
      activeSets && activeSets.length > 0
        ? new Set(activeSets.map((s) => s.toUpperCase()))
        : null;

    let candidates = [];

    switch (intent.strategy) {
      case "initials":
        candidates = await this.searchByInitials(intent.query, setFilter);
        break;
        
      case "space_initials":
        candidates = await this.searchByInitials(intent.query, setFilter);
        break;
        
      case "multi_token":
        candidates = await this.searchByMultiToken(intent.tokens, intent.firstToken, setFilter);
        break;
        
      case "prefix":
        candidates = await this.searchByPrefix(intent.query, setFilter);
        break;
        
      default:
        return [];
    }

    // Score and sort results
    const scored = candidates.map(card => ({
      card,
      score: scoreMatch(intent, card)
    }));

    scored.sort((a, b) => a.score - b.score);
    
    return scored
      .slice(0, maxResults)
      .map(item => item.card);
  },

  /**
   * Search by initials using the initials index.
   */
  async searchByInitials(query, setFilter) {
    const db = await openDB();
    const tx = db.transaction("cards", "readonly");
    const index = tx.objectStore("cards").index("by_initials");

    const results = [];
    return new Promise((resolve, reject) => {
      const req = index.openCursor();
      req.onsuccess = () => {
        const cursor = req.result;
        if (!cursor) {
          resolve(results);
          return;
        }
        
        const card = cursor.value;
        // Handle migration: check if search fields exist, if not skip
        if (!card.initials || !card.progressive_initials) {
          cursor.continue();
          return;
        }
        
        if (
          (card.initials.startsWith(query) || card.progressive_initials.includes(query)) &&
          (!setFilter || setFilter.has(card.set_code))
        ) {
          results.push(card);
        }
        cursor.continue();
      };
      req.onerror = () => reject(req.error);
    });
  },

  /**
   * Search by multi-token prefix matching.
   */
  async searchByMultiToken(tokens, firstToken, setFilter) {
    if (!firstToken) return [];

    const db = await openDB();
    const tx = db.transaction("cards", "readonly");
    
    // Use first letter of first token for initial filtering
    const index = tx.objectStore("cards").index("by_first_letter");
    const range = IDBKeyRange.only(firstToken.charAt(0));

    const results = [];
    return new Promise((resolve, reject) => {
      const req = index.openCursor(range);
      req.onsuccess = () => {
        const cursor = req.result;
        if (!cursor) {
          resolve(results);
          return;
        }
        
        const card = cursor.value;
        // Handle migration: check if search fields exist
        if (!card.tokens) {
          cursor.continue();
          return;
        }
        
        const cardTokens = card.tokens || [];
        
        if (
          matchesTokenPrefixes(tokens, cardTokens) &&
          (!setFilter || setFilter.has(card.set_code))
        ) {
          results.push(card);
        }
        cursor.continue();
      };
      req.onerror = () => reject(req.error);
    });
  },

  /**
   * Search by prefix using the search_normalized index.
   */
  async searchByPrefix(query, setFilter) {
    if (!query) return [];

    const db = await openDB();
    const tx = db.transaction("cards", "readonly");
    const index = tx.objectStore("cards").index("by_search_normalized");
    
    // For prefix search, we need to iterate through all entries
    // starting with the query
    const lowerBound = IDBKeyRange.lowerBound(query);
    const upperBound = IDBKeyRange.upperBound(query + '\uffff'); // Unicode max char

    const results = [];
    return new Promise((resolve, reject) => {
      const req = index.openCursor(lowerBound);
      req.onsuccess = () => {
        const cursor = req.result;
        if (!cursor || !cursor.key.startsWith(query)) {
          resolve(results);
          return;
        }
        
        const card = cursor.value;
        if (!setFilter || setFilter.has(card.set_code)) {
          results.push(card);
        }
        cursor.continue();
      };
      req.onerror = () => reject(req.error);
    });
  },

  // -----------------------------------------------------------------------
  // State helpers
  // -----------------------------------------------------------------------

  /**
   * Read a value from the state store.
   * @param {string} key
   * @returns {Promise<any>} The stored value, or undefined.
   */
  async getState(key) {
    const db = await openDB();
    const tx = db.transaction("state", "readonly");
    const record = await promisify(tx.objectStore("state").get(key));
    return record?.value;
  },

  /**
   * Write a value to the state store.
   * @param {string} key
   * @param {any} value
   * @returns {Promise<void>}
   */
  async setState(key, value) {
    const db = await openDB();
    const tx = db.transaction("state", "readwrite");
    tx.objectStore("state").put({ key, value });
    await txComplete(tx);
  },

  /**
   * Read multiple state keys at once.
   * @param {string[]} keys
   * @returns {Promise<object>} Map of key → value.
   */
  async getStates(keys) {
    const db = await openDB();
    const tx = db.transaction("state", "readonly");
    const store = tx.objectStore("state");
    const result = {};
    for (const key of keys) {
      const record = await promisify(store.get(key));
      result[key] = record?.value;
    }
    return result;
  },
};

export default CardDB;
