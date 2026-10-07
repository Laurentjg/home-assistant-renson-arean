# How it works, and what it cannot do

## How it works

The integration talks to the local OpenMotics REST API. Authentication uses a token with a one-hour lifetime, renewed automatically and kept in memory only.

There is no single polling interval. Each source is polled at a rate matching how fast it actually changes, which keeps the thermostat current without re-reading the topology every ten seconds.

Setpoint and preset changes are written as Modbus register writes to the wall thermostat, exactly as the previous version did. Because the app polls that thermostat every 5 seconds, confirmation cannot arrive sooner — so the card shows your change immediately, the gateway is asked again at 2, 5, 8, 12 and 20 seconds, and a poll carrying the old value cannot undo what you just set. If confirmation never comes, the gateway value takes over again and one warning is logged.

There is deliberately **no service to write an arbitrary Modbus register**. As a service that would be a remote arbitrary write onto the installation bus. Writing is limited to the setpoint and the preset, both range-checked before they are sent.

## Known limitations

- **The two heat pump apps are read-only.** Silent mode and the backup heater are shown but cannot be switched. Changing them means rewriting a whole configuration block, which can collide with the app itself, and a wrong control parameter costs comfort or heat pump life. Set them in OpenMotics or the Renson One app instead.
- **Preset temperatures and the heating schedule are cloud-only.** They are stored locally on the Brain and keep working without internet; only *changing* them needs Renson One.
- **No energy metering.** The P1 port cannot be used alongside the expansion bus, and the expansion bus carries the Modbus link to the heat pump and thermostat. This is a property of the hardware, not an omission. A separate P1 Concentrator module would be needed.
- **The bypass position is a state, not a percentage.** All eight outputs report a constant dimmer value, so there is no percentage to read. What the log does report is `Open` or `Closed`.
- **A sensor drifting out of true cannot be detected.** An NTC is a passive resistor with no error signal; only a disconnected or short-circuited sensor is recognisable. A perfectly ordinary reading, 0 °C included, is never discarded.
- **Removing and re-adding the integration breaks history**, long-term statistics included. Identifiers are rooted on the config entry, because the gateway offers no stable hardware id. Every alternative fails at a moment you cannot see coming; this one fails only when you do it yourself.

---

[← Back to the README](../README.md)
