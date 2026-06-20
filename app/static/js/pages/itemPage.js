// Item detail page: view / edit / move / delete a single item.
import { api } from "../core/api.js";
import { $, el, esc, toast } from "../core/dom.js";
import { askConfirm } from "../core/dialogs.js";
import { mountShelfSelect } from "../core/shelfSelect.js";
import { clearLocLoading } from "../core/skeleton.js";
import { wireFieldRefresh } from "../core/fieldRefresh.js";
import { randomItemSku } from "../core/itemGen.js";

const root = $(".detail-page");
const itemId = root.dataset.itemId;
const shelfPicker = mountShelfSelect($("#shelf-select"));
const nameInput = $("#detail-name-input");
const skuInput = $("#detail-sku-input");
let allItems = [], treeData = [], robots = [], tasks = [], statusColors = {}, statusLabels = {};
const TASK_LABELS = { queued: "Queued", in_progress: "In progress", done: "Done", cancelled: "Cancelled" };

const fillSku = wireFieldRefresh(skuInput, $("#detail-sku-refresh"), () => {
  skuInput.value = randomItemSku(shelfPicker.getValue(), allItems, treeData);
  skuInput.dataset.userEdited = "";
});

shelfPicker.onChange(() => {
  if (skuInput && !skuInput.dataset.userEdited && !skuInput.value.trim()) fillSku();
});

skuInput?.addEventListener("input", () => {
  skuInput.dataset.userEdited = skuInput.value.trim() ? "1" : "";
});

function resolveSku(shelfId) {
  const typed = skuInput?.value.trim();
  if (typed) return typed;
  const generated = randomItemSku(shelfId, allItems, treeData);
  if (skuInput) skuInput.value = generated;
  return generated;
}

function robotsWithTasksInSection(sid) {
  const ids = new Set(
    tasks
      .filter((t) => t.section_id == sid && (t.status === "queued" || t.status === "in_progress"))
      .map((t) => t.robot_id),
  );
  return robots.filter((r) => ids.has(r.id));
}

function fillShelfSelect(tree, current) {
  const entries = [];
  for (const w of tree) {
    for (const s of w.sections) {
      for (const sh of s.shelves) {
        entries.push([sh.id, `${w.name} · ${s.name} · ${sh.code}`]);
      }
    }
  }
  if (!entries.length) {
    shelfPicker.setOptions([["", "— create a bay first —"]]);
    shelfPicker.setValue("");
    return;
  }
  shelfPicker.setOptions(entries);
  shelfPicker.setValue(current);
}

function renderLoc(item) {
  clearLocLoading();
  $("#detail-name").textContent = item.name.toUpperCase();
  const onBay = allItems.filter((it) => it.shelf_id == item.shelf_id).length;
  const inSection = allItems.filter((it) => it.location.section_id == item.location.section_id).length;
  const secRobots = robotsWithTasksInSection(item.location.section_id);
  const robotNote = secRobots.length ? secRobots.map((r) => esc(r.name)).join(", ") : "none";
  $("#loc-card").innerHTML =
    `<div class="loc-path">${esc(item.location.path)}</div>` +
    `<div class="loc-row"><span>SKU / number</span><span>${item.sku ? esc(item.sku) : "—"}</span></div>` +
    `<div class="loc-row"><span>Quantity in stock</span><span>${item.quantity ?? 1}</span></div>` +
    `<div class="loc-row"><span>Warehouse</span><span>${esc(item.location.warehouse)}</span></div>` +
    `<div class="loc-row"><span>Section</span><span>${esc(item.location.section)}</span></div>` +
    `<div class="loc-row"><span>Bay</span><span>${esc(item.location.shelf)}</span></div>` +
    `<div class="loc-row"><span>Items on this bay</span><span>${onBay}</span></div>` +
    `<div class="loc-row"><span>Items in section</span><span>${inSection}</span></div>` +
    `<div class="loc-row"><span>Robots with tasks here</span><span>${robotNote}</span></div>` +
    `<div class="loc-row"><span>Item ID</span><span>#${item.id}</span></div>` +
    `<div class="loc-row"><span>Added</span><span>${esc(item.created_at)}</span></div>` +
    `<div class="loc-robot">Robot lookup: <code>GET /api/items/${item.id}</code></div>`;
}

function renderExtra(item) {
  const sid = item.location.section_id;

  // other items on the same bay
  const neighbors = allItems.filter((it) => it.shelf_id == item.shelf_id && it.id != item.id);
  $("#bay-items").innerHTML = neighbors.length
    ? neighbors.map((it) =>
        `<a class="mini-row" href="/items/${it.id}"><span class="mini-name">${esc(it.name)}</span>` +
        `<span class="mini-tag">${it.sku ? esc(it.sku) : "—"}</span></a>`).join("")
    : `<div class="muted-line">This bay holds only this item.</div>`;

  // robots stationed in this section
  const secRobots = robotsWithTasksInSection(sid);
  $("#section-robots").innerHTML = secRobots.length
    ? secRobots.map((r) =>
        `<a class="mini-row" href="/robots/${r.id}"><span class="dot" style="background:${esc(statusColors[r.status] || "#888")}"></span>` +
        `<span class="mini-name">${esc(r.name)}</span><span class="mini-tag">${esc(statusLabels[r.status] || r.status)}</span></a>`).join("")
    : `<div class="muted-line">No robots with open tasks in this section.</div>`;

  // tasks targeting this item
  const itemTasks = tasks.filter((t) => t.item_id == item.id);
  $("#item-tasks").innerHTML = itemTasks.length
    ? itemTasks.map((t) => {
        const who = t.staff_username ? ` · ${esc(t.staff_username)}` : "";
        return `<div class="mini-row${t.status === "done" || t.status === "cancelled" ? " muted-task" : ""}">` +
        `<span class="mini-name">${esc(t.action.toUpperCase())} · ${esc(t.robot)}${who}</span>` +
        `<span class="mini-tag">${esc(TASK_LABELS[t.status] || t.status)}</span></div>`;
      }).join("")
    : `<div class="muted-line">No tasks target this item.</div>`;
  renderQrCodes(item);
}

function renderQrCodes(item) {
  const grid = $("#item-qr-grid");
  if (!grid || typeof QRCode === "undefined") return;
  const scanBase = (grid.dataset.scanUrl || "http://localhost:5002").replace(/\/$/, "");
  const origin = window.location.origin;
  const codes = [
    { label: "Mobile scan", hint: "Floor PWA — scan to act", text: `${scanBase}/i/${item.id}` },
    { label: "Staff item page", hint: "Warehouse record", text: `${origin}/items/${item.id}` },
    { label: "Robot payload", hint: "Device lookup token", text: `WH:ITEM:${item.id}` },
  ];
  if (item.sku) {
    codes.push({ label: "SKU barcode", hint: item.sku, text: `WH:SKU:${item.sku}` });
  } else {
    codes.push({ label: "Item API", hint: `GET /api/items/${item.id}`, text: `${origin}/api/items/${item.id}` });
  }
  grid.innerHTML = codes.map((c, i) =>
    `<div class="qr-card"><div class="qr-label">${esc(c.label)}</div>` +
    `<div id="qr-slot-${i}"></div>` +
    `<div class="qr-hint">${esc(c.hint)}</div></div>`,
  ).join("");
  codes.forEach((c, i) => {
    // eslint-disable-next-line no-undef
    new QRCode($(`#qr-slot-${i}`), {
      text: c.text,
      width: 120,
      height: 120,
      correctLevel: QRCode.CorrectLevel.M,
    });
  });
}

async function load() {
  const [item, boot] = await Promise.all([
    api.get(`/api/items/${itemId}`),
    api.get("/api/bootstrap"),
  ]);
  if (!item) return;
  if (item.error) {
    clearLocLoading();
    $("#detail-name").textContent = "NOT FOUND";
    $("#loc-card").innerHTML = `<div class="muted-line">Item not found.</div>`;
    return;
  }
  const tree = boot?.tree || [];
  const items = boot?.items || [];
  const rbts = boot?.robots || [];
  const tsk = boot?.tasks || [];
  const settings = boot?.settings || {};
  allItems = items || []; robots = rbts || []; tasks = tsk || [];
  treeData = tree || [];
  statusColors = settings?.status_colors || {}; statusLabels = settings?.status_labels || {};
  const f = $("#detail-form");
  f.name.value = item.name;
  f.sku.value = item.sku || "";
  delete skuInput?.dataset.userEdited;
  f.notes.value = item.notes || "";
  f.quantity.value = item.quantity ?? 1;
  fillShelfSelect(tree, item.shelf_id);
  if (!item.sku) fillSku();
  renderLoc(item);
  renderExtra(item);
}

$("#detail-form").onsubmit = async (e) => {
  e.preventDefault();
  const f = e.target;
  const shelfId = Number(shelfPicker.getValue());
  if (!shelfId) return toast("Pick a bay first", true);
  const body = {
    name: f.name.value.trim(),
    sku: resolveSku(shelfId),
    shelf_id: shelfId,
    notes: f.notes.value.trim(),
    quantity: Math.max(1, Number(f.quantity.value) || 1),
  };
  if (!body.name) return toast("Enter a product name", true);
  try {
    const updated = await api.send("PUT", `/api/items/${itemId}`, body);
    if (updated) { await load(); }
    toast("Saved");
  } catch (err) { toast(err.message, true); }
};

$("#delete-item").onclick = async () => {
  if (!(await askConfirm("Delete this item permanently?", "Delete item"))) return;
  await api.send("DELETE", `/api/items/${itemId}`);
  location.href = "/items";
};

load();
