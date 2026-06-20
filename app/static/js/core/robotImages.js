// Chassis art + catalog — staff pick a model when pairing (unit-amr-01 … unit-amr-10).
export const UNIT_IMAGE_COUNT = 10;

const PAD = String(UNIT_IMAGE_COUNT).length;

export const UNIT_CATALOG = [
  { id: 1, code: "unit-amr-01", brand: "Atlas MK-I" },
  { id: 2, code: "unit-amr-02", brand: "Vector S2" },
  { id: 3, code: "unit-amr-03", brand: "Nomad XR" },
  { id: 4, code: "unit-amr-04", brand: "Forge Hauler" },
  { id: 5, code: "unit-amr-05", brand: "Lumen Glide" },
  { id: 6, code: "unit-amr-06", brand: "Drift Courier" },
  { id: 7, code: "unit-amr-07", brand: "Harbor Dock" },
  { id: 8, code: "unit-amr-08", brand: "Swift Pallet" },
  { id: 9, code: "unit-amr-09", brand: "Keen Scout" },
  { id: 10, code: "unit-amr-10", brand: "Pulse Runner" },
];

export function unitById(id) {
  return UNIT_CATALOG.find((u) => u.id === Number(id)) || UNIT_CATALOG[0];
}

export function unitImageFile(unitImage) {
  const n = Number(unitImage);
  if (!Number.isInteger(n) || n < 1 || n > UNIT_IMAGE_COUNT) return UNIT_CATALOG[0].code + ".png";
  return `unit-amr-${String(n).padStart(PAD, "0")}.png`;
}

export function robotImageUrl(unitImage) {
  return `/static/images/${unitImageFile(unitImage)}`;
}
