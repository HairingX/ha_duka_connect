# Duka Connect

A Home Assistant integration for **Duka One** ventilation units, over the unit's own UDP protocol
on your local network. No cloud.

Built on [duka_connect](https://github.com/HairingX/duka_connect).

> **Not yet tested on a unit.** Every value is taken from the manufacturer's connection guide for
> the protocol; none has been read on a Duka One by this integration yet. Reports of what your
> unit shows are welcome - the diagnostics download has what is needed.

## Supported devices

Duka One units with Wi-Fi, such as the Duka One Pro 50 S Wi-Fi and the Duka One 50+ Wi-Fi.

## What you get

| Entity | What it is |
|---|---|
| Fan | On and off, the three preset speeds, and any speed as a percentage (the manual speed) |
| Speed, manual speed | The fan's speed and manual speed as entities of their own, with their history |
| Ventilation mode | Extract, heat recovery or supply |
| Timer mode | Off, night or party; with the night and party durations as settings |
| Humidity, fan speeds | Measurements; humidity over its threshold as a flag |
| Alarm | None, alarm or warning, as the unit reports it |
| Filter replacement | On when the filter needs replacing, with the time left until it does |
| Clock battery | The voltage of the CR1220 cell that keeps the unit's clock |
| Clock battery low | On while that voltage is under the limit set in the options |
| Weekly schedule, cloud access | Switches |
| Humidity boost, humidity threshold, boost off delay | Settings |
| Set clock | Sets the unit's clock to Home Assistant's local time; its weekly schedule runs by it |
| Reset filter timer, reset alarms | Buttons |
| Relay and 0-10 V sensors | Their switches, states and threshold; disabled until enabled |
| Supply and exhaust speed per preset, restore fan speeds | Only on units that have them; disabled until enabled |
| Filter change interval | Only on units that have it |
| Operating time, firmware, unit type, IP address | Diagnostics |

A value the unit says it does not have gets no entity.

## Installation

1. In HACS, add `https://github.com/HairingX/ha_duka_connect` as a custom repository of the
   type *Integration*, and install **Duka Connect**.
2. Restart Home Assistant.
3. Settings > Devices & services > Add integration > **Duka Connect**.

Choose how to find the unit:

- **Search the network**: the integration asks every unit on the network, by broadcast. Pick the
  unit from those found, name it, and give its password. When none is found, search again or
  enter the unit by hand.
- **Enter the unit by hand**: its IP address, best a fixed one set in your router, and its
  password. The device id is in Duka's app; leave it empty, and the integration asks the unit
  for it.

| Setting | What it is |
|---|---|
| Name | What the unit and its entities are called. It cannot be changed later: every entity's unique id starts with it. |
| Host | The unit's IP address. |
| Device id | The 16 characters in Duka's app, or on the board under the front cover. |
| Password | `1111` unless it was changed in Duka's app. |

The address and password can be changed later: the integration's three dots > Reconfigure.

## Options

The integration's three dots > Configure:

| Option | What it is |
|---|---|
| Clock battery low under (mV) | The voltage under which *Clock battery low* is on; 2500 mV unless changed. A new CR1220 gives about 3000 mV, and no document says when Duka's app calls it flat: set it just over what *Clock battery* shows when the app asks for a new cell. |

## How the data is updated

The integration polls the unit locally. Each value is read at its own rate, and only values an
entity follows: the fan, its speed and the mode every 10 seconds, most values every 30 or 60
seconds, the filter timer, clock battery and operating time every 15 minutes, the firmware once.
A change made from Home Assistant is read back at once.

## Known limitations

- **Untested on a unit**, as said above.
- **The search reaches only the network Home Assistant is on.** A router does not forward a
  broadcast between subnets or VLANs, whatever its firewall allows. Across them, enter the unit
  by hand, and allow UDP port 4000 from Home Assistant to the unit. In Docker, Home Assistant
  needs host networking.
- **No discovery by Home Assistant itself.** The unit announces nothing of its own: no mDNS, and
  its DHCP host name (`esp-…`) and MAC prefix are its Wi-Fi module's.
- **A wrong password looks like a unit that is away**: the unit does not answer it.
- **The weekly schedule's periods** cannot be set from Home Assistant; switch the schedule on
  and off, and set its periods in Duka's app.
- The unit's clock has no time zone; *Set clock* writes Home Assistant's local time.

## Troubleshooting

| What you see | What to do |
|---|---|
| "The unit did not answer" | Check the address and password. Across subnets, allow UDP port 4000 from Home Assistant to the unit. |
| The search finds nothing | Home Assistant and the unit are on different networks; enter the unit by hand. |
| Entities unavailable | The unit stopped answering; the log says when it stopped and when it answers again. Give the unit a fixed IP address. |
| A value looks wrong | Download the diagnostics (the integration's three dots > Download diagnostics) and open an issue with it. It holds every value with its raw bytes, and no password, address or device id. |

For more detail, enable debug logging: the integration's three dots > Enable debug logging.

## Removing the integration

1. Settings > Devices & services > Duka Connect > three dots > **Delete**.
2. In HACS, remove **Duka Connect**, and restart Home Assistant.

The unit is left as it is.

## License

MIT
