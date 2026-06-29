# Renson Arean — Home Assistant Integration

A fully local Home Assistant custom integration for the **Renson Arean heat pump**, controlled via the OpenMotics gateway (Brain module). No cloud connection required for day-to-day operation.

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
![HA Version](https://img.shields.io/badge/Home%20Assistant-2026.6%2B-blue)
![Version](https://img.shields.io/badge/version-2026.6.0-green)

---

## Features

| Feature | Local | Without internet |
|---------|-------|-----------------|
| Read room temperature | ✅ | ✅ |
| Read / set target temperature (setpoint) | ✅ | ✅ |
| Read / switch preset (schedule / away / manual) | ✅ | ✅ |
| Read / switch HVAC mode (heating / cooling) | ✅ | ✅ |
| Silent mode on/off | ✅ | ✅ |
| HVAC output status (valves, pumps) | ✅ | ✅ |
| Bypass valve position | ✅ | ✅ |
| Steering power (compressor load) | ✅ | ✅ |
| Edit preset temperatures (e.g. away = 14 °C) | ❌ | ❌ cloud only |
| Manage heating schedule | ❌ | ❌ cloud only |

---

## Entities

> Entity names are in English. When Home Assistant is configured in Dutch (Nederlands), entity names are automatically shown in Dutch.

### Climate (thermostat)

| HA entity | Name | Description |
|-----------|------|-------------|
| `climate.renson_arean_heat_pump` | **Heat pump** | Main thermostat control — shows room temperature, setpoint, preset, HVAC mode, and compressor action. This is the primary object you add to your dashboard. |

Supported thermostat features:

| Feature | Values |
|---------|--------|
| HVAC modes | `heat` / `cool` |
| Preset modes | `schedule` / `away` / `manual` |
| Target temperature range | 10 °C – 30 °C, in 0.5 °C steps |
| Current temperature | Read from the wall thermostat via Modbus |

### Sensors

| HA entity | Name | Description |
|-----------|------|-------------|
| `sensor.renson_arean_steering_power` | **Steering power** | Compressor drive output (0–100 %). A value above 0 means the heat pump is actively heating or cooling. |
| `sensor.renson_arean_bypass_valve` | **Bypass valve** | Bypass valve position — raw gateway dimmer value. Controls the supply temperature mix. |
| `sensor.renson_arean_silent_mode_max_duration` | **Silent mode max duration** | Maximum time (hours) a single silent mode activation runs before switching off automatically. |
| `sensor.renson_arean_silent_mode_start_time` | **Silent mode start time** | Time of day at which recurring silent mode activates (e.g. `22:00`). |
| `sensor.renson_arean_silent_mode_running_time` | **Silent mode running time** | How long the current silent mode activation has been running (hours). Diagnostic — disabled by default. |
| `sensor.renson_arean_energy_source` | **Energy source** | Heat pump energy source as configured in the OpenMotics plugin (e.g. `0_Air_source`). Diagnostic — disabled by default. |
| `sensor.renson_arean_heat_pump_logic_state` | **Heat pump logic state** | Operational state of the `rensonheatpumplogic` plugin (e.g. `Logic`). Diagnostic — disabled by default. |
| `sensor.renson_arean_commissioning_state` | **Commissioning state** | Commissioning state reported by the plugin (e.g. `Preconfigured`). Diagnostic — disabled by default. |

### Switches

| HA entity | Name | Description |
|-----------|------|-------------|
| `switch.renson_arean_silent_mode` | **Silent mode** | Reduces noise from the outdoor unit (compressor / fan). |


### Binary sensors — HVAC outputs

| HA entity | Name | Description |
|-----------|------|-------------|
| `binary_sensor.renson_arean_bathroom_valve` | **Bathroom valve** | Bathroom underfloor heating valve (open/closed). |
| `binary_sensor.renson_arean_three_way_valve` | **Three-way valve** | Switches between the heating circuit and the domestic hot water circuit. |
| `binary_sensor.renson_arean_central_heating_pump` | **Central heating pump** | Central heating circulation pump (running/idle). |
| `binary_sensor.renson_arean_recirculation_pump` | **Recirculation pump** | Hot water recirculation pump (running/idle). |

### Diagnostic binary sensors (disabled by default)

| HA entity | Name | Description |
|-----------|------|-------------|
| `binary_sensor.renson_arean_backup_heater` | **Backup heater** | Read-only: whether the backup electric heater is enabled in the OpenMotics plugin. |
| `binary_sensor.renson_arean_silent_mode_recurring` | **Silent mode recurring** | Read-only: whether the recurring silent mode schedule is active in the OpenMotics plugin. |
| `binary_sensor.renson_arean_gateway_output_0` | **Gateway output 0** | Unknown function — possibly auxiliary boiler relay (230 V). |
| `binary_sensor.renson_arean_gateway_output_5` | **Gateway output 5** | Unknown function. |
| `binary_sensor.renson_arean_gateway_output_7` | **Gateway output 7** | Unknown function. |

Enable these via **Settings → Devices & Services → Renson Arean → entity** once you have identified their purpose.

---

## Preconditions

### Create a local user on the Renson Brain module

The integration authenticates against the **local REST API** of the Brain module. A local user account must exist before you can configure the integration.

**Steps:**

1. **Enable authorization mode** on the Brain module by pressing and holding the **ACTION** and **SETUP** buttons simultaneously for at least 5 seconds. The module will indicate that authorization mode is active.
2. Open a browser and navigate to `https://<brain-module-ip>` (accept the self-signed certificate warning).
3. Log in and create a local user account (username + password). Note the credentials — you will need them during integration setup.

> The Brain module uses a self-signed TLS certificate. The integration handles this automatically — no manual certificate configuration is needed in Home Assistant.

---

## Requirements

- Home Assistant 2026.6 or newer (may work on older versions, although not tested)
- Renson Arean heat pump connected to an **OpenMotics gateway (Brain module)**, firmware v3.13.4
- The gateway must be reachable on your local network (HTTPS, port 443)
- A local user account on the gateway (see [Preconditions](#preconditions))

---

## Installation

### Via HACS (recommended)

1. In Home Assistant, open **HACS → Integrations**
2. Click the three-dot menu → **Custom repositories**
3. Add this repository URL, category: **Integration**
4. Search for **Renson Arean** and install
5. Restart Home Assistant

### Manual

1. Copy the `custom_components/renson_arean/` folder to your HA config directory:
   ```
   <ha-config>/custom_components/renson_arean/
   ```
2. Restart Home Assistant

---

## Configuration

### Initial setup

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **Renson Arean**
3. Enter the gateway details:

| Field | Example | Notes |
|-------|---------|-------|
| IP address or hostname | e.g. `192.168.x.x` | Without `http(s)://` |
| Username | `myuser` | Local gateway user (see Preconditions) |
| Password | `••••••••` | Local gateway user password |

The integration uses the gateway serial number as a unique device identifier, so reconfiguring the IP address does not create a duplicate device.

### Changing the Modbus slave address

The integration communicates with the wall thermostat via Modbus. The default slave address is **41**, which matches the factory default of the RensonThermostat plugin on the OpenMotics gateway.

If your installation uses a different address, you can change it without reinstalling the integration:

1. Go to **Settings → Devices & Services**
2. Find the **Renson Arean** integration and click **Configure**
3. Enter the correct Modbus slave address (1–247)

**Where to find the address:** Open the OpenMotics web interface (`https://<brain-module-ip>`), navigate to **Plugins → RensonThermostat**, and look for the Modbus slave address in the plugin settings.

---

## How it works

The integration communicates directly with the **OpenMotics local REST API** on the gateway — no cloud traffic for any of the supported features. Authentication uses a bearer token (1-hour TTL, auto-renewed).

Setpoint and preset changes are written via **Modbus register writes to the wall thermostat (slave 41 by default)**. The gateway's RensonThermostat plugin picks up the change within ~5 seconds and propagates it to the heat pump logic. The integration applies optimistic state updates so Home Assistant reflects the change immediately.

The coordinator polls all data every **30 seconds** (3 API calls per cycle).

For a full technical description, see [docs/architecture.md](docs/architecture.md).

---

## Known limitations

- **Single thermostat only** — the integration currently supports one wall thermostat (Modbus slave 41, thermostat ID 0). Installations with multiple thermostat zones are not yet supported.
- **Preset temperatures** (e.g. what temperature "away" means in degrees) can only be changed via the Renson One cloud portal — there is no local API endpoint for this in firmware v3.13.4.
- **Heating schedule** management is cloud-only.
- **Water supply temperature** and **outdoor temperature** sensors are not available: the gateway plugin logs do not expose this data in a parseable format in v3.13.4.
- **Bypass valve** is shown as a raw gateway dimmer value; the exact scale (0–100 vs 100–255) is not fully confirmed.

---

## Contributing

Issues and pull requests are welcome. See [docs/development.md](docs/development.md) for the development setup and validation steps.

---

## License

MIT
