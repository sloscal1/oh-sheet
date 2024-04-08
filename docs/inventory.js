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
let full_data
let possible
let inventory
let currentLocation = "somewhere"
let currentPosition = 1
let activeRow = -1
let paginationSize = 10
let keepers = []
let entered = false

async function load_data () {
  await fetch("./mtg_possible_20240407_clean.json")
    .then(response => response.json())
    .then(json => {
      full_data = json
    })

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
        headerFilterFunc: "like"
      }
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
      }
    ],
    downloadRowRange: "all"
  })
  possible.on("rowClick", addToInventory)
  inventory.on("tableBuilt", finalLoad)
  inventory.on("rowClick", removeFromInventory)
  const loc = document.getElementById("location")
  loc.addEventListener("keyup", event => {
    currentLocation = event.target.value
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
      currentLocation = new_data[0]["location"]
      document.getElementById("location").value = currentLocation
      currentPosition = new_data[0]["pos"] + 1
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

function finalLoad (_event) {
  possible.on("dataFiltered", function (_filters, rows) {
    const images = []
    if (rows.length === 1) {
      if (document.getElementById("images").children.length > 1) {
        document.getElementById("images").textContent = ""
        rows.map(element => {
          images.push(downloadImage(element._row.data))
        })
      }
    } else if (rows.length <= 10) {
      document.getElementById("images").textContent = ""
      rows.map(element => {
        images.push(downloadImage(element._row.data))
      })
    }
    if (images.length > 0){
      const img_div = document.getElementById("images")
      images.forEach(el => el.then(result => img_div.appendChild(result)))
    }
  })
  possible.on("pageLoaded", _pageno => activeRow = -1)
  possible.setHeaderFilterFocus("name")

  inventory.setData([])
  inventory.hideColumn("id")
  inventory.on("dataChanged", _data => {possible.refreshFilter()})
}

function _addToInventory (rowData) {
  let new_data = rowData
  new_data["location"] = currentLocation
  new_data["pos"] = currentPosition
  currentPosition += 1
  inventory.addRow(new_data, true)
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

function removeFromInventory (_event, row) {
  if (row !== undefined && row.getData() !== undefined) {
    row.delete()
  }
}

async function saveInventory (_event) {
  inventory.showColumn("id")
  inventory.download("json", "inventory_mtg.json")
  inventory.hideColumn("id")
}

async function fetchImage (card_id, version = "small") {
  const url = `https://api.scryfall.com/cards/${card_id}?format=image&version=${version}`
  const response = await fetch(url)
  const blob = await response.blob()

  return blob
}

async function downloadImage (data, version = "small") {
  await new Promise(r => setTimeout(r, 100)) // Per Scryfall guidelines
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
  new_el.setAttribute("data", JSON.stringify(data))
  new_el.addEventListener("click", event => {
    _addToInventory(JSON.parse(event.target.getAttribute("data")))
  })
  return new_el
}
