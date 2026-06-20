// Pair-robot modal (desktop) — mobile goes to /fleet/pair instead.
import { $ } from "../core/dom.js";
import { isMobileViewport } from "../core/viewport.js";
import { configurePairFlow, initPairRobotFlow, preparePairForm } from "../core/pairRobotFlow.js";

configurePairFlow({ onExit: () => {} });
initPairRobotFlow();

export function newRobot() {
  $("#robot-title").textContent = "PAIR ROBOT";
  preparePairForm({ focusCode: true });
}

export function openPairRobot() {
  if (isMobileViewport()) {
    location.href = "/fleet/pair";
    return;
  }
  newRobot();
}
