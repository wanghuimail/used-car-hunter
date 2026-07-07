(function () {
  const catalog = window.MODEL_CATALOG || [];
  const maxModels = 5;
  const selections = Array.isArray(window.MODEL_SELECTION)
    ? window.MODEL_SELECTION.map((item) => ({
        make: item.make,
        model: item.model,
      }))
    : [];

  const makeSelect = document.getElementById("make-select");
  const modelSelect = document.getElementById("model-select");
  const addBtn = document.getElementById("add-model-btn");
  const listEl = document.getElementById("selected-models-list");
  const emptyEl = document.getElementById("selected-models-empty");
  const countEl = document.getElementById("selection-count");
  const slotTrack = document.getElementById("slot-track");
  const searchBtn = document.getElementById("search-btn");
  const form = document.getElementById("model-search-form");

  function modelsForMake(make) {
    const brand = catalog.find((item) => item.make === make);
    return brand ? brand.models : [];
  }

  function pairKey(make, model) {
    return `${make}|${model}`;
  }

  function fillModelSelect(make) {
    modelSelect.innerHTML = "";
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = make ? "Choose model" : "Select make first";
    modelSelect.appendChild(placeholder);

    if (!make) {
      modelSelect.disabled = true;
      return;
    }

    modelSelect.disabled = false;
    for (const model of modelsForMake(make)) {
      const option = document.createElement("option");
      option.value = model.name;
      option.textContent = model.name;
      modelSelect.appendChild(option);
    }
  }

  function updateSlotTrack() {
    if (!slotTrack) {
      return;
    }
    const dots = slotTrack.querySelectorAll(".slot-dot");
    dots.forEach((dot, index) => {
      dot.classList.toggle("filled", index < selections.length);
    });
  }

  function renderList() {
    listEl.innerHTML = "";
    selections.forEach((item, index) => {
      const card = document.createElement("article");
      card.className = "vehicle-card";
      card.innerHTML = `
        <div class="vehicle-card-rank" aria-hidden="true">${index + 1}</div>
        <div class="vehicle-card-body">
          <div class="vehicle-card-make">${item.make}</div>
          <div class="vehicle-card-model">${item.model}</div>
        </div>
        <button type="button" class="vehicle-card-remove remove-model-btn" data-index="${index}" aria-label="Remove ${item.make} ${item.model}">
          Remove
        </button>
      `;
      listEl.appendChild(card);
    });

    const hasItems = selections.length > 0;
    listEl.hidden = !hasItems;
    emptyEl.hidden = hasItems;

    const count = selections.length;
    countEl.textContent = `${count} of ${maxModels}`;
    countEl.classList.toggle("is-full", count >= maxModels);

    const atMax = count >= maxModels;
    addBtn.disabled = atMax;
    searchBtn.disabled = count === 0;
    updateSlotTrack();
  }

  function addSelection() {
    const make = makeSelect.value.trim();
    const model = modelSelect.value.trim();
    if (!make || !model) {
      window.alert("Choose both a make and a model before adding.");
      return;
    }
    if (selections.length >= maxModels) {
      window.alert(`You can add up to ${maxModels} vehicles.`);
      return;
    }
    if (selections.some((item) => pairKey(item.make, item.model) === pairKey(make, model))) {
      window.alert(`${make} ${model} is already on your shortlist.`);
      return;
    }

    selections.push({ make, model });
    renderList();
    modelSelect.value = "";
    makeSelect.focus();
  }

  function removeSelection(index) {
    selections.splice(index, 1);
    renderList();
  }

  function writeHiddenFields() {
    const container = document.getElementById("selection-hidden-fields");
    container.innerHTML = "";
    selections.forEach((pair, index) => {
      const makeInput = document.createElement("input");
      makeInput.type = "hidden";
      makeInput.name = `make_${index}`;
      makeInput.value = pair.make;
      container.appendChild(makeInput);

      const modelInput = document.createElement("input");
      modelInput.type = "hidden";
      modelInput.name = `model_${index}`;
      modelInput.value = pair.model;
      container.appendChild(modelInput);
    });
  }

  function init() {
    if (!makeSelect || !form) {
      return;
    }

    fillModelSelect(makeSelect.value);
    renderList();

    makeSelect.addEventListener("change", () => {
      fillModelSelect(makeSelect.value);
    });

    addBtn.addEventListener("click", addSelection);

    listEl.addEventListener("click", (event) => {
      const button = event.target.closest(".remove-model-btn");
      if (!button) {
        return;
      }
      removeSelection(Number(button.dataset.index));
    });

    form.addEventListener("submit", (event) => {
      if (selections.length === 0) {
        event.preventDefault();
        window.alert("Add at least one vehicle before searching.");
        return;
      }
      writeHiddenFields();
      searchBtn.disabled = true;
      searchBtn.textContent = "Searching…";
    });
  }

  document.addEventListener("DOMContentLoaded", init);
})();
