// Shared pair-robot form — used by fleet modal (desktop) and /fleet/pair page (mobile).
import { api } from "./api.js";
import { store, reload } from "./store.js";
import { refresh as refreshNotifications } from "./notifications.js";
import { $, esc, toast } from "./dom.js";
import { wireHomeBayCustom, resolveHomeBaySelection, fillHomeBaySelect } from "./homeBays.js";
import { mountUnitPicker } from "./unitPicker.js";
import { unitById } from "./robotImages.js";

const PAIR_TIMEOUT_MS = 30000;

let pollTimer = null;
let activeRobotId = null;
let activePairingCode = "";
let waitStartedAt = 0;
let unitPicker = null;
let wired = false;

let onExit = () => {};

export function configurePairFlow({ onExit: exitHandler } = {}) {
  if (typeof exitHandler === "function") onExit = exitHandler;
}

function noopPicker() {
  return { getValue: () => 1, getBrand: () => unitById(1).brand, reset: () => {} };
}

function ensureUnitPicker() {
  const mount = $("#robot-unit-picker");
  if (!mount) return noopPicker();
  unitPicker = mountUnitPicker(mount, {
    hiddenInput: $("#robot-unit-image"),
    selectedLabelEl: $("#robot-unit-selected"),
  });
  return unitPicker;
}

function getUnitPicker() {
  return unitPicker || ensureUnitPicker();
}

function fillHomeSelect() {
  fillHomeBaySelect(
    $("#robot-home-bay"),
    { warehouse_name: store.homeWarehouseName, bays: store.homeBays },
    null,
  );
}

function setPairError(msg, robot) {
  const box = $("#pair-code-error");
  const input = $("#pairing-code-input");
  if (!box) return;
  if (!msg) {
    box.textContent = "";
    box.classList.add("hidden");
    input?.classList.remove("pair-input-error");
    return;
  }
  if (robot?.id) {
    box.innerHTML = `${esc(msg)} <a href="/robots/${robot.id}">View robot</a>`;
  } else {
    box.textContent = msg;
  }
  box.classList.remove("hidden");
  input?.classList.add("pair-input-error");
}

function formatCode(code) {
  const d = String(code || "").replace(/\D/g, "").slice(0, 6);
  return d.length > 3 ? `${d.slice(0, 3)} ${d.slice(3)}` : d;
}

function showStep(step) {
  $("#robot-form")?.classList.toggle("hidden", step !== "form");
  $("#robot-wait")?.classList.toggle("hidden", step !== "wait");
  $("#robot-failed")?.classList.toggle("hidden", step !== "failed");
  $("#robot-paired")?.classList.toggle("hidden", step !== "done");
}

function stopPolling() {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = null;
}

function isWaitStep() {
  const wait = $("#robot-wait");
  return wait && !wait.classList.contains("hidden");
}

async function discardPendingPairing(robotId) {
  if (!robotId) return;
  try {
    await api.send("POST", `/api/robots/${robotId}/cancel-pairing`, {});
    await reload({ silent: true });
    await refreshNotifications();
  } catch {
    /* slot may already be gone */
  }
}

async function showPairFailed(message) {
  stopPolling();
  const robotId = activeRobotId;
  activeRobotId = null;
  activePairingCode = "";
  $("#pair-fail-msg").textContent = message;
  showStep("failed");
  await discardPendingPairing(robotId);
}

async function pollPairStatus() {
  if (!activePairingCode) return;

  if (Date.now() - waitStartedAt > PAIR_TIMEOUT_MS) {
    await showPairFailed(
      "No robot responded with this pairing code. Check that the code on the robot screen matches, " +
      "the ESP32 WAREHOUSE_HOST in config.h points at this PC's LAN IP (not 127.0.0.1), " +
      "port 8000 is allowed in Windows Firewall, and the robot is on the same Wi-Fi.",
    );
    return;
  }

  const st = await api.get(`/api/robots/pair-status?code=${encodeURIComponent(activePairingCode)}`);
  if (!st || st.error) return;

  if (st.paired) {
    stopPolling();
    const unitId = Number($("#robot-unit-image")?.value || getUnitPicker().getValue());
    const name = unitById(unitId).brand;
    const robotId = st.robot_id || activeRobotId;
    $("#pair-success-msg").textContent = st.connected
      ? `${name} is paired and online in the fleet.`
      : `${name} is paired — robot will appear online on its next check-in.`;
    const viewLink = $("#pair-view");
    if (viewLink) viewLink.href = `/robots/${robotId}`;
    activeRobotId = null;
    activePairingCode = "";
    showStep("done");
    await reload({ silent: true });
    await refreshNotifications();
    return;
  }

  $("#wait-status").textContent = "Waiting for robot to reach the server…";
}

function showWait(code, robotId) {
  activeRobotId = robotId;
  activePairingCode = code;
  waitStartedAt = Date.now();
  $("#wait-code").textContent = formatCode(code);
  $("#wait-status").textContent = "Checking pairing code…";
  showStep("wait");
  stopPolling();
  pollPairStatus();
  pollTimer = setInterval(() => { pollPairStatus(); }, 2000);
}

export function resetPairForm() {
  stopPolling();
  activeRobotId = null;
  activePairingCode = "";
  waitStartedAt = 0;
  setPairError("");
  $("#robot-form")?.reset();
  fillHomeSelect();
  ensureUnitPicker().reset();
  showStep("form");
}

export function preparePairForm({ focusCode = true } = {}) {
  resetPairForm();
  $("#robot-modal")?.classList.remove("hidden");
  if (focusCode) $("#pairing-code-input")?.focus();
}

async function exitPairFlow() {
  stopPolling();
  const robotId = activeRobotId;
  const shouldDiscard = robotId && isWaitStep();
  activeRobotId = null;
  activePairingCode = "";
  waitStartedAt = 0;
  $("#robot-modal")?.classList.add("hidden");
  showStep("form");
  if (shouldDiscard) await discardPendingPairing(robotId);
  onExit();
}

async function submitPair(body) {
  const res = await fetch("/api/robots/pair", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (res.status === 401) { location.href = "/login"; return; }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data.error || "Request failed");
    err.code = data.code;
    err.robot = data.robot;
    throw err;
  }
  return data;
}

export function initPairRobotFlow() {
  if (wired || !$("#robot-form")) return;
  wired = true;

  wireHomeBayCustom($("#robot-home-bay"), $("#robot-home-bay-custom"), $("#robot-home-bay-custom-name"));

  $("#pairing-code-input")?.addEventListener("input", (e) => {
    e.target.value = e.target.value.replace(/\D/g, "").slice(0, 6);
    setPairError("");
  });

  $("#robot-form").onsubmit = async (e) => {
    e.preventDefault();
    const f = e.target;
    const code = f.pairing_code.value.replace(/\D/g, "");
    if (code.length !== 6) return toast("Enter the 6-digit code from the robot", true);
    setPairError("");
    let home_bay_id;
    try {
      home_bay_id = await resolveHomeBaySelection($("#robot-home-bay"), $("#robot-home-bay-custom-name"));
    } catch (err) {
      setPairError(err.message);
      return;
    }
    const picker = getUnitPicker();
    const unitId = Number(f.unit_image.value || picker.getValue());
    const body = {
      pairing_code: code,
      name: unitById(unitId).brand,
      home_bay_id,
      unit_image: unitId,
    };
    try {
      const res = await submitPair(body);
      showWait(code, res.id || res.robot_id);
      await refreshNotifications();
    } catch (err) {
      if (err.code === "already_paired") {
        setPairError(err.message, err.robot);
        $("#pairing-code-input")?.focus();
        return;
      }
      setPairError(err.message || "Pairing failed");
      toast(err.message, true);
    }
  };

  $("#pair-cancel")?.addEventListener("click", () => { exitPairFlow(); });
  $("#pair-fail-close")?.addEventListener("click", () => { exitPairFlow(); });
  $("#pair-retry")?.addEventListener("click", () => { resetPairForm(); });
  $("#pair-done")?.addEventListener("click", () => { exitPairFlow(); });
  $("#robot-close")?.addEventListener("click", () => { exitPairFlow(); });
}
