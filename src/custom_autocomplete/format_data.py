""" Include any custom transformations needed to clean the fields and entries of the data set.
"""
import argparse
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import yaml

image_maps = {
    "archiveofourown.org": "./imgs/archive_of_our_own.png",
    "open.spotify.com": "./imgs/spotify.png",
    "soundcloud.com": "./imgs/soundcloud.png",
    "archive.org": "./imgs/archive.png",
}

def format_links(raw_link: str) -> str:
    img_link = image_maps[urlparse(raw_link).netloc]
    if not img_link:
        img_link = "./imgs/default.png"
    return f'<a href="{raw_link}"><img src="{img_link}" alt="{Path(img_link).stem}" class="link_icon"></a>'

class DataCleaner:
    def __init__(self) -> None:
        parser = argparse.ArgumentParser(
            prog="dataprep",
            description="Custom data transformations before hosting for autocomplete.",
        )
        parser.add_argument("config_file", help="Path to the yaml configuration file.", default="config.yaml")
        self.args = parser.parse_args()

        with open(self.args.config_file, encoding="utf-8", mode="rt") as config_file:
            self.config = yaml.safe_load(config_file)
    
    def clean(self) -> None:
        (
            pd.read_csv(self.config["raw_data"]["name"], header=0)
            .fillna("")
            .assign(Link=lambda x: x.Link.apply(format_links))
            [self.config["clean_data"]["used_fields"]]
            .to_csv(self.config["clean_data"]["name"], index=False, header=True)
        )


def main() -> None:
    DataCleaner().clean()

if __name__ == "__main__":
    main()
