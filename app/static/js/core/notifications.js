// Masthead alerts — live SSE feed + dropdown panel under ALERTS button.
import { api } from "./api.js";
import { isMobileViewport } from "./viewport.js";
import { $, esc, toast } from "./dom.js";
import { handleOfflineNotification } from "./fleetAlerts.js";
import { alertSound, maybeDesktop, loadSoundPrefs } from "./sound.js";

let items = [];
let lastUnread = 0;
let lastLatestId = 0;
let feedReady = false;
let eventSource = null;
let fallbackTimer = null;

function timeAgo(ts) {
  if (!ts) return "";
  // Stored timestamps are UTC (SQLite datetime('now')) with no offset — append
  // "Z" so JS doesn't misread them as local time.
  const d = new Date(ts.replace(" ", "T") + "Z");
  if (Number.isNaN(d.getTime())) return ts;
  const sec = Math.max(0, Math.floor((Date.now() - d.getTime()) / 1000));
  if (sec < 60) return "just now";
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
  if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`;
  return d.toLocaleDateString();
}

function kindLabel(kind) {
  return ({ task: "TASK", fleet: "FLEET", store: "STORE", system: "SYSTEM" }[kind] || kind).toUpperCase();
}

function setBadge(unread) {
  const badge = $("#notif-badge");
  if (!badge) return;
  badge.textContent = unread > 99 ? "99+" : String(unread);
  badge.classList.toggle("hidden", unread === 0);
  $("#notif-btn")?.classList.toggle("has-unread", unread > 0);
}

function normalizeHref(href) {
  if (!href) return href;
  try {
    const u = new URL(href, location.origin);
    const view = u.searchParams.get("view");
    if (u.pathname === "/" && view && ["items", "fleet", "tasks", "map"].includes(view)) {
      return view === "items" ? "/items" : `/${view}`;
    }
    const taskMatch = u.pathname.match(/^\/tasks\/(\d+)$/);
    if (taskMatch) {
      const id = taskMatch[1];
      return isMobileViewport() ? `/tasks/${id}` : `/tasks?edit=${id}`;
    }
  } catch { /* ignore */ }
  return href;
}

function renderList() {
  const box = $("#notif-list");
  if (!box) return;
  if (!items.length) {
    box.innerHTML = `<div class="notif-empty">No alerts yet — robot and task activity appears here in real time.</div>`;
    return;
  }
  box.innerHTML = items.map((n) =>
    `<button type="button" class="notif-card${n.read ? "" : " unread"}" data-id="${n.id}" data-href="${esc(n.href || "")}" data-ts="${esc(n.created_at || "")}">` +
    `<div class="notif-card-top">` +
    `<span class="notif-kind kind-${esc(n.kind)}">${esc(kindLabel(n.kind))}</span>` +
    `<span class="notif-time">${esc(timeAgo(n.created_at))}</span>` +
    `</div>` +
    `<span class="notif-title">${esc(n.title)}</span>` +
    (n.body ? `<span class="notif-body">${esc(n.body)}</span>` : "") +
    `</button>`,
  ).join("");

  box.querySelectorAll(".notif-card").forEach((btn) => {
    btn.onclick = () => {
      const id = Number(btn.dataset.id);
      const href = normalizeHref(btn.dataset.href);
      closePanel();
      if (href) {
        location.href = href;
        api.send("PUT", `/api/notifications/${id}/read`).catch(() => {});
        return;
      }
      api.send("PUT", `/api/notifications/${id}/read`).then(() => refresh()).catch(() => {});
    };
  });
}

// Re-stamp the relative times in place (cheap) so "just now" → "2m ago" ticks live.
function updateTimes() {
  const box = $("#notif-list");
  if (!box) return;
  box.querySelectorAll(".notif-card").forEach((card) => {
    const span = card.querySelector(".notif-time");
    if (span && card.dataset.ts) span.textContent = timeAgo(card.dataset.ts);
  });
}

function onLiveUpdate(snap) {
  const unread = snap.unread ?? 0;
  const latestId = snap.latest_id ?? 0;
  if (feedReady && latestId > lastLatestId) {
    const newest = items.find((n) => !n.read);
    if (/went offline/i.test(newest?.title || "")) {
      handleOfflineNotification(newest);
    } else if (newest?.kind === "store" && newest?.body) {
      toast(`${newest.title}: ${newest.body}`);
    } else {
      toast(newest?.title || "New alert");
    }
    alertSound(newest?.kind);
    maybeDesktop(newest);
    $("#notif-btn")?.classList.add("notif-pulse");
    setTimeout(() => $("#notif-btn")?.classList.remove("notif-pulse"), 1200);
  }
  lastUnread = unread;
  lastLatestId = latestId;
  setBadge(unread);
}

export async function refresh() {
  const [list, snap] = await Promise.all([
    api.get("/api/notifications"),
    api.get("/api/notifications/snapshot"),
  ]);
  if (!list) return;
  items = list;
  if (snap && !snap.error) onLiveUpdate(snap);
  else setBadge(items.filter((n) => !n.read).length);
  renderList();
  feedReady = true;
}

function isOpen() {
  const panel = $("#notif-panel");
  return panel && !panel.classList.contains("hidden");
}

const MOBILE_MQ = window.matchMedia("(max-width: 640px)");

function positionNotifPanel() {
  const panel = $("#notif-panel");
  const btn = $("#notif-btn");
  if (!panel || !btn || panel.classList.contains("hidden")) return;

  if (MOBILE_MQ.matches) {
    const rect = btn.getBoundingClientRect();
    panel.classList.add("is-fixed");
    panel.style.setProperty("--dropdown-top", `${Math.round(rect.bottom + 8)}px`);
    panel.style.setProperty(
      "--dropdown-max-h",
      `${Math.max(180, Math.round(window.innerHeight - rect.bottom - 16))}px`,
    );
  } else {
    panel.classList.remove("is-fixed");
    panel.style.removeProperty("--dropdown-top");
    panel.style.removeProperty("--dropdown-max-h");
  }
}

function openPanel() {
  const accountMenu = $("#account-menu");
  accountMenu?.classList.add("hidden");
  accountMenu?.classList.remove("is-fixed");
  accountMenu?.style.removeProperty("--dropdown-top");
  accountMenu?.style.removeProperty("--dropdown-max-h");
  $("#notif-panel")?.classList.remove("hidden");
  $("#notif-btn")?.setAttribute("aria-expanded", "true");
  positionNotifPanel();
  refresh();
}

export function closePanel() {
  const panel = $("#notif-panel");
  panel?.classList.add("hidden");
  panel?.classList.remove("is-fixed");
  panel?.style.removeProperty("--dropdown-top");
  panel?.style.removeProperty("--dropdown-max-h");
  $("#notif-btn")?.setAttribute("aria-expanded", "false");
}

function startLiveFeed() {
  stopLiveFeed();
  if (typeof EventSource !== "undefined") {
    eventSource = new EventSource("/api/notifications/stream");
    eventSource.onmessage = async (ev) => {
      try {
        const snap = JSON.parse(ev.data);
        const was = lastLatestId;
        onLiveUpdate(snap);
        if (snap.latest_id > was) await refresh();
        $("#notif-feed-status").textContent = "Live · warehouse activity";
        $("#notif-live")?.classList.add("on");
      } catch { /* ignore */ }
    };
    eventSource.onerror = () => {
      $("#notif-feed-status").textContent = "Reconnecting…";
      $("#notif-live")?.classList.remove("on");
      eventSource?.close();
      eventSource = null;
      startFallbackPoll();
    };
    return;
  }
  startFallbackPoll();
}

function startFallbackPoll() {
  if (fallbackTimer) return;
  fallbackTimer = setInterval(refresh, 4000);
  $("#notif-feed-status").textContent = "Polling · every few seconds";
}

function stopLiveFeed() {
  eventSource?.close();
  eventSource = null;
  if (fallbackTimer) clearInterval(fallbackTimer);
  fallbackTimer = null;
}

let timeTicker = null;
export function startPolling() {
  loadSoundPrefs();
  startLiveFeed();
  if (!timeTicker) timeTicker = setInterval(() => { if (isOpen()) updateTimes(); }, 30000);
}

export function stopPolling() {
  stopLiveFeed();
}

export function wireNotifications() {
  const btn = $("#notif-btn");
  if (!btn || btn.dataset.wired) return;
  btn.dataset.wired = "1";

  btn.addEventListener("click", (e) => {
    e.stopPropagation();
    if (isOpen()) closePanel();
    else openPanel();
  });

  $("#notif-panel")?.addEventListener("click", (e) => e.stopPropagation());

  $("#notif-read-all")?.addEventListener("click", async (e) => {
    e.stopPropagation();
    try { await api.send("PUT", "/api/notifications/read-all"); await refresh(); }
    catch { /* ignore */ }
  });

  $("#notif-clear-all")?.addEventListener("click", async (e) => {
    e.stopPropagation();
    try {
      await api.send("DELETE", "/api/notifications/clear-all");
      await refresh();
    } catch { /* ignore */ }
  });

  document.addEventListener("click", () => closePanel());

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closePanel();
  });

  window.addEventListener("resize", () => { if (isOpen()) positionNotifPanel(); });
  window.addEventListener("orientationchange", () => { if (isOpen()) positionNotifPanel(); });
  if (MOBILE_MQ.addEventListener) {
    MOBILE_MQ.addEventListener("change", () => { if (isOpen()) positionNotifPanel(); });
  }
}
