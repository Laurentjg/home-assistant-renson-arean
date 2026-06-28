# Development Guide

## Project structure

```
renson/
├── custom_components/
│   └── renson_arean/
│       ├── __init__.py          # async_setup_entry + async_unload_entry
│       ├── manifest.json        # Integration metadata
│       ├── config_flow.py       # UI setup + reauth flow
│       ├── coordinator.py       # DataUpdateCoordinator (30-second poll)
│       ├── api.py               # RensonApiClient — all gateway calls
│       ├── entity.py            # RensonAreanEntity base (shared DeviceInfo)
│       ├── climate.py           # ClimateEntity (main control entity)
│       ├── sensor.py            # SensorEntity (steering power, bypass valve)
│       ├── switch.py            # SwitchEntity (silent mode)
│       ├── binary_sensor.py     # BinarySensorEntity (HVAC outputs)
│       ├── diagnostics.py       # Diagnostics with password redaction
│       ├── const.py             # Constants, mappings
│       ├── strings.json         # Config flow text keys
│       ├── translations/
│       │   └── en.json          # English translations
│       └── icon.png             # 256×256 PNG integration icon
├── docs/
│   ├── architecture.md          # System architecture and API reference
│   └── development.md           # This file
├── hacs.json                    # HACS metadata
└── README.md                    # User-facing documentation
```

---

## Architecture: data flow

```
Entities (climate.py, sensor.py, ...)
    ↓  read only from coordinator.data
RensonCoordinator  (coordinator.py)
    ↓  calls API, handles errors
RensonApiClient  (api.py)
    ↓  aiohttp, async, ssl=False
OpenMotics Gateway  https://<host>:443
```

**Rule:** Entities never call the API directly. All data flows through the coordinator.

---

## Coordinator poll cycle

Per 30-second poll, three API calls are made:

1. `GET /get_thermostat_group_status` → room temp, setpoint, preset, HVAC mode, steering power
2. `GET /get_output_status` → all 8 gateway outputs
3. `GET /plugins/rensonheatpumplogic/get_config` → silent mode state

All results are stored in a single `RensonData` dataclass. Entities read exclusively from this.

---

## Error handling

| Exception | When | Effect |
|-----------|------|--------|
| `ConfigEntryNotReady` | Gateway unreachable at setup | HA retries with exponential backoff |
| `ConfigEntryAuthFailed` | 401 response | HA triggers reauth flow |
| `UpdateFailed` | Connection error during poll | All entities become unavailable; retry at next interval |

---

## Deploying to Home Assistant

Use `rsync` to avoid `__pycache__` permission issues:

```bash
rsync -av --exclude='__pycache__' --exclude='*.pyc' \
  ./custom_components/ \
  ubuntu@<ha-host>:~/ha_config/custom_components/
```

Restart Home Assistant after each deployment.

---

## Validation

### Syntax check
```bash
python3 -m py_compile custom_components/renson_arean/*.py
```

### JSON validation
```bash
python3 -m json.tool custom_components/renson_arean/manifest.json
python3 -m json.tool custom_components/renson_arean/strings.json
python3 -m json.tool custom_components/renson_arean/translations/en.json
```

### Security scan
```bash
pip install bandit
bandit -r custom_components/renson_arean/
```

### hassfest (before HACS publication)

hassfest is the official HA validation tool. It requires a local clone of `home-assistant/core`:

```bash
git clone https://github.com/home-assistant/core.git
cd core
python -m script.hassfest --integration-path /path/to/renson/custom_components/renson_arean
```

Run hassfest before publishing to HACS or submitting to HA Core.

---

## Debug logging

Add to `configuration.yaml`:

```yaml
logger:
  default: warning
  logs:
    custom_components.renson_arean: debug
```

Or set at runtime: **Settings → System → Logs → Set level** → `custom_components.renson_arean` → DEBUG.

The API client logs raw gateway responses at DEBUG level for each endpoint.

---

## Known limitations and future work

- **Water supply temperature and outdoor temperature**: not available from `get_plugin_logs` in firmware v3.13.4 (returns text strings only). May become available in a future firmware version.
- **Bypass valve scale**: the gateway reports a raw dimmer value; the exact mapping to a physical percentage is not fully confirmed.
- **Preset temperatures**: changing what temperature each preset uses (e.g. "afwezig" = 14°C) requires the Renson One cloud — no local endpoint exists in v3.13.4.
- **Heating schedule**: cloud-only in v3.13.4.
