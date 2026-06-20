// Robot detail page: edit, see location on a map, and manage its tasks.
import { api } from "../core/api.js";
import { $, el, esc, icon, toast } from "../core/dom.js";
import { askConfirm } from "../core/dialogs.js";
import { fillHomeBaySelect, wireHomeBayCustom, resolveHomeBaySelection, normalizeHomePayload, bayLabel } from "../core/homeBays.js";
import { watchRobotStatuses, wireFleetAlertBar, startRobotWatch } from "../core/fleetAlerts.js";
import {
  syncActionOptions, applyTaskFormRules, validateTaskPayload, wireTaskForm, readQuantity, setFieldVal,
} from "../core/taskFormLogic.js";
import { wireTaskTagField, setTaskTagValue, commitTaskTag, taskTagsHtml } from "../core/taskTagField.js";
import { mountPickSelect } from "../core/shelfSelect.js";

const itemPicker = mountPickSelect($("#t-item-mount"), {
  name: "item_id", placeholder: "— select item —", visibleRows: 4,
});
const sectionPicker = mountPickSelect($("#t-section-mount"), {
  name: "section_id", placeholder: "— select section —", visibleRows: 4,
});

const robotTagField = $("#t-tag-field");
wireTaskTagField(robotTagField);

const robotTaskCtx = {
  getTree: () => tree,
  getItems: () => items,
  actionEl: $("#t-action"),
  itemEl: itemPicker,
  sectionEl: sectionPicker,
  qtyEl: $("#t-qty"),
  qtyHintEl: $("#t-qty-hint"),
  hintEl: $("#t-action-hint"),
  fromHintEl: $("#t-from-hint"),
  sectionLabelEl: $("#t-section-label"),
  itemLabelEl: $("#t-item-label"),
};
const refreshRobotTaskForm = wireTaskForm(robotTaskCtx);

const root = $(".robot-page");
const robotId = root.dataset.robotId;
const TASK_LABELS = { queued: "Queued", in_progress: "In progress", done: "Done", cancelled: "Cancelled" };
const TASKS_PREVIEW_LIMIT = 2;
let tree = [], items = [], labels = {}, currentRobot = null, allRobots = [], homePayload = { warehouse_name: "Robot Home", bays: [] };
let editDirty = false;
let taskDirty = false;

$("#robot-edit-form")?.addEventListener("input", () => { editDirty = true; });
$("#robot-edit-form")?.addEventListener("change", () => { editDirty = true; });
wireHomeBayCustom($("#robot-home-bay"), $("#robot-home-bay-custom"), $("#robot-home-bay-custom-name"));
wireFleetAlertBar();
startRobotWatch();
$("#add-task-form")?.addEventListener("input", () => { taskDirty = true; });
$("#add-task-form")?.addEventListener("change", () => { taskDirty = true; });

function resetRobotTaskForm() {
  syncActionOptions(robotTaskCtx.actionEl, tree);
  refreshRobotTaskForm();
}

function renderHomeDocks(robot) {
  const box = $("#robot-map");
  const bays = homePayload.bays || [];
  if (!bays.length) {
    box.innerHTML = `<div class="map-empty">Home docks are loading…</div>`;
    return;
  }
  box.innerHTML = `<div class="robot-map-head">${esc(homePayload.warehouse_name)} · robot home bases</div>`;
  const floor = el("div", "map-floor mini home-dock-floor");
  for (const bay of bays) {
    const here = bay.id == robot.home_bay_id;
    const zone = el("div", "map-zone home-dock" + (here ? " here" : ""),
      `<div class="map-zone-head"><span>${esc(bay.name)}</span><em>${esc(bay.code)}</em></div>`);
    if (here) {
      zone.appendChild(el("div", `map-bot status-${robot.status}`,
        `<span class="dot status-${robot.status}"></span>${esc(robot.name)}`));
    } else {
      zone.appendChild(el("div", "map-zone-empty", "— empty —"));
    }
    floor.appendChild(zone);
  }
  box.appendChild(floor);
}

function renderTaskRow(t, box) {
  const qty = t.quantity > 1 ? ` ×${t.quantity}` : "";
  const itemPart = t.item ? `${esc(t.item)}${qty}${t.item_sku ? ` #${esc(t.item_sku)}` : ""}` : "";
  const row = el("div", "task-row" + (t.status === "done" || t.status === "cancelled" ? " muted-task" : ""));
  const main = el("div", "task-row-main",
    `<span class="task-row-id">#${esc(t.id)}</span> ` +
    `<b>${esc(t.action.toUpperCase())}</b>` +
    `<span class="task-dest"> → ${esc(t.section)}${itemPart ? ` · ${itemPart}` : ""}</span>`);
  const badges = el("div", "task-row-badges");
  badges.appendChild(el("span", `task-status status-${t.status}`, (TASK_LABELS[t.status] || t.status).toUpperCase()));
  if (t.note) {
    const tmp = document.createElement("div");
    tmp.innerHTML = taskTagsHtml(t.note, esc);
    [...tmp.children].forEach((node) => badges.appendChild(node));
  }
  main.appendChild(badges);
  row.appendChild(main);
  const actions = el("div", "task-row-actions");
  if (t.status === "queued" || t.status === "in_progress") {
    const cancel = el("button", "btn btn-ghost btn-sm", "CANCEL");
    cancel.onclick = () => cancelTask(t);
    actions.appendChild(cancel);
  }
  const del = el("button", "icon-btn", icon("trash"));
  del.title = "Delete task";
  del.onclick = () => removeTask(t);
  actions.appendChild(del);
  row.appendChild(actions);
  box.appendChild(row);
}

function renderTasks(tasks) {
  const box = $("#robot-tasks");
  const more = $("#robot-tasks-more");
  box.innerHTML = "";
  if (!tasks.length) {
    if (more) { more.classList.add("hidden"); more.innerHTML = ""; }
    box.innerHTML = `<div class="muted-line">No tasks assigned yet.</div>`;
    return;
  }
  const visible = tasks.slice(0, TASKS_PREVIEW_LIMIT);
  for (const t of visible) renderTaskRow(t, box);
  if (more) {
    const extra = tasks.length - visible.length;
    if (extra > 0) {
      more.classList.remove("hidden");
      more.innerHTML =
        `<a class="robot-tasks-view-all" href="/tasks">` +
        `View all ${tasks.length} tasks on the board` +
        `<span class="robot-tasks-view-all-sub">+${extra} more not shown here</span></a>`;
    } else {
      more.classList.add("hidden");
      more.innerHTML = "";
    }
  }
}

async function cancelTask(t) {
  if (!(await askConfirm("Cancel this task?", "Cancel task"))) return;
  try {
    await api.send("POST", `/api/tasks/${t.id}/cancel`);
    toast("Task cancelled");
    load();
  } catch (err) { toast(err.message, true); }
}

async function removeTask(t) {
  if (!(await askConfirm("Delete this task?", "Delete task"))) return;
  await api.send("DELETE", `/api/tasks/${t.id}`);
  load();
}

function formatLastSeen(ts) {
  if (!ts) return "Never — waiting for robot to connect";
  const d = new Date(ts.replace(" ", "T"));
  if (Number.isNaN(d.getTime())) return ts;
  return d.toLocaleString();
}

function renderBattery(robot) {
  const barEl = $("#robot-battery-bar");
  const pctEl = $("#robot-battery-pct");
  const fillEl = $("#robot-battery-fill");
  if (!pctEl || !fillEl) return;

  const pct = robot.battery_pct;
  const charging = robot.status === "charging" || robot.reported_status === "charging";

  fillEl.className = "charge-bar-fill";
  if (pct == null || pct === "") {
    pctEl.textContent = "—";
    pctEl.className = "charge-bar-pct is-empty";
    fillEl.style.width = "0%";
    barEl?.setAttribute("aria-valuenow", "0");
    return;
  }

  const n = Math.max(0, Math.min(100, Number(pct)));
  pctEl.textContent = `${n}%`;
  pctEl.className = "charge-bar-pct";
  fillEl.style.width = `${n}%`;
  barEl?.setAttribute("aria-valuenow", String(n));
  if (charging) fillEl.classList.add("charging");
  else if (n <= 15) fillEl.classList.add("critical");
  else if (n <= 30) fillEl.classList.add("low");
  else if (n <= 60) fillEl.classList.add("mid");
}

function renderFirmware(robot) {
  const fw = robot.firmware || {};
  const banner = $("#robot-firmware-banner");
  const updateBtn = $("#robot-fw-update");
  const installedEl = $("#robot-fw-installed");
  const latestEl = $("#robot-fw-latest");
  const noteEl = $("#robot-fw-note");
  const sketchEl = $("#robot-fw-sketch");
  const releasedRow = $("#robot-fw-released-row");
  if (!installedEl || !latestEl) return;

  const installed = fw.installed || null;
  const latest = fw.latest || null;
  installedEl.textContent = installed || "Unknown";
  installedEl.className = "info-val" + (fw.update_available ? " fw-outdated" : "");
  latestEl.textContent = latest || "—";
  if (releasedRow && fw.released_at) {
    releasedRow.classList.remove("hidden");
    $("#robot-fw-released").textContent = fw.released_at;
  } else if (releasedRow) {
    releasedRow.classList.add("hidden");
  }

  if (banner) {
    banner.classList.toggle("hidden", !fw.update_available);
    const copy = banner.querySelector(".firmware-banner-copy");
    if (copy && fw.update_available && latest) {
      copy.textContent = installed
        ? `Installed ${installed} — version ${latest} is ready to flash.`
        : `Version ${latest} is ready to flash on this unit.`;
    }
  }

  if (updateBtn) {
    updateBtn.classList.toggle("hidden", !fw.update_available);
    updateBtn.disabled = !robot.paired;
    updateBtn.title = robot.paired
      ? `Send home and flash ${fw.sketch_folder || "the unit sketch"} to ${latest || "latest"}`
      : "Pair this robot before updating firmware";
  }

  if (noteEl) {
    if (!latest) {
      noteEl.textContent = "No firmware catalog found on this server.";
    } else if (fw.update_available) {
      noteEl.textContent = fw.notes
        ? `${fw.notes} Tap UPDATE FIRMWARE to send the robot home, then re-flash from Arduino IDE.`
        : `Tap UPDATE FIRMWARE to send the robot home, then re-flash the sketch to ${latest}.`;
    } else if (installed) {
      noteEl.textContent = "This robot is on the latest firmware release.";
    } else {
      noteEl.textContent = "Installed version unknown until the robot checks in with a firmware_version heartbeat.";
    }
  }

  if (sketchEl && fw.sketch_folder) {
    sketchEl.textContent = `Sketch folder: ${fw.sketch_folder}/ — bump FIRMWARE_VERSION in config.h when you ship an update.`;
  }
}

function renderConnection(robot) {
  const stateEl = $("#robot-conn-state");
  if (!stateEl) return;

  if (!robot.paired) {
    stateEl.textContent = "Waiting for robot";
    stateEl.className = "info-val state-waiting";
  } else if (robot.connected) {
    stateEl.textContent = "Online";
    stateEl.className = "info-val state-online";
  } else {
    stateEl.textContent = "Offline";
    stateEl.className = "info-val state-offline";
  }

  $("#robot-paired-at").textContent = robot.paired_at
    ? formatLastSeen(robot.paired_at).replace("Never — waiting for robot to connect", "—")
    : "Not yet";
  $("#robot-last-seen").textContent = robot.last_seen_at
    ? formatLastSeen(robot.last_seen_at)
    : "Never";
  $("#robot-conn-note").textContent = robot.paired
    ? "Communication is automatic after pairing — the robot checks in with the server using its pairing code."
    : "Pair from the fleet board using the 6-digit code shown on this robot's display.";
}

async function load() {
  const [robot, tasks, boot] = await Promise.all([
    api.get(`/api/robots/${robotId}`),
    api.get(`/api/robots/${robotId}/tasks`),
    api.get("/api/bootstrap"),
  ]);
  if (!robot) return;
  if (robot.error) {
    $("#robot-name").textContent = "ROBOT NOT FOUND";
    return;
  }
  currentRobot = robot;
  allRobots = boot?.robots || [];
  homePayload = normalizeHomePayload(boot?.home_bays);
  tree = boot?.tree || [];
  items = boot?.items || [];
  const settings = boot?.settings || {};
  labels = settings.status_labels || {};
  applyColors(settings);

  const statusLbl = labels[robot.status] || robot.status;
  $("#robot-name").textContent = robot.name.toUpperCase();
  $("#robot-status-pill").className = `status-pill status-${robot.status}`;
  $("#robot-status-pill").textContent = statusLbl;
  $("#robot-status-note").textContent = !robot.paired
    ? "Not paired — use Pair robot on the fleet board and enter the code from this unit's screen."
    : robot.connected
      ? "Live — the robot is connected and reporting status."
      : "Paired but offline — the robot has not checked in recently. Make sure it is powered on and on the network.";
  const f = $("#robot-edit-form");
  if (!editDirty) {
    f.name.value = robot.name;
    fillHomeBaySelect($("#robot-home-bay"), homePayload, robot.home_bay_id);
  }
  if (!taskDirty) {
    resetRobotTaskForm();
  }
  renderConnection(robot);
  renderFirmware(robot);
  renderBattery(robot);
  renderHomeDocks(robot);
  renderTasks(tasks);
  updateAssignForm(robot);
}

function applyColors(s) {
  const r = document.documentElement.style;
  for (const [k, c] of Object.entries(s.status_colors || {})) r.setProperty(`--st-${k}`, c);
}

function updateAssignForm(robot) {
  const form = $("#add-task-form");
  const note = $("#assign-task-note");
  if (!form) return;
  const blocked = !robot.paired;
  form.querySelectorAll("select, input, button").forEach((el) => { el.disabled = blocked; });
  const home = robot.home_bay_id ? robot.location : "assigning on first connect";
  if (note) {
    note.classList.remove("hidden");
    if (!robot.paired) {
      note.textContent = "Pair this robot before assigning tasks — use Pair robot on the fleet board.";
    } else if (robot.status === "offline") {
      note.textContent = `Home dock: ${home}. Robot is offline — new tasks queue until it connects.`;
    } else {
      note.textContent = `Home dock: ${home}. Pick action, then item, then destination as needed.`;
    }
  }
}

$("#robot-edit-form").onsubmit = async (e) => {
  e.preventDefault();
  const f = e.target;
  let home_bay_id;
  try {
    home_bay_id = await resolveHomeBaySelection($("#robot-home-bay"), $("#robot-home-bay-custom-name"));
  } catch (err) {
    toast(err.message, true);
    return;
  }
  const body = {
    name: f.name.value.trim(),
    home_bay_id,
  };
  try {
    await api.send("PUT", `/api/robots/${robotId}`, body);
    editDirty = false;
    toast("Saved — home bay updated");
    load();
  } catch (err) { toast(err.message, true); }
};

$("#delete-robot").onclick = async () => {
  if (!(await askConfirm("Remove this robot from the fleet?", "Delete robot"))) return;
  await api.send("DELETE", `/api/robots/${robotId}`);
  location.href = "/items";
};


$("#send-charge-btn")?.addEventListener("click", async () => {
  if (!currentRobot?.paired) return toast("Pair this robot first", true);
  try {
    const res = await api.send("POST", `/api/robots/${robotId}/charge`);
    toast(res?.id ? `Charge queued (#${res.id})` : "Sent to home bay to charge");
    load();
  } catch (err) { toast(err.message, true); }
});

$("#robot-fw-update")?.addEventListener("click", async () => {
  if (!currentRobot?.paired) return toast("Pair this robot first", true);
  const fw = currentRobot.firmware || {};
  const latest = fw.latest || "latest";
  const sketch = fw.sketch_folder || "Arduino sketch";
  const msg =
    `Send ${currentRobot.name} home to its dock, then re-flash ${sketch} to version ${latest} in Arduino IDE. Continue?`;
  if (!(await askConfirm(msg, "Update firmware"))) return;
  try {
    const res = await api.send("POST", `/api/robots/${robotId}/charge`);
    toast(
      res?.id
        ? `Robot heading home (#${res.id}) — open Flash guide when it arrives`
        : `Robot sent home — open Flash guide to re-flash ${latest}`,
    );
    load();
  } catch (err) { toast(err.message, true); }
});

$("#add-task-form").onsubmit = async (e) => {
  e.preventDefault();
  if (!currentRobot?.paired) return toast("Pair this robot before assigning tasks", true);
  const f = e.target;
  const check = validateTaskPayload(
    f.action.value, f.section_id.value, f.item_id.value,
    readQuantity(robotTaskCtx.qtyEl), tree, items,
  );
  if (!check.ok) return toast(check.error, true);
  const body = {
    robot_id: Number(robotId),
    action: f.action.value,
    section_id: check.section_id,
    item_id: check.item_id,
    quantity: check.quantity,
    note: commitTaskTag(robotTagField),
  };
  try {
    const res = await api.send("POST", "/api/tasks", body);
    setTaskTagValue(robotTagField, "");
    if (robotTaskCtx.qtyEl) robotTaskCtx.qtyEl.value = "1";
    setFieldVal(itemPicker, "");
    setFieldVal(sectionPicker, "");
    resetRobotTaskForm();
    toast(res?.id ? `#${res.id} queued` : "Task queued");
    taskDirty = false;
    load();
  } catch (err) { toast(err.message, true); }
};

let liveTimer = null;
function startLiveRefresh() {
  if (liveTimer) return;
  liveTimer = setInterval(load, 3000);
}
startLiveRefresh();
load();
