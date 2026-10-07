# Renson Arean dashboard card

Source of the dashboard card `custom:renson-arean-card`: a drawn heat pump with its temperatures,
flow, compressor load and COP around it.

The card has **no dependencies**. There is nothing to install and no `node_modules`: the only tool
needed is Node.js (18 or newer), and only for the tests and for joining the source files.

## Layout

```
frontend/
  src/          the source, one module per concern
  test/         tests, run with Node's built-in test runner
  demo/         a page that shows the card against a simulated Home Assistant
  build.mjs     joins src/ into the one file Home Assistant loads
custom_components/renson_arean/frontend/
  renson-arean-card.js    the built card; committed, because HACS runs no build
```

| Module | What it does |
|---|---|
| `pump.js` | The drawing: geometry, projection, anchor points, fan blades |
| `model.js` | From Home Assistant states to what the card shows; entity roles, units, heat output |
| `stats.js` | COP per day and rolling COP from the long-term statistics |
| `format.js` | Numbers in the user's locale |
| `i18n.js` | The card's own texts, Dutch and English |
| `editor.js` | The visual editor |
| `card.js` | The element itself: layout, rendering, animation |

## Working on the card

```bash
cd frontend
node --test test/     # run the tests
node build.mjs        # write custom_components/renson_arean/frontend/renson-arean-card.js
node build.mjs --check
```

Then open `demo/index.html` in a browser. It needs no server and no Home Assistant, and has
switches for every state the card knows. The last test fails when the committed card is not built
from the current source, so a forgotten build does not go unnoticed.

`build.mjs` is not a bundler. It puts the modules behind each other in dependency order and drops
the `import` and `export` keywords. Two rules follow from that: a module only imports from modules
listed before it in `build.mjs`, and top-level names are unique across modules.

## Configuration

```yaml
type: custom:renson-arean-card
title: Renson warmtepomp          # optional
max_hz: 90                        # optional; the frequency at which all ten bars are lit
quality: detailed                 # optional; "sketch" is a lighter drawing
entities:
  status: sensor.heatpump_operating_state
  silent_mode: binary_sensor.app_rensonheatpumplogic_silent_mode
  outdoor_temp: sensor.heatpump_outside_temperature
  compressor_hz: sensor.heatpump_compressor_frequency
  fan_running: sensor.heatpump_operating_state
  circulation_pump: binary_sensor.heatpump_waterpump_active
  cold_temp: sensor.heatpump_return_temperature
  hot_temp: sensor.heatpump_flow_temperature
  pressure: sensor.hvac_module_in1_pressure
  flow: sensor.heatpump_flow
  voltage: sensor.heatpump_mains_voltage
  current: sensor.heatpump_current
  room_temp: climate.thermostat_0
  setpoint: climate.thermostat_0
  heat_demand: climate.thermostat_0
  # Optional, from your own meter and helpers:
  power: sensor.heat_pump_power
  elec_energy: sensor.heat_pump_energy
  heat_energy: sensor.heat_pump_heat_energy
```

Every role is an entity id, or `{entity: ..., attribute: ...}` to read an attribute. The card
assumes no entity ids: a new card is pre-filled with the entities of this integration that exist,
and each one can be changed.

| Role | Shows | When it is left out |
|---|---|---|
| `status` | Operating state; also decides the cooling mode | a dash |
| `silent_mode` | Row and the moon over the fan; the fan turns slower | a dash |
| `serial`, `operating_hours` | Rows in the information box | row hidden |
| `outdoor_temp`, `compressor_hz` | Above the pump | a dash |
| `fan_running` | Fan turns while this is not off or idle | follows `status` |
| `circulation_pump` | Water flows in the pipes | flows while `flow` is above 0 |
| `cooling_mode` | Red and blue swap sides, "heat" becomes "cooling" | follows `status` |
| `cold_temp`, `hot_temp` | Below the left and right pipe | a dash |
| `pressure`, `flow` | Below the pipes; m³/h is shown with three decimals | a dash |
| `heat_power` | Heat output | computed: flow × 1.163 × ΔT (plain water) |
| `voltage`, `current` | Below "electricity" | a dash |
| `room_temp`, `setpoint`, `heat_demand`, `gas_boiler` | The heat demand box | row hidden |
| `power` | Electrical power | hidden, together with the live COP |
| `cop_now` | Live COP | computed from heat output ÷ `power` while the compressor runs |
| `heat_energy`, `elec_energy` | The energy box | a note that says which one is missing |

A climate entity can fill `room_temp`, `setpoint` and `heat_demand` at once: the card reads the
matching attribute. A value that is temporarily unavailable shows as a grey dash, never as zero.
Tapping a value opens its entity.

### The heat energy counter

The integration supplies flow and temperatures, not an energy counter. Make one with a template
sensor and an integration helper, as described under "Building a COP sensor yourself" in the
[README](../README.md), steps 1 and 3, and point `heat_energy` at the result
(`sensor.heat_pump_heat_energy` in that recipe). `elec_energy` is the kWh counter of your own meter.

The COP figures need long-term statistics, so both counters must have a `state_class`. The helpers
from the recipe have one. COP per day and the rolling COP over 24 hours, 2 months and 12 months are
always total heat ÷ total electricity over the period, never a mean of separate COP values. They
refresh every five minutes.

### Two layouts

The card measures its own width. From 640 px it draws the wide layout, on an 800 × 600 grid
(`LAYOUT` in `card.js`). Below that it draws the stacked layout (`NARROW`): the values in a row
above and below a smaller pump, then the boxes below each other, as high as their rows. A
dashboard section is about 500 px wide and a phone about 400 px, so both get the stacked layout;
the wide layout is for a full-width section or a panel view. In the demo page, `?width=420` shows
the stacked layout.

Neither layout is drawn larger than designed, so the text always has Home Assistant's own sizes
and the pump keeps its proportion to it. The stacked layout is as wide as the card: the pump
stays the same size in the middle and the boxes and the chart take the extra width. The wide
layout stops growing at 800 px and is centred in a wider card. Only a card narrower than the
design (below 400 px stacked, 640 to 800 px wide) is scaled down as a whole.

### How the integration serves the card

`async_setup` in `__init__.py` serves this folder at `/renson_arean` and adds the card to the
frontend with a hash of the file in the URL, so a browser fetches every new build instead of
reusing a cached one.

### Colours

The drawing uses its own variables, which a theme can override: `--wp-cold`, `--wp-hot`,
`--wp-elec`, `--wp-gold`, `--wp-green` and `--wp-flame`. Everything else follows the Home Assistant
theme.

## Not built yet

- Defrost, a fault or offline state, and hot water are not designed yet.
