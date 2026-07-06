(function () {
  const catalog = window.MODEL_CATALOG || [];
  const maxSlots = 5;

  function modelsForMake(make) {
    const brand = catalog.find((item) => item.make === make);
    return brand ? brand.models : [];
  }

  function fillModelSelect(modelSelect, make, selectedModel) {
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
      if (model.name === selectedModel) {
        option.selected = true;
      }
      modelSelect.appendChild(option);
    }
  }

  function initRow(row) {
    const makeSelect = row.querySelector(".make-select");
    const modelSelect = row.querySelector(".model-select");
    const selectedModel = modelSelect.dataset.selected || "";

    fillModelSelect(modelSelect, makeSelect.value, selectedModel);

    makeSelect.addEventListener("change", () => {
      fillModelSelect(modelSelect, makeSelect.value, "");
    });
  }

  function init() {
    document.querySelectorAll(".model-picker-row").forEach(initRow);

    const form = document.getElementById("model-selection-form");
    if (!form) {
      return;
    }

    form.addEventListener("submit", (event) => {
      const pairs = [];
      const seen = new Set();

      document.querySelectorAll(".model-picker-row").forEach((row) => {
        const make = row.querySelector(".make-select").value.trim();
        const model = row.querySelector(".model-select").value.trim();
        if (!make || !model) {
          return;
        }
        const key = `${make}|${model}`;
        if (seen.has(key)) {
          return;
        }
        seen.add(key);
        pairs.push({ make, model });
      });

      if (pairs.length === 0) {
        event.preventDefault();
        window.alert("Choose at least one brand and model.");
        return;
      }

      if (pairs.length > maxSlots) {
        event.preventDefault();
        window.alert(`You can select up to ${maxSlots} models.`);
        return;
      }

      const container = document.getElementById("selection-hidden-fields");
      container.innerHTML = "";
      pairs.forEach((pair, index) => {
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
    });
  }

  document.addEventListener("DOMContentLoaded", init);
})();
