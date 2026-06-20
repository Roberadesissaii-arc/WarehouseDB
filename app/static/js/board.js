// Board page entry point — wires the deck, views, tabs, search, and modals.
import { store, loadData, hydrateFromSessionCache, hasBoardData, setRender, render } from "./core/store.js";
import { $ } from "./core/dom.js";
import { isMobileViewport } from "./core/viewport.js";
import { openTaskById } from "./modals/taskModal.js";
import { renderBoardSkeleton, renderCountersSkeleton, renderDeckSkeleton, clearSkeletonState } from "./core/skeleton.js";
import { watchRobotStatuses, wireFleetAlertBar, startRobotWatch } from "./core/fleetAlerts.js";
import { renderDeck } from "./views/deck.js";
import { renderItems } from "./views/items.js";
import { renderFleet } from "./views/fleet.js";
import { renderTasks } from "./views/tasks.js";
import { renderMap, startMapLive, stopMapLive } from "./views/map.js";
import { startFleetLive, stopFleetLive } from "./views/fleet.js";
import { markBoardTabScroll, scrollBoardContentIntoView, setItemsShellVisible } from "./core/boardLayout.js";
import { newItem } from "./modals/itemModal.js";

const boardPage = document.querySelector(".board-page");
const routeView = boardPage?.dataset.activeView;
if (routeView && ["items", "fleet", "tasks", "map"].includes(routeView)) {
  store.view = routeView;
}

const pad = (n) => String(n).padStart(2, "0");

function renderCounters() {
  let bays = 0; for (const w of store.tree) for (const s of w.sections) bays += s.shelves.length;
  const open = store.tasks.filter((t) => t.status === "queued" || t.status === "in_progress").length;
  $("#counters").innerHTML =
    `<div class="counter"><span class="n">${pad(store.tree.length)}</span><span class="l">Warehouses</span></div>` +
    `<div class="counter"><span class="n">${pad(bays)}</span><span class="l">Bays</span></div>` +
    `<div class="counter hot"><span class="n">${pad(store.items.length)}</span><span class="l">Items on file</span></div>` +
    `<div class="counter"><span class="n">${pad(store.robots.length)}</span><span class="l">Robots</span></div>` +
    `<div class="counter"><span class="n">${pad(open)}</span><span class="l">Open tasks</span></div>`;
}

function renderView() {
  if (store.view === "fleet") return renderFleet();
  if (store.view === "map") return renderMap();
  if (store.view === "tasks") return renderTasks();
  renderItems();
}

function showLoadingShell() {
  setItemsShellVisible(store.view === "items");
  renderCountersSkeleton();
  renderDeckSkeleton(store.view);
  renderBoardSkeleton(store.view);
}

function fullRender() {
  if (store.loading && !hasBoardData()) {
    showLoadingShell();
    return;
  }
  clearSkeletonState();
  renderCounters();
  renderDeck();
  renderView();
  scrollBoardContentIntoView();
}
setRender(fullRender);

const restoredFromCache = hydrateFromSessionCache();
if (restoredFromCache) {
  fullRender();
} else {
  store.loading = true;
  showLoadingShell();
}

$("#shell-new-item")?.addEventListener("click", newItem);

function maybeOpenTaskFromQuery() {
  const editId = new URLSearchParams(location.search).get("edit");
  if (!editId || store.view !== "tasks") return;
  if (isMobileViewport()) {
    location.replace(`/tasks/${editId}`);
    return;
  }
  openTaskById(editId);
  history.replaceState(null, "", location.pathname);
}

// ---- wiring ----
document.querySelectorAll(".vtab").forEach((tab) => {
  tab.addEventListener("click", () => {
    if (isMobileViewport(900)) markBoardTabScroll();
  });
});

wireFleetAlertBar();

let searchTimer;
$("#search").oninput = () => { clearTimeout(searchTimer); searchTimer = setTimeout(renderView, 150); };

document.querySelectorAll(".modal").forEach((m) => (m.onclick = (e) => {
  if (e.target === m && m.id !== "prompt-modal" && m.id !== "confirm-modal") m.classList.add("hidden");
}));
document.addEventListener("keydown", (e) => { if (e.key === "Escape") document.querySelectorAll(".modal").forEach((m) => m.classList.add("hidden")); });

// Signature of only the robot fields the board actually renders. The status poll
// runs every few seconds (updating last_seen_at etc.); we re-render only when one
// of these visible fields changes, so cards and their images never flicker when
// nothing on screen has actually changed.
function robotsRenderSignature(robots) {
  return (robots || [])
    .map((r) => `${r.id}|${r.status}|${r.name}|${r.location}|${r.home_bay_id}|${r.paired ? 1 : 0}|${r.unit_image}|${r.unit_brand}|${r.unit_code}`)
    .join("~");
}

// ---- boot ----
(async () => {
  if (await loadData({ silent: true })) {
    watchRobotStatuses(store.robots);
    let lastRobotsSig = robotsRenderSignature(store.robots);
    startRobotWatch((robots) => {
      store.robots = robots;
      const sig = robotsRenderSignature(robots);
      if (sig === lastRobotsSig) return; // nothing visible changed — update silently, no flicker
      lastRobotsSig = sig;
      if (store.view === "fleet" || store.view === "tasks" || store.view === "map") fullRender();
    });
    fullRender();
    maybeOpenTaskFromQuery();
    if (store.view === "map") startMapLive();
    if (store.view === "fleet" || store.view === "tasks") startFleetLive();
  }
})();
