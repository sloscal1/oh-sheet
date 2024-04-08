# suggest

Suggest is a simple web UI to track your Magic the Gathering inventory using a local json file. The
UI is optimized for fast manual entry, where you can enter things like: "TYE" and see "Thousand-Year Elixer" show up in its various printings. If there are fewer than 10 potential matches for an entry, then images will be loaded which can help narrow down the field (especially useful for older lands without collector numbers printed on them!). Otherwise, additional filters can be set (expansion set name, finish, promotion type, etc.) so that fewer potential names match -- further speeding up entry.

Inventory can be selected in a few different ways:
* Pressing "Enter" will select the highlighted row, or the first row if nothing is selected.
* Arrow keys can be used to select a visible row.
* A row can be clicked.
* An image (if any are visible) can be clicked.

Images will have silver borders for foil and gold for etched foil finishes.

Undoing a selection is as simple as clicking on the offending row in the inventory table at the bottom of the page. Once your inventory is all set you can save it to a file (inventory_mtg.json). Next time you want to add more cards you can load the file from the UI and pick up where you left off.

The data itself comes from [scryfall](scryfall.com) (an awesome website) using their bulk data. The id values used in the json data will have an extra -n, -f, or -e suffix for normal-, foil-, and etched-finish, which is used to uniquely identify cards in the UI. Trimming off the last two characters will result in a scryfall-usable card id.


### Usage

 To view your website locally, enter the base directory of the project and on the terminal type:
```bash
python -m http.server
```
Then open `http://localhost:8000/docs/index.html` in your browser. Any changes you make to the website should be reflected in the page after refreshing.
