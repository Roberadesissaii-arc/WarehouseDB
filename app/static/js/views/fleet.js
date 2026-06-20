// FLEET view — robots grouped by home dock. First card pairs a new robot.
import { store, statusLabel, render } from "../core/store.js";
import { bayLabel } from "../core/homeBays.js";
import { prepareAlternateView } from "../core/boardLayout.js";
import { createCard } from "../core/createCard.js";
import { viewIntro } from "../core/viewIntro.js";
import { $, el, esc } from "../core/dom.js";
import { robotImageUrl, unitById } from "../core/robotImages.js";
import { openPairRobot } from "../modals/robotModal.js";

export function startFleetLive() {
  /* robot status polling handled globally by startRobotWatch in board.js */
}

export function stopFleetLive() {
  /* no-op — global watch keeps running */
}

function robotCard(r) {
  const s = `status-${r.status}`;
  const unit = unitById(r.unit_image);
  const img = robotImageUrl(r.unit_image);
  const card = el("div", "bot",
    `<img class="bot-img" src="${img}" alt="" loading="lazy" />` +
    `<div class="bot-body">` +
    `<div class="bot-top"><span class="dot ${s}"></span><span class="bot-name">${esc(r.name)}</span></div>` +
    `<span class="bot-model">${esc(r.unit_brand || unit.brand)} · ${esc(r.unit_code || unit.code)}</span>` +
    `<span class="bot-badge ${s}">${esc(statusLabel(r.status))}</span>` +
    `<div class="bot-loc"><span class="lbl">HOME // </span>${esc(r.location)}</div>` +
    `</div>`);
  card.onclick = () => { location.href = `/robots/${r.id}`; };
  return card;
}

export function renderFleet() {
  const q = $("#search").value.trim().toLowerCase();
  const board = $("#board");
  const dynamic = prepareAlternateView();
  board.className = "board";
  dynamic.appendChild(viewIntro(
    "Robot fleet",
    "Units grouped by home base inside the robot home warehouse. Each robot gets a dock on first connect — add more bases in Settings → Fleet.",
  ));
  dynamic.appendChild(createCard({
    variant: "bot",
    label: "PAIR ROBOT",
    sub: "Register a slot for a new unit",
    onClick: openPairRobot,
  }));

  if (q) {
    const list = store.robots.filter((r) => r.paired && r.name.toLowerCase().includes(q));
    $("#board-title").textContent = `SEARCH “${q.toUpperCase()}”`;
    $("#board-count").textContent = `${list.length} ROBOT${list.length === 1 ? "" : "S"}`;
    list.forEach((r) => dynamic.appendChild(robotCard(r)));
    return;
  }

  $("#board-title").textContent = "FLEET";
  const groups = [];
  for (const bay of store.homeBays || []) {
    const bots = store.robots.filter((r) => r.paired && r.home_bay_id == bay.id);
    if (bots.length) groups.push({ name: bayLabel(bay, store.homeWarehouseName), robots: bots });
  }
  const un = store.robots.filter((r) => r.paired && !r.home_bay_id);
  if (un.length) groups.push({ name: "Unassigned", robots: un });

  const total = store.robots.filter((r) => r.paired).length;
  $("#board-count").textContent = `${total} ROBOT${total === 1 ? "" : "S"}`;

  for (const g of groups) {
    if (!g.robots.length) continue;
    dynamic.appendChild(el("div", "fleet-group", `<h3>${esc(g.name)}</h3><div class="line"></div><span class="n">${g.robots.length}</span>`));
    g.robots.forEach((r) => dynamic.appendChild(robotCard(r)));
  }
}
