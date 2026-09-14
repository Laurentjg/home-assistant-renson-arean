# Renson Arean — Home Assistant Integration

A fully local Home Assistant custom integration for the **Renson Arean heat pump**, talking to the OpenMotics gateway on the **Brain module** over your own network.

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
![HA Version](https://img.shields.io/badge/Home%20Assistant-2026.6%2B-blue)
![Version](https://img.shields.io/badge/version-2026.9.0-green)

> **You do not need a Renson One account.** Every feature below works on a network with no internet access at all. The integration never contacts the Renson cloud — not for data, not for telemetry, not for anything.

---

## What you get

| | Local | Without internet |
|---|---|---|
| Room temperature, setpoint, preset, heating/cooling | ✅ | ✅ |
| Status of the HVAC module's valves and pumps | ✅ | ✅ |
| System pressure and system water temperature | ✅ | ✅ |
| Heat pump flow, return, compressor frequency, operating state and reachability | ✅ | ✅ |
| Silent mode, backup heater, control parameters | read-only | read-only |
| Module and app versions, firmware updates available | ✅ | ✅ |
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

**Heat pump reachable** follows the heat pump itself, not the app that reads it. If the heat pump loses power or its bus link while the Brain keeps running, this entity turns off within three minutes, all heat pump values go unavailable together, and one warning is logged — with one recovery line, including the outage duration, when it comes back.

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

Settings, voltages and diagnostic values get none. The integration computes **no COP and no electrical consumption** itself: the heat pump only reports voltage and current, from which no reliable consumption follows. A dedicated energy meter does that better — and with one, you can build the COP yourself, see below.

---

## Building a COP sensor yourself

The COP (coefficient of performance) is the heat delivered divided by the electricity used. The integration supplies the heat side; the electricity side has to come from **your own energy meter** on the heat pump's supply (a smart plug is not suitable — use a DIN-rail meter or a sub-meter).

### Live or per day?

Both can be built, and they answer different questions:

| | Live COP | COP per day |
|---|---|---|
| What it is | heat output ÷ electrical power, right now | heat energy ÷ electrical energy over a whole day |
| Use it for | watching a cycle: how does the COP react to the flow temperature, to modulation, to a defrost? | judging the installation, and comparing days, weeks, seasons |
| How to read it | as a **trend**. Single values jump around; do not draw conclusions from one number | as **the** figure. This is what "my heat pump has a COP of 4" means |

The live value is noisy by nature, for reasons that have nothing to do with the heat pump:

- **Timing.** The heat pump values are logged only when they change and read every 30 seconds; your meter updates on its own schedule. For a moment, the heat output and the power drawn belong to slightly different instants.
- **Small temperature difference.** Flow and return usually differ by only 2–4 K. A sensor tolerance of 0.2 K is already 5–10 % of the heat output.
- **Start-up, defrost and overrun.** At start-up the power is there before the heat is. During a defrost the heat pump takes heat *out* of the system, so the heat output — and the COP — briefly turn negative. After switching off, the pump keeps running for a few minutes with hardly any temperature difference.

A day averages all of that out, and includes the standby consumption and the defrosts the heat pump really costs you. Therefore: **judge by the daily COP, watch the live COP for understanding.**

> Never average COP values. A day's COP is *total heat ÷ total electricity*, not the mean of the live values — one minute at COP 8 with the compressor barely running would otherwise weigh as much as an hour of full load.

### Step 1 — heat output

Heat output (kW) = flow (m³/h) × 1.163 × (flow temperature − return temperature). The factor 1.163 kWh/(m³·K) holds for **plain water**. If your primary circuit contains glycol, the factor is lower (roughly 1.0–1.1 depending on concentration) — check with your installer.

Add to `configuration.yaml` (or create the same via **Settings → Devices & Services → Helpers → Template**):

```yaml
template:
  - sensor:
      - name: "Heat pump heat output"
        unique_id: heat_pump_heat_output
        unit_of_measurement: "kW"
        device_class: power
        state_class: measurement
        state: >
          {% set flow = states('sensor.heatpump_flow') | float(0) %}
          {% set supply = states('sensor.heatpump_flow_temperature') | float(0) %}
          {% set ret = states('sensor.heatpump_return_temperature') | float(0) %}
          {{ (flow * 1.163 * (supply - ret)) | round(2) }}
        availability: >
          {{ has_value('sensor.heatpump_flow')
             and has_value('sensor.heatpump_flow_temperature')
             and has_value('sensor.heatpump_return_temperature') }}
```

### Step 2 — live COP

Replace `sensor.heat_pump_power` with your own meter's power sensor (in W). The COP is only shown while the compressor runs; the rest of the time it is `unavailable`, which is more honest than 0 or a division by almost nothing.

```yaml
template:
  - sensor:
      - name: "Heat pump COP live"
        unique_id: heat_pump_cop_live
        state_class: measurement
        state: >
          {{ (states('sensor.heat_pump_heat_output') | float(0)
              / (states('sensor.heat_pump_power') | float(0) / 1000)) | round(1) }}
        availability: >
          {{ states('sensor.heatpump_compressor_frequency') | float(0) > 0
             and states('sensor.heat_pump_power') | float(0) > 200 }}
```

### Step 3 — COP per day

First turn heat output into heat energy, then count both energies per day:

```yaml
sensor:
  - platform: integration
    name: "Heat pump heat energy"
    unique_id: heat_pump_heat_energy
    source: sensor.heat_pump_heat_output
    method: left
    round: 3
    # The heat pump values are only logged when they change: keep integrating
    # while the value holds steady.
    max_sub_interval:
      minutes: 5

utility_meter:
  heat_pump_heat_energy_daily:
    unique_id: heat_pump_heat_energy_daily
    source: sensor.heat_pump_heat_energy
    cycle: daily
    # A defrost makes the counter go down briefly; that is not a meter reset.
    net_consumption: true
  heat_pump_electric_energy_daily:
    unique_id: heat_pump_electric_energy_daily
    source: sensor.heat_pump_energy  # your meter's energy sensor, in kWh
    cycle: daily

template:
  - sensor:
      - name: "Heat pump COP today"
        unique_id: heat_pump_cop_today
        state: >
          {{ (states('sensor.heat_pump_heat_energy_daily') | float(0)
              / states('sensor.heat_pump_electric_energy_daily') | float(0)) | round(2) }}
        availability: >
          {{ states('sensor.heat_pump_electric_energy_daily') | float(0) > 0.2 }}
```

`Heat pump COP today` builds up during the day; the value just before midnight is that day's COP. Early in the morning, with little consumed yet, it can still swing — hence the 0.2 kWh threshold. For a week, month or season, do the same division on the long-term statistics of the two energy sensors (for example with two statistic cards), not on the daily COPs.

### How reliable is it?

- **The flow rate and the flow/return assignment are well-supported inferences**, not values Renson names (`function_confidence: assumed`). The strongest evidence for them is precisely this calculation: on a measured cycle it came out at a COP of 3.6–5.8 at 15 °C outside and 40 °C flow, which is what an R290 monobloc should achieve. If you see structurally impossible values (below 1 or above 8 over a whole day), report it.
- **Domestic hot water** is included in the heat output as long as it is heated through the same circuit.
- **Do not use mains voltage × current as a substitute for a meter.** That is apparent power: without the power factor it overestimates the consumption, so the COP comes out systematically too low — and in a daily total that error accumulates.

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
