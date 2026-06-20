# WarehouseDB — robot firmware

Two robot folders — one per physical ESP32:

| Folder | Unit ID |
|--------|---------|
| `WarehouseDB_55EF4` | `55EF4` |
| `WarehouseDB_C8A21` | `C8A21` |

Pattern: `Arduino/WarehouseDB_<unitId>/` (e.g. `WarehouseDB_55EF4`). Display names are set when you pair in the web app.

## config.h (required for upload)

Each folder includes **`config.h`** so Arduino IDE can compile. **Edit it before upload:**

- `WIFI_SSID` / `WIFI_PASSWORD` — your 2.4 GHz network
- `WAREHOUSE_HOST` — LAN IP of the PC running WarehouseDB (`python run.py` prints this)
- `ROBOT_UNIT_ID` — must match the folder suffix

Do not put passwords in the `.ino` file.

`config.h.example` is a backup copy of the template.

## Upload

1. Open the robot folder in Arduino IDE (e.g. `WarehouseDB_C8A21.ino`).
2. Edit **`config.h`** in that same folder.
3. Board: **ESP32 Dev Module** → Upload.

## Add another robot

Copy `WarehouseDB_55EF4` → `WarehouseDB_<newUnitId>`, rename the `.ino`, update `ROBOT_UNIT_ID` in `config.h`.
