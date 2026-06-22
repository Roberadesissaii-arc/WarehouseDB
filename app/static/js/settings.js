// Settings page logic.
import { clearSessionCache } from "./core/store.js";
import { homeBayOptionsHtml, wireHomeBayCustom, resolveHomeBaySelection, normalizeHomePayload, bayLabel } from "./core/homeBays.js";
import { mountUnitPicker } from "./core/unitPicker.js";
import { unitById } from "./core/robotImages.js";
import { playSound, unlockAudio, applyPrefs } from "./core/sound.js";
import {
  enablePushForPlatform,
  isMobileDevice,
  permissionStatusText,
  pushPermission,
  showPushNotification,
} from "./core/pushNotifications.js";

const STATUS_ORDER = ["working", "idle", "charging", "returning", "error", "offline"];

const api = {
  async get(url) { const r = await fetch(url); if (r.status === 401) return (location.href = "/login"); return r.json(); },
  async send(method, url, body) {
    const res = await fetch(url, { method, headers: { "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : undefined });
    if (res.status === 401) { location.href = "/login"; return; }
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || "Request failed");
    return data;
  },
};

const $ = (s) => document.querySelector(s);
function toast(msg, isError) { const t = $("#toast"); t.textContent = msg; t.className = "toast" + (isError ? " error" : ""); setTimeout(() => t.classList.add("hidden"), 2400); }
const esc = (s) => (s ?? "").toString().replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

function askConfirm(message, title = "Confirm") {
  return new Promise((resolve) => {
    $("#confirm-title").textContent = title;
    $("#confirm-msg").textContent = message;
    $("#confirm-modal").classList.remove("hidden");
    const done = (v) => { $("#confirm-yes").onclick = null; $("#confirm-no").onclick = null; $("#confirm-modal").classList.add("hidden"); resolve(v); };
    $("#confirm-yes").onclick = () => done(true);
    $("#confirm-no").onclick = () => done(false);
  });
}

function askPassword(message, title = "Confirm password") {
  return new Promise((resolve) => {
    $("#password-title").textContent = title;
    $("#password-msg").textContent = message;
    const inp = $("#password-input");
    inp.value = "";
    $("#password-modal").classList.remove("hidden");
    const done = (val) => {
      $("#password-form").onsubmit = null;
      $("#password-cancel").onclick = null;
      $("#password-modal").classList.add("hidden");
      resolve(val);
    };
    $("#password-form").onsubmit = (e) => { e.preventDefault(); done(inp.value || null); };
    $("#password-cancel").onclick = () => done(null);
    setTimeout(() => inp.focus(), 30);
  });
}

let settingsCache = null;
let orgCache = null;
let fleetRobots = [];
const fleetUnitPicker = { getValue: () => 1, getBrand: () => "", reset: () => {} };

function ensureFleetUnitPicker() {
  const mount = $("#fleet-unit-picker");
  if (!mount) return fleetUnitPicker;
  return mountUnitPicker(mount, {
    hiddenInput: $("#fleet-unit-image"),
    selectedLabelEl: $("#fleet-unit-selected"),
  });
}

async function load() {
  const [s, org] = await Promise.all([api.get("/api/settings"), api.get("/api/organization")]);
  if (!s) return;
  settingsCache = s;

  const rows = $("#status-rows"); rows.innerHTML = "";
  for (const key of STATUS_ORDER) {
    const row = document.createElement("div");
    row.className = "status-row";
    row.innerHTML =
      `<span class="status-key">${key}</span>` +
      `<input class="st-label" data-key="${key}" value="${esc(s.status_labels[key] || key)}" />` +
      `<input class="st-color" type="color" data-key="${key}" value="${esc(s.status_colors[key] || "#888888")}" />`;
    rows.appendChild(row);
  }

  if (org) {
    orgCache = org;
    settingsCache.org_name = org.org_name;
    renderGeneralOverview(org);
  }
  renderFleetAssignSettings(s);
}

function renderFleetAssignSettings(s) {
  const box = $("#fleet-assign-backlog");
  if (!box) return;
  box.checked = Boolean(s?.fleet?.assign_backlog_on_pair);
}

$("#fleet-assign-form")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const res = await api.send("PUT", "/api/settings", {
      fleet: { assign_backlog_on_pair: $("#fleet-assign-backlog").checked },
    });
    if (res && settingsCache) settingsCache.fleet = res.fleet;
    toast("Task assignment saved");
  } catch (err) { toast(err.message, true); }
});

function renderGeneralOverview(org) {
  syncOrgUi(org);

  const tile = (n, l, on = false) =>
    `<div class="org-stat${on ? " on" : ""}"><span class="n">${esc(n)}</span><span class="l">${esc(l)}</span></div>`;
  const name = (org.org_name || "").trim();
  const overview = $("#org-overview");
  if (overview) {
    overview.className = "org-overview";
    overview.innerHTML =
      tile(name || "—", "Current name", Boolean(name)) +
      tile(String(org.max_length || 120), "Max characters") +
      tile(org.updated_at ? "Saved" : "Default", org.updated_at ? "In database" : "Not customized");
  }

  const where = $("#org-where-list");
  if (where && Array.isArray(org.shown_on)) {
    where.innerHTML = org.shown_on.map((p) => `<li>${esc(p.label)}</li>`).join("");
  }
}

function orgPreviewText(name, fallback) {
  const trimmed = (name || "").trim();
  return trimmed || fallback || "/// physical inventory & fleet control";
}

function formatOrgUpdated(iso) {
  if (!iso) return "Not saved yet";
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "Saved";
    return `Last saved ${d.toLocaleString()}`;
  } catch {
    return "Saved";
  }
}

function syncOrgUi(org) {
  const max = org?.max_length || 120;
  const name = org?.org_name ?? "";
  const input = $("#org-name");
  if (input && document.activeElement !== input) input.value = name;
  const preview = $("#org-preview-sub");
  if (preview) preview.textContent = orgPreviewText(input?.value ?? name, org?.fallback_subtitle);
  const count = $("#org-char-count");
  if (count) count.textContent = `${(input?.value ?? name).length} / ${max}`;
  const updated = $("#org-updated-at");
  if (updated) updated.textContent = formatOrgUpdated(org?.updated_at);
}

async function loadGeneral() {
  if (orgCache) {
    renderGeneralOverview(orgCache);
    return;
  }
  const org = await api.get("/api/organization");
  if (!org) return;
  orgCache = org;
  if (settingsCache) settingsCache.org_name = org.org_name;
  renderGeneralOverview(org);
}

// ---- section navigation ----
const SECTION_LOADERS = { general: loadGeneral, system: loadSystem, fleet: loadFleet, locations: loadLocations, data: loadData, storage: loadStorage, security: loadSecurity, notifications: loadNotifications, integration: loadIntegration };

let relayPollTimer = null;

function stopRelayPoll() {
  if (relayPollTimer) clearInterval(relayPollTimer);
  relayPollTimer = null;
}

function relayModeLabel(r) {
  if (!r?.installed) return "N/A";
  if (r.mode === "named") return "Named";
  if (r.mode === "quick") return "Quick";
  if (r.named_tunnel_ready) return "Named ready";
  return "Quick ready";
}

function renderRelay(r) {
  if (!r) return;
  const installed = $("#relay-stat-installed");
  if (installed) {
    installed.classList.toggle("on", r.installed);
    installed.querySelector(".n").textContent = r.installed ? "YES" : "NO";
    installed.querySelector(".l").textContent = r.installed ? (r.version || "cloudflared") : "Not installed";
  }
  const mode = $("#relay-stat-mode");
  if (mode) {
    mode.classList.toggle("on", r.running && r.mode === "named");
    mode.querySelector(".n").textContent = relayModeLabel(r);
    mode.querySelector(".l").textContent = r.tunnel_name ? `Tunnel · ${r.tunnel_name}` : "Tunnel mode";
  }
  const live = $("#relay-stat-live");
  if (live) {
    live.classList.toggle("on", Boolean(r.url));
    live.querySelector(".n").textContent = r.url ? "LIVE" : (r.enabled && r.running ? "…" : "—");
    live.querySelector(".l").textContent = r.url_locked ? "Fixed domain" : "This server run";
  }

  const toggle = $("#relay-enabled");
  if (toggle && document.activeElement !== toggle) toggle.checked = !!r.enabled;

  const msg = $("#relay-status-msg");
  if (msg) {
    msg.classList.remove("is-ok", "is-warn", "is-blocked");
    if (!r.installed) {
      msg.textContent = "cloudflared is not on this server yet — install it during setup (deploy/CLOUDFLARE-TUNNEL.md), then enable relay here.";
      msg.classList.add("is-warn");
    } else if (r.error) {
      msg.textContent = r.error;
      msg.classList.add(r.enabled ? "is-warn" : "is-blocked");
    } else if (r.url) {
      msg.textContent = r.url_locked
        ? "Named tunnel — this address stays the same across restarts."
        : "Quick tunnel — this address stays the same until WarehouseDB restarts.";
      msg.classList.add("is-ok");
    } else if (r.enabled && r.running) {
      msg.textContent = "Starting tunnel — waiting for Cloudflare to publish your public link…";
      msg.classList.add("is-warn");
    } else if (r.enabled) {
      msg.textContent = "Relay is enabled — starting tunnel…";
      msg.classList.add("is-warn");
    } else {
      msg.textContent = "Relay is off — enable it to publish a public link while the server runs.";
    }
  }

  const box = $("#relay-url-box");
  const urlEl = $("#relay-url");
  const open = $("#relay-open");
  if (box && urlEl) {
    if (r.url) {
      box.classList.remove("hidden");
      urlEl.textContent = r.url;
      if (open) open.href = r.url;
    } else {
      box.classList.add("hidden");
      urlEl.textContent = "—";
      if (open) open.href = "#";
    }
  }
}

async function loadIntegration() {
  stopRelayPoll();
  const r = await api.get("/api/relay");
  renderRelay(r);
  if (r?.enabled && r?.installed && !r?.url) {
    relayPollTimer = setInterval(async () => {
      const live = await api.get("/api/relay");
      renderRelay(live);
      if (live?.url || (live?.error && !live.error.includes("Waiting"))) stopRelayPoll();
    }, 3000);
  }
}

$("#relay-form")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const res = await api.send("PUT", "/api/settings", { relay: { enabled: $("#relay-enabled").checked } });
    if (res?.relay && settingsCache) settingsCache.relay = res.relay;
    toast("Warehouse Relay saved");
    loadIntegration();
  } catch (err) { toast(err.message, true); }
});

$("#relay-refresh")?.addEventListener("click", () => loadIntegration());

$("#relay-copy")?.addEventListener("click", async () => {
  const url = $("#relay-url")?.textContent?.trim();
  if (!url || url === "—") return;
  try {
    await navigator.clipboard.writeText(url);
    toast("Public address copied");
  } catch { toast("Could not copy address", true); }
});

// Generic "copy this command/text" buttons (e.g. the Add-more-apps installers).
document.querySelectorAll("[data-copy]").forEach((btn) => {
  btn.addEventListener("click", async () => {
    const target = document.querySelector(btn.dataset.copy);
    const text = target?.textContent?.trim();
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      const original = btn.textContent;
      btn.textContent = "COPIED";
      setTimeout(() => { btn.textContent = original; }, 1500);
    } catch { toast("Could not copy", true); }
  });
});

// "Add more apps" — Install runs a no-root background install and shows progress.
const installModal = document.getElementById("install-modal");
let installPoll = null;
function stopInstallPoll() { if (installPoll) { clearInterval(installPoll); installPoll = null; } }

async function pollInstall(id) {
  let s;
  try { s = await api.get(`/api/addons/${id}/status`); } catch { return; }
  if (!s) return;
  const msg = document.getElementById("install-msg");
  const open = document.getElementById("install-open");
  const spin = document.getElementById("install-spinner");
  if (s.state === "done") {
    stopInstallPoll();
    spin?.classList.add("hidden");
    if (msg) msg.textContent = "✓ Installed and running.";
    if (open && s.url) { open.href = s.url; open.classList.remove("hidden"); }
  } else if (s.state === "error") {
    stopInstallPoll();
    spin?.classList.add("hidden");
    if (msg) msg.textContent = "Couldn't auto-install: " + (s.message || "error") + " — use the manual command below.";
  } else if (msg) {
    msg.textContent = s.message || "Installing…";
  }
}

document.querySelectorAll(".addon-install").forEach((btn) => {
  btn.addEventListener("click", async () => {
    const id = btn.dataset.id;
    document.getElementById("install-title").textContent = "Install " + (btn.dataset.name || "app");
    document.getElementById("install-cmd").textContent = btn.dataset.cmd || "";
    const msg = document.getElementById("install-msg");
    const open = document.getElementById("install-open");
    const spin = document.getElementById("install-spinner");
    if (open) { open.classList.add("hidden"); open.href = "#"; }
    spin?.classList.remove("hidden");
    if (msg) msg.textContent = "Starting…";
    installModal?.classList.remove("hidden");
    if (!id) return;
    try {
      await api.send("POST", `/api/addons/${id}/install`, {});
    } catch (err) {
      if (msg) msg.textContent = "Could not start: " + (err?.message || "error") + " — use the manual command below.";
      spin?.classList.add("hidden");
      return;
    }
    stopInstallPoll();
    installPoll = setInterval(() => pollInstall(id), 2000);
    pollInstall(id);
  });
});
document.getElementById("install-close")?.addEventListener("click", () => { stopInstallPoll(); installModal?.classList.add("hidden"); });
installModal?.addEventListener("click", (e) => { if (e.target === installModal) { stopInstallPoll(); installModal.classList.add("hidden"); } });

function showSection(sec, activeBtn) {
  document.querySelectorAll(".snav[data-sec]").forEach((b) => b.classList.toggle("active", b === activeBtn));
  document.querySelectorAll(".sset").forEach((s) => s.classList.toggle("hidden", s.dataset.sec !== sec));
  window.scrollTo(0, 0);
  SECTION_LOADERS[sec]?.();
}

document.querySelectorAll(".snav[data-sec]").forEach((btn) => {
  btn.onclick = () => showSection(btn.dataset.sec, btn);
});

// ---- Notifications section ----
function setPermStatus(el, perm) {
  if (!el) return;
  el.textContent = permissionStatusText(perm);
  el.classList.remove("is-ok", "is-warn", "is-blocked");
  if (perm === "granted") el.classList.add("is-ok");
  else if (perm === "denied" || perm === "insecure") el.classList.add("is-blocked");
  else if (perm === "unsupported") el.classList.add("is-warn");
}

function refreshNotificationPermissionUi() {
  const perm = pushPermission();
  setPermStatus($("#notif-desktop-status"), perm);
  setPermStatus($("#notif-mobile-status"), perm);
}

function loadNotifications() {
  const n = (settingsCache && settingsCache.notifications) || {};
  $("#notif-sound").checked = n.sound !== false;
  $("#notif-sound-kind").value = n.sound_kind || "chime";
  const vol = n.volume ?? 70;
  $("#notif-volume").value = vol;
  $("#notif-volume-val").textContent = vol;
  $("#notif-desktop").checked = !!n.desktop;
  $("#notif-mobile").checked = !!n.mobile;
  const kinds = n.kinds || { fleet: true, store: true, system: true };
  document.querySelectorAll(".notif-kind-check").forEach((c) => { c.checked = kinds[c.dataset.kind] !== false; });
  refreshNotificationPermissionUi();
  applyPrefs(n);
}

async function requestPlatformNotifications(platform) {
  const toggle = platform === "mobile" ? $("#notif-mobile") : $("#notif-desktop");
  const result = await enablePushForPlatform(platform, {
    onStatus: () => refreshNotificationPermissionUi(),
  });
  refreshNotificationPermissionUi();
  if (result.ok) {
    if (toggle) toggle.checked = true;
    toast(platform === "mobile" ? "Mobile notifications allowed on this phone" : "Desktop notifications allowed on this computer");
    return true;
  }
  if (toggle) toggle.checked = false;
  toast(result.message || "Could not enable notifications", true);
  return false;
}

async function handlePlatformToggle(platform, checked) {
  if (!checked) return;
  if (pushPermission() === "granted") return;
  const toggle = platform === "mobile" ? $("#notif-mobile") : $("#notif-desktop");
  if (toggle) toggle.checked = false;
  await requestPlatformNotifications(platform);
}

function testPlatformNotification(platform) {
  if (pushPermission() !== "granted") {
    toast("Allow notifications on this device first", true);
    return;
  }
  const title = platform === "mobile" ? "WarehouseDB · phone test" : "WarehouseDB · desktop test";
  const body = platform === "mobile"
    ? "Mobile notifications are working on this phone."
    : "Desktop notifications are working on this computer.";
  if (!showPushNotification(title, body, `wdb-test-${platform}`)) {
    toast("Could not show a test notification", true);
  }
}

$("#notif-volume")?.addEventListener("input", (e) => { $("#notif-volume-val").textContent = e.target.value; });

$("#notif-test")?.addEventListener("click", () => {
  unlockAudio();
  playSound($("#notif-sound-kind").value, (Number($("#notif-volume").value) || 0) / 100);
});

$("#notif-desktop")?.addEventListener("change", (e) => {
  void handlePlatformToggle("desktop", e.target.checked);
});

$("#notif-mobile")?.addEventListener("change", (e) => {
  void handlePlatformToggle("mobile", e.target.checked);
});

$("#notif-desktop-enable")?.addEventListener("click", () => {
  void requestPlatformNotifications("desktop");
});

$("#notif-mobile-enable")?.addEventListener("click", () => {
  void requestPlatformNotifications("mobile");
});

$("#notif-desktop-test")?.addEventListener("click", () => testPlatformNotification("desktop"));
$("#notif-mobile-test")?.addEventListener("click", () => testPlatformNotification("mobile"));

$("#notif-form")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const kinds = {};
  document.querySelectorAll(".notif-kind-check").forEach((c) => { kinds[c.dataset.kind] = c.checked; });
  const payload = {
    sound: $("#notif-sound").checked,
    sound_kind: $("#notif-sound-kind").value,
    volume: Number($("#notif-volume").value) || 0,
    desktop: $("#notif-desktop").checked,
    mobile: $("#notif-mobile").checked,
    kinds,
  };
  if (payload.desktop && pushPermission() !== "granted" && !isMobileDevice()) {
    toast("Use ALLOW ON THIS COMPUTER before saving desktop notifications", true);
    return;
  }
  if (payload.mobile && pushPermission() !== "granted" && isMobileDevice()) {
    toast("Use ALLOW ON THIS PHONE before saving mobile notifications", true);
    return;
  }
  try {
    const res = await api.send("PUT", "/api/settings", { notifications: payload });
    if (res && settingsCache) settingsCache.notifications = res.notifications;
    applyPrefs(res?.notifications || payload);
    toast("Notifications saved");
  } catch (err) { toast(err.message, true); }
});

let fleetHomePayload = { warehouse_name: "Robot Home", bays: [] };
wireHomeBayCustom($("#fleet-home-bay"), $("#fleet-home-bay-custom"), $("#fleet-home-bay-custom-name"));

function renderHomeBayAdmin(payload) {
  const list = $("#home-bay-list");
  if (!list) return;
  const { warehouse_name: wh, bays } = normalizeHomePayload(payload);
  fleetHomePayload = { warehouse_name: wh, bays };
  $("#home-wh-name").value = wh;
  if (!bays.length) {
    list.innerHTML = `<div class="muted-line">No home bases yet.</div>`;
    return;
  }
  list.innerHTML = bays.map((bay) =>
    `<div class="home-bay-row">` +
    `<span class="home-bay-row-label">${esc(bayLabel(bay, wh))}</span>` +
    `<button type="button" class="icon-btn home-bay-del" data-id="${bay.id}" title="Remove base"><svg class="ic"><use href="#i-trash"/></svg></button>` +
    `</div>`,
  ).join("");
  list.querySelectorAll(".home-bay-del").forEach((btn) => {
    btn.onclick = async () => {
      if (!(await askConfirm("Remove this home base?", "Delete base"))) return;
      try {
        await api.send("DELETE", `/api/home-bays/${btn.dataset.id}`);
        toast("Base removed");
        loadFleet();
      } catch (err) { toast(err.message, true); }
    };
  });
}

// ---- Fleet section ----
async function loadFleet() {
  const [robots, homeRaw] = await Promise.all([api.get("/api/robots"), api.get("/api/home-bays")]);
  if (!robots) return;
  fleetRobots = robots;
  renderHomeBayAdmin(homeRaw);
  const labels = settingsCache?.status_labels || {}, colors = settingsCache?.status_colors || {};
  const list = $("#fleet-list"); list.className = "fleet-list";
  list.innerHTML = robots.length
    ? robots.map((r) =>
        `<a class="fleet-row" href="/robots/${r.id}">` +
        `<span class="dot" style="background:${esc(colors[r.status] || "#888")}"></span>` +
        `<span class="fleet-name">${esc(r.name)}</span>` +
        `<span class="fleet-sec">${esc(r.location)}</span>` +
        `<span class="fleet-badge">${esc(labels[r.status] || r.status)}</span></a>`).join("")
    : `<div class="muted-line">No robots yet.</div>`;
  $("#fleet-home-bay").innerHTML = homeBayOptionsHtml(fleetHomePayload);
  ensureFleetUnitPicker().reset();
}

$("#home-wh-form")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const res = await api.send("PUT", "/api/home-bays/warehouse", { name: $("#home-wh-name").value.trim() });
    renderHomeBayAdmin(res);
    toast("Home warehouse name saved");
    $("#fleet-home-bay").innerHTML = homeBayOptionsHtml(fleetHomePayload);
  } catch (err) { toast(err.message, true); }
});

$("#add-home-bay-form")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target;
  try {
    await api.send("POST", "/api/home-bays", { name: f.name.value.trim() });
    f.reset();
    toast("Home base added");
    loadFleet();
  } catch (err) { toast(err.message, true); }
});

$("#add-robot-form").onsubmit = async (e) => {
  e.preventDefault();
  const f = e.target;
  const code = f.pairing_code.value.replace(/\D/g, "");
  if (code.length !== 6) return toast("Enter the 6-digit code from the robot", true);
  try {
    let home_bay_id;
    try {
      home_bay_id = await resolveHomeBaySelection($("#fleet-home-bay"), $("#fleet-home-bay-custom-name"));
    } catch (err) {
      toast(err.message, true);
      return;
    }
    const unitId = Number(f.unit_image.value || ensureFleetUnitPicker().getValue());
    await api.send("POST", "/api/robots/pair", {
      pairing_code: code,
      name: unitById(unitId).brand,
      home_bay_id,
      unit_image: unitId,
    });
    f.reset();
    ensureFleetUnitPicker().reset();
    toast("Pairing started — waiting for robot"); loadFleet();
  } catch (err) { toast(err.message, true); }
};

// ---- Locations section ----
async function loadLocations() {
  const tree = await api.get("/api/tree");
  if (!tree) return;
  const list = $("#loc-list"); list.className = "loc-list";
  list.innerHTML = tree.length ? tree.map((w) => {
    const secs = w.sections.map((s) => {
      const items = s.shelves.reduce((a, sh) => a + sh.item_count, 0);
      return `<div class="loc-sec"><span class="loc-sec-name">${esc(s.name)}</span><span class="loc-sec-meta">${s.shelves.length} bays · ${items} items</span></div>`;
    }).join("");
    return `<div class="loc-wh"><div class="loc-wh-head">${esc(w.name)}<span>${w.sections.length} sections</span></div>${secs}</div>`;
  }).join("") : `<div class="muted-line">No warehouses yet.</div>`;
}

$("#add-wh-form").onsubmit = async (e) => {
  e.preventDefault();
  const f = e.target;
  try { await api.send("POST", "/api/warehouses", { name: f.name.value.trim() }); f.reset(); toast("Warehouse added"); loadLocations(); }
  catch (err) { toast(err.message, true); }
};

// ---- Data section (product JSON import) ----
async function loadData() {
  const [tree, items] = await Promise.all([api.get("/api/tree"), api.get("/api/items")]);
  if (!tree) return;

  let sections = 0, bays = 0;
  for (const w of tree) {
    sections += w.sections.length;
    for (const s of w.sections) bays += s.shelves.length;
  }

  const box = $("#data-import-info");
  if (!box) return;
  box.className = "data-import-info";
  box.innerHTML =
    `<div class="data-file-card data-file-card--items">` +
    `<div class="data-file-icon">JSON</div>` +
    `<div class="data-file-body">` +
    `<strong>Product catalog import</strong>` +
    `<p>Adds items to existing locations. Does not delete warehouses, aisles, bays, or robots. The sample JSON on disk is not your database.</p>` +
    `<div class="data-file-meta">` +
    `<span>${tree.length} warehouse${tree.length === 1 ? "" : "s"}</span>` +
    `<span>${sections} aisle${sections === 1 ? "" : "s"}</span>` +
    `<span>${bays} bay${bays === 1 ? "" : "s"}</span>` +
    `<span>${items.length} item${items.length === 1 ? "" : "s"} now</span>` +
    `</div></div></div>` +
    (bays === 0
      ? `<div class="sys-note">No bays yet — add warehouses and bays under <strong>Locations</strong> before importing products.</div>`
      : `<div class="sys-note">Warehouse, aisle, and bay names in your JSON must match exactly what is on the board.</div>`);
}

// ---- Storage section (backup manifest) ----
async function loadStorage() {
  const [tree, items, robots, tasks] = await Promise.all([
    api.get("/api/tree"), api.get("/api/items"), api.get("/api/robots"), api.get("/api/tasks"),
  ]);
  if (!tree) return;

  let sections = 0, bays = 0;
  for (const w of tree) {
    sections += w.sections.length;
    for (const s of w.sections) bays += s.shelves.length;
  }

  const org = settingsCache?.org_name || "—";
  const mRow = (name, count, note, exported = true) =>
    `<tr class="${exported ? "" : "data-m-skip"}">` +
    `<td><strong>${esc(name)}</strong><span class="data-m-note">${esc(note)}</span></td>` +
    `<td class="data-m-count">${exported ? count : "—"}</td>` +
    `<td class="data-m-flag">${exported ? "✓" : "—"}</td></tr>`;

  const empty = tree.length === 0;
  $("#seed-demo-btn")?.classList.toggle("hidden", !empty);

  $("#storage-stats").className = "";
  $("#storage-stats").innerHTML =
    `<div class="data-file-card">` +
    `<div class="data-file-icon">JSON</div>` +
    `<div class="data-file-body">` +
    `<strong>warehousedb-export.json</strong>` +
    `<p>Single-file backup of inventory, locations, fleet records, and workspace settings. Tasks and alerts are server-only and are not exported.</p>` +
    `<div class="data-file-meta"><span>SQLite · <code>instance/warehouse.db</code></span><span>Org · ${esc(org)}</span></div>` +
    `</div></div>` +
    `<h3 class="sys-sub">Export manifest</h3>` +
    `<div class="data-manifest-wrap"><table class="data-manifest">` +
    `<thead><tr><th>Dataset</th><th>Records</th><th>In export</th></tr></thead><tbody>` +
    mRow("Warehouses", tree.length, "Sites and nested hierarchy") +
    mRow("Sections", sections, "Zones inside each warehouse") +
    mRow("Bays", bays, "Shelf slots with item counts") +
    mRow("Items", items.length, "SKU name, quantity, shelf path") +
    mRow("Robots", robots.length, "Names and home bays — pairing codes excluded") +
    mRow("Settings", 1, "Organization + status labels/colors") +
    mRow("Tasks", tasks.length, "Work orders — live on server only", false) +
    mRow("Alerts", "—", "Notification feed — not archived", false) +
    mRow("Account", "—", "Login credentials — never exported", false) +
    `</tbody></table></div>` +
    `<div class="sys-note">Use <strong>Export</strong> before major changes. <strong>Import</strong> replaces all warehouse data. Pairing codes are not stored in backups — robots may need to pair again. <strong>Clear all data</strong> wipes inventory and fleet but keeps your login.</div>`;
}

// ---- Security ----
function syncIpAllowlistUi() {
  const on = $("#sec-ip-enabled")?.checked;
  const body = $("#sec-ip-body");
  const lbl = $("#sec-ip-toggle-lbl");
  const card = $("#sec-ip-card");
  if (body) body.classList.toggle("is-off", !on);
  if (lbl) lbl.textContent = on ? "On" : "Off";
  if (card) card.classList.toggle("security-card-active", !!on);
}

async function loadSecurity() {
  const sec = await api.get("/api/security");
  if (!sec) return;
  $("#sec-attempts").value = sec.max_login_attempts;
  $("#sec-lockout").value = sec.lockout_minutes;
  $("#sec-session").value = sec.session_hours;
  $("#sec-ip-enabled").checked = sec.ip_allowlist_enabled;
  $("#sec-ip-list").value = sec.ip_allowlist || "";
  syncIpAllowlistUi();

  const stat = (n, l, on = false) =>
    `<div class="security-stat${on ? " on" : ""}"><span class="n">${esc(n)}</span><span class="l">${esc(l)}</span></div>`;

  const overview = $("#security-overview");
  overview.className = "security-overview";
  overview.innerHTML =
    `<div class="security-status-row">` +
    stat(sec.max_login_attempts, "Max logins") +
    stat(sec.lockout_minutes + "m", "Lockout") +
    stat(sec.session_hours + "h", "Session") +
    stat(sec.ip_allowlist_enabled ? "ON" : "OFF", "IP filter", sec.ip_allowlist_enabled) +
    `</div>` +
    `<div class="security-meta">` +
    `<span class="security-meta-item"><span class="lbl">Your IP</span><code>${esc(sec.client_ip)}</code></span>` +
    `<span class="security-meta-item"><span class="lbl">Password</span><span>${sec.password_min_length}+ chars · letter + number</span></span>` +
    `<span class="security-meta-item${sec.headers_enabled ? " on" : ""}"><span class="lbl">Headers</span><code>${sec.headers_enabled ? "enabled" : "off"}</code></span>` +
  `</div>`;
}

$("#sec-ip-enabled")?.addEventListener("change", syncIpAllowlistUi);

$("#security-form").onsubmit = async (e) => {
  e.preventDefault();
  const f = e.target;
  const body = {
    max_login_attempts: Number(f.max_login_attempts.value),
    lockout_minutes: Number(f.lockout_minutes.value),
    session_hours: Number(f.session_hours.value),
    ip_allowlist_enabled: f.ip_allowlist_enabled.checked,
    ip_allowlist: f.ip_allowlist.value,
    current_password: f.current_password.value,
  };
  try {
    await api.send("PUT", "/api/security", body);
    f.current_password.value = "";
    toast("Security settings saved");
    loadSecurity();
  } catch (err) { toast(err.message, true); }
};

// ---- System overview ----
function fmtBytes(n) {
  if (n == null) return "—";
  let size = Number(n);
  for (const unit of ["B", "KB", "MB", "GB", "TB"]) {
    if (size < 1024 || unit === "TB") {
      return unit === "B" ? `${Math.round(size)} B` : `${size.toFixed(1)} ${unit}`;
    }
    size /= 1024;
  }
  return `${size.toFixed(1)} TB`;
}

function fmtUptime(sec) {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  if (h) return `${h}h ${m}m`;
  if (m) return `${m}m ${s}s`;
  return `${s}s`;
}

function meterBar(pct) {
  const p = Math.max(0, Math.min(100, pct ?? 0));
  const cls = p >= 92 ? "critical" : p >= 80 ? "warn" : "";
  return `<div class="sys-meter"><div class="sys-meter-bar"><div class="sys-meter-fill ${cls}" style="width:${p}%"></div></div><span class="sys-meter-pct">${p}%</span></div>`;
}

function renderHostCard(sys) {
  if (!sys?.host) return "";
  const h = sys.host;
  const db = sys.database || {};
  const kv = (k, v) => `<div class="sys-kv"><span class="sys-k">${k}</span><span class="sys-v">${v}</span></div>`;
  const mem = h.memory;
  const disk = h.disk;
  return (
    `<h3 class="sys-sub">Server device</h3>` +
    `<div class="sys-host-card">` +
    `<div class="sys-host-grid">` +
    kv("Hostname", esc(h.hostname)) +
    kv("Platform", esc(h.platform)) +
    kv("Architecture", esc(h.arch)) +
    kv("Python", esc(h.python)) +
    kv("CPU cores", esc(h.cpu_cores)) +
    kv("Uptime", esc(fmtUptime(h.uptime_seconds))) +
    kv("Listening on", `<code>${esc(h.bind)}</code>`) +
    kv("Environment", esc(h.flask_env) + (h.debug ? " (debug)" : "")) +
    `</div>` +
    (mem
      ? `<div class="sys-meter-row"><div class="sys-meter-label">Memory <span>${esc(fmtBytes(mem.used_bytes))} / ${esc(fmtBytes(mem.total_bytes))}</span></div>${meterBar(mem.percent)}</div>`
      : "") +
    (disk
      ? `<div class="sys-meter-row"><div class="sys-meter-label">Disk (data volume) <span>${esc(fmtBytes(disk.free_bytes))} free of ${esc(fmtBytes(disk.total_bytes))}</span></div>${meterBar(disk.percent)}</div>`
      : "") +
    `<div class="sys-db-row"><span class="sys-k">Database file</span><span class="sys-v"><code>${esc(db.path || "")}</code> — ${esc(db.size_label || fmtBytes(db.total_bytes))}</span></div>` +
    `</div>`
  );
}

async function loadSystem() {
  const [tree, items, robots, tasks, sys] = await Promise.all([
    api.get("/api/tree"),
    api.get("/api/items"),
    api.get("/api/robots"),
    api.get("/api/tasks"),
    api.get("/api/system"),
  ]);
  if (!tree) return;
  let sections = 0, bays = 0;
  for (const w of tree) { sections += w.sections.length; for (const s of w.sections) bays += s.shelves.length; }
  const open = tasks.filter((t) => t.status === "queued" || t.status === "in_progress").length;
  const labels = settingsCache?.status_labels || {};
  const colors = settingsCache?.status_colors || {};
  const byStatus = {}; for (const r of robots) byStatus[r.status] = (byStatus[r.status] || 0) + 1;

  const tile = (n, l) => `<div class="sys-tile"><span class="n">${n}</span><span class="l">${l}</span></div>`;
  const stat = (k) =>
    `<div class="sys-status"><span class="dot" style="background:${esc(colors[k] || "#888")}"></span>` +
    `<span class="sys-status-l">${esc(labels[k] || k)}</span><b>${byStatus[k] || 0}</b></div>`;

  $("#system-stats").className = "";
  $("#system-stats").innerHTML =
    renderHostCard(sys) +
    `<h3 class="sys-sub">Warehouse data</h3>` +
    `<div class="sys-grid">` +
    tile(tree.length, "Warehouses") + tile(sections, "Sections") + tile(bays, "Bays") +
    tile(items.length, "Items") + tile(robots.length, "Robots") + tile(tasks.length, "Tasks") +
    tile(open, "Open tasks") +
    `</div>` +
    `<h3 class="sys-sub">Fleet status</h3>` +
    `<div class="sys-status-list">` + STATUS_ORDER.map(stat).join("") + `</div>` +
    `<div class="sys-note">Robots pair over HTTP — they poll <code>GET /api/robots/&lt;id&gt;/tasks</code> ` +
    `(optionally with <code>?status=idle</code>) to stay online, and report task progress with ` +
    `<code>PUT /api/tasks/&lt;id&gt;</code>. Status is live, not set manually.</div>`;
}

$("#system-refresh")?.addEventListener("click", () => loadSystem());

$("#org-name")?.addEventListener("input", () => {
  const max = orgCache?.max_length || 120;
  const val = $("#org-name").value;
  $("#org-char-count").textContent = `${val.length} / ${max}`;
  $("#org-preview-sub").textContent = orgPreviewText(val, orgCache?.fallback_subtitle);
});

$("#org-form").onsubmit = async (e) => {
  e.preventDefault();
  try {
    const res = await api.send("PUT", "/api/organization", { org_name: $("#org-name").value });
    if (!res) return;
    if (settingsCache) settingsCache.org_name = res.org_name;
    syncOrgUi(res);
    await loadGeneral();
    toast("Organization saved");
  } catch (err) { toast(err.message, true); }
};

const PASSWORD_POLICY = /^(?=.*[A-Za-z])(?=.*\d).{8,}$/;

function validateNewPassword(newPassword, confirmPassword) {
  if (!newPassword) return null;
  if (!confirmPassword) return "Confirm your new password.";
  if (newPassword !== confirmPassword) return "New password and confirmation do not match.";
  if (!PASSWORD_POLICY.test(newPassword)) {
    return "Password must be at least 8 characters with a letter and a number.";
  }
  return null;
}

$("#account-form").onsubmit = async (e) => {
  e.preventDefault();
  const f = e.target;
  const newPassword = (f.new_password.value || "").trim();
  const confirmPassword = (f.confirm_password.value || "").trim();
  const policyError = validateNewPassword(newPassword, confirmPassword);
  if (policyError) return toast(policyError, true);

  const body = {
    first_name: f.first_name.value.trim(),
    last_name: f.last_name.value.trim(),
    email: f.email.value.trim(),
    username: f.username.value.trim(),
    current_password: f.current_password.value,
    new_password: newPassword || undefined,
    confirm_password: newPassword ? confirmPassword : undefined,
  };
  try {
    const res = await api.send("PUT", "/api/account", body);
    if (!res) return;
    f.current_password.value = "";
    f.new_password.value = "";
    f.confirm_password.value = "";
    if (res.username) {
      f.username.value = res.username;
      document.body.dataset.warehouseUser = res.username;
      const who = document.querySelector(".account-head .who");
      if (who) who.textContent = res.username;
      const navName = document.querySelector(".account-name");
      if (navName) { navName.textContent = res.username; navName.title = res.username; }
    }
    toast(res.password_changed ? "Password updated — use the new password next time you sign in" : "Account updated");
  } catch (err) { toast(err.message, true); }
};

$("#status-form").onsubmit = async (e) => {
  e.preventDefault();
  const labels = {}, colors = {};
  document.querySelectorAll(".st-label").forEach((i) => (labels[i.dataset.key] = i.value.trim() || i.dataset.key));
  document.querySelectorAll(".st-color").forEach((i) => (colors[i.dataset.key] = i.value));
  try { await api.send("PUT", "/api/settings", { status_labels: labels, status_colors: colors }); toast("Statuses saved"); }
  catch (err) { toast(err.message, true); }
};

$("#export-btn").onclick = async () => {
  const pw = await askPassword("Enter your current password to download a backup.");
  if (!pw) return;
  const res = await fetch("/api/export", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ current_password: pw }),
  });
  if (res.status === 401) return (location.href = "/login");
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    return toast(err.error || "Export failed", true);
  }
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "warehousedb-export.json";
  a.click();
  URL.revokeObjectURL(a.href);
  toast("Backup downloaded");
};

$("#import-btn").onclick = () => $("#import-file").click();

$("#products-import-btn")?.addEventListener("click", () => $("#products-import-file")?.click());

$("#products-import-file")?.addEventListener("change", async () => {
  const file = $("#products-import-file").files[0];
  $("#products-import-file").value = "";
  if (!file) return;
  if (!(await askConfirm(`Import products from "${file.name}"?`, "Import products"))) return;
  const pw = await askPassword("Enter your current password to import products.");
  if (!pw) return;
  const fd = new FormData();
  fd.append("file", file);
  fd.append("current_password", pw);
  try {
    const res = await fetch("/api/import/products", { method: "POST", body: fd });
    if (res.status === 401) return (location.href = "/login");
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Import failed");
    const s = data.summary || {};
    const msg = `Added ${s.created || 0} item${s.created === 1 ? "" : "s"}`
      + (s.skipped ? ` · ${s.skipped} skipped` : "");
    toast(msg);
    if (s.errors?.length) {
      console.warn("Product import issues:", s.errors);
      toast(s.errors[0], true);
    }
    clearSessionCache();
    loadData();
    loadStorage();
  } catch (err) { toast(err.message, true); }
});

$("#import-file").onchange = async () => {
  const file = $("#import-file").files[0];
  $("#import-file").value = "";
  if (!file) return;
  if (!(await askConfirm(`Replace all warehouse data with "${file.name}"? Tasks and alerts will be cleared.`, "Import backup"))) return;
  const pw = await askPassword("Enter your current password to import this backup.");
  if (!pw) return;
  const fd = new FormData();
  fd.append("file", file);
  fd.append("current_password", pw);
  try {
    const res = await fetch("/api/import", { method: "POST", body: fd });
    if (res.status === 401) return (location.href = "/login");
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Import failed");
    toast(`Imported ${data.summary.items} items, ${data.summary.robots} robots`);
    loadStorage();
    loadData();
  } catch (err) { toast(err.message, true); }
};

$("#reset-btn").onclick = async () => {
  if (!(await askConfirm("Delete all warehouses, items, robots, tasks, and alerts?", "Clear all data"))) return;
  const pw = await askPassword("Enter your current password to clear warehouse data.");
  if (!pw) return;
  try { await api.send("POST", "/api/reset", { current_password: pw }); clearSessionCache(); toast("All warehouse data cleared"); loadStorage(); loadData(); }
  catch (err) { toast(err.message, true); }
};

$("#seed-demo-btn")?.addEventListener("click", async () => {
  if (!(await askConfirm("Load demo warehouses and ~100 sample items? Robots are not included — pair real hardware from Fleet.", "Load demo inventory"))) return;
  const pw = await askPassword("Enter your current password to load demo inventory.");
  if (!pw) return;
  try {
    const data = await api.send("POST", "/api/seed-demo", { current_password: pw });
    const s = data.summary || {};
    toast(`Loaded ${s.items || 0} items in ${s.warehouses || 0} warehouses`);
    clearSessionCache();
    loadStorage();
    loadData();
  } catch (err) { toast(err.message, true); }
});

load();
