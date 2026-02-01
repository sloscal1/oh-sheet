"""CSV processing utilities for EchoMTG inventory sync."""

import re
from pathlib import Path
from typing import List

import pandas as pd

from .models import DeduplicatedCard, MergeResult


def load_csv(path: Path) -> pd.DataFrame:
    """Load a CSV file and return as DataFrame.

    All columns are loaded as strings to preserve formatting.
    NaN values are replaced with empty strings.
    """
    df = pd.read_csv(path, dtype=str)
    df = df.fillna("")
    return df


def normalize_card_name(name: str) -> str:
    """Normalize card name for matching.

    - Takes only the front face for double-faced cards (before ' // ')
    - Removes treatment suffixes like (Retro Frame), (Extended Art), (Borderless), etc.
    - Removes collector number suffixes like (265) for basic lands
    - Removes "Token" suffix for token cards
    - Normalizes emblem names (both formats to common form)
    - Strips whitespace
    """
    name = name.strip()

    # For double-faced cards, use only the front face name
    if " // " in name:
        name = name.split(" // ")[0].strip()

    # Normalize emblem names - convert both formats to a common form
    # Local: "Domri Rade Emblem" -> "Domri Rade Emblem"
    # Echo: "Emblem - Domri Rade" -> "Domri Rade Emblem"
    emblem_match = re.match(r"^Emblem\s*-\s*(.+)$", name, re.IGNORECASE)
    if emblem_match:
        name = f"{emblem_match.group(1)} Emblem"

    # Remove parenthetical suffixes that indicate treatments/variants
    # This handles: (Retro Frame), (Extended Art), (Borderless), (Showcase),
    # (Full Art), (265), (15/81), etc.
    # Apply patterns repeatedly until no more changes occur
    treatment_patterns = [
        r"\s*\(Retro Frame\)",
        r"\s*\(Extended Art\)",
        r"\s*\(Borderless\)",
        r"\s*\(Borderless Poster\)",
        r"\s*\(Showcase\)",
        r"\s*\(Full Art\)",
        r"\s*\(Foil Etched\)",
        r"\s*\(Etched\)",
        r"\s*\(Serialized\)",
        r"\s*\(Surge Foil\)",
        r"\s*\(Galaxy Foil\)",
        r"\s*\(Textured Foil\)",
        r"\s*\(Flavor Text\)",
        r"\s*\(Phyrexian\)",
        r"\s*\(0*\d+\)",  # (265), (0280), (015) for basic lands (anywhere in string)
        r"\s*\(\d+/\d+\)",  # (15/81) for art cards
        r"\s*- JP Full Art",  # Japanese full art suffix
        r"\s*Art Card.*$",  # Art Card variants
        r"\s*\(Gold-Stamped.*\)",  # Gold-stamped signatures
        r"\s+Token$",  # Token suffix (e.g., "Citizen Token" -> "Citizen")
        # Basic land art variants - remove parenthetical art names
        r"\s*\([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\)",  # (River), (White Sky), (Ant Hill), etc.
    ]

    # Apply patterns repeatedly until name stabilizes
    prev_name = None
    while prev_name != name:
        prev_name = name
        for pattern in treatment_patterns:
            name = re.sub(pattern, "", name, flags=re.IGNORECASE)
        name = name.strip()

    return name


def create_card_key(row: pd.Series) -> str:
    """Create a unique key for matching cards between inventories.

    Key format: set_code|collector_number|R/F
    - Set code + collector number uniquely identifies a card (for most sets)
    - For PLIST (The List), collector numbers are inconsistent across sources,
      so we match on name only (ignoring collector number)
    - Collector numbers are normalized (leading zeros stripped)
    - R = Regular card (Reg Qty > 0), F = Foil card (Foil Qty > 0)
    """
    set_code = str(row.get("Set Code", "")).upper()

    # Determine if foil or regular based on quantities
    foil_qty = float(row.get("Foil Qty", 0) or 0)
    is_foil = "F" if foil_qty > 0 else "R"

    # PLIST (The List) has inconsistent collector numbers across sources
    # Match on name only for this set
    if set_code == "PLIST":
        name = normalize_card_name(str(row.get("Name", "")))
        return f"{name}|{set_code}|{is_foil}"

    # Normalize collector number - strip leading zeros
    collector_num = str(row.get("Collector Number", "")).lstrip("0") or "0"

    return f"{set_code}|{collector_num}|{is_foil}"


def merge_inventories(
    local_df: pd.DataFrame,
    echo_df: pd.DataFrame,
) -> MergeResult:
    """Merge local inventory (has locations) with EchoMTG export (has IDs).

    Matching Strategy:
    1. Group both DataFrames by card_key
    2. For each matched key, pair rows 1:1 (local row gets echo_inventory_id)
    3. Track unmatched rows from both sides

    Args:
        local_df: Local inventory with location notes
        echo_df: EchoMTG export with echo_inventory_id values

    Returns:
        MergeResult containing merged, unmatched_local, and unmatched_echo DataFrames
    """
    # Add card_key to both DataFrames
    local_df = local_df.copy()
    echo_df = echo_df.copy()
    local_df["card_key"] = local_df.apply(create_card_key, axis=1)
    echo_df["card_key"] = echo_df.apply(create_card_key, axis=1)

    # Group by card_key
    local_groups = dict(list(local_df.groupby("card_key")))
    echo_groups = dict(list(echo_df.groupby("card_key")))

    merged_rows = []
    unmatched_local = []
    unmatched_echo = []

    # Process each local card_key
    for key, local_group in local_groups.items():
        if key in echo_groups:
            echo_group = echo_groups[key]
            local_rows = list(local_group.iterrows())
            echo_rows = list(echo_group.iterrows())

            # Pair rows 1:1
            for i, (_, local_row) in enumerate(local_rows):
                if i < len(echo_rows):
                    _, echo_row = echo_rows[i]
                    merged_row = local_row.copy()
                    merged_row["echo_inventory_id"] = echo_row["echo_inventory_id"]
                    merged_row["tcgid"] = echo_row.get("tcgid", "")
                    merged_row["echoid"] = echo_row.get("echoid", "")
                    merged_rows.append(merged_row)
                else:
                    # More local rows than echo rows
                    unmatched_local.append(local_row)

            # Track excess echo rows (to be removed as duplicates)
            if len(echo_rows) > len(local_rows):
                for j in range(len(local_rows), len(echo_rows)):
                    _, echo_row = echo_rows[j]
                    unmatched_echo.append(echo_row)
        else:
            # Local cards not in EchoMTG
            for _, row in local_group.iterrows():
                unmatched_local.append(row)

    # Track echo cards not in local inventory
    for key in echo_groups:
        if key not in local_groups:
            for _, row in echo_groups[key].iterrows():
                unmatched_echo.append(row)

    return MergeResult(
        merged=pd.DataFrame(merged_rows) if merged_rows else pd.DataFrame(),
        unmatched_local=pd.DataFrame(unmatched_local) if unmatched_local else pd.DataFrame(),
        unmatched_echo=pd.DataFrame(unmatched_echo) if unmatched_echo else pd.DataFrame(),
    )


def deduplicate_inventory(merged_df: pd.DataFrame) -> List[DeduplicatedCard]:
    """Consolidate duplicate rows into single records.

    For rows with the same card_key:
    - Sum Reg Qty and Foil Qty
    - Concatenate all location notes
    - Keep first echo_inventory_id as primary
    - Track remaining echo_inventory_ids as duplicates (to be removed)

    Args:
        merged_df: DataFrame from merge_inventories with card_key column

    Returns:
        List of DeduplicatedCard objects
    """
    if merged_df.empty:
        return []

    deduplicated = []

    for card_key, group in merged_df.groupby("card_key"):
        rows = list(group.to_dict("records"))

        # Sum quantities
        total_reg = sum(int(float(r.get("Reg Qty", 0) or 0)) for r in rows)
        total_foil = sum(int(float(r.get("Foil Qty", 0) or 0)) for r in rows)

        # Collect all non-empty location notes
        locations = [
            r.get("note", "").strip()
            for r in rows
            if r.get("note", "").strip()
        ]

        # Get echo_inventory_ids
        echo_ids = [
            r.get("echo_inventory_id", "")
            for r in rows
            if r.get("echo_inventory_id", "")
        ]
        primary_id = echo_ids[0] if echo_ids else ""
        duplicate_ids = echo_ids[1:] if len(echo_ids) > 1 else []

        # Use first row for other fields
        first = rows[0]

        deduplicated.append(DeduplicatedCard(
            card_key=card_key,
            name=first.get("Name", ""),
            set_name=first.get("Set", ""),
            set_code=first.get("Set Code", ""),
            collector_number=first.get("Collector Number", ""),
            is_foil=total_foil > 0,
            condition=first.get("Condition", "NM"),
            language=first.get("Language", "EN"),
            reg_qty=total_reg,
            foil_qty=total_foil,
            locations=locations,
            primary_echo_id=primary_id,
            duplicate_echo_ids=duplicate_ids,
            tcgid=first.get("tcgid", ""),
            echoid=first.get("echoid", ""),
        ))

    return deduplicated
