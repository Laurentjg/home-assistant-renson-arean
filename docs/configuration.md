# Installation and configuration

## Requirements

- Home Assistant 2026.6 or newer
- A Renson Arean heat pump on an OpenMotics gateway (Brain module), gateway firmware 3.14.0 or comparable
- The gateway reachable on your local network over HTTPS
- A local user account on the gateway

The integration has **no external dependencies**. `requirements` in the manifest is empty and stays that way: a library that is not there cannot carry a vulnerability.

## Create a local user on the Renson Brain module

The integration authenticates against the **local REST API** of the Brain module, so a local user account has to exist first.

1. **Enable authorization mode** by pressing and holding **ACTION** and **SETUP** together for at least 5 seconds. The module indicates that authorization mode is active.
2. Browse to `https://<brain-module-ip>` and accept the self-signed certificate warning.
3. Log in and create a local user account. Note the credentials.

> The Brain module uses a self-signed TLS certificate. Certificate verification is therefore off by default; you can switch it on in the options if your gateway presents a certificate your Home Assistant trusts.

## Installation

### Via HACS

1. **HACS → Integrations**
2. Three-dot menu → **Custom repositories**
3. Add this repository, category **Integration**
4. Search for **Renson Arean**, install, restart Home Assistant

### Manual

Copy `custom_components/renson_arean/` into `<ha-config>/custom_components/` and restart.

## Setup

**Settings → Devices & Services → Add Integration → Renson Arean**, then enter the host (without `http(s)://`), username and password.

The gateway reports no serial number, so the integration cannot tell two identical gateways apart automatically. If you enter a host that is already configured, it warns you rather than silently refusing — adding a genuine second installation stays possible.

## Options

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

[← Back to the README](../README.md)
