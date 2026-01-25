"""
API integration tests for the MTG Inventory backend.

These tests verify the API endpoints work correctly with a test database.
"""
import csv
import io
import pytest


class TestCardsAPI:
    """Tests for card-related endpoints."""

    def test_get_all_cards_empty(self, client):
        """Test getting all cards when database is empty."""
        response = client.get("/api/cards/all")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_all_cards_with_data(self, client, sample_cards):
        """Test getting all cards returns all cards."""
        response = client.get("/api/cards/all")
        assert response.status_code == 200
        cards = response.json()
        assert len(cards) == 5

    def test_search_cards_by_name(self, client, sample_cards):
        """Test searching cards by name."""
        response = client.get("/api/cards", params={"name": "Lightning"})
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2  # Both foil and nonfoil Lightning Bolt

    def test_search_cards_by_language(self, client, sample_cards):
        """Test filtering cards by language."""
        response = client.get("/api/cards", params={"lang": "ja"})
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2  # Shock (ja) and Island (ja)

    def test_search_cards_by_set(self, client, sample_cards):
        """Test filtering cards by set."""
        response = client.get("/api/cards", params={"set": "sta"})
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["cards"][0]["name"] == "Shock"


class TestInventoryAPI:
    """Tests for inventory-related endpoints."""

    def test_get_inventory_empty(self, client, sample_cards):
        """Test getting inventory when empty."""
        response = client.get("/api/inventory")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_get_inventory_with_data(self, client, sample_inventory):
        """Test getting inventory returns all items."""
        response = client.get("/api/inventory")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 6

    def test_get_inventory_filter_by_location(self, client, sample_inventory):
        """Test filtering inventory by location."""
        response = client.get("/api/inventory", params={"location": "Box A"})
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3

    def test_add_to_inventory(self, client, sample_cards):
        """Test adding a card to inventory."""
        response = client.post("/api/inventory", json={
            "card_id": "test-uuid-1-n",
            "location": "Test Box",
            "position": 1,
            "condition": "near mint",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["card_id"] == "test-uuid-1-n"
        assert data["location"] == "Test Box"
        assert data["name"] == "Lightning Bolt"

    def test_add_to_inventory_invalid_card(self, client, sample_cards):
        """Test adding non-existent card returns 404."""
        response = client.post("/api/inventory", json={
            "card_id": "nonexistent-card-id",
            "location": "Test Box",
            "position": 1,
            "condition": "near mint",
        })
        assert response.status_code == 404

    def test_remove_from_inventory(self, client, sample_inventory, db_session):
        """Test removing a card from inventory."""
        # Get an inventory item ID
        response = client.get("/api/inventory")
        item_id = response.json()["items"][0]["id"]

        # Remove it
        response = client.delete(f"/api/inventory/{item_id}")
        assert response.status_code == 200

        # Verify it's gone
        response = client.get("/api/inventory")
        assert response.json()["total"] == 5

    def test_get_next_position(self, client, sample_inventory):
        """Test getting next position for a location."""
        response = client.get("/api/inventory/next-position", params={"location": "Box A"})
        assert response.status_code == 200
        assert response.json()["next_position"] == 4  # 3 items, next is 4

    def test_get_next_position_new_location(self, client, sample_inventory):
        """Test getting next position for new location."""
        response = client.get("/api/inventory/next-position", params={"location": "New Box"})
        assert response.status_code == 200
        assert response.json()["next_position"] == 1

    def test_get_locations(self, client, sample_inventory):
        """Test getting all unique locations."""
        response = client.get("/api/locations")
        assert response.status_code == 200
        locations = response.json()
        assert set(locations) == {"Box A", "Box B", "Box C"}


class TestExportDeckbox:
    """Tests for Deckbox CSV export endpoint."""

    def test_export_deckbox_empty(self, client, sample_cards):
        """Test Deckbox export with empty inventory."""
        response = client.get("/api/inventory/export/deckbox")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"

        # Parse CSV
        content = response.text
        reader = csv.DictReader(io.StringIO(content))
        rows = list(reader)
        assert len(rows) == 0

    def test_export_deckbox_headers(self, client, sample_inventory):
        """Test Deckbox export has correct headers."""
        response = client.get("/api/inventory/export/deckbox")
        content = response.text
        reader = csv.DictReader(io.StringIO(content))

        expected_headers = [
            "Count", "Tradelist Count", "Name", "Edition", "Card Number",
            "Condition", "Language", "Foil", "Signed", "Artist Proof",
            "Altered Art", "Mis"
        ]
        assert reader.fieldnames == expected_headers

    def test_export_deckbox_aggregates_quantity(self, client, sample_inventory):
        """Test Deckbox export aggregates quantity correctly."""
        response = client.get("/api/inventory/export/deckbox")
        content = response.text
        reader = csv.DictReader(io.StringIO(content))
        rows = list(reader)

        # Find Lightning Bolt nonfoil (should have count of 2)
        bolt_rows = [r for r in rows if r["Name"] == "Lightning Bolt" and r["Foil"] == ""]
        assert len(bolt_rows) == 1
        assert bolt_rows[0]["Count"] == "2"

    def test_export_deckbox_language_mapping(self, client, sample_inventory):
        """Test Deckbox export maps language codes to full names."""
        response = client.get("/api/inventory/export/deckbox")
        content = response.text
        reader = csv.DictReader(io.StringIO(content))
        rows = list(reader)

        # Find Japanese cards
        ja_rows = [r for r in rows if r["Language"] == "Japanese"]
        assert len(ja_rows) == 2  # Shock and Island

        # Find Phyrexian cards
        ph_rows = [r for r in rows if r["Language"] == "Phyrexian"]
        assert len(ph_rows) == 1

        # Find English cards
        en_rows = [r for r in rows if r["Language"] == "English"]
        assert len(en_rows) == 2  # Lightning Bolt foil and nonfoil

    def test_export_deckbox_foil_status(self, client, sample_inventory):
        """Test Deckbox export sets foil status correctly."""
        response = client.get("/api/inventory/export/deckbox")
        content = response.text
        reader = csv.DictReader(io.StringIO(content))
        rows = list(reader)

        # Find foil Lightning Bolt
        foil_bolt = [r for r in rows if r["Name"] == "Lightning Bolt" and r["Foil"] == "foil"]
        assert len(foil_bolt) == 1

        # Find etched Shock (should also be foil)
        etched_shock = [r for r in rows if r["Name"] == "Shock"]
        assert len(etched_shock) == 1
        assert etched_shock[0]["Foil"] == "foil"
        assert "etched" in etched_shock[0]["Mis"]

    def test_export_deckbox_condition_mapping(self, client, sample_inventory):
        """Test Deckbox export maps conditions to full names."""
        response = client.get("/api/inventory/export/deckbox")
        content = response.text
        reader = csv.DictReader(io.StringIO(content))
        rows = list(reader)

        conditions = {r["Condition"] for r in rows}
        assert "Near Mint" in conditions
        assert "Lightly Played" in conditions
        assert "Played" in conditions

    def test_export_deckbox_location_in_mis(self, client, sample_inventory):
        """Test Deckbox export includes location in Mis field."""
        response = client.get("/api/inventory/export/deckbox")
        content = response.text
        reader = csv.DictReader(io.StringIO(content))
        rows = list(reader)

        for row in rows:
            assert "Locations:" in row["Mis"]

        # Check specific location format
        bolt_rows = [r for r in rows if r["Name"] == "Lightning Bolt" and r["Foil"] == ""]
        assert "Box A:1" in bolt_rows[0]["Mis"]
        assert "Box A:2" in bolt_rows[0]["Mis"]


class TestExportMtggoldfish:
    """Tests for MTGGoldfish CSV export endpoint."""

    def test_export_mtggoldfish_empty(self, client, sample_cards):
        """Test MTGGoldfish export with empty inventory."""
        response = client.get("/api/inventory/export/mtggoldfish")
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"

        content = response.text
        reader = csv.DictReader(io.StringIO(content))
        rows = list(reader)
        assert len(rows) == 0

    def test_export_mtggoldfish_headers(self, client, sample_inventory):
        """Test MTGGoldfish export has correct headers."""
        response = client.get("/api/inventory/export/mtggoldfish")
        content = response.text
        reader = csv.DictReader(io.StringIO(content))

        expected_headers = [
            "Card Name", "Quantity", "ID #", "Rarity", "Set", "Collector #", "Premium"
        ]
        assert reader.fieldnames == expected_headers

    def test_export_mtggoldfish_aggregates_quantity(self, client, sample_inventory):
        """Test MTGGoldfish export aggregates quantity correctly."""
        response = client.get("/api/inventory/export/mtggoldfish")
        content = response.text
        reader = csv.DictReader(io.StringIO(content))
        rows = list(reader)

        # Find Lightning Bolt nonfoil (should have quantity of 2)
        bolt_rows = [r for r in rows if r["Card Name"] == "Lightning Bolt" and r["Premium"] == "No"]
        assert len(bolt_rows) == 1
        assert bolt_rows[0]["Quantity"] == "2"

    def test_export_mtggoldfish_premium_field(self, client, sample_inventory):
        """Test MTGGoldfish export sets Premium field correctly."""
        response = client.get("/api/inventory/export/mtggoldfish")
        content = response.text
        reader = csv.DictReader(io.StringIO(content))
        rows = list(reader)

        # Find foil Lightning Bolt
        foil_bolt = [r for r in rows if r["Card Name"] == "Lightning Bolt" and r["Premium"] == "Yes"]
        assert len(foil_bolt) == 1

        # Nonfoil should have Premium = No
        nonfoil_bolt = [r for r in rows if r["Card Name"] == "Lightning Bolt" and r["Premium"] == "No"]
        assert len(nonfoil_bolt) == 1

        # Etched should have Premium = Yes
        etched_shock = [r for r in rows if r["Card Name"] == "Shock"]
        assert len(etched_shock) == 1
        assert etched_shock[0]["Premium"] == "Yes"

    def test_export_mtggoldfish_set_uppercase(self, client, sample_inventory):
        """Test MTGGoldfish export uses uppercase set codes."""
        response = client.get("/api/inventory/export/mtggoldfish")
        content = response.text
        reader = csv.DictReader(io.StringIO(content))
        rows = list(reader)

        for row in rows:
            assert row["Set"] == row["Set"].upper()

    def test_export_mtggoldfish_collector_number_stripped(self, client, sample_inventory):
        """Test MTGGoldfish export strips leading zeros from collector numbers."""
        response = client.get("/api/inventory/export/mtggoldfish")
        content = response.text
        reader = csv.DictReader(io.StringIO(content))
        rows = list(reader)

        # All collector numbers should not have leading zeros
        for row in rows:
            if row["Collector #"]:
                assert not row["Collector #"].startswith("0")


class TestReindex:
    """Tests for reindex endpoint."""

    def test_reindex_location(self, client, sample_inventory, db_session):
        """Test reindexing a location."""
        response = client.post("/api/inventory/reindex", params={
            "location": "Box A",
            "divider_interval": 2,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["location"] == "Box A"
        assert data["total_cards"] == 3

    def test_reindex_nonexistent_location(self, client, sample_inventory):
        """Test reindexing a location with no cards."""
        response = client.post("/api/inventory/reindex", params={
            "location": "Nonexistent",
        })
        assert response.status_code == 404
