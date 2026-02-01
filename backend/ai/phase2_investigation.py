#!/usr/bin/env python3
"""
Phase 2 Investigation: Inventory Cards Missing from EchoMTG

Categorizes all inventory cards not found in echomtg, presents them
category by category for investigation, and applies matching/skip logic.

Outputs:
- Updated inventory_with_locations_compact_fixed.csv with echo_matched_id
- phase2_cards_to_upload.csv for cards that need adding to echomtg
"""

from __future__ import annotations

import csv
import re
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class EchoCard:
    """A card from the echomtg export."""
    name: str
    set_name: str
    set_code: str
    collector_num: str
    inventory_id: str
    echo_id: str
    reg_qty: str
    foil_qty: str


@dataclass
class InventoryCard:
    """A card from the local inventory."""
    name: str
    set_code: str
    collector_num: str
    note: str
    reg_qty: float
    foil_qty: float
    echo_matched_id: str = ""
    row_data: Dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

class Phase2Investigator:
    INVENTORY_FILE = "inventory_with_locations_compact_fixed.csv"
    ECHO_FILE = "echomtg-export-2ManyCards-01-26-2026.csv"
    UPLOAD_FILE = "phase2_cards_to_upload.csv"

    # Categories in investigation order
    CATEGORY_ORDER = [
        "dual_faced_front_in_echo",
        "dfc_diff_collector",
        "token_set",
        "art_series",
        "diff_collector_same_set",
        "world_championship",
        "partial_name_match",
        "supplemental",
        "uncategorized",
        "jumpstart_front",
        "dual_faced_not_in_echo",
        "the_list",
        "special_chars",
        "promo_set",
        "anthology",
    ]

    CATEGORY_DESCRIPTIONS = {
        "dual_faced_front_in_echo": "Inventory has 'Front // Back' but echo has just 'Front'. Auto-match by collector#.",
        "dfc_diff_collector": "DFC front face found in echo but at a different collector# (variant/showcase numbering).",
        "token_set": "Cards from token sets (t-prefixed set codes like tdmu). Likely skip or partial match.",
        "art_series": "Art series cards (a-prefixed set codes like amh2). Likely skip or partial match.",
        "diff_collector_same_set": "Same name and set but different collector number (e.g., basic land art variants in JMP).",
        "world_championship": "World Championship deck cards (wc97, wc98, etc.).",
        "partial_name_match": "Names partially match an echo entry (substring match). May be DFCs or name variants.",
        "supplemental": "Substitute/supplemental cards (s-prefixed set codes like svow, smid).",
        "uncategorized": "Cards that don't fit other categories. Needs manual investigation.",
        "jumpstart_front": "Jumpstart front/theme cards (fjmp set code).",
        "dual_faced_not_in_echo": "DFC cards (has //) where echo doesn't have even the front face. Likely needs upload.",
        "the_list": "Cards from 'The List' (plist set code).",
        "special_chars": "Names with non-ASCII characters that may cause matching issues.",
        "promo_set": "Promo set cards (p-prefixed set codes, excluding plist).",
        "anthology": "Anthology/guild kit cards (ath, gk1, gk2).",
    }

    SUPPLEMENTAL_SETS = frozenset([
        "svow", "smid", "sneo", "swoe", "slci", "sbro", "sone", "slst", "smom",
    ])

    def __init__(self):
        # Echo data indexes
        self.echo_exact: set = set()  # (name.lower(), set_code, collector_num)
        self.echo_by_name_set: Dict[Tuple[str, str], List[str]] = defaultdict(list)
        self.echo_by_basename_set: Dict[Tuple[str, str], List[str]] = defaultdict(list)
        self.echo_names: Dict[str, set] = defaultdict(set)  # set_code -> names
        self.echo_rows: Dict[Tuple[str, str, str], List[Dict]] = defaultdict(list)

        # Inventory data
        self.inventory_rows: List[InventoryCard] = []
        self.inventory_fieldnames: List[str] = []

        # Missing cards categorized
        self.categories: Dict[str, List[Dict]] = defaultdict(list)
        self.missing: List[Dict] = []

        # Actions applied per category
        self.actions: Dict[str, str] = {}  # category -> action description

        # Cards to upload
        self.to_upload: List[Dict] = []

        # Stats
        self.matched_count = 0
        self.skipped_count = 0
        self.upload_count = 0

        self._load_echo()
        self._load_inventory()
        self._find_and_categorize_missing()

    # -- Loading --

    def _load_echo(self):
        """Load echomtg export and build indexes."""
        print("Loading echomtg export...")
        with open(self.ECHO_FILE, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                set_code = row["Set Code"].strip().lower()
                collector_num = row["Collector Number"].strip().lstrip("0") or "0"
                name = row["Name"].strip()

                self.echo_exact.add((name.lower(), set_code, collector_num))
                self.echo_by_name_set[(name.lower(), set_code)].append(collector_num)
                self.echo_names[set_code].add(name.lower())

                base_name = re.sub(r"\s*\([^)]*\)\s*$", "", name).strip().lower()
                self.echo_by_basename_set[(base_name, set_code)].append(collector_num)

                key = (name.lower(), set_code, collector_num)
                self.echo_rows[key].append(row)

    def _load_inventory(self):
        """Load inventory CSV."""
        print("Loading inventory...")
        with open(self.INVENTORY_FILE, "r") as f:
            reader = csv.DictReader(f)
            self.inventory_fieldnames = list(reader.fieldnames)
            if "echo_matched_id" not in self.inventory_fieldnames:
                self.inventory_fieldnames.append("echo_matched_id")

            for row in reader:
                if "echo_matched_id" not in row:
                    row["echo_matched_id"] = ""
                card = InventoryCard(
                    name=row["Name"].strip(),
                    set_code=row["Set Code"].strip().lower(),
                    collector_num=row["Collector Number"].strip().lstrip("0") or "0",
                    note=row.get("note", ""),
                    reg_qty=float(row["Reg Qty"] or 0),
                    foil_qty=float(row["Foil Qty"] or 0),
                    echo_matched_id=row.get("echo_matched_id", ""),
                    row_data=row,
                )
                self.inventory_rows.append(card)

    def _is_matched_in_echo(self, name: str, set_code: str, collector_num: str) -> bool:
        """Check if a card is already matched in echomtg (exact or basename)."""
        if (name.lower(), set_code, collector_num) in self.echo_exact:
            return True
        base_name = re.sub(r"\s*\([^)]*\)\s*$", "", name).strip().lower()
        if (base_name, set_code) in self.echo_by_basename_set:
            if collector_num in self.echo_by_basename_set[(base_name, set_code)]:
                return True
        if (name.lower(), set_code) in self.echo_by_basename_set:
            if collector_num in self.echo_by_basename_set[(name.lower(), set_code)]:
                return True
        return False

    def _find_and_categorize_missing(self):
        """Find all inventory cards missing from echomtg and categorize them."""
        print("Finding missing cards...")
        for card in self.inventory_rows:
            if self._is_matched_in_echo(card.name, card.set_code, card.collector_num):
                continue

            m = {
                "name": card.name,
                "set_code": card.set_code,
                "collector_num": card.collector_num,
                "reg_qty": card.reg_qty,
                "foil_qty": card.foil_qty,
                "note": card.note,
                "inv_card": card,
            }
            self.missing.append(m)
            self._categorize(m)

        print(f"Total inventory cards missing from echomtg: {len(self.missing)}")
        print()
        self._print_category_summary()

    def _categorize(self, m: Dict):
        """Assign a category to a missing card."""
        name = m["name"]
        set_code = m["set_code"]

        # Token sets (t-prefixed)
        if set_code.startswith("t"):
            self.categories["token_set"].append(m)
            return

        # Art series sets (a-prefixed, 4 chars)
        if set_code.startswith("a") and len(set_code) == 4:
            self.categories["art_series"].append(m)
            return

        # World Championship decks
        if set_code.startswith("wc") or set_code in ("pcel",):
            self.categories["world_championship"].append(m)
            return

        # Jumpstart front cards
        if set_code in ("fjmp",):
            self.categories["jumpstart_front"].append(m)
            return

        # Dual-faced with //
        if "//" in name:
            front_face = name.split("//")[0].strip().lower()
            if (front_face, set_code) in self.echo_by_name_set:
                m["front_face"] = front_face
                m["echo_collectors"] = self.echo_by_name_set[(front_face, set_code)]
                self.categories["dual_faced_front_in_echo"].append(m)
            else:
                self.categories["dual_faced_not_in_echo"].append(m)
            return

        # Anthologies / guild kits
        if set_code in ("ath", "gk1", "gk2"):
            self.categories["anthology"].append(m)
            return

        # Special characters
        if any(ord(c) > 127 for c in name):
            self.categories["special_chars"].append(m)
            return

        # Same name, same set, different collector number
        if (name.lower(), set_code) in self.echo_by_name_set:
            m["echo_collectors"] = self.echo_by_name_set[(name.lower(), set_code)]
            self.categories["diff_collector_same_set"].append(m)
            return

        # Partial name match (substring)
        found_partial = False
        for echo_name in self.echo_names.get(set_code, set()):
            if name.lower() in echo_name or echo_name in name.lower():
                if echo_name != name.lower():
                    m["echo_partial"] = echo_name
                    self.categories["partial_name_match"].append(m)
                    found_partial = True
                    break
        if found_partial:
            return

        # Promo sets (p-prefixed, not plist)
        if set_code.startswith("p") and set_code != "plist":
            self.categories["promo_set"].append(m)
            return

        # The List
        if set_code == "plist":
            self.categories["the_list"].append(m)
            return

        # Supplemental sets
        if set_code in self.SUPPLEMENTAL_SETS:
            self.categories["supplemental"].append(m)
            return

        self.categories["uncategorized"].append(m)

    # -- Display helpers --

    def _print_category_summary(self):
        """Print summary of all categories."""
        print("=" * 80)
        print("  CATEGORY SUMMARY")
        print("=" * 80)
        total = 0
        for cat in self.CATEGORY_ORDER:
            items = self.categories.get(cat, [])
            count = len(items)
            total += count
            action = self.actions.get(cat, "")
            action_str = f"  [{action}]" if action else ""
            print(f"  {cat:<35} {count:>5}{action_str}")
        print(f"  {'TOTAL':<35} {total:>5}")
        print()

    def show_category(self, cat: str, n: int = 15):
        """Show examples from a category."""
        items = self.categories.get(cat, [])
        if not items:
            print(f"No cards in category '{cat}'.")
            return

        desc = self.CATEGORY_DESCRIPTIONS.get(cat, "")
        print()
        print("=" * 80)
        print(f"  {cat.upper()} ({len(items)} cards)")
        if desc:
            print(f"  {desc}")
        print("=" * 80)

        for i, m in enumerate(items[:n]):
            extras = []
            if "front_face" in m:
                collectors = m.get("echo_collectors", [])[:3]
                extras.append(f"Front face in echo at #{collectors}")
            elif "echo_collectors" in m:
                collectors = m.get("echo_collectors", [])[:3]
                extras.append(f"Echo has collectors: {collectors}")
            if "echo_partial" in m:
                extras.append(f"Partial echo match: '{m['echo_partial']}'")

            qty_str = f"{int(m['reg_qty'])}R/{int(m['foil_qty'])}F"
            print(
                f"  {i+1:>3}. {m['name'][:50]:<50} "
                f"{m['set_code'].upper():<6} #{m['collector_num']:<6} "
                f"{qty_str:<6} {m['note'][:15]}"
            )
            for ex in extras:
                print(f"       -> {ex}")

        if len(items) > n:
            print(f"\n  ... and {len(items) - n} more")
        print()

    def show_category_sets(self, cat: str):
        """Show which sets appear in a category and how many cards per set."""
        items = self.categories.get(cat, [])
        by_set = defaultdict(int)
        for m in items:
            by_set[m["set_code"].upper()] += 1
        print(f"\n  Sets in {cat}:")
        for s, c in sorted(by_set.items(), key=lambda x: -x[1]):
            print(f"    {s}: {c}")
        print()

    # -- Matching actions --

    def apply_auto_match_art_series(self, cat: str = "art_series"):
        """Auto-match art series cards.

        Inventory names: "Card Name // Card Name" (front // back identical)
        Echo names: "card name art card", "card name art card (gold-stamped signature)",
                    "card name art card (33/81) (gold-stamped signature)", etc.

        Strategy: take inventory front face, find echo name that starts with
        "{front_face} art card" in the same set code, then match by collector#.
        Also handles special char differences (e.g. clavileño vs clavileno).
        """
        import unicodedata

        def to_ascii(s):
            return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()

        items = self.categories.get(cat, [])
        matched = 0
        no_match = 0
        no_match_items = []

        for m in items:
            inv_card: InventoryCard = m["inv_card"]
            set_code = inv_card.set_code
            collector_num = inv_card.collector_num

            # Get front face name (before " // ")
            inv_name = inv_card.name
            front_face = inv_name.split("//")[0].strip().lower() if "//" in inv_name else inv_name.lower()
            front_ascii = to_ascii(front_face)

            # Build expected echo prefix
            prefix = f"{front_face} art card"
            prefix_ascii = f"{front_ascii} art card"

            found = False
            for echo_name_lower in self.echo_names.get(set_code, set()):
                echo_ascii = to_ascii(echo_name_lower)
                if echo_ascii.startswith(prefix_ascii) or echo_name_lower.startswith(prefix):
                    # Name matches - look up by collector#
                    ek = (echo_name_lower, set_code, collector_num)
                    entries = self.echo_rows.get(ek, [])
                    if entries:
                        echo_inv_id = entries[0].get("echo_inventory_id", "")
                        if echo_inv_id:
                            inv_card.echo_matched_id = echo_inv_id
                            inv_card.row_data["echo_matched_id"] = echo_inv_id
                            matched += 1
                            found = True
                            break

                    # Try any collector# for this echo name
                    for cn in self.echo_by_name_set.get((echo_name_lower, set_code), []):
                        ek2 = (echo_name_lower, set_code, cn)
                        entries2 = self.echo_rows.get(ek2, [])
                        if entries2:
                            echo_inv_id = entries2[0].get("echo_inventory_id", "")
                            if echo_inv_id:
                                inv_card.echo_matched_id = echo_inv_id
                                inv_card.row_data["echo_matched_id"] = echo_inv_id
                                matched += 1
                                found = True
                                break
                    if found:
                        break

            if not found:
                no_match += 1
                no_match_items.append(m)

        self.matched_count += matched
        self.actions[cat] = f"AUTO-MATCH ART ({matched} matched, {no_match} unmatched)"
        print(f"Art series auto-match: {matched} matched, {no_match} unmatched.")

        if no_match_items:
            print(f"\nUnmatched art cards ({no_match}):")
            shown = set()
            for m in no_match_items:
                key = (m["name"], m["set_code"])
                if key not in shown:
                    shown.add(key)
                    print(f"  {m['name'][:50]:<50} {m['set_code'].upper():<6} #{m['collector_num']}")
                if len(shown) >= 20:
                    remaining = no_match - len(shown)
                    if remaining > 0:
                        print(f"  ... and {remaining} more unique")
                    break

    def apply_skip(self, cat: str):
        """Mark a category as skipped (not relevant for echomtg)."""
        items = self.categories.get(cat, [])
        self.actions[cat] = f"SKIP ({len(items)})"
        self.skipped_count += len(items)
        print(f"Skipped {len(items)} cards in '{cat}'.")

    def apply_auto_match_token_set(self, cat: str = "token_set"):
        """Auto-match token/emblem cards by normalizing echo naming conventions.

        Echo naming patterns for tokens:
        - "Card Name Token" or "Card Name (collector#) Token"
        - "Emblem - Card Name" (inventory has "Card Name Emblem")
        - "Card Name (collector#) // Other Double-Sided Token"
        - "Double-Faced Helper Card - N/M" (no inventory equivalent)
        - "Magic Minigame: ..." (no inventory equivalent)

        Matching strategy: for each inventory card, build normalized echo name
        candidates and look them up by set code + collector number.
        """
        items = self.categories.get(cat, [])
        matched = 0
        no_match = 0
        no_match_items = []

        for m in items:
            inv_card: InventoryCard = m["inv_card"]
            inv_name = inv_card.name
            set_code = inv_card.set_code
            collector_num = inv_card.collector_num

            found = False

            # Build candidate echo names to search for
            echo_name_candidates = set()

            # Check if emblem: "Card Name Emblem" -> "emblem - card name"
            emblem_match = re.match(r"^(.+?)\s+Emblem$", inv_name, re.IGNORECASE)
            if emblem_match:
                base = emblem_match.group(1).strip().lower()
                echo_name_candidates.add(f"emblem - {base}")
            else:
                base = inv_name.lower()
                # Token patterns:
                # "Name" -> "name token", "name (collector#) token"
                echo_name_candidates.add(f"{base} token")
                echo_name_candidates.add(f"{base} ({collector_num.zfill(3)}) token")
                echo_name_candidates.add(f"{base} (0{collector_num.zfill(3)}) token")
                # DFC token: "name (collector#) // other double-sided token"
                # Also try just matching any echo name that starts with base

            # Try each candidate against echo data
            for echo_candidate in echo_name_candidates:
                echo_key = (echo_candidate, set_code, collector_num)
                entries = self.echo_rows.get(echo_key, [])
                if entries:
                    echo_inv_id = entries[0].get("echo_inventory_id", "")
                    if echo_inv_id:
                        inv_card.echo_matched_id = echo_inv_id
                        inv_card.row_data["echo_matched_id"] = echo_inv_id
                        matched += 1
                        found = True
                        break

            if found:
                continue

            # Broader search: scan all echo names in this set for matches
            # Match by collector# first, then check if names are related
            for echo_name_lower in self.echo_names.get(set_code, set()):
                # Skip helper/minigame cards
                if "helper card" in echo_name_lower or "magic minigame" in echo_name_lower:
                    continue

                # Normalize echo name to match inventory naming
                # Order matters: collector# parens can appear after "token",
                # so strip them first, then suffixes.
                cleaned = echo_name_lower
                # Remove " // other" part (DFC tokens)
                cleaned = re.sub(r"\s*//.*$", "", cleaned)
                # Remove collector# parenthetical like (008) or (0008)
                cleaned = re.sub(r"\s*\(0*\d+\)", "", cleaned)
                # Remove double-sided suffix (before generic token)
                cleaned = re.sub(r"\s+double-sided token$", "", cleaned)
                # Remove " token" suffix
                cleaned = re.sub(r"\s+token$", "", cleaned)
                cleaned = cleaned.strip()

                # Convert "emblem - name" to "name emblem"
                em = re.match(r"^emblem\s*-\s*(.+)$", cleaned)
                if em:
                    cleaned = f"{em.group(1).strip()} emblem"

                inv_lower = inv_name.lower()
                # Also handle DFC inventory names: "Day // Night" -> "day"
                inv_front = inv_lower.split("//")[0].strip() if "//" in inv_lower else inv_lower

                if cleaned == inv_lower or cleaned == inv_front:
                    # Name matches - now check collector#
                    ek = (echo_name_lower, set_code, collector_num)
                    entries = self.echo_rows.get(ek, [])
                    if entries:
                        echo_inv_id = entries[0].get("echo_inventory_id", "")
                        if echo_inv_id:
                            inv_card.echo_matched_id = echo_inv_id
                            inv_card.row_data["echo_matched_id"] = echo_inv_id
                            matched += 1
                            found = True
                            break

                    # Try any collector# for this echo name in same set
                    for cn in self.echo_by_name_set.get((echo_name_lower, set_code), []):
                        ek2 = (echo_name_lower, set_code, cn)
                        entries2 = self.echo_rows.get(ek2, [])
                        if entries2:
                            echo_inv_id = entries2[0].get("echo_inventory_id", "")
                            if echo_inv_id:
                                inv_card.echo_matched_id = echo_inv_id
                                inv_card.row_data["echo_matched_id"] = echo_inv_id
                                matched += 1
                                found = True
                                break
                    if found:
                        break

            if not found:
                no_match += 1
                no_match_items.append(m)

        self.matched_count += matched
        self.actions[cat] = f"AUTO-MATCH TOKEN ({matched} matched, {no_match} unmatched)"
        print(f"Token auto-match: {matched} matched, {no_match} unmatched.")

        if no_match_items:
            print(f"\nUnmatched tokens ({no_match}):")
            for m in no_match_items[:20]:
                print(f"  {m['name'][:50]:<50} {m['set_code'].upper():<6} #{m['collector_num']}")
            if len(no_match_items) > 20:
                print(f"  ... and {len(no_match_items) - 20} more")

    def apply_auto_match_dfc_by_collector(self, cat: str = "dual_faced_front_in_echo"):
        """Auto-match DFC cards where front face name + set + collector# all match.

        Cards where the collector# differs are moved to the 'dfc_diff_collector'
        category for manual investigation.
        """
        items = self.categories.get(cat, [])
        matched = 0
        deferred = []

        for m in items:
            inv_card: InventoryCard = m["inv_card"]
            front_face = m.get("front_face", "")
            if not front_face:
                deferred.append(m)
                continue

            # Only match when front face name + set + collector# all agree
            echo_key = (front_face, inv_card.set_code, inv_card.collector_num)
            echo_entries = self.echo_rows.get(echo_key, [])

            if echo_entries:
                echo_inv_id = echo_entries[0].get("echo_inventory_id", "")
                if echo_inv_id:
                    inv_card.echo_matched_id = echo_inv_id
                    inv_card.row_data["echo_matched_id"] = echo_inv_id
                    matched += 1
                else:
                    deferred.append(m)
            else:
                deferred.append(m)

        # Move non-exact matches to dfc_diff_collector for investigation
        if deferred:
            self.categories["dfc_diff_collector"] = deferred

        self.matched_count += matched
        self.actions[cat] = f"AUTO-MATCH DFC ({matched} matched, {len(deferred)} deferred)"
        print(f"DFC auto-match: {matched} matched, {len(deferred)} deferred to 'dfc_diff_collector'.")

    def apply_auto_match_by_name_set(self, cat: str):
        """Auto-match cards where name+set match but collector# differs.

        Pairs inventory cards with echo entries that share the same name and set.
        If echo has collectors for this name+set, match them 1:1 in order.
        """
        items = self.categories.get(cat, [])
        matched = 0
        no_match = 0

        # Group by (name, set) to handle multiple cards with same name
        by_name_set = defaultdict(list)
        for m in items:
            key = (m["name"].lower(), m["set_code"])
            by_name_set[key].append(m)

        for (name_lower, set_code), group in by_name_set.items():
            # Find echo entries for this name+set
            echo_collectors = self.echo_by_name_set.get((name_lower, set_code), [])
            # Get actual echo rows
            available_echo = []
            for cn in echo_collectors:
                ek = (name_lower, set_code, cn)
                for row in self.echo_rows.get(ek, []):
                    eid = row.get("echo_inventory_id", "")
                    if eid:
                        available_echo.append(row)

            # Match 1:1
            for i, m in enumerate(group):
                if i < len(available_echo):
                    echo_inv_id = available_echo[i].get("echo_inventory_id", "")
                    inv_card: InventoryCard = m["inv_card"]
                    inv_card.echo_matched_id = echo_inv_id
                    inv_card.row_data["echo_matched_id"] = echo_inv_id
                    matched += 1
                else:
                    no_match += 1

        self.matched_count += matched
        self.actions[cat] = f"AUTO-MATCH NAME+SET ({matched} matched, {no_match} unmatched)"
        print(f"Name+Set auto-match for '{cat}': {matched} matched, {no_match} unmatched.")

    def apply_auto_match_partial_name(self, cat: str = "partial_name_match"):
        """Auto-match cards where name is a partial match (substring).

        For each card, find the echo entry that contains or is contained by
        the inventory name, in the same set, and match by collector#.
        """
        items = self.categories.get(cat, [])
        matched = 0
        no_match = 0

        for m in items:
            inv_card: InventoryCard = m["inv_card"]
            echo_partial = m.get("echo_partial", "")
            if not echo_partial:
                no_match += 1
                continue

            # Try matching by echo_partial name + same set + same collector#
            echo_key = (echo_partial, inv_card.set_code, inv_card.collector_num)
            echo_entries = self.echo_rows.get(echo_key, [])

            if echo_entries:
                echo_inv_id = echo_entries[0].get("echo_inventory_id", "")
                if echo_inv_id:
                    inv_card.echo_matched_id = echo_inv_id
                    inv_card.row_data["echo_matched_id"] = echo_inv_id
                    matched += 1
                    continue

            # Try any collector# for echo partial name
            echo_collectors = self.echo_by_name_set.get(
                (echo_partial, inv_card.set_code), []
            )
            found = False
            for cn in echo_collectors:
                ek = (echo_partial, inv_card.set_code, cn)
                entries = self.echo_rows.get(ek, [])
                if entries:
                    echo_inv_id = entries[0].get("echo_inventory_id", "")
                    if echo_inv_id:
                        inv_card.echo_matched_id = echo_inv_id
                        inv_card.row_data["echo_matched_id"] = echo_inv_id
                        matched += 1
                        found = True
                        break
            if not found:
                no_match += 1

        self.matched_count += matched
        self.actions[cat] = f"AUTO-MATCH PARTIAL ({matched} matched, {no_match} unmatched)"
        print(f"Partial name auto-match: {matched} matched, {no_match} unmatched.")

    def apply_auto_match_special_chars(self, cat: str = "special_chars"):
        """Auto-match cards with special characters by normalizing to ASCII.

        Tries multiple strategies:
        1. Exact ASCII match on name + collector#
        2. ASCII match on basename (strip parentheticals) + collector#
        3. ASCII substring match (echo name contains inventory name or vice versa)
        """
        items = self.categories.get(cat, [])
        matched = 0
        no_match = 0

        import unicodedata

        def to_ascii(s):
            return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()

        def strip_parens(s):
            return re.sub(r"\s*\([^)]*\)\s*$", "", s).strip()

        for m in items:
            inv_card: InventoryCard = m["inv_card"]
            ascii_name = to_ascii(inv_card.name.lower())
            found = False

            for echo_name_lower in self.echo_names.get(inv_card.set_code, set()):
                echo_ascii = to_ascii(echo_name_lower)
                echo_base_ascii = to_ascii(strip_parens(echo_name_lower).lower())

                # Strategy 1: exact ASCII match
                # Strategy 2: basename ASCII match (echo may have parenthetical)
                if echo_ascii == ascii_name or echo_base_ascii == ascii_name:
                    ek = (echo_name_lower, inv_card.set_code, inv_card.collector_num)
                    entries = self.echo_rows.get(ek, [])
                    if entries:
                        echo_inv_id = entries[0].get("echo_inventory_id", "")
                        if echo_inv_id:
                            inv_card.echo_matched_id = echo_inv_id
                            inv_card.row_data["echo_matched_id"] = echo_inv_id
                            matched += 1
                            found = True
                            break
                    # Try any collector# for this echo name
                    for cn in self.echo_by_name_set.get((echo_name_lower, inv_card.set_code), []):
                        ek2 = (echo_name_lower, inv_card.set_code, cn)
                        entries2 = self.echo_rows.get(ek2, [])
                        if entries2:
                            echo_inv_id = entries2[0].get("echo_inventory_id", "")
                            if echo_inv_id:
                                inv_card.echo_matched_id = echo_inv_id
                                inv_card.row_data["echo_matched_id"] = echo_inv_id
                                matched += 1
                                found = True
                                break
                    if found:
                        break

            if not found:
                no_match += 1

        self.matched_count += matched
        self.actions[cat] = f"AUTO-MATCH CHARS ({matched} matched, {no_match} unmatched)"
        print(f"Special chars auto-match: {matched} matched, {no_match} unmatched.")

    def apply_generate_upload(self, cat: str):
        """Mark cards for upload to echomtg."""
        items = self.categories.get(cat, [])
        for m in items:
            self.to_upload.append({
                "Name": m["name"],
                "Set Code": m["set_code"].upper(),
                "Collector Number": m["collector_num"],
                "Reg Qty": int(m["reg_qty"]),
                "Foil Qty": int(m["foil_qty"]),
                "note": m["note"],
            })
        self.upload_count += len(items)
        self.actions[cat] = f"UPLOAD ({len(items)})"
        print(f"Marked {len(items)} cards in '{cat}' for upload.")

    # -- Save --

    def save_inventory(self):
        """Save inventory back to CSV with updated echo_matched_id."""
        backup_file = f"{self.INVENTORY_FILE}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        temp_file = self.INVENTORY_FILE + ".tmp"

        with open(temp_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self.inventory_fieldnames)
            writer.writeheader()
            for card in self.inventory_rows:
                writer.writerow(card.row_data)

        if os.path.exists(self.INVENTORY_FILE):
            os.rename(self.INVENTORY_FILE, backup_file)
        os.rename(temp_file, self.INVENTORY_FILE)
        print(f"Saved inventory. Backup: {backup_file}")

    def save_upload_csv(self):
        """Save cards to upload to echomtg."""
        if not self.to_upload:
            print("No cards to upload.")
            return

        fieldnames = ["Name", "Set Code", "Collector Number", "Reg Qty", "Foil Qty", "note"]
        with open(self.UPLOAD_FILE, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in self.to_upload:
                writer.writerow(row)
        print(f"Saved {len(self.to_upload)} cards to {self.UPLOAD_FILE}")

    # -- Verification --

    def verify(self):
        """Verify totals after all categories processed."""
        total_missing = len(self.missing)
        total_actioned = self.matched_count + self.skipped_count + self.upload_count

        print()
        print("=" * 80)
        print("  VERIFICATION")
        print("=" * 80)
        print(f"  Total missing from echomtg:  {total_missing}")
        print(f"  Matched (echo_matched_id):   {self.matched_count}")
        print(f"  Skipped:                     {self.skipped_count}")
        print(f"  To upload:                   {self.upload_count}")
        print(f"  Total actioned:              {total_actioned}")
        print(f"  Unactioned:                  {total_missing - total_actioned}")
        print()

        # Check for unprocessed categories
        unprocessed = []
        for cat in self.CATEGORY_ORDER:
            if cat not in self.actions and self.categories.get(cat):
                unprocessed.append(cat)
        if unprocessed:
            print(f"  WARNING: Unprocessed categories: {', '.join(unprocessed)}")
        else:
            print("  All categories processed!")
        print()

    # -- Card-by-card investigation --

    def investigate_category(self, cat: str):
        """Interactively investigate cards in a category one by one.

        For each card, shows details and echo candidates, then lets the user:
        - [m]atch <#> to match to an echo candidate
        - [s]kip to skip this card
        - [u]pload to mark for upload
        - [n]ext / [p]rev to navigate
        - [d]one to finish and return to main prompt
        """
        items = self.categories.get(cat, [])
        if not items:
            print(f"No cards in category '{cat}'.")
            return

        idx = 0
        local_matched = 0
        local_skipped = 0
        local_uploaded = 0

        while True:
            m = items[idx]
            inv_card: InventoryCard = m["inv_card"]
            already_matched = bool(inv_card.echo_matched_id)

            print()
            print("-" * 80)
            status = "MATCHED" if already_matched else "PENDING"
            print(f"  [{cat}] Card {idx + 1} of {len(items)}  [{status}]")
            print("-" * 80)
            print(f"  Inventory: {m['name']}")
            print(f"  Set:       {m['set_code'].upper()}  Collector#: {m['collector_num']}")
            qty_str = f"{int(m['reg_qty'])}R / {int(m['foil_qty'])}F"
            print(f"  Qty:       {qty_str}")
            print(f"  Note:      {m['note'] or '(none)'}")
            if already_matched:
                print(f"  >>> Already matched to echo_inventory_id: {inv_card.echo_matched_id}")

            # Show echo candidates
            front_face = m.get("front_face", m["name"].split("//")[0].strip().lower() if "//" in m["name"] else m["name"].lower())
            echo_candidates = self._find_echo_candidates(front_face, m["name"].lower(), m["set_code"])

            if echo_candidates:
                print(f"\n  Echo candidates ({len(echo_candidates)}):")
                for ci, (echo_name, echo_sc, echo_cn, echo_inv_id, echo_eid) in enumerate(echo_candidates):
                    marker = " <-- same collector#" if echo_cn == m["collector_num"] else ""
                    print(f"    [{ci + 1}] {echo_name}  {echo_sc.upper()} #{echo_cn}  inv_id={echo_inv_id}{marker}")
            else:
                print("\n  No echo candidates found.")

            print()
            print("  [m]atch <#>  [s]kip  [u]pload  [n]ext  [p]rev  [d]one")

            subcmd = input(f"  {cat}[{idx+1}]> ").strip()
            if not subcmd:
                continue

            sparts = subcmd.split()
            saction = sparts[0].lower()

            if saction in ("n", "next", ""):
                if idx < len(items) - 1:
                    idx += 1
                else:
                    print("  Last card. Use [d]one to finish.")

            elif saction in ("p", "prev"):
                if idx > 0:
                    idx -= 1
                else:
                    print("  First card.")

            elif saction in ("m", "match"):
                if not echo_candidates:
                    print("  No candidates to match.")
                    continue
                try:
                    match_num = int(sparts[1]) if len(sparts) > 1 else int(input("  Match candidate #: "))
                    if 1 <= match_num <= len(echo_candidates):
                        _, _, _, echo_inv_id, _ = echo_candidates[match_num - 1]
                        inv_card.echo_matched_id = echo_inv_id
                        inv_card.row_data["echo_matched_id"] = echo_inv_id
                        local_matched += 1
                        self.matched_count += 1
                        print(f"  Matched -> echo_inventory_id {echo_inv_id}")
                        # Auto-advance
                        if idx < len(items) - 1:
                            idx += 1
                    else:
                        print(f"  Invalid. Must be 1-{len(echo_candidates)}")
                except ValueError:
                    print("  Invalid number.")

            elif saction in ("s", "skip"):
                local_skipped += 1
                self.skipped_count += 1
                print("  Skipped.")
                if idx < len(items) - 1:
                    idx += 1

            elif saction in ("u", "upload"):
                self.to_upload.append({
                    "Name": m["name"],
                    "Set Code": m["set_code"].upper(),
                    "Collector Number": m["collector_num"],
                    "Reg Qty": int(m["reg_qty"]),
                    "Foil Qty": int(m["foil_qty"]),
                    "note": m["note"],
                })
                local_uploaded += 1
                self.upload_count += 1
                print("  Marked for upload.")
                if idx < len(items) - 1:
                    idx += 1

            elif saction in ("d", "done"):
                break

            elif saction in ("g", "go"):
                try:
                    num = int(sparts[1]) if len(sparts) > 1 else int(input("  Go to #: "))
                    if 1 <= num <= len(items):
                        idx = num - 1
                    else:
                        print(f"  Must be 1-{len(items)}")
                except ValueError:
                    print("  Invalid number.")

            else:
                print(f"  Unknown: {saction}")

        self.actions[cat] = f"INVESTIGATED ({local_matched} matched, {local_skipped} skipped, {local_uploaded} upload)"
        print(f"\n  Done investigating '{cat}': {local_matched} matched, {local_skipped} skipped, {local_uploaded} upload.")

    def _find_echo_candidates(
        self, front_face: str, full_name: str, set_code: str
    ) -> List[Tuple[str, str, str, str, str]]:
        """Find echo candidates for a card.

        Returns list of (echo_name, set_code, collector_num, echo_inventory_id, echo_id).
        """
        candidates = []
        seen = set()

        # Search by front face name in same set
        for cn in self.echo_by_name_set.get((front_face, set_code), []):
            key = (front_face, set_code, cn)
            for row in self.echo_rows.get(key, []):
                eid = row.get("echo_inventory_id", "")
                if eid and eid not in seen:
                    seen.add(eid)
                    candidates.append((
                        row["Name"].strip(), set_code, cn, eid,
                        row.get("echoid", ""),
                    ))

        # Also search by full name (for non-DFC categories)
        if full_name != front_face:
            for cn in self.echo_by_name_set.get((full_name, set_code), []):
                key = (full_name, set_code, cn)
                for row in self.echo_rows.get(key, []):
                    eid = row.get("echo_inventory_id", "")
                    if eid and eid not in seen:
                        seen.add(eid)
                        candidates.append((
                            row["Name"].strip(), set_code, cn, eid,
                            row.get("echoid", ""),
                        ))

        # Search by basename (strip parentheticals) in same set
        base_name = re.sub(r"\s*\([^)]*\)\s*$", "", front_face).strip()
        if base_name != front_face:
            for cn in self.echo_by_basename_set.get((base_name, set_code), []):
                key_candidates = [
                    (en, set_code, cn)
                    for en in self.echo_names.get(set_code, set())
                    if re.sub(r"\s*\([^)]*\)\s*$", "", en).strip() == base_name
                ]
                for kc in key_candidates:
                    for row in self.echo_rows.get(kc, []):
                        eid = row.get("echo_inventory_id", "")
                        if eid and eid not in seen:
                            seen.add(eid)
                            candidates.append((
                                row["Name"].strip(), set_code, cn, eid,
                                row.get("echoid", ""),
                            ))

        return candidates

    # -- Interactive loop --

    def run_interactive(self):
        """Run the interactive investigation loop."""
        print()
        print("=" * 80)
        print("  PHASE 2: INVESTIGATING MISSING INVENTORY CARDS")
        print("=" * 80)
        print()
        print("Commands:")
        print("  show <category>       - Show examples from a category")
        print("  show <category> <N>   - Show N examples")
        print("  sets <category>       - Show set breakdown for a category")
        print("  summary               - Show category summary")
        print("  next                  - Show next unprocessed category")
        print()
        print("Actions (apply to a category):")
        print("  skip <category>       - Skip category (not in echomtg)")
        print("  match-dfc             - Auto-match DFCs by front face + collector#")
        print("  match-token           - Auto-match token/emblem cards by name normalization")
        print("  match-art             - Auto-match art series cards")
        print("  match-name <cat>      - Auto-match by name+set (diff collector#)")
        print("  match-partial         - Auto-match partial name matches")
        print("  match-chars           - Auto-match special character variants")
        print("  upload <category>     - Mark category for upload to echomtg")
        print("  investigate <cat>     - Review cards in category one by one")
        print()
        print("Save/verify:")
        print("  save                  - Save inventory + upload CSV")
        print("  verify                - Check totals")
        print("  quit                  - Exit (prompts to save)")
        print()

        while True:
            cmd = input("phase2> ").strip()
            if not cmd:
                continue

            parts = cmd.split()
            action = parts[0].lower()

            try:
                if action == "show":
                    cat = parts[1] if len(parts) > 1 else self._next_unprocessed()
                    n = int(parts[2]) if len(parts) > 2 else 15
                    if cat:
                        self.show_category(cat, n)

                elif action == "sets":
                    cat = parts[1] if len(parts) > 1 else self._next_unprocessed()
                    if cat:
                        self.show_category_sets(cat)

                elif action == "summary":
                    self._print_category_summary()

                elif action == "next":
                    cat = self._next_unprocessed()
                    if cat:
                        self.show_category(cat)
                    else:
                        print("All categories processed!")

                elif action == "skip":
                    cat = parts[1] if len(parts) > 1 else None
                    if cat:
                        self.apply_skip(cat)
                    else:
                        print("Usage: skip <category>")

                elif action == "match-dfc":
                    self.apply_auto_match_dfc_by_collector()

                elif action == "match-token":
                    self.apply_auto_match_token_set()

                elif action == "match-art":
                    self.apply_auto_match_art_series()

                elif action == "match-name":
                    cat = parts[1] if len(parts) > 1 else None
                    if cat:
                        self.apply_auto_match_by_name_set(cat)
                    else:
                        print("Usage: match-name <category>")

                elif action == "match-partial":
                    self.apply_auto_match_partial_name()

                elif action == "match-chars":
                    self.apply_auto_match_special_chars()

                elif action == "upload":
                    cat = parts[1] if len(parts) > 1 else None
                    if cat:
                        self.apply_generate_upload(cat)
                    else:
                        print("Usage: upload <category>")

                elif action in ("investigate", "inv"):
                    cat = parts[1] if len(parts) > 1 else self._next_unprocessed()
                    if cat:
                        self.investigate_category(cat)
                    else:
                        print("All categories processed!")

                elif action == "save":
                    self.save_inventory()
                    self.save_upload_csv()

                elif action == "verify":
                    self.verify()

                elif action in ("quit", "q", "exit"):
                    if self.matched_count > 0 or self.upload_count > 0:
                        resp = input("Save changes before quitting? [y/n]: ").strip().lower()
                        if resp == "y":
                            self.save_inventory()
                            self.save_upload_csv()
                    print("Goodbye!")
                    break

                else:
                    print(f"Unknown command: {action}")

            except IndexError:
                print("Missing argument. Type a command for usage info.")
            except Exception as e:
                print(f"Error: {e}")
                import traceback
                traceback.print_exc()

    def _next_unprocessed(self) -> Optional[str]:
        """Return the next unprocessed category name."""
        for cat in self.CATEGORY_ORDER:
            if cat not in self.actions and self.categories.get(cat):
                return cat
        return None


def main():
    investigator = Phase2Investigator()
    investigator.run_interactive()


if __name__ == "__main__":
    main()
