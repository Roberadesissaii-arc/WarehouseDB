// Shared task create/edit form — used by board modal (desktop) and /tasks/:id page (mobile).
import { api } from "./api.js";
import { store, reload, statusLabel, TASK_STATUS_LABELS } from "./store.js";
import { refresh as refreshNotifications } from "./notifications.js";
import { $, el, esc, toast } from "./dom.js";
import { askConfirm } from "./dialogs.js";
import {
  syncActionOptions,
  applyTaskFormRules,
  validateTaskPayload,
  wireTaskForm,
  readQuantity,
} from "./taskFormLogic.js";
import { wireTaskTagField, setTaskTagValue, commitTaskTag } from "./taskTagField.js";
import { mountPickSelect } from "./shelfSelect.js";

const itemPicker = mountPickSelect($("#task-item-mount"), {
  name: "item_id", placeholder: "— select item —", visibleRows: 4,
});
const sectionPicker = mountPickSelect($("#task-section-mount"), {
  name: "section_id", placeholder: "— select section —", visibleRows: 4,
});

const taskTagField = $("#task-tag-field");
wireTaskTagField(taskTagField);

let editingId = null;
let onClose = () => {};
let onSaved = async () => {};
let wired = false;

const taskFormCtx = {
  getTree: () => store.tree,
  getItems: () => store.items,
  actionEl: $("#task-action"),
  itemEl: itemPicker,
  sectionEl: sectionPicker,
  qtyEl: $("#task-qty"),
  qtyHintEl: $("#task-qty-hint"),
  hintEl: $("#task-action-hint"),
  fromHintEl: $("#task-from-hint"),
  sectionLabelEl: $("#task-section-label"),
  itemLabelEl: $("#task-item-label"),
};

const refreshTaskForm = wireTaskForm(taskFormCtx);

function robotLabel(r) {
  if (!r.paired) return `${r.name} — not paired`;
  return `${r.name} — ${statusLabel(r.status)}`;
}

function updateRobotHint() {
  const hint = $("#task-robot-hint");
  const sel = $("#task-robot");
  if (!hint || !sel || editingId) return;
  const r = store.robots.find((x) => String(x.id) === sel.value);
  if (!r) { hint.textContent = ""; return; }
  if (!r.paired) {
    hint.textContent = "This robot is not paired yet — pair it from the fleet board first.";
    return;
  }
  if (r.status === "offline") {
    hint.textContent = `Home bay: ${r.location || "unassigned"}. Robot is offline — the task will queue until it connects.`;
    return;
  }
  hint.textContent = `Home bay: ${r.location || "unassigned"}. Pick action, item, then destination as needed.`;
}

function fillRobots() {
  const rb = $("#task-robot");
  if (!rb) return;
  rb.innerHTML = "";
  const paired = store.robots.filter((r) => r.paired);
  if (!paired.length) {
    const o = el("option", null, "— pair a robot first —");
    o.value = "";
    rb.appendChild(o);
  } else {
    for (const r of store.robots) {
      const o = el("option", null, esc(robotLabel(r)));
      o.value = r.id;
      if (!r.paired) o.disabled = true;
      rb.appendChild(o);
    }
    rb.value = String(paired[0].id);
  }
}

function setTaskStatusBadge(status) {
  const badge = $("#task-status-badge");
  if (!badge) return;
  badge.className = `task-status status-${status}`;
  badge.textContent = (TASK_STATUS_LABELS[status] || status).toUpperCase();
}

function setFormMode(isEdit, taskStatus = null) {
  $("#task-status-display")?.classList.toggle("hidden", !isEdit);
  $("#task-assign-hint")?.classList.toggle("hidden", isEdit);
  $("#task-title").textContent = isEdit ? "Edit task" : "New task";
  const open = taskStatus === "queued" || taskStatus === "in_progress";
  $("#cancel-task")?.classList.toggle("hidden", !isEdit || !open);
  if (isEdit && taskStatus) setTaskStatusBadge(taskStatus);
}

export function configureTaskEditor({ close, saved } = {}) {
  if (typeof close === "function") onClose = close;
  if (typeof saved === "function") onSaved = saved;
}

export function initTaskEditor() {
  if (wired) return;
  wired = true;

  $("#task-robot")?.addEventListener("change", updateRobotHint);

  $("#task-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const f = e.target;
    const robot = store.robots.find((r) => r.id === Number(f.robot_id.value));
    if (!robot) return toast("Select a robot", true);
    if (!robot.paired) return toast("Pair this robot before assigning tasks", true);

    const check = validateTaskPayload(
      f.action.value,
      f.section_id.value,
      f.item_id.value,
      readQuantity(taskFormCtx.qtyEl),
      store.tree,
      store.items,
    );
    if (!check.ok) return toast(check.error, true);

    const body = {
      robot_id: robot.id,
      action: f.action.value,
      section_id: check.section_id,
      item_id: check.item_id,
      quantity: check.quantity,
      note: commitTaskTag(taskTagField),
    };
    try {
      let created;
      if (editingId) await api.send("PUT", `/api/tasks/${editingId}`, body);
      else created = await api.send("POST", "/api/tasks", body);
      await onSaved({ editingId, created });
      await reload({ silent: true });
      await refreshNotifications();
      toast(editingId ? "Task updated" : (created?.id ? `#${created.id} queued` : "Task queued"));
    } catch (err) { toast(err.message, true); }
  });

  $("#cancel-task")?.addEventListener("click", async () => {
    if (!editingId || !(await askConfirm("Cancel this task?", "Cancel task"))) return;
    try {
      await api.send("POST", `/api/tasks/${editingId}/cancel`);
      await onSaved({ editingId, cancelled: true });
      await reload({ silent: true });
      await refreshNotifications();
      toast("Task cancelled");
    } catch (err) { toast(err.message, true); }
  });

  $("#delete-task")?.addEventListener("click", async () => {
    if (!editingId || !(await askConfirm("Delete this task?", "Delete task"))) return;
    await api.send("DELETE", `/api/tasks/${editingId}`);
    await onSaved({ editingId, deleted: true });
    await reload({ silent: true });
    toast("Task deleted");
  });

  $("#task-close")?.addEventListener("click", () => onClose());
}

export function startNewTask() {
  editingId = null;
  $("#task-form")?.reset();
  fillRobots();
  syncActionOptions(taskFormCtx.actionEl, store.tree);
  refreshTaskForm();
  setFormMode(false);
  if (store.sel.s) sectionPicker.setValue(store.sel.s);
  applyTaskFormRules({ ...taskFormCtx, tree: store.tree, items: store.items });
  setTaskTagValue(taskTagField, "");
  updateRobotHint();
  $("#delete-task")?.classList.add("hidden");
  if (!store.robots.some((r) => r.paired)) {
    toast("Pair a robot before assigning tasks", true);
  }
}

export function startEditTask(t) {
  editingId = t.id;
  fillRobots();
  syncActionOptions(taskFormCtx.actionEl, store.tree, t.action);
  setFormMode(true, t.status);
  const f = $("#task-form");
  if (!f) return;
  f.robot_id.value = t.robot_id;
  f.action.value = t.action;
  itemPicker.setValue(t.item_id || "");
  sectionPicker.setValue(t.section_id || "");
  setTaskTagValue(taskTagField, t.note || "");
  if (taskFormCtx.qtyEl) taskFormCtx.qtyEl.value = String(t.quantity || 1);
  applyTaskFormRules({ ...taskFormCtx, tree: store.tree, items: store.items });
  const hint = $("#task-robot-hint");
  if (hint) hint.textContent = "";
  $("#delete-task")?.classList.remove("hidden");
}

export function getEditingTaskId() {
  return editingId;
}
