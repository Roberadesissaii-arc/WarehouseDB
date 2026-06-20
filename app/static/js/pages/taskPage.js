// Task edit page for mobile (/tasks/:id).
import { api } from "../core/api.js";
import { loadData } from "../core/store.js";
import { $, esc, icon } from "../core/dom.js";
import { configureTaskEditor, initTaskEditor, startEditTask } from "../core/taskEditor.js";
import { wireFleetAlertBar } from "../core/fleetAlerts.js";

const root = $(".task-page");
const taskId = root?.dataset.taskId;

configureTaskEditor({
  close: () => { location.href = "/tasks"; },
  saved: async () => { location.href = "/tasks"; },
});
initTaskEditor();
wireFleetAlertBar();

async function load() {
  if (!taskId) {
    $("#task-page-title").innerHTML = icon("tasks", "ic-lg") + " TASK NOT FOUND";
    $("#task-form")?.classList.add("hidden");
    return;
  }
  await loadData({ silent: true });
  const task = await api.get(`/api/tasks/${taskId}`);
  if (!task || task.error) {
    $("#task-page-title").innerHTML = icon("tasks", "ic-lg") + " TASK NOT FOUND";
    $("#task-form")?.classList.add("hidden");
    return;
  }

  $("#task-page-title").innerHTML = icon("tasks", "ic-lg") + ` TASK #${esc(task.id)}`;
  startEditTask(task);
}

load();
