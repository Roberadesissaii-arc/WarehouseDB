// Loading skeletons — mirror real layout (intro, create card, deck, board tiles).
import { $ } from "./dom.js";

const repeat = (n, fn) => Array.from({ length: n }, (_, i) => fn(i)).join("");

const VIEW_INTRO_SKEL = () =>
  `<div class="skel skel-view-intro" aria-hidden="true">` +
  `<div class="skel-block skel-intro-kicker"></div>` +
  `<div class="skel-block skel-intro-text"></div>` +
  `</div>`;

const CREATE_CARD_SKEL = (variant) =>
  `<div class="skel skel-create-card skel-create-card--${variant}" aria-hidden="true">` +
  `<div class="skel-block skel-create-plus"></div>` +
  `<div class="skel-block skel-create-label"></div>` +
  `<div class="skel-block skel-create-sub"></div>` +
  `</div>`;

const TAG_SKEL = () =>
  `<div class="skel skel-tag" aria-hidden="true">` +
  `<div class="skel-block skel-line-lg"></div>` +
  `<div class="skel-block skel-line-sm"></div>` +
  `<div class="skel-block skel-line-bar"></div>` +
  `<div class="skel-block skel-line-loc"></div>` +
  `</div>`;

const BOT_SKEL = () =>
  `<div class="skel skel-bot" aria-hidden="true">` +
  `<div class="skel-block skel-bot-img"></div>` +
  `<div class="skel-bot-body">` +
  `<div class="skel-bot-top">` +
  `<div class="skel-block skel-bot-dot"></div>` +
  `<div class="skel-block skel-bot-name"></div>` +
  `</div>` +
  `<div class="skel-block skel-bot-badge"></div>` +
  `<div class="skel-block skel-bot-loc"></div>` +
  `</div>` +
  `</div>`;

const TASK_SKEL = () =>
  `<div class="skel skel-task" aria-hidden="true">` +
  `<div class="skel-task-top">` +
  `<div class="skel-block skel-task-id"></div>` +
  `<div class="skel-block skel-task-action"></div>` +
  `<div class="skel-block skel-task-status"></div>` +
  `</div>` +
  `<div class="skel-block skel-task-robot"></div>` +
  `<div class="skel-block skel-task-route"></div>` +
  `</div>`;

const FLEET_GROUP_SKEL = () =>
  `<div class="skel skel-fleet-group" aria-hidden="true">` +
  `<div class="skel-block skel-fleet-group-title"></div>` +
  `<div class="skel-fleet-group-line"></div>` +
  `<div class="skel-block skel-fleet-group-n"></div>` +
  `</div>`;

const MAP_SKEL = () =>
  `<div class="skel skel-map-canvas" aria-hidden="true">` +
  `<div class="skel-map-toolbar">` +
  `<div class="skel-block skel-map-toolbar-title"></div>` +
  `<div class="skel-map-stats">` +
  repeat(4, () => `<div class="skel-block skel-map-stat"></div>`) +
  `</div>` +
  `</div>` +
  `<div class="skel-map-legend">` +
  repeat(4, () => `<div class="skel-block skel-map-legend-item"></div>`) +
  `</div>` +
  `<div class="skel-map-floor-grid">` +
  repeat(3, () =>
    `<div class="skel skel-map-card">` +
    `<div class="skel-block skel-map-card-tag"></div>` +
    `<div class="skel-block skel-map-card-head"></div>` +
    `<div class="skel-block skel-map-card-meta"></div>` +
    `<div class="skel-map-bays">` +
    repeat(3, () => `<div class="skel-block skel-map-bay"></div>`) +
    `</div>` +
    `</div>`,
  ) +
  `</div>` +
  `</div>`;

const COUNTER_SKELS = [
  { hot: false, labelW: 88 },
  { hot: false, labelW: 36 },
  { hot: true, labelW: 96 },
  { hot: false, labelW: 52 },
  { hot: false, labelW: 76 },
];

/** Navigation deck skeleton — warehouse / aisle chips + bay tiles (shown on every view). */
export function renderDeckSkeleton() {
  // The deck is a persistent navigator shown on every view, so always render
  // its loading skeleton (no view gating).
  const deck = document.querySelector(".deck");
  if (deck) {
    deck.classList.add("deck--loading");
    deck.style.display = "";
  }

  $("#wh-row").innerHTML =
    `<div class="skel skel-chip skel-chip-wh"></div>` +
    `<div class="skel skel-chip skel-chip-wh"></div>` +
    `<div class="skel skel-chip skel-chip-wh"></div>` +
    `<div class="skel skel-chip skel-chip-add"></div>`;

  $("#sec-row").innerHTML =
    `<div class="skel skel-chip skel-chip-all"></div>` +
    `<div class="skel skel-chip skel-chip-sec"></div>` +
    `<div class="skel skel-chip skel-chip-sec"></div>` +
    `<div class="skel skel-chip skel-chip-sec"></div>` +
    `<div class="skel skel-chip skel-chip-add"></div>`;

  const baysLine = $("#bays-line");
  const binRow = $("#bin-row");
  if (baysLine && binRow) {
    baysLine.style.display = "";
    binRow.innerHTML =
      `<div class="skel skel-bin skel-bin-all"></div>` +
      repeat(4, () => `<div class="skel skel-bin"></div>`) +
      `<div class="skel skel-chip skel-chip-add skel-chip-add-bin"></div>`;
  }
}

/** Top stat counters — pulse baked-in HTML until real counts arrive. */
export function renderCountersSkeleton() {
  const row = $("#counters");
  if (!row || row.querySelector(".counter:not(.counter--skel)")) {
    row?.classList.add("counters--loading");
    return;
  }
  row.classList.add("counters--loading");
  row.innerHTML = COUNTER_SKELS.map(({ hot, labelW }) =>
    `<div class="counter counter--skel${hot ? " hot" : ""}">` +
    `<span class="skel-block skel-counter-n"></span>` +
    `<span class="skel-block skel-counter-l" style="width:${labelW}px"></span>` +
    `</div>`,
  ).join("");
}

/** Home board — loading placeholders in #board-dynamic only (shell stays visible). */
export function renderBoardSkeleton(view = "items") {
  const board = $("#board");
  const dynamic = $("#board-dynamic");
  if (!board || !dynamic) return;
  board.classList.add("board--loading");
  if (view === "map") board.className = "board map-board board--loading";

  if (view === "fleet") {
    dynamic.innerHTML = repeat(5, () => BOT_SKEL());
  } else if (view === "tasks") {
    dynamic.innerHTML = repeat(4, () => TASK_SKEL());
  } else if (view === "map") {
    dynamic.innerHTML = MAP_SKEL();
  } else {
    board.className = "board board--loading";
    dynamic.innerHTML = repeat(7, () => TAG_SKEL());
  }
}

/** Item detail — location panel placeholder. */
export function renderLocSkeleton() {
  const card = $("#loc-card");
  if (!card) return;
  card.classList.add("loc-card--loading");
  card.innerHTML =
    `<div class="skel-block skel-loc-path"></div>` +
    repeat(7, () => `<div class="skel-loc-row"><div class="skel-block skel-loc-k"></div><div class="skel-block skel-loc-v"></div></div>`) +
    `<div class="skel-block skel-loc-api"></div>`;
}

/** Board tab title + count badge while data loads. */
export function renderBoardMetaSkeleton(view = "items") {
  const title = $("#board-title");
  const count = $("#board-count");
  if (!title || !count) return;
  if (title.textContent?.trim()) return;
  document.querySelector(".board-meta")?.classList.add("board-meta--loading");
  const titleW = view === "map" ? 120 : view === "fleet" ? 72 : view === "tasks" ? 148 : 108;
  title.innerHTML = `<span class="skel-block skel-board-title" style="width:${titleW}px"></span>`;
  count.className = "board-count board-count--skel";
  count.innerHTML = `<span class="skel-block skel-board-count"></span>`;
}

export function clearBoardMetaLoading() {
  document.querySelector(".board-meta")?.classList.remove("board-meta--loading");
  const count = $("#board-count");
  count?.classList.remove("board-count--skel");
}

export function clearDeckLoading() {
  document.querySelector(".deck")?.classList.remove("deck--loading");
}

export function clearCountersLoading() {
  $("#counters")?.classList.remove("counters--loading");
}

export function clearBoardLoading() {
  $("#board")?.classList.remove("board--loading");
}

export function clearLocLoading() {
  const card = $("#loc-card");
  if (!card) return;
  card.classList.remove("loc-card--loading");
}

export function renderSkeleton() {
  renderCountersSkeleton();
  renderDeckSkeleton();
  renderBoardMetaSkeleton();
  renderBoardSkeleton();
}

export function clearSkeletonState() {
  clearCountersLoading();
  clearDeckLoading();
  clearBoardLoading();
  clearBoardMetaLoading();
}
