# Copyright (c) 2024 Steven Loscalzo
# Distributed under the terms of the MIT License.
# SPDX-License-Identifier: MIT
""" Include any custom transformations needed to clean the fields and entries of the data set.

This example does a custom transformation on a field "Link" to
get it to be served as HTML.

This class is optional; if your raw.csv data is already
in good shape to host then no cleaning is needed.
"""
import argparse
from pathlib import Path

import pandas as pd
import yaml

# This is used to map a raw.csv field value to an icon
image_maps = {
    "https://www.google.com/search?q=wink": "./imgs/wink.png",
    "https://www.google.com/search?q=smiley": "./imgs/smiley.png",
}

def _format_links(raw_link: str) -> str:
    """Transforms a string URL into a clickable html image.

    Args:
        raw_link (str): a string URL

    Returns:
        str: HTML to display in the completed table.
    """
    img_link = image_maps[raw_link] if raw_link in image_maps else "./imgs/default.png"
    return (
        f'<a href="{raw_link}">'
        f'<img src="{img_link}" alt="{Path(img_link).stem}" class="link_icon">'
        f'</a>'
    )

class DataCleaner:
    """Apply the specific cleaning steps listed in the
    clean method to produce an output csv suitable for hosting.
    """
    def __init__(self) -> None:
        parser = argparse.ArgumentParser(
            prog="dataprep",
            description="Custom data transformations before hosting for autocomplete.",
        )
        parser.add_argument(
            "config_file",
             help="Path to the yaml configuration file.",
            default="config.yaml"
        )
        self.args = parser.parse_args()

        with open(self.args.config_file, encoding="utf-8", mode="rt") as config_file:
            self.config = yaml.safe_load(config_file)

    def clean(self) -> None:
        """ Apply custom transformations to the input csv file here. """
        (
            pd.read_csv(self.config["raw_data"]["name"], header=0)
            .fillna("")
            .assign(Link=lambda x: x.Link.apply(_format_links))
            [self.config["clean_data"]["used_fields"]]
            .to_csv(self.config["clean_data"]["name"], index=False, header=True)
        )


def main() -> None:
    """ ALlow this code to be called from the terminal. """
    DataCleaner().clean()

if __name__ == "__main__":
    main()
