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
        self.table_entries_per_page = self.config["website"]["table_entries_per_page"]
        self.autocomplete_max_length = self.config["website"]["autocomplete_max_length"]

        self.dropdown_selected = -1
        self.autocompletes: Dict[str, Trie] = {} 
        search_boxes = pydom["#autocompletes"][0]
        for field in self.config["clean_data"]["used_fields"]:
            if field not in self.config["clean_data"]["no_filter_fields"]:
                self._create_ac_from_field(field)
                new_form = search_boxes.create("form", classes=["result_form"])
                new_form.id = f"form{field}"
                new_form._js.autocomplete = "off"
                new_form._js.addEventListener("submit", create_proxy(self.form_submit))
                new_box = new_form.create("input", classes=["result_input"])
                new_box.id = field
                new_box._js.placeholder = field
                new_box.type = "text"
                new_box._js.addEventListener("keyup", create_proxy(self.suggest))
                new_box._js.addEventListener("focus", create_proxy(self._clear_dropdowns))
                # new_box._js.addEventListener("blur", create_proxy(close_dropdowns))
                new_div = new_form.create("div", classes=["result"])
                new_div.id = f"result{field}"

        # Set up the main data table
        self.table = create_table(self.config).servable(target="table")
        self.current_data = self.full_data.copy()
        self.table.value = self.current_data

        # Add other control flow actions
        document.addEventListener("keyup", create_proxy(self.close_dropdowns))
    
    def _filter_on(self, selected: str, field) -> None:
        print(field)
        pydom[f"#{field}"][0].value = selected
        pydom[f"#result{field}"][0].html = ""
        self._update_table_filters()
    
    def form_submit(self, event) -> None:
        event.preventDefault()
        field = event.target.id[len('form'):]
        list_elements = pydom[f".{field}"]
        if list_elements:
            selected = 0
            if self.dropdown_selected >= 0:
                selected = self.dropdown_selected
                self.dropdown_selected = -1
            self._filter_on(list_elements[selected].content, field)

    def filter_on(self, event) -> None:
        event.preventDefault()
        selected = event.target.innerText
        selected_field = event.target.classList.item(1)
        self._filter_on(selected, selected_field)
    
    def _update_table_filters(self) -> None:
        self.current_data = self.full_data
        for field in pydom[".result_input"]:
            if field.value:
                self.current_data = self.current_data[self.current_data[f"{field.id}"].str.startswith(field.value)]  # type: ignore
        self.table.value = self.current_data  # type: ignore

    def suggest(self, event) -> None:
        event.preventDefault()
        print(event.code)
        if event.isComposing or event.keyCode == 229:
            return
        if event.code == "Enter" or event.code == "Tab":
            self.dropdown_selected = -1
            return
        direction = 1
        if event.code == "ArrowUp":
            direction = -1
        if event.code in ["ArrowUp", "ArrowDown"]:
            choices = pydom[f".{event.target.id}"]
            if choices:
                if self.dropdown_selected >= 0:
                    pydom[f"#dropdown_{self.dropdown_selected}"][0].remove_class("highlight")
                    self.dropdown_selected = (self.dropdown_selected + direction) % len(choices)
                else:
                    self.dropdown_selected = 0 if direction == 1 else len(choices) - 1
                pydom[f"#dropdown_{self.dropdown_selected}"][0].add_class("highlight")
                pydom[f"#{event.target.id}"].value = pydom[f".{event.target.id}"][self.dropdown_selected].content
            return
        entered = event.target.value
        if entered:
            results = self.autocompletes[event.target.id].match(entered, case_sensitive=False)
            if results:
                divs = pydom[f"#result{event.target.id}"]
                if divs is not None:
                    result_div = divs[0]
                    result_div.html = ""
                    result_list = result_div.create("ul")
                    for pos, response in enumerate(results[:self.table_entries_per_page]):
                        list_element = result_list.create("li", html=response[:self.autocomplete_max_length])
                        list_element.add_class("selectable")
                        list_element.add_class(event.target.id)
                        list_element.id = f"dropdown_{pos}"
                    elements = pydom[".selectable"]
                    for element in elements:
                        element._js.addEventListener("click", create_proxy(self.filter_on))
            else:
                self._clear_dropdowns()
        else:
            self._clear_dropdowns()
            self._update_table_filters()

    def _clear_dropdowns(self, _ = None):
        elements = pydom[".result"]
        for element in elements:
            element.html = ""

    def close_dropdowns(self, event):
        event.preventDefault()
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
