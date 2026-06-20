// config.h — edit Wi-Fi and server settings below, then upload the sketch.
#pragma once

#define ROBOT_UNIT_ID "55EF4"
#define ROBOT_NVS_NS "wdb_55ef4"

#define WIFI_SSID "AIR Cloud"
#define WIFI_PASSWORD "saved+by+grace"

#define WAREHOUSE_HOST "192.168.4.41"
#define WAREHOUSE_PORT 8000

#define OLED_SDA 21
#define OLED_SCL 22
#define OLED_ADDRESS 0x3C

#define CLAIM_POLL_MS 2000
#define HEARTBEAT_MS 1000
#define TASK_POLL_MS 5000

#define BATTERY_PIN -1
#define BATTERY_MIN_MV 3200
#define BATTERY_MAX_MV 4200
#define BATTERY_DIVIDER 2.0f
