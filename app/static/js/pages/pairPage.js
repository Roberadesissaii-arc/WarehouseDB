// Full-screen pair robot flow for mobile (/fleet/pair).
import { loadData } from "../core/store.js";
import { configurePairFlow, initPairRobotFlow, preparePairForm } from "../core/pairRobotFlow.js";
import { wireFleetAlertBar } from "../core/fleetAlerts.js";

configurePairFlow({ onExit: () => { location.href = "/fleet"; } });
initPairRobotFlow();
wireFleetAlertBar();

(async () => {
  await loadData({ silent: true });
  preparePairForm({ focusCode: false });
})();
