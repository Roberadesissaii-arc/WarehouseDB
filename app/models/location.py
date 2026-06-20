"""Location hierarchy data access: warehouses, sections, shelves."""
from ..database import get_db

_DELETABLE = {"warehouses", "sections", "shelves", "items", "robots", "tasks"}


def fetch_tree():
    """Full Warehouse -> Section -> Shelf hierarchy with item counts."""
    db = get_db()
    counts = {
        row["shelf_id"]: row["c"]
        for row in db.execute("SELECT shelf_id, COUNT(*) AS c FROM items GROUP BY shelf_id")
    }
    sections_by_wh = {}
    for row in db.execute("SELECT * FROM sections ORDER BY warehouse_id, name"):
        sections_by_wh.setdefault(row["warehouse_id"], []).append(row)
    shelves_by_sec = {}
    for row in db.execute("SELECT * FROM shelves ORDER BY section_id, code"):
        shelves_by_sec.setdefault(row["section_id"], []).append(row)

    tree = []
    for w in db.execute("SELECT * FROM warehouses ORDER BY name"):
        sections = []
        for s in sections_by_wh.get(w["id"], []):
            shelves = [
                {
                    "id": sh["id"],
                    "code": sh["code"],
                    "item_count": counts.get(sh["id"], 0),
                }
                for sh in shelves_by_sec.get(s["id"], [])
            ]
            sections.append({"id": s["id"], "name": s["name"], "shelves": shelves})
        tree.append({"id": w["id"], "name": w["name"], "sections": sections})
    return tree


def create_warehouse(name):
    db = get_db()
    cur = db.execute("INSERT INTO warehouses(name) VALUES(?)", (name,))
    db.commit()
    return cur.lastrowid


def create_section(warehouse_id, name):
    db = get_db()
    cur = db.execute(
        "INSERT INTO sections(warehouse_id, name) VALUES(?,?)", (warehouse_id, name)
    )
    db.commit()
    return cur.lastrowid


def create_shelf(section_id, code):
    db = get_db()
    cur = db.execute("INSERT INTO shelves(section_id, code) VALUES(?,?)", (section_id, code))
    db.commit()
    return cur.lastrowid


def delete_entity(table, entity_id):
    """Delete a row by id. Foreign keys cascade (or null robots) per the schema."""
    assert table in _DELETABLE
    db = get_db()
    db.execute(f"DELETE FROM {table} WHERE id=?", (entity_id,))
    db.commit()
