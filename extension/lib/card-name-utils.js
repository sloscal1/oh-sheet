/**
 * Card name normalisation and variant extraction.
 *
 * Ported from backend/echomtg_sync/csv_processor.py normalize_card_name()
 * with additions for variant-tag and foil detection.
 */

/**
 * Treatment / variant parenthetical patterns to strip during normalisation.
 * Order matters: more specific patterns should come before the generic
 * capitalised-word parenthetical at the end.
 */
const TREATMENT_PATTERNS = [
  /\s*\(Retro Frame\)/i,
  /\s*\(Extended Art\)/i,
  /\s*\(Borderless\)/i,
  /\s*\(Borderless Poster\)/i,
  /\s*\(Showcase\)/i,
  /\s*\(Full Art\)/i,
  /\s*\(Foil Etched\)/i,
  /\s*\(Etched\)/i,
  /\s*\(Serialized\)/i,
  /\s*\(Surge Foil\)/i,
  /\s*\(Galaxy Foil\)/i,
  /\s*\(Textured Foil\)/i,
  /\s*\(Step-And-Compleat Foil\)/i,
  /\s*\(Flavor Text\)/i,
  /\s*\(Phyrexian\)/i,
  /\s*\(0*\d+\)/,                    // (265), (0280)
  /\s*\(\d+\/\d+\)/,                 // (15/81)
  /\s*- JP Full Art/i,
  /\s*Art Card.*$/i,
  /\s*\(Gold-Stamped.*\)/i,
  /\s+Token$/i,
  /\s*\([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\)/,  // (River), (White Sky)
];

/**
 * Foil-treatment tags that, when present in the original card name, indicate
 * a special foil variant (distinct from regular / regular-foil).
 */
const FOIL_VARIANT_TAGS = [
  "Foil Etched",
  "Surge Foil",
  "Galaxy Foil",
  "Textured Foil",
  "Step-And-Compleat Foil",
  "Gilded Foil",
  "Neon Ink",
];

/**
 * Normalize a card name for search / matching.
 *
 * - Takes only the front face of double-faced cards (before " // ")
 * - Normalises "Emblem - Name" → "Name Emblem"
 * - Strips treatment / variant parenthetical suffixes
 *
 * @param {string} name
 * @returns {string} Normalised name.
 */
export function normalizeCardName(name) {
  name = name.trim();

  // Double-faced: keep front face only
  const dfcIdx = name.indexOf(" // ");
  if (dfcIdx !== -1) {
    name = name.substring(0, dfcIdx).trim();
  }

  // Emblem normalisation
  const emblemMatch = name.match(/^Emblem\s*-\s*(.+)$/i);
  if (emblemMatch) {
    name = `${emblemMatch[1]} Emblem`;
  }

  // Strip treatment patterns repeatedly until stable
  let prev;
  do {
    prev = name;
    for (const pattern of TREATMENT_PATTERNS) {
      name = name.replace(pattern, "");
    }
    name = name.trim();
  } while (name !== prev);

  return name;
}

/**
 * Extract variant / treatment tags from a raw card name.
 *
 * Returns an array of human-readable tag strings found in the name,
 * e.g. ["Borderless", "Foil Etched"], plus a boolean indicating whether
 * the name contains a special foil variant tag.
 *
 * @param {string} name - Raw card name as returned by the API.
 * @returns {{ tags: string[], isFoilVariant: boolean }}
 */
export function extractVariantTags(name) {
  const tags = [];
  let isFoilVariant = false;

  // Match all parenthetical groups
  const parenMatches = name.matchAll(/\(([^)]+)\)/g);
  for (const m of parenMatches) {
    const content = m[1];
    // Skip purely numeric parentheticals (collector numbers)
    if (/^0*\d+$/.test(content) || /^\d+\/\d+$/.test(content)) continue;
    tags.push(content);
  }

  // Match non-parenthetical variant suffixes
  if (/Neon (?:Red|Blue|Green|Yellow)/i.test(name)) {
    const neonMatch = name.match(/Neon (?:Red|Blue|Green|Yellow)/i);
    if (neonMatch) tags.push(neonMatch[0]);
  }

  // Check foil variant status
  for (const foilTag of FOIL_VARIANT_TAGS) {
    if (name.toLowerCase().includes(foilTag.toLowerCase())) {
      isFoilVariant = true;
      break;
    }
  }

  return { tags, isFoilVariant };
}
