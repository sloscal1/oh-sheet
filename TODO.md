-- Browser Extension for echomtg.com

 Here's the idea: It's a front-end to the echomtg.com website that facilitates faster inventory input. Users have a lot of cards, let's say 100 or more, that they want to add to their inventory. They're often from a limited collection of "sets", and have other options.

1. The users do some setup to select which sets they are working with, and other card options, like foil/etched/promo. This triggers caching the possible card info in the background.
2. The user specifies a tag for where the cards will be physically stored (like b5r1 for box 5 row 1), and a position offset.
3. The user then flips through a stack of cards, and types in parts of the name. A list of potential matches is quickly populated in the UI and the user can select the correct match.
4. The match triggers an API call to add the new card to the website inventory, and then another API call to store the location as a note.
5. The next open location is persisted between runs of the application so the user can start adding cards to where they just were.
---

## Overall shape of the extension

You’d probably build this as:

* A **content script** injected into `echomtg.com` pages
  → Handles the in-page UI overlay and any DOM interaction.
* A **background/service worker** (Manifest V3)
  → Handles API calls, caching, and persisting state.
* Optional **side panel / popup**
  → For settings/setup, if you don’t want to clutter the main page.

---

## 1. Setup & caching card data

> The users do some setup to select which sets they are working with, and other card options. This triggers caching the possible card info in the background.

**How it might look:**

* In your extension UI (popup, side panel, or an overlay on the EchoMTG page), user:

  * Chooses sets
  * Chooses options (foil / etched / promo, etc.)
  * The options are words that most often come from terms in parentheses in card titles on EchoMTG.

* Your **background script**:

  * Calls the appropriate EchoMTG API endpoints (or the site’s own APIs) to fetch card metadata for those sets
  * Stores them using:
    * IndexedDB (if you want more control / larger datasets)
    * I also want to create normalized indexes based on the first letter of the card name for faster searching later.

**Constraints / considerations:**

* **Authentication**
  You need some way to be authenticated to EchoMTG:

  * Use their *official API* & user-provided token/key, or
  * Piggyback on the existing session cookies if you call their website APIs (this can work from a content script or background script with appropriate permissions).
* **ToS / rate limits**
  Make sure EchoMTG is okay with this and that you respect their API rate limits.

---

## 2. Tag + position offset

> The user specifies a tag for where the cards will be stored and a position offset.


You’d provide a small form in your overlay/popup UI:

* Fields: `locationTag` (e.g., `b5r1`), `offset` (integer)
* Save to `storage.local` so it persists:

  * Per user
  * Optionally per set or per “session”
  * This might be another storage value in the IndexedDB.

---

## 3. Fast fuzzy search on card names

> User flips through cards, types parts of the name, list of matches updates quickly, user selects correct match.

Mechanics:

* The card metadata you cached in step 1 is stored locally in the IndexedDB.
* When the user types, you:

  * Use a fuzzy search library in the content script (e.g., Fuse.js) over the cached list (might not need fuzzy search if IndexedDB + normalized keys is performant)
  * Render a dropdown/list overlayed on the page
* For each keypress:

  * Filter the cached list
  * Show top N results
* The UI is just HTML/CSS in a **content script injected into the page**, so it can “share the screen” with the actual EchoMTG site.

---

## 4. API calls for add-to-inventory + location note

> Match triggers an API call to add the card to inventory, then another to store the location as a note.


* Background script or content script does:

  ```js
  fetch("https://api.echomtg.com/...", {
    method: "POST",
    headers: { Authorization: "Bearer <user-token>", "Content-Type": "application/json" },
    body: JSON.stringify({ card_id, ...options })
  });
  ```
* Token is stored in extension storage (with user consent).
* You probably:

  * Add the card to inventory
  * Then call another endpoint to annotate location, or
  * One call that includes the location note (if API supports it)

You’ll grant the extension permission to talk to `https://api.echomtg.com/` via `host_permissions` in `manifest.json`. That also largely sidesteps CORS issues because the extension is allowed to talk directly to that origin.

---

## 5. Persisting the “next open location” between runs

> The next open location is persisted between runs so they can continue where they left off.


You can store anything like:

```js
chrome.storage.local.set({
  nextLocation: {
    tag: "b5r1",
    index: 37,
    updatedAt: Date.now()
  }
});
```

On startup / page load, your content script or background service worker:

```js
chrome.storage.local.get("nextLocation", (res) => {
  // Use res.nextLocation to prefill fields
});
```

Although I would prefer to store them in the IndexedDB along with other cached data for easier management.


## Practical architecture sketch

If you want a concrete structure, something like:

* **manifest.json**

  * `host_permissions`: `["https://echomtg.com/*", "https://api.echomtg.com/*"]`
  * `permissions`: `["storage", "scripting", "activeTab"]`
  * content script: on `echomtg.com/*`
  * service worker (background)

* **content script**

  * Injects UI overlay into the inventory page
  * Handles:

    * Card name input
    * Fuzzy search results display
    * Arrow key / enter navigation
    * Simple state: currently selected set, foil flag, etc.
  * Communicates with background via `chrome.runtime.sendMessage` for:

    * Fetching cached card lists
    * Triggering “add card” actions

* **background (service worker)**

  * On setup:

    * Fetch & cache card metadata (by set)
  * On “add card” message:

    * Call EchoMTG API to add card
    * Call API to store note/location
    * Update `nextLocation` and store in `storage.local`

* **options page or popup**

  * For:

    * Entering API token (if needed)
    * Choosing default sets / preferences

---
