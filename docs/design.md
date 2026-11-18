# Design

How the integration is built, and why.

## A client, not a coordinator

Home Assistant's usual way to poll is a `DataUpdateCoordinator`, which fetches everything on one
interval. The `duka_connect` client plans every read itself instead: each value has its own
interval, only values an entity follows are read, everything due is read in one request, and a
poll with nothing due sends nothing. A coordinator would read every value as often as the
fastest one needs.

So the integration owns no update interval and no loop. It runs the client's `run()` as one
background task per config entry, which polls whenever the client has something due; a new
subscription or a write wakes it at once.

- The task is made with `ConfigEntry.async_create_background_task`. Unloading cancels the task
  and awaits it before the client disconnects, as a disconnect would end it with an error.
- A poll that raises is logged by the client, and polling goes on. A unit that does not answer is
  told by the client's status, which turns only after several reads in a row have gone
  unanswered: a lost answer is asked again within seconds while the entities show the last
  values. Then the entities become unavailable, and the integration logs once when the unit stops
  answering and once when it answers again. That logging stops before an unload disconnects the
  client, as a disconnect turns the status too.
- With polling disabled in the entry's system options, the client reads nothing on its schedule:
  only what is asked for, by `homeassistant.update_entity`, and what a write asks to be read back.
  The task still runs, as that read-back is made by it. Changing it reloads the entry.

## How often

| Interval | Values |
|---|---|
| 10 s | On/off, speed, manual speed, boost, timer mode, ventilation mode, fan RPMs |
| 30 s | Humidity and its flag, the timer's time left, the external sensors |
| 60 s | The settings, the alarm and the filter flag |
| 15 min | Clock battery, filter time left, operating time, clock, cloud access, IP address |
| once | Firmware and unit type |

The unit sends nothing by itself: its protocol answers requests only, so polling is the only way.

## Entities

A unique id is the unit's name and the point's key, so a replaced unit keeps its entities. Every
entity follows its points and the client's status, and sets its `_attr_` values on every change.

| Quality of the value | The entity |
|---|---|
| `GOOD` | shows it |
| `NO_DATA` | is unknown |
| `STALE` | shows the last good value |
| `OFFLINE`, `MISSING`, or the unit has not answered for half a minute | is unavailable |

The unit's clock has no time zone. *Set clock* writes Home Assistant's local time to it, and the
*Clock* sensor reads it back in the same time zone; *Clock offset* compares it with the time it
was read, which stays meaningful between the readings, 15 minutes apart.

A point the unit says it lacks gets no entity, and an entity of a point the unit no longer has
is removed at the next setup.
