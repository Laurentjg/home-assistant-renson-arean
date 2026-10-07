# The devices you will see

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

Measured values on this device — system water temperature and system pressure — come from the log of `rensonheatpumplogic`, not from the gateway. The tank and recirculation sensors (T1, T2, T4) exist as entities but are disabled unless your installation has domestic hot water or recirculation switched on. See [A note on the measured values](measured-values.md).

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

The factor depends on what the heating circuit is filled with: 1.163 kWh/(m³·K) for plain water, 1.08 for water with glycol. Choose it under [Options](configuration.md#options); the default is water. Both values can be negative or go down for a while: during a defrost, and while cooling, the heat pump takes heat *out* of the water. What the heat pump did while Home Assistant was not running is not counted.

When the heat pump is unreachable, the heat output is unavailable with it, and the counter waits.

---

[← Back to the README](../README.md)
