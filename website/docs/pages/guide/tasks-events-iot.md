# Tasks, events and IoT

## Background tasks

`task` starts a function in the background; `await` waits for results. Tasks run in parallel, which helps when each one waits on the network or a slow service.

```mcn
function fetch_report(name)
    sleep(1)                    // stands in for a slow API call
    return {name: name, rows: 120}

task "sales" fetch_report "sales"
task "stock" fetch_report "stock"

var results = await("sales", "stock")     // about 1 second, not 2
log(results.sales.rows)                   // by name
log(results[1].name)                      // or by position
```

- `task "name" function arg1 arg2` — the function and its arguments, separated by spaces.
- `await("a", "b")` returns the results by task name and position. With no names it waits for every task.
- If a task fails, `await` raises an error naming the task.

## Events

Register a handler for a named event, then trigger it:

```mcn
function notify_warehouse(order)
    log("Ship order " + str(order.id))

on event "order_placed" notify_warehouse
trigger("order_placed", {id: 1042})
```

`trigger` with a URL sends an HTTP request instead (see [services](#/guide/services)).

## IoT devices

`device()` registers, reads and controls devices. In Studio, registered devices appear in the **IoT Simulator**, where sliders change their readings and commands show up in a log.

```mcn
device("register", "office_temp", {type: "temperature_sensor", location: "office"})
device("register", "office_fan", {type: "fan"})

var reading = device("read", "office_temp").value
if reading > 25
    device("command", "office_fan", {command: "on", value: "high"})
log("Temperature: " + str(reading))
```

| Operation | Meaning |
|---|---|
| `device("register", id, {type, location})` | Add a device. Sensor types: `temperature_sensor`, `humidity_sensor`, `motion_sensor` |
| `device("read", id)` | Current reading as `{value: ...}` |
| `device("command", id, {command, ...})` | Send a command; actuators remember it as their state |

## Timing

```mcn
var start = now_ms()
sleep(0.2)
log("Took " + str(now_ms() - start) + " ms")
log(now())                          // 2026-11-03T14:05:00.123456
log(format_date(now(), "%d %b %Y"))
```
