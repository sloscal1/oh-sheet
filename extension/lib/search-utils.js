/**
 * Advanced search utilities for Magic card names.
 * 
 * Implements multiple search strategies:
 * - Initials search ("SF" → "Stormfighter Falcon")
 * - Prefix search ("sto" → "Stormfighter")
 * - Multi-token search ("storm fal" → "Stormfighter Falcon")
 * - Hybrid strategy with intent detection
 */

// Stop words to filter out when generating initials
const STOP_WORDS = ["of", "the", "and", "a", "an", "for", "to", "in"];

/**
 * Extract tokens from a card name for indexing.
 * @param {string} name - Original card name
 * @returns {string[]} - Array of normalized tokens
 */
export function extractTokens(name) {
  return name
    .toLowerCase()
    .split(/[\s-–—]+/) // Split on spaces and dashes
    .filter(token => token.length > 0)
    .filter(token => !STOP_WORDS.includes(token));
}

/**
 * Generate initials from a card name.
 * @param {string} name - Original card name
 * @returns {string} - Lowercase initials string
 */
export function generateInitials(name) {
  const tokens = extractTokens(name);
  return tokens.map(token => token.charAt(0)).join("");
}

/**
 * Generate progressive initials for matching.
 * @param {string} name - Original card name
 * @returns {string[]} - Array of progressive initials ["s", "st", "sto", ...]
 */
export function generateProgressiveInitials(name) {
  const initials = generateInitials(name);
  const progressive = [];
  for (let i = 1; i <= initials.length; i++) {
    progressive.push(initials.substring(0, i));
  }
  return progressive;
}

/**
 * Generate strict individual character initials.
 * @param {string} name - Original card name
 * @returns {string[]} - Array of individual initials ["s", "t", "o", ...]
 */
export function generateStrictInitials(name) {
  const initials = generateInitials(name);
  return initials.split("");
}

/**
 * Normalize a card name for searching.
 * @param {string} name - Original card name
 * @returns {string} - Normalized name
 */
export function normalizeForSearch(name) {
  return name
    .toLowerCase()
    .replace(/['']/g, "") // Remove apostrophes
    .replace(/[^\w\s-]/g, "") // Remove special chars except hyphens
    .trim();
}

/**
 * Detect search intent from user input.
 * @param {string} query - User search input
 * @returns {object} - Intent object with strategy and metadata
 */
export function detectSearchIntent(query) {
  const trimmed = query.trim().toLowerCase();
  
  if (!trimmed) {
    return { strategy: "empty", query: trimmed };
  }

  // Check for pure initials (2+ uppercase letters, no spaces)
  if (/^[a-z]{2,}$/.test(trimmed) && query === query.toUpperCase()) {
    return { 
      strategy: "initials", 
      query: trimmed,
      originalCase: query // Preserve original case for exact matching
    };
  }

  // Check for space-separated initials ("S F" → "Stormfighter Falcon")
  if (/^[a-z](\s+[a-z])+$/i.test(trimmed)) {
    const initials = trimmed.replace(/\s+/g, "").toLowerCase();
    return { 
      strategy: "space_initials", 
      query: initials,
      originalCase: query.replace(/\s+/g, "")
    };
  }

  // Check for multi-token search (contains spaces)
  if (trimmed.includes(" ")) {
    const tokens = trimmed.split(/\s+/).filter(t => t.length > 0);
    return { 
      strategy: "multi_token", 
      query: trimmed,
      tokens,
      firstToken: tokens[0]
    };
  }

  // Default to prefix search
  return { 
    strategy: "prefix", 
    query: trimmed 
  };
}

/**
 * Check if a query matches initials.
 * @param {string} query - Search query (normalized)
 * @param {string} cardInitials - Card initials from database
 * @param {string[]} progressiveInitials - Progressive initials from database
 * @returns {boolean} - Whether there's a match
 */
export function matchesInitials(query, cardInitials, progressiveInitials) {
  // Exact initials match
  if (query === cardInitials) return true;
  
  // Progressive initials match (allows partial initials)
  return progressiveInitials.includes(query);
}

/**
 * Check if a query matches token prefixes.
 * @param {string[]} queryTokens - Tokens from user query
 * @param {string[]} cardTokens - Tokens from card
 * @returns {boolean} - Whether there's a match
 */
export function matchesTokenPrefixes(queryTokens, cardTokens) {
  if (queryTokens.length === 0) return false;
  
  // All query tokens must match prefixes in card tokens
  return queryTokens.every(qToken => 
    cardTokens.some(cToken => cToken.startsWith(qToken))
  );
}

/**
 * Score a card match based on strategy.
 * @param {object} intent - Search intent object
 * @param {object} card - Card record from database
 * @returns {number} - Score (lower is better)
 */
export function scoreMatch(intent, card) {
  const { strategy, query } = intent;
  
  // Handle migration: if new search fields don't exist, fall back to basic matching
  if (!card.tokens || !card.initials) {
    // Fallback to basic substring matching
    const nameToMatch = card.name_normalized || card.name_lower || card.name || "";
    switch (strategy) {
      case "initials":
      case "space_initials":
        // For old cards, try to match initials on the fly
        const fallbackInitials = generateInitials(card.name || "");
        return query === fallbackInitials ? 0 : 1000;
        
      case "multi_token":
        const fallbackTokens = extractTokens(card.name || "");
        const queryTokens = intent.tokens;
        const matchedTokens = queryTokens.filter(qToken => 
          fallbackTokens.some(cToken => cToken.startsWith(qToken))
        ).length;
        return matchedTokens === queryTokens.length ? 500 : 1000;
        
      case "prefix":
        const nameStart = nameToMatch.indexOf(query);
        return nameStart === 0 ? 100 : 1000;
        
      default:
        return 1000;
    }
  }
  
  // New search fields available - use optimized scoring
  switch (strategy) {
    case "initials":
      // Perfect initials match gets highest priority
      return query === card.initials ? 0 : 100;
      
    case "space_initials":
      // Space-separated initials
      return query === card.initials ? 0 : 100;
      
    case "multi_token":
      // Score based on how many tokens match and how early
      const queryTokens = intent.tokens;
      const cardTokens = card.tokens || [];
      let score = 0;
      let matchedTokens = 0;
      
      queryTokens.forEach((qToken, i) => {
        const tokenIndex = cardTokens.findIndex(cToken => 
          cToken.startsWith(qToken)
        );
        if (tokenIndex !== -1) {
          matchedTokens++;
          score += tokenIndex; // Prefer earlier matches
          score += i * 0.1; // Prefer earlier query tokens
        }
      });
      
      return matchedTokens === queryTokens.length ? score : 1000;
      
    case "prefix":
      // Prefix match score based on position
      const nameStart = card.search_normalized.indexOf(query);
      return nameStart === 0 ? 0 : nameStart;
      
    default:
      return 1000;
  }
}