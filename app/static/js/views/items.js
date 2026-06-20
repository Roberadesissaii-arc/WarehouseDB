// ITEMS view — inventory tags, paginated. First card logs a new item.
import { store, whById, secById } from "../core/store.js";
import { prepareItemsView, setItemsShellVisible } from "../core/boardLayout.js";
import { $, el, esc } from "../core/dom.js";

const PAGE_SIZE = 20;          // items per page when searching (no create card)
const ITEMS_PER_PAGE = 19;     // items per page + 1 create card = 20 tiles on the board
let page = 0;
let lastKey = "";

export function renderItems() {
  const q = $("#search").value.trim().toLowerCase();
  let list, title;
  if (q) {
    list = store.items.filter((it) => {
      const hay = [
        it.name,
        it.sku || "",
        it.location.path,
        it.location.shelf || "",
      ].join(" ").toLowerCase();
      return hay.includes(q);
    });
    title = `SEARCH “${q.toUpperCase()}”`;
  } else {
    const { w: wid, s: sid, shelf } = store.sel;
    list = store.items.filter((it) =>
      it.location.warehouse_id == wid &&
      (!sid || it.location.section_id == sid) &&
      (!shelf || it.shelf_id == shelf));
    const w = whById(wid), s = secById(w, sid);
    title = !w ? "NO WAREHOUSE" : shelf ? `BAY ${store.shelfMap[shelf].split(" / ").pop()}` : s ? s.name.toUpperCase() : w.name.toUpperCase();
  }

  // reset to the first page whenever the filter/search changes
  const key = q + "|" + JSON.stringify(store.sel);
  if (key !== lastKey) { page = 0; lastKey = key; }
  const perPage = q ? PAGE_SIZE : ITEMS_PER_PAGE;
  const pages = Math.max(1, Math.ceil(list.length / perPage));
  if (page >= pages) page = pages - 1;
  const slice = list.slice(page * perPage, page * perPage + perPage);

  $("#board-title").textContent = title;
  $("#board-count").textContent = `${list.length} ITEM${list.length === 1 ? "" : "S"}`;

  const board = $("#board");
  const dynamic = prepareItemsView();
  board.className = "board";
  setItemsShellVisible(!q);
  dynamic.innerHTML = "";

  if (!list.length) {
    if (q) dynamic.appendChild(el("div", "empty", `<div class="msg">No matches</div>`));
    return;
  }
  for (const it of slice) {
    const segs = it.location.path.split(" / ").map((x) => `<span class="seg">${esc(x)}</span>`).join(`<span class="arrow">→</span>`);
    const tag = el("div", "tag",
      `<div class="name">${esc(it.name)}</div>` +
      `<span class="sku ${it.sku ? "" : "empty"}">${it.sku ? esc(it.sku) : "NO SKU"}</span>` +
      `<div class="barcode"></div>` +
      `<div class="loc">${segs}</div>`);
    tag.onclick = () => { location.href = `/items/${it.id}`; };
    dynamic.appendChild(tag);
  }

  if (pages > 1) dynamic.appendChild(buildPager(pages, list.length));
}

function buildPager(pages, total) {
  const pager = el("div", "pager");
  const prev = el("button", "btn btn-line" + (page === 0 ? " disabled" : ""), "← PREV");
  const next = el("button", "btn btn-line" + (page >= pages - 1 ? " disabled" : ""), "NEXT →");
  prev.disabled = page === 0;
  next.disabled = page >= pages - 1;
  prev.onclick = () => { page--; renderItems(); };
  next.onclick = () => { page++; renderItems(); };
  const info = el("span", "pager-info", `PAGE ${page + 1} / ${pages} · ${total} items`);
  pager.append(prev, info, next);
  return pager;
}
