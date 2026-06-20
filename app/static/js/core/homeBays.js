// Home warehouse bases — robot docks where units return to charge / idle.
import { api } from "./api.js";
import { esc } from "./dom.js";

export const CUSTOM_HOME_BAY = "__custom__";

export function normalizeHomePayload(raw) {
  if (Array.isArray(raw)) {
    return { warehouse_name: "Robot Home", bays: raw };
  }
  return {
    warehouse_name: raw?.warehouse_name || "Robot Home",
    bays: raw?.bays || [],
  };
}

export function bayLabel(bay, warehouseName = null) {
  if (!bay) return "";
  return bay.label || `${warehouseName || bay.warehouse_name || "Robot Home"} / ${bay.name}`;
}

export function fillHomeBaySelect(
  sel,
  payload,
  currentId = null,
  noneLabel = "— Auto-assign on connect —",
  { includeCustom = true } = {},
) {
  if (!sel) return;
  const { warehouse_name: wh, bays } = normalizeHomePayload(payload);
  sel.innerHTML = "";
  const none = document.createElement("option");
  none.value = "";
  none.textContent = noneLabel;
  sel.appendChild(none);
  for (const bay of bays) {
    const o = document.createElement("option");
    o.value = bay.id;
    o.textContent = bayLabel(bay, wh);
    if (bay.id == currentId) o.selected = true;
    sel.appendChild(o);
  }
  if (includeCustom) {
    const custom = document.createElement("option");
    custom.value = CUSTOM_HOME_BAY;
    custom.textContent = `+ Custom base in ${wh}…`;
    sel.appendChild(custom);
  }
}

export function homeBayOptionsHtml(payload, currentId = null, { includeCustom = true } = {}) {
  const { warehouse_name: wh, bays } = normalizeHomePayload(payload);
  let html = `<option value="">— Auto-assign on connect —</option>`;
  for (const bay of bays) {
    const sel = bay.id == currentId ? " selected" : "";
    html += `<option value="${bay.id}"${sel}>${esc(bayLabel(bay, wh))}</option>`;
  }
  if (includeCustom) {
    html += `<option value="${CUSTOM_HOME_BAY}">+ Custom base in ${esc(wh)}…</option>`;
  }
  return html;
}

export function wireHomeBayCustom(select, customWrap, customInput) {
  if (!select || !customWrap) return;
  const sync = () => {
    const on = select.value === CUSTOM_HOME_BAY;
    customWrap.classList.toggle("hidden", !on);
    if (customInput) customInput.required = on;
    if (on) customInput?.focus();
  };
  select.addEventListener("change", sync);
  sync();
}

export async function resolveHomeBaySelection(select, customInput) {
  const val = select?.value;
  if (!val) return null;
  if (val === CUSTOM_HOME_BAY) {
    const name = customInput?.value?.trim();
    if (!name) throw new Error("Enter a name for the custom home base");
    const bay = await api.send("POST", "/api/home-bays", { name });
    return bay.id;
  }
  return Number(val);
}
