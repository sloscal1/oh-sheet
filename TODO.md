-- Starting over from scratch
* Using MTGoldfish for storage of inventory
   * I need a way to quickly enter in cards that I have
   * I need to track where those cards are
   * I want to add in entire precons and secret lair drops at once

* Why don't I just use the MTGoldfish interface?
    * The text search is worse than my current app
        * Specifically, I like the first letter of each word
        * And the image fetch when there are few results
        * I also like the ability to limit the search to sets, finishes, etc.
    * I also need to track where in my physical inventory the cards are 
        * Could be boxes, binders, shelves, frames, slabs, etc.
        * These containers should have some kind of dividers
    * Because it's a physical inventory, I also need the ability to get "search plans" when trying to build a deck
        * For example, if I want to build a deck with 4 copies of "Thousand-Year Elixir"
        * I need to know where to look for those cards in my physical inventory
        * This means that the inventory app needs to be able to generate a list of locations for each card in a decklist
        * This could be a simple text output or a more complex UI feature
    