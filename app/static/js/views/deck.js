// Navigation deck: warehouse / section chips + bay grid, with add/delete.
import { api } from "../core/api.js";
import { store, whById, secById, render, reload } from "../core/store.js";
import { el, esc, $, toast } from "../core/dom.js";
import { askPrompt, askConfirm } from "../core/dialogs.js";
import { randomWarehouseName, randomSectionName, randomBayCode } from "../core/nameGen.js";

const addBtn = (label, onClick) => { const b = el("button", "btn btn-add", label); b.onclick = onClick; return b; };

export async function addChild(table, title, label, extra, field, defaultValue = "", refreshFn = null) {
  const value = await askPrompt(title, label, "", defaultValue, refreshFn);
  if (!value) return;
  try {
    const res = await api.send("POST", "/api/" + table, { ...extra, [field]: value });
    if (await reloadKeepingSelection(table, extra, res)) toast("Added");
  } catch (err) { toast(err.message, true); }
}

async function reloadKeepingSelection(table, extra, res) {
  if (table === "warehouses") store.sel = { w: res.id, s: null, shelf: null };
  else if (table === "sections") store.sel = { w: extra.warehouse_id, s: res.id, shelf: null };
  else if (table === "shelves") store.sel.shelf = res.id;
  await reload({ silent: true });
  return true;
}

export async function delEntity(table, id, confirmMsg) {
  if (!(await askConfirm(confirmMsg, "Delete"))) return;
  await api.send("DELETE", `/api/${table}/${id}`);
  if (table === "warehouses" && store.sel.w == id) store.sel = { w: null, s: null, shelf: null };
  if (table === "sections" && store.sel.s == id) { store.sel.s = null; store.sel.shelf = null; }
  if (table === "shelves" && store.sel.shelf == id) store.sel.shelf = null;
  await reload({ silent: true });
  toast("Deleted");
}

export function renderDeck() {
  // The location deck (warehouse / aisle / bays) stays visible on every view —
  // it's a persistent navigator, not items-only, so switching tabs (Items /
  // Fleet / Tasks / Map) no longer makes it pop in and out.
  const whRow = $("#wh-row"); whRow.innerHTML = "";
  for (const w of store.tree) {
    const c = el("button", "chip" + (w.id == store.sel.w ? " active" : ""), `${esc(w.name)}<span class="x" title="Delete">✕</span>`);
    c.onclick = (e) => {
      if (e.target.classList.contains("x")) return delEntity("warehouses", w.id, `Delete "${w.name}" and everything inside it?`);
      store.sel = { w: w.id, s: null, shelf: null }; render();
    };
    whRow.appendChild(c);
  }
  whRow.appendChild(addBtn("＋ Warehouse", () => addChild("warehouses", "New warehouse", "Warehouse name", {}, "name", randomWarehouseName(), randomWarehouseName)));

  const w = whById(store.sel.w);
  const secRow = $("#sec-row"); secRow.innerHTML = "";
  if (w) {
    const allSec = el("button", "chip" + (store.sel.s === null ? " active" : ""), "ALL");
    allSec.onclick = () => { store.sel.s = null; store.sel.shelf = null; render(); };
    secRow.appendChild(allSec);
    for (const s of w.sections) {
      const c = el("button", "chip" + (s.id == store.sel.s ? " active" : ""), `${esc(s.name)}<span class="x" title="Delete">✕</span>`);
      c.onclick = (e) => {
        if (e.target.classList.contains("x")) return delEntity("sections", s.id, `Delete section "${s.name}" and its bays & items?`);
        store.sel.s = s.id; store.sel.shelf = null; render();
      };
      secRow.appendChild(c);
    }
    secRow.appendChild(addBtn("＋ Aisle", () => addChild("sections", "New aisle", "Aisle name", { warehouse_id: w.id }, "name", randomSectionName(), randomSectionName)));
  } else {
    secRow.innerHTML = `<span class="deck-empty">— add a warehouse first —</span>`;
  }

  const s = secById(w, store.sel.s);
  const binRow = $("#bin-row"); binRow.innerHTML = "";
  if (s) {
    const all = el("div", "bin all" + (store.sel.shelf === null ? " active" : ""),
      `<div class="code">ALL<br>BAYS</div><div class="meta"><span class="qty">${s.shelves.reduce((a, sh) => a + sh.item_count, 0)}</span></div>`);
    all.onclick = () => { store.sel.shelf = null; render(); };
    binRow.appendChild(all);
    for (const sh of s.shelves) {
      const b = el("div", "bin" + (sh.id == store.sel.shelf ? " active" : ""),
        `<div class="code">${esc(sh.code)}</div><div class="meta"><span class="qty">${sh.item_count}</span><span class="x" title="Delete">✕</span></div>`);
      b.onclick = (e) => {
        if (e.target.classList.contains("x")) return delEntity("shelves", sh.id, `Delete bay "${sh.code}" and its items?`);
        store.sel.shelf = sh.id; render();
      };
      binRow.appendChild(b);
    }
    binRow.appendChild(addBtn("＋ Bay", () => {
      const taken = new Set(s.shelves.map((sh) => sh.code));
      addChild("shelves", "New bay", "Bay code", { section_id: s.id }, "code", randomBayCode(taken), () => randomBayCode(taken));
    }));
  } else if (w && w.sections.length) {
    binRow.innerHTML = `<span class="deck-empty">— select a section to see its bays —</span>`;
  } else if (w) {
    binRow.innerHTML = `<span class="deck-empty">— add a section first —</span>`;
  }

  $("#bays-line").style.display = "";
}
