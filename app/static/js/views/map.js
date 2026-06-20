// MAP view — warehouse floor plan: sections, bays, and live robot positions.
import { api } from "../core/api.js";
import { store, whById } from "../core/store.js";
import { prepareAlternateView } from "../core/boardLayout.js";
import { $, el, esc } from "../core/dom.js";

let liveTimer = null;

const LEGEND = [
  ["working", "Working"],
  ["idle", "Idle"],
  ["charging", "Charging"],
  ["returning", "Returning"],
  ["error", "Error"],
  ["offline", "Offline"],
];

function bayChip(sh) {
  const stocked = sh.item_count > 0;
  return `<span class="map-bay${stocked ? " has-stock" : ""}">${esc(sh.code)}<b>${sh.item_count}</b></span>`;
}

function sectionCard(w, s, index) {
  const items = s.shelves.reduce((a, sh) => a + sh.item_count, 0);
  const card = el("div", "map-card");
  card.innerHTML =
    `<div class="map-zone-tag">ZONE ${String(index + 1).padStart(2, "0")}</div>` +
    `<div class="map-card-head">` +
    `<h3>${esc(s.name)}</h3>` +
    `<span class="map-count">work zone</span>` +
    `</div>` +
    `<div class="map-card-meta">${esc(w.name)} · ${s.shelves.length} bays · ${items} items</div>` +
    `<div class="map-bays-label">Bays</div>` +
    `<div class="map-bays">${s.shelves.map(bayChip).join("") || `<span class="map-bay empty">no bays</span>`}</div>`;
  return card;
}

function mapLegend() {
  return `<div class="map-legend">${LEGEND.map(([k, l]) =>
    `<span class="map-legend-item"><span class="dot status-${k}"></span>${l}</span>`,
  ).join("")}</div>`;
}

function mapStats(w) {
  const sections = w.sections.length;
  const bays = w.sections.reduce((a, s) => a + s.shelves.length, 0);
  const items = w.sections.reduce((a, s) => a + s.shelves.reduce((b, sh) => b + sh.item_count, 0), 0);
  const online = store.robots.filter((r) => r.status !== "offline").length;
  return `<div class="map-stats">` +
    `<span><b>${sections}</b> zones</span>` +
    `<span><b>${bays}</b> bays</span>` +
    `<span><b>${items}</b> items</span>` +
    `<span class="map-stats-live"><b>${online}</b> robots online</span>` +
    `</div>`;
}

export function renderMap() {
  const w = whById(store.sel.w);
  const board = $("#board");
  const dynamic = prepareAlternateView();
  board.className = "board map-board";
  $("#board-title").textContent = w ? `MAP // ${w.name.toUpperCase()}` : "MAP";
  $("#board-count").innerHTML = `${store.robots.length} ROBOTS <span class="live-dot"></span>LIVE`;

  if (!w) {
    dynamic.appendChild(el("div", "map-empty-state",
      `<div class="map-empty-icon">◎</div>` +
      `<p class="map-empty-title">No warehouse selected</p>` +
      `<p class="map-empty-sub">Pick a warehouse from the deck above to view its floor plan.</p>`));
    return;
  }

  const canvas = el("div", "map-canvas");
  canvas.innerHTML =
    `<div class="map-toolbar">` +
    `<div class="map-toolbar-title"><span class="map-toolbar-kicker">Floor plan</span>${esc(w.name)}</div>` +
    mapStats(w) +
    `</div>` +
    mapLegend();

  const grid = el("div", "map-floor-grid");
  w.sections.forEach((s, i) => grid.appendChild(sectionCard(w, s, i)));

  if (!w.sections.length) {
    grid.appendChild(el("div", "map-empty-state map-empty-inline",
      `<p class="map-empty-title">No sections yet</p>` +
      `<p class="map-empty-sub">Add sections in Settings to build your floor map.</p>`));
  }

  canvas.appendChild(grid);
  dynamic.appendChild(canvas);
}

export function startMapLive() {
  stopMapLive();
  liveTimer = setInterval(async () => {
    if (store.view !== "map") return;
    const robots = await api.get("/api/robots");
    if (robots) { store.robots = robots; renderMap(); }
  }, 5000);
}

export function stopMapLive() {
  if (liveTimer) { clearInterval(liveTimer); liveTimer = null; }
}
