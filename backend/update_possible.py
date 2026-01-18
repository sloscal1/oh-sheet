import argparse
import datetime
import json
from pathlib import Path

import ijson
import pandas

CURRENT = str(datetime.date.today()).replace("-", "")
DATA_DIR = Path(__file__).parent.parent / "data"
DOCS_DIR = Path(__file__).parent.parent / "docs"

USEFUL_COLS = [
    "id",
    "object",
    "lang",
    "layout",
    "name",
    "set",
    "set_name",
    "finishes",
    "promo",
    "border_color",
    "promo_types",
    "collector_number",
    "full_art",
]


def extract_cards(scryfall_path: Path, output_path: Path):
    """Extract card objects from Scryfall bulk data file."""
    with open(scryfall_path, "rb") as mtg_cards:
        with open(output_path, "wt", encoding="utf-8") as possible:
            possible.write("[")
            count = 0
            for obj in ijson.items(mtg_cards, "item"):
                if obj["object"] == "card":
                    new_obj = {key: obj[key] for key in USEFUL_COLS if key in obj}
                    if count != 0:
                        possible.write(",")
                    possible.write(json.dumps(new_obj))
                count += 1
                if count % 1000 == 0:
                    print("*", end="", flush=True)
                if count % 80000 == 0:
                    print()
            possible.write("]")
    print()


def filter_and_transform(subset_path: Path, output_path: Path):
    """Filter cards by language/set criteria and transform for output."""
    possible = (
        pandas.read_json(subset_path)[USEFUL_COLS]
        [lambda x: x.object == "card"]
        [lambda x:
            ((x.lang == "ja") & (x.set == "sta"))
            | ((x.lang == "ja") & (x.set == "neo") & (x.full_art))
            | (x.lang == "ph")
            | (x.lang == "en")
        ]
        .explode("promo_types")
        .explode("finishes")
        .explode("border_color")
        .fillna({"promo_types": "--", "finishes": "--", "border_color": "--"})
    )
    print("Read in data")

    art_series = (
        possible[lambda x: (x.layout == "art_series") & (~x.collector_number.str.endswith("s"))]
        .assign(promo_types="")
        .drop_duplicates(subset="id")
    )
    print("Created art series")

    possible = (
        pandas.concat([
            possible[lambda x: x.layout != "art_series"],
            art_series,
            art_series.assign(promo_types="stamped"),
        ])
        .assign(collector_number=lambda x: ("000" + x.collector_number).str.slice(-4))
        .assign(id=lambda x: x.id + "-" + x.finishes.str[0])
    )
    print("Data about to print")

    possible.to_json(output_path, orient="records")


def main():
    parser = argparse.ArgumentParser(description="Process Scryfall MTG card data")
    parser.add_argument(
        "scryfall_file",
        type=Path,
        help="Path to Scryfall all-cards JSON file",
    )
    args = parser.parse_args()

    subset_path = DATA_DIR / f"mtg_possible_{CURRENT}.json"
    output_path = DOCS_DIR / f"mtg_possible_{CURRENT}_clean.json"

    extract_cards(args.scryfall_file, subset_path)
    filter_and_transform(subset_path, output_path)


if __name__ == "__main__":
    main()
