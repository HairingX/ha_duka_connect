# Duka Connect

A Home Assistant integration for **Duka One** ventilation units, over the unit's own UDP protocol
on your local network. No cloud.

Built on [duka_connect](https://github.com/HairingX/duka_connect).

> **Not yet tested on a unit.** Every value is taken from published material about the
> protocol; none has been read on a Duka One by this integration yet. Reports of what your unit
> shows are welcome - the diagnostics download has what is needed.

## What you get

| Entity | What it is |
|---|---|
| Fan | On and off, the three preset speeds, and any speed as a percentage (the manual speed) |
| Ventilation mode | Extract, heat recovery or supply |
| Timer mode | Off, night or party |
| Humidity, fan speed | Measurements |
| Alarm | None, alarm or warning |
| Filter replacement | On when the filter needs replacing, with the time left until it does |
| Clock battery | The voltage of the CR1220 cell that keeps the unit's clock |
| Humidity boost, humidity threshold, boost off delay | Settings |
| Reset filter timer, reset alarms | Buttons |
| Operating time, firmware, unit type | Diagnostics |

A value the unit says it does not have gets no entity.

## Installation

1. In HACS, add `https://github.com/HairingX/ha_duka_connect` as a custom repository of the
   type *Integration*, and install **Duka Connect**.
2. Restart Home Assistant.
3. Settings > Devices & services > Add integration > **Duka Connect**.

Choose how to find the unit:

- **Search the network**: the integration asks every unit on the network, by broadcast. Pick the
  unit from those found, name it, and give its password. When none is found, search again or
  enter the unit by hand. The search reaches units on the same network as Home Assistant: in
  Docker, that needs host networking, and across VLANs it is not forwarded.
- **Enter the unit by hand**: its IP address, best a fixed one set in your router, and its
  password. The device id is in Duka's app; leave it empty, and the integration asks the unit
  for it.

The password is `1111` unless it was changed in the app. A unit does not answer a wrong password,
so a wrong one shows as "did not answer".

The address and password can be changed later: the integration's three dots > Reconfigure.

## License

MIT
