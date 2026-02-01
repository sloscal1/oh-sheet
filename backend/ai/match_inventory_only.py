#!/usr/bin/env python3
"""
Interactive matcher for inventory_only.csv cards.

Fetches set data from echomtg API (cached locally), finds the top 3 most
likely matches for each inventory card, and lets the user confirm matches.
Matched rows move to matched_inv_echo.csv; unmatched stay in inventory_only.csv.
"""

import asyncio
import csv
import json
import os
import re
import sys
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, "backend")
from echomtg_sync.api_client import EchoMTGClient, EchoMTGConfig

CACHE_DIR = Path("echo_set_cache")
INVENTORY_ONLY = "inventory_only.csv"
MATCHED_FILE = "matched_inv_echo.csv"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def to_ascii(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


def normalize_name(s: str) -> str:
    """Normalize a card name for comparison."""
    s = s.strip().lower()
    # Take front face
    if " // " in s:
        s = s.split(" // ")[0].strip()
    # Remove parentheticals
    s = re.sub(r"\s*\([^)]*\)", "", s).strip()
    # Remove common suffixes
    s = re.sub(r"\s+token$", "", s)
    s = re.sub(r"\s+art card.*$", "", s)
    # Normalize special chars
    s = to_ascii(s)
    return s


def score_match(inv_name: str, inv_cn: str, echo_card: dict,
                inv_set: str = "") -> float:
    """Score how likely an echo card matches an inventory card. Higher = better."""
    echo_name = echo_card.get("name", "")
    echo_cn = str(echo_card.get("collectors_number", "")).lstrip("0") or "0"

    inv_norm = normalize_name(inv_name)
    echo_norm = normalize_name(echo_name)

    score = 0.0

    # Collector number match is the strongest signal
    if inv_cn == echo_cn:
        score += 50.0

    # For FJMP/FJ22: inventory has plain number, echo has T-prefix
    # e.g., inv "0011" -> "11", echo "T11" -> strip T -> "11"
    if inv_set in ("fjmp", "fj22"):
        echo_cn_raw = str(echo_card.get("collectors_number", ""))
        is_theme = echo_cn_raw.upper().startswith("T")
        echo_cn_stripped = echo_cn_raw.lstrip("Tt").lstrip("0") or "0"
        inv_cn_stripped = inv_cn.lstrip("0") or "0"
        is_name_theme = "theme card" in echo_name.lower()
        # Strong boost when both T-prefix collector# AND theme card name match
        if inv_cn_stripped == echo_cn_stripped and is_theme and is_name_theme:
            score += 70.0
        elif inv_cn_stripped == echo_cn_stripped and is_theme:
            score += 55.0

    # Name similarity
    name_ratio = SequenceMatcher(None, inv_norm, echo_norm).ratio()
    score += name_ratio * 40.0

    # Exact normalized name match bonus
    if inv_norm == echo_norm:
        score += 10.0

    # For theme cards: "Dogs" matching "Dogs Theme Card" should score well
    # even though normalize_name doesn't strip "theme card"
    if "theme card" in echo_norm:
        echo_base = echo_norm.replace(" theme card", "").strip()
        if echo_base == inv_norm:
            score += 10.0

    # For WC98: echo uses WCD set with suffixes like "- 1998 Brian Selden" and/or "[CHR]"
    # e.g. "Survival of the Fittest - 1998 Brian Selden [CHR]"
    if inv_set == "wc98":
        echo_lower = echo_name.lower()
        if "1998" in echo_lower and "selden" in echo_lower:
            score += 20.0
        if "[chr]" in echo_lower:
            score += 10.0

    # For substitute card sets (SVOW, SMID, SNEO, SBRO, SLCI, SMOM):
    # Inventory: "Double-Faced Substitute Card" #1
    # Echo TVOW: "Helper Card (1/9)" with collector# like "H1"
    if inv_set.startswith("s") and "substitute card" in inv_norm:
        if "helper card" in echo_name.lower():
            inv_num = inv_cn.lstrip("0") or "0"
            # Check if the echo name contains "(N/M)" where N matches inv collector#
            m = re.search(r"\((\d+)/(\d+)\)", echo_name)
            if m and m.group(1) == inv_num:
                score += 80.0
            # Also check H-prefix collector numbers (H1, H2, etc.)
            echo_cn_raw = str(echo_card.get("collectors_number", ""))
            if echo_cn_raw.upper().startswith("H"):
                h_num = echo_cn_raw[1:].lstrip("0") or "0"
                if h_num == inv_num:
                    score += 80.0

    return score


# ---------------------------------------------------------------------------
# Set cache
# ---------------------------------------------------------------------------

async def fetch_and_cache_set(client: EchoMTGClient, set_code: str) -> list:
    """Fetch a set from echomtg, caching to disk."""
    CACHE_DIR.mkdir(exist_ok=True)
    cache_path = CACHE_DIR / f"{set_code.lower()}.json"

    if cache_path.exists():
        with open(cache_path) as f:
            cards = json.load(f)
        print(f"  Loaded {len(cards)} cards from cache for {set_code.upper()}")
        return cards

    # API expects lowercase p prefix: pWAR, pKHM, pSTX, etc.
    if set_code.lower().startswith("p") and len(set_code) > 3:
        api_code = "p" + set_code[1:].upper()
    else:
        api_code = set_code.upper()
    print(f"  Fetching {api_code} from echomtg API...")
    cards = await client.get_set_all(api_code)
    with open(cache_path, "w") as f:
        json.dump(cards, f)
    print(f"  Fetched and cached {len(cards)} cards for {set_code.upper()}")
    return cards


# ---------------------------------------------------------------------------
# CSV I/O
# ---------------------------------------------------------------------------

def load_csv(path):
    with open(path, "r") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames), list(reader)


def save_csv(path, fieldnames, rows):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


# ---------------------------------------------------------------------------
# Main interactive loop
# ---------------------------------------------------------------------------

async def main():
    # Load data
    inv_fields, inv_rows = load_csv(INVENTORY_ONLY)
    matched_fields, matched_rows = load_csv(MATCHED_FILE)

    # Group inventory by set code
    inv_by_set = defaultdict(list)
    for r in inv_rows:
        sc = r["Set Code"].strip().lower()
        inv_by_set[sc].append(r)

    set_codes = sorted(inv_by_set.keys(), key=lambda s: -len(inv_by_set[s]))

    print(f"Loaded {len(inv_rows)} inventory-only cards across {len(set_codes)} sets.\n")

    # Authenticate
    client = await EchoMTGClient.create()

    # Prefetch all needed sets
    echo_sets = {}
    print("Fetching/loading set data...")
    for sc in set_codes:
        # Some set codes need mapping (t-prefix tokens, s-prefix supplemental, etc.)
        # Try the exact code first, then common variants
        codes_to_try = [sc]
        if sc.startswith("f") and len(sc) == 4:
            # fjmp -> jmp, fj22 -> j22
            codes_to_try.append(sc[1:])
        if sc.startswith("s") and len(sc) == 4:
            # Substitute cards live in token sets: svow -> tvow, smid -> tmid, etc.
            # Try token set first since helper cards are there, not in main set
            codes_to_try.insert(0, "t" + sc[1:])
            codes_to_try.append(sc[1:])
        if sc.startswith("t") and len(sc) == 4:
            # tdmu -> dmu
            codes_to_try.append(sc[1:])
        if sc == "wc98":
            # WC98 -> WCD in echomtg
            codes_to_try.append("wcd")
        if sc.startswith("p") and len(sc) > 3:
            # pkhm -> khm, plist stays plist, pwar -> war, pxln -> xln
            codes_to_try.append(sc[1:])

        cards = []
        for code in codes_to_try:
            try:
                cards = await fetch_and_cache_set(client, code)
                if cards:
                    break
            except Exception as e:
                print(f"    Failed to fetch {code.upper()}: {e}")

        echo_sets[sc] = cards

    print(f"\nAll sets loaded. Starting interactive matching.\n")
    print("Commands during card review:")
    print("  <number>  - Match to candidate #N")
    print("  s         - Skip this card")
    print("  q         - Quit (saves progress)")
    print("  skip-set  - Skip remaining cards in this set")
    print()

    total_matched = 0

    for sc in set_codes:
        cards_in_set = inv_by_set[sc]
        echo_cards = echo_sets.get(sc, [])

        if not echo_cards:
            print(f"{'='*70}")
            print(f"  {sc.upper()}: {len(cards_in_set)} cards — NO ECHO DATA AVAILABLE")
            print(f"{'='*70}\n")
            continue

        print(f"{'='*70}")
        print(f"  {sc.upper()}: {len(cards_in_set)} inventory cards, {len(echo_cards)} echo cards")
        print(f"{'='*70}\n")

        skip_set = False
        i = 0
        while i < len(cards_in_set):
            r = cards_in_set[i]
            inv_name = r["Name"].strip()
            inv_cn = r["Collector Number"].strip().lstrip("0") or "0"
            inv_qty = f"{r['Reg Qty']}R/{r['Foil Qty']}F"
            inv_note = r.get("note", "")

            # Score all echo cards
            scored = []
            for ec in echo_cards:
                s = score_match(inv_name, inv_cn, ec, inv_set=sc)
                scored.append((s, ec))
            scored.sort(key=lambda x: -x[0])
            top3 = scored[:3]

            inv_finishes = r.get("finishes", "")
            inv_promo = r.get("promo", "")
            inv_border = r.get("border_color", "")

            print(f"  [{i+1}/{len(cards_in_set)}] {inv_name}")
            print(f"          {sc.upper()} #{inv_cn}  {inv_qty}  {inv_finishes}  border={inv_border}  promo={inv_promo}  note={inv_note}")
            print()
            for ci, (score, ec) in enumerate(top3):
                ec_name = ec.get("name", "")
                ec_cn = str(ec.get("collectors_number", "")).lstrip("0") or "0"
                ec_eid = ec.get("emid", "?")
                cn_flag = " <-- same collector#" if ec_cn == inv_cn else ""
                print(f"    [{ci+1}] {ec_name:<50} #{ec_cn:<6} echoid={ec_eid}{cn_flag}")
                print(f"        score={score:.1f}")
            print()

            cmd = input(f"  {sc.upper()}[{i+1}]> ").strip().lower()

            if cmd == "q":
                # Save and quit
                _save_all(inv_by_set, inv_fields, matched_fields, matched_rows, set_codes)
                print(f"\nSaved. Total matched this session: {total_matched}")
                return

            if cmd == "skip-set":
                skip_set = True
                break

            if cmd == "s":
                i += 1
                continue

            try:
                choice = int(cmd)
                if 1 <= choice <= len(top3):
                    _, echo_card = top3[choice - 1]
                    # Build matched row in echo format
                    matched_row = _build_matched_row(echo_card, r, matched_fields)
                    matched_rows.append(matched_row)
                    # Remove from inv list
                    cards_in_set.pop(i)
                    total_matched += 1
                    print(f"  -> Matched! ({total_matched} this session)\n")
                    # Don't increment i since we popped
                else:
                    print(f"  Invalid choice. Pick 1-{len(top3)}, s, or q.")
            except ValueError:
                print(f"  Unknown command: {cmd}")

        if skip_set:
            print(f"  Skipping rest of {sc.upper()}.\n")

    # Save at the end
    _save_all(inv_by_set, inv_fields, matched_fields, matched_rows, set_codes)
    print(f"\nDone. Total matched this session: {total_matched}")


def _build_matched_row(echo_card: dict, inv_row: dict, matched_fields: list) -> dict:
    """Build a matched_inv_echo.csv row from an echo API card + inventory row."""
    row = {}
    # Map echo API fields to CSV fields
    row["Reg Qty"] = inv_row.get("Reg Qty", "0")
    row["Foil Qty"] = inv_row.get("Foil Qty", "0")
    row["Name"] = echo_card.get("name", "")
    row["Set"] = echo_card.get("set", "")
    row["Rarity"] = echo_card.get("rarity", "")
    row["Acquired"] = ""
    row["Language"] = inv_row.get("Language", "EN")
    row["Date Acquired"] = ""
    row["Set Code"] = echo_card.get("set_code", echo_card.get("setcode", ""))
    row["Collector Number"] = str(echo_card.get("collectors_number", ""))
    row["Condition"] = inv_row.get("Condition", "NM")
    row["Marked as Trade"] = "0"
    row["note"] = inv_row.get("note", "")
    row["echo_inventory_id"] = ""
    row["tcgid"] = str(echo_card.get("tcgplayer_id", ""))
    row["echoid"] = str(echo_card.get("emid", ""))

    # Only keep fields that exist in matched_fields
    return {k: row.get(k, "") for k in matched_fields}


def _save_all(inv_by_set, inv_fields, matched_fields, matched_rows, set_codes):
    """Save matched and remaining inventory files."""
    # Rebuild inv_only from remaining cards across all sets
    remaining = []
    for sc in set_codes:
        remaining.extend(inv_by_set[sc])

    save_csv(INVENTORY_ONLY, inv_fields, remaining)
    save_csv(MATCHED_FILE, matched_fields, matched_rows)
    print(f"  Saved: {MATCHED_FILE} ({len(matched_rows)} rows), {INVENTORY_ONLY} ({len(remaining)} rows)")


if __name__ == "__main__":
    asyncio.run(main())
