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
    placeholder.textContent = "Select model…";
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

  function renderList() {
    listEl.innerHTML = "";
    selections.forEach((item, index) => {
      const li = document.createElement("li");
      li.innerHTML = `
        <span><strong>#${index + 1}</strong> ${item.make} ${item.model}</span>
        <button type="button" class="secondary remove-model-btn" data-index="${index}">Remove</button>
      `;
      listEl.appendChild(li);
    });

    const hasItems = selections.length > 0;
    listEl.hidden = !hasItems;
    emptyEl.hidden = hasItems;
    countEl.textContent = `${selections.length} / ${maxModels} models selected`;

    const atMax = selections.length >= maxModels;
    addBtn.disabled = atMax;
    searchBtn.disabled = selections.length === 0;
    if (atMax) {
      countEl.textContent += " — maximum reached";
    }
  }

  function addSelection() {
    const make = makeSelect.value.trim();
    const model = modelSelect.value.trim();
    if (!make || !model) {
      window.alert("Choose both a brand and a model before adding.");
      return;
    }
    if (selections.length >= maxModels) {
      window.alert(`You can add up to ${maxModels} models.`);
      return;
    }
    if (selections.some((item) => pairKey(item.make, item.model) === pairKey(make, model))) {
      window.alert(`${make} ${model} is already in your list.`);
      return;
    }

    selections.push({ make, model });
    renderList();
    modelSelect.value = "";
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
        window.alert("Add at least one brand and model before starting a search.");
        return;
      }
      writeHiddenFields();
    });
  }

  document.addEventListener("DOMContentLoaded", init);
})();
