import os
from sqlalchemy import create_engine, Column, String, Boolean, Integer, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://localhost/mtg_inventory")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class Card(Base):
    __tablename__ = "cards"

    id = Column(String(50), primary_key=True)  # e.g., "uuid-n", "uuid-f"
    name = Column(String(255), nullable=False, index=True)
    set = Column(String(10), nullable=False, index=True)
    lang = Column(String(5), nullable=False)
    finishes = Column(String(20), nullable=False)  # nonfoil/foil/etched
    promo = Column(Boolean, default=False)
    border_color = Column(String(20))
    promo_types = Column(String(100))
    full_art = Column(Boolean, default=False)
    collector_number = Column(String(20))

    inventory_items = relationship("InventoryItem", back_populates="card")


class InventoryItem(Base):
    __tablename__ = "inventory"

    id = Column(Integer, primary_key=True, autoincrement=True)
    card_id = Column(String(50), ForeignKey("cards.id"), nullable=False, index=True)
    location = Column(String(100), nullable=False, index=True)
    position = Column(Integer, nullable=False)
    condition = Column(String(20), default="near mint")
    created_at = Column(DateTime, default=datetime.utcnow)

    card = relationship("Card", back_populates="inventory_items")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
