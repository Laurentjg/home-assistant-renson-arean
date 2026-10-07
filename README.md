# Renson Arean — Home Assistant Integration

A fully local Home Assistant custom integration for the **Renson Arean heat pump**, talking to the OpenMotics gateway on the **Brain module** over your own network.

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
![HA Version](https://img.shields.io/badge/Home%20Assistant-2026.6%2B-blue)
![Version](https://img.shields.io/badge/version-2026.10.0-green)

> **You do not need a Renson One account.** Every feature below works on a network with no internet access at all. The integration never contacts the Renson cloud — not for data, not for telemetry, not for anything.

---

## What you get

| | Local | Without internet |
|---|---|---|
| Room temperature, setpoint, preset, heating/cooling | ✅ | ✅ |
| Status of the HVAC module's valves and pumps | ✅ | ✅ |
| System pressure and system water temperature | ✅ | ✅ |
| Heat pump flow, return, compressor frequency, operating state and reachability | ✅ | ✅ |
| Heat output and a heat energy counter, calculated from flow rate and temperature difference | ✅ | ✅ |
| Silent mode, backup heater, control parameters | read-only | read-only |
| Module and app versions, firmware updates available | ✅ | ✅ |
| A dashboard card that draws the heat pump with its live values | ✅ | ✅ |
| Edit preset temperatures (what "away" means in degrees) | ❌ | ❌ cloud only |
| Manage the heating schedule | ❌ | ❌ cloud only |

---

## The devices you will see

The integration mirrors how the installation is actually built, rather than presenting one lump.

```
Brain module                        the controller: firmware, system bus, updates
├── HVAC module                     the DIN-rail box with the relays and sensor inputs
├── Thermostaat 0                   the thermostat zone (wall thermostat + controller) — your climate card
├── Brain-App RensonThermostat      the driver for the wall thermostat
├── Brain-App rensonheatpumplogic   the control logic
│   └── (raw log values)
└── Brain-App RensonHeatPumpR290    the Modbus driver
    └── Renson Arean R290           the heat pump itself
        └── Berekende waarden       what the integration calculates from the heat pump's readings
```

### Thermostaat — your main card

`climate.thermostat_0` shows room temperature, setpoint, preset, heating/cooling mode, and whether the thermostat is calling for heat right now. Alongside it are room temperature, the active preset and whether the thermostat is switched on.

Heating/cooling is a setting of the **thermostat group**, not of one thermostat: changing it on one card changes it for every thermostat in that group.

The control internals — hysteresis and steering power — are not on this device. They are owned by the control logic, which sets them in the controller on the Brain, and the wall thermostat has no register for them, so they appear under **Brain-App rensonheatpumplogic** as diagnostics (under **Brain module** if that app is not installed).

Presets are `schedule`, `away` and `manual`, shown in your own language. The internal values are unchanged, so existing automations that use `preset_mode: away` keep working.

### HVAC module — the valves and pumps

One binary sensor per output channel. The entity id follows the **physical channel**, the display name follows the **function**:

| Entity | Name | Channel |
|---|---|---|
| `binary_sensor.hvac_module_r1` | Zone 1-afsluiter | R1, dry contact |
| `binary_sensor.hvac_module_r2` | Badkamerventiel | R2, dry contact |
| `binary_sensor.hvac_module_r3` | Driewegklep | R3, 230 V |
| `binary_sensor.hvac_module_r4` | CV-pomp | R4, 230 V |
| `binary_sensor.hvac_module_r5` | Recirculatiepomp | R5, 230 V |
| `binary_sensor.hvac_module_out1` | OUT1 (function unknown) | OUT1, 0-10 V |
| `binary_sensor.hvac_module_out2` | Zone 0-dummyklep | OUT2, 0-10 V |
| `binary_sensor.hvac_module_out3` | Bypass-klep | OUT3, 0-10 V |

That split is deliberate: if it later turns out R3 switches something other than a three-way valve, only the label is wrong. Your automations keep working, and you can rename the entity yourself in two clicks.

The same rule holds one level up: an entity id never names the *device* it is shown on, only the channel or datapoint it reads. So if a measurement turns out to belong to a different device than first assumed, the entity moves without its id changing.

Every one of these carries the wiring story in its attributes — what kind of contact it is, what may be connected, which connector it sits on, and how sure the function label is. The **Kanaaloverzicht** sensor holds the whole table at once, including which source each channel depends on.

Measured values on this device — system water temperature and system pressure — come from the log of `rensonheatpumplogic`, not from the gateway. The tank and recirculation sensors (T1, T2, T4) exist as entities but are disabled unless your installation has domestic hot water or recirculation switched on. See [A note on the measured values](#a-note-on-the-measured-values).

### The apps

Each app on the Brain is its own device, named exactly as OpenMotics names it, with its version as the software version. Each has an **App actief** and a **Brondata** indicator (OK / Probleem), so a failing app is a state you can automate on rather than a log line nobody reads.

`rensonheatpumplogic` additionally exposes its control parameters read-only: silent mode, backup heater, hysteresis per zone, the logic and commissioning state.

### The heat pump

Flow and return temperature, flow rate, flow temperature setpoint, compressor frequency, operating state, domestic hot water temperature, mains voltage, current drawn and the outside temperature the control logic is working with. Two on/off indicators show whether the compressor is *requested* (this comes on about two minutes before it actually runs) and whether the pump inside the monobloc is running.

The **warranty number** (Garantienummer) of the heat pump, as stored in the control logic, is a diagnostic sensor.

**Heat pump reachable** follows the heat pump itself, not the app that reads it. If the heat pump loses power or its bus link while the Brain keeps running, this entity turns off within three minutes, all heat pump values go unavailable together, and one warning is logged — with one recovery line, including the outage duration, when it comes back.

### Berekende waarden — what the integration calculates

Every other device shows what the installation reports. **Heat output and heat energy** are not reported by anything: the integration calculates them from the heat pump's readings. They therefore have a device of their own, *Berekende waarden* (calculated values), so the heat pump device only holds what the heat pump says itself:

| Entity | Name | What it is |
|---|---|---|
| `sensor.calculated_heat_output` | Warmtevermogen | the heat given to the water right now, in kW: flow rate × factor × (flow temperature − return temperature) |
| `sensor.calculated_heat_energy` | Warmte-energie | that heat output added up over time, in kWh. A counter: it keeps its total across restarts |

The factor depends on what the heating circuit is filled with: 1.163 kWh/(m³·K) for plain water, 1.08 for water with glycol. Choose it under [Options](#options); the default is water. Both values can be negative or go down for a while: during a defrost, and while cooling, the heat pump takes heat *out* of the water. What the heat pump did while Home Assistant was not running is not counted.

When the heat pump is unreachable, the heat output is unavailable with it, and the counter waits.

---

## The dashboard card

The integration brings its own dashboard card: a drawn heat pump with the values around it, where they belong. There is nothing extra to install — the card comes with the integration and is available after a restart.

**What it shows**

- **On the pump:** the fan turns while the heat pump runs, the water flows through the pipes while the pump circulates, and ten bars show how hard the compressor works. In silent mode a moon appears over the fan and it turns slower. In cooling mode red and blue swap sides.
- **Around the pump:** outside temperature, flow and return temperature, flow rate, system pressure, mains voltage and current, and the heat output.
- **In the boxes:** operating state, silent mode and the warranty number; what your thermostat measures, wants and asks for; and an energy overview with the COP per day over the last 14 days and the COP over 24 hours, 2 months and 12 months.

The card only shows; it does not change settings. Tap a value to open its entity. It follows your Home Assistant theme, light or dark, and writes numbers the way your profile says. Its texts are in Dutch or English, following your language.

**Adding it**

Edit a dashboard, choose **Add card** and search for *Renson*. The card fills in the entities of this integration by itself; you can change each one in the editor. In YAML it is `type: custom:renson-arean-card`. The card adapts to the room it gets: in a full-width section or a panel view it is one wide picture, and in a normal section or on a phone it stacks the same parts below each other, so the text keeps the size of the rest of your dashboard. The drawing is never enlarged beyond its design size: in a very wide view the card stays 800 px wide, centred.

After an update a browser can keep running the previous version of the card for a while. The card notices that and shows the message *The Renson Arean card has been updated* at the bottom of the screen: choose **Refresh**.

If the card does not appear in the list after an update, or shows a configuration error in one browser only, that browser still holds an older copy of Home Assistant's pages. Reload the page once without cache (Ctrl+Shift+R). If that does not help, clear the stored data for your Home Assistant address — in Firefox: the padlock in the address bar → **Clear cookies and site data** — and log in again. The first page after that may still show the error for a moment before the card appears. A private window is a quick way to tell: if the card works there, stored data in your normal profile is the cause.

**Electricity and COP need your own meter**

The integration supplies the heat side: the card fills in the heat output and the heat energy counter by itself. It measures no electrical power (see [Long-term statistics](#long-term-statistics)), so the card has optional places for your own sensors:

| In the editor | What to choose | What you get |
|---|---|---|
| Electrical power | your meter's power sensor | power next to "electricity", and the live COP |
| Electrical energy counter | your meter's kWh sensor | electricity today, and all COP figures |
| Gas boiler active | an entity of your own that knows whether the boiler burns | the flame in the heat demand box |

If you clear the heat output entity in the editor, the card calculates the heat output itself, for plain water.

Without your own sensors the card still works: what cannot be shown is left out, with a short note in the energy box saying which sensor is missing. A value that is temporarily unavailable shows as a grey dash, never as zero. The COP figures come from Home Assistant's long-term statistics and are always total heat ÷ total electricity over the period.

The full list of settings is in [`frontend/README.md`](frontend/README.md).

---

## A note on the measured values

The heat pump's readings and the HVAC module's sensor inputs are **not offered by the gateway API**. They exist only in the log lines the `rensonheatpumplogic` app writes, as unnamed lists of numbers. This integration reads them there, and is honest about what that costs:

- **They can be empty after a restart.** The app only logs a value when it *changes*. If a temperature holds steady for an hour, nothing is written for an hour. That is not a bug and polling faster does not help.
- **They go unavailable when the app updates.** The meaning of each position is tied to a specific app version — the layout demonstrably changed between two versions in ten weeks. On an unfamiliar version these entities report nothing rather than a wrong number.
- **Some of them are still being confirmed.** Every entity carries a `function_confidence` attribute. Where it says `assumed`, the mapping is a well-supported inference that has not been verified against the installation yet.

Every position of every log array is also published under a neutral name — `HP_UNIT/hp1 waarde 17`, as `sensor.ssr_hp_unit_hp1_17` — as a diagnostic sensor, so the remaining meanings can be established by correlating history.

---

## Long-term statistics

Home Assistant keeps long-term statistics forever, even after the regular history is purged. This integration deliberately keeps them for only a few quantities — the ones that tell you, a year from now, whether the system still performs as it does today:

- outside temperature
- heat pump flow and return temperature
- compressor frequency
- system pressure
- heat energy, as a counter

Settings, voltages and diagnostic values get none. Neither does the heat output: the heat energy counter holds the same information, and the heat delivered over any hour, day or month follows from it. The integration computes **no COP and no electrical consumption** itself: the heat pump only reports voltage and current, from which no reliable consumption follows. A dedicated energy meter does that better — and with one, you can calculate the COP yourself, see below.

---

## Calculating the COP yourself

The COP (coefficient of performance) is the heat delivered divided by the electricity used. The integration supplies the heat side, as `sensor.calculated_heat_energy`. The electricity side has to come from **your own energy meter** on the heat pump's supply (a smart plug is not suitable — use a DIN-rail meter or a sub-meter), as a counter in kWh.

The dashboard card does this calculation for you once you point it at your meter. To do it by hand, read both counters at two moments and divide the differences:

```
COP = (heat energy at the end − heat energy at the start)
      ÷ (electrical energy at the end − electrical energy at the start)
```

For example, over one day:

| | Midnight | Next midnight | Difference |
|---|---|---|---|
| Heat energy (`sensor.calculated_heat_energy`) | 1 250.4 kWh | 1 275.2 kWh | 24.8 kWh |
| Electrical energy (your meter) | 3 410.7 kWh | 3 416.9 kWh | 6.2 kWh |

COP = 24.8 ÷ 6.2 = 4.0.

You find the readings in the history of each sensor: open the entity, pick the two moments in the graph and read the values. Home Assistant keeps these counters in its long-term statistics, so the same works for moments months apart. A statistic card or statistics graph card with the type *change* gives the difference over a period directly.

**Choosing the two moments**

- **Take both readings at the same two moments.** The heat counter and your meter must cover exactly the same period.
- **Take at least a day.** Over a short period the result swings: at start-up the power is there before the heat is, a defrost takes heat *out* of the system, and flow and return often differ by only 2–4 K, so a sensor tolerance of 0.2 K is already 5–10 % of the heat output. A day averages that out, and includes the standby consumption and the defrosts the heat pump really costs you.
- **Never average COP values.** The COP over a week is *total heat ÷ total electricity* over that week, not the mean of seven daily COPs — a mild day with little consumption would otherwise weigh as much as a cold one.

### How reliable is it?

- **The flow rate and the flow/return assignment are well-supported inferences**, not values Renson names (`function_confidence: assumed`). The strongest evidence for them is precisely this calculation: on a measured cycle it came out at a COP of 3.6–5.8 at 15 °C outside and 40 °C flow, which is what an R290 monobloc should achieve. If you see structurally impossible values (below 1 or above 8 over a whole day), report it.
- **The factor for glycol is an approximation.** 1.08 kWh/(m³·K) is for water with about 30 % glycol. The real value depends on the kind of glycol and the concentration and can differ by a few percent; the COP differs by the same percentage.
- **The heat counter only counts while Home Assistant runs.** After a restart or a connection outage, the heat delivered in the meantime is missing, while your meter kept counting. A period that contains such a gap gives a COP that is too low.
- **Domestic hot water** is included in the heat output as long as it is heated through the same circuit.
- **Do not use mains voltage × current as a substitute for a meter.** That is apparent power: without the power factor it overestimates the consumption, so the COP comes out systematically too low — and in a total that error accumulates.

---

## Storing your gateway password

**Your password is stored in plain text — not hashed, not encrypted.** This is worth understanding before you install anything, and it is true of every Home Assistant integration that needs a password.

It cannot be otherwise here: the OpenMotics gateway trades your real password for a one-hour token, so the integration must be able to present that password again at every renewal. A hash is useless for that. And Home Assistant stores integration settings as plain JSON in `.storage/core.config_entries`; there is no encrypted store.

**In practice: your gateway password is readable in your Home Assistant backups.**

What the integration does do: the token is kept in memory and never written to disk, credentials never appear in a log line (not even at debug level — the password travels in the URL, so naive logging would leak it outright), and downloadable diagnostics are redacted.

What you can do:

- Create a **separate gateway user for Home Assistant**, not your main or installer account. Revoking it then affects nothing else.
- Keep Home Assistant backups encrypted, and preferably not on a shared network drive.

---

## Preconditions

### Create a local user on the Renson Brain module

The integration authenticates against the **local REST API** of the Brain module, so a local user account has to exist first.

1. **Enable authorization mode** by pressing and holding **ACTION** and **SETUP** together for at least 5 seconds. The module indicates that authorization mode is active.
2. Browse to `https://<brain-module-ip>` and accept the self-signed certificate warning.
3. Log in and create a local user account. Note the credentials.

> The Brain module uses a self-signed TLS certificate. Certificate verification is therefore off by default; you can switch it on in the options if your gateway presents a certificate your Home Assistant trusts.

---

## Requirements

- Home Assistant 2026.6 or newer
- A Renson Arean heat pump on an OpenMotics gateway (Brain module), gateway firmware 3.14.0 or comparable
- The gateway reachable on your local network over HTTPS
- A local user account on the gateway

The integration has **no external dependencies**. `requirements` in the manifest is empty and stays that way: a library that is not there cannot carry a vulnerability.

---

## Installation

### Via HACS

1. **HACS → Integrations**
2. Three-dot menu → **Custom repositories**
3. Add this repository, category **Integration**
4. Search for **Renson Arean**, install, restart Home Assistant

### Manual

Copy `custom_components/renson_arean/` into `<ha-config>/custom_components/` and restart.

---

## Configuration

### Setup

**Settings → Devices & Services → Add Integration → Renson Arean**, then enter the host (without `http(s)://`), username and password.

The gateway reports no serial number, so the integration cannot tell two identical gateways apart automatically. If you enter a host that is already configured, it warns you rather than silently refusing — adding a genuine second installation stays possible.

### Options

**Settings → Devices & Services → Renson Arean → Configure**

| Option | Default | What it does |
|---|---|---|
| Verify TLS certificate | off | On means the gateway's certificate must be trusted. Leave off for the factory self-signed certificate. |
| Thermostat Modbus slave address | 41 | Must match the address in the RensonThermostat app. |
| Wall thermostat is wired to | Brain module | Only affects where the thermostat appears in the device tree. |
| Thermostat status interval | 10 s | What you watch live. |
| Outputs and app log interval | 30 s | Do not raise much: the log buffer holds about 90 seconds. |
| App configuration interval | 5 min | These are settings, not measurements. |
| Modules, apps and versions | 15 min | Rarely changes. |
| Voltage measurement offset | 0 V | Added to the heat pump's mains voltage reading, from −10 to +10 V. Only a certified professional should measure the real voltage at the monobloc. |
| The heating circuit is filled with | Water | Water, or water with glycol (antifreeze). Decides the factor behind the heat output and the heat energy: 1.163 for water, 1.08 for glycol. Changing it does not recalculate what was already counted. |

---

## How it works

The integration talks to the local OpenMotics REST API. Authentication uses a token with a one-hour lifetime, renewed automatically and kept in memory only.

There is no single polling interval. Each source is polled at a rate matching how fast it actually changes, which keeps the thermostat current without re-reading the topology every ten seconds.

Setpoint and preset changes are written as Modbus register writes to the wall thermostat, exactly as the previous version did. Because the app polls that thermostat every 5 seconds, confirmation cannot arrive sooner — so the card shows your change immediately, the gateway is asked again at 2, 5, 8, 12 and 20 seconds, and a poll carrying the old value cannot undo what you just set. If confirmation never comes, the gateway value takes over again and one warning is logged.

There is deliberately **no service to write an arbitrary Modbus register**. As a service that would be a remote arbitrary write onto the installation bus. Writing is limited to the setpoint and the preset, both range-checked before they are sent.

---

## Known limitations

- **The two heat pump apps are read-only.** Silent mode and the backup heater are shown but cannot be switched. Changing them means rewriting a whole configuration block, which can collide with the app itself, and a wrong control parameter costs comfort or heat pump life. Set them in OpenMotics or the Renson One app instead.
- **Preset temperatures and the heating schedule are cloud-only.** They are stored locally on the Brain and keep working without internet; only *changing* them needs Renson One.
- **No energy metering.** The P1 port cannot be used alongside the expansion bus, and the expansion bus carries the Modbus link to the heat pump and thermostat. This is a property of the hardware, not an omission. A separate P1 Concentrator module would be needed.
- **The bypass position is a state, not a percentage.** All eight outputs report a constant dimmer value, so there is no percentage to read. What the log does report is `Open` or `Closed`.
- **A sensor drifting out of true cannot be detected.** An NTC is a passive resistor with no error signal; only a disconnected or short-circuited sensor is recognisable. A perfectly ordinary reading, 0 °C included, is never discarded.
- **Removing and re-adding the integration breaks history**, long-term statistics included. Identifiers are rooted on the config entry, because the gateway offers no stable hardware id. Every alternative fails at a moment you cannot see coming; this one fails only when you do it yourself.

---

## Upgrading from 2026.6.0

Some entity ids change and a few entities disappear. See [docs/release-notes.md](docs/release-notes.md) before you upgrade.

---

## Contributing

Issues and pull requests are welcome.

---

## License

MIT
