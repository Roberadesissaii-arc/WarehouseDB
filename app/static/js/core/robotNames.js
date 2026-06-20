// Suggested display names for new robots (pairing forms) — short for small OLED screens.
const WORDS = [
  "Scout", "Hauler", "Picker", "Rover", "Bolt", "Glider", "Atlas", "Vector",
  "Nomad", "Pulse", "Forge", "Lumen", "Drift", "Harbor", "Swift", "Keen",
];

function pick(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

function pad2(n) {
  return String(n).padStart(2, "0");
}

/** One word + number, e.g. Scout-06 — avoids long names on robot displays. */
export function randomRobotName(exclude = []) {
  const taken = new Set(exclude.map((n) => String(n || "").toLowerCase().trim()).filter(Boolean));
  for (let i = 0; i < 64; i++) {
    const num = pad2(Math.floor(Math.random() * 90) + 10);
    const name = `${pick(WORDS)}-${num}`;
    if (!taken.has(name.toLowerCase())) return name;
  }
  return `${pick(WORDS)}-${pad2(Math.floor(Math.random() * 900) + 100)}`;
}

/** Wire a name input + refresh button. Returns a function to fill a new suggestion. */
export function wireRobotNameField(input, refreshBtn, getExclude = () => []) {
  const fill = () => {
    if (!input) return;
    const exclude = typeof getExclude === "function" ? getExclude() : [];
    const current = String(input.value || "").trim();
    if (current) exclude.push(current);
    input.value = randomRobotName(exclude);
  };
  refreshBtn?.addEventListener("click", (e) => {
    e.preventDefault();
    fill();
  });
  return fill;
}
