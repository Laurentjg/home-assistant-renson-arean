/* From Home Assistant states to what the card shows. Pure functions: no DOM. */

import { formatNumber } from './format.js';
import { hasString, t } from './i18n.js';

export const NA = '—';

// kWh per m³ per K, for plain water.
const WATER_HEAT_FACTOR = 1.163;

// Every entity role of the card, with the domains the editor offers for it.
export const ROLES = [
  { key: 'status', domains: ['sensor', 'climate'] },
  { key: 'silent_mode', domains: ['binary_sensor', 'switch', 'input_boolean'] },
  { key: 'serial', domains: ['sensor'] },
  { key: 'operating_hours', domains: ['sensor'] },
  { key: 'outdoor_temp', domains: ['sensor'] },
  { key: 'compressor_hz', domains: ['sensor'] },
  { key: 'fan_running', domains: ['sensor', 'binary_sensor'] },
  { key: 'circulation_pump', domains: ['binary_sensor', 'sensor', 'switch'] },
  { key: 'cooling_mode', domains: ['binary_sensor', 'sensor', 'climate'] },
  { key: 'cold_temp', domains: ['sensor'] },
  { key: 'hot_temp', domains: ['sensor'] },
  { key: 'pressure', domains: ['sensor'] },
  { key: 'flow', domains: ['sensor'] },
  { key: 'heat_power', domains: ['sensor'] },
  { key: 'voltage', domains: ['sensor'] },
  { key: 'current', domains: ['sensor'] },
  { key: 'room_temp', domains: ['sensor', 'climate'] },
  { key: 'setpoint', domains: ['sensor', 'climate', 'number', 'input_number'] },
  { key: 'heat_demand', domains: ['binary_sensor', 'climate', 'sensor'] },
  { key: 'gas_boiler', domains: ['binary_sensor', 'switch', 'sensor'] },
  { key: 'power', domains: ['sensor'] },
  { key: 'cop_now', domains: ['sensor'] },
  { key: 'heat_energy', domains: ['sensor'] },
  { key: 'elec_energy', domains: ['sensor'] },
];

const ROLE_KEYS = new Set(ROLES.map((role) => role.key));

// A role that points at a climate entity reads the matching attribute, so one
// thermostat entity can fill room temperature, setpoint and heat demand.
const CLIMATE_ATTRIBUTES = {
  room_temp: 'current_temperature',
  setpoint: 'temperature',
  heat_demand: 'hvac_action',
  status: 'hvac_action',
};

// Entity ids the integration registers. They are only suggestions for a new
// card: nothing is assumed to exist, and every role stays configurable.
const SUGGESTIONS = {
  status: ['sensor.heatpump_operating_state'],
  fan_running: ['sensor.heatpump_operating_state'],
  silent_mode: ['binary_sensor.app_rensonheatpumplogic_silent_mode'],
  outdoor_temp: ['sensor.heatpump_outside_temperature'],
  compressor_hz: ['sensor.heatpump_compressor_frequency'],
  circulation_pump: ['binary_sensor.heatpump_waterpump_active'],
  cold_temp: ['sensor.heatpump_return_temperature'],
  hot_temp: ['sensor.heatpump_flow_temperature'],
  pressure: ['sensor.hvac_module_in1_pressure'],
  flow: ['sensor.heatpump_flow'],
  voltage: ['sensor.heatpump_mains_voltage'],
  current: ['sensor.heatpump_current'],
  room_temp: ['climate.thermostat_0'],
  setpoint: ['climate.thermostat_0'],
  heat_demand: ['climate.thermostat_0'],
};

const QUALITIES = ['detailed', 'sketch'];
export const DEFAULT_MAX_HZ = 90;
export const COMPRESSOR_BARS = 10;

export function entityIdOf(ref) {
  if (!ref) return null;
  return typeof ref === 'string' ? ref : ref.entity || null;
}

export function normalizeConfig(config) {
  if (!config || typeof config !== 'object') throw new Error('Invalid configuration');
  const entities = config.entities === undefined ? {} : config.entities;
  if (!entities || typeof entities !== 'object' || Array.isArray(entities)) {
    throw new Error('"entities" must map a role to an entity');
  }
  const cleaned = {};
  for (const [role, ref] of Object.entries(entities)) {
    if (!ROLE_KEYS.has(role)) throw new Error(`Unknown role: ${role}`);
    if (ref === null || ref === undefined || ref === '') continue;
    if (!entityIdOf(ref)) throw new Error(`Role ${role} needs an entity`);
    cleaned[role] = ref;
  }
  const maxHz = config.max_hz === undefined ? DEFAULT_MAX_HZ : Number(config.max_hz);
  if (!(maxHz > 0)) throw new Error('"max_hz" must be a number above 0');
  const quality = config.quality === undefined ? 'detailed' : config.quality;
  if (!QUALITIES.includes(quality)) throw new Error('"quality" must be "detailed" or "sketch"');
  return {
    title: typeof config.title === 'string' && config.title ? config.title : null,
    max_hz: maxHz,
    quality,
    entities: cleaned,
  };
}

export function suggestEntities(hass) {
  const states = (hass && hass.states) || {};
  const entities = {};
  for (const [role, candidates] of Object.entries(SUGGESTIONS)) {
    const found = candidates.find((entityId) => states[entityId]);
    if (found) entities[role] = found;
  }
  return entities;
}

const MISSING = { configured: false, available: false, value: null, unit: '', entityId: null };

export function readRole(hass, ref, role) {
  const entityId = entityIdOf(ref);
  if (!entityId) return MISSING;
  const unavailable = { configured: true, available: false, value: null, unit: '', entityId };
  let attribute = typeof ref === 'object' ? ref.attribute : undefined;
  if (!attribute && entityId.startsWith('climate.')) attribute = CLIMATE_ATTRIBUTES[role];
  const state = hass && hass.states && hass.states[entityId];
  if (!state || state.state === 'unavailable') return unavailable;
  const attributes = state.attributes || {};
  const value = attribute ? attributes[attribute] : state.state;
  if (value === null || value === undefined || (!attribute && value === 'unknown')) return unavailable;
  let unit = attributes.unit_of_measurement || '';
  if (attribute) {
    const system = hass.config && hass.config.unit_system;
    unit = attribute.includes('temperature') ? (system && system.temperature) || '°C' : '';
  }
  return { configured: true, available: true, value, unit, entityId };
}

function toNumber(reading) {
  if (!reading.available || reading.value === '' || typeof reading.value === 'boolean') return null;
  const number = Number(reading.value);
  return Number.isFinite(number) ? number : null;
}

const INACTIVE = new Set(['off', 'false', '0', 'idle', 'standby', 'none', 'closed', 'no', '']);

// Whether a state means "running": on/off, a number above 0, or any operating
// state other than off or idle (HEATING, COOLING, ...).
export function isActive(value) {
  if (value === null || value === undefined) return null;
  if (typeof value === 'boolean') return value;
  if (typeof value === 'number') return value > 0;
  const text = String(value).trim().toLowerCase();
  if (INACTIVE.has(text)) return false;
  const number = Number(text);
  if (Number.isFinite(number)) return number > 0;
  return true;
}

const COOLING = new Set(['cool', 'cooling', 'on', 'true']);

export function isCooling(value) {
  if (value === null || value === undefined) return false;
  if (typeof value === 'boolean') return value;
  return COOLING.has(String(value).trim().toLowerCase());
}

function normalizeUnit(unit) {
  return String(unit || '').replace(/\s/g, '').replace('³', '3').toLowerCase();
}

export function toCubicMetresPerHour(value, unit) {
  switch (normalizeUnit(unit)) {
    case 'l/min':
      return value * 0.06;
    case 'l/h':
      return value / 1000;
    case 'l/s':
      return value * 3.6;
    default:
      return value;
  }
}

export function toKilowatt(value, unit) {
  return normalizeUnit(unit) === 'kw' ? value : value / 1000;
}

export function heatOutput(flowM3h, deltaT) {
  if (flowM3h === null || deltaT === null) return null;
  return flowM3h * WATER_HEAT_FACTOR * deltaT;
}

const BAR_STOPS = [
  [0, [29, 158, 117]],
  [0.4, [224, 165, 38]],
  [0.7, [232, 118, 43]],
  [1, [217, 55, 43]],
];

// Green, ochre, orange, red: the colour of compressor bar `fraction` (0..1).
export function barColor(fraction) {
  const f = Math.min(1, Math.max(0, fraction));
  for (let i = 1; i < BAR_STOPS.length; i++) {
    if (f <= BAR_STOPS[i][0]) {
      const [a0, c0] = BAR_STOPS[i - 1];
      const [a1, c1] = BAR_STOPS[i];
      const u = (f - a0) / (a1 - a0);
      return `rgb(${c0.map((v, k) => Math.round(v + (c1[k] - v) * u)).join(',')})`;
    }
  }
  return `rgb(${BAR_STOPS[BAR_STOPS.length - 1][1].join(',')})`;
}

export function barsLit(hz, maxHz) {
  if (hz === null || !(maxHz > 0)) return 0;
  return Math.min(COMPRESSOR_BARS, Math.max(0, Math.round((hz / maxHz) * COMPRESSOR_BARS)));
}

function cell(reading, text) {
  const missing = text === null || text === undefined;
  return { text: missing ? NA : text, na: missing, entity: reading ? reading.entityId : null };
}

export function buildView(hass, config, lang) {
  const entities = config.entities;
  const locale = (hass && hass.locale) || { language: lang };
  const tr = (key) => t(lang, key);
  const read = (role) => readRole(hass, entities[role], role);
  const number = (value, decimals) => formatNumber(value, decimals, locale);
  const measure = (role, decimals, fallbackUnit) => {
    const reading = read(role);
    const value = toNumber(reading);
    if (value === null) return cell(reading, null);
    return cell(reading, `${number(value, decimals)} ${reading.unit || fallbackUnit}`.trim());
  };
  const onOff = (reading, on = 'on', off = 'off') => {
    const active = reading.available ? isActive(reading.value) : null;
    return cell(reading, active === null ? null : tr(active ? on : off));
  };

  // --- Operating state, and what follows from it ---
  const status = read('status');
  const cooling = isCooling((entities.cooling_mode ? read('cooling_mode') : status).value);
  let statusText = null;
  if (status.available) {
    const key = `state_${String(status.value).toUpperCase()}`;
    statusText = hasString(key) ? tr(key) : String(status.value);
  }
  const fan = entities.fan_running ? read('fan_running') : status;
  const silent = read('silent_mode');

  // --- Water side ---
  const flow = read('flow');
  const flowValue = toNumber(flow);
  const flowM3h = flowValue === null ? null : toCubicMetresPerHour(flowValue, flow.unit);
  const hot = toNumber(read('hot_temp'));
  const cold = toNumber(read('cold_temp'));
  let deltaT = hot !== null && cold !== null ? hot - cold : null;
  if (cooling && deltaT !== null) deltaT = -deltaT;

  let heatKw;
  let heatReading = null;
  if (entities.heat_power) {
    heatReading = read('heat_power');
    const value = toNumber(heatReading);
    heatKw = value === null ? null : toKilowatt(value, heatReading.unit);
  } else {
    heatKw = heatOutput(flowM3h, deltaT);
  }

  const pump = entities.circulation_pump ? read('circulation_pump') : null;
  const pumpOn = pump ? pump.available && isActive(pump.value) === true : (flowM3h || 0) > 0;

  const flowUnit = flow.unit || 'm³/h';
  const flowDecimals = normalizeUnit(flowUnit) === 'm3/h' ? 3 : 1;

  // --- Electrical side: the power comes from the user's own meter ---
  const hzReading = read('compressor_hz');
  const hz = toNumber(hzReading);
  const powerReading = read('power');
  const powerValue = toNumber(powerReading);
  const powerKw = powerValue === null ? null : toKilowatt(powerValue, powerReading.unit);

  let copNow = null;
  if (entities.cop_now) {
    const reading = read('cop_now');
    const value = toNumber(reading);
    copNow = cell(reading, value === null ? null : number(value, 1));
  } else if (powerReading.configured) {
    // Only while the compressor runs; a COP at standby is a division by nearly nothing.
    const running = (hz || 0) > 0 && powerKw !== null && powerKw > 0.2 && heatKw !== null;
    copNow = cell(null, running ? number(heatKw / powerKw, 1) : null);
  }

  // --- Boxes ---
  const info = [
    { label: tr('status'), cell: cell(status, statusText) },
    { label: tr('silent'), cell: onOff(silent) },
  ];
  if (entities.serial) {
    const reading = read('serial');
    info.push({ label: tr('serial'), cell: cell(reading, reading.available ? String(reading.value) : null) });
  }
  if (entities.operating_hours) {
    const reading = read('operating_hours');
    const value = toNumber(reading);
    info.push({
      label: tr('hours'),
      cell: cell(reading, value === null ? null : `${number(value, 0)} ${reading.unit || 'h'}`),
    });
  }

  const demand = [];
  if (entities.room_temp) demand.push({ label: tr('thermostat'), cell: measure('room_temp', 1, '°C') });
  if (entities.setpoint) demand.push({ label: tr('setpoint'), cell: measure('setpoint', 1, '°C') });
  if (entities.heat_demand) {
    demand.push({ label: tr('demand'), cell: onOff(read('heat_demand'), 'yes', 'no') });
  }
  let gasOn = false;
  if (entities.gas_boiler) {
    const reading = read('gas_boiler');
    gasOn = reading.available && isActive(reading.value) === true;
    demand.push({ label: tr('boiler'), cell: onOff(reading), flame: true });
  }

  return {
    title: config.title || tr('title'),
    cooling,
    silent: silent.available && isActive(silent.value) === true,
    fanOn: fan.available && isActive(fan.value) === true,
    pumpOn,
    gasOn,
    barsLit: barsLit(hz, config.max_hz),
    compressor: cell(hzReading, hz === null ? null : `${number(hz, 0)} ${hzReading.unit || 'Hz'}`),
    outdoor: measure('outdoor_temp', 1, '°C'),
    info,
    demand,
    elec: {
      power: powerReading.configured
        ? cell(powerReading, powerKw === null ? null : `${number(powerKw, 2)} kW`)
        : null,
      voltage: measure('voltage', 0, 'V'),
      current: measure('current', 1, 'A'),
    },
    heat: {
      power: cell(heatReading, heatKw === null ? null : `${number(heatKw, 1)} kW`),
      deltaT: cell(null, deltaT === null ? null : `${number(deltaT, 1)} K`),
    },
    cold: { temp: measure('cold_temp', 1, '°C'), pressure: measure('pressure', 1, 'bar') },
    hot: { temp: measure('hot_temp', 1, '°C'), flow: measure('flow', flowDecimals, 'm³/h'), cop: copNow },
  };
}

function counterAvailable(hass, entityId) {
  const state = hass && hass.states && hass.states[entityId];
  return Boolean(state) && state.state !== 'unavailable' && state.state !== 'unknown';
}

// The energy box. `summary` is the result of `fetchEnergy`, or null while it
// is loading or when the statistics could not be read.
export function buildEnergyView(hass, config, summary, lang) {
  const locale = (hass && hass.locale) || { language: lang };
  const heatId = entityIdOf(config.entities.heat_energy);
  const elecId = entityIdOf(config.entities.elec_energy);
  const kwh = (value) =>
    value === null || value === undefined ? null : `${formatNumber(value, 1, locale)} kWh`;
  // Configured but unavailable: grey bars and dashes, not zeros.
  const grey = Boolean(elecId) && !counterAvailable(hass, elecId);

  const rows = [];
  if (heatId) {
    const text = summary && counterAvailable(hass, heatId) ? kwh(summary.heatToday) : null;
    rows.push({ label: t(lang, 'heat_today'), cell: cell({ entityId: heatId }, text) });
  }
  if (elecId) {
    const text = summary && !grey ? kwh(summary.elecToday) : null;
    rows.push({ label: t(lang, 'elec_today'), cell: cell({ entityId: elecId }, text) });
  }

  let mode = 'chart';
  if (!elecId) mode = 'no_power';
  else if (!heatId) mode = 'no_heat';

  const cop = (value) =>
    cell(null, grey || value === null || value === undefined ? null : formatNumber(value, 1, locale));
  return {
    rows,
    mode,
    grey,
    days: summary ? summary.days.map((day) => ({ start: day.start, cop: day.cop })) : [],
    cops: [
      { label: t(lang, 'cop24'), cell: cop(summary && summary.cop24) },
      { label: t(lang, 'cop2m'), cell: cop(summary && summary.cop2m) },
      { label: t(lang, 'cop12m'), cell: cop(summary && summary.cop12m) },
    ],
  };
}
