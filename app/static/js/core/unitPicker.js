// Chassis model picker for pair-robot forms.
import { esc } from "./dom.js";
import { UNIT_CATALOG, robotImageUrl, unitById } from "./robotImages.js";

export function mountUnitPicker(mountEl, { hiddenInput, selectedLabelEl } = {}) {
  if (!mountEl) return { getValue: () => 1, getBrand: () => unitById(1).brand, reset: () => {} };

  let selected = 1;

  function updateSelectedLabel() {
    if (!selectedLabelEl) return;
    const unit = unitById(selected);
    selectedLabelEl.textContent = `${unit.brand} · ${unit.code}`;
  }

  function applySelection(id) {
    const unit = unitById(id);
    selected = unit.id;
    if (hiddenInput) hiddenInput.value = String(selected);
    mountEl.querySelectorAll(".unit-pick").forEach((btn) => {
      const on = Number(btn.dataset.id) === selected;
      btn.classList.toggle("selected", on);
      btn.setAttribute("aria-selected", on ? "true" : "false");
    });
    updateSelectedLabel();
  }

  function onPick(id) {
    applySelection(id);
  }

  function render() {
    mountEl.innerHTML = UNIT_CATALOG.map((u) =>
      `<button type="button" class="unit-pick${u.id === selected ? " selected" : ""}" data-id="${u.id}" ` +
      `role="option" aria-selected="${u.id === selected ? "true" : "false"}">` +
      `<img class="unit-pick-img" src="${robotImageUrl(u.id)}" alt="" loading="lazy" draggable="false" />` +
      `<span class="unit-pick-brand">${esc(u.brand)}</span>` +
      `<span class="unit-pick-code">${esc(u.code)}</span>` +
      `</button>`,
    ).join("");

    mountEl.querySelectorAll(".unit-pick").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        onPick(Number(btn.dataset.id));
      });
    });
  }

  render();
  applySelection(selected);

  return {
    getValue: () => selected,
    getBrand: () => unitById(selected).brand,
    reset() {
      applySelection(1);
    },
    setSelected(id) {
      applySelection(unitById(id).id);
    },
  };
}
