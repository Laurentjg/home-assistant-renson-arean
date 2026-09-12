"""Constants and static tables for the Renson Arean integration.

This module is deliberately free of Home Assistant imports so that the static
tables and mappings can be tested without a Home Assistant runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

DOMAIN = "renson_arean"
MANUFACTURER = "Renson"

PLATFORMS = ["binary_sensor", "button", "climate", "sensor"]

CONFIG_ENTRY_VERSION = 2

# --- Config entry keys (§5.1) ------------------------------------------------

CONF_HOST = "host"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_VERIFY_SSL = "verify_ssl"
CONF_THERMOSTAT_SLAVE = "thermostat_slave"
CONF_THERMOSTAT_CONNECTED_TO = "thermostat_connected_to"
CONF_INTERVAL_THERMOSTAT = "interval_thermostat"
CONF_INTERVAL_STATE = "interval_state"
CONF_INTERVAL_CONFIG = "interval_config"
CONF_INTERVAL_TOPOLOGY = "interval_topology"

DEFAULT_THERMOSTAT_SLAVE = 41
DEFAULT_VERIFY_SSL = False

# Per-source intervals (§6.2). The lower bounds protect the Modbus bus (CN-01)
# and keep the half-megabyte log response from being re-parsed pointlessly.
DEFAULT_INTERVAL_THERMOSTAT = timedelta(seconds=10)
DEFAULT_INTERVAL_STATE = timedelta(seconds=30)
DEFAULT_INTERVAL_CONFIG = timedelta(minutes=5)
DEFAULT_INTERVAL_TOPOLOGY = timedelta(minutes=15)

MIN_INTERVAL_THERMOSTAT = 5
MIN_INTERVAL_STATE = 30
MIN_INTERVAL_CONFIG = 60
MIN_INTERVAL_TOPOLOGY = 300

# via_device of the thermostat device — the wiring differs per installation and
# is not derivable from the API (V-13).
CONNECTED_TO_BRAIN = "brain"
CONNECTED_TO_HVAC = "hvac"
DEFAULT_CONNECTED_TO = CONNECTED_TO_BRAIN

# --- Sources (§5.0) ----------------------------------------------------------

SOURCE_GATEWAY_CORE = "gateway:core"


def source_app_config(app: str) -> str:
    """Source id for `plugins/<app>/get_config`."""
    return f"app:{app}:config"


def source_app_log(app: str) -> str:
    """Source id for the log lines of an app (D-14)."""
    return f"app:{app}:log"


def source_app_runtime(app: str) -> str:
    """Source id for the version and status an app reports via get_plugins."""
    return f"app:{app}:runtime"


# The device underneath a healthy app (D-17). There is no status field for it
# anywhere; the evidence is freshness. While the app keeps logging arrays that
# can only come from the monobloc, the Modbus coupling demonstrably works.
SOURCE_HARDWARE_HEATPUMP = "hardware:heatpump"
HEATPUMP_ARRAYS = ("HP_UNIT/hp1", "HP_GLOBAL/0")
# Both arrays appear about once a minute; three silent polls is itself abnormal.
# Shorter makes the entity restless, longer makes it slow (§5.0).
HEATPUMP_FRESHNESS = timedelta(minutes=3)


# --- Apps (§2.2) -------------------------------------------------------------
#
# Apps are discovered at runtime (P-05); these names only bind the per-app
# entity sets of §5.5–5.7 to the apps they were written for. An app that is not
# in this list is still registered as a device with its version and status.

APP_THERMOSTAT = "RensonThermostat"
APP_LOGIC = "rensonheatpumplogic"
APP_HEATPUMP = "RensonHeatPumpR290"

APP_MODELS: dict[str, str] = {
    APP_THERMOSTAT: "Thermostaat-app",
    APP_LOGIC: "Regellogica-app",
    APP_HEATPUMP: "Modbus-driver warmtepomp",
}

# --- Presets (§5.4) ----------------------------------------------------------

PRESET_SCHEDULE = "schedule"
PRESET_AWAY = "away"
PRESET_MANUAL = "manual"

# Modbus slave 41, register 3
PRESET_TO_REGISTER: dict[str, int] = {
    PRESET_SCHEDULE: 0,
    PRESET_AWAY: 1,
    PRESET_MANUAL: 5,
}

# Gateway preset name → HA preset name. `override` is mapped onto `manual`;
# that is an open decision, not a settled one (V-18).
OM_PRESET_TO_HA: dict[str, str] = {
    "auto": PRESET_SCHEDULE,
    "away": PRESET_AWAY,
    "manual": PRESET_MANUAL,
    "override": PRESET_MANUAL,
}

# Written values are validated against these bounds before they reach the bus
# (SEC-12).
SETPOINT_MIN = 10.0
SETPOINT_MAX = 30.0

# --- Channel table of the HVAC module (§2.1, §2.3, §4.4) ---------------------

CHANNEL_RELAY_DRY = "relay_dry_contact"
CHANNEL_RELAY_230V = "relay_230v"
CHANNEL_ANALOG_OUT = "analog_out_0_10v"
CHANNEL_ANALOG_IN = "analog_in_0_10v"
CHANNEL_NTC = "ntc_5k"

WIRED_YES = "true"
WIRED_NO = "false"
WIRED_UNKNOWN = "unknown"

CONFIDENCE_CONFIRMED = "confirmed"
CONFIDENCE_ASSUMED = "assumed"
CONFIDENCE_UNKNOWN = "unknown"

SHARED_SUPPLY_R3_R5 = "R3–R5 delen L en N, af te zekeren op 16 A"

# The technical sheet states: "Wanneer meerdere uitgangen in motor configuratie
# worden geplaatst kan slechts 1 van de uitgangen tegelijkertijd aan staan."
# Whether a given channel is wired in motor configuration is an installation
# property that the gateway does not report, so no channel claims a group here.
INTERLOCK_NOTE = (
    "Staan meerdere uitgangen in motorconfiguratie, dan mag er slechts één "
    "tegelijk aan staan (technische fiche HVAC module)."
)


@dataclass(frozen=True)
class HvacChannel:
    """One physical channel of the HVAC module.

    `key` is the stable half: it feeds the unique_id and the entity_id and
    never changes. `default_name` is the label half and may improve per
    release (§4.3, P-11).
    """

    key: str
    channel: str
    direction: str
    channel_type: str
    electrical: str
    connector: str
    default_name: str
    device_class: str | None = None
    hvac_config_key: str | None = None
    shared_supply: str | None = None
    signal_range: str = "unknown"
    wired: str = WIRED_UNKNOWN
    diagnostic: bool = False
    enabled_default: bool = True
    note: str | None = None
    # The subsystem an input belongs to; while it is off the entity is created
    # but disabled by default (§5.3, I-15).
    subsystem: str | None = None


SUBSYSTEM_DHW = "dhw"
SUBSYSTEM_RECIRCULATION = "recirculation"

# Output id (as reported by get_output_status) → channel.
HVAC_OUTPUTS: dict[int, HvacChannel] = {
    0: HvacChannel(
        key="r1",
        channel="R1",
        direction="output",
        channel_type=CHANNEL_RELAY_DRY,
        electrical="spanningsvrij contact, max. 6 A @ 230 VAC",
        connector="4×4-polig, type 1",
        default_name="Zone 1-afsluiter",
        device_class="opening",
        hvac_config_key="zone_1_shutoff_valve",
        wired=WIRED_YES,
    ),
    1: HvacChannel(
        key="r2",
        channel="R2",
        direction="output",
        channel_type=CHANNEL_RELAY_DRY,
        electrical="spanningsvrij contact, max. 6 A @ 230 VAC",
        connector="4×4-polig, type 1",
        default_name="Badkamerventiel",
        device_class="opening",
        hvac_config_key="output_bathroom_valve",
        wired=WIRED_YES,
    ),
    2: HvacChannel(
        key="r3",
        channel="R3",
        direction="output",
        channel_type=CHANNEL_RELAY_230V,
        electrical="230 VAC schakelend, max. 6 A",
        connector="4×4-polig, type 3",
        default_name="Driewegklep",
        device_class="opening",
        hvac_config_key="output_3way_valve",
        shared_supply=SHARED_SUPPLY_R3_R5,
        wired=WIRED_YES,
    ),
    3: HvacChannel(
        key="r4",
        channel="R4",
        direction="output",
        channel_type=CHANNEL_RELAY_230V,
        electrical="230 VAC schakelend, max. 6 A",
        connector="4×4-polig, type 3",
        default_name="CV-pomp",
        device_class="running",
        hvac_config_key="output_pump",
        shared_supply=SHARED_SUPPLY_R3_R5,
        wired=WIRED_YES,
    ),
    4: HvacChannel(
        key="r5",
        channel="R5",
        direction="output",
        channel_type=CHANNEL_RELAY_230V,
        electrical="230 VAC schakelend, max. 6 A",
        connector="4×4-polig, type 3",
        default_name="Recirculatiepomp",
        device_class="running",
        hvac_config_key="output_recirculation",
        shared_supply=SHARED_SUPPLY_R3_R5,
        wired=WIRED_UNKNOWN,
        note="Subsysteem uit: has_recirculation staat op Off.",
    ),
    5: HvacChannel(
        key="out1",
        channel="OUT1",
        direction="output",
        channel_type=CHANNEL_ANALOG_OUT,
        electrical="0/1-10 V analoog, max. 10 mA",
        connector="11-polig, type 2",
        default_name="OUT1",
        wired=WIRED_UNKNOWN,
        diagnostic=True,
        enabled_default=False,
        note="Functie onbekend: hvac_config wijst geen functie aan dit kanaal toe.",
    ),
    6: HvacChannel(
        key="out2",
        channel="OUT2",
        direction="output",
        channel_type=CHANNEL_ANALOG_OUT,
        electrical="0/1-10 V analoog, max. 10 mA",
        connector="11-polig, type 2",
        default_name="Zone 0-dummyklep",
        device_class="opening",
        wired=WIRED_YES,
        diagnostic=True,
        note="In OpenMotics geconfigureerd als 'Dummy Zone 0', type 1 (valve).",
    ),
    7: HvacChannel(
        key="out3",
        channel="OUT3",
        direction="output",
        channel_type=CHANNEL_ANALOG_OUT,
        electrical="0/1-10 V analoog, max. 10 mA",
        connector="11-polig, type 2",
        default_name="Bypass-klep",
        device_class="opening",
        hvac_config_key="out_3_bypass_sensor",
        wired=WIRED_YES,
    ),
}

# Input id (as used inside hvac_config) → channel. The gateway does not expose
# them as sensors (V-03/V-04); T3, IN1 and IN2 have a position in HP_HVAC/0.
# T1, T2 and T4 have none — all twelve positions are taken — but they still get
# an entity that stays unavailable, because an installation with hot water or
# recirculation in use may well log a longer array (I-15).
HVAC_INPUTS: dict[int, HvacChannel] = {
    0: HvacChannel(
        key="t1",
        channel="T1",
        direction="input",
        channel_type=CHANNEL_NTC,
        electrical="NTC 5K",
        connector="type 2",
        default_name="Boilertank boven",
        device_class="temperature",
        hvac_config_key="input_tank_top",
        signal_range="n.v.t.",
        wired=WIRED_UNKNOWN,
        note="Subsysteem uit: dhw_status staat op Disabled.",
        subsystem=SUBSYSTEM_DHW,
    ),
    1: HvacChannel(
        key="t2",
        channel="T2",
        direction="input",
        channel_type=CHANNEL_NTC,
        electrical="NTC 5K",
        connector="type 2",
        default_name="Boilertank onder",
        device_class="temperature",
        hvac_config_key="input_tank_bottom",
        signal_range="n.v.t.",
        wired=WIRED_UNKNOWN,
        note="Subsysteem uit: dhw_status staat op Disabled.",
        subsystem=SUBSYSTEM_DHW,
    ),
    2: HvacChannel(
        key="t3",
        channel="T3",
        direction="input",
        channel_type=CHANNEL_NTC,
        electrical="NTC 5K",
        connector="type 2",
        default_name="Systeemwatertemperatuur",
        device_class="temperature",
        hvac_config_key="temperature_sensor",
        signal_range="n.v.t.",
        wired=WIRED_YES,
    ),
    3: HvacChannel(
        key="t4",
        channel="T4",
        direction="input",
        channel_type=CHANNEL_NTC,
        electrical="NTC 5K",
        connector="type 2",
        default_name="Recirculatietemperatuur",
        device_class="temperature",
        hvac_config_key="recirculation_sensor",
        signal_range="n.v.t.",
        wired=WIRED_UNKNOWN,
        note="Subsysteem uit: has_recirculation staat op Off.",
        subsystem=SUBSYSTEM_RECIRCULATION,
    ),
    4: HvacChannel(
        key="in1",
        channel="IN1",
        direction="input",
        channel_type=CHANNEL_ANALOG_IN,
        electrical="0-10 V analoog, ingangsbeveiliging tot 12 VDC",
        connector="11-polig, type 2",
        default_name="Systeemdruk 1",
        device_class="pressure",
        hvac_config_key="pressure_sensor_ai1",
        signal_range="unknown",
        wired=WIRED_YES,
    ),
    5: HvacChannel(
        key="in2",
        channel="IN2",
        direction="input",
        channel_type=CHANNEL_ANALOG_IN,
        electrical="0-10 V analoog, ingangsbeveiliging tot 12 VDC",
        connector="11-polig, type 2",
        default_name="Systeemdruk 2",
        device_class="pressure",
        hvac_config_key="pressure_sensor_ai2",
        signal_range="unknown",
        wired=WIRED_YES,
    ),
}

HVAC_MODULE_MODEL = "HVAC module (30076)"
BRAIN_MODULE_MODEL = "Brain module (33108)"
HEATPUMP_MODEL = "Arean 5 kW"

# --- SSR log arrays (D-14, V-16) --------------------------------------------
#
# `rensonheatpumplogic` writes its system status reports as unnamed positional
# arrays. Which position carries which channel is NOT established (V-16), so
# every position is published under a neutral name and nothing is interpreted.
# The lengths below were observed on the app version named here; an array with
# a different length yields nothing rather than a guess (D-14 b/d).

SSR_APP_VERSION = "2026.6.4"

SSR_ARRAY_LENGTHS: dict[str, int] = {
    "HP_HVAC/0": 12,
    "HP_UNIT/hp1": 25,
    "HP_THERMOSTAT/0": 4,
}


@dataclass(frozen=True)
class SsrPosition:
    """One position of an SSR array that has been given a meaning.

    `confidence` is the honest half: `confirmed` means the app named the value
    itself in a log line, `assumed` means it was inferred from the measurements
    and still needs a check (see non-public/design/open-issues.md).
    """

    index: int
    key: str
    name: str
    confidence: str
    device_class: str | None = None
    unit: str | None = None
    diagnostic: bool = False
    # None unless there is an answer to "which decision do I take on this series
    # in half a year" (§5.9).
    state_class: str | None = None


STATE_CLASS_MEASUREMENT = "measurement"


@dataclass(frozen=True)
class SsrArray:
    """One SSR array as `rensonheatpumplogic` writes it."""

    key: str
    slug: str
    length: int
    positions: tuple[SsrPosition, ...] = ()

    def position(self, index: int) -> SsrPosition | None:
        """Return the meaning of `index`, if one is established."""
        for position in self.positions:
            if position.index == index:
                return position
        return None


# The value a Modbus device returns for "not available": 0x7FFF / 10. The app
# validates ranges itself and logs it as out of bounds (S-01, §7.3).
MODBUS_SENTINEL = 3276.7

# The voltage/pressure pairs below are not guesses: on 2026-06-26 the app named
# them itself — `pressure_cv_in1: 1.64 bar` and `voltage_dhw_in2: None V` — next
# to the array `[..., 4.1, None, 1.64, None]`. The scaling confirms it twice
# over: 4.1 V / 10 V × 4 bar (`type_sensor_ai1`) = 1.64 bar exactly, and
# 2.61 V likewise gives the 1.04 bar measured on 2026-09-06.
SSR_ARRAYS: dict[str, SsrArray] = {
    "HP_HVAC/0": SsrArray(
        key="HP_HVAC/0",
        slug="hp_hvac_0",
        length=12,
        positions=(
            SsrPosition(
                index=7,
                key="t3_temperature",
                name="Systeemwatertemperatuur",
                confidence=CONFIDENCE_ASSUMED,
                device_class="temperature",
                unit="°C",
            ),
            SsrPosition(
                index=8,
                key="in1_voltage",
                name="Ingangsspanning IN1",
                confidence=CONFIDENCE_CONFIRMED,
                device_class="voltage",
                unit="V",
                diagnostic=True,
            ),
            SsrPosition(
                index=9,
                key="in2_voltage",
                name="Ingangsspanning IN2",
                confidence=CONFIDENCE_CONFIRMED,
                device_class="voltage",
                unit="V",
                diagnostic=True,
            ),
            SsrPosition(
                index=10,
                key="in1_pressure",
                name="Systeemdruk 1",
                confidence=CONFIDENCE_CONFIRMED,
                device_class="pressure",
                unit="bar",
                state_class=STATE_CLASS_MEASUREMENT,
            ),
            SsrPosition(
                index=11,
                key="in2_pressure",
                name="Systeemdruk 2",
                confidence=CONFIDENCE_CONFIRMED,
                device_class="pressure",
                unit="bar",
            ),
        ),
    ),
    "HP_UNIT/hp1": SsrArray(
        key="HP_UNIT/hp1",
        slug="hp_unit_hp1",
        length=25,
        positions=(
            # 0 at rest, 30–72 while running, pinned at 30 = the lower
            # modulation limit for minutes on end (2026-09-09).
            SsrPosition(
                index=12,
                key="compressor_frequency",
                name="Compressorfrequentie",
                confidence=CONFIDENCE_ASSUMED,
                device_class="frequency",
                unit="Hz",
                state_class=STATE_CLASS_MEASUREMENT,
            ),
            SsrPosition(
                index=18,
                key="flow_temperature",
                name="Aanvoertemperatuur",
                confidence=CONFIDENCE_ASSUMED,
                device_class="temperature",
                unit="°C",
                state_class=STATE_CLASS_MEASUREMENT,
            ),
            SsrPosition(
                index=19,
                key="return_temperature",
                name="Retourtemperatuur",
                confidence=CONFIDENCE_ASSUMED,
                device_class="temperature",
                unit="°C",
                state_class=STATE_CLASS_MEASUREMENT,
            ),
            SsrPosition(
                index=21,
                key="dhw_temperature",
                name="Tapwatertemperatuur",
                confidence=CONFIDENCE_CONFIRMED,
                device_class="temperature",
                unit="°C",
            ),
            SsrPosition(
                index=23,
                key="mains_voltage",
                name="Netspanning",
                confidence=CONFIDENCE_CONFIRMED,
                device_class="voltage",
                unit="V",
                diagnostic=True,
            ),
            # Current drawn, not power: 6.9 kW electrical out of a 5 kW unit is
            # impossible. No power is derived from V × A (D-16).
            SsrPosition(
                index=24,
                key="current",
                name="Opgenomen stroom",
                confidence=CONFIDENCE_ASSUMED,
                device_class="current",
                unit="A",
                diagnostic=True,
            ),
        ),
    ),
    "HP_THERMOSTAT/0": SsrArray(
        key="HP_THERMOSTAT/0",
        slug="hp_thermostat_0",
        length=4,
    ),
    # Resolved by the cycle measurement of 2026-09-09: [outside temperature,
    # operating mode, flow]. Index 1 is the live operating state — HP_UNIT/hp1
    # index 3 read HEATING throughout, also with the compressor at rest (I-11).
    "HP_GLOBAL/0": SsrArray(
        key="HP_GLOBAL/0",
        slug="hp_global_0",
        length=3,
        positions=(
            SsrPosition(
                index=1,
                key="operating_state",
                name="Bedrijfstoestand",
                confidence=CONFIDENCE_CONFIRMED,
            ),
        ),
    ),
}


# --- Identifiers (§4.1) ------------------------------------------------------
#
# The root is the config entry's `entry_id` (D-13): the gateway has no serial
# number and no other stable hardware id (V-17).


def brain_id(entry_id: str) -> str:
    """Identifier of the Brain module — the root of everything."""
    return entry_id


def module_id(entry_id: str, address: str) -> str:
    """Identifier of a bus module, keyed on its energybus address."""
    return f"{entry_id}:module:{address}"


def thermostat_id(entry_id: str, om_id: int) -> str:
    """Identifier of one OpenMotics thermostat."""
    return f"{entry_id}:thermostat:{om_id}"


def app_id(entry_id: str, app: str) -> str:
    """Identifier of a Brain app. App names are used verbatim."""
    return f"{entry_id}:app:{app}"


def heatpump_id(entry_id: str, slave: int) -> str:
    """Identifier of the heat pump behind its Modbus slave address."""
    return f"{entry_id}:modbus:{slave}"


# --- Origins (§4.3) ----------------------------------------------------------
#
# An identifier above says which *device* something is. An origin says what a
# *datapoint* is, and those are not the same question.
#
# The device an entity is displayed on can move. Renson may relocate a
# datapoint, and the cycle measurement of 2026-09-09 already reassigned two of
# them by itself. Home Assistant does not mind: change `device_info` and the
# registry re-parents the entity, which keeps both its entity_id and its
# history. But that only holds if the identity does not mention the device —
# and that is exactly what an origin guarantees.


@dataclass(frozen=True)
class Origin:
    """What a datapoint is, independent of the device it is shown on.

    `uid` roots the unique_id and therefore carries the entry_id (D-13).
    `slug` roots the entity_id and must stay readable, so it carries no
    entry_id and no bus address.
    """

    uid: str
    slug: str


def gateway_origin(entry_id: str) -> Origin:
    """The gateway itself — independent of every app (§5.2)."""
    return Origin(f"{entry_id}:gateway", "brain_module")


def hvac_origin(entry_id: str) -> Origin:
    """The channels of the HVAC module.

    The energybus address is deliberately absent. It identifies the *module*
    well enough (see `module_id`), but replacing the module would then rewrite
    the identity of all fourteen channels — while R3 stays R3 on the new one.
    """
    return Origin(f"{entry_id}:hvac", "hvac_module")


def thermostat_origin(entry_id: str, om_id: int) -> Origin:
    """One OpenMotics thermostat, read over L2 (§5.4)."""
    return Origin(f"{entry_id}:thermostat:{om_id}", f"thermostat_{om_id}")


def app_origin(entry_id: str, app: str) -> Origin:
    """The configuration and runtime of one Brain app. Names are verbatim."""
    return Origin(f"{entry_id}:app:{app}", f"app_{app.lower()}")


def heatpump_origin(entry_id: str) -> Origin:
    """The heat pump itself.

    The Modbus slave address is absent for the same reason as the bus address
    in `hvac_origin`: it addresses the unit, it does not identify its readings.
    """
    return Origin(f"{entry_id}:heatpump", "heatpump")


def ssr_origin(entry_id: str) -> Origin:
    """The raw array positions of the app log (D-14, V-16).

    These hang on no device at all: they are the measuring instrument used to
    establish what the remaining positions mean. They are *shown* on the app
    device, which is a display choice and not an identity.
    """
    return Origin(f"{entry_id}:ssr", "ssr")


# The heat pump sits on Modbus slave 1; `rensonheatpumplogic` reports it in
# `heatpump_config.modbus_address` and it is the same on every installation.
HEATPUMP_SLAVE = 1
