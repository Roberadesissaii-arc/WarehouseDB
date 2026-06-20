# Unit `C8A21`

ESP32 firmware for physical robot **`WarehouseDB_C8A21`**.

The display name (e.g. “Atlas”, “Nexus One”) is set when you pair in the web app — not in the folder name.

## Configure before upload (config.h)

Each folder includes **`config.h`** — open it and set your Wi-Fi and server IP before uploading. Do not put passwords in the `.ino` file.

## Upload

1. Open **`WarehouseDB_C8A21.ino`** in Arduino IDE.
2. Select board **ESP32 Dev Module** and the correct COM port.
3. Upload.

## Pair in the app

1. OLED shows a **6-digit code**.
2. **Fleet → PAIR ROBOT** → enter code and choose a display name.
3. Screen shows **ONLINE** when connected.

## Libraries

Adafruit SSD1306, Adafruit GFX, ArduinoJson (v7), ESP32 board package.

See `../README.md` for naming rules and adding more robots.
