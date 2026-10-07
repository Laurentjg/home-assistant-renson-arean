import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

import { build } from '../build.mjs';
import { formatNumber } from '../src/format.js';
import { languageOf, t } from '../src/i18n.js';
import {
  ROLES,
  barColor,
  barsLit,
  buildEnergyView,
  buildView,
  isActive,
  isCooling,
  normalizeConfig,
  readRole,
  suggestEntities,
  toCubicMetresPerHour,
} from '../src/model.js';
import { WP } from '../src/pump.js';
import { changeNear, localMidnight, ratio, sumChange, summarize } from '../src/stats.js';
import { CARD_BUILD, isOutdated, watchBuild } from '../src/version.js';

const NL = { language: 'nl', number_format: 'language' };
const state = (value, unit, attributes = {}) => ({
  state: String(value),
  attributes: unit ? { unit_of_measurement: unit, ...attributes } : attributes,
});

function hass(overrides = {}) {
  return {
    locale: NL,
    config: { unit_system: { temperature: '°C' } },
    states: {
      'sensor.heatpump_operating_state': state('HEATING'),
      'binary_sensor.silent': state('off'),
      'sensor.outside': state(12.44, '°C'),
      'sensor.hz': state(45, 'Hz'),
      'binary_sensor.pump': state('on'),
      'sensor.return': state(21.8, '°C'),
      'sensor.supply': state(26.3, '°C'),
      'sensor.pressure': state(1.84, 'bar'),
      'sensor.flow': state(1.6, 'm³/h'),
      'sensor.voltage': state(231, 'V'),
      'sensor.current': state(5.4, 'A'),
      'climate.thermostat_0': {
        state: 'heat',
        attributes: { current_temperature: 20.4, temperature: 20.5, hvac_action: 'heating' },
      },
      ...overrides,
    },
  };
}

const ENTITIES = {
  status: 'sensor.heatpump_operating_state',
  silent_mode: 'binary_sensor.silent',
  outdoor_temp: 'sensor.outside',
  compressor_hz: 'sensor.hz',
  circulation_pump: 'binary_sensor.pump',
  cold_temp: 'sensor.return',
  hot_temp: 'sensor.supply',
  pressure: 'sensor.pressure',
  flow: 'sensor.flow',
  voltage: 'sensor.voltage',
  current: 'sensor.current',
  room_temp: 'climate.thermostat_0',
  setpoint: 'climate.thermostat_0',
  heat_demand: 'climate.thermostat_0',
};

const view = (entities = ENTITIES, overrides = {}) =>
  buildView(hass(overrides), normalizeConfig({ entities }), 'nl');

test('anchors match the reference projection of the design spec', () => {
  const anchors = WP.anchors(WP.makeProjection({ cx: 400, cy: 284, scale: 1.32, yaw: -32, pitch: 14 }));
  const near = (actual, expected) => assert.ok(Math.abs(actual - expected) < 1, `${actual} vs ${expected}`);
  near(anchors.top, 183);
  near(anchors.cableEnd[0], 63);
  near(anchors.cableEnd[1], 286);
  near(anchors.leftPipeEnd[0], 68);
  near(anchors.leftPipeEnd[1], 350);
  near(anchors.rightPipeEnd[0], 648);
  near(anchors.rightPipeEnd[1], 258);
  near(anchors.fanCenter[0], 414);
  near(anchors.fanCenter[1], 300);
});

test('the drawing exposes its animation hooks', () => {
  const P = WP.makeProjection();
  const drawing = WP.detailed(P, { hot: 'red', cold: 'blue', id: 'wp' });
  for (const hook of ['id="wp-fan"', 'id="wp-pipe-left"', 'id="wp-pipe-right"', 'id="wp-cable"', 'wp-flow']) {
    assert.ok(drawing.body.includes(hook), hook);
  }
  assert.ok(WP.sketch(P, { hot: 'red', cold: 'blue' }).includes('id="wp-fan"'));
});

test('numbers follow the user locale', () => {
  assert.equal(formatNumber(1.6, 3, NL), '1,600');
  assert.equal(formatNumber(1.6, 3, { language: 'en' }), '1.600');
  assert.equal(formatNumber(1234.5, 1, { language: 'nl', number_format: 'comma_decimal' }), '1,234.5');
  assert.equal(formatNumber(-0.01, 1, NL), '0,0');
  assert.equal(formatNumber(NaN, 1, NL), null);
});

test('every text exists in Dutch and English', () => {
  assert.equal(languageOf({ locale: { language: 'nl-BE' } }), 'nl');
  assert.equal(languageOf({ language: 'fr' }), 'en');
  for (const role of ROLES) {
    for (const lang of ['nl', 'en']) assert.ok(t(lang, `role_${role.key}`), `${lang} role_${role.key}`);
  }
});

test('configuration is validated', () => {
  assert.throws(() => normalizeConfig(null));
  assert.throws(() => normalizeConfig({ entities: { nonsense: 'sensor.x' } }), /Unknown role/);
  assert.throws(() => normalizeConfig({ max_hz: 0 }));
  assert.throws(() => normalizeConfig({ quality: 'photo' }));
  const config = normalizeConfig({ entities: { status: 'sensor.x', flow: '' } });
  assert.deepEqual(config, { title: null, max_hz: 90, quality: 'detailed', entities: { status: 'sensor.x' } });
});

test('suggestions only name entities that exist', () => {
  assert.deepEqual(suggestEntities({ states: {} }), {});
  const found = suggestEntities(hass());
  assert.equal(found.status, 'sensor.heatpump_operating_state');
  assert.equal(found.fan_running, 'sensor.heatpump_operating_state');
  assert.equal(found.setpoint, 'climate.thermostat_0');
  assert.equal(found.flow, undefined);
  assert.equal(found.heat_power, undefined);

  // What the integration derives and what it reads from the app are pre-filled too.
  const own = suggestEntities(
    hass({
      'sensor.calculated_heat_output': state(4.9, 'kW'),
      'sensor.calculated_heat_energy': state(1234.5, 'kWh'),
      'sensor.heatpump_warranty_number': state('RS-1'),
    })
  );
  assert.equal(own.heat_power, 'sensor.calculated_heat_output');
  assert.equal(own.heat_energy, 'sensor.calculated_heat_energy');
  assert.equal(own.serial, 'sensor.heatpump_warranty_number');
});

test('a heat output entity replaces the calculation', () => {
  const own = { ...ENTITIES, heat_power: 'sensor.heat' };
  // Not 8.4 kW from flow × ΔT: the entity knows what the circuit is filled with.
  assert.equal(view(own, { 'sensor.heat': state(7.77, 'kW') }).heat.power.text, '7,8 kW');
  assert.equal(view(own, { 'sensor.heat': state(7770, 'W') }).heat.power.text, '7,8 kW');
  assert.equal(view(own, { 'sensor.heat': state('unavailable') }).heat.power.na, true);
  // A defrost takes heat out of the system, and that stays visible.
  assert.equal(view(own, { 'sensor.heat': state(-2.5, 'kW') }).heat.power.text, '-2,5 kW');
  // While cooling the sign says nothing new: the label already reads "cooling".
  const cooling = view(own, {
    'sensor.heatpump_operating_state': state('COOLING'),
    'sensor.heat': state(-3.2, 'kW'),
  });
  assert.equal(cooling.heat.power.text, '3,2 kW');
});

test('states are read as running or not', () => {
  assert.equal(isActive('HEATING'), true);
  assert.equal(isActive('OFF'), false);
  assert.equal(isActive('idle'), false);
  assert.equal(isActive('on'), true);
  assert.equal(isActive('1.6'), true);
  assert.equal(isActive('0.0'), false);
  assert.equal(isActive(null), null);
  assert.equal(isCooling('COOLING'), true);
  assert.equal(isCooling('cool'), true);
  assert.equal(isCooling('HEATING'), false);
});

test('a climate entity fills room temperature, setpoint and demand', () => {
  const h = hass();
  assert.equal(readRole(h, 'climate.thermostat_0', 'setpoint').value, 20.5);
  assert.equal(readRole(h, 'climate.thermostat_0', 'setpoint').unit, '°C');
  assert.equal(readRole(h, { entity: 'sensor.flow', attribute: 'nope' }, 'flow').available, false);
  assert.equal(readRole(h, 'sensor.absent', 'flow').available, false);
  const vm = view();
  assert.deepEqual(
    vm.demand.map((row) => row.cell.text),
    ['20,4 °C', '20,5 °C', 'Ja']
  );
});

test('the view shows the measured values', () => {
  const vm = view();
  assert.equal(vm.info[0].cell.text, 'Verwarmen');
  assert.equal(vm.info[1].cell.text, 'Uit');
  assert.equal(vm.outdoor.text, '12,4 °C');
  assert.equal(vm.compressor.text, '45 Hz');
  assert.equal(vm.barsLit, 5);
  assert.equal(vm.hot.flow.text, '1,600 m³/h');
  assert.equal(vm.cold.pressure.text, '1,8 bar');
  assert.equal(vm.elec.voltage.text, '231 V');
  assert.equal(vm.elec.current.text, '5,4 A');
  // 1.6 m³/h × 1.163 × 4.5 K = 8.37 kW
  assert.equal(vm.heat.power.text, '8,4 kW');
  assert.equal(vm.heat.deltaT.text, '4,5 K');
  assert.equal(vm.pumpOn, true);
  assert.equal(vm.cooling, false);
});

test('the fan follows the operating state unless it has its own entity', () => {
  assert.equal(view().fanOn, true);
  assert.equal(view(ENTITIES, { 'sensor.heatpump_operating_state': state('OFF') }).fanOn, false);
  assert.equal(view(ENTITIES, { 'sensor.heatpump_operating_state': state('unavailable') }).fanOn, false);
  const own = { ...ENTITIES, fan_running: 'binary_sensor.fan' };
  assert.equal(view(own, { 'binary_sensor.fan': state('off') }).fanOn, false);
});

test('without a pump entity the flow decides whether water moves', () => {
  const { circulation_pump: _pump, ...rest } = ENTITIES;
  assert.equal(view(rest).pumpOn, true);
  assert.equal(view(rest, { 'sensor.flow': state(0, 'm³/h') }).pumpOn, false);
});

test('a flow in litres per minute is converted for the heat output', () => {
  assert.equal(toCubicMetresPerHour(20, 'l/min'), 1.2);
  const vm = view(ENTITIES, { 'sensor.flow': state(20, 'l/min') });
  assert.equal(vm.hot.flow.text, '20,0 l/min');
  assert.equal(vm.heat.power.text, '6,3 kW');
});

test('cooling mode follows the operating state and flips the temperature difference', () => {
  const vm = view(ENTITIES, {
    'sensor.heatpump_operating_state': state('COOLING'),
    'sensor.return': state(18, '°C'),
    'sensor.supply': state(14, '°C'),
  });
  assert.equal(vm.cooling, true);
  assert.equal(vm.info[0].cell.text, 'Koelen');
  assert.equal(vm.heat.deltaT.text, '4,0 K');
});

test('power meter: hidden when not configured, a dash when unavailable', () => {
  assert.equal(view().elec.power, null);
  assert.equal(view().hot.cop, null);

  const withPower = { ...ENTITIES, power: 'sensor.power' };
  const ok = view(withPower, { 'sensor.power': state(1240, 'W') });
  assert.equal(ok.elec.power.text, '1,24 kW');
  assert.equal(ok.hot.cop.text, '6,8');

  const gone = view(withPower, { 'sensor.power': state('unavailable', 'W') });
  assert.equal(gone.elec.power.na, true);
  assert.equal(gone.hot.cop.na, true);

  const standby = view(withPower, { 'sensor.power': state(46, 'W'), 'sensor.hz': state(0, 'Hz') });
  assert.equal(standby.hot.cop.na, true);
});

test('unavailable values become a dash, optional rows disappear', () => {
  const vm = view(ENTITIES, { 'sensor.supply': state('unavailable', '°C') });
  assert.equal(vm.hot.temp.text, '—');
  assert.equal(vm.hot.temp.na, true);
  assert.equal(vm.heat.power.na, true);
  assert.equal(vm.info.length, 2);
  const bare = view({ status: 'sensor.heatpump_operating_state' });
  assert.equal(bare.demand.length, 0);
  assert.equal(bare.outdoor.na, true);
});

test('the gas boiler row carries the flame', () => {
  const vm = view({ ...ENTITIES, gas_boiler: 'binary_sensor.boiler' }, { 'binary_sensor.boiler': state('on') });
  assert.equal(vm.gasOn, true);
  assert.equal(vm.demand[3].flame, true);
  assert.equal(vm.demand[3].cell.text, 'Aan');
});

test('compressor bars', () => {
  assert.equal(barsLit(0, 90), 0);
  assert.equal(barsLit(90, 90), 10);
  assert.equal(barsLit(200, 90), 10);
  assert.equal(barsLit(null, 90), 0);
  assert.equal(barColor(0), 'rgb(29,158,117)');
  assert.equal(barColor(1), 'rgb(217,55,43)');
});

const DAY = 24 * 3600 * 1000;

test('COP is a ratio of sums, never a mean of ratios', () => {
  assert.equal(ratio(10, 0), null);
  assert.equal(ratio(null, 2), null);
  assert.equal(ratio(10, 2.5), 4);
  const buckets = [
    { start: 1000, change: 1 },
    { start: 2000, change: 2 },
    { start: 3000, change: null },
  ];
  assert.equal(sumChange(buckets, 1500), 2);
  assert.equal(sumChange(buckets, 5000), null);
  assert.equal(changeNear(buckets, 2100, 500), 2);
  assert.equal(changeNear(buckets, 9000, 500), null);
});

test('statistics become daily bars and rolling figures', () => {
  const now = new Date(2026, 9, 5, 15, 0, 0).getTime();
  const midnight = localMidnight(now);
  const dayAt = (daysAgo) => new Date(2026, 9, 5 - daysAgo).getTime();
  const daily = {
    heat: [
      { start: dayAt(2), change: 30 },
      { start: dayAt(1), change: 20 },
      { start: midnight, change: 8 },
    ],
    elec: [
      { start: dayAt(2), change: 10 },
      { start: dayAt(1), change: 0 },
      { start: new Date(midnight).toISOString(), change: 2 },
    ],
  };
  const hourly = {
    heat: [
      { start: now - 30 * 3600 * 1000, change: 100 },
      { start: now - 2 * 3600 * 1000, change: 6 },
    ],
    elec: [{ start: now - 2 * 3600 * 1000, change: 1.5 }],
  };
  const summary = summarize(daily, hourly, 'heat', 'elec', now);
  assert.equal(summary.days.length, 14);
  assert.equal(summary.days[13].cop, 4);
  // A day without electricity use has no bar.
  assert.equal(summary.days[12].cop, null);
  assert.equal(summary.days[11].cop, 3);
  assert.equal(summary.days[0].cop, null);
  assert.equal(summary.heatToday, 8);
  assert.equal(summary.elecToday, 2);
  assert.equal(summary.cop24, 4);
  // (30 + 20 + 8) / (10 + 0 + 2)
  assert.ok(Math.abs(summary.cop2m - 58 / 12) < 1e-9);
  assert.equal(summary.days[13].start - summary.days[12].start, DAY);

  const heatOnly = summarize(daily, hourly, 'heat', null, now);
  assert.equal(heatOnly.heatToday, 8);
  assert.equal(heatOnly.cop24, null);
});

test('the energy box has three states per counter', () => {
  const summary = {
    days: [{ start: 0, cop: 4 }],
    heatToday: 24.8,
    elecToday: 6.2,
    cop24: 4,
    cop2m: 3.9,
    cop12m: null,
  };
  const counters = { 'sensor.heat': state(100, 'kWh'), 'sensor.elec': state(30, 'kWh') };
  const config = (entities) => normalizeConfig({ entities });

  const both = buildEnergyView(
    hass(counters),
    config({ heat_energy: 'sensor.heat', elec_energy: 'sensor.elec' }),
    summary,
    'nl'
  );
  assert.equal(both.mode, 'chart');
  assert.deepEqual(both.rows.map((row) => row.cell.text), ['24,8 kWh', '6,2 kWh']);
  assert.deepEqual(both.cops.map((row) => row.cell.text), ['4,0', '3,9', '—']);

  const noPower = buildEnergyView(hass(counters), config({ heat_energy: 'sensor.heat' }), summary, 'nl');
  assert.equal(noPower.mode, 'no_power');
  assert.equal(noPower.rows.length, 1);

  const noHeat = buildEnergyView(hass(counters), config({ elec_energy: 'sensor.elec' }), null, 'nl');
  assert.equal(noHeat.mode, 'no_heat');

  const grey = buildEnergyView(
    hass({ ...counters, 'sensor.elec': state('unavailable', 'kWh') }),
    config({ heat_energy: 'sensor.heat', elec_energy: 'sensor.elec' }),
    summary,
    'nl'
  );
  assert.equal(grey.grey, true);
  assert.equal(grey.rows[1].cell.na, true);
  assert.equal(grey.cops[0].cell.na, true);

  const loading = buildEnergyView(
    hass(counters),
    config({ heat_energy: 'sensor.heat', elec_energy: 'sensor.elec' }),
    null,
    'nl'
  );
  assert.equal(loading.rows[0].cell.na, true);
  assert.equal(loading.days.length, 0);
});

test('only another build of the card counts as outdated', () => {
  assert.equal(isOutdated('aaaaaaaaaaaa', 'bbbbbbbbbbbb'), true);
  assert.equal(isOutdated('aaaaaaaaaaaa', 'aaaaaaaaaaaa'), false);
  // An integration that does not know its build, and a card straight from src/.
  assert.equal(isOutdated('aaaaaaaaaaaa', null), false);
  assert.equal(isOutdated('aaaaaaaaaaaa', undefined), false);
  assert.equal(isOutdated(CARD_BUILD, 'bbbbbbbbbbbb'), false);
});

test('the build is asked again when the connection comes back', async () => {
  const settle = () => new Promise((done) => setImmediate(done));
  const listeners = {};
  let served = 'aaaaaaaaaaaa';
  const connection = {
    sendMessagePromise: async (message) => {
      assert.deepEqual(message, { type: 'renson_arean/card_build' });
      if (served === null) throw new Error('unknown command');
      return { build: served };
    },
    addEventListener: (name, listener) => {
      listeners[name] = listener;
    },
  };
  let outdated = 0;
  watchBuild(connection, 'aaaaaaaaaaaa', () => outdated++);
  await settle();
  assert.equal(outdated, 0);

  // An integration without the command is not a reason to complain.
  served = null;
  listeners.ready();
  await settle();
  assert.equal(outdated, 0);

  // Home Assistant restarted with an update.
  served = 'bbbbbbbbbbbb';
  listeners.ready();
  await settle();
  assert.equal(outdated, 1);
});

test('the built card carries the build id the integration reads', () => {
  const built = build();
  const integration = readFileSync(
    new URL('../../custom_components/renson_arean/__init__.py', import.meta.url),
    'utf8'
  );
  const pattern = integration.match(/CARD_BUILD_PATTERN = re\.compile\(r"(.+)"\)/);
  assert.ok(pattern, 'the integration has a pattern for the build id');
  assert.match(built, new RegExp(pattern[1]));
  assert.ok(!built.includes(CARD_BUILD), 'the placeholder is filled in');
});

test('the committed card is built from the current source', () => {
  const committed = readFileSync(
    new URL('../../custom_components/renson_arean/frontend/renson-arean-card.js', import.meta.url),
    'utf8'
  );
  const built = build();
  assert.equal(committed, built);
  assert.ok(!/^\s*(import|export)\s/m.test(built), 'no module syntax left');
});
