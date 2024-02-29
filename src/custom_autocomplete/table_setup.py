# Copyright (c) 2024 Steven Loscalzo
# Distributed under the terms of the MIT License.
# SPDX-License-Identifier: MIT
"""
Encapsulates any custom logic for specifying the table
that appears on the website.

This file is expected to be loaded by pyscript and
contain a `create_table` function as defined below.
"""
from typing import Any

import panel as pn


def create_table(config: Any) -> pn.widgets.Tabulator:
    """Specify the definition of the website table.

    Args:
        config (Any): The loaded yaml configuration.

    Returns:
        pn.widgets.Tablulator: The table specification used by
        the website.
    """
    return pn.widgets.Tabulator(
        # if there is an index, don't show it
        hidden_columns=["index"],
        pagination="remote",
        page_size=config["website"]["table_entries_per_page"],
        # custom column formatting
        # in this example the field "Link" will be
        # rendered as html in the table instead of a string
        formatters={"Link": {"type": "html"}},
        disabled=True,
    )