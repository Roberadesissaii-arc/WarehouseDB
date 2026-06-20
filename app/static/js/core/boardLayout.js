// Board layout — static shell (HTML) + dynamic grid (#board-dynamic).
import { $ } from "./dom.js";
import { isMobileViewport } from "./viewport.js";

const BOARD_SCROLL_KEY = "board-tab-scroll";

export function boardDynamic() {
  return $("#board-dynamic");
}

/** Show baked-in items intro + NEW ITEM card; other views render their own chrome. */
export function setItemsShellVisible(visible) {
  $("#board-static-intro")?.classList.toggle("hidden", !visible);
  $("#shell-new-item")?.classList.toggle("hidden", !visible);
}

export function clearBoardDynamic() {
  const el = boardDynamic();
  if (el) el.innerHTML = "";
  return el;
}

/** Reset dynamic area and hide items-only shell (fleet / tasks / map). */
export function prepareAlternateView() {
  setItemsShellVisible(false);
  return clearBoardDynamic();
}

/** Items view — keep shell, clear tag grid only. */
export function prepareItemsView() {
  setItemsShellVisible(true);
  return clearBoardDynamic();
}

/** Mark that the next board page load should scroll content into view (mobile tab nav). */
export function markBoardTabScroll() {
  try {
    sessionStorage.setItem(BOARD_SCROLL_KEY, "1");
  } catch {
    /* ignore private mode / quota */
  }
}

let boardScrollDone = false;

/** After switching ITEMS / FLEET / TASKS / MAP on mobile, scroll past masthead + deck. */
export function scrollBoardContentIntoView() {
  if (boardScrollDone) return;
  let shouldScroll = false;
  try {
    shouldScroll = sessionStorage.getItem(BOARD_SCROLL_KEY) === "1";
    if (shouldScroll) sessionStorage.removeItem(BOARD_SCROLL_KEY);
  } catch {
    /* ignore */
  }
  if (!shouldScroll || !isMobileViewport(900)) return;

  const target = document.querySelector(".board-head") || $("#board");
  if (!target) return;

  boardScrollDone = true;
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
}
