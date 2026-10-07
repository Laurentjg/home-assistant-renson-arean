# Renson Arean — Home Assistant Integration

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
![HA Version](https://img.shields.io/badge/Home%20Assistant-2026.6%2B-blue)
![Version](https://img.shields.io/badge/version-2026.10.0-green)

> **This integration is still in development, and it has been tested on one installation only.** What differs from one Renson installation to the next is not known yet, so it needs other installations to find out. **Feedback and contributions are very welcome**: tell us what works and what does not on yours through the [issue tracker](https://github.com/Laurentjg/home-assistant-renson-arean/issues), or send a pull request.

A fully local Home Assistant custom integration for the **Renson Arean heat pump**. It talks to the OpenMotics gateway on the **Brain module** over your own network, and brings its own dashboard card.

**Languages:** the dashboard card and the settings screens are in Dutch and English, following your Home Assistant language; the entity names are in Dutch for now. French is wished for — a translation is a welcome contribution.

![The Renson Arean dashboard card](docs/images/card.png)

**You do not need a Renson One account.** Everything works on a network with no internet access at all. The integration never contacts the Renson cloud.

---

## What you get

Everything below works locally, also on a network without internet.

| | |
|---|---|
| ✏️ | Setpoint, preset and heating/cooling mode of the thermostat |
| 👁️ | Room temperature and whether the thermostat calls for heat |
| 👁️ | Status of the HVAC module's valves and pumps |
| 👁️ | System pressure and system water temperature |
| 👁️ | Heat pump flow, return, compressor frequency, operating state and reachability |
| 👁️ | Heat output and a heat energy counter, calculated from flow rate and temperature difference |
| 👁️ | Silent mode, backup heater, control parameters |
| 👁️ | Module and app versions, firmware updates available |
| 👁️ | A dashboard card that draws the heat pump with its live values |
| ❌ | Edit preset temperatures (what "away" means in degrees) — cloud only |
| ❌ | Manage the heating schedule — cloud only |

✏️ read and change · 👁️ read only · ❌ not possible locally

---

## Getting started

1. **Create a local user on the Brain module.** Hold **ACTION** and **SETUP** together for 5 seconds, browse to `https://<brain-module-ip>` and create a user. Use a separate user for Home Assistant, not your main or installer account.
2. **Install through HACS.** Add this repository as a custom repository (category **Integration**), install **Renson Arean** and restart Home Assistant.
3. **Add the integration.** **Settings → Devices & Services → Add Integration → Renson Arean**, then enter the host, username and password.
4. **Add the card.** Edit a dashboard, choose **Add card** and search for *Renson*. It fills in its entities by itself.

You need Home Assistant 2026.6 or newer and the gateway reachable on your local network.

→ Requirements, manual installation and all options: [Installation and configuration](docs/configuration.md)

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

An entity id follows the physical channel or datapoint; the display name follows its function. If a function label later turns out to be wrong, your automations keep working.

→ Every device and its entities: [The devices you will see](docs/devices.md)

---

## The dashboard card

A drawn heat pump with the values around it, where they belong: the fan turns while the heat pump runs, water flows through the pipes, and ten bars show how hard the compressor works. Around it are the temperatures, flow rate, pressure, voltage and heat output, and below it an energy overview.

The card only shows; it does not change settings. It comes with the integration — there is nothing extra to install.

→ What it shows, how to add it and which sensors of your own it can use: [The dashboard card](docs/dashboard-card.md)

---

## Heat output, heat energy and COP

The heat pump does not report how much heat it delivers. The integration calculates it from the flow rate and the temperature difference, and adds it up in a counter:

| Entity | What it is |
|---|---|
| `sensor.calculated_heat_output` | the heat given to the water right now, in kW |
| `sensor.calculated_heat_energy` | that heat added up over time, in kWh |

In the options you choose whether the heating circuit is filled with water or with water and glycol; the default is water.

The integration measures no electricity, so it has **no COP sensor**. With your own energy meter the card shows the COP, and you can calculate it by hand: heat energy gained between two moments ÷ electricity used between the same two moments.

→ The calculation, a worked example and how reliable it is: [Heat output, heat energy and COP](docs/heat-and-cop.md)

---

## Good to know before you install

- **The heat pump's readings come from a log, not from an API.** They can be empty after a restart, they go unavailable when Renson updates the app that writes them, and some of them are still being confirmed. → [The measured values](docs/measured-values.md)
- **Your gateway password is stored in plain text**, as with every Home Assistant integration that needs a password, and is therefore readable in your backups. → [Storing your gateway password](docs/security.md)
- **Some things cannot be done locally.** Silent mode and the backup heater are read-only, preset temperatures and the heating schedule are cloud-only, and there is no energy metering. → [How it works, and what it cannot do](docs/how-it-works.md)
- **Removing and re-adding the integration breaks history**, long-term statistics included.

---

## Upgrading

Each version's changes, and what they mean for you, are in the [release notes](docs/release-notes.md). Read them before upgrading from 2026.6.0: some entity ids change and a few entities disappear.

---

## Documentation

| | |
|---|---|
| [Installation and configuration](docs/configuration.md) | requirements, the local user, HACS or manual, setup and options |
| [The devices you will see](docs/devices.md) | every device and what its entities mean |
| [The dashboard card](docs/dashboard-card.md) | what it shows and how to set it up |
| [Heat output, heat energy and COP](docs/heat-and-cop.md) | the calculated values and the COP by hand |
| [The measured values](docs/measured-values.md) | where the readings come from, and long-term statistics |
| [Storing your gateway password](docs/security.md) | what is stored, and what you can do |
| [How it works, and what it cannot do](docs/how-it-works.md) | polling, writing, known limitations |
| [Release notes](docs/release-notes.md) | what each version means for you |
| [The card for developers](frontend/README.md) | card configuration in YAML, and working on the card |

---

## Contributing

The integration has run on one installation. Reports from yours help most: which values appear, which stay empty, and what differs from this description. A French translation is wished for as well. Issues and pull requests are welcome at the [issue tracker](https://github.com/Laurentjg/home-assistant-renson-arean/issues).

---

## License

MIT
