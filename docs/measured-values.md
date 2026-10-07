# The measured values

The heat pump's readings and the HVAC module's sensor inputs are **not offered by the gateway API**. They exist only in the log lines the `rensonheatpumplogic` app writes, as unnamed lists of numbers. This integration reads them there, and is honest about what that costs:

- **They can be empty after a restart.** The app only logs a value when it *changes*. If a temperature holds steady for an hour, nothing is written for an hour. That is not a bug and polling faster does not help.
- **They go unavailable when the app updates.** The meaning of each position is tied to a specific app version — the layout demonstrably changed between two versions in ten weeks. On an unfamiliar version these entities report nothing rather than a wrong number.
- **Some of them are still being confirmed.** Every entity carries a `function_confidence` attribute. Where it says `assumed`, the mapping is a well-supported inference that has not been verified against the installation yet.

Every position of every log array is also published under a neutral name — `HP_UNIT/hp1 waarde 17`, as `sensor.ssr_hp_unit_hp1_17` — as a diagnostic sensor, so the remaining meanings can be established by correlating history.

## Long-term statistics

Home Assistant keeps long-term statistics forever, even after the regular history is purged. This integration deliberately keeps them for only a few quantities — the ones that tell you, a year from now, whether the system still performs as it does today:

- outside temperature
- heat pump flow and return temperature
- compressor frequency
- system pressure
- heat energy, as a counter

Settings, voltages and diagnostic values get none. Neither does the heat output: the heat energy counter holds the same information, and the heat delivered over any hour, day or month follows from it. The integration computes **no COP and no electrical consumption** itself: the heat pump only reports voltage and current, from which no reliable consumption follows. A dedicated energy meter does that better — and with one, you can calculate the COP yourself, see [Heat output, heat energy and COP](heat-and-cop.md).

---

[← Back to the README](../README.md)
