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
| System pressure and zone temperature | ✅ | ✅ |
| Heat pump flow, return and operating state | ✅ | ✅ |
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
├── Thermostaat 0                   the wall thermostat — this is your climate card
├── Brain-App RensonThermostat      the driver for the wall thermostat
├── Brain-App rensonheatpumplogic   the control logic
│   └── (raw log values)
└── Brain-App RensonHeatPumpR290    the Modbus driver
    └── Renson Arean R290           the heat pump itself
```

### Thermostaat — your main card

`climate.thermostaat_0` shows room temperature, setpoint, preset and heating/cooling mode. Alongside it are room temperature, steering power, the active preset and the thermostat's operating state.

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

Every one of these carries the wiring story in its attributes — what kind of contact it is, what may be connected, which connector it sits on, and how sure the function label is. The **Kanaaloverzicht** sensor holds the whole table at once, including which source each channel depends on.

Measured values on this device — zone temperature and system pressure — come from the log of `rensonheatpumplogic`, not from the gateway. See [A note on the measured values](#a-note-on-the-measured-values).

### The apps

Each app on the Brain is its own device, named exactly as OpenMotics names it, with its version as the software version. Each has an **App actief** and a **Brondata beschikbaar** indicator, so a failing app is a state you can automate on rather than a log line nobody reads.

`rensonheatpumplogic` additionally exposes its control parameters read-only: silent mode, backup heater, hysteresis per zone, the logic and commissioning state.

### The heat pump

Flow and return temperature, operating state, domestic hot water temperature, mains voltage and the outside temperature the control logic is working with.

---

## A note on the measured values

The heat pump's readings and the HVAC module's sensor inputs are **not offered by the gateway API**. They exist only in the log lines the `rensonheatpumplogic` app writes, as unnamed lists of numbers. This integration reads them there, and is honest about what that costs:

- **They can be empty after a restart.** The app only logs a value when it *changes*. If a temperature holds steady for an hour, nothing is written for an hour. That is not a bug and polling faster does not help.
- **They go unavailable when the app updates.** The meaning of each position is tied to a specific app version — the layout demonstrably changed between two versions in ten weeks. On an unfamiliar version these entities report nothing rather than a wrong number.
- **Some of them are still being confirmed.** Every entity carries a `function_confidence` attribute. Where it says `assumed`, the mapping is a well-supported inference that has not been verified against the installation yet.

Every position of every log array is also published under a neutral name (`HP_UNIT/hp1 waarde 17`) as a diagnostic sensor, so the remaining meanings can be established by correlating history.

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
- **Removing and re-adding the integration breaks history.** Identifiers are rooted on the config entry, because the gateway offers no stable hardware id. Every alternative fails at a moment you cannot see coming; this one fails only when you do it yourself.

---

## Upgrading from 2026.6.0

Some entity ids change and a few entities disappear. See [docs/release-notes.md](docs/release-notes.md) before you upgrade.

---

## Contributing

Issues and pull requests are welcome.

---

## License

MIT
