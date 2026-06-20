"""Robot chassis catalog — staff pick a model when pairing (like choosing a car trim)."""

UNIT_IMAGE_COUNT = 10

UNIT_CATALOG = [
    {"id": 1, "code": "unit-amr-01", "brand": "Atlas MK-I"},
    {"id": 2, "code": "unit-amr-02", "brand": "Vector S2"},
    {"id": 3, "code": "unit-amr-03", "brand": "Nomad XR"},
    {"id": 4, "code": "unit-amr-04", "brand": "Forge Hauler"},
    {"id": 5, "code": "unit-amr-05", "brand": "Lumen Glide"},
    {"id": 6, "code": "unit-amr-06", "brand": "Drift Courier"},
    {"id": 7, "code": "unit-amr-07", "brand": "Harbor Dock"},
    {"id": 8, "code": "unit-amr-08", "brand": "Swift Pallet"},
    {"id": 9, "code": "unit-amr-09", "brand": "Keen Scout"},
    {"id": 10, "code": "unit-amr-10", "brand": "Pulse Runner"},
]

_BY_ID = {row["id"]: row for row in UNIT_CATALOG}


def catalog():
    return list(UNIT_CATALOG)


def validate(unit_image):
    """Return a valid catalog id or raise ValueError."""
    try:
        slot = int(unit_image)
    except (TypeError, ValueError):
        raise ValueError("Select a chassis model for this robot") from None
    if slot not in _BY_ID:
        raise ValueError("Select a chassis model for this robot")
    return slot


def brand_for(unit_image):
    row = _BY_ID.get(int(unit_image) if unit_image is not None else 0)
    return row["brand"] if row else _BY_ID[1]["brand"]


def code_for(unit_image):
    row = _BY_ID.get(int(unit_image) if unit_image is not None else 0)
    return row["code"] if row else _BY_ID[1]["code"]
