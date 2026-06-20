// First-card “create” affordance used inside board grids.
import { el, icon } from "./dom.js";

export function createCard({ variant, label, sub, onClick }) {
  const card = el(
    "button",
    `create-card create-card--${variant}`,
    `<span class="create-card-plus">${icon("plus", "ic-lg")}</span>` +
    `<span class="create-card-label">${label}</span>` +
    `<span class="create-card-sub">${sub}</span>`,
  );
  card.type = "button";
  card.onclick = onClick;
  return card;
}
