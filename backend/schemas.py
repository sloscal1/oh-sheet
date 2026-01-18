from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class CardBase(BaseModel):
    id: str
    name: str
    set: str
    lang: str
    finishes: str
    promo: bool
    border_color: Optional[str] = None
    promo_types: Optional[str] = None
    full_art: bool
    collector_number: Optional[str] = None


class CardResponse(CardBase):
    class Config:
        from_attributes = True


class CardSearchResponse(BaseModel):
    cards: List[CardResponse]
    total: int
    page: int
    page_size: int


class InventoryItemBase(BaseModel):
    card_id: str
    location: str
    position: int
    condition: str = "near mint"


class InventoryItemCreate(InventoryItemBase):
    pass


class InventoryItemUpdate(BaseModel):
    location: Optional[str] = None
    position: Optional[int] = None
    condition: Optional[str] = None


class InventoryItemResponse(BaseModel):
    id: int
    card_id: str
    location: str
    position: int
    condition: str
    created_at: datetime
    # Include card details for display
    name: Optional[str] = None
    set: Optional[str] = None
    lang: Optional[str] = None
    finishes: Optional[str] = None
    promo: Optional[bool] = None
    border_color: Optional[str] = None
    promo_types: Optional[str] = None
    full_art: Optional[bool] = None
    collector_number: Optional[str] = None

    class Config:
        from_attributes = True


class InventoryListResponse(BaseModel):
    items: List[InventoryItemResponse]
    total: int
