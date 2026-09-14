# Release notes

What each version means for you as a user.

---

## 2026.9.0 — in preparation

This version reorganises the integration so that it follows how a Renson installation is actually built. Functionally you can do the same things, but you will find them in different places and **every entity id changes**. Upgrading means removing the integration and adding it again. Read this before you start.

### What gets better

- **Your installation is recognisable.** Instead of one device "Renson Arean" you see the Brain module, the HVAC module, your thermostat, the three apps running on the Brain, and the heat pump itself — each app with the version number OpenMotics shows as well.
- **The three "unknown outputs" are resolved.** They turned out to be `Zone 1-afsluiter` (zone 1 shut-off valve, R1), `Bypass-klep` (bypass valve, OUT3) and one channel `hvac_config` assigns nothing to (OUT1). The names no longer come from the code but from the installation itself: the app supplies the wiring map your installer filled in at commissioning.
- **New measurements.** System water temperature, system pressure, heat pump flow and return temperature, flow rate, flow temperature setpoint, compressor frequency, outside temperature and mains voltage, plus whether the compressor is requested and whether the pump inside the monobloc runs. Do read the note further down — these values arrive by a detour.
- **You can see when your heat pump drops out.** `Warmtepomp bereikbaar` (heat pump reachable) now follows the heat pump itself: if it fails while the Brain keeps running, the entity turns off within three minutes, one warning appears in the log, and one message with the outage duration when it recovers. Before, such an outage was completely invisible.
- **Your thermostat card shows whether heat is being requested.** The card now says "heating" or "idle", instead of you having to work that out from two separate diagnostic values.
- **Changes show immediately.** When you change the temperature, the card responds at once instead of at the next polling round. And it no longer jumps back to the old value: a poll that happens just before the app's own cycle can no longer undo your change.
- **A quieter log.** At start-up the integration reports once per data source whether it works, and after that only when something changes. A failure is reported once, not again at every poll.
- **Every polling interval fits its source.** The thermostat every 10 seconds, the valves and pumps every 30, the app settings every 5 minutes, the module list every 15 minutes.
- **The thermostat's Modbus address is a number field** in the options, no longer a slider.

### What you need to change

**You must remove the integration and add it again.** There is no automatic transition from 2026.6.0 to 2026.9.0. All entity ids are new; the history of the old entities stays in the database but is no longer filled.

*Why no migration:* an earlier design converted the old entities to the new layout. That worked, but Home Assistant does not rename an existing entity id when the identity underneath it moves. The result was one installation with four naming conventions mixed together — including ids naming the wrong device, such as an output of the HVAC module called `gateway_uitgang_7`. One clean layout is cheaper in the long run than a correct migration to a messy one.

**How the new names are built.** The entity id names the *channel or datapoint* and never changes after that; the display name names the *function* and may improve with each release. A name you set yourself always wins.

| What | Entity id | Display name |
|---|---|---|
| Output R3 of the HVAC module | `binary_sensor.hvac_module_r3` | Driewegklep |
| Output OUT3 | `binary_sensor.hvac_module_out3` | Bypass-klep |
| Your thermostat | `climate.thermostat_0` | Thermostaat 0 |
| Silent mode | `binary_sensor.app_rensonheatpumplogic_silent_mode` | Stille modus actief |
| Heat pump flow temperature | `sensor.heatpump_flow_temperature` | Aanvoertemperatuur |

If R3 later turns out to switch something other than a three-way valve, only the label changes. Your automations keep working, because they refer to the channel.

**The silent mode switch becomes a status display.** You can still read silent mode, but no longer switch it from Home Assistant. If an automation switches it today, that automation will stop working.

*Why:* the setting lives in the `rensonheatpumplogic` app, where a change is only possible by writing back the whole configuration block. That can collide with the app itself, and a wrong control parameter costs comfort or heat pump life. It becomes switchable again once a per-field write path has been demonstrated. Meanwhile you can set it in OpenMotics or the Renson One app. The same goes for the backup heater, which was already read-only in 2026.6.0.

**The bypass sensor is dropped without a replacement percentage.** It read a percentage from output 6. That was the wrong channel — the bypass is on output 7 — and the value turned out to be a constant: all eight outputs report the same unchanging dimmer value. What you get instead is `Bypass-stand` (bypass position), reporting `Open` or `Closed`.

**`Modbus-verbinding gezond` (Modbus connection healthy) is dropped.** In practice it reported a fault permanently, even while the heat pump was running: it read an error message from an app that does not handle the Modbus link at all, and that message never changes. Use `Warmtepomp bereikbaar` in automations instead.

**Hysteresis and steering power are now under `Brain-App rensonheatpumplogic`.** That app owns the control: it sets these values in the controller on the Brain, and your wall thermostat has no register for them. Without that app they appear under the Brain module. Whether heat is being requested is still shown on your thermostat card. `Bedrijfstoestand thermostaat` is now called `Thermostaat ingeschakeld` (thermostat switched on): it is an on/off flag, not an operating state, and the old name suggested otherwise.

**`Brondata beschikbaar` is now called `Brondata`** (source data). It already was a problem indicator — `on` meant something was wrong — but the name promised the opposite. Home Assistant now shows it as `OK` or `Probleem`.

**`Zonetemperatuur` is now called `Systeemwatertemperatuur`** (system water temperature). Measurements on a running installation showed this sensor rising to almost 40 °C while the room was at 20 °C: it is the water temperature in the heating system, not a room temperature.

**The sensors of the hot water tank and the recirculation exist as entities, but are disabled by default** if your installation does not use domestic hot water or recirculation. If those subsystems are switched on, the sensors are enabled automatically. Enable them manually without the subsystem running and they stay empty — the `Kanaaloverzicht` (channel overview) tells you why.

**Output 6 has a different name.** It appeared as "Bypass-klep" in your overview; it is in fact the dummy zone valve of the thermostat system. The label was wrong, not the channel.

**`Temperatuuroffset` (temperature offset) is a regular entity** on `Brain-App RensonThermostat`, enabled by default, instead of a hidden diagnostic value.

**Your thermostat moves to a device of its own.** Dashboard cards that refer to the *device* rather than to the entity need to be linked again.

**New devices appear** that you did not have before: the three apps on the Brain and the heat pump itself, shown with model `Arean R290`. That is not clutter but the place where their version numbers and fault indicators belong.

### A note on the new measurements

The temperatures and pressures of the HVAC module and all heat pump values are **not offered by the gateway**. They exist only in the log the `rensonheatpumplogic` app keeps, as unnamed lists of numbers. The integration reads them there, and is honest about what that costs:

- **They can be empty after a restart.** The app only writes a value when it *changes*. If a temperature holds steady for an hour, nothing about it is logged for an hour. That is not a fault, and polling faster does not help.
- **They go unavailable when the app is updated.** The meaning of each position is tied to a specific app version, and that layout demonstrably changed between two versions in ten weeks. On an unknown version these entities report nothing rather than a wrong number.
- **The meaning of some of them is not yet settled.** Every entity carries a `function_confidence` attribute. Where it says `assumed`, the mapping rests on a well-supported inference that has not yet been verified against the installation.

In addition, every position of every log array is published under a neutral name (`HP_UNIT/hp1 waarde 17`) as a diagnostic sensor, disabled by default. That makes it possible to work out what the remaining positions mean.

### Long-term statistics

Home Assistant keeps statistics for some values forever, even after the regular history is purged. This version deliberately chooses few values for that — only the quantities that tell you, a year from now, whether your system still performs as it does today:

- outside temperature
- heat pump flow and return temperature
- compressor frequency
- system pressure

Everything else — settings, voltages, diagnostic values — gets no long-term statistics. That keeps your database small and your graphs readable.

The integration computes **no efficiency (COP) and no electrical consumption** itself. The heat pump only reports voltage and current, from which no reliable consumption follows; a dedicated energy meter does that more accurately. With such a meter you can build a COP sensor yourself — the README explains how, and how to read it.

**Notifications after the upgrade.** After updating, Home Assistant may report that it can no longer keep statistics for some old entities — for example *Looptijd stille modus*, *Max. duur stille modus* or *Stuurvermogen* — and ask whether you want to delete the existing statistics. That is fine: these values deliberately no longer get long-term statistics.

### Storing your gateway password

Worth knowing, and true of every Home Assistant integration with a password:

**Your gateway password is stored in plain text, not hashed or encrypted.** It cannot be otherwise: the OpenMotics gateway only hands out a temporary one-hour token in exchange for your real password, so the integration must be able to present that password again. Home Assistant stores integration settings as plain JSON in `.storage/core.config_entries`; there is no encrypted store.

In practice: **your password is readable in your Home Assistant backups.**

What the integration does do: the temporary token is never written to disk, passwords never appear in the log (not even at debug level — the password travels in the URL, so naive logging would leak it outright), and the downloadable diagnostics are redacted.

What you can do:

- Create a **separate gateway user for Home Assistant** instead of using your main or installer account.
- Keep Home Assistant backups encrypted, and preferably not on a shared network drive.

### One more thing to know

**If you remove the integration and add it again, your history starts over** — long-term statistics included. That applies to upgrading to this version, and afterwards as well. The identity of all devices and entities is tied to the config entry, because the gateway provides no serial number or other stable hardware id. Every alternative fails at a moment you do not see coming — a DHCP change, or a module being replaced. This one only fails when you do it yourself.

What does last: as long as you leave the integration in place, your entity ids no longer change. They are tied to the channel or datapoint, not to the device they are shown on — so if a measurement later turns out to belong to a different device, the entity moves along without breaking your automations.

### What does not change

- **You do not need a Renson One account.** The integration talks exclusively and locally to the Brain module on your own network. Not a single request goes to the Renson cloud — not even for the outside temperature, which comes from the local log.
- **Everything keeps working without internet.** The heating schedule and preset temperatures you set earlier through Renson One are stored locally on the Brain and keep working. Only *changing* those two requires the Renson One app — that was already the case in 2026.6.0.
- **Your presets keep their values.** The menu shows them in your own language, but the underlying values `schedule`, `away` and `manual` are unchanged. Existing automations keep working.

---

## 2026.6.0 — 25 June 2026

First working version. One device with thermostat control (temperature, preset, heating/cooling), silent mode, and the status of the valves and pumps.
