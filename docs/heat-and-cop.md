# Heat output, heat energy and COP

## What the integration calculates

Every other device shows what the installation reports. **Heat output and heat energy** are not reported by anything: the integration calculates them from the heat pump's readings. They therefore have a device of their own, *Berekende waarden* (calculated values), so the heat pump device only holds what the heat pump says itself:

| Entity | Name | What it is |
|---|---|---|
| `sensor.calculated_heat_output` | Warmtevermogen | the heat given to the water right now, in kW: flow rate × factor × (flow temperature − return temperature) |
| `sensor.calculated_heat_energy` | Warmte-energie | that heat output added up over time, in kWh. A counter: it keeps its total across restarts |

The factor depends on what the heating circuit is filled with: 1.163 kWh/(m³·K) for plain water, 1.08 for water with glycol. Choose it under [Options](configuration.md#options); the default is water. Both values can be negative or go down for a while: during a defrost, and while cooling, the heat pump takes heat *out* of the water. What the heat pump did while Home Assistant was not running is not counted.

When the heat pump is unreachable, the heat output is unavailable with it, and the counter waits.

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

## How reliable is it?

- **The flow rate and the flow/return assignment are well-supported inferences**, not values Renson names (`function_confidence: assumed`). The strongest evidence for them is precisely this calculation: on a measured cycle it came out at a COP of 3.6–5.8 at 15 °C outside and 40 °C flow, which is what an R290 monobloc should achieve. If you see structurally impossible values (below 1 or above 8 over a whole day), report it.
- **The factor for glycol is an approximation.** 1.08 kWh/(m³·K) is for water with about 30 % glycol. The real value depends on the kind of glycol and the concentration and can differ by a few percent; the COP differs by the same percentage.
- **The heat counter only counts while Home Assistant runs.** After a restart or a connection outage, the heat delivered in the meantime is missing, while your meter kept counting. A period that contains such a gap gives a COP that is too low.
- **Domestic hot water** is included in the heat output as long as it is heated through the same circuit.
- **Do not use mains voltage × current as a substitute for a meter.** That is apparent power: without the power factor it overestimates the consumption, so the COP comes out systematically too low — and in a total that error accumulates.

---

[← Back to the README](../README.md)
