// Shared task form rules — action drives which fields appear and in what order.
import { esc } from "./dom.js";

export const TASK_ACTIONS = [
  { value: "pick", label: "PICK", desc: "Collect an item from where it is stored" },
  { value: "restock", label: "RESTOCK", desc: "Bring stock to a work section" },
  { value: "move", label: "MOVE", desc: "Relocate an item to another section" },
  { value: "inspect", label: "INSPECT", desc: "Visit a section (optional item check)" },
];

export function countSections(tree) {
  let n = 0;
  for (const w of tree || []) n += (w.sections || []).length;
  return n;
}

export function moveIsAvailable(tree) {
  return countSections(tree) > 1;
}

export function itemById(items, id) {
  return (items || []).find((it) => String(it.id) === String(id));
}

export function syncActionOptions(actionEl, tree, current) {
  if (!actionEl) return;
  const canMove = moveIsAvailable(tree);
  const val = current || actionEl.value;
  actionEl.innerHTML = "";
  for (const a of TASK_ACTIONS) {
    if (a.value === "move" && !canMove) continue;
    const o = document.createElement("option");
    o.value = a.value;
    o.textContent = a.label;
    actionEl.appendChild(o);
  }
  if ([...actionEl.options].some((o) => o.value === val)) actionEl.value = val;
  else if (actionEl.options.length) actionEl.value = actionEl.options[0].value;
}

function sectionOptions(tree, { excludeSectionId = null, onlySectionId = null } = {}) {
  const out = [];
  for (const w of tree || []) {
    for (const s of w.sections || []) {
      if (onlySectionId != null && s.id != onlySectionId) continue;
      if (excludeSectionId != null && s.id == excludeSectionId) continue;
      out.push({ id: s.id, label: `${w.name} / ${s.name}` });
    }
  }
  return out;
}

export function fillSectionSelect(sel, tree, opts = {}) {
  if (!sel) return;
  const { placeholder = "— select section —", selectedId = null } = opts;
  const entries = sectionOptions(tree, opts).map((s) => ({ value: s.id, label: s.label }));
  if (sel.setOptions) {
    fillPicker(sel, entries, { placeholder, selectedId: selectedId ?? fieldVal(sel) });
    return;
  }
  sel.innerHTML = "";
  const none = document.createElement("option");
  none.value = "";
  none.textContent = placeholder;
  sel.appendChild(none);
  for (const s of entries) {
    const o = document.createElement("option");
    o.value = s.value;
    o.textContent = s.label;
    if (s.value == selectedId) o.selected = true;
    sel.appendChild(o);
  }
}

function itemOptionLabel(it) {
  const qty = it.quantity ?? 1;
  return `${it.name}${it.sku ? ` (${it.sku})` : ""} · ${qty} in stock`;
}

export function fieldVal(field) {
  if (!field) return "";
  return field.getValue ? field.getValue() : field.value;
}

export function setFieldVal(field, val) {
  if (!field) return;
  if (field.setValue) field.setValue(val ?? "");
  else field.value = val ?? "";
}

function fillPicker(picker, entries, { placeholder, selectedId = null } = {}) {
  if (!picker?.setOptions) return;
  const selected = selectedId ?? fieldVal(picker);
  picker.setOptions([{ value: "", label: placeholder }, ...entries], placeholder);
  const ok = selected && entries.some((e) => String(e.value) === String(selected));
  picker.setValue(ok ? selected : "");
}

export function fillItemSelect(sel, items, opts = {}) {
  if (!sel) return;
  const {
    placeholder = "— select item —",
    selectedId = null,
    sectionId = null,
    requireStock = false,
  } = opts;
  let list = items || [];
  if (sectionId) list = list.filter((it) => it.location.section_id == sectionId);
  if (requireStock) list = list.filter((it) => (it.quantity ?? 1) > 0);
  const entries = list.map((it) => ({ value: it.id, label: itemOptionLabel(it) }));
  if (sel.setOptions) {
    fillPicker(sel, entries, { placeholder, selectedId: selectedId ?? fieldVal(sel) });
    return;
  }
  sel.innerHTML = "";
  const none = document.createElement("option");
  none.value = "";
  none.textContent = placeholder;
  sel.appendChild(none);
  for (const it of list) {
    const o = document.createElement("option");
    o.value = it.id;
    o.textContent = itemOptionLabel(it);
    o.dataset.sectionId = it.location.section_id;
    o.dataset.quantity = String(it.quantity ?? 1);
    o.dataset.path = it.location.path;
    if (it.id == selectedId) o.selected = true;
    sel.appendChild(o);
  }
}

function setVisible(field, on) {
  if (!field) return;
  const wrap = field.root?.closest("label") || field.closest?.("label");
  if (wrap) wrap.classList.toggle("hidden", !on);
  if (field.setDisabled) field.setDisabled(!on);
  else if (field.tagName === "SELECT" || field.tagName === "INPUT") field.disabled = !on;
}

export function applyTaskFormRules(ctx) {
  const {
    actionEl, itemEl, sectionEl, qtyEl, hintEl, fromHintEl,
    tree, items,
    sectionLabelEl, itemLabelEl,
  } = ctx;
  if (!actionEl) return;

  const action = actionEl.value;
  const item = itemById(items, fieldVal(itemEl));
  const meta = TASK_ACTIONS.find((a) => a.value === action);

  if (hintEl && meta) hintEl.textContent = meta.desc;

  if (itemLabelEl) itemLabelEl.textContent = "ITEM";
  if (sectionLabelEl) {
    sectionLabelEl.textContent =
      action === "move" ? "MOVE TO"
        : action === "restock" ? "RESTOCK AT"
          : action === "pick" ? "PICK FROM"
            : "WHERE TO GO";
  }

  const needsItem = action === "pick" || action === "restock" || action === "move";
  const needsQty = action === "pick" || action === "restock" || action === "move";
  const needsSection = action === "inspect" || action === "restock" || action === "move";

  setVisible(itemEl, needsItem);
  const qtyWrap = qtyEl?.closest("label");
  if (qtyWrap) qtyWrap.classList.toggle("hidden", !needsQty);
  if (qtyEl) qtyEl.disabled = !needsQty;
  setVisible(sectionEl, needsSection || action === "pick");

  if (action === "pick") {
    fillItemSelect(itemEl, items, {
      placeholder: "— select item to pick —",
      selectedId: fieldVal(itemEl),
      requireStock: true,
    });
    if (item) {
      fillSectionSelect(sectionEl, tree, {
        placeholder: "— pick location —",
        onlySectionId: item.location.section_id,
        selectedId: item.location.section_id,
      });
      if (sectionEl?.setDisabled) sectionEl.setDisabled(true);
      else if (sectionEl) sectionEl.disabled = true;
      if (fromHintEl) {
        fromHintEl.classList.remove("hidden");
        fromHintEl.textContent = `Picking from ${item.location.path}`;
      }
    } else {
      fillSectionSelect(sectionEl, tree, { placeholder: "— select item first —" });
      if (sectionEl?.setDisabled) sectionEl.setDisabled(true);
      else if (sectionEl) sectionEl.disabled = true;
      if (fromHintEl) fromHintEl.classList.add("hidden");
    }
  } else if (action === "move") {
    fillItemSelect(itemEl, items, {
      placeholder: "— select item to move —",
      selectedId: fieldVal(itemEl),
      requireStock: true,
    });
    if (item) {
      fillSectionSelect(sectionEl, tree, {
        placeholder: "— select destination —",
        excludeSectionId: item.location.section_id,
        selectedId: fieldVal(sectionEl),
      });
      if (sectionEl?.setDisabled) sectionEl.setDisabled(false);
      else if (sectionEl) sectionEl.disabled = false;
      if (fromHintEl) {
        fromHintEl.classList.remove("hidden");
        fromHintEl.textContent = `Currently at ${item.location.path}`;
      }
    } else {
      fillSectionSelect(sectionEl, tree, { placeholder: "— select item first —" });
      if (sectionEl?.setDisabled) sectionEl.setDisabled(true);
      else if (sectionEl) sectionEl.disabled = true;
      if (fromHintEl) fromHintEl.classList.add("hidden");
    }
  } else if (action === "restock") {
    fillItemSelect(itemEl, items, {
      placeholder: "— select item —",
      selectedId: fieldVal(itemEl),
      requireStock: true,
    });
    fillSectionSelect(sectionEl, tree, {
      placeholder: "— deliver to section —",
      selectedId: fieldVal(sectionEl),
    });
    if (sectionEl?.setDisabled) sectionEl.setDisabled(false);
    else if (sectionEl) sectionEl.disabled = false;
    if (fromHintEl) {
      fromHintEl.classList.toggle("hidden", !item);
      fromHintEl.textContent = item ? `Stock now at ${item.location.path}` : "";
    }
  } else if (action === "inspect") {
    fillSectionSelect(sectionEl, tree, {
      placeholder: "— section to inspect —",
      selectedId: fieldVal(sectionEl),
    });
    fillItemSelect(itemEl, items, {
      placeholder: "— optional item —",
      selectedId: fieldVal(itemEl),
      sectionId: fieldVal(sectionEl) || null,
    });
    setVisible(itemEl, true);
    if (itemLabelEl) itemLabelEl.textContent = "ITEM (OPTIONAL)";
    if (sectionEl?.setDisabled) sectionEl.setDisabled(false);
    else if (sectionEl) sectionEl.disabled = false;
    if (fromHintEl) fromHintEl.classList.add("hidden");
  }

  if (needsQty && qtyEl) {
    const max = item ? (item.quantity ?? 1) : 1;
    const selected = readQuantity(qtyEl);
    fillQuantityPicker(qtyEl, ctx.qtyHintEl, max, selected);
  } else if (qtyEl) {
    qtyEl.disabled = true;
  }
}

export function fillQuantityPicker(qtyEl, hintEl, maxQty, selected = 1) {
  if (!qtyEl) return;
  const max = Math.max(1, Number(maxQty) || 1);
  const val = Math.min(max, Math.max(1, Number(selected) || 1));

  qtyEl.max = String(max);
  qtyEl.min = "1";
  qtyEl.value = String(val);
  qtyEl.disabled = false;

  if (hintEl) {
    hintEl.textContent = max === 1 ? "1 in stock" : `1–${max} in stock`;
  }

  if (!qtyEl.dataset.qtyWired) {
    qtyEl.dataset.qtyWired = "1";
    qtyEl.addEventListener("input", () => {
      const cap = Math.max(1, Number(qtyEl.max) || 1);
      const raw = Number(qtyEl.value);
      if (!raw || raw < 1) return;
      qtyEl.value = String(Math.min(cap, Math.max(1, Math.floor(raw))));
    });
    qtyEl.addEventListener("change", () => {
      const cap = Math.max(1, Number(qtyEl.max) || 1);
      const clamped = Math.min(cap, Math.max(1, Math.floor(Number(qtyEl.value) || 1)));
      qtyEl.value = String(clamped);
    });
  }
}

export function readQuantity(qtyEl) {
  const v = qtyEl ? Number(qtyEl.value) : NaN;
  if (!Number.isNaN(v) && v >= 1) return Math.floor(v);
  return 1;
}

export function validateTaskPayload(action, sectionId, itemId, quantity, tree, items) {
  const item = itemById(items, itemId);
  const qty = Math.max(1, Number(quantity) || 1);

  if (action === "pick") {
    if (!itemId) return { ok: false, error: "Select an item to pick" };
    if (!item) return { ok: false, error: "Item not found" };
    if (qty > (item.quantity ?? 1)) return { ok: false, error: `Only ${item.quantity ?? 1} in stock` };
    return { ok: true, section_id: item.location.section_id, item_id: Number(itemId), quantity: qty };
  }
  if (action === "move") {
    if (!moveIsAvailable(tree)) return { ok: false, error: "Move needs at least two sections" };
    if (!itemId) return { ok: false, error: "Select an item to move" };
    if (!sectionId) return { ok: false, error: "Choose where to move it" };
    if (!item) return { ok: false, error: "Item not found" };
    if (Number(sectionId) === Number(item.location.section_id)) {
      return { ok: false, error: "Destination must be a different section" };
    }
    if (qty > (item.quantity ?? 1)) return { ok: false, error: `Only ${item.quantity ?? 1} in stock` };
    return { ok: true, section_id: Number(sectionId), item_id: Number(itemId), quantity: qty };
  }
  if (action === "restock") {
    if (!itemId) return { ok: false, error: "Select an item to restock" };
    if (!sectionId) return { ok: false, error: "Choose the section to restock" };
    if (!item) return { ok: false, error: "Item not found" };
    if (qty > (item.quantity ?? 1)) return { ok: false, error: `Only ${item.quantity ?? 1} available` };
    return { ok: true, section_id: Number(sectionId), item_id: Number(itemId), quantity: qty };
  }
  if (action === "inspect") {
    if (!sectionId) return { ok: false, error: "Choose a section to inspect" };
    return {
      ok: true,
      section_id: Number(sectionId),
      item_id: itemId ? Number(itemId) : null,
      quantity: 1,
    };
  }
  return { ok: false, error: "Unknown action" };
}

export function wireTaskForm(ctx) {
  const refresh = () => {
    const tree = ctx.getTree ? ctx.getTree() : ctx.tree;
    const items = ctx.getItems ? ctx.getItems() : ctx.items;
    applyTaskFormRules({ ...ctx, tree, items });
  };
  ctx.actionEl?.addEventListener("change", () => {
    setFieldVal(ctx.itemEl, "");
    setFieldVal(ctx.sectionEl, "");
    refresh();
  });
  if (ctx.itemEl?.onChange) ctx.itemEl.onChange(refresh);
  else ctx.itemEl?.addEventListener("change", refresh);
  if (ctx.sectionEl?.onChange) {
    ctx.sectionEl.onChange(() => {
      if (ctx.actionEl?.value === "inspect") refresh();
    });
  } else {
    ctx.sectionEl?.addEventListener("change", () => {
      if (ctx.actionEl?.value === "inspect") refresh();
    });
  }
  return refresh;
}
