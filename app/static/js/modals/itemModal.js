// Create-item modal (editing happens on the item detail page).
import { api } from "../core/api.js";
import { store, reload } from "../core/store.js";
import { $, toast } from "../core/dom.js";
import { mountShelfSelect } from "../core/shelfSelect.js";
import { wireFieldRefresh } from "../core/fieldRefresh.js";
import { randomItemSku } from "../core/itemGen.js";

const shelfPicker = mountShelfSelect($("#shelf-select"));
const nameInput = $("#item-name-input");
const skuInput = $("#item-sku-input");

const fillSku = wireFieldRefresh(skuInput, $("#item-sku-refresh"), () => {
  skuInput.value = randomItemSku(shelfPicker.getValue());
  skuInput.dataset.userEdited = "";
});

shelfPicker.onChange(() => {
  if (skuInput && !skuInput.dataset.userEdited && !skuInput.value.trim()) fillSku();
});

skuInput?.addEventListener("input", () => {
  skuInput.dataset.userEdited = skuInput.value.trim() ? "1" : "";
});

function resolveSku() {
  const typed = skuInput?.value.trim();
  if (typed) return typed;
  const generated = randomItemSku(shelfPicker.getValue());
  if (skuInput) skuInput.value = generated;
  return generated;
}

function fillShelfSelect() {
  const entries = Object.entries(store.shelfMap);
  if (!entries.length) {
    shelfPicker.setOptions([["", "— create a bay first —"]]);
    shelfPicker.setValue("");
    return;
  }
  shelfPicker.setOptions(entries);
  if (store.sel.shelf) shelfPicker.setValue(store.sel.shelf);
  else shelfPicker.setValue(entries[0][0]);
}

export function newItem() {
  $("#modal-title").textContent = "New item";
  $("#item-form").reset();
  shelfPicker.reset();
  delete skuInput?.dataset.userEdited;
  fillShelfSelect();
  fillSku();
  $("#delete-item").classList.add("hidden");
  $("#locate").classList.add("hidden");
  $("#modal").classList.remove("hidden");
}

$("#item-form").onsubmit = async (e) => {
  e.preventDefault();
  const f = e.target;
  const body = {
    name: f.name.value.trim(),
    sku: resolveSku(),
    shelf_id: Number(shelfPicker.getValue()),
    notes: f.notes.value.trim(),
    quantity: Math.max(1, Number(f.quantity.value) || 1),
  };
  if (!body.name) return toast("Enter a product name", true);
  if (!body.shelf_id) return toast("Create a bay first", true);
  try {
    await api.send("POST", "/api/items", body);
    $("#modal").classList.add("hidden");
    await reload({ silent: true });
    toast("Item logged");
  } catch (err) { toast(err.message, true); }
};

$("#modal-close").onclick = () => $("#modal").classList.add("hidden");
