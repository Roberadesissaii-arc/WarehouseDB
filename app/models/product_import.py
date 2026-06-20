"""Import product catalog from JSON (additive — does not wipe existing data)."""
import json

from ..database import get_db
from . import item

MAX_ITEMS = 5000
MAX_NAME_LEN = 120
MAX_CODE_LEN = 32
MAX_SKU_LEN = 64


def _clip(text, limit):
    return (str(text or "")).strip()[:limit]


def _find_shelf_id(db, warehouse_name, aisle_name, bay_code):
    row = db.execute(
        """
        SELECT shelves.id
        FROM shelves
        JOIN sections ON shelves.section_id = sections.id
        JOIN warehouses ON sections.warehouse_id = warehouses.id
        WHERE warehouses.name = ? AND sections.name = ? AND shelves.code = ?
        """,
        (warehouse_name, aisle_name, bay_code),
    ).fetchone()
    return row["id"] if row else None


def _product_notes(age_days, notes):
    parts = []
    if age_days is not None and str(age_days).strip() != "":
        try:
            days = int(age_days)
            if days >= 0:
                parts.append(f"Stocked {days} day{'s' if days != 1 else ''}")
        except (TypeError, ValueError):
            pass
    extra = _clip(notes, 500)
    if extra:
        parts.append(extra)
    return " · ".join(parts) if parts else None


def import_products(raw):
    """Add items from a product catalog JSON file. Locations must already exist."""
    if isinstance(raw, (bytes, str)):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid JSON file") from exc
    elif isinstance(raw, dict):
        data = raw
    else:
        raise ValueError("Invalid import format")

    if isinstance(data.get("warehouses"), list):
        raise ValueError(
            "This looks like a full backup file. "
            "Use Settings → Storage → Import JSON backup instead."
        )

    products = data.get("products")
    if not isinstance(products, list):
        raise ValueError('JSON must include a "products" array')

    if len(products) > MAX_ITEMS:
        raise ValueError(f"Too many products (max {MAX_ITEMS})")

    db = get_db()
    created = 0
    skipped = 0
    errors = []

    for index, row in enumerate(products, start=1):
        if not isinstance(row, dict):
            errors.append(f"Row {index}: must be an object")
            skipped += 1
            continue

        name = _clip(row.get("name"), MAX_NAME_LEN)
        warehouse = _clip(row.get("warehouse"), MAX_NAME_LEN)
        aisle = _clip(row.get("aisle") or row.get("section"), MAX_NAME_LEN)
        bay = _clip(row.get("bay") or row.get("shelf"), MAX_CODE_LEN)
        sku = _clip(row.get("sku"), MAX_SKU_LEN) or None

        if not name:
            errors.append(f"Row {index}: name is required")
            skipped += 1
            continue
        if not warehouse or not aisle or not bay:
            errors.append(f"Row {index} ({name}): warehouse, aisle, and bay are required")
            skipped += 1
            continue

        shelf_id = _find_shelf_id(db, warehouse, aisle, bay)
        if not shelf_id:
            errors.append(
                f"Row {index} ({name}): location not found — "
                f"{warehouse} / {aisle} / {bay}"
            )
            skipped += 1
            continue

        try:
            qty = int(row.get("quantity") or 1)
        except (TypeError, ValueError):
            errors.append(f"Row {index} ({name}): quantity must be a number")
            skipped += 1
            continue
        if qty < 1:
            qty = 1

        notes = _product_notes(row.get("age_days"), row.get("notes"))
        item.create_item(name, sku, shelf_id, notes, qty)
        created += 1

    return {
        "created": created,
        "skipped": skipped,
        "errors": errors[:20],
        "error_count": len(errors),
    }
