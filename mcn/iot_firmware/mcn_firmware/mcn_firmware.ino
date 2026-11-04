// MCN firmware for Arduino (Uno, Nano, Mega, Leonardo), ESP32, ESP8266 and Raspberry Pi Pico.
//
// Upload this sketch, plug the board into the computer running MCN, and use
// driver: "serial" in your MCN code:
//
//   device("register", "soil", {type: "soil_moisture", driver: "serial", pin: "A0", scale: [0, 100]})
//   device("register", "pump", {type: "relay", driver: "serial", pin: 7})
//
// MCN sends one command per line and the board answers "OK <value>" or "ERR <reason>":
//   HELLO            → OK MCN 1
//   R <pin>          → OK <reading>     analogRead for A0..A7, digitalRead otherwise
//   W <pin> <0|1>    → OK 1             digital output (relays, LEDs, buzzers)
//   P <pin> <0-255>  → OK 128           PWM output (dimmers, motors)
//   S <pin> <angle>  → OK 90            servo, 0-180
//   D <pin> <T|H>    → OK 23.5          DHT11/DHT22 temperature or humidity (enable below)

// Uncomment to read DHT sensors (install "DHT sensor library" by Adafruit first)
// #define MCN_USE_DHT
#define MCN_DHT_TYPE DHT22          // or DHT11

#if defined(ESP32)
  #include <ESP32Servo.h>           // install "ESP32Servo"
#else
  #include <Servo.h>
#endif
#ifdef MCN_USE_DHT
  #include <DHT.h>
#endif

const long BAUD = 115200;
const int MCN_PINS = 64;
const int MCN_SERVOS = 8;

bool isOutput[MCN_PINS];
Servo servos[MCN_SERVOS];
int servoPins[MCN_SERVOS];
#ifdef MCN_USE_DHT
DHT* dhts[MCN_PINS];
#endif

String line;

// "A0".."A7" or a pin number. Returns -1 for something else.
int parsePin(String text, bool &analog) {
  text.trim();
  text.toUpperCase();
  analog = false;
  if (text.startsWith("A")) {
    int n = text.substring(1).toInt();
    analog = true;
    switch (n) {
#ifdef A0
      case 0: return A0;
#endif
#ifdef A1
      case 1: return A1;
#endif
#ifdef A2
      case 2: return A2;
#endif
#ifdef A3
      case 3: return A3;
#endif
#ifdef A4
      case 4: return A4;
#endif
#ifdef A5
      case 5: return A5;
#endif
#ifdef A6
      case 6: return A6;
#endif
#ifdef A7
      case 7: return A7;
#endif
      default: return -1;
    }
  }
  if (text.length() == 0 || !isDigit(text.charAt(0))) return -1;
  return text.toInt();
}

Servo* servoFor(int pin) {
  for (int i = 0; i < MCN_SERVOS; i++) {
    if (servoPins[i] == pin) return &servos[i];
  }
  for (int i = 0; i < MCN_SERVOS; i++) {
    if (servoPins[i] < 0) {
      servoPins[i] = pin;
      servos[i].attach(pin);
      return &servos[i];
    }
  }
  return NULL;
}

void reply(String text) {
  Serial.print("OK ");
  Serial.println(text);
}

void fail(String reason) {
  Serial.print("ERR ");
  Serial.println(reason);
}

void handle(String cmd) {
  cmd.trim();
  if (cmd.length() == 0) return;
  int first = cmd.indexOf(' ');
  String op = first < 0 ? cmd : cmd.substring(0, first);
  String rest = first < 0 ? "" : cmd.substring(first + 1);
  int second = rest.indexOf(' ');
  String pinText = second < 0 ? rest : rest.substring(0, second);
  String arg = second < 0 ? "" : rest.substring(second + 1);
  op.toUpperCase();

  if (op == "HELLO") { reply("MCN 1"); return; }

  bool analog;
  int pin = parsePin(pinText, analog);
  if (pin < 0 || pin >= MCN_PINS) { fail("bad pin '" + pinText + "'"); return; }

  if (op == "R") {
    if (analog) { reply(String(analogRead(pin))); return; }
    if (!isOutput[pin]) pinMode(pin, INPUT);
    reply(String(digitalRead(pin)));
  } else if (op == "W") {
    pinMode(pin, OUTPUT);
    isOutput[pin] = true;
    digitalWrite(pin, arg.toInt() ? HIGH : LOW);
    reply(String(arg.toInt() ? 1 : 0));
  } else if (op == "P") {
    pinMode(pin, OUTPUT);
    isOutput[pin] = true;
    int value = constrain(arg.toInt(), 0, 255);
    analogWrite(pin, value);
    reply(String(value));
  } else if (op == "S") {
    Servo* s = servoFor(pin);
    if (s == NULL) { fail("too many servos"); return; }
    int angle = constrain(arg.toInt(), 0, 180);
    s->write(angle);
    reply(String(angle));
  } else if (op == "D") {
#ifdef MCN_USE_DHT
    if (dhts[pin] == NULL) {
      dhts[pin] = new DHT(pin, MCN_DHT_TYPE);
      dhts[pin]->begin();
      delay(2000);
    }
    arg.toUpperCase();
    float value = arg == "H" ? dhts[pin]->readHumidity() : dhts[pin]->readTemperature();
    if (isnan(value)) { fail("no reading from the DHT sensor on pin " + pinText); return; }
    reply(String(value, 1));
#else
    fail("DHT support is off: uncomment #define MCN_USE_DHT in the sketch");
#endif
  } else {
    fail("unknown command '" + op + "'");
  }
}

void setup() {
  Serial.begin(BAUD);
  for (int i = 0; i < MCN_PINS; i++) {
    isOutput[i] = false;
#ifdef MCN_USE_DHT
    dhts[i] = NULL;
#endif
  }
  for (int i = 0; i < MCN_SERVOS; i++) servoPins[i] = -1;
  line.reserve(48);
  Serial.println("MCN READY 1");
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      handle(line);
      line = "";
    } else if (c != '\r' && line.length() < 64) {
      line += c;
    }
  }
}
