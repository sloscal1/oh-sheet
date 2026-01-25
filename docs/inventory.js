// TODO: Show borders around images for finish type
// TODO: Make arrow keys work  DONE
// TODO: Make the order of images line up with table  DONE
// TODO: Handle names like "Blank of the Blank", Ill-Gotten Gains  DONE
// TODO: Enter when < 20 cards takes the first row  DONE
// TODO: Make the position of the entered cards stay stable  DONE
// TODO: Remove cards (keep leave inventory numbers alone) DONE
// TODO: Search filters with blanks  DONE
// TODO: Shift+Enter takes the top row of the active data DONE
// TOOD: Sort order needs to be set  (using arrows) DONE
// TODO: Handle searching around stopwords DONE
// TODO: Add tab for Adding and Movement DONE
// TODO: Movement tab has cards being editable. When this happens we need to check to see if it's going to a new
// place and then we need to track the next Position
// TODO: Inventory needs to update the management table in parallel
// TODO: Movement tab needs current location
// TODO: "Inventory Location" -> "Updated Location Tag"
// TODO: What to do when there are multiples?
// TODO: I need a card condition label  DONE

// API Configuration
const API_BASE = "http://localhost:8000"

let full_data
let possible
let inventory
let manager
let currentLocation = "somewhere"
let currentPosition = 1
let activeRow = -1
let paginationSize = 10
let keepers = []
let entered = false
let imgTimeout = 5000
let dneBlob


function customCNHeaderFilter(headerValue, rowValue, _rowData, _filterParams){
    //headerValue - the value of the header filter element
    //rowValue - the value of the column in this row
    //rowData - the data for the row being filtered
    //filterParams - params object passed to the headerFilterFuncParams property
    if (headerValue.slice(0, 1) === "="){
      return rowValue == headerValue.slice(1)
    }
    else if (headerValue.slice(0, 1) === ">"){
      return rowValue > headerValue.slice(1)
    }
    else if (headerValue.slice(0, 1) === "<"){
      return rowValue < headerValue.slice(1)
    }
    return true
}

async function load_data() {
  // Try to load from API first, fall back to JSON file
  try {
    const response = await fetch(`${API_BASE}/api/cards/all`)
    if (response.ok) {
      full_data = await response.json()
      console.log("Loaded cards from API")
    } else {
      throw new Error("API request failed")
    }
  } catch (error) {
    console.log("API not available, falling back to JSON file:", error.message)
    await fetch("./mtg_possible_20240407_clean.json")
      .then(response => response.json())
      .then(json => {
        full_data = json
      })
  }

  possible = new Tabulator("#table", {
    data: full_data, //assign data to table
    layout: "fitData", //fit columns to width of table (optional)
    pagination: true,
    paginationSize: paginationSize,
    columns: [
      {
        title: "Name",
        field: "name",
        headerFilter: "input",
        // headerFilterFunc:"like",
        width: "250",
        headerFilterFunc: function (term, label, _value, _item) {
          //replace built in filter function with custom
          //term - the string being searched for
          //label - the text lable for the item
          //value - the value for the item
          //item - the original value object for the item
          const term_parts = term.split(/(?=[A-Z])/)
          const re = RegExp(term_parts.join("[^ -]*[ -]([a-z]*[ -])*?") + "[^ -]*")
          return re.test(label)
        }
      },
      {
        title: "Set",
        field: "set"
      },
      { title: "Lang", field: "lang" },
      { title: "Finishes", field: "finishes" },
      { title: "Promo", field: "promo" },
      { title: "Border Color", field: "border_color" },
      { title: "Promo Types", field: "promo_types" },
      { title: "Full Art", field: "full_art" },
      {
        title: "Collector Number",
        field: "collector_number",
        headerFilter: "input",
        headerFilterFunc: customCNHeaderFilter,
      },
    ],
    columnDefaults: {
      headerFilter: "list",
      headerFilterFunc: "=",
      headerFilterParams: {
        valuesLookup: "active",
        sort: "asc",
        clearable: true,
        multiselect: false,
        autocomplete: false
      }
    },
    selectableRows:1,
    selectableRows:true,
    selectableRowsRollingSelection:true,
    selectableRowsPersistence:false,
  })
  inventory = new Tabulator("#inventory", {
    data: full_data.slice(0, 1), //assign data to table
    layout: "fitData", //fit columns to width of table (optional)
    pagination: true,
    paginationSize: 10,
    columns: [
      {
        title: "Location",
        field: "location",
        headerFilter: "input",
        headerFilterFunc: "like"
      },
      { title: "Id", field: "id"},
      { title: "Position", field: "pos" },
      {
        title: "Name",
        field: "name",
        headerFilter: "input",
        // headerFilterFunc:"like",
        width: "250"
      },
      {
        title: "Set",
        field: "set"
      },
      { title: "Lang", field: "lang" },
      { title: "Finishes", field: "finishes" },
      { title: "Promo", field: "promo" },
      { title: "Border Color", field: "border_color" },
      { title: "Promo Types", field: "promo_types" },
      { title: "Full Art", field: "full_art" },
      {
        title: "Collector Number",
        field: "collector_number",
        headerFilter: "input",
        headerFilterFunc: "like"
      },
      {
        title: "Condition",
        field: "condition",
        headerFilter: "input",
        validator: ["required", "in:near mint|lightly played|played|heavily played|damaged"],
        editable: true,
      }
    ],
    downloadRowRange: "all"
  })
  manager = new Tabulator("#manager", {
    data: full_data.slice(0, 1), //assign data to table
    layout: "fitData", //fit columns to width of table (optional)
    pagination: true,
    paginationSize: 100,
    columns: [
      {
        title: "Location",
        field: "location",
        headerFilter: "input",
        headerFilterFunc: "like"
      },
      { title: "Id", field: "id"},
      { title: "Position", field: "pos" },
      {
        title: "Name",
        field: "name",
        headerFilter: "input",
        // headerFilterFunc:"like",
        width: "250"
      },
      {
        title: "Set",
        field: "set"
      },
      { title: "Lang", field: "lang" },
      { title: "Finishes", field: "finishes" },
      { title: "Promo", field: "promo" },
      { title: "Border Color", field: "border_color" },
      { title: "Promo Types", field: "promo_types" },
      { title: "Full Art", field: "full_art" },
      {
        title: "Collector Number",
        field: "collector_number",
        headerFilter: "input",
        headerFilterFunc: "like"
      },
      {
        title: "Condition",
        field: "condition",
        headerFilter: "input",
        validator: ["required", "in:near mint|lightly played|played|heavily played|damaged"],
        editable: true,
      }
    ],
    downloadRowRange: "all"
  })
  possible.on("rowClick", addToInventory)
  inventory.on("tableBuilt", finalLoad)
  manager.on("tableBuilt", inventoryFinalLoad)
  inventory.on("rowClick", removeFromInventory)
  const loc = document.getElementById("location")
  loc.addEventListener("keyup", async event => {
    currentLocation = event.target.value
    // Auto-collapse toolbar once location is set
    if (currentLocation.length > 0) {
      collapseToolbar()
      saveLocationToCookie()
    }
    // Try to get next position from API
    try {
      const response = await fetch(`${API_BASE}/api/inventory/next-position?location=${encodeURIComponent(currentLocation)}`)
      if (response.ok) {
        const data = await response.json()
        currentPosition = data.next_position
        return
      }
    } catch (error) {
      // Fall back to local calculation
    }
    let matched = inventory.searchData("location", "=", currentLocation)
    currentPosition = 1
    if (matched.length !== 0) {
      currentPosition =
        matched.sort((a, b) => {
          a.pos > b.pos
        })[0].pos + 1
    }
  })
  document.getElementById("myfile").addEventListener("change", event => {
    parse_json(event).then(new_data => {
      inventory.setData(new_data)
      manager.setData(new_data)
      currentLocation = new_data[0]["location"]
      document.getElementById("location").value = currentLocation
      currentPosition = new_data[0]["pos"] + 1
      dest = document.getElementById("destination")

      const values = new Set([])
      for(const row of new_data)
        values.add(row["location"])

      const options = [...values]
      options.sort()
      for (var i = 0; i <= options.length; i++){
        var opt = document.createElement('option');
        opt.value = i;
        opt.innerHTML = options[i];
        dest.appendChild(opt);
      }
      updateInventoryCount()
      collapseToolbar()
    })
  })
  document.addEventListener("keydown", event => {
    if (event.key === "Enter"){
      entered = true
      event.stopImmediatePropagation()
    }
  })
  document.addEventListener("keyup", event => {
    if (event.key === "Enter"){
      event.stopImmediatePropagation()
      if (possible.getSelectedData().length > 0){
        _addToInventory(possible.getSelectedData()[0])
      }
      else if (isNameFocused()){
        event.stopPropagation()
        addToInventory(null, possible.getRows("visible")[0])
      }
      entered = false
    }
    else if (event.key === "ArrowDown" || event.key === "ArrowUp"){
      possible.deselectRow()
      let change = 1
      if (event.key === "ArrowUp")
        change = -1
      activeRow = (activeRow + change) % paginationSize
      if (activeRow < 0)
        activeRow += paginationSize
      const new_id = possible.getData("visible")[activeRow].id
      possible.selectRow(new_id)
    }
  })
}

function isNameFocused(){
    let retval = false
    let active = document.activeElement
    if (active.parentElement !== null && active.parentElement.parentElement !== null){
      active = active.parentElement.parentElement
      retval = active.children[0].children[0].innerText == "Name"
    }
    return retval
}

async function parse_json (event) {
  return new Promise((resolve, reject) => {
    const fileReader = new FileReader()
    fileReader.onload = event => {
      resolve(JSON.parse(event.target.result))
    }
    fileReader.onerror = error => reject(error)
    fileReader.readAsText(event.target.files[0])
  })
}

async function onDataFiltered(_filters, rows){
    const imgDiv = document.getElementById("images")
    imgDiv.innerText = ""
    if (rows.length <= 10 && rows.length > 1){
      for (const row of rows){
        let resp = await downloadImage(row._row.data)
        imgDiv.append(resp)
      }
    }
}
async function finalLoad (_event) {
  possible.on("dataFiltered", await onDataFiltered)
  possible.on("pageLoaded", _pageno => activeRow = -1)
  possible.setHeaderFilterFocus("name")

  // Try to load inventory from API
  try {
    const response = await fetch(`${API_BASE}/api/inventory/export`)
    if (response.ok) {
      const inventoryData = await response.json()
      if (inventoryData.length > 0) {
        inventory.setData(inventoryData)
        manager.setData(inventoryData)
        currentLocation = inventoryData[0]["location"]
        document.getElementById("location").value = currentLocation
        currentPosition = inventoryData[0]["pos"] + 1

        // Populate destination dropdown
        const dest = document.getElementById("destination")
        const values = new Set([])
        for (const row of inventoryData) {
          values.add(row["location"])
        }
        const options = [...values]
        options.sort()
        for (var i = 0; i <= options.length; i++) {
          var opt = document.createElement('option');
          opt.value = i;
          opt.innerHTML = options[i];
          dest.appendChild(opt);
        }
        console.log("Loaded inventory from API")
        updateInventoryCount()
        collapseToolbar()
      } else {
        inventory.setData([])
      }
    } else {
      throw new Error("API request failed")
    }
  } catch (error) {
    console.log("Could not load inventory from API:", error.message)
    inventory.setData([])
  }

  updateInventoryCount()
  inventory.hideColumn("id")
  // inventory.on("dataChanged", _data => {possible.refreshFilter()})
  const dneData = await fetch("./dne.png")
  dneBlob = await dneData.blob()

  // Load saved location from cookie if no inventory was loaded
  if (inventory.getData().length === 0) {
    await loadLocationFromCookie()
  }
}

async function inventoryFinalLoad (_event) {
  manager.setData([])
  manager.hideColumn("id")
}

async function _addToInventory (rowData) {
  let new_data = {...rowData}  // Create a copy to avoid mutating original
  new_data["location"] = currentLocation
  new_data["pos"] = currentPosition
  new_data["condition"] = document.getElementById("condition").value

  // Try to add to API
  try {
    const response = await fetch(`${API_BASE}/api/inventory`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        card_id: rowData.id,
        location: currentLocation,
        position: currentPosition,
        condition: new_data["condition"]
      })
    })
    if (response.ok) {
      const savedItem = await response.json()
      // Update the data with the server-generated ID for tracking
      new_data._inventory_id = savedItem.id
      console.log("Added to inventory via API")
    } else {
      console.log("API add failed, adding locally only")
    }
  } catch (error) {
    console.log("Could not add to API, adding locally:", error.message)
  }

  currentPosition += 1
  inventory.addRow(new_data, true)
  updateInventoryCount()
  activeRow = -1
  possible.deselectRow()
  const img_div = document.getElementById("images")
  img_div.innerText = ""
  possible.setHeaderFilterValue("name", undefined)
  possible.setHeaderFilterFocus("name")
}

function addToInventory (_event, row) {
  if (row !== undefined && row.getData() !== undefined) {
    _addToInventory(row.getData())
  }
}

async function removeFromInventory (_event, row) {
  if (row !== undefined && row.getData() !== undefined) {
    const rowData = row.getData()

    // Try to remove from API
    try {
      // Use the inventory ID if available, otherwise use card_id with location/position
      let url
      if (rowData._inventory_id) {
        url = `${API_BASE}/api/inventory/${rowData._inventory_id}`
      } else {
        url = `${API_BASE}/api/inventory/by-card/${encodeURIComponent(rowData.id)}?location=${encodeURIComponent(rowData.location)}&position=${rowData.pos}`
      }

      const response = await fetch(url, { method: "DELETE" })
      if (response.ok) {
        console.log("Removed from inventory via API")
      } else {
        console.log("API remove failed")
      }
    } catch (error) {
      console.log("Could not remove from API:", error.message)
    }

    row.delete()
    updateInventoryCount()
  }
}

async function saveInventory (_event) {
  inventory.showColumn("id")
  inventory.download("json", "inventory_mtg.json")
  inventory.hideColumn("id")
}

async function loadInventoryFromAPI() {
  try {
    const response = await fetch(`${API_BASE}/api/inventory/export`)
    if (response.ok) {
      const inventoryData = await response.json()
      inventory.setData(inventoryData)
      manager.setData(inventoryData)
      if (inventoryData.length > 0) {
        currentLocation = inventoryData[0]["location"]
        document.getElementById("location").value = currentLocation
        currentPosition = inventoryData[0]["pos"] + 1
      }
      console.log("Reloaded inventory from API")
    }
  } catch (error) {
    console.log("Could not reload inventory from API:", error.message)
  }
}

async function fetchImage (card_id, version = "small") {
  const url = `https://api.scryfall.com/cards/${card_id}?format=image&version=${version}`
  let blob = dneBlob
  try{
    const response = await fetch(url, { signal: AbortSignal.timeout(imgTimeout) })
    blob = await response.blob()
  }
  catch{
    console.log("Missing img: " + card_id)
  }
  return blob
}

async function downloadImage (data, version = "small") {
  await new Promise(r => setTimeout(r, 50)) // Per Scryfall guidelines
  const imageBlob = await fetchImage(data.id.slice(0, -2), version)
  const imageBase64 = URL.createObjectURL(imageBlob)
  const new_el = document.createElement("img")
  new_el.src = imageBase64
  const cardType = data.id.slice(-1)
  let className = "normal-finish"
  if (cardType === "f")
    className = "foil-finish"
  else if (cardType == "e")
    className = "etched-finish"
  new_el.className = className
  const setDisplay = data.set_name ? `${data.set_name} (${data.set})` : data.set
  new_el.title = `Set: ${setDisplay} | Finish: ${data.finishes} | #${data.collector_number}`
  new_el.setAttribute("data", JSON.stringify(data))
  new_el.addEventListener("click", event => {
    _addToInventory(JSON.parse(event.target.getAttribute("data")))
  })
  return new_el
}

function showTab(tabName){
  tabs = [...document.getElementsByClassName("tab_section")]
  for (const tab of tabs){
    tab.style.display = "none"
  }
  document.getElementById(tabName).style.display = "flex"

  // Update active button state
  const buttons = document.querySelectorAll('.w3-bar-item.w3-button')
  buttons.forEach(btn => btn.classList.remove('active'))
  event.target.classList.add('active')
}

function toggleInventoryPanel() {
  const panel = document.getElementById('inventory-panel')
  const overlay = document.getElementById('panel-overlay')
  panel.classList.toggle('open')
  overlay.classList.toggle('open')
}

function updateInventoryCount() {
  const countEl = document.getElementById('inventory-count')
  if (countEl && inventory) {
    const count = inventory.getData().length
    countEl.textContent = count
  }
}

function collapseToolbar() {
  const wrapper = document.getElementById('toolbar-wrapper')
  if (wrapper && !wrapper.classList.contains('collapsed')) {
    wrapper.classList.add('collapsed')
  }
}

function expandToolbar() {
  const wrapper = document.getElementById('toolbar-wrapper')
  if (wrapper) {
    wrapper.classList.remove('collapsed')
  }
}

// Cookie utilities
function setCookie(name, value, days = 365) {
  const expires = new Date(Date.now() + days * 864e5).toUTCString()
  document.cookie = `${name}=${encodeURIComponent(value)}; expires=${expires}; path=/; SameSite=Strict`
}

function getCookie(name) {
  const cookies = document.cookie.split('; ')
  for (const cookie of cookies) {
    const [key, val] = cookie.split('=')
    if (key === name) {
      return decodeURIComponent(val)
    }
  }
  return null
}

function saveLocationToCookie() {
  if (currentLocation) {
    setCookie('mtg_inventory_location', currentLocation)
  }
}

function exportDeckbox() {
  window.location.href = `${API_BASE}/api/inventory/export/deckbox`
}

function exportMtggoldfish() {
  window.location.href = `${API_BASE}/api/inventory/export/mtggoldfish`
}

async function loadLocationFromCookie() {
  const savedLocation = getCookie('mtg_inventory_location')
  if (savedLocation) {
    currentLocation = savedLocation
    document.getElementById('location').value = savedLocation

    // Try to get next position from API
    try {
      const response = await fetch(`${API_BASE}/api/inventory/next-position?location=${encodeURIComponent(currentLocation)}`)
      if (response.ok) {
        const data = await response.json()
        currentPosition = data.next_position
        return
      }
    } catch (error) {
      // Fall back to local calculation
    }

    // Local fallback
    if (inventory) {
      let matched = inventory.searchData("location", "=", currentLocation)
      currentPosition = 1
      if (matched.length !== 0) {
        currentPosition = matched.sort((a, b) => a.pos > b.pos)[0].pos + 1
      }
    }

    collapseToolbar()
  }
}
