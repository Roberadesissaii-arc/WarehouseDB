// TASKS view — work orders. First card creates a new task.
import { store, TASK_STATUS_LABELS, statusLabel } from "../core/store.js";
import { prepareAlternateView } from "../core/boardLayout.js";
import { createCard } from "../core/createCard.js";
import { viewIntro } from "../core/viewIntro.js";
import { $, el, esc, icon } from "../core/dom.js";
import { newTask, openTask } from "../modals/taskModal.js";
import { taskTagsHtml } from "../core/taskTagField.js";

export function renderTasks() {
  const q = $("#search").value.trim().toLowerCase();
  let list = store.tasks;
  if (q) list = list.filter((t) => (t.robot || "").toLowerCase().includes(q) || (t.item || "").toLowerCase().includes(q));
  else if (store.sel.s) list = list.filter((t) => t.section_id == store.sel.s);

  $("#board-title").textContent = q ? `SEARCH “${q.toUpperCase()}”` : "WORK ORDERS";
  $("#board-count").textContent = `${list.length} TASK${list.length === 1 ? "" : "S"}`;

  const board = $("#board");
  const dynamic = prepareAlternateView();
  board.className = "board";
  dynamic.appendChild(viewIntro(
    "Work orders",
    "Tasks tell a robot what to do and which section to visit. Status updates automatically when the robot works — use Cancel to stop an open task.",
  ));
  dynamic.appendChild(createCard({
    variant: "task",
    label: "NEW TASK",
    sub: "Assign work to a robot",
    onClick: newTask,
  }));

  if (!list.length) return;

  for (const t of list) {
    const qty = t.quantity > 1 ? ` ×${t.quantity}` : "";
    const target = t.item
      ? `${esc(t.item)}${qty}${t.item_sku ? ` <span class="t-sku">#${esc(t.item_sku)}</span>` : ""}`
      : "—";
    const rb = store.robots.find((r) => r.id === t.robot_id);
    const robotLine = rb
      ? `${esc(t.robot)} <span class="task-robot-st status-${esc(rb.status)}">${esc(statusLabel(rb.status))}</span>`
      : esc(t.robot);
    const card = el("div", "task" + (t.status === "done" || t.status === "cancelled" ? " muted-task" : ""),
      `<div class="task-top"><span class="task-id">#${esc(t.id)}</span><span class="task-action">${esc(t.action)}</span>` +
      `<span class="task-status status-${t.status}">${esc(TASK_STATUS_LABELS[t.status] || t.status)}</span></div>` +
      `<div class="task-robot">${icon("robot", "ic-sm")} ${robotLine}</div>` +
      `<div class="task-route"><span class="seg">${esc(t.section)}</span><span class="arrow">→</span><span class="seg item">${target}</span></div>` +
      (t.note ? `<div class="task-tags">${taskTagsHtml(t.note, esc)}</div>` : ""));
    card.onclick = () => openTask(t);
    dynamic.appendChild(card);
  }
}
