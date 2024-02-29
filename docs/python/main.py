# Copyright (c) 2024 Steven Loscalzo
# Distributed under the terms of the MIT License.
# SPDX-License-Identifier: MIT
""" This code powers the dynamic aspects of the filter table webpage.

This could should not need to be modified by downstream applications,
instead the table_setup and config.yaml files should be sufficient to customize
most behaviors.

This code is meant to be run through pyscript in the browswer.
"""
from typing import Dict

import pandas as pd
import panel as pn
import yaml
from pyodide.ffi import create_proxy
from pyscript import document
from pyweb import pydom
from table_setup import create_table
from trie import Trie


class AutocompleteTable:
    """ Generic table with autocomplete fields for filtering.
    
    Attributes:
        autocompletes:  Must have a div with id "autocompletes" in source html to house the filter inputs
        full_data:   The cleaned data read in from the virtual file system
        current_data:  The data subset currently visible in the table
        config:  The config info from config.yaml
        table:  The table object that gets dynamically updated by the filters
    """
    def __init__(self) -> None:
        """ Setup necessary datastructures when the file is loaded. """

        with open("./config.yaml", encoding="utf-8", mode="rt") as config_file:
            self.config = yaml.safe_load(config_file)
        self.full_data = pd.read_csv(self.config["website"]["data"]).fillna("")

        self.autocompletes: Dict[str, Trie] = {} 
        search_boxes = pydom["#autocompletes"][0]
        for field in self.config["clean_data"]["used_fields"]:
            if field not in self.config["clean_data"]["no_filter_fields"]:
                self._create_ac_from_field(field)
                new_form = search_boxes.create("form", classes=["result_form"])
                new_form._js.autocomplete = "off"
                new_box = new_form.create("input", classes=["result_input"])
                new_box.id = field
                new_box._js.placeholder = field
                new_box.type = "text"
                new_box._js.addEventListener("keyup", create_proxy(self.suggest))
                # new_box._js.addEventListener("blur", create_proxy(close_dropdowns))
                new_div = new_form.create("div", classes=["result"])
                new_div.id = f"result{field}"

        # Set up the main data table
        self.table = create_table(self.config).servable(target="table")
        self.current_data = self.full_data.copy()
        self.table.value = self.current_data

        # Add other control flow actions
        document.addEventListener("keyup", create_proxy(self.close_dropdowns))
        print(pd.__version__)

    def filter_on(self, event) -> None:
        selected = event.target.innerText
        print(event.target.classList.item(1))
        selected_field = event.target.classList.item(1)
        pydom[f"#{selected_field}"][0].value = selected
        pydom[f"#result{selected_field}"][0].html = ""
        self.current_data = self.current_data[lambda x: x[f"{selected_field}"].str.startswith(selected)]  # type: ignore
        self.table.value = self.current_data

    def suggest(self, event) -> None:
        if event.isComposing or event.keyCode == 229:
            return
        # if not event.code.startswith("Key"):  # TODO this is too specific;
        #     return
        entered = event.target.value
        if entered:
            results = self.autocompletes[event.target.id].match(entered, case_sensitive=False)
            if results:
                divs = pydom[f"#result{event.target.id}"]
                if divs is not None:
                    result_div = divs[0]
                    result_div.html = ""
                    result_list = result_div.create("ul")
                    for response in results[:10]:
                        result_list.create("li", html=response[:self.config["website"]["autocomplete_max_length"]], classes=["selectable", event.target.id])
                    elements = pydom[".selectable"]
                    for element in elements:
                        print(element.html)
                        element._js.addEventListener("click", create_proxy(self.filter_on))
        else:
            result_div = pydom["#result"]
            if result_div:
                result_div = result_div[0]
                result_div.html = ""
            self.table.value = self.full_data  # type: ignore
            self.current_data = self.full_data

    def close_dropdowns(self, event):
        if event.code == "Escape":
            elements = pydom[".result"]
            for element in elements:
                element.html = ""

    def _create_ac_from_field(self, field: str) -> None:
        ac = Trie()
        for entry in self.full_data[field]:
            cleaned_entry = entry.strip()
            if cleaned_entry:
                ac.insert(cleaned_entry)
        self.autocompletes[field] = ac


AutocompleteTable()
