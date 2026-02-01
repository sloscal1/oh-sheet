"""Tests for CSV processing functions."""

import pandas as pd
import pytest

from echomtg_sync.csv_processor import (
    create_card_key,
    deduplicate_inventory,
    merge_inventories,
)


class TestCreateCardKey:
    """Tests for create_card_key function."""

    def test_creates_key_for_regular_card(self):
        """Regular card (Reg Qty > 0) should have R suffix."""
        row = pd.Series({
            "Name": "Lightning Bolt",
            "Set Code": "2XM",
            "Collector Number": "0117",
            "Reg Qty": "1",
            "Foil Qty": "0",
        })
        key = create_card_key(row)
        assert key == "Lightning Bolt|2XM|117|R"

    def test_creates_key_for_foil_card(self):
        """Foil card (Foil Qty > 0) should have F suffix."""
        row = pd.Series({
            "Name": "Lightning Bolt",
            "Set Code": "2XM",
            "Collector Number": "117",
            "Reg Qty": "0",
            "Foil Qty": "1",
        })
        key = create_card_key(row)
        assert key == "Lightning Bolt|2XM|117|F"

    def test_normalizes_collector_number_leading_zeros(self):
        """Leading zeros in collector number should be stripped."""
        row = pd.Series({
            "Name": "Card",
            "Set Code": "SET",
            "Collector Number": "0001",
            "Reg Qty": "1",
            "Foil Qty": "0",
        })
        key = create_card_key(row)
        assert key == "Card|SET|1|R"

    def test_handles_zero_collector_number(self):
        """Collector number '0' or '000' should become '0'."""
        row = pd.Series({
            "Name": "Card",
            "Set Code": "SET",
            "Collector Number": "000",
            "Reg Qty": "1",
            "Foil Qty": "0",
        })
        key = create_card_key(row)
        assert key == "Card|SET|0|R"

    def test_uppercases_set_code(self):
        """Set code should be uppercased."""
        row = pd.Series({
            "Name": "Card",
            "Set Code": "sta",
            "Collector Number": "49",
            "Reg Qty": "1",
            "Foil Qty": "0",
        })
        key = create_card_key(row)
        assert key == "Card|STA|49|R"

    def test_strips_name_whitespace(self):
        """Card name should have whitespace stripped."""
        row = pd.Series({
            "Name": "  Lightning Bolt  ",
            "Set Code": "2XM",
            "Collector Number": "117",
            "Reg Qty": "1",
            "Foil Qty": "0",
        })
        key = create_card_key(row)
        assert key == "Lightning Bolt|2XM|117|R"

    def test_handles_empty_qty_values(self):
        """Empty quantity values should default to regular."""
        row = pd.Series({
            "Name": "Card",
            "Set Code": "SET",
            "Collector Number": "1",
            "Reg Qty": "",
            "Foil Qty": "",
        })
        key = create_card_key(row)
        assert key == "Card|SET|1|R"


class TestMergeInventories:
    """Tests for merge_inventories function."""

    def test_matches_cards_by_key(self, sample_local_df, sample_echo_df):
        """Cards with same key should be matched."""
        result = merge_inventories(sample_local_df, sample_echo_df)

        # All 7 local rows should be matched (2 bolt reg + 1 bolt foil + 1 shock + 3 guildgate)
        assert result.merged_count == 7

    def test_assigns_echo_inventory_id(self, sample_local_df, sample_echo_df):
        """Merged rows should have echo_inventory_id from echo."""
        result = merge_inventories(sample_local_df, sample_echo_df)

        # Check that merged rows have echo_inventory_id
        for _, row in result.merged.iterrows():
            assert row["echo_inventory_id"] != "", f"Row missing echo_inventory_id: {row['Name']}"

    def test_tracks_excess_echo_rows(self, sample_local_df, sample_echo_df):
        """Echo rows without local match should be unmatched."""
        result = merge_inventories(sample_local_df, sample_echo_df)

        # Echo has:
        # - 3 regular bolts (local has 2) -> 1 excess
        # - 1 foil bolt (local has 1) -> 0 excess
        # - 1 shock (local has 1) -> 0 excess
        # - 3 guildgates (local has 3) -> 0 excess
        # - 1 counterspell (local has 0) -> 1 excess
        # Total: 2 unmatched echo
        assert result.unmatched_echo_count == 2

    def test_tracks_unmatched_local_rows(self):
        """Local rows without echo match should be unmatched."""
        local_df = pd.DataFrame([{
            "Reg Qty": "1",
            "Foil Qty": "0",
            "Name": "Unique Card",
            "Set Code": "UNQ",
            "Collector Number": "1",
            "note": "location1",
        }]).fillna("")

        echo_df = pd.DataFrame([{
            "Reg Qty": "1",
            "Foil Qty": "0",
            "Name": "Different Card",
            "Set Code": "DIF",
            "Collector Number": "1",
            "echo_inventory_id": "123",
        }]).fillna("")

        result = merge_inventories(local_df, echo_df)

        assert result.merged_count == 0
        assert result.unmatched_local_count == 1
        assert result.unmatched_echo_count == 1

    def test_preserves_local_note_in_merged(self, sample_local_df, sample_echo_df):
        """Merged rows should preserve note from local."""
        result = merge_inventories(sample_local_df, sample_echo_df)

        # Find a bolt row and check it has a note
        bolt_rows = result.merged[result.merged["Name"] == "Lightning Bolt"]
        assert len(bolt_rows) > 0
        notes = [r["note"] for _, r in bolt_rows.iterrows()]
        assert all(n.startswith("b3r4p") or n.startswith("frame") for n in notes)


class TestDeduplicateInventory:
    """Tests for deduplicate_inventory function."""

    def test_sums_quantities(self, sample_local_df, sample_echo_df):
        """Duplicate rows should have quantities summed."""
        result = merge_inventories(sample_local_df, sample_echo_df)
        deduplicated = deduplicate_inventory(result.merged)

        # Find regular bolt (should have qty 2)
        bolt_reg = next(d for d in deduplicated if "Lightning Bolt" in d.card_key and not d.is_foil)
        assert bolt_reg.reg_qty == 2

        # Find guildgate (should have qty 3)
        guildgate = next(d for d in deduplicated if "Selesnya Guildgate" in d.card_key)
        assert guildgate.reg_qty == 3

    def test_concatenates_locations(self, sample_local_df, sample_echo_df):
        """Duplicate rows should have locations concatenated."""
        result = merge_inventories(sample_local_df, sample_echo_df)
        deduplicated = deduplicate_inventory(result.merged)

        # Find guildgate - should have 3 locations
        guildgate = next(d for d in deduplicated if "Selesnya Guildgate" in d.card_key)
        assert len(guildgate.locations) == 3
        assert "b3r4p466a" in guildgate.locations
        assert "b3r4p466b" in guildgate.locations
        assert "b3r4p466c" in guildgate.locations

    def test_tracks_primary_and_duplicate_ids(self, sample_local_df, sample_echo_df):
        """First echo_inventory_id should be primary, rest should be duplicates."""
        result = merge_inventories(sample_local_df, sample_echo_df)
        deduplicated = deduplicate_inventory(result.merged)

        # Find regular bolt - should have 1 primary + 1 duplicate
        bolt_reg = next(d for d in deduplicated if "Lightning Bolt" in d.card_key and not d.is_foil)
        assert bolt_reg.primary_echo_id == "58942001"
        assert bolt_reg.duplicate_echo_ids == ["58942002"]

    def test_handles_single_row_card(self, sample_local_df, sample_echo_df):
        """Single row cards should have no duplicates."""
        result = merge_inventories(sample_local_df, sample_echo_df)
        deduplicated = deduplicate_inventory(result.merged)

        # Find shock - should have 1 row, no duplicates
        shock = next(d for d in deduplicated if "Shock" in d.card_key)
        assert shock.reg_qty == 1
        assert shock.primary_echo_id == "58942005"
        assert shock.duplicate_echo_ids == []

    def test_separates_foil_and_regular(self, sample_local_df, sample_echo_df):
        """Foil and regular versions should be separate entries."""
        result = merge_inventories(sample_local_df, sample_echo_df)
        deduplicated = deduplicate_inventory(result.merged)

        # Should have both regular and foil bolt
        bolts = [d for d in deduplicated if "Lightning Bolt" in d.card_key]
        assert len(bolts) == 2

        foil_bolt = next(d for d in bolts if d.is_foil)
        reg_bolt = next(d for d in bolts if not d.is_foil)

        assert foil_bolt.foil_qty == 1
        assert reg_bolt.reg_qty == 2

    def test_returns_empty_for_empty_df(self):
        """Empty DataFrame should return empty list."""
        result = deduplicate_inventory(pd.DataFrame())
        assert result == []

    def test_handles_empty_note(self):
        """Rows with empty notes should not add to locations."""
        merged = pd.DataFrame([
            {
                "card_key": "Card|SET|1|R",
                "Name": "Card",
                "Set": "Set Name",
                "Set Code": "SET",
                "Collector Number": "1",
                "Reg Qty": "1",
                "Foil Qty": "0",
                "Condition": "NM",
                "Language": "EN",
                "note": "",
                "echo_inventory_id": "123",
                "tcgid": "456",
                "echoid": "789",
            },
            {
                "card_key": "Card|SET|1|R",
                "Name": "Card",
                "Set": "Set Name",
                "Set Code": "SET",
                "Collector Number": "1",
                "Reg Qty": "1",
                "Foil Qty": "0",
                "Condition": "NM",
                "Language": "EN",
                "note": "   ",  # whitespace only
                "echo_inventory_id": "124",
                "tcgid": "456",
                "echoid": "789",
            },
        ])

        result = deduplicate_inventory(merged)

        assert len(result) == 1
        assert result[0].locations == []  # Both notes were empty/whitespace
