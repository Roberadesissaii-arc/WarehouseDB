"""Item data access. Items resolve up to their full warehouse location."""
from ..database import get_db

# Resolve an item all the way up to its warehouse in one query.
_ITEM_LOCATION_SQL = """
SELECT items.id, items.name, items.sku, items.quantity, items.notes, items.created_at,
       items.shelf_id,
       shelves.code    AS shelf_code,
       sections.id     AS section_id,
       sections.name   AS section_name,
       warehouses.id   AS warehouse_id,
       warehouses.name AS warehouse_name
FROM items
JOIN shelves    ON items.shelf_id        = shelves.id
JOIN sections   ON shelves.section_id    = sections.id
JOIN warehouses ON sections.warehouse_id = warehouses.id
"""


def _parse_quantity(raw, default=1):
    if raw is None or raw == "":
        return default
    qty = int(raw)
    if qty < 1:
        raise ValueError("Quantity must be at least 1")
    return qty


def _to_dict(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "sku": row["sku"],
        "quantity": row["quantity"] if row["quantity"] is not None else 1,
        "notes": row["notes"],
        "created_at": row["created_at"],
        "shelf_id": row["shelf_id"],
        "location": {
            "warehouse_id": row["warehouse_id"],
            "warehouse": row["warehouse_name"],
            "section_id": row["section_id"],
            "section": row["section_name"],
            "shelf": row["shelf_code"],
            "path": f'{row["warehouse_name"]} / {row["section_name"]} / {row["shelf_code"]}',
        },
    }


def search_items(query=None, shelf_id=None):
    sql, params, clauses = _ITEM_LOCATION_SQL, [], []
    if shelf_id:
        clauses.append("items.shelf_id = ?")
        params.append(shelf_id)
    if query:
        clauses.append("(items.name LIKE ? OR items.sku LIKE ?)")
        params += [f"%{query}%", f"%{query}%"]
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY items.created_at DESC, items.id DESC"
    return [_to_dict(r) for r in get_db().execute(sql, params)]


def get_item(item_id):
    row = get_db().execute(_ITEM_LOCATION_SQL + " WHERE items.id = ?", (item_id,)).fetchone()
    return _to_dict(row) if row else None


def get_item_by_sku(sku):
    sku = (sku or "").strip()
    if not sku:
        return None
    row = get_db().execute(
        _ITEM_LOCATION_SQL + " WHERE items.sku = ? COLLATE NOCASE",
        (sku,),
    ).fetchone()
    return _to_dict(row) if row else None


def create_item(name, sku, shelf_id, notes, quantity=1):
    db = get_db()
    qty = _parse_quantity(quantity)
    cur = db.execute(
        "INSERT INTO items(name, sku, shelf_id, quantity, notes) VALUES(?,?,?,?,?)",
        (name, sku or None, shelf_id, qty, notes or None),
    )
    db.commit()
    return cur.lastrowid


def update_item(item_id, name, sku, shelf_id, notes, quantity=None):
    db = get_db()
    existing = get_item(item_id)
    qty = _parse_quantity(quantity if quantity is not None else (existing or {}).get("quantity", 1))
    db.execute(
        "UPDATE items SET name=?, sku=?, shelf_id=?, quantity=?, notes=? WHERE id=?",
        (name, sku or None, shelf_id, qty, notes or None, item_id),
    )
    db.commit()
    return get_item(item_id)
