/*
 * WarehouseDB — unit 55EF4
 * Folder: Arduino/WarehouseDB_55EF4/
 *
 * Wi-Fi, passwords, server IP → config.h only (copy config.h.example → config.h).
 * Pairing: OLED shows 6-digit code → Fleet → PAIR ROBOT in the web app.
 */

#include <Wire.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Preferences.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#include "config.h"

#ifndef ROBOT_NVS_NS
#define ROBOT_NVS_NS "warehousedb"
#endif
#ifndef ROBOT_UNIT_ID
#define ROBOT_UNIT_ID "unknown"
#endif

#define SCREEN_W 128
#define SCREEN_H 64
Adafruit_SSD1306 display(SCREEN_W, SCREEN_H, &Wire, -1);

Preferences prefs;

String pairingCode;
int robotId = 0;
bool paired = false;

unsigned long lastClaimMs = 0;
unsigned long lastHeartbeatMs = 0;
unsigned long lastTaskMs = 0;
String statusLine = "starting";
String robotName = "";
String robotReportStatus = "idle";
int activeTaskId = 0;
int heartbeatAuthFails = 0;
int lastBatteryPct = -1;

int readBatteryPercent() {
#if BATTERY_PIN < 0
  return -1;
#else
  int mv = analogReadMilliVolts(BATTERY_PIN);
  mv = (int)(mv * BATTERY_DIVIDER);
  if (mv <= BATTERY_MIN_MV) return 0;
  if (mv >= BATTERY_MAX_MV) return 100;
  return (mv - BATTERY_MIN_MV) * 100 / (BATTERY_MAX_MV - BATTERY_MIN_MV);
#endif
}

bool isAuthFailure(int code) {
  return code == 401 || code == 404;
}

void clearPairedState() {
  paired = false;
  robotId = 0;
  robotName = "";
  activeTaskId = 0;
  robotReportStatus = "idle";
  heartbeatAuthFails = 0;
  prefs.begin(ROBOT_NVS_NS, false);
  prefs.putBool("paired", false);
  prefs.putInt("robot_id", 0);
  prefs.putString("robot_name", "");
  prefs.end();
}

String warehouseBase() {
  return String("http://") + WAREHOUSE_HOST + ":" + String(WAREHOUSE_PORT);
}

String deviceId() {
  return WiFi.macAddress();
}

String randomPairingCode() {
  uint32_t n = 100000UL + (esp_random() % 900000UL);
  char buf[8];
  snprintf(buf, sizeof(buf), "%06lu", (unsigned long)n);
  return String(buf);
}

void loadStoredState() {
  prefs.begin(ROBOT_NVS_NS, true);
  pairingCode = prefs.getString("pair_code", "");
  robotId = prefs.getInt("robot_id", 0);
  paired = prefs.getBool("paired", false);
  robotName = prefs.getString("robot_name", "");
  prefs.end();

  if (pairingCode.length() != 6) {
    pairingCode = randomPairingCode();
    prefs.begin(ROBOT_NVS_NS, false);
    prefs.putString("pair_code", pairingCode);
    prefs.end();
  }
}

void savePairedState(int id, const String &name) {
  robotId = id;
  paired = true;
  robotName = name;
  prefs.begin(ROBOT_NVS_NS, false);
  prefs.putInt("robot_id", id);
  prefs.putBool("paired", true);
  prefs.putString("robot_name", name);
  prefs.end();
}

void drawCentered(const String &line1, const String &line2 = "", const String &line3 = "") {
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);

  display.setTextSize(1);
  display.setCursor(0, 0);
  display.println("WAREHOUSEDB");

  if (line1.length()) {
    display.setTextSize(2);
    int16_t x1, y1;
    uint16_t w, h;
    display.getTextBounds(line1.c_str(), 0, 0, &x1, &y1, &w, &h);
    display.setCursor((SCREEN_W - (int)w) / 2, 16);
    display.println(line1);
  }

  if (line2.length()) {
    display.setTextSize(1);
    int16_t x2, y2;
    uint16_t w2, h2;
    display.getTextBounds(line2.c_str(), 0, 0, &x2, &y2, &w2, &h2);
    display.setCursor((SCREEN_W - (int)w2) / 2, 40);
    display.println(line2);
  }

  if (line3.length()) {
    display.setTextSize(1);
    int16_t x3, y3;
    uint16_t w3, h3;
    display.getTextBounds(line3.c_str(), 0, 0, &x3, &y3, &w3, &h3);
    display.setCursor((SCREEN_W - (int)w3) / 2, 52);
    display.println(line3);
  }

  int batt = readBatteryPercent();
  if (batt >= 0) {
    display.setTextSize(1);
    String battLine = String(batt) + "%";
    display.setCursor(SCREEN_W - 28, 0);
    display.println(battLine);
  }

  display.display();
}

void showPairingScreen(const String &sub, const String &detail = "") {
  drawCentered(pairingCode, sub, detail);
}

void enterPairingMode(const String &sub, const String &detail = "") {
  clearPairedState();
  pairingCode = randomPairingCode();
  prefs.begin(ROBOT_NVS_NS, false);
  prefs.putString("pair_code", pairingCode);
  prefs.end();
  lastClaimMs = 0;
  showPairingScreen(sub, detail);
  Serial.printf("Pairing mode — new code %s\n", pairingCode.c_str());
}

void showPairedScreen(const String &sub) {
  String title = robotName.length() ? robotName : ("ROBOT " + String(robotId));
  if (title.length() > 10) title = title.substring(0, 10);
  drawCentered(title, "ONLINE", sub);
}

void showOfflineScreen(const String &sub) {
  String title = robotName.length() ? robotName : ("ROBOT " + String(robotId));
  if (title.length() > 10) title = title.substring(0, 10);
  drawCentered(title, "OFFLINE", sub);
}

void showTaskScreen(int taskId, const String &action) {
  String act = action;
  act.toUpperCase();
  if (act.length() > 10) act = act.substring(0, 10);
  drawCentered("#" + String(taskId), act, "ONLINE");
}

bool sendHeartbeat() {
  if (!paired || robotId <= 0) return false;

  HTTPClient http;
  String url = warehouseBase() + "/api/robots/" + String(robotId) + "/heartbeat";

  JsonDocument doc;
  doc["status"] = robotReportStatus;
  int batt = readBatteryPercent();
  if (batt >= 0) doc["battery_pct"] = batt;
#ifdef FIRMWARE_VERSION
  doc["firmware_version"] = FIRMWARE_VERSION;
#endif
  String body;
  serializeJson(doc, body);

  http.begin(url);
  http.addHeader("X-Robot-Code", pairingCode);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(3000);

  int code = http.POST(body);
  String response = http.getString();
  http.end();

  if (code == 200) {
    heartbeatAuthFails = 0;
    JsonDocument res;
    if (!deserializeJson(res, response)) {
      String name = res["name"] | "";
      if (name.length() && name != robotName) {
        robotName = name;
        prefs.begin(ROBOT_NVS_NS, false);
        prefs.putString("robot_name", name);
        prefs.end();
        Serial.printf("Display name updated: %s\n", name.c_str());
        if (activeTaskId <= 0) {
          showPairedScreen(robotReportStatus == "working" ? "working" : "idle");
        }
      }
    }
    return true;
  }

  Serial.printf("heartbeat HTTP %d\n", code);

  if (isAuthFailure(code)) {
    enterPairingMode("DISCONNECTED", "enter code in app");
    return false;
  }

  if (code < 0) {
    showOfflineScreen("no server");
  } else {
    showOfflineScreen("retrying");
  }
  return false;
}

bool connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return true;

  statusLine = "wifi...";
  drawCentered("Wi-Fi", WIFI_SSID, statusLine);

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 20000) {
    delay(250);
    Serial.print(".");
  }
  Serial.println();

  if (WiFi.status() != WL_CONNECTED) {
    statusLine = "wifi failed";
    drawCentered("Wi-Fi", "FAILED", "check config.h");
    return false;
  }

  statusLine = WiFi.localIP().toString();
  Serial.print("IP: ");
  Serial.println(statusLine);
  drawCentered("Wi-Fi OK", statusLine, "");
  delay(800);
  return true;
}

bool serverReachable() {
  HTTPClient http;
  String url = warehouseBase() + "/api/robots/ping";
  http.begin(url);
  http.setTimeout(5000);
  int code = http.GET();
  http.end();
  Serial.printf("ping %s -> %d\n", url.c_str(), code);
  return code == 200;
}

void showAlreadyPaired(const String &name) {
  String shortName = name;
  if (shortName.length() > 11) shortName = shortName.substring(0, 11);
  drawCentered("ALREADY", "PAIRED", shortName.length() ? shortName : "");
}

void showClaimError(int code, const String &response = "") {
  if (code == -1) {
    showPairingScreen("no server", WAREHOUSE_HOST);
    return;
  }
  if (code == -11) {
    showPairingScreen("timeout", WAREHOUSE_HOST);
    return;
  }
  if (code == 409 || code == 400) {
    JsonDocument res;
    if (!deserializeJson(res, response)) {
      const char *errCode = res["code"] | "";
      if (strcmp(errCode, "already_paired") == 0) {
        String name = res["robot"]["name"] | "";
        showAlreadyPaired(name);
        return;
      }
      if (strcmp(errCode, "code_in_use") == 0) {
        drawCentered("CODE IN", "USE", "SEE APP");
        return;
      }
    }
  }
  statusLine = "claim " + String(code);
  showPairingScreen(statusLine);
}

bool tryClaim() {
  HTTPClient http;
  String url = warehouseBase() + "/api/robots/claim";

  JsonDocument doc;
  doc["pairing_code"] = pairingCode;
  doc["device_id"] = deviceId();
  String body;
  serializeJson(doc, body);

  http.begin(url);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(8000);

  int code = http.POST(body);
  String response = http.getString();
  http.end();

  Serial.printf("claim HTTP %d: %s\n", code, response.c_str());

  if (code == 404) {
    statusLine = "waiting for staff";
    showPairingScreen("enter code in app");
    return false;
  }

  if (code != 200) {
    if (code == 409 || code == 400) {
      JsonDocument res;
      if (!deserializeJson(res, response)) {
        const char *errCode = res["code"] | "";
        if (strcmp(errCode, "already_paired") == 0) {
          int id = res["robot"]["id"] | 0;
          String name = res["robot"]["name"] | "Robot";
          if (id > 0) {
            savePairedState(id, name);
            showPairedScreen("connected");
            Serial.printf("Already paired as #%d %s\n", robotId, robotName.c_str());
            return true;
          }
          showAlreadyPaired(name);
          return false;
        }
      }
    }
    showClaimError(code, response);
    return false;
  }

  JsonDocument res;
  DeserializationError err = deserializeJson(res, response);
  if (err) {
    statusLine = "bad json";
    showPairingScreen(statusLine);
    return false;
  }

  int id = res["id"] | 0;
  String name = res["name"] | "Robot";
  if (id <= 0) {
    statusLine = "no robot id";
    showPairingScreen(statusLine);
    return false;
  }

  savePairedState(id, name);
  showPairedScreen("connected");
  Serial.printf("Paired as #%d %s\n", robotId, robotName.c_str());
  return true;
}

void pollTasks() {
  if (!paired || robotId <= 0) return;

  HTTPClient http;
  String url = warehouseBase() + "/api/robots/" + String(robotId) + "/tasks";

  http.begin(url);
  http.addHeader("X-Robot-Code", pairingCode);
  http.setTimeout(8000);

  int code = http.GET();
  String response = http.getString();
  http.end();

  Serial.printf("tasks HTTP %d\n", code);

  if (code != 200) {
    if (isAuthFailure(code)) {
      enterPairingMode("DISCONNECTED", "enter code in app");
      return;
    }
    showOfflineScreen("tasks " + String(code));
    return;
  }

  JsonDocument res;
  if (deserializeJson(res, response)) {
    showPairedScreen("bad tasks json");
    return;
  }

  activeTaskId = 0;
  String nextAction = "";
  JsonArray list = res.as<JsonArray>();
  for (JsonObject t : list) {
    const char *st = t["status"];
    if (!st) continue;
    if (strcmp(st, "queued") == 0 || strcmp(st, "in_progress") == 0) {
      activeTaskId = t["id"] | 0;
      nextAction = t["action"].as<String>();
      break;
    }
  }

  if (activeTaskId > 0) {
    if (nextAction.equalsIgnoreCase("charge")) robotReportStatus = "returning";
    else robotReportStatus = "working";
    showTaskScreen(activeTaskId, nextAction);
  } else {
    robotReportStatus = "idle";
    showPairedScreen("idle");
  }
}

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println("\nWarehouseDB");
  Serial.print("Unit ");
  Serial.println(ROBOT_UNIT_ID);

  Wire.begin(OLED_SDA, OLED_SCL);

#if BATTERY_PIN >= 0
  pinMode(BATTERY_PIN, INPUT);
#endif

  if (!display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDRESS)) {
    Serial.println("SSD1306 not found — check wiring / OLED_ADDRESS");
    for (;;) delay(1000);
  }

  display.clearDisplay();
  display.display();

  loadStoredState();

  if (!connectWiFi()) {
    for (;;) delay(5000);
  }

  if (paired && robotId > 0) {
    robotReportStatus = "idle";
    drawCentered(robotName.length() ? robotName : "ROBOT", "CONNECTING", "");
    lastHeartbeatMs = 0;
    lastTaskMs = 0;
    if (sendHeartbeat()) {
      pollTasks();
    } else if (!paired) {
      lastClaimMs = 0;
    }
  } else {
    if (!serverReachable()) {
      showPairingScreen("NO SERVER", WAREHOUSE_HOST);
    } else {
      showPairingScreen("ENTER IN APP", statusLine);
    }
    lastClaimMs = 0;
  }
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
    return;
  }

  unsigned long now = millis();

  if (!paired) {
    if (now - lastClaimMs >= CLAIM_POLL_MS) {
      lastClaimMs = now;
      if (!serverReachable()) {
        showPairingScreen("NO SERVER", WAREHOUSE_HOST);
      } else if (tryClaim()) {
        lastHeartbeatMs = 0;
        lastTaskMs = 0;
      }
    }
    return;
  }

  if (now - lastHeartbeatMs >= HEARTBEAT_MS) {
    lastHeartbeatMs = now;
    if (!sendHeartbeat()) return;
  }

  if (now - lastTaskMs >= TASK_POLL_MS) {
    lastTaskMs = now;
    pollTasks();
  }
}
