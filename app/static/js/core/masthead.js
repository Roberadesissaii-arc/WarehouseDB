// Global masthead — account menu + live alerts on every staff page.
import { $ } from "./dom.js";
import { wireNotifications, startPolling, refresh, closePanel as closeNotifPanel } from "./notifications.js";

const MOBILE_MQ = window.matchMedia("(max-width: 640px)");

function closeAccountMenu() {
  const menu = $("#account-menu");
  menu?.classList.add("hidden");
  menu?.classList.remove("is-fixed");
  menu?.style.removeProperty("--dropdown-top");
}

function positionAccountMenu() {
  const menu = $("#account-menu");
  const btn = $("#account-btn");
  if (!menu || !btn || menu.classList.contains("hidden")) return;

  if (MOBILE_MQ.matches) {
    const rect = btn.getBoundingClientRect();
    menu.classList.add("is-fixed");
    menu.style.setProperty("--dropdown-top", `${Math.round(rect.bottom + 8)}px`);
    menu.style.setProperty(
      "--dropdown-max-h",
      `${Math.max(160, Math.round(window.innerHeight - rect.bottom - 20))}px`,
    );
  } else {
    menu.classList.remove("is-fixed");
    menu.style.removeProperty("--dropdown-top");
    menu.style.removeProperty("--dropdown-max-h");
  }
}

function openAccountMenu() {
  closeNotifPanel();
  const menu = $("#account-menu");
  menu?.classList.remove("hidden");
  positionAccountMenu();
}

function wireAccountMenu() {
  const btn = $("#account-btn");
  const menu = $("#account-menu");
  if (!btn || btn.dataset.wired) return;
  btn.dataset.wired = "1";

  btn.addEventListener("click", (e) => {
    e.stopPropagation();
    if (menu?.classList.contains("hidden")) openAccountMenu();
    else closeAccountMenu();
  });

  menu?.addEventListener("click", (e) => e.stopPropagation());

  document.addEventListener("click", () => closeAccountMenu());

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeAccountMenu();
  });
}

function onViewportChange() {
  positionAccountMenu();
}

function initMasthead() {
  if (!$("#notif-btn")) return;
  wireNotifications();
  wireAccountMenu();
  startPolling();
  refresh();
  window.addEventListener("resize", onViewportChange);
  window.addEventListener("orientationchange", onViewportChange);
  if (MOBILE_MQ.addEventListener) MOBILE_MQ.addEventListener("change", onViewportChange);
}

initMasthead();

export { closeAccountMenu, positionAccountMenu };
