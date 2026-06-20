// Shared application state for the board, plus data loading.
import { api } from "./api.js";
import { normalizeHomePayload } from "./homeBays.js";

const CACHE_PREFIX = "wdb-board-v1";

export const store = {
  tree: [],
  items: [],
  robots: [],
  tasks: [],
  homeBays: [],
  homeWarehouseName: "Robot Home",
  settings: { status_labels: {}, status_colors: {} },
  shelfMap: {},                         // shelf_id -> "Warehouse / Section / Bay"
  sel: { w: null, s: null, shelf: null },
  view: "items",                        // items | fleet | tasks | map
  loading: false,
  ready: false,                         // true after first successful load in this tab
};

export const TASK_STATUS_LABELS = {
  queued: "Queued", in_progress: "In progress", done: "Done", cancelled: "Cancelled",
};

export const whById = (id) => store.tree.find((w) => w.id == id);
export const secById = (w, id) => w && w.sections.find((s) => s.id == id);
export const statusLabel = (k) => store.settings.status_labels[k] || k;

function cacheKey() {
  const user = document.body?.dataset?.warehouseUser || "";
  return user ? `${CACHE_PREFIX}:${user}` : CACHE_PREFIX;
}

function rebuildShelfMap(tree) {
  store.shelfMap = {};
  for (const w of tree) {
    for (const s of w.sections) {
      for (const sh of s.shelves) {
        store.shelfMap[sh.id] = `${w.name} / ${s.name} / ${sh.code}`;
      }
    }
  }
}

function applyPayload(tree, items, robots, tasks, settings, homePayload, sel) {
  store.tree = tree || [];
  store.items = items || [];
  store.robots = robots || [];
  store.tasks = tasks || [];
  const home = normalizeHomePayload(homePayload);
  store.homeBays = home.bays;
  store.homeWarehouseName = home.warehouse_name;
  applySettings(settings);
  rebuildShelfMap(store.tree);
  if (sel && typeof sel === "object") store.sel = { ...store.sel, ...sel };
  normalizeSelection();
}

function normalizeSelection() {
  const { tree } = store;
  if (!whById(store.sel.w)) store.sel = { w: tree[0]?.id ?? null, s: null, shelf: null };
  const w = whById(store.sel.w);
  if (w && store.sel.s && !secById(w, store.sel.s)) {
    store.sel.s = null;
    store.sel.shelf = null;
  }
}

export function applySettings(s) {
  if (!s) return;
  store.settings = s;
  const root = document.documentElement.style;
  for (const [k, color] of Object.entries(s.status_colors || {})) {
    root.setProperty(`--st-${k}`, color);
  }
}

export function clearSessionCache() {
  try {
    sessionStorage.removeItem(cacheKey());
  } catch { /* ignore */ }
}

function readSessionCache() {
  try {
    const raw = sessionStorage.getItem(cacheKey());
    if (!raw) return null;
    const data = JSON.parse(raw);
    if (!data?.tree?.length && !data?.items?.length) return null;
    return data;
  } catch {
    return null;
  }
}

function writeSessionCache() {
  try {
    sessionStorage.setItem(cacheKey(), JSON.stringify({
      tree: store.tree,
      items: store.items,
      robots: store.robots,
      tasks: store.tasks,
      homeBays: store.homeBays,
      homeWarehouseName: store.homeWarehouseName,
      settings: store.settings,
      sel: store.sel,
    }));
  } catch { /* ignore quota */ }
}

/** Restore the last board snapshot from this browser tab (instant revisit). */
export function hydrateFromSessionCache() {
  const cached = readSessionCache();
  if (!cached) return false;
  applyPayload(
    cached.tree,
    cached.items,
    cached.robots,
    cached.tasks,
    cached.settings,
    { warehouse_name: cached.homeWarehouseName, bays: cached.homeBays },
    cached.sel,
  );
  store.loading = false;
  store.ready = true;
  return true;
}

export function hasBoardData() {
  return store.tree.length > 0 || store.items.length > 0;
}

export async function loadData({ silent = false } = {}) {
  const useSilent = silent || store.ready || hasBoardData();
  if (!useSilent && !hasBoardData()) {
    store.loading = true;
    _render();
  }

  const [tree, items, robots, tasks, settings, homePayload] = await (async () => {
    const boot = await api.get("/api/bootstrap");
    if (boot?.tree) {
      return [boot.tree, boot.items, boot.robots, boot.tasks, boot.settings, boot.home_bays];
    }
    return Promise.all([
      api.get("/api/tree"), api.get("/api/items"), api.get("/api/robots"),
      api.get("/api/tasks"), api.get("/api/settings"), api.get("/api/home-bays"),
    ]);
  })();

  store.loading = false;
  if (!tree) return false;

  applyPayload(tree, items, robots, tasks, settings, homePayload, store.sel);
  store.ready = true;
  writeSessionCache();
  return true;
}

// Re-render hook wired up by the board entry point.
let _render = () => {};
export const setRender = (fn) => { _render = fn; };
export const render = () => _render();

export async function reload({ silent } = {}) {
  const quiet = silent ?? hasBoardData();
  if (await loadData({ silent: quiet })) _render();
}
