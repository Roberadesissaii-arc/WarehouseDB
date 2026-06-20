// Task modal — desktop create/edit; mobile navigates to /tasks/:id.
import { store } from "../core/store.js";
import { $, toast } from "../core/dom.js";
import { isMobileViewport } from "../core/viewport.js";
import {
  configureTaskEditor,
  initTaskEditor,
  startEditTask,
  startNewTask,
} from "../core/taskEditor.js";

configureTaskEditor({
  close: () => $("#task-modal")?.classList.add("hidden"),
  saved: async () => { $("#task-modal")?.classList.add("hidden"); },
});
initTaskEditor();

export function newTask() {
  if (isMobileViewport()) {
    toast("New tasks on mobile: use the Tasks board and assign from a robot page.", true);
    return;
  }
  startNewTask();
  $("#task-modal")?.classList.remove("hidden");
}

export function openTask(t) {
  if (!t?.id) return;
  if (isMobileViewport()) {
    location.href = `/tasks/${t.id}`;
    return;
  }
  startEditTask(t);
  $("#task-modal")?.classList.remove("hidden");
}

export function openTaskById(taskId) {
  const t = store.tasks.find((row) => String(row.id) === String(taskId));
  if (t) openTask(t);
}
