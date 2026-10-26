# Duka Connect

Control and follow your **Duka One** ventilation units from Home Assistant. It talks to the units
directly on your home network; no Duka account or cloud is needed.

Built on [duka_connect](https://github.com/HairingX/duka_connect).

> **Early version, not yet tested on a real unit.** Everything is built from the manufacturer's
> documentation. If something looks wrong, please open an issue and attach the diagnostics file
> (see [Troubleshooting](#troubleshooting)).

## Supported devices

Duka One units with Wi-Fi, such as the Duka One Pro 50 S Wi-Fi and the Duka One 50+ Wi-Fi.

## What you get

The unit shows up as one device in Home Assistant. On its page, the entities are grouped the
same way as here. Entities marked *hidden* are turned off at first: turn them on from the device
page if you need them. An entity your unit does not have is not created.

### Controls

| Entity | What it does |
|---|---|
| *(the unit's name)* | Turns the unit on and off, and sets its speed. |
| Speed | Low, medium, high or manual. Its history shows which speed the unit ran at. |
| Manual speed | The speed used when *Speed* is manual, in %. It is the same percentage the fan shows. |
| Ventilation mode | How the air moves: see [Ventilation modes](#ventilation-modes). |
| Timer mode | Off, night (quiet) or party (strong) for a while. |

### Sensors

| Entity | What it shows |
|---|---|
| Humidity | The room's humidity, in %. |
| Alarm | None, warning or alarm, as the unit reports it. |
| Filter | *Problem* when the filter needs changing. |
| Filter time left | How long until the filter should be changed. |
| Boost | *Running* while the unit runs extra strong, for example because of high humidity. |
| High humidity | *Wet* while the humidity is over *Humidity threshold*, *Dry* otherwise. |
| Fan 1 RPM, Fan 2 RPM | How fast each fan turns. |
| Time left on timer | Time left of the night or party mode. *Hidden.* |
| Relay sensor, 0-10 V sensor level, 0-10 V sensor over threshold | An external sensor wired to the unit, if there is one. *Hidden.* |

### Configuration

| Entity | What it does |
|---|---|
| Humidity boost | Lets high humidity make the unit run extra strong. |
| Humidity threshold | The humidity that does so, from 40 to 80 %. |
| Boost off delay | How many minutes it keeps running strong after the humidity has fallen. |
| Night mode duration, Party mode duration | How long each timer mode lasts. |
| Weekly schedule | Lets the unit follow the weekly schedule set in Duka's app. |
| Cloud access | Lets Duka's app reach the unit through Duka's cloud: from away, or from a phone on another network (VLAN). Turn it off to keep the app out; turn it on when you want to use the app. It shows what the unit reports; Home Assistant changes it only when you do. |
| Reset filter timer | Press after changing the filter. |
| Reset alarms | Clears the unit's alarms. |
| Set clock | Sets the unit's clock to Home Assistant's time. The weekly schedule runs by this clock; *Clock* and *Clock offset* show how it stands. |
| Filter change interval | Days between filter changes. Only on units that have it. |
| Relay sensor boost, 0-10 V sensor boost, 0-10 V sensor threshold | Settings for an external sensor wired to the unit. *Hidden.* |
| Supply speed 1-3, Exhaust speed 1-3, Restore fan speeds | Separate speeds in and out for each speed step. Only on units that have them. *Hidden.* |

### Diagnostic

| Entity | What it shows |
|---|---|
| Clock battery | *Low* when the unit's clock battery, a CR1220 coin cell, needs changing. |
| Clock battery voltage | That battery's voltage. |
| Clock | The date and time the unit's clock shows, as of its last reading (every 15 minutes). |
| Clock offset | How many seconds the unit's clock is ahead (+) or behind (−) Home Assistant's. Press *Set clock* to make it 0. |
| Operating time | How long the unit has run in all. |
| Firmware version | The unit's software version, also shown on the device page. |
| Firmware date, Unit type, IP address | Details for troubleshooting. *Hidden.* |

With Home Assistant set to Danish, the names are shown in Danish.

### Ventilation modes

| Mode | What the unit does |
|---|---|
| Ventilation (one-way) | Moves air one way all the time: in or out, as a switch inside the unit (DIP switch) sets it. Duka recommends that half of a home's units blow in and half blow out, so that the air is balanced. |
| Heat recovery | Changes direction every 70 seconds. The ceramic core keeps the heat of the air going out and gives it to the air coming in. Duka's app calls this "Regeneration". |
| Supply | Only brings fresh air in. |

## Installation

1. In HACS, open the three dots > **Custom repositories**, add
   `https://github.com/HairingX/ha_duka_connect` with the type **Integration**, and download
   **Duka Connect**.
2. Restart Home Assistant.
3. Go to **Settings > Devices & services > Add integration** and pick **Duka Connect**.
4. Choose how to find the unit:
   - **Search the network** finds the units on the same network as Home Assistant. Pick yours,
     give it a name, and enter its password. If none is found, search again or enter it by hand.
   - **Enter the unit by hand** if the search finds nothing, for example when the unit is on
     another network (VLAN) than Home Assistant.

What you are asked for:

| Field | What to enter |
|---|---|
| Name | What the unit is called in Home Assistant, such as *Bathroom*. Choose with care: it cannot be changed later. |
| Host | The unit's IP address, from your router. Give the unit a fixed IP address in the router, so that it does not change. |
| Device id | Leave it empty, and the integration finds it. Otherwise: the 16 characters shown in Duka's app, or printed on the board under the unit's front cover. |
| Password | `1111`, unless you changed it in Duka's app. |

The address and password can be changed later: **Settings > Devices & services > Duka Connect >
three dots > Reconfigure**.

## Options

**Settings > Devices & services > Duka Connect > Configure**:

| Option | What it is |
|---|---|
| Clock battery low under (mV) | *Clock battery* shows *Low* when the battery's voltage falls under this. 2500 mV unless you change it. A new battery gives about 3000 mV. Tip: when Duka's app says the battery is flat, look at *Clock battery voltage* and set the limit just above that value. |

## How often values are updated

Home Assistant asks the unit for its values on your network; the unit does not send them by
itself. The fan, its speed and the ventilation mode every 10 seconds; most other values every 30
or 60 seconds; the filter, clock battery and operating time every 15 minutes. A change made in
Home Assistant shows at once. A change made with the unit's buttons, its remote or Duka's app
shows within those times.

What a change affects is read sooner than its own time. The fans' speeds are read 3 seconds after
the speed changes, and again until they have settled. When the unit's warning or alarm clears,
the clock battery and the filter are read 10 seconds later, and again every 10 seconds while
they change, for up to 2 minutes. What a button changes is read a second after it is pressed.

## Known limitations

- **Not yet tested on a real unit**: some values may be missing or wrong.
- **The search only finds units on the same network as Home Assistant.** If your units are on
  another network (VLAN or subnet), enter them by hand. Your router must then let Home Assistant
  reach the unit on UDP port 4000. If Home Assistant runs in Docker, it needs host networking.
- **Home Assistant does not find the units by itself**: add them as described above.
- **A wrong password looks like a unit that is turned off**: the unit does not answer it at all.
- **The weekly schedule's times are set in Duka's app**; Home Assistant can only turn the
  schedule on and off.

## Troubleshooting

| Problem | What to do |
|---|---|
| "The unit did not answer" | Check the IP address and the password. If the unit is on another network than Home Assistant, let Home Assistant reach it on UDP port 4000 in your router. |
| The search finds nothing | The unit is probably on another network than Home Assistant. Enter it by hand. |
| The entities are *Unavailable* | The unit has stopped answering, for example after getting a new IP address. Check it in your router and give it a fixed address; change it with Reconfigure. |
| A value looks wrong or is missing | Download the diagnostics file (**Duka Connect > three dots > Download diagnostics**) and attach it to an issue on GitHub. It contains no password, IP address or device id. |

For more detail in the log: **Duka Connect > three dots > Enable debug logging**.

## Removing the integration

1. **Settings > Devices & services > Duka Connect > three dots > Delete**.
2. In HACS, remove **Duka Connect**, and restart Home Assistant.

The unit keeps running as before, and Duka's app still works.

## License

MIT
