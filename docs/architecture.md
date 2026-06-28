# Technical Architecture

## System overview

The Renson Arean heat pump is controlled via an **OpenMotics gateway (Brain module, firmware v3.13.4)**. The gateway runs a layered plugin architecture on a shared Modbus RTU bus and exposes a local HTTPS REST API.

```
┌──────────────────────────────────────────────────────────────┐
│                    RENSON ONE CLOUD (optional)               │
│  Preset temperatures, heating schedule, weather API          │
└──────────────────────┬───────────────────────────────────────┘
                       │ HTTPS (optional)
┌──────────────────────▼───────────────────────────────────────┐
│         OPENMOTICS GATEWAY  192.168.178.36:443               │
│                   firmware v3.13.4                           │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐    │
│  │          OpenMotics thermostat module                │    │
│  │   Group 1 "Zone 0"  /  Thermostat 0                  │    │
│  │   actual: 30.0°C  setpoint: 18.0°C  preset: manual   │    │
│  └──────────┬────────────────────────┬──────────────────┘    │
│             │ feeds actual temp      │ delivers setpoint      │
│  ┌──────────▼──────────┐  ┌─────────▼──────────────────┐    │
│  │  RensonThermostat   │  │  rensonheatpumplogic        │    │
│  │  plugin  v1.5.1     │  │  plugin  v2025.10.7         │    │
│  │  polls slave 41     │  │  hysteresis: -0.5 / 0.0°C  │    │
│  │  interval: 5 sec    │  │  silent mode, water temp    │    │
│  └──────────▲──────────┘  └─────────┬──────────────────┘    │
│             │                        │                        │
│      Modbus RTU bus (shared, serial RS-485)                   │
│             │                        ▼                        │
│  ┌──────────┴──────────┐  ┌──────────────────────────────┐   │
│  │  Wall thermostat    │  │  RensonHeatPumpR290           │   │
│  │  Modbus slave 41    │  │  plugin  v0.5.6               │   │
│  │  reg 3:  preset     │  │  Modbus slave 1               │   │
│  │  reg 13: temp       │  └──────────┬───────────────────┘   │
│  │  reg 20: setpoint   │             │ Modbus RTU             │
│  └─────────────────────┘  ┌──────────▼───────────────────┐   │
│                           │  Renson Arean 5kW            │   │
└───────────────────────────┤  Modbus slave 1              ├───┘
                            └──────────────────────────────┘
```

---

## Gateway software components

| Component | Version | Role |
|-----------|---------|------|
| OpenMotics firmware | 3.13.4 (master 1.1.16) | Gateway OS + REST API |
| RensonThermostat plugin | 1.5.1 | Wall thermostat interface (slave 41) |
| rensonheatpumplogic plugin | 2025.10.7 | Control logic, silent mode |
| RensonHeatPumpR290 plugin | 0.5.6 | Heat pump Modbus interface (slave 1) |

---

## Authentication

```
GET /login?username=<user>&password=<pass>
  → {"token": "<bearer>", "success": true}

Token TTL: 1 hour
Auth method: query parameter ?token=<token>  (no Authorization header)
SSL: self-signed certificate — ssl verification disabled
```

The integration auto-renews the token 5 minutes before expiry.

---

## Read paths (coordinator poll, every 30 seconds)

| Endpoint | Data |
|----------|------|
| `GET /get_thermostat_group_status` | Room temperature, setpoint, preset, HVAC mode, steering power |
| `GET /get_output_status` | All 8 gateway outputs (valves, pumps, bypass) |
| `GET /plugins/rensonheatpumplogic/get_config` | Silent mode state |

---

## Write paths (all confirmed working locally, tested 2026-06-25)

| Action | Endpoint | Notes |
|--------|----------|-------|
| Set setpoint | `GET /write_modbus_register?slaveaddress=41&registeraddress=20&value=<temp×10>` | 21°C → value=210 |
| Set preset | `GET /write_modbus_register?slaveaddress=41&registeraddress=3&value=0\|1\|5` | 0=klokprogramma, 1=afwezig, 5=handmatig |
| Set HVAC mode | `GET /set_thermostat_group?thermostat_group_id=1&mode=heating\|cooling` | |
| Set silent mode | `GET /plugins/rensonheatpumplogic/set_config?config={...}` | Reads current config, patches silent_mode field |

### Setpoint write path (detail)

```
HA sets 21°C
  → GET /write_modbus_register?slaveaddress=41&registeraddress=20&value=210
  → Gateway writes to Modbus slave 41 register 20
  → (~5 sec) RensonThermostat plugin detects change
  → OpenMotics thermostat module: setpoint updated to 21.0°C
  → rensonheatpumplogic: compares room temp vs new setpoint
  → RensonHeatPumpR290: drives heat pump accordingly
```

**Latency:** ~5 seconds (RensonThermostat plugin poll cycle). The integration applies optimistic state updates immediately after writing.

---

## Wall thermostat register map (Modbus slave 41)

| Register | Direction | Value | Meaning |
|----------|-----------|-------|---------|
| 3 | HA writes | 0 | Preset: klokprogramma (auto / clock program) |
| 3 | HA writes | 1 | Preset: afwezig (away) |
| 3 | HA writes | 5 | Preset: handmatig (manual override) |
| 13 | Read | temp × 10 | Room temperature (raw sensor) |
| 20 | HA writes | temp × 10 | Heating setpoint |

---

## Gateway outputs

| Output ID | Name | Type | Function |
|-----------|------|------|----------|
| 0 | Gateway uitgang 0 | Relay | Unknown — possibly auxiliary boiler relay |
| 1 | Badkamerventiel | Relay | Bathroom underfloor heating valve |
| 2 | Driewegklep | Relay | Heating / DHW circuit switch valve |
| 3 | CV-pomp | Relay | Heating circulation pump |
| 4 | Recirculatiepomp | Relay | Hot water recirculation pump |
| 5 | Gateway uitgang 5 | Relay | Unknown |
| 6 | Bypass-klep | Dimmer | Mixing valve for supply temperature control |
| 7 | Gateway uitgang 7 | — | Unknown (possibly bypass sensor input) |

---

## Known constraints

| ID | Constraint |
|----|------------|
| CN-01 | No direct Modbus RTU access — bus is continuously occupied by the three plugins (~5 sec cycle). Concurrent external access causes frame collisions. |
| CN-02 | No local endpoint to change preset temperatures (e.g. away = 14°C) — cloud only in v3.13.4. |
| CN-03 | No local endpoint for heating schedule — cloud only in v3.13.4. |
| CN-04 | Auth token valid for 1 hour — renewed automatically by the integration. |
| CN-05 | Self-signed TLS certificate — certificate validation disabled (`ssl=False`). |
| CN-06 | `get_plugin_logs` returns only text strings — water supply temperature and outdoor temperature are not available in parseable form in v3.13.4. |

---

## Verified operation without cloud (tested 2026-06-25)

All local features remain fully functional when the gateway's internet connection is blocked. The heating schedule and preset temperature values (set via Renson One) are retained locally and continue to work. Only changing those values requires the cloud.
