from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import Optional, List
from collections import defaultdict
import csv
import io
import re

from database import get_db, Card, InventoryItem, init_db
from schemas import (
    CardResponse,
    CardSearchResponse,
    InventoryItemCreate,
    InventoryItemUpdate,
    InventoryItemResponse,
    InventoryListResponse,
)

app = FastAPI(title="MTG Inventory API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    init_db()


@app.get("/api/cards", response_model=CardSearchResponse)
def search_cards(
    name: Optional[str] = None,
    set: Optional[str] = None,
    lang: Optional[str] = None,
    finishes: Optional[str] = None,
    promo: Optional[bool] = None,
    border_color: Optional[str] = None,
    promo_types: Optional[str] = None,
    full_art: Optional[bool] = None,
    collector_number: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    query = db.query(Card)

    if name:
        # Support the same fuzzy search as the frontend
        # Split on capital letters and create a regex-like pattern
        term_parts = re.split(r"(?=[A-Z])", name)
        pattern = "%".join(p for p in term_parts if p)
        query = query.filter(Card.name.ilike(f"%{pattern}%"))

    if set:
        query = query.filter(Card.set == set)

    if lang:
        query = query.filter(Card.lang == lang)

    if finishes:
        query = query.filter(Card.finishes == finishes)

    if promo is not None:
        query = query.filter(Card.promo == promo)

    if border_color:
        query = query.filter(Card.border_color == border_color)

    if promo_types:
        query = query.filter(Card.promo_types == promo_types)

    if full_art is not None:
        query = query.filter(Card.full_art == full_art)

    if collector_number:
        # Support =, >, < prefixes like the frontend
        if collector_number.startswith("="):
            query = query.filter(Card.collector_number == collector_number[1:])
        elif collector_number.startswith(">"):
            query = query.filter(Card.collector_number > collector_number[1:])
        elif collector_number.startswith("<"):
            query = query.filter(Card.collector_number < collector_number[1:])

    total = query.count()
    cards = query.offset((page - 1) * page_size).limit(page_size).all()

    return CardSearchResponse(
        cards=[CardResponse.model_validate(c) for c in cards],
        total=total,
        page=page,
        page_size=page_size,
    )


@app.get("/api/cards/all")
def get_all_cards(db: Session = Depends(get_db)):
    """Get all cards - used for initial frontend load."""
    cards = db.query(Card).all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "set": c.set,
            "lang": c.lang,
            "finishes": c.finishes,
            "promo": c.promo,
            "border_color": c.border_color,
            "promo_types": c.promo_types,
            "full_art": c.full_art,
            "collector_number": c.collector_number,
        }
        for c in cards
    ]


@app.get("/api/inventory", response_model=InventoryListResponse)
def get_inventory(
    location: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(InventoryItem).join(Card)

    if location:
        query = query.filter(InventoryItem.location.ilike(f"%{location}%"))

    items = query.all()

    result = []
    for item in items:
        result.append(
            InventoryItemResponse(
                id=item.id,
                card_id=item.card_id,
                location=item.location,
                position=item.position,
                condition=item.condition,
                created_at=item.created_at,
                name=item.card.name,
                set=item.card.set,
                lang=item.card.lang,
                finishes=item.card.finishes,
                promo=item.card.promo,
                border_color=item.card.border_color,
                promo_types=item.card.promo_types,
                full_art=item.card.full_art,
                collector_number=item.card.collector_number,
            )
        )

    return InventoryListResponse(items=result, total=len(result))


@app.get("/api/inventory/export")
def export_inventory(db: Session = Depends(get_db)):
    """Export inventory in the same format as the original JSON file."""
    items = db.query(InventoryItem).join(Card).all()

    result = []
    for item in items:
        result.append(
            {
                "location": item.location,
                "id": item.card_id,
                "pos": item.position,
                "name": item.card.name,
                "set": item.card.set,
                "lang": item.card.lang,
                "finishes": item.card.finishes,
                "promo": item.card.promo,
                "border_color": item.card.border_color,
                "promo_types": item.card.promo_types,
                "full_art": item.card.full_art,
                "collector_number": item.card.collector_number,
                "condition": item.condition,
            }
        )

    return result


@app.post("/api/inventory", response_model=InventoryItemResponse)
def add_to_inventory(
    item: InventoryItemCreate,
    db: Session = Depends(get_db),
):
    # Verify the card exists
    card = db.query(Card).filter(Card.id == item.card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    db_item = InventoryItem(
        card_id=item.card_id,
        location=item.location,
        position=item.position,
        condition=item.condition,
    )
    db.add(db_item)
    db.commit()
    db.refresh(db_item)

    return InventoryItemResponse(
        id=db_item.id,
        card_id=db_item.card_id,
        location=db_item.location,
        position=db_item.position,
        condition=db_item.condition,
        created_at=db_item.created_at,
        name=card.name,
        set=card.set,
        lang=card.lang,
        finishes=card.finishes,
        promo=card.promo,
        border_color=card.border_color,
        promo_types=card.promo_types,
        full_art=card.full_art,
        collector_number=card.collector_number,
    )


@app.delete("/api/inventory/{item_id}")
def remove_from_inventory(
    item_id: int,
    db: Session = Depends(get_db),
):
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")

    db.delete(item)
    db.commit()

    return {"message": "Item removed from inventory"}


@app.delete("/api/inventory/by-card/{card_id}")
def remove_from_inventory_by_card_id(
    card_id: str,
    location: Optional[str] = None,
    position: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Remove inventory item by card_id (and optionally location/position for specificity)."""
    query = db.query(InventoryItem).filter(InventoryItem.card_id == card_id)

    if location:
        query = query.filter(InventoryItem.location == location)
    if position is not None:
        query = query.filter(InventoryItem.position == position)

    item = query.first()
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")

    db.delete(item)
    db.commit()

    return {"message": "Item removed from inventory"}


@app.put("/api/inventory/{item_id}", response_model=InventoryItemResponse)
def update_inventory_item(
    item_id: int,
    update: InventoryItemUpdate,
    db: Session = Depends(get_db),
):
    item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")

    if update.location is not None:
        item.location = update.location
    if update.position is not None:
        item.position = update.position
    if update.condition is not None:
        item.condition = update.condition

    db.commit()
    db.refresh(item)

    card = item.card

    return InventoryItemResponse(
        id=item.id,
        card_id=item.card_id,
        location=item.location,
        position=item.position,
        condition=item.condition,
        created_at=item.created_at,
        name=card.name,
        set=card.set,
        lang=card.lang,
        finishes=card.finishes,
        promo=card.promo,
        border_color=card.border_color,
        promo_types=card.promo_types,
        full_art=card.full_art,
        collector_number=card.collector_number,
    )


@app.get("/api/locations")
def get_locations(db: Session = Depends(get_db)):
    """Get all unique locations in the inventory."""
    locations = (
        db.query(InventoryItem.location).distinct().order_by(InventoryItem.location).all()
    )
    return [loc[0] for loc in locations]


@app.get("/api/inventory/next-position")
def get_next_position(
    location: str,
    db: Session = Depends(get_db),
):
    """Get the next available position for a location."""
    max_pos = (
        db.query(func.max(InventoryItem.position))
        .filter(InventoryItem.location == location)
        .scalar()
    )
    return {"next_position": (max_pos or 0) + 1}


@app.post("/api/inventory/reindex")
def reindex_location(
    location: str,
    divider_interval: int = 50,
    db: Session = Depends(get_db),
):
    """
    Reindex all cards in a location to remove position gaps.

    Renumbers positions from 1 to N (total cards in location).
    Returns cards at every divider_interval position for physical divider placement.
    """
    # Get all items in this location, ordered by current position
    items = (
        db.query(InventoryItem)
        .filter(InventoryItem.location == location)
        .order_by(InventoryItem.position)
        .all()
    )

    if not items:
        raise HTTPException(status_code=404, detail=f"No items found in location: {location}")

    divider_cards = []

    # Reassign positions sequentially starting from 1
    for new_pos, item in enumerate(items, start=1):
        item.position = new_pos

        # Track cards at divider intervals (50, 100, 150, etc.)
        if new_pos % divider_interval == 0:
            divider_cards.append({
                "position": new_pos,
                "card_id": item.card_id,
                "name": item.card.name,
                "set": item.card.set,
                "collector_number": item.card.collector_number,
                "finishes": item.card.finishes,
            })

    db.commit()

    return {
        "location": location,
        "total_cards": len(items),
        "message": f"Reindexed {len(items)} cards in '{location}' from position 1 to {len(items)}",
        "divider_cards": divider_cards,
    }


# Language code to full name mapping
LANGUAGE_MAP = {
    "en": "English",
    "ja": "Japanese",
    "ph": "Phyrexian",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "ko": "Korean",
    "ru": "Russian",
    "zhs": "Chinese Simplified",
    "zht": "Chinese Traditional",
}

# Condition mapping to Deckbox format
CONDITION_MAP = {
    "near mint": "Near Mint",
    "lightly played": "Lightly Played",
    "played": "Played",
    "heavily played": "Heavily Played",
    "damaged": "Damaged",
}


@app.get("/api/inventory/export/deckbox")
def export_inventory_deckbox(db: Session = Depends(get_db)):
    """
    Export inventory in Deckbox CSV format.
    Format: Count,Tradelist Count,Name,Edition,Card Number,Condition,Language,Foil,Signed,Artist Proof,Altered Art,Mis

    The Mis (Miscellaneous) field contains location and finish type for reference.
    """
    items = db.query(InventoryItem).join(Card).order_by(
        InventoryItem.location, InventoryItem.position
    ).all()

    # Aggregate by unique card characteristics + condition + location
    aggregated = defaultdict(lambda: {"count": 0, "locations": []})

    for item in items:
        card = item.card
        # Key includes all identifying factors
        key = (
            card.name,
            card.set,
            card.collector_number,
            card.lang,
            card.finishes,
            item.condition,
        )
        aggregated[key]["count"] += 1
        aggregated[key]["locations"].append(f"{item.location}:{item.position}")
        aggregated[key]["card"] = card
        aggregated[key]["condition"] = item.condition

    output = io.StringIO()
    writer = csv.writer(output)

    # Deckbox header
    writer.writerow([
        "Count", "Tradelist Count", "Name", "Edition", "Card Number",
        "Condition", "Language", "Foil", "Signed", "Artist Proof", "Altered Art", "Mis"
    ])

    for key, data in aggregated.items():
        card = data["card"]
        condition = data["condition"]

        # Determine foil status
        is_foil = card.finishes in ("foil", "etched")

        # Build miscellaneous field with location and finish details
        locations_str = "; ".join(data["locations"])
        mis_parts = [f"Locations: {locations_str}"]
        if card.finishes == "etched":
            mis_parts.append("Finish: etched")
        mis_field = " | ".join(mis_parts)

        writer.writerow([
            data["count"],                              # Count
            0,                                          # Tradelist Count
            card.name,                                  # Name
            card.set.upper(),                           # Edition (set code)
            card.collector_number.lstrip("0"),          # Card Number (strip leading zeros)
            CONDITION_MAP.get(condition, condition),    # Condition
            LANGUAGE_MAP.get(card.lang, card.lang),     # Language
            "foil" if is_foil else "",                  # Foil
            "",                                         # Signed
            "",                                         # Artist Proof
            "",                                         # Altered Art
            mis_field,                                  # Mis (locations + finish)
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=inventory_deckbox.csv"}
    )


@app.get("/api/inventory/export/mtggoldfish")
def export_inventory_mtggoldfish(db: Session = Depends(get_db)):
    """
    Export inventory in MTGGoldfish CSV format.
    Format: Card Name,Quantity,ID #,Rarity,Set,Collector #,Premium

    Note: This format does not support language, so non-English cards
    may not import correctly into MTGGoldfish.
    """
    items = db.query(InventoryItem).join(Card).all()

    # Aggregate by card name + set + collector number + finish
    aggregated = defaultdict(lambda: {"count": 0, "card": None})

    for item in items:
        card = item.card
        key = (card.name, card.set, card.collector_number, card.finishes)
        aggregated[key]["count"] += 1
        aggregated[key]["card"] = card

    output = io.StringIO()
    writer = csv.writer(output)

    # MTGGoldfish header
    writer.writerow([
        "Card Name", "Quantity", "ID #", "Rarity", "Set", "Collector #", "Premium"
    ])

    for key, data in aggregated.items():
        card = data["card"]

        # Premium: Yes for foil/etched, No for nonfoil
        premium = "Yes" if card.finishes in ("foil", "etched") else "No"

        writer.writerow([
            card.name,                              # Card Name
            data["count"],                          # Quantity
            "",                                     # ID # (optional)
            "",                                     # Rarity (optional)
            card.set.upper(),                       # Set
            card.collector_number.lstrip("0"),      # Collector #
            premium,                                # Premium
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=inventory_mtggoldfish.csv"}
    )
