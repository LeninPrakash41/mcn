// MCN firmware for ESP32 and ESP8266 over WiFi (MQTT).
//
// 1. Install the "PubSubClient" library (and "ESP32Servo" on ESP32 if you use servos).
// 2. Fill in WiFi, the MQTT broker and the DEVICES table below, then upload.
// 3. In MCN, register each device with driver: "mqtt" and the same id:
//
//      device("register", "soil", {type: "soil_moisture", driver: "mqtt", scale: [0, 100], raw_max: 4095})
//      device("register", "pump", {type: "relay", driver: "mqtt"})
//
// Topics (the MCN mqtt driver's defaults):
//   inputs  publish their reading to  mcn/<id>
//   outputs listen on                 mcn/<id>/set     (ON / OFF, or a number for pwm and servo)
//   outputs report their state to     mcn/<id>/state

#if defined(ESP32)
  #include <WiFi.h>
#else
  #include <ESP8266WiFi.h>
#endif
#include <PubSubClient.h>

const char* WIFI_SSID     = "your-wifi";
const char* WIFI_PASSWORD = "your-password";
const char* MQTT_HOST     = "192.168.1.10";   // the computer or Pi running your broker (e.g. mosquitto)
const int   MQTT_PORT     = 1883;
const char* MQTT_USER     = "";               // leave empty if the broker has no login
const char* MQTT_PASSWORD = "";
const char* TOPIC_PREFIX  = "mcn/";
const unsigned long PUBLISH_EVERY_MS = 2000;

enum Kind { ANALOG_IN, DIGITAL_IN, DIGITAL_OUT, PWM_OUT };

struct Item {
  const char* id;
  Kind kind;
  int pin;
  int value;      // last value sent or set
};

// One line per device: its MCN id, what it is, and its pin
Item DEVICES[] = {
  {"soil", ANALOG_IN,   34, -1},
  {"door", DIGITAL_IN,  27, -1},
  {"pump", DIGITAL_OUT, 26,  0},
  {"lamp", PWM_OUT,     25,  0},
};
const int COUNT = sizeof(DEVICES) / sizeof(DEVICES[0]);

WiFiClient wifi;
PubSubClient mqtt(wifi);
unsigned long lastPublish = 0;

String topicFor(const Item& d, const char* suffix) {
  return String(TOPIC_PREFIX) + d.id + suffix;
}

void publishState(Item& d) {
  String payload;
  if (d.kind == DIGITAL_OUT) payload = d.value ? "ON" : "OFF";
  else payload = String(d.value);
  const char* suffix = (d.kind == DIGITAL_OUT || d.kind == PWM_OUT) ? "/state" : "";
  mqtt.publish(topicFor(d, suffix).c_str(), payload.c_str(), true);
}

void onMessage(char* topic, byte* body, unsigned int length) {
  String text;
  for (unsigned int i = 0; i < length; i++) text += (char)body[i];
  text.trim();
  for (int i = 0; i < COUNT; i++) {
    Item& d = DEVICES[i];
    if (topicFor(d, "/set") != topic) continue;
    if (d.kind == DIGITAL_OUT) {
      text.toUpperCase();
      d.value = (text == "ON" || text == "1" || text == "TRUE") ? 1 : 0;
      digitalWrite(d.pin, d.value ? HIGH : LOW);
    } else if (d.kind == PWM_OUT) {
      d.value = constrain(text.toInt(), 0, 100);           // percent, like MCN's pwm devices
      analogWrite(d.pin, map(d.value, 0, 100, 0, 255));
    }
    publishState(d);
  }
}

void connectWifi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) delay(250);
}

void connectMqtt() {
  while (!mqtt.connected()) {
    String clientId = String("mcn-") + String((uint32_t)random(0xffffff), HEX);
    bool ok = strlen(MQTT_USER) ? mqtt.connect(clientId.c_str(), MQTT_USER, MQTT_PASSWORD)
                                : mqtt.connect(clientId.c_str());
    if (!ok) { delay(2000); continue; }
    for (int i = 0; i < COUNT; i++) {
      Item& d = DEVICES[i];
      if (d.kind == DIGITAL_OUT || d.kind == PWM_OUT) {
        mqtt.subscribe(topicFor(d, "/set").c_str());
        publishState(d);
      }
    }
  }
}

void setup() {
  for (int i = 0; i < COUNT; i++) {
    Item& d = DEVICES[i];
    if (d.kind == DIGITAL_OUT || d.kind == PWM_OUT) pinMode(d.pin, OUTPUT);
    else if (d.kind == DIGITAL_IN) pinMode(d.pin, INPUT_PULLUP);
  }
  connectWifi();
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(onMessage);
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) connectWifi();
  if (!mqtt.connected()) connectMqtt();
  mqtt.loop();

  if (millis() - lastPublish >= PUBLISH_EVERY_MS) {
    lastPublish = millis();
    for (int i = 0; i < COUNT; i++) {
      Item& d = DEVICES[i];
      int reading;
      if (d.kind == ANALOG_IN) reading = analogRead(d.pin);
      else if (d.kind == DIGITAL_IN) reading = digitalRead(d.pin) == LOW ? 1 : 0;   // pulled up: pressed/closed = 1
      else continue;
      if (reading != d.value || d.kind == ANALOG_IN) {
        d.value = reading;
        publishState(d);
      }
    }
  }
}
