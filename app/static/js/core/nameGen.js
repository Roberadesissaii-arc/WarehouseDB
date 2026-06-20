// Random default names for warehouses, sections, and bays.
const pick = (arr) => arr[Math.floor(Math.random() * arr.length)];
const digit = () => String(Math.floor(Math.random() * 9) + 1);
const pad2 = (n) => String(n).padStart(2, "0");

const WAREHOUSE_PREFIX = [
  "North", "South", "East", "West", "Central", "Riverside", "Harbor",
  "Metro", "District", "Valley", "Summit", "Gateway", "Frontier", "Union",
];
const WAREHOUSE_SUFFIX = [
  "Depot", "Distribution", "Hub", "Warehouse", "Yard", "Terminal", "Facility", "Center",
];

const SECTION_NAMES = [
  "Receiving Dock", "Outbound Staging", "Small Parts", "Electronics", "Cold Storage",
  "Frozen Vault", "Pallet Racking", "Heavy Goods", "Returns Intake", "Spare Parts",
  "Quarantine", "Dispatch", "Pick Zone", "Bulk Storage", "Hazmat Cage",
  "Cross-Dock", "Sortation", "Pack & Ship", "Overflow", "Inspection",
];

const BAY_LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ";

export function randomWarehouseName() {
  return `${pick(WAREHOUSE_PREFIX)} ${pick(WAREHOUSE_SUFFIX)}`;
}

export function randomSectionName() {
  const base = pick(SECTION_NAMES);
  if (Math.random() < 0.35) return `${base} ${pick(["A", "B", "C", "North", "South"])}`;
  return base;
}

export function randomBayCode(existing = new Set()) {
  for (let i = 0; i < 40; i++) {
    const letter = BAY_LETTERS[Math.floor(Math.random() * BAY_LETTERS.length)];
    const code = `${letter}${digit()}-${pad2(Math.floor(Math.random() * 99) + 1)}`;
    if (!existing.has(code)) return code;
  }
  return `B${digit()}-${pad2(Date.now() % 100)}`;
}
