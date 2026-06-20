// Full-width intro strip at the top of board views (items, fleet, tasks).
import { el, esc } from "./dom.js";

export function viewIntro(kicker, text) {
  const box = el("div", "view-intro");
  box.innerHTML =
    `<span class="view-intro-kicker">${esc(kicker)}</span>` +
    `<p class="view-intro-text">${text}</p>`;
  return box;
}
