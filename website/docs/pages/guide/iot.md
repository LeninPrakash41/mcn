# IoT and hardware

`device()` reads sensors and drives outputs. The same code runs three ways:

- **In Studio**, every device is simulated. The **IoT Simulator** panel shows each one live: drag a sensor's slider to test your code, trigger a motion sensor, or flip a relay.
- **On a Raspberry Pi**, `driver: "gpio"` uses the Pi's own pins.
- **With a microcontroller**, `driver: "serial"` talks to an Arduino, ESP32 or Pico over USB, and `driver: "mqtt"` or `driver: "http"` reaches boards and smart-home gear over the network.

```mcn
device("register", "greenhouse_temp", {type: "temperature_sensor", driver: "gpio", pin: 4, sensor: "dht22"})
device("register", "vent_fan", {type: "fan", driver: "gpio", pin: 17})

function on_temperature(value)
    if value > 28
        device("on", "vent_fan")
    if value < 25
        device("off", "vent_fan")

device("watch", "greenhouse_temp", on_temperature, 2)
log("Greenhouse at " + str(device("read", "greenhouse_temp").value) + "°C")
```

## Operations

| Call | What it does |
|---|---|
| `device("register", id, {type, driver, ...})` | Add a device. Registering the same id again replaces it |
| `device("read", id)` | `{value, unit, at}` |
| `device("on", id)` / `device("off", id)` / `device("toggle", id)` | Switch an output |
| `device("write", id, value)` | Set an output: `1`/`0` for switches, a percentage for dimmers and motors, an angle for servos, text for displays |
| `device("command", id, {command, value})` | The same as a map: `{command: "on"}`, `{command: "set", value: 40}` |
| `device("watch", id, fn, seconds)` | Call `fn(value, previous, id)` whenever the reading changes, checking every `seconds` (default 0.5). `fn` may take just `value` |
| `device("list")` | Every device with its type, value, unit, driver and pin |
| `device("remove", id)` | Forget a device and release its pin |

A problem with the hardware, such as a missing board, a wrong pin or an unreachable broker, stops the program with a `Device error` that says what to check. Catch it with `try` if your program should keep going.

## Device types

| Type | Kind | Value |
|---|---|---|
| `temperature_sensor`, `humidity_sensor`, `light_sensor`, `distance_sensor`, `soil_moisture`, `gas_sensor`, `pressure_sensor`, `power_meter`, `analog_sensor` | sensor | A number in °C, %, lux, cm, %, ppm, hPa, W, or raw |
| `motion_sensor`, `button`, `door_sensor`, `digital_input` | on/off input | `1` or `0` |
| `led`, `light`, `relay`, `fan`, `pump`, `lock`, `buzzer`, `switch`, `digital_output` | on/off output | `1` or `0` |
| `dimmer`, `pwm`, `motor` | level output | 0–100 % |
| `servo` | level output | 0–180° |
| `hvac_controller`, `display` | text | Any text, such as a mode |

Any device also takes `location`, plus `min`, `max` and `unit` to override the defaults.

## Raspberry Pi

Install MCN on the Pi (64-bit Raspberry Pi OS) with the [one-line installer](#/getting-started/installation), then add hardware support:

```bash
mcn add iot
```

Pins use BCM numbering: `pin: 17` is GPIO17, physical pin 11.

| Part | Register it as |
|---|---|
| LED, relay, buzzer | `{type: "relay", driver: "gpio", pin: 17}`. Add `active_high: false` for relay boards that switch on when the pin is low |
| PWM dimmer or motor | `{type: "dimmer", driver: "gpio", pin: 18}` |
| Servo | `{type: "servo", driver: "gpio", pin: 18}` |
| Button | `{type: "button", driver: "gpio", pin: 27}`, wired to ground (uses the internal pull-up) |
| PIR motion sensor | `{type: "motion_sensor", driver: "gpio", pin: 4}` |
| DHT22 / DHT11 | `{type: "temperature_sensor", driver: "gpio", pin: 4, sensor: "dht22"}`, and the same with `humidity_sensor` |
| Analog sensor through an MCP3008 | `{type: "soil_moisture", driver: "gpio", adc: "mcp3008", channel: 0}` |

The Pi has no analog inputs, so analog sensors need an MCP3008 or an Arduino. To start an app when the Pi boots:

```bash
mcn iot service backend/main.mcn       # writes mcn-main.service
sudo cp mcn-main.service /etc/systemd/system/
sudo systemctl enable --now mcn-main.service
```

The service sets `MCN_IOT_SIMULATE=0`, so a wiring problem stops the app with a clear error instead of quietly simulating.

## Arduino, ESP32 and Pico over USB

Upload the MCN firmware once, plug the board into the computer or Pi running MCN, and use `driver: "serial"`:

```bash
mcn iot firmware arduino     # writes mcn_firmware/mcn_firmware.ino; open it in the Arduino IDE and upload
mcn iot ports                # shows which port the board is on
```

```mcn
device("register", "soil", {type: "soil_moisture", driver: "serial", pin: "A0", scale: [0, 100]})
device("register", "pump", {type: "pump", driver: "serial", pin: 7})

if device("read", "soil").value < 30
    device("on", "pump")
```

- `pin` is `"A0"`–`"A7"` for analog inputs, or a number for digital pins.
- `scale: [0, 100]` maps the board's 0–1023 reading onto a range.
- `port` defaults to the first board found; set `port: "/dev/ttyACM0"` (or `"COM3"`) when several are plugged in. `baud` defaults to 115200.
- For DHT sensors, uncomment `#define MCN_USE_DHT` in the sketch and use `sensor: "dht22"`.

The firmware is tested on the Uno, Nano, Mega, Leonardo and ESP32. It speaks a one-line text protocol (`R A0` → `OK 512`), described at the top of the sketch, so you can add your own commands.

## ESP32 and smart-home devices over MQTT

`driver: "mqtt"` works with any MQTT device: the MCN ESP32 firmware, Tasmota, ESPHome, Zigbee2MQTT or Home Assistant.

```bash
mcn iot firmware esp32       # writes mcn_esp32/mcn_esp32.ino: fill in WiFi, the broker and your devices
```

```mcn
device("register", "porch_light", {type: "light", driver: "mqtt", topic: "mcn/porch_light"})
device("register", "bedroom", {type: "temperature_sensor", driver: "mqtt", topic: "zigbee2mqtt/bedroom", field: "temperature"})
device("on", "porch_light")
```

| Option | Default | Meaning |
|---|---|---|
| `broker` | `MCN_MQTT_URL`, else `mqtt://localhost:1883` | `mqtt://user:pass@host:1883`; `mqtts://` for TLS |
| `topic` | `mcn/<id>` | Where inputs publish readings |
| `state_topic` | `<topic>/state` for outputs | Where outputs report their state |
| `command_topic` | `<topic>/set` | Where MCN publishes commands |
| `payload_on` / `payload_off` | `ON` / `OFF` | Switch payloads |
| `field` | `value` | Key to read when a message is JSON |
| `scale` / `raw_max` | — / 4095 | Map raw readings onto a range |

## HTTP devices

`driver: "http"` reads a URL that returns a number or JSON (`field` picks the key), and sets outputs by POSTing `{"value": ...}` to `write_url` (or the same URL).

```mcn
device("register", "tank_level", {type: "distance_sensor", driver: "http", url: "http://10.0.0.7/level"})
log(device("read", "tank_level").value)
```

## Simulation

`MCN_IOT_SIMULATE` decides what happens when the hardware isn't there:

| Value | Behavior |
|---|---|
| `1` | Always simulate. Studio sets this |
| `0` | Always use hardware; a missing board or library is an error. Use this in production |
| not set | Use hardware when it's there. Otherwise simulate, and print one line saying why |

So code written for a Pi runs on your laptop, in Studio and in `mcn test` without changes. Simulated sensors drift around a believable value; outputs remember what they were set to.

In Studio, the IoT Simulator shows the devices of scripts you **Run** and, while **Preview** is running, your backend's devices too. Changing a value there reaches the running app, so you can watch automations react. The **Smart Home** and **IoT Telemetry Hub** templates are complete examples.

## Virtual lab

`lab()` starts a simulated world whose devices behave like the real thing, so you can build and test Physical AI without any hardware. The world runs on its own, your program reads and drives its devices with the usual `device()` calls, and Studio's **IoT** panel draws it live, with **Reset** and speed controls.

```mcn
lab("greenhouse", {speed: 600})       // ten simulated minutes per second

function check_soil(value)
    if value < 35
        device("on", "pump")
    if value > 60
        device("off", "pump")

device("watch", "soil_moisture", check_soil, 1)
```

| World | Devices | What happens |
|---|---|---|
| `lab("greenhouse")` | sensors `soil_moisture`, `temperature`, `humidity`, `light`; outputs `pump`, `fan`, `grow_light`, `vent` (servo, 0–180°) | A day passes (sunrise to night, starting at 08:00). Soil dries in the sun and heat and gets wetter while the pump runs; the sun warms the air, the fan and vent cool it; the grow light adds light. Plant health rises when soil, temperature and light are right, and the water used is counted. Default speed 60: one simulated minute per second |
| `lab("rover")` | outputs `drive` (-100 to 100 %, negative backs up), `steering` (0–180°, 90 straight, above 90 turns left), `headlight`; sensors `front_distance`, `left_distance`, `right_distance` (cm, up to 400) and `bumper` | A small robot in a 6 m × 4 m room with three obstacles and a charging pad. It drives like a car (it can't turn on the spot), slides along walls it scrapes, and the bumper reads 1 while it touches something. Default speed 1 (real time) |

| Call | What it does |
|---|---|
| `lab("greenhouse")` / `lab("rover")` | Start the world and add its devices. Options: `speed` (simulated seconds per real second), `prefix` (put a prefix on the device ids) |
| `lab("state")` / `lab("state", "rover")` | Every running world, or one: its readings, outputs, events and position, as the IoT panel draws it |
| `lab("reset", "rover")` | Put a world back to its start |
| `lab("speed", {world: "greenhouse", speed: 3600})` | Run it faster or slower |
| `lab("remove", "rover")` | Stop the world and remove its devices |

To move to real hardware, replace `lab(...)` with `device("register", ...)` lines for your sensors and outputs; the rest of the program stays the same. The **Greenhouse Lab** and **Rover Lab** templates (Templates → Physical AI lab) are complete programs to start from.

## Control policies

`policy()` declares what a device may do. MCN enforces it on every change, whoever asks: your program, an AI agent calling one of your functions, or someone in Studio's IoT panel. A refused change raises an error that says why, so an agent gets the reason back and can try something else, and every refusal is in the device log.

```mcn
device("register", "pump", {type: "pump", driver: "gpio", pin: 17})
device("register", "door_lock", {type: "lock", driver: "gpio", pin: 22})
device("register", "drive", {type: "motor", driver: "gpio", pin: 18})

policy("pump", {max_on: 600, cooldown: 300, hours: [6, 20]})   // 10 minutes at most, 5 minutes' rest, daytime only
policy("drive", {max: 70, rate: 30})                            // never above 70 %, 30 changes a minute at most
policy("door_lock", {approve: true, audit: true})               // a person approves each change; recorded in the audit log

try
    device("write", "drive", 90)
catch e
    log(e.message)              // Refused: 'drive' can't go above 70 (asked for 90)
```

| Rule | Meaning |
|---|---|
| `min`, `max` | Allowed values. Anything outside is refused, not quietly limited |
| `max_on` | Seconds a switch may stay on; MCN switches it off after that |
| `cooldown` | Seconds it must stay off before it may be switched on again |
| `rate` | Changes allowed per minute |
| `hours` | `[start, end]` in 24-hour time when it may be switched on or changed (turning off is always allowed). `[22, 6]` spans midnight |
| `check` | Your own function, called with the value (and the device id): return `true` to allow, or a reason to refuse. Use it for zones and conditions, such as "not while it's raining" |
| `approve` | `true`: each change waits for a person. It appears under **Waiting for approval** in Studio's IoT panel with **Approve** and **Reject**; your app can use `policy("approvals")`, `policy("approve", id)` and `policy("reject", id)` |
| `safe` | The value an emergency stop sets (default: off, 0, or a servo's starting angle) |
| `audit` | `true`: also record every change and refusal with `audit_log` (tamper-evident) |

`policy("pump")` shows a device's policy, `policy("list")` every policy, the pending approvals and the emergency stop, and `policy("remove", "pump")` removes one. Studio shows each device's policy under it.

### Emergency stop

`emergency_stop()` puts every output in its safe state and refuses all changes (except to the safe state) until `emergency_stop(false)` releases it. The red **STOP** button in Studio's IoT panel does the same, for your scripts and the running backend at once.

In the [virtual lab](#/guide/iot), `max_on`, `cooldown` and `hours` follow the world's simulated clock, so a greenhouse policy behaves the same at any speed.

## Testing

Simulated devices make automations easy to test. Call the handler directly, or hold a reading:

```mcn fragment
test "the vent opens when it's hot"
    device("off", "vent_fan")
    on_temperature(30)
    assert device("read", "vent_fan").value == 1
```
