#!/usr/bin/env python3
"""
Migration script to import existing JSON data into PostgreSQL database.

Usage:
    python migrate.py [--cards-only] [--inventory-only]

Prerequisites:
    - PostgreSQL database 'mtg_inventory' must exist
    - Run: createdb mtg_inventory
"""

import json
import argparse
import sys
from pathlib import Path

from database import engine, Base, SessionLocal, Card, InventoryItem

# Paths to JSON files
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CARDS_JSON = PROJECT_ROOT / "docs" / "mtg_possible_20240407_clean.json"
INVENTORY_JSON = PROJECT_ROOT / "data" / "inventory.json"


def create_tables():
    """Create database tables if they don't exist."""
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully.")


def migrate_cards(batch_size: int = 5000, force: bool = False):
    """Migrate cards from JSON file to database."""
    if not CARDS_JSON.exists():
        print(f"Error: Cards JSON file not found at {CARDS_JSON}")
        return False

    print(f"Loading cards from {CARDS_JSON}...")
    with open(CARDS_JSON, "r") as f:
        cards_data = json.load(f)

    print(f"Found {len(cards_data)} cards to migrate.")

    db = SessionLocal()
    try:
        # Check if cards table already has data
        existing_count = db.query(Card).count()
        if existing_count > 0:
            print(f"Cards table already has {existing_count} records.")
            if force:
                response = "y"
            else:
                response = input("Do you want to clear and re-import? (y/N): ")
            if response.lower() == "y":
                db.query(Card).delete()
                db.commit()
                print("Cleared existing cards.")
            else:
                print("Skipping cards migration.")
                return True

        # Deduplicate cards by ID (keep first occurrence)
        seen_ids = set()
        unique_cards_data = []
        for card_data in cards_data:
            if card_data["id"] not in seen_ids:
                seen_ids.add(card_data["id"])
                unique_cards_data.append(card_data)

        if len(unique_cards_data) < len(cards_data):
            print(f"Note: Removed {len(cards_data) - len(unique_cards_data)} duplicate card IDs.")

        # Insert cards in batches
        total = len(unique_cards_data)
        for i in range(0, total, batch_size):
            batch = unique_cards_data[i : i + batch_size]
            cards = []
            for card_data in batch:
                cards.append(
                    Card(
                        id=card_data["id"],
                        name=card_data["name"],
                        set=card_data["set"],
                        lang=card_data["lang"],
                        finishes=card_data["finishes"],
                        promo=card_data.get("promo", False),
                        border_color=card_data.get("border_color"),
                        promo_types=card_data.get("promo_types"),
                        full_art=card_data.get("full_art", False),
                        collector_number=card_data.get("collector_number"),
                    )
                )

            db.bulk_save_objects(cards)
            db.commit()

            progress = min(i + batch_size, total)
            print(f"Progress: {progress}/{total} cards ({100 * progress // total}%)")

        print(f"Successfully migrated {total} cards.")
        return True

    except Exception as e:
        db.rollback()
        print(f"Error migrating cards: {e}")
        return False

    finally:
        db.close()


def migrate_inventory(force: bool = False):
    """Migrate inventory from JSON file to database."""
    if not INVENTORY_JSON.exists():
        print(f"Warning: Inventory JSON file not found at {INVENTORY_JSON}")
        print("Skipping inventory migration.")
        return True

    print(f"Loading inventory from {INVENTORY_JSON}...")
    with open(INVENTORY_JSON, "r") as f:
        inventory_data = json.load(f)

    print(f"Found {len(inventory_data)} inventory items to migrate.")

    db = SessionLocal()
    try:
        # Check if inventory table already has data
        existing_count = db.query(InventoryItem).count()
        if existing_count > 0:
            print(f"Inventory table already has {existing_count} records.")
            if force:
                response = "y"
            else:
                response = input("Do you want to clear and re-import? (y/N): ")
            if response.lower() == "y":
                db.query(InventoryItem).delete()
                db.commit()
                print("Cleared existing inventory.")
            else:
                print("Skipping inventory migration.")
                return True

        # Insert inventory items
        items = []
        missing_cards = set()
        for item_data in inventory_data:
            card_id = item_data["id"]

            # Check if card exists
            card_exists = db.query(Card).filter(Card.id == card_id).first()
            if not card_exists:
                missing_cards.add(card_id)
                continue

            items.append(
                InventoryItem(
                    card_id=card_id,
                    location=item_data["location"],
                    position=item_data["pos"],
                    condition=item_data.get("condition", "near mint"),
                )
            )

        if missing_cards:
            print(f"Warning: {len(missing_cards)} inventory items reference cards not in database:")
            for card_id in list(missing_cards)[:5]:
                print(f"  - {card_id}")
            if len(missing_cards) > 5:
                print(f"  ... and {len(missing_cards) - 5} more")

        db.bulk_save_objects(items)
        db.commit()

        print(f"Successfully migrated {len(items)} inventory items.")
        return True

    except Exception as e:
        db.rollback()
        print(f"Error migrating inventory: {e}")
        return False

    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Migrate MTG data from JSON to PostgreSQL")
    parser.add_argument("--cards-only", action="store_true", help="Only migrate cards")
    parser.add_argument("--inventory-only", action="store_true", help="Only migrate inventory")
    parser.add_argument("--force", action="store_true", help="Force re-import without prompting")
    args = parser.parse_args()

    print("MTG Inventory Migration Script")
    print("=" * 40)

    create_tables()

    if args.inventory_only:
        success = migrate_inventory(force=args.force)
    elif args.cards_only:
        success = migrate_cards(force=args.force)
    else:
        success = migrate_cards(force=args.force) and migrate_inventory(force=args.force)

    if success:
        print("\nMigration completed successfully!")
    else:
        print("\nMigration completed with errors.")
        sys.exit(1)


if __name__ == "__main__":
    main()
