// Robot-offline alerts — small cards sliding in from the bottom-right.
import { api } from "./api.js";
import { $, esc } from "./dom.js";

const prevStatus = new Map();
const dismissedUntilOnline = new Set();
let pollTimer = null;

function statusWord(status) {
  return ({
    working: "WORKING",
    idle: "IDLE",
    charging: "CHARGING",
    returning: "RETURNING",
    error: "ERROR",
    offline: "OFFLINE",
  }[status] || String(status).toUpperCase());
}

function stackEl() {
  return $("#fleet-alert-stack");
}

function removeOfflineCard(robotId) {
  const card = document.getElementById(`fleet-alert-${robotId}`);
  if (!card) return;
  card.classList.add("fleet-alert-out");
  setTimeout(() => card.remove(), 280);
}

function showOfflineCard(robot, wasStatus) {
  if (dismissedUntilOnline.has(robot.id)) return;
  const stack = stackEl();
  if (!stack || document.getElementById(`fleet-alert-${robot.id}`)) return;

  const was = wasStatus && wasStatus !== "offline" ? statusWord(wasStatus) : "ONLINE";
  const card = document.createElement("div");
  card.className = "fleet-alert-card";
  card.id = `fleet-alert-${robot.id}`;
  card.setAttribute("role", "alert");
  card.innerHTML =
    `<button type="button" class="fleet-alert-close" aria-label="Dismiss">×</button>` +
    `<span class="fleet-alert-kind">ROBOT OFFLINE</span>` +
    `<span class="fleet-alert-title">${esc(robot.name)}</span>` +
    `<span class="fleet-alert-body">Was ${esc(was)} — stopped responding</span>` +
    `<a class="fleet-alert-link" href="/robots/${robot.id}">View robot →</a>`;

  card.querySelector(".fleet-alert-close").addEventListener("click", (e) => {
    e.stopPropagation();
    dismissedUntilOnline.add(robot.id);
    removeOfflineCard(robot.id);
  });

  stack.appendChild(card);
  requestAnimationFrame(() => card.classList.add("fleet-alert-in"));
}

export function watchRobotStatuses(robots) {
  if (!robots?.length) return;

  for (const r of robots) {
    if (!r.paired) continue;
    const cur = r.status;
    const prev = prevStatus.get(r.id);

    if (prev !== undefined && prev !== "offline" && cur === "offline") {
      showOfflineCard(r, r.reported_status && r.reported_status !== "offline" ? r.reported_status : prev);
      dismissedUntilOnline.delete(r.id);
    }

    if (cur !== "offline") {
      dismissedUntilOnline.delete(r.id);
      removeOfflineCard(r.id);
    }

    prevStatus.set(r.id, cur);
  }
}

export function handleOfflineNotification(notif) {
  if (!notif || notif.kind !== "fleet") return;
  if (!/went offline/i.test(notif.title || "")) return;
  const name = (notif.title || "").replace(/ went offline$/i, "");
  const idMatch = (notif.href || "").match(/\/robots\/(\d+)/);
  const wasMatch = (notif.body || "").match(/^Was (\w+)/i);
  showOfflineCard(
    { id: idMatch ? idMatch[1] : `n-${notif.id}`, name, paired: true },
    wasMatch ? wasMatch[1].toLowerCase() : "online",
  );
}

/** Poll robot status on every page — no refresh needed when a unit drops offline. */
export function startRobotWatch(onUpdate) {
  if (pollTimer) return;
  const tick = async () => {
    const robots = await api.get("/api/robots");
    if (!robots) return;
    watchRobotStatuses(robots);
    onUpdate?.(robots);
  };
  tick();
  pollTimer = setInterval(tick, 2500);
}

export function stopRobotWatch() {
  if (!pollTimer) return;
  clearInterval(pollTimer);
  pollTimer = null;
}

export function wireFleetAlertBar() {
  /* cards wire their own dismiss — stack container only */
}
