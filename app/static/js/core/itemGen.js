// Suggested product names and unique SKU codes for new inventory items.
import { store } from "./store.js";

const pick = (arr) => arr[Math.floor(Math.random() * arr.length)];
const pad2 = (n) => String(n).padStart(2, "0");

const PRODUCT_NAMES = [
  "Pallet Jack", "Shrink Wrap Roll", "Receiving Scanner", "Dock Plate", "Stretch Film", "Inbound Label Roll",
  "M6 Hex Bolt 100pk", "Cable Ties 200mm", "Rubber Grommet Set", "Spring Washer M8", "Cotter Pin Assortment",
  "Nylon Spacer Kit", "Hose Clamp 50mm", "O-Ring Box", "Threaded Insert M5", "Split Pin Tray",
  "Lidar Module", "6-Axis Servo Arm", "Gripper Claw v3", "Motor Driver Board", "Proximity Sensor",
  "Ethernet Switch 8-Port", "Single-Board Computer", "HD Camera Module", "Power Supply 12V", "Stepper Motor NEMA17",
  "Courier Mailer Bag", "Carton 400x300", "Fragile Tape", "Pallet Wrap", "Shipping Label Roll", "Void Fill Pillows",
  "Yogurt Crate", "Fresh Salad Box", "Deli Meat Tray", "Cheese Wheel", "Chilled Ready Meal", "Smoothie Pack",
  "Frozen Peas 1kg", "Ice Cream Tub", "Frozen Fish Fillet", "Frozen Pizza", "Gel Ice Pack", "Frozen Berries",
  "Milk 2L", "Butter Block", "Egg Tray 30", "Apple Crate", "Banana Box", "Tomato Flat",
  "Insulated Shipper", "Dry Ice Pack", "Cold Chain Logger", "Thermal Blanket",
  "Cement Bag 25kg", "Sand Bag", "Gravel Sack", "Brick Pallet", "Timber Plank Bundle", "Plasterboard Sheet",
  "Roofing Felt Roll", "Paint Drum 20L", "Adhesive Pail", "Floor Tile Pallet", "Insulation Roll", "Sealant Crate",
  "Steel Beam 3m", "Engine Block", "Generator Unit", "Hydraulic Pump", "Gearbox Assembly",
  "Lithium Battery Pack", "Solvent Canister", "Aerosol Crate", "Compressed Gas Cylinder", "Battery Pack 48V",
  "Returned Tablet", "Returned Headphones", "Damaged Monitor", "Open-Box Blender", "Returned Router", "Returned Keyboard",
  "Refurb Laptop", "Replacement Screen", "Swap Battery", "Reflow Station",
  "Conveyor Belt 2m", "Drive Chain", "Bearing 6204", "Fuse Box", "Relay 24V", "Limit Switch", "Charging Dock",
  "Timing Belt", "Coupling 25mm", "Idler Pulley", "Recalled Charger", "Suspect Battery", "Hold Item", "Inspection Pending Unit",
];

export function shelfContext(shelfId, tree = store.tree) {
  const id = Number(shelfId);
  if (!id) return null;
  for (const w of tree) {
    for (const s of w.sections) {
      for (const sh of s.shelves) {
        if (sh.id === id) {
          return {
            warehouse: w.name,
            section: s.name,
            sectionId: s.id,
            bay: sh.code,
          };
        }
      }
    }
  }
  return null;
}

function skusInSection(sectionId, items) {
  return items
    .filter((it) => it.location?.section_id == sectionId && it.sku)
    .map((it) => String(it.sku).trim());
}

export function sectionSkuPrefix(sectionName, sectionSkus = []) {
  const counts = new Map();
  for (const sku of sectionSkus) {
    const m = /^([A-Za-z]{2,4})-/.exec(String(sku).trim());
    if (m) {
      const p = m[1].toUpperCase();
      counts.set(p, (counts.get(p) || 0) + 1);
    }
  }
  if (counts.size) {
    return [...counts.entries()].sort((a, b) => b[1] - a[1])[0][0];
  }

  const words = String(sectionName || "")
    .trim()
    .split(/\s+/)
    .filter((w) => w.length > 1);
  if (words.length >= 3) return words.slice(0, 3).map((w) => w[0]).join("").toUpperCase();
  if (words.length === 2) return (words[0].slice(0, 2) + words[1][0]).toUpperCase().slice(0, 3);
  const one = words[0] || "ITM";
  return one.slice(0, 3).toUpperCase().padEnd(3, "X");
}

function takenSkus(items) {
  return new Set(
    items.map((it) => String(it.sku || "").trim().toUpperCase()).filter(Boolean),
  );
}

function takenNames(items, excludeItemId = null) {
  return new Set(
    items
      .filter((it) => excludeItemId == null || it.id != excludeItemId)
      .map((it) => String(it.name || "").trim().toLowerCase())
      .filter(Boolean),
  );
}

function maxSkuNumber(prefix, skus) {
  let max = 0;
  const re = new RegExp(`^${prefix}-(\\d+)$`, "i");
  for (const sku of skus) {
    const m = re.exec(String(sku).trim());
    if (m) max = Math.max(max, parseInt(m[1], 10));
  }
  return max;
}

/** Unique product name, e.g. "Lidar Module". */
export function randomItemName(items = store.items, excludeItemId = null) {
  const taken = takenNames(items, excludeItemId);
  for (let i = 0; i < 80; i++) {
    const name = pick(PRODUCT_NAMES);
    if (!taken.has(name.toLowerCase())) return name;
  }
  const base = pick(PRODUCT_NAMES);
  for (let n = 10; n < 100; n++) {
    const name = `${base} ${n}`;
    if (!taken.has(name.toLowerCase())) return name;
  }
  return `${pick(PRODUCT_NAMES)} ${Date.now() % 1000}`;
}

/** Unique SKU for a bay/section, e.g. GRP-22 or HVY-014. */
export function randomItemSku(shelfId, items = store.items, tree = store.tree) {
  const ctx = shelfContext(shelfId, tree);
  const taken = takenSkus(items);
  const prefix = ctx
    ? sectionSkuPrefix(ctx.section, skusInSection(ctx.sectionId, items))
    : "ITM";

  const related = [
    ...skusInSection(ctx?.sectionId, items),
    ...items.map((it) => it.sku).filter(Boolean),
  ];
  let next = maxSkuNumber(prefix, related) + 1;

  for (let n = next; n < next + 500; n++) {
    const sku = `${prefix}-${n}`;
    if (!taken.has(sku.toUpperCase())) return sku;
  }

  for (let i = 0; i < 80; i++) {
    const sku = `${prefix}-${pad2(Math.floor(Math.random() * 98) + 1)}`;
    if (!taken.has(sku.toUpperCase())) return sku;
  }

  return `${prefix}-${Date.now() % 10000}`;
}
