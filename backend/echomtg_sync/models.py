"""Pydantic models for EchoMTG sync operations."""

from dataclasses import dataclass, field
from typing import List, Optional

import pandas as pd


@dataclass
class DeduplicatedCard:
    """Represents a card after deduplication.

    Consolidates multiple rows for the same card into one record with:
    - Summed quantities
    - Concatenated locations
    - Primary echo_inventory_id (to keep)
    - List of duplicate echo_inventory_ids (to remove)
    """
    card_key: str
    name: str
    set_name: str
    set_code: str
    collector_number: str
    is_foil: bool
    condition: str
    language: str
    reg_qty: int
    foil_qty: int
    locations: List[str] = field(default_factory=list)
    primary_echo_id: str = ""
    duplicate_echo_ids: List[str] = field(default_factory=list)
    tcgid: str = ""
    echoid: str = ""


@dataclass
class MergeResult:
    """Result of merging local inventory with EchoMTG export."""
    merged: pd.DataFrame
    unmatched_local: pd.DataFrame
    unmatched_echo: pd.DataFrame

    @property
    def merged_count(self) -> int:
        return len(self.merged)

    @property
    def unmatched_local_count(self) -> int:
        return len(self.unmatched_local)

    @property
    def unmatched_echo_count(self) -> int:
        return len(self.unmatched_echo)
