#!/usr/bin/env python3
"""
Phase 1 Investigation Interface

For each mismatched card in echomtg, shows:
1. The echomtg card details
2. Potential inventory matches
3. Whether each inventory match is already in echomtg

Tracks progress by updating inventory CSV with matched echo_inventory_ids.
"""

from __future__ import annotations

import csv
import re
import os
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional, List, Dict
from datetime import datetime


@dataclass
class EchoCard:
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
    name: str
    set_code: str
    collector_num: str
    note: str
    reg_qty: float
    foil_qty: float
    echo_matched_id: str = ""  # Track which echo card this was matched to
    row_data: Dict = field(default_factory=dict)  # Full row for saving


@dataclass
class PotentialMatch:
    inv_card: InventoryCard
    already_in_echo: bool
    echo_inventory_ids: List[str]  # If already in echo, which inventory IDs


class InvestigationTracker:
    def __init__(self):
        self.inventory_file = 'inventory_with_locations_compact_fixed.csv'
        self.echo_file = 'echomtg-export-2ManyCards-01-26-2026.csv'
        self.fix_file = 'phase1_cards_to_fix.csv'

        self.inventory = {}  # (name.lower(), set_code, collector_num) -> InventoryCard
        self.inventory_by_name_set = defaultdict(list)
        self.inventory_rows = []  # All rows for saving
        self.inventory_fieldnames = []

        self.echo_by_key = defaultdict(list)
        self.cards_to_fix = []
        self.all_matches = []

        # Track which echo cards have been processed
        self.processed_echo_ids = set()

        self.load_data()

    def load_data(self):
        """Load all data sources."""
        print("Loading inventory...")
        self._load_inventory()
        print("Loading echomtg export...")
        self._load_echo()
        print("Loading cards to fix...")
        self._load_cards_to_fix()
        print("Computing matches...")
        self._compute_matches()
        print(f"Loaded {len(self.cards_to_fix)} cards to investigate.")

        # Count already processed
        processed = sum(1 for m in self.all_matches if self._is_processed(m))
        if processed > 0:
            print(f"  {processed} cards already processed (have matched inventory).")

    def _load_inventory(self):
        """Load inventory CSV."""
        with open(self.inventory_file, 'r') as f:
            reader = csv.DictReader(f)
            self.inventory_fieldnames = list(reader.fieldnames)

            # Add echo_matched_id column if not present
            if 'echo_matched_id' not in self.inventory_fieldnames:
                self.inventory_fieldnames.append('echo_matched_id')

            for row in reader:
                set_code = row['Set Code'].strip().lower()
                collector_num = row['Collector Number'].strip().lstrip('0') or '0'
                name = row['Name'].strip()

                # Ensure echo_matched_id exists
                if 'echo_matched_id' not in row:
                    row['echo_matched_id'] = ''

                card = InventoryCard(
                    name=name,
                    set_code=set_code,
                    collector_num=collector_num,
                    note=row.get('note', ''),
                    reg_qty=float(row['Reg Qty'] or 0),
                    foil_qty=float(row['Foil Qty'] or 0),
                    echo_matched_id=row.get('echo_matched_id', ''),
                    row_data=row,
                )

                key = (name.lower(), set_code, collector_num)
                self.inventory[key] = card
                self.inventory_rows.append(card)

                # Index by name and set for fuzzy matching
                self.inventory_by_name_set[(name.lower(), set_code)].append(card)

                # Also index by base name (remove parentheticals)
                base_name = re.sub(r'\s*\([^)]*\)\s*$', '', name).strip().lower()
                if base_name != name.lower():
                    self.inventory_by_name_set[(base_name, set_code)].append(card)

    def _load_echo(self):
        """Load echomtg export."""
        with open(self.echo_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                set_code = row['Set Code'].strip().lower()
                collector_num = row['Collector Number'].strip().lstrip('0') or '0'
                name = row['Name'].strip()

                card = EchoCard(
                    name=name,
                    set_name=row['Set'],
                    set_code=set_code,
                    collector_num=collector_num,
                    inventory_id=row['echo_inventory_id'],
                    echo_id=row['echoid'],
                    reg_qty=row['Reg Qty'],
                    foil_qty=row['Foil Qty'],
                )

                key = (name.lower(), set_code, collector_num)
                self.echo_by_key[key].append(card)

    def _load_cards_to_fix(self):
        """Load the cards to fix list."""
        with open(self.fix_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                card = EchoCard(
                    name=row['echo_name'],
                    set_name=row['echo_set'],
                    set_code=row['echo_set_code'],
                    collector_num=row['echo_collector'],
                    inventory_id=row['echo_inventory_id'],
                    echo_id=row['echo_id'],
                    reg_qty=row['echo_reg_qty'],
                    foil_qty=row['echo_foil_qty'],
                )
                self.cards_to_fix.append(card)

    def _compute_matches(self):
        """Compute potential matches for all cards."""
        for card in self.cards_to_fix:
            matches = self._find_potential_matches(card)
            self.all_matches.append(matches)

    def _find_potential_matches(self, echo_card: EchoCard) -> List[PotentialMatch]:
        """Find potential inventory matches for an echomtg card."""
        matches = []

        # Try exact name match
        name_key = (echo_card.name.lower(), echo_card.set_code)
        inv_cards = list(self.inventory_by_name_set.get(name_key, []))

        # Also try base name (remove parentheticals from echo name)
        base_name = re.sub(r'\s*\([^)]*\)\s*$', '', echo_card.name).strip().lower()
        if base_name != echo_card.name.lower():
            inv_cards = inv_cards + list(self.inventory_by_name_set.get((base_name, echo_card.set_code), []))

        # Deduplicate
        seen = set()
        unique_inv_cards = []
        for c in inv_cards:
            key = (c.name, c.set_code, c.collector_num)
            if key not in seen:
                seen.add(key)
                unique_inv_cards.append(c)

        for inv_card in unique_inv_cards:
            echo_key = (inv_card.name.lower(), inv_card.set_code, inv_card.collector_num)
            echo_matches = list(self.echo_by_key.get(echo_key, []))

            # Also check with base name variations
            if not echo_matches:
                for echo_name_key, echo_cards in self.echo_by_key.items():
                    if echo_name_key[1] == inv_card.set_code and echo_name_key[2] == inv_card.collector_num:
                        echo_base = re.sub(r'\s*\([^)]*\)\s*$', '', echo_name_key[0]).strip().lower()
                        if echo_base == inv_card.name.lower() or echo_name_key[0] == inv_card.name.lower():
                            echo_matches.extend(echo_cards)

            already_in_echo = len(echo_matches) > 0
            echo_inv_ids = [e.inventory_id for e in echo_matches]

            matches.append(PotentialMatch(
                inv_card=inv_card,
                already_in_echo=already_in_echo,
                echo_inventory_ids=echo_inv_ids,
            ))

        return matches

    def _is_processed(self, matches: List[PotentialMatch]) -> bool:
        """Check if any match has been processed (has echo_matched_id)."""
        return any(m.inv_card.echo_matched_id for m in matches)

    def _get_status(self, index: int) -> str:
        """Get status string for a card."""
        matches = self.all_matches[index]

        # Check if already processed
        for m in matches:
            if m.inv_card.echo_matched_id:
                return f"[MATCHED -> inv {m.inv_card.collector_num}]"

        if not matches:
            return "[NO MATCHES]"

        all_in_echo = all(m.already_in_echo for m in matches)
        if all_in_echo:
            return "[ALL MATCHES ALREADY IN ECHO]"

        return "[HAS AVAILABLE MATCH]"

    def save_inventory(self):
        """Save inventory back to CSV with updated echo_matched_id."""
        # Create backup first
        backup_file = f"{self.inventory_file}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Write to temp file first
        temp_file = self.inventory_file + '.tmp'
        with open(temp_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.inventory_fieldnames)
            writer.writeheader()
            for card in self.inventory_rows:
                writer.writerow(card.row_data)

        # Backup original and replace
        if os.path.exists(self.inventory_file):
            os.rename(self.inventory_file, backup_file)
        os.rename(temp_file, self.inventory_file)

        print(f"Saved inventory. Backup: {backup_file}")

    def mark_match(self, echo_card: EchoCard, inv_card: InventoryCard):
        """Mark an inventory card as matched to an echo card."""
        inv_card.echo_matched_id = echo_card.inventory_id
        inv_card.row_data['echo_matched_id'] = echo_card.inventory_id
        print(f"Marked: {inv_card.name} ({inv_card.set_code} #{inv_card.collector_num}) -> echo_inventory_id {echo_card.inventory_id}")

    def unmark_match(self, inv_card: InventoryCard):
        """Remove match marking from an inventory card."""
        old_id = inv_card.echo_matched_id
        inv_card.echo_matched_id = ''
        inv_card.row_data['echo_matched_id'] = ''
        print(f"Unmarked: {inv_card.name} ({inv_card.set_code} #{inv_card.collector_num}) (was {old_id})")

    def display_card(self, index: int):
        """Display a card and its potential matches."""
        echo_card = self.cards_to_fix[index]
        matches = self.all_matches[index]

        print("\n" + "=" * 80)
        print(f"  CARD {index + 1} of {len(self.cards_to_fix)}  {self._get_status(index)}")
        print("=" * 80)

        print(f"\n  ECHOMTG CARD (needs fixing):")
        print(f"    Name:         {echo_card.name}")
        print(f"    Set:          {echo_card.set_name} ({echo_card.set_code.upper()})")
        print(f"    Collector #:  {echo_card.collector_num}")
        print(f"    Qty:          {echo_card.reg_qty} reg / {echo_card.foil_qty} foil")
        print(f"    Inventory ID: {echo_card.inventory_id}")
        print(f"    Echo ID:      {echo_card.echo_id}")

        print(f"\n  POTENTIAL INVENTORY MATCHES:")
        print("-" * 80)

        if not matches:
            print("    No potential matches found in inventory.")
        else:
            for i, match in enumerate(matches):
                inv = match.inv_card
                flags = []

                if inv.echo_matched_id:
                    if inv.echo_matched_id == echo_card.inventory_id:
                        flags.append("*** MATCHED TO THIS CARD ***")
                    else:
                        flags.append(f"MATCHED TO DIFFERENT ECHO: {inv.echo_matched_id}")

                if match.already_in_echo:
                    flags.append(f"ALREADY IN ECHO: {', '.join(match.echo_inventory_ids)}")
                elif inv.collector_num == echo_card.collector_num:
                    flags.append("SAME COLLECTOR #")

                print(f"    [{i + 1}] {inv.name}")
                print(f"        Set: {inv.set_code.upper()} | Collector #: {inv.collector_num}")
                print(f"        Qty: {inv.reg_qty} reg / {inv.foil_qty} foil")
                print(f"        Note: {inv.note or '(none)'}")
                if flags:
                    for flag in flags:
                        print(f"        >>> {flag}")
                print()

        print("-" * 80)

    def display_summary(self, show_all=False):
        """Display summary of all cards."""
        print("\n" + "=" * 80)
        print("  SUMMARY OF ALL CARDS")
        print("=" * 80)

        matched = 0
        pending = 0

        for i, (card, matches) in enumerate(zip(self.cards_to_fix, self.all_matches)):
            status = self._get_status(i)

            if "[MATCHED" in status:
                matched += 1
                if not show_all:
                    continue
            else:
                pending += 1

            print(f"  {i + 1:3}. {card.name[:40]:<40} {card.set_code.upper()} #{card.collector_num:<6} {status}")

        print()
        print(f"  Total: {len(self.cards_to_fix)} | Matched: {matched} | Pending: {pending}")
        print()

    def run(self):
        """Run the interactive interface."""
        current_index = 0

        # Find first unprocessed card
        for i, matches in enumerate(self.all_matches):
            if not self._is_processed(matches):
                current_index = i
                break

        while True:
            self.display_card(current_index)

            print("\nCommands:")
            print("  [n]ext  [p]rev  [g]o to #  [q]uit")
            print("  [s]ummary (pending only)  [S]ummary (all)")
            print("  [m]atch <#> - mark inventory match  [u]nmatch <#> - remove match")
            print("  [w]rite - save progress to file")
            print("  [j]ump to next unmatched")

            cmd = input("\n> ").strip()

            if cmd.lower() == 'n' or cmd == '':
                if current_index < len(self.cards_to_fix) - 1:
                    current_index += 1
                else:
                    print("Already at last card.")

            elif cmd.lower() == 'p':
                if current_index > 0:
                    current_index -= 1
                else:
                    print("Already at first card.")

            elif cmd.lower().startswith('g'):
                try:
                    parts = cmd.split()
                    if len(parts) > 1:
                        num = int(parts[1])
                    else:
                        num = int(input("Go to card #: "))
                    if 1 <= num <= len(self.cards_to_fix):
                        current_index = num - 1
                    else:
                        print(f"Invalid card number. Must be 1-{len(self.cards_to_fix)}")
                except ValueError:
                    print("Invalid number.")

            elif cmd == 's':
                self.display_summary(show_all=False)

            elif cmd == 'S':
                self.display_summary(show_all=True)

            elif cmd.lower().startswith('m'):
                try:
                    parts = cmd.split()
                    if len(parts) > 1:
                        match_num = int(parts[1])
                    else:
                        match_num = int(input("Match inventory #: "))

                    matches = self.all_matches[current_index]
                    if 1 <= match_num <= len(matches):
                        self.mark_match(self.cards_to_fix[current_index], matches[match_num - 1].inv_card)
                    else:
                        print(f"Invalid match number. Must be 1-{len(matches)}")
                except ValueError:
                    print("Invalid number.")

            elif cmd.lower().startswith('u'):
                try:
                    parts = cmd.split()
                    if len(parts) > 1:
                        match_num = int(parts[1])
                    else:
                        match_num = int(input("Unmatch inventory #: "))

                    matches = self.all_matches[current_index]
                    if 1 <= match_num <= len(matches):
                        self.unmark_match(matches[match_num - 1].inv_card)
                    else:
                        print(f"Invalid match number. Must be 1-{len(matches)}")
                except ValueError:
                    print("Invalid number.")

            elif cmd.lower() == 'w':
                self.save_inventory()

            elif cmd.lower() == 'j':
                found = False
                for i in range(current_index + 1, len(self.all_matches)):
                    if not self._is_processed(self.all_matches[i]):
                        current_index = i
                        found = True
                        break
                if not found:
                    # Wrap around
                    for i in range(0, current_index):
                        if not self._is_processed(self.all_matches[i]):
                            current_index = i
                            found = True
                            break
                if not found:
                    print("All cards have been matched!")

            elif cmd.lower() == 'q':
                # Check for unsaved changes
                has_changes = any(
                    m.inv_card.echo_matched_id
                    for matches in self.all_matches
                    for m in matches
                )
                if has_changes:
                    save = input("Save changes before quitting? [y/n]: ").strip().lower()
                    if save == 'y':
                        self.save_inventory()
                print("Goodbye!")
                break

            else:
                print("Unknown command.")


def main():
    tracker = InvestigationTracker()
    tracker.run()


if __name__ == '__main__':
    main()
