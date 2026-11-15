# Physical AI

Physical AI connects AI with physical devices that **sense, reason, decide and act** in the real world: robots and humanoids, autonomous vehicles and drones, industrial automation and smart manufacturing, IoT devices and sensors, smart agriculture, and edge AI on intelligent machines.

MCN already does much of this: devices, events, agents and workflows are part of the language, and the same code runs simulated in Studio and on real hardware. **MCN Physical Intelligence (MCN PI)** is the plan to take it the rest of the way, to robotics, vision and industrial systems. This page shows what works today, and what's planned.

> **Note** Sections marked *Planned* describe the roadmap, not features you can use yet.

## The building blocks

| Capability | In Physical AI | Status in MCN |
|---|---|---|
| **SENSOR** | Read temperature, distance, motion and camera data | **Available**: `device("read", ...)` for temperature, humidity, light, distance, soil, gas, pressure, power, motion, doors and buttons. *Planned*: cameras |
| **DEVICE** | Manage robots, motors and IoT hardware | **Available**: relays, pumps, fans, locks, dimmers, motors (0–100 %) and servos (0–180°) over Raspberry Pi pins, USB boards (Arduino, ESP32, Pico), MQTT and HTTP; `mcn iot firmware` writes the board code. *Planned*: robot arms and mobile robots |
| **EVENT** | React to physical-world events | **Available**: `device("watch", id, handler)` runs code whenever a reading changes; `schedule` runs it on a timetable |
| **AGENT** | Make intelligent decisions | **Available**: `agent_run` lets Claude call your functions, such as reading sensors and switching devices |
| **WORKFLOW** | Coordinate multiple devices and actions | **Available**: `workflow` steps, `checkpoint` for a person's approval in a terminal session, and the visual workflow builder |
| **VISION** | Interpret camera and visual inputs | *Planned*: camera devices and a `vision()` function to describe, detect and count objects in an image |
| **CONTROL** | Execute approved physical actions | **Available**: [control policies](#/guide/iot) declare what each device may do (allowed values, how long it may run, rest time, changes per minute, hours, your own checks, a person's approval) and every action must pass them, an agent's included; `emergency_stop()` and Studio's STOP button make everything safe |
| **TELEMETRY** | Monitor device health and performance | **Available**: the IoT Simulator panel and the [virtual lab](#/guide/iot) (`lab("greenhouse")`, `lab("rover")`), drawn live, `device("list")`, and the **IoT Telemetry Hub** template (MQTT readings, alerts, charts). *Planned*: device health, uptime and fleet dashboards |

## Today: sense, reason, decide, act

Everything below runs now: simulated in Studio and in `mcn test`, and on real hardware when the ESP32 is there. An agent reads the field and decides whether to water; a control policy decides what the pump may do, whoever asks, and every use is recorded.

```mcn
// Smart irrigation: sense, reason, decide and act, with MCN as it is today

// SENSOR and DEVICE: an ESP32 in the field publishes readings over MQTT
device("register", "soil", {type: "soil_moisture", driver: "mqtt", topic: "farm/bed1/soil"})
device("register", "air_temp", {type: "temperature_sensor", driver: "mqtt", topic: "farm/bed1/temp"})
device("register", "pump", {type: "pump", driver: "mqtt", topic: "farm/bed1/pump"})

// The agent's eyes: what it may read
function read_field()
    return {soil_moisture: device("read", "soil").value, temperature: device("read", "air_temp").value,
            pump_on: device("read", "pump").value == 1}

// CONTROL: what the pump may do, enforced on every action, the agent's included
policy("pump", {max_on: 600, cooldown: 900, hours: [5, 21], audit: true})   // 10 minutes at most, 15 minutes' rest, never at night

function run_pump()
    device("on", "pump")         // refused with a reason if the policy says no; the agent sees it
    return {started: true, stops_after_minutes: 10}

// AGENT: decides what to do from the readings
function decide(value)
    var result = agent_run("Soil moisture is now " + str(value) + "%. Decide whether to water bed 1, and for how long.", {
        system: "You run a greenhouse. Water when soil moisture is below 30%, for less time when it's cool. Use read_field; never guess readings.",
        tools: ["read_field", {name: "run_pump", description: "Start the pump; it stops by itself after 10 minutes"}],
        max_steps: 4
    })
    log(result.reply)
    return result

// EVENT: decide again whenever the soil reading changes (checked every minute)
device("watch", "soil", decide, 60)

test "the pump can't run again before it has rested"
    run_pump()
    device("off", "pump")
    var refused = false
    try
        run_pump()
    catch e
        refused = true
    assert refused
```

Run it in Studio to see the devices in the **IoT** panel: drag the soil reading down and the agent decides. Without `ANTHROPIC_API_KEY` the agent runs in mock mode (it replies, but doesn't call tools); set the key for real decisions. See [IoT and hardware](#/guide/iot) and [agents with tools](#/guide/ai).

> **Warning** An agent can do whatever its tools do. For anything that moves, heats, cuts or locks, give the device a control policy, check every input, and record each action. Test with simulated devices, or in the virtual lab, before connecting real ones.

## Try it without hardware

The [virtual lab](#/guide/iot) gives you a simulated world to practise on: `lab("greenhouse")` (soil, temperature, light, a pump, fan, grow light and vent, through a whole day) or `lab("rover")` (a robot with distance sensors in a room with obstacles). Studio's IoT panel draws it as your program runs. Start from the **Greenhouse Lab** or **Rover Lab** template.

## The architecture

MCN PI has three layers:

| Layer | What it holds | Status |
|---|---|---|
| **MCN AI Intelligence Layer** | LLMs · Vision · Decision agents · Planning | LLMs and decision agents (Claude) available; vision and multi-step planning *planned* |
| **MCN Physical Runtime** | Sensors · Events · Device state · Workflows · Control policies | Available |
| **Hardware Integration Layer** | ROS 2 · MQTT · OPC UA · Modbus · GPIO · APIs | MQTT, GPIO, USB serial and HTTP APIs available; ROS 2, OPC UA and Modbus *planned* |

The idea is that an app describes **what** should happen (read this, decide that, never exceed this), and the runtime and drivers handle **how**, so the same program can move from the simulator to a Raspberry Pi to an industrial line.

## Three studios

| Environment | Focus | Status |
|---|---|---|
| **MCN Application Studio** | Web, mobile and backend | Available today as MCN Studio |
| **MCN Agent Studio** | AI agents, workflows and automation | Available today inside Studio: the Agent panel, the AI Agent Builder and Workflow Automation templates, and the visual workflow builder |
| **MCN Physical Studio** | Robotics, IoT and Physical AI | Started: the IoT panel simulates every device and runs the **virtual lab**, a greenhouse and a rover drawn live, so anyone can build Physical AI on a laptop. It also shows each device's control policy, approvals and a STOP button. *Planned*: device fleets, live telemetry and camera feeds |

## Roadmap *(planned)*

1. **Vision**: camera devices (USB, Raspberry Pi camera, IP cameras), and `vision(image, question)` with any model that reads images: describe a scene, detect and count objects, read gauges and labels.
2. **Industrial protocols**: `driver: "modbus"` and `driver: "opcua"` for PLCs and factory equipment.
3. **Robotics**: `driver: "ros2"` to read ROS 2 topics and send commands and goals, so an MCN agent can drive a robot or a drone through ROS.
4. **Telemetry**: device health, uptime, alerts and fleet views, with readings stored for charts.
5. **MCN Physical Studio**: one place to build, simulate, monitor and safely operate physical AI systems.

Each step will keep MCN's rule: the same code runs simulated first, then on hardware.
