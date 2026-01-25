import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

# Set test database before importing app modules
os.environ["DATABASE_URL"] = "postgresql+psycopg://localhost/mtg_inventory_test"

from database import Base, get_db, Card, InventoryItem
from main import app


@pytest.fixture(scope="session")
def engine():
    """Create test database engine."""
    engine = create_engine(os.environ["DATABASE_URL"])
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(engine):
    """Create a fresh database session for each test."""
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def client(db_session):
    """Create test client with database session override."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_cards(db_session):
    """Create sample cards for testing."""
    cards = [
        Card(
            id="test-uuid-1-n",
            name="Lightning Bolt",
            set="2xm",
            lang="en",
            finishes="nonfoil",
            promo=False,
            border_color="black",
            promo_types="--",
            full_art=False,
            collector_number="0117",
        ),
        Card(
            id="test-uuid-1-f",
            name="Lightning Bolt",
            set="2xm",
            lang="en",
            finishes="foil",
            promo=False,
            border_color="black",
            promo_types="--",
            full_art=False,
            collector_number="0117",
        ),
        Card(
            id="test-uuid-2-n",
            name="Shock",
            set="sta",
            lang="ja",
            finishes="etched",
            promo=False,
            border_color="black",
            promo_types="--",
            full_art=False,
            collector_number="0107",
        ),
        Card(
            id="test-uuid-3-n",
            name="Island",
            set="neo",
            lang="ja",
            finishes="nonfoil",
            promo=False,
            border_color="black",
            promo_types="--",
            full_art=True,
            collector_number="0295",
        ),
        Card(
            id="test-uuid-4-n",
            name="Gitaxian Probe",
            set="nph",
            lang="ph",
            finishes="nonfoil",
            promo=False,
            border_color="black",
            promo_types="--",
            full_art=False,
            collector_number="0035",
        ),
    ]
    for card in cards:
        db_session.add(card)
    db_session.commit()
    return cards


@pytest.fixture
def sample_inventory(db_session, sample_cards):
    """Create sample inventory items for testing."""
    items = [
        InventoryItem(
            card_id="test-uuid-1-n",
            location="Box A",
            position=1,
            condition="near mint",
        ),
        InventoryItem(
            card_id="test-uuid-1-n",
            location="Box A",
            position=2,
            condition="near mint",
        ),
        InventoryItem(
            card_id="test-uuid-1-f",
            location="Box A",
            position=3,
            condition="lightly played",
        ),
        InventoryItem(
            card_id="test-uuid-2-n",
            location="Box B",
            position=1,
            condition="near mint",
        ),
        InventoryItem(
            card_id="test-uuid-3-n",
            location="Box B",
            position=2,
            condition="played",
        ),
        InventoryItem(
            card_id="test-uuid-4-n",
            location="Box C",
            position=1,
            condition="near mint",
        ),
    ]
    for item in items:
        db_session.add(item)
    db_session.commit()
    return items
