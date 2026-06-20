"""Sample warehouse layout and products for an empty database.

Real data is written to SQLite (instance/warehouse.db). JSON files such as
json/products.sample.json are never loaded automatically — staff import those
from Settings → Data when needed.

Demo seed includes warehouses, sections, bays, and items only. Robots are never
fabricated: a robot row is created only when staff pair real hardware.
"""
from .connection import get_db

# Warehouse -> sections -> bays + a pool of realistic products per section.
WAREHOUSES = [
    {
        "name": "Central Distribution",
        "sections": [
            {"name": "Receiving Dock", "sku": "RCV", "bays": ["RC-01", "RC-02"],
             "items": ["Pallet Jack", "Shrink Wrap Roll", "Receiving Scanner", "Dock Plate", "Stretch Film", "Inbound Label Roll"]},
            {"name": "Small Parts", "sku": "SPT", "bays": ["SP-01", "SP-02", "SP-03"],
             "items": ["M6 Hex Bolt 100pk", "Cable Ties 200mm", "Rubber Grommet Set", "Spring Washer M8", "Cotter Pin Assortment", "Nylon Spacer Kit", "Hose Clamp 50mm", "O-Ring Box", "Threaded Insert M5", "Split Pin Tray"]},
            {"name": "Electronics", "sku": "ELC", "bays": ["EL-01", "EL-02"],
             "items": ["Lidar Module", "6-Axis Servo Arm", "Gripper Claw v3", "Motor Driver Board", "Proximity Sensor", "Ethernet Switch 8-Port", "Single-Board Computer", "HD Camera Module", "Power Supply 12V", "Stepper Motor NEMA17"]},
            {"name": "Outbound Staging", "sku": "OUT", "bays": ["OB-01", "OB-02"],
             "items": ["Courier Mailer Bag", "Carton 400x300", "Fragile Tape", "Pallet Wrap", "Shipping Label Roll", "Void Fill Pillows"]},
        ],
    },
    {
        "name": "Cold Chain Facility",
        "sections": [
            {"name": "Chilled Storage", "sku": "CHL", "bays": ["CH-01", "CH-02"],
             "items": ["Yogurt Crate", "Fresh Salad Box", "Deli Meat Tray", "Cheese Wheel", "Chilled Ready Meal", "Smoothie Pack"]},
            {"name": "Frozen Vault", "sku": "FRZ", "bays": ["FZ-01", "FZ-02"],
             "items": ["Frozen Peas 1kg", "Ice Cream Tub", "Frozen Fish Fillet", "Frozen Pizza", "Gel Ice Pack", "Frozen Berries"]},
            {"name": "Dairy & Produce", "sku": "DRY", "bays": ["DP-01", "DP-02"],
             "items": ["Milk 2L", "Butter Block", "Egg Tray 30", "Apple Crate", "Banana Box", "Tomato Flat"]},
            {"name": "Dispatch", "sku": "DSP", "bays": ["DS-01"],
             "items": ["Insulated Shipper", "Dry Ice Pack", "Cold Chain Logger", "Thermal Blanket"]},
        ],
    },
    {
        "name": "Bulk & Pallet Yard",
        "sections": [
            {"name": "Pallet Racking A", "sku": "PRA", "bays": ["PA-01", "PA-02", "PA-03"],
             "items": ["Cement Bag 25kg", "Sand Bag", "Gravel Sack", "Brick Pallet", "Timber Plank Bundle", "Plasterboard Sheet", "Roofing Felt Roll"]},
            {"name": "Pallet Racking B", "sku": "PRB", "bays": ["PB-01", "PB-02"],
             "items": ["Paint Drum 20L", "Adhesive Pail", "Floor Tile Pallet", "Insulation Roll", "Sealant Crate"]},
            {"name": "Heavy Goods", "sku": "HVY", "bays": ["HG-01", "HG-02"],
             "items": ["Steel Beam 3m", "Engine Block", "Generator Unit", "Hydraulic Pump", "Gearbox Assembly"]},
            {"name": "Hazmat Cage", "sku": "HAZ", "bays": ["HZ-01"],
             "items": ["Lithium Battery Pack", "Solvent Canister", "Aerosol Crate", "Compressed Gas Cylinder", "Battery Pack 48V"]},
        ],
    },
    {
        "name": "Returns & Spares",
        "sections": [
            {"name": "Inbound Returns", "sku": "RET", "bays": ["IR-01", "IR-02"],
             "items": ["Returned Tablet", "Returned Headphones", "Damaged Monitor", "Open-Box Blender", "Returned Router", "Returned Keyboard"]},
            {"name": "Refurbishment", "sku": "RFB", "bays": ["RF-01"],
             "items": ["Refurb Laptop", "Replacement Screen", "Swap Battery", "Reflow Station"]},
            {"name": "Spare Parts", "sku": "SPR", "bays": ["SPR-01", "SPR-02"],
             "items": ["Conveyor Belt 2m", "Drive Chain", "Bearing 6204", "Fuse Box", "Relay 24V", "Limit Switch", "Charging Dock", "Timing Belt", "Coupling 25mm", "Idler Pulley"]},
            {"name": "Quarantine", "sku": "QAR", "bays": ["QR-01"],
             "items": ["Recalled Charger", "Suspect Battery", "Hold Item", "Inspection Pending Unit"]},
        ],
    },
]

# Pairing codes 100001–100010 were used by an older demo seed. Real robots claim with device_id.
_DEMO_FAKE_PAIRING_CODES = tuple(f"{100000 + i:06d}" for i in range(1, 11))


def _insert_sample(db):
    """Insert warehouse structure and items. Returns item count."""
    item_count = 0

    for wh in WAREHOUSES:
        wid = db.execute("INSERT INTO warehouses(name) VALUES(?)", (wh["name"],)).lastrowid
        for sec in wh["sections"]:
            sid = db.execute(
                "INSERT INTO sections(warehouse_id, name) VALUES(?,?)", (wid, sec["name"])
            ).lastrowid
            bay_ids = [
                db.execute("INSERT INTO shelves(section_id, code) VALUES(?,?)", (sid, code)).lastrowid
                for code in sec["bays"]
            ]
            for i, product in enumerate(sec["items"]):
                shelf_id = bay_ids[i % len(bay_ids)]
                sku = f"{sec['sku']}-{i + 1:03d}"
                db.execute(
                    "INSERT INTO items(name, sku, shelf_id, quantity) VALUES(?,?,?,?)",
                    (product, sku, shelf_id, (i % 24) + 1),
                )
                item_count += 1

    from ..models import home_bay
    home_bay.ensure_defaults(db)
    db.commit()
    return item_count


DEMO_SUPPRESSED_KEY = "warehouse_demo_suppressed"


def _wipe_warehouse_graph(db):
    """Wipe inventory, fleet, tasks, and alerts. Keeps users & settings."""
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("DELETE FROM notifications")
    db.execute("DELETE FROM tasks")
    db.execute("DELETE FROM robots")
    db.execute("DELETE FROM warehouses")
    db.execute("DELETE FROM items")
    db.execute("DELETE FROM shelves")
    db.execute("DELETE FROM sections")


def purge_demo_fleet(db=None):
    """Remove legacy demo robots that were seeded without real hardware."""
    db = db or get_db()
    placeholders = ",".join("?" * len(_DEMO_FAKE_PAIRING_CODES))
    rows = db.execute(
        f"SELECT id FROM robots WHERE pairing_code IN ({placeholders}) AND device_id IS NULL",
        _DEMO_FAKE_PAIRING_CODES,
    ).fetchall()
    if not rows:
        return 0
    ids = [row["id"] for row in rows]
    id_placeholders = ",".join("?" * len(ids))
    db.execute(f"DELETE FROM robots WHERE id IN ({id_placeholders})", ids)
    db.commit()
    return len(ids)


def seed_if_empty():
    """Load demo locations/items on a fresh database, or repair orphaned rows."""
    db = get_db()
    purge_demo_fleet(db)

    if db.execute("SELECT COUNT(*) AS n FROM warehouses").fetchone()["n"] > 0:
        return

    orphans = (
        db.execute("SELECT COUNT(*) AS n FROM sections").fetchone()["n"]
        + db.execute("SELECT COUNT(*) AS n FROM items").fetchone()["n"]
    )
    if orphans:
        _wipe_warehouse_graph(db)
        db.commit()

    if db.execute(
        "SELECT 1 FROM settings WHERE key=? AND value='1'",
        (DEMO_SUPPRESSED_KEY,),
    ).fetchone():
        return

    _insert_sample(db)


def clear_warehouse_data():
    """Wipe inventory, fleet, tasks, and alerts. Keeps users & settings."""
    db = get_db()
    _wipe_warehouse_graph(db)
    db.execute(
        "INSERT INTO settings(key, value) VALUES(?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (DEMO_SUPPRESSED_KEY, "1"),
    )
    db.commit()


def load_demo_data():
    """Load demo warehouses and items. Only when no warehouses exist. No robots."""
    db = get_db()
    if db.execute("SELECT COUNT(*) AS n FROM warehouses").fetchone()["n"] > 0:
        raise ValueError("Warehouse data already exists — clear it first if you want demo content")
    _wipe_warehouse_graph(db)
    db.execute("DELETE FROM settings WHERE key=?", (DEMO_SUPPRESSED_KEY,))
    item_count = _insert_sample(db)
    return {
        "warehouses": len(WAREHOUSES),
        "items": item_count,
    }


def reset_sample_data():
    """Password-gated reset from Settings — clears all warehouse data (no sample re-seed)."""
    clear_warehouse_data()
