#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SH110X.h>
#include "time.h"
#include <TOTP.h>
#include <Preferences.h>
#include <RtcDS3231.h>

// --- SERVER ---
const char* serverBaseUrl = "https://YOUR-PROJECT-NAME.vercel.app";

// --- PINS ---
#define TOUCH_NEXT_PIN 13
#define TOUCH_PREV_PIN 12
#define TOUCH_SYNC_PIN 33
#define LED_PIN        2
#define I2C_SDA        21
#define I2C_SCL        22
#define i2c_Address    0x3c

// --- OBJECTS ---
Adafruit_SH1106G display = Adafruit_SH1106G(128, 64, &Wire, -1);
Preferences preferences;
RtcDS3231<TwoWire> Rtc(Wire);

// --- ACCOUNT STORAGE ---
struct Account {
  String name;
  String issuer;
  String secret;
  uint8_t hmacKey[20];
  int keyLength;
};
Account myAccounts[10];
int accountCount        = 0;
int currentAccountIndex = 0;

// --- CONFIG (loaded from NVS) ---
String cfg_ssid       = "";
String cfg_password   = "";
String cfg_userId     = "";
String cfg_deviceKey  = "";

// -------------------------------------------------------
// BASE32 DECODER
// -------------------------------------------------------
int base32Decode(String encoded, uint8_t *result) {
  int buffer = 0, bitsLeft = 0, count = 0;
  const char *ptr = encoded.c_str();
  for (; *ptr; ++ptr) {
    uint8_t val;
    char c = toupper(*ptr);
    if      (c >= 'A' && c <= 'Z') val = c - 'A';
    else if (c >= '2' && c <= '7') val = c - '2' + 26;
    else continue;
    buffer    = (buffer << 5) | val;
    bitsLeft += 5;
    if (bitsLeft >= 8) {
      result[count++] = (buffer >> (bitsLeft - 8)) & 0xFF;
      bitsLeft -= 8;
    }
  }
  return count;
}

// -------------------------------------------------------
// PARSE ACCOUNTS FROM JSON
// -------------------------------------------------------
void parseAccounts(String jsonPayload) {
  JsonDocument doc;
  if (!deserializeJson(doc, jsonPayload)) {
    accountCount = 0;
    for (JsonObject v : doc.as<JsonArray>()) {
      if (accountCount >= 10) break;
      myAccounts[accountCount].name    = v["name"].as<String>();
      myAccounts[accountCount].issuer  = v["issuer"].as<String>();
      myAccounts[accountCount].secret  = v["secret"].as<String>();
      myAccounts[accountCount].keyLength = base32Decode(
        myAccounts[accountCount].secret,
        myAccounts[accountCount].hmacKey);
      accountCount++;
    }
  }
}

// -------------------------------------------------------
// LOAD CONFIG FROM NVS
// -------------------------------------------------------
bool loadConfig() {
  preferences.begin("device_cfg", true);
  cfg_ssid      = preferences.getString("ssid",      "");
  cfg_password  = preferences.getString("password",  "");
  cfg_userId    = preferences.getString("user_id",   "");
  cfg_deviceKey = preferences.getString("device_key","");
  preferences.end();
  // All four fields must be present
  return (cfg_ssid.length() > 0 &&
          cfg_userId.length() > 0 &&
          cfg_deviceKey.length() > 0);
}

// -------------------------------------------------------
// SAVE CONFIG TO NVS
// -------------------------------------------------------
void saveConfig() {
  preferences.begin("device_cfg", false);
  preferences.putString("ssid",       cfg_ssid);
  preferences.putString("password",   cfg_password);
  preferences.putString("user_id",    cfg_userId);
  preferences.putString("device_key", cfg_deviceKey);
  preferences.end();
  Serial.println("CONFIG_SAVED");
}

// -------------------------------------------------------
// WAIT FOR CONFIG FROM DESKTOP APP VIA USB SERIAL
// Protocol (sent by desktop app):
//   SSID:<wifi name>
//   PASS:<wifi password>
//   UID:<user_id>
//   DKEY:<device_key>
//   CONFIG_DONE
// -------------------------------------------------------
bool waitForSerialConfig(int timeoutMs) {
  display.clearDisplay();
  display.setCursor(0, 0);
  display.println("Not configured.");
  display.println("");
  display.println("Open the desktop");
  display.println("app & click");
  display.println("'Setup Device'.");
  display.display();

  Serial.println("WAITING_FOR_CONFIG");

  String in_ssid   = "";
  String in_pass   = "";
  String in_uid    = "";
  String in_dkey   = "";
  unsigned long start = millis();

  while (millis() - start < timeoutMs) {
    if (Serial.available()) {
      String line = Serial.readStringUntil('\n');
      line.trim();

      if      (line.startsWith("SSID:"))  { in_ssid  = line.substring(5); Serial.println("SSID_OK"); }
      else if (line.startsWith("PASS:"))  { in_pass  = line.substring(5); Serial.println("PASS_OK"); }
      else if (line.startsWith("UID:"))   { in_uid   = line.substring(4); Serial.println("UID_OK");  }
      else if (line.startsWith("DKEY:"))  { in_dkey  = line.substring(5); Serial.println("DKEY_OK"); }
      else if (line == "CONFIG_DONE") {
        if (in_ssid.length() > 0 && in_uid.length() > 0 && in_dkey.length() > 0) {
          cfg_ssid      = in_ssid;
          cfg_password  = in_pass;
          cfg_userId    = in_uid;
          cfg_deviceKey = in_dkey;
          saveConfig();  // Sends "CONFIG_SAVED" over Serial

          display.clearDisplay();
          display.setCursor(0, 0);
          display.println("Configured!");
          display.println("");
          display.print("WiFi: ");
          display.println(cfg_ssid);
          display.display();
          delay(1500);
          return true;
        }
      }
    }
    delay(10);
  }
  return false;  // Timed out
}

// -------------------------------------------------------
// CLOUD SYNC
// -------------------------------------------------------
void performCloudSync() {
  display.clearDisplay();
  display.setCursor(0, 0);
  display.println("Connecting WiFi...");
  display.display();

  WiFi.begin(cfg_ssid.c_str(), cfg_password.c_str());
  int retry = 0;
  while (WiFi.status() != WL_CONNECTED && retry < 20) {
    delay(500);
    digitalWrite(LED_PIN, !digitalRead(LED_PIN));
    retry++;
  }
  digitalWrite(LED_PIN, LOW);

  if (WiFi.status() != WL_CONNECTED) {
    display.clearDisplay();
    display.setCursor(0, 0);
    display.println("WiFi Failed!");
    display.println("Re-run Setup");
    display.println("Device from app.");
    display.display();
    delay(2000);
    return;
  }

  display.println("WiFi OK!");
  display.println("Syncing time...");
  display.display();

  // NTP time sync + update RTC
  configTime(0, 0, "pool.ntp.org", "time.google.com");
  struct tm timeinfo;
  if (getLocalTime(&timeinfo)) {
    time_t now; time(&now);
    struct tm *t = localtime(&now);
    RtcDateTime accurate(t->tm_year + 1900, t->tm_mon + 1, t->tm_mday,
                         t->tm_hour, t->tm_min, t->tm_sec);
    Rtc.SetDateTime(accurate);
  }

  display.println("Fetching keys...");
  display.display();

  WiFiClientSecure client;
  client.setInsecure();
  HTTPClient http;

  preferences.begin("2fa_storage", false);
  String cachedJson = preferences.getString("json", "");

  // Build URL with user_id
  String url = String(serverBaseUrl) +
               "/api/device/fetch?user_id=" + cfg_userId;

  if (http.begin(client, url)) {
    http.addHeader("X-API-Key", cfg_deviceKey);
    int code = http.GET();

    if (code > 0) {
      String payload = http.getString();
      if (payload.length() > 10) {
        preferences.putString("json", payload);
        parseAccounts(payload);
        display.println("Synced!");
      } else {
        if (cachedJson.length() > 0) parseAccounts(cachedJson);
        display.println("Using cache.");
      }
    } else {
      if (cachedJson.length() > 0) parseAccounts(cachedJson);
      display.println("Server error.");
    }
    http.end();
  }

  preferences.end();
  display.display();
  delay(1000);
  WiFi.disconnect(true);
}

// -------------------------------------------------------
// RTC HELPERS
// -------------------------------------------------------
void setInternalTimeFromRTC() {
  RtcDateTime now = Rtc.GetDateTime();
  struct timeval tv;
  tv.tv_sec  = now.Epoch32Time();
  tv.tv_usec = 0;
  settimeofday(&tv, NULL);
}

// -------------------------------------------------------
// SETUP
// -------------------------------------------------------
void setup() {
  Serial.begin(115200);
  pinMode(TOUCH_NEXT_PIN, INPUT);
  pinMode(TOUCH_PREV_PIN, INPUT);
  pinMode(TOUCH_SYNC_PIN, INPUT);
  pinMode(LED_PIN, OUTPUT);

  Wire.begin(I2C_SDA, I2C_SCL);
  delay(100);
  display.begin(i2c_Address, true);
  display.clearDisplay();
  display.setTextColor(SH110X_WHITE);
  display.setTextSize(1);
  display.setCursor(0, 0);
  display.println("Booting...");
  display.display();

  Rtc.Begin();
  if (!Rtc.GetIsRunning()) Rtc.SetIsRunning(true);
  RtcDateTime rtcNow = Rtc.GetDateTime();
  if (rtcNow.Year() > 2024) setInternalTimeFromRTC();

  // Load cached accounts
  preferences.begin("2fa_storage", false);
  String cachedJson = preferences.getString("json", "");
  if (cachedJson.length() > 0) parseAccounts(cachedJson);
  preferences.end();

  // Load config — if missing, wait for desktop app
  if (!loadConfig()) {
    bool got = waitForSerialConfig(60000);  // Wait 60s for setup
    if (!got) {
      display.clearDisplay();
      display.setCursor(0, 0);
      display.println("Setup timeout.");
      display.println("Restart & open");
      display.println("desktop app.");
      display.display();
      delay(5000);
      return;
    }
  }

  performCloudSync();
}

// -------------------------------------------------------
// LOOP
// -------------------------------------------------------
void loop() {
  // Always listen for re-configuration via Serial
  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();

    // Accept individual field updates or a full reconfigure
    if      (line.startsWith("SSID:"))  cfg_ssid      = line.substring(5);
    else if (line.startsWith("PASS:"))  cfg_password  = line.substring(5);
    else if (line.startsWith("UID:"))   cfg_userId    = line.substring(4);
    else if (line.startsWith("DKEY:"))  cfg_deviceKey = line.substring(5);
    else if (line == "CONFIG_DONE") {
      saveConfig();
      performCloudSync();
    }
  }

  if (accountCount == 0) {
    display.clearDisplay();
    display.setCursor(0, 0);
    display.println("No Accounts!");
    display.println("Press Sync btn");
    display.println("or run Setup");
    display.println("Device from app.");
    display.display();
    if (digitalRead(TOUCH_SYNC_PIN) == HIGH) performCloudSync();
    delay(200);
    return;
  }

  // Navigation
  if (digitalRead(TOUCH_NEXT_PIN) == HIGH) {
    currentAccountIndex = (currentAccountIndex + 1) % accountCount;
    delay(250);
  }
  if (digitalRead(TOUCH_PREV_PIN) == HIGH) {
    currentAccountIndex = (currentAccountIndex - 1 + accountCount) % accountCount;
    delay(250);
  }
  if (digitalRead(TOUCH_SYNC_PIN) == HIGH) {
    delay(100);
    if (digitalRead(TOUCH_SYNC_PIN) == HIGH) {
      performCloudSync();
      setInternalTimeFromRTC();
    }
  }

  // Generate TOTP
  time_t now; time(&now);
  TOTP totp(myAccounts[currentAccountIndex].hmacKey,
            myAccounts[currentAccountIndex].keyLength);
  char* newCode        = totp.getCode(now);
  int secondsRemaining = 30 - (now % 30);

  if (secondsRemaining <= 10) {
    digitalWrite(LED_PIN, (millis() / 100) % 2 == 0 ? HIGH : LOW);
  } else {
    digitalWrite(LED_PIN, LOW);
  }

  // Draw display
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SH110X_WHITE);

  display.setCursor(0, 0);
  display.printf("%s (%d/%d)",
    myAccounts[currentAccountIndex].issuer.c_str(),
    currentAccountIndex + 1, accountCount);

  display.setCursor(0, 12);
  display.println(myAccounts[currentAccountIndex].name.substring(0, 20));

  display.setTextSize(2);
  display.setCursor(15, 35);
  String c = String(newCode);
  display.print(c.substring(0, 3) + " " + c.substring(3));

  display.fillRect(0, 60,
    map(secondsRemaining, 0, 30, 0, 128), 4, SH110X_WHITE);

  if (digitalRead(TOUCH_NEXT_PIN) == HIGH)
    display.fillCircle(124, 30, 3, SH110X_WHITE);
  if (digitalRead(TOUCH_PREV_PIN) == HIGH)
    display.fillCircle(4, 30, 3, SH110X_WHITE);

  display.display();
}
