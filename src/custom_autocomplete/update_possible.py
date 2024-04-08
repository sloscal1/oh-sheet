import datetime
import json

import ijson
import pandas

CURRENT = str(datetime.date.today()).replace('-', '')

SCRYFALL_DATA_PATH = "/Users/sloscal1/Downloads/all-cards-20240317211946.json"
SUBSET_DATA_PATH = f"data/mgt_possible_{CURRENT}.json"
JSON_OUTPUT = f"docs/mtg_possible_{CURRENT}_clean.json"

def main():
    useful_cols = [
        "id",
        "object",
        "lang",
        "layout",
        "name",
        "set",
        "finishes",
        "promo",
        "border_color",
        "promo_types",
        "collector_number",
        "full_art",
    ]

    with open(SCRYFALL_DATA_PATH, "rb") as mtg_cards:
        with open(SUBSET_DATA_PATH, "wt", encoding="utf-8") as possible:
            possible.write("[")
            count = 0
            for obj in ijson.items(mtg_cards, "item"):
                if obj["object"] == "card":
                    new_obj = {key: obj[key] for key in useful_cols if key in obj}
                    if count != 0:
                        possible.write(",")
                    possible.write(json.dumps(new_obj))
                count += 1
                if count % 1000 == 0:
                    print("*", end="")
                if count % 80000 == 0:
                    print()
            possible.write("]")

    possible = (
        pandas.read_json(SUBSET_DATA_PATH)
        [useful_cols]
        [lambda x: (x.object == "card")]
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
    print("read in data")
    art_series = (
        possible[lambda x: (x.layout == "art_series") & (~x.collector_number.str.endswith("s"))]
        .assign(promo_types="")
        .drop_duplicates(subset="id")
    )
    print("created art series")
    possible = (
        pandas.concat(
            [
                possible[lambda x: x.layout != "art_series"],  # Non art cards
                art_series,  # Non-stamped art cards
                art_series.assign(promo_types="stamped")  # Stamped art cards
            ]
        )
        .assign(collector_number=lambda x: ("000" + x.collector_number).str.slice(-4))
    )
    possible = possible.assign(
        id=lambda x: x.id + "-" + x.finishes.str[0]
    )
    print("data about to print")

    possible.to_json(JSON_OUTPUT, orient="records")

if __name__ == "__main__":
    main()
