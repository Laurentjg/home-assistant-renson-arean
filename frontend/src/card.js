/* The card element. Draws on one 800 × 600 reference grid; see LAYOUT. */

import { EDITOR_TAG, RensonAreanCardEditor } from './editor.js';
import { escapeHtml } from './format.js';
import { languageOf, t } from './i18n.js';
import {
  COMPRESSOR_BARS,
  barColor,
  buildEnergyView,
  buildView,
  entityIdOf,
  normalizeConfig,
  suggestEntities,
} from './model.js';
import { WP } from './pump.js';
import { fetchEnergy } from './stats.js';

const CARD_TAG = 'renson-arean-card';

// All sizes are in px on the reference width of 800 px (viewBox 0 0 800 600).
const LAYOUT = {
  ref: { w: 800, h: 600 },
  projection: { cx: 400, cy: 284, scale: 1.32, yaw: -32, pitch: 14 },
  boxInfo: { x: 16, y: 16, w: 252, h: 136, r: 12 },
  boxDemand: { x: 532, y: 16, w: 252, h: 136, r: 12 },
  boxEnergy: { x: 16, y: 440, w: 768, h: 144, r: 12 },
  rowStep: 22,
  compressor: { barW: 9, pitch: 12, hMin: 6, hStep: 3.6, labelGap: 10 },
  outside: { gapAboveBars: 14 },
  // Offsets relative to the baseline of the stacks above the cable and the pipe.
  stack: { label: -74, value: -52, sub1: -18, sub2: 0, gapAboveLine: 12 },
  belowPipe: { v1: 30, v2: 50, v3: 70 },
  // The right pipe rises towards its end, so its values sit a little lower to clear it.
  belowPipeRight: { v1: 38, v2: 58, v3: 78 },
  chart: { x: 300, w: 268, top: 488, bottom: 560, max: 5, barW: 13, barPitch: 19 },
  copCol: { xLabel: 604, xValue: 768, rowStep: 36 },
};

// Labels hang on anchor points of the drawing, not on fixed coordinates.
const PROJECT = WP.makeProjection(LAYOUT.projection);
const ANCHORS = WP.anchors(PROJECT);

const COLD = 'var(--wp-cold, #2b7fd6)';
const HOT = 'var(--wp-hot, #d9372b)';
const ELEC = 'var(--wp-elec, #e0a526)';
const GOLD = 'var(--wp-gold, #c9a34a)';
const GREEN = 'var(--wp-green, #1d9e75)';
const FLAME = 'var(--wp-flame, #e8762b)';

// Radians per second; 0.03 rad per frame at 60 frames per second.
const FAN_SPEED = 1.8;
const FAN_SILENT_FACTOR = 0.4;
const STATS_INTERVAL_MS = 5 * 60 * 1000;

// Font sizes come straight from the Home Assistant tokens. `--wp-s` is the
// factor by which the card is wider than the reference: dividing by it keeps
// the text at the size the rest of Home Assistant uses instead of letting it
// grow with the card.
const size = (token, fallback) => `calc(var(${token}, ${fallback}px) / var(--wp-s, 1))`;

const STYLE = `
  :host { display: block; }
  ha-card { overflow: hidden; }
  svg { display: block; width: 100%; height: auto;
    font-family: var(--ha-font-family-body, Roboto, Noto, sans-serif); }
  .t-title { font-size: ${size('--ha-font-size-l', 16)}; font-weight: var(--ha-font-weight-medium, 500);
    fill: var(--primary-text-color); }
  .t-row-l { font-size: ${size('--ha-font-size-m', 14)}; fill: var(--secondary-text-color); }
  .t-row-v { font-size: ${size('--ha-font-size-m', 14)}; font-weight: var(--ha-font-weight-medium, 500);
    fill: var(--primary-text-color); }
  .t-label { font-size: ${size('--ha-font-size-s', 12)}; fill: var(--secondary-text-color); }
  .t-sub { font-size: ${size('--ha-font-size-m', 14)}; fill: var(--primary-text-color); }
  .t-value { font-size: ${size('--ha-font-size-xl', 20)}; font-weight: var(--ha-font-weight-medium, 500);
    fill: var(--primary-text-color); }
  .t-hero { font-size: ${size('--ha-font-size-2xl', 24)}; font-weight: var(--ha-font-weight-medium, 500);
    fill: var(--primary-text-color); }
  .t-axis { font-size: ${size('--ha-font-size-s', 12)}; fill: var(--secondary-text-color); }
  .t-na { fill: var(--secondary-text-color); opacity: .6; }
  .tap { cursor: pointer; }
  .wp-box { fill: color-mix(in srgb, var(--primary-text-color) 4%, transparent); stroke: var(--divider-color); }
  .grid { stroke: var(--divider-color); }
  .axis0 { stroke: color-mix(in srgb, var(--primary-text-color) 35%, transparent); }
  .bar-off { fill: color-mix(in srgb, var(--secondary-text-color) 30%, transparent); }

  .wp-flow { stroke-dasharray: 5 11; animation: wp-dash .9s linear infinite; }
  .wp-flow.off { display: none; }
  @keyframes wp-dash { to { stroke-dashoffset: -16; } }
  .pulse { animation: wp-pulse 1.1s ease-in-out infinite; transform-box: fill-box; transform-origin: 50% 100%; }
  @keyframes wp-pulse { 0%, 100% { transform: scale(1); opacity: 1; } 50% { transform: scale(1.25); opacity: .65; } }
  .z { animation: wp-z 2.4s ease-in-out infinite; opacity: 0; }
  .z2 { animation-delay: .8s; }
  .z3 { animation-delay: 1.6s; }
  @keyframes wp-z { 0% { opacity: 0; transform: translate(0, 0); } 30% { opacity: 1; }
    100% { opacity: 0; transform: translate(6px, -10px); } }
  @media (prefers-reduced-motion: reduce) {
    .wp-flow, .pulse, .z { animation: none; }
    .z { opacity: 1; }
  }
`;

function text(x, y, content, cls, anchor = 'start', options = {}) {
  const style = options.style ? ` style="${options.style}"` : '';
  const entity = options.entity ? ` data-entity="${escapeHtml(options.entity)}"` : '';
  const classes = cls + (options.entity ? ' tap' : '');
  return `<text class="${classes}" x="${x.toFixed(1)}" y="${y.toFixed(1)}" text-anchor="${anchor}"${style}${entity}>${escapeHtml(content)}</text>`;
}

// A value from the view: greyed when unavailable, tappable when it has an entity.
function value(x, y, cell, cls, anchor = 'start', options = {}) {
  const content = options.prefix ? `${options.prefix} ${cell.text}` : cell.text;
  return text(x, y, content, cell.na ? `${cls} t-na` : cls, anchor, {
    style: cell.na ? '' : options.style,
    entity: cell.entity,
  });
}

function box(b) {
  return `<rect class="wp-box" x="${b.x}" y="${b.y}" width="${b.w}" height="${b.h}" rx="${b.r}"/>`;
}

function rows(b, list) {
  return list
    .map((row, i) => {
      const y = b.y + 54 + i * LAYOUT.rowStep;
      return text(b.x + 16, y, row.label, 't-row-l') + value(b.x + b.w - 16, y, row.cell, 't-row-v', 'end');
    })
    .join('');
}

function silentBadge() {
  const [x, y] = ANCHORS.fanCenter;
  return `<g transform="translate(${x.toFixed(1)},${y.toFixed(1)})">
    <circle r="30" fill="rgba(18,20,23,.88)" stroke="${GOLD}" stroke-width="1.5"/>
    <path d="M6,-13.7 A15,15 0 1 0 6,13.7 A17,17 0 0 1 6,-13.7Z" transform="translate(-4,2)" fill="${GOLD}"/>
    <g style="fill:${GOLD};font-weight:600">
      <text class="z" x="6" y="-2" style="font-size:9px">z</text>
      <text class="z z2" x="11" y="-9" style="font-size:11px">z</text>
      <text class="z z3" x="16" y="-16" style="font-size:13px">Z</text>
    </g></g>`;
}

function flame(x, y, on) {
  const outer = `<path class="${on ? 'pulse' : ''}" d="M0,-11 C7,-4 7,3 0,7 C-7,3 -7,-4 0,-11Z" fill="${
    on ? FLAME : 'var(--secondary-text-color)'
  }" opacity="${on ? 1 : 0.45}"/>`;
  const core = on ? '<path class="pulse" d="M0,-4 C3,-1 3,2 0,5 C-3,2 -3,-1 0,-4Z" fill="#f6c343"/>' : '';
  return `<g transform="translate(${x},${y}) scale(1.05)">${outer}${core}</g>`;
}

function renderEnergy(energy, lang) {
  const L = LAYOUT;
  const be = L.boxEnergy;
  let s = box(be) + text(be.x + 16, be.y + 28, t(lang, 'energy'), 't-title');
  s += rows({ ...be, w: 260 }, energy.rows);

  if (energy.mode !== 'chart') {
    s += text(L.chart.x, be.y + 54, t(lang, `${energy.mode}_1`), 't-row-l');
    s += text(L.chart.x, be.y + 76, t(lang, `${energy.mode}_2`), 't-row-l');
    return s;
  }

  const ch = L.chart;
  const height = ch.bottom - ch.top;
  s += text(ch.x, be.y + 28, t(lang, 'chart'), 't-label');
  for (let v = 0; v <= ch.max; v++) {
    const y = ch.bottom - (v / ch.max) * height;
    s += `<line class="${v ? 'grid' : 'axis0'}" x1="${ch.x}" x2="${ch.x + ch.w}" y1="${y}" y2="${y}"/>`;
    s += text(ch.x - 6, y + 4, String(v), 't-axis', 'end');
  }
  energy.days.forEach((day, i) => {
    const x = ch.x + 4 + i * ch.barPitch;
    if (day.cop !== null && day.cop > 0) {
      const h = (Math.min(day.cop, ch.max) / ch.max) * height;
      const last = i === energy.days.length - 1;
      const fill = energy.grey ? 'var(--secondary-text-color)' : GREEN;
      const opacity = energy.grey ? 0.25 : last ? 1 : 0.6;
      s += `<rect x="${x}" y="${(ch.bottom - h).toFixed(1)}" width="${ch.barW}" height="${h.toFixed(1)}" rx="2" fill="${fill}" opacity="${opacity}"/>`;
    }
    if (i % 2 === 1) {
      const date = new Date(day.start);
      s += text(x + ch.barW / 2, ch.bottom + 16, `${date.getDate()}/${date.getMonth() + 1}`, 't-axis', 'middle');
    }
  });
  energy.cops.forEach((row, i) => {
    const y = be.y + 54 + i * L.copCol.rowStep;
    s += text(L.copCol.xLabel, y, row.label, 't-row-l');
    s += value(L.copCol.xValue, y + 2, row.cell, 't-hero', 'end');
  });
  return s;
}

function renderDynamic(vm, energy, lang) {
  const L = LAYOUT;
  const A = ANCHORS;
  // In cooling mode red and blue swap sides.
  const cold = vm.cooling ? HOT : COLD;
  const hot = vm.cooling ? COLD : HOT;
  let s = '';

  if (vm.silent) s += silentBadge();

  // Compressor bars, centred above the pump, with the outside temperature on top.
  const C = L.compressor;
  const labelY = A.top - C.labelGap;
  const base = labelY - 18;
  const x0 = L.ref.w / 2 - (COMPRESSOR_BARS * C.pitch - (C.pitch - C.barW)) / 2;
  for (let j = 0; j < COMPRESSOR_BARS; j++) {
    const h = C.hMin + j * C.hStep;
    const lit = j < vm.barsLit;
    s += `<rect x="${(x0 + j * C.pitch).toFixed(1)}" y="${(base - h).toFixed(1)}" width="${C.barW}" height="${h.toFixed(1)}" rx="2" ${
      lit ? `fill="${barColor(j / (COMPRESSOR_BARS - 1))}"` : 'class="bar-off"'
    }/>`;
  }
  s += value(400, labelY, vm.compressor, 't-label', 'middle', { prefix: t(lang, 'compressor') });
  const barsTop = base - (C.hMin + (COMPRESSOR_BARS - 1) * C.hStep);
  s += text(400, barsTop - L.outside.gapAboveBars - 30, t(lang, 'outside'), 't-label', 'middle');
  s += value(400, barsTop - L.outside.gapAboveBars, vm.outdoor, 't-hero', 'middle');

  // Electricity on the left and heat on the right: same height, same style.
  const st = L.stack;
  const yb = Math.min(A.cableEnd[1], A.rightPipeEnd[1]) - st.gapAboveLine;
  const xl = A.cableEnd[0];
  const xr = A.rightPipeEnd[0];
  s += text(xl, yb + st.label, t(lang, 'electricity'), 't-label', 'start', { style: `fill:${ELEC}` });
  if (vm.elec.power) s += value(xl, yb + st.value, vm.elec.power, 't-value');
  s += value(xl, yb + st.sub1, vm.elec.voltage, 't-sub', 'start', { prefix: t(lang, 'voltage') });
  s += value(xl, yb + st.sub2, vm.elec.current, 't-sub', 'start', { prefix: t(lang, 'current') });
  s += text(xr, yb + st.label, t(lang, vm.cooling ? 'cooling' : 'heat'), 't-label', 'end', { style: `fill:${hot}` });
  s += value(xr, yb + st.value, vm.heat.power, 't-value', 'end');
  s += value(xr, yb + st.sub1, vm.heat.deltaT, 't-sub', 'end', { prefix: 'ΔT' });

  // Values below the pipes.
  const bp = L.belowPipe;
  const lp = A.leftPipeEnd;
  const rp = A.rightPipeEnd;
  s += value(lp[0], lp[1] + bp.v1, vm.cold.temp, 't-value', 'start', { style: `fill:${cold}` });
  s += value(lp[0], lp[1] + bp.v2, vm.cold.pressure, 't-sub', 'start', { prefix: t(lang, 'pressure') });
  s += value(rp[0], rp[1] + L.belowPipeRight.v1, vm.hot.temp, 't-value', 'end', { style: `fill:${hot}` });
  s += value(rp[0], rp[1] + L.belowPipeRight.v2, vm.hot.flow, 't-sub', 'end', { prefix: t(lang, 'flow') });
  if (vm.hot.cop) s += value(rp[0], rp[1] + L.belowPipeRight.v3, vm.hot.cop, 't-sub', 'end', { prefix: t(lang, 'cop_now') });

  // Boxes: administrative information, not something on the pump itself.
  const bi = L.boxInfo;
  s += box(bi) + text(bi.x + 16, bi.y + 28, vm.title, 't-title') + rows(bi, vm.info);

  if (vm.demand.length) {
    const bd = L.boxDemand;
    s += box(bd) + text(bd.x + 16, bd.y + 28, t(lang, 'demand_title'), 't-title') + rows(bd, vm.demand);
    const flameRow = vm.demand.findIndex((row) => row.flame);
    if (flameRow >= 0) {
      s += flame(bd.x + bd.w - 16 - 44, bd.y + 54 + flameRow * L.rowStep - 5, vm.gasOn);
    }
  }

  return s + renderEnergy(energy, lang);
}

function renderPump(quality, cooling) {
  const colors = { hot: cooling ? COLD : HOT, cold: cooling ? HOT : COLD };
  if (quality === 'detailed') {
    const drawing = WP.detailed(PROJECT, { ...colors, id: 'wp' });
    return `<defs>${drawing.defs}</defs>${drawing.body}`;
  }
  return WP.sketch(PROJECT, colors);
}

export class RensonAreanCard extends HTMLElement {
  static getConfigElement() {
    return document.createElement(EDITOR_TAG);
  }

  static getStubConfig(hass) {
    return { entities: suggestEntities(hass) };
  }

  constructor() {
    super();
    this._angle = 0.3;
    this._visible = true;
    this._tick = this._tick.bind(this);
    this._onVisibility = () => this._syncAnimation();
    this._onTap = this._onTap.bind(this);
  }

  setConfig(config) {
    this._config = normalizeConfig(config);
    this._signature = null;
    this._pumpSignature = null;
    this._stats = null;
    this._statsAt = 0;
    this._update();
  }

  set hass(hass) {
    this._hass = hass;
    this._update();
  }

  getCardSize() {
    return 8;
  }

  getGridOptions() {
    return { columns: 'full', min_columns: 6 };
  }

  connectedCallback() {
    this._build();
    document.addEventListener('visibilitychange', this._onVisibility);
    if (typeof IntersectionObserver !== 'undefined') {
      this._intersection = new IntersectionObserver((entries) => {
        this._visible = entries[entries.length - 1].isIntersecting;
        this._syncAnimation();
      });
      this._intersection.observe(this);
    }
    if (typeof ResizeObserver !== 'undefined') {
      this._resize = new ResizeObserver((entries) => {
        const width = entries[entries.length - 1].contentRect.width;
        if (width > 0) this._svg.style.setProperty('--wp-s', String(Math.max(1, width / LAYOUT.ref.w)));
      });
      this._resize.observe(this._svg);
    }
    this._update();
  }

  disconnectedCallback() {
    document.removeEventListener('visibilitychange', this._onVisibility);
    if (this._intersection) this._intersection.disconnect();
    if (this._resize) this._resize.disconnect();
    this._intersection = null;
    this._resize = null;
    this._syncAnimation();
  }

  _build() {
    if (this._svg) return;
    const root = this.attachShadow({ mode: 'open' });
    root.innerHTML = `<style>${STYLE}</style><ha-card><svg viewBox="0 0 ${LAYOUT.ref.w} ${LAYOUT.ref.h}" role="img"><g id="pump"></g><g id="dynamic"></g></svg></ha-card>`;
    this._svg = root.querySelector('svg');
    this._pumpLayer = root.getElementById('pump');
    this._dynamicLayer = root.getElementById('dynamic');
    this._svg.addEventListener('click', this._onTap);
  }

  _update() {
    if (!this._svg || !this._config || !this._hass) return;
    const lang = languageOf(this._hass);
    const vm = buildView(this._hass, this._config, lang);
    this._vm = vm;
    this._loadStats();

    // The drawing itself only changes with the quality and the cooling mode.
    const pumpSignature = `${this._config.quality}|${vm.cooling}`;
    if (pumpSignature !== this._pumpSignature) {
      this._pumpSignature = pumpSignature;
      this._pumpLayer.innerHTML = renderPump(this._config.quality, vm.cooling);
      this._fan = this.shadowRoot.getElementById('wp-fan');
      this._flowOn = null;
      this._drawFan();
    }
    if (vm.pumpOn !== this._flowOn) {
      this._flowOn = vm.pumpOn;
      this._pumpLayer.querySelectorAll('.wp-flow').forEach((line) => line.classList.toggle('off', !vm.pumpOn));
    }

    // Home Assistant hands over a new `hass` on every state change anywhere;
    // redraw only when something this card shows has changed.
    const energy = buildEnergyView(this._hass, this._config, this._stats, lang);
    const signature = JSON.stringify([lang, vm, energy]);
    if (signature !== this._signature) {
      this._signature = signature;
      this._svg.setAttribute('aria-label', t(lang, 'aria'));
      this._dynamicLayer.innerHTML = renderDynamic(vm, energy, lang);
    }
    this._syncAnimation();
  }

  async _loadStats() {
    const heatId = entityIdOf(this._config.entities.heat_energy);
    if (!heatId || this._statsLoading || !this._hass.callWS) return;
    if (Date.now() - this._statsAt < STATS_INTERVAL_MS) return;
    const config = this._config;
    this._statsLoading = true;
    let stats = null;
    try {
      stats = await fetchEnergy(this._hass, heatId, entityIdOf(config.entities.elec_energy));
    } catch (_err) {
      // No statistics for these entities (yet): the box shows dashes.
    }
    this._statsLoading = false;
    // The configuration may have changed while the request was under way.
    if (config !== this._config) return;
    this._stats = stats;
    this._statsAt = Date.now();
    this._update();
  }

  _drawFan() {
    if (this._fan) this._fan.innerHTML = WP.blades(PROJECT, this._angle, this._config.quality === 'detailed');
  }

  _shouldAnimate() {
    if (!this.isConnected || !this._vm || !this._vm.fanOn || !this._visible || document.hidden) return false;
    return !(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  }

  _syncAnimation() {
    const animate = this._shouldAnimate();
    if (animate && !this._frame) {
      this._lastFrame = null;
      this._frame = requestAnimationFrame(this._tick);
    } else if (!animate && this._frame) {
      cancelAnimationFrame(this._frame);
      this._frame = null;
    }
  }

  _tick(now) {
    this._frame = null;
    if (!this._shouldAnimate()) return;
    // Time based, so the fan turns equally fast on a 60 Hz and a 120 Hz screen.
    const elapsed = this._lastFrame === null ? 0 : Math.min(0.1, (now - this._lastFrame) / 1000);
    this._lastFrame = now;
    this._angle += elapsed * FAN_SPEED * (this._vm.silent ? FAN_SILENT_FACTOR : 1);
    this._drawFan();
    this._frame = requestAnimationFrame(this._tick);
  }

  _onTap(event) {
    const target = event.target.closest ? event.target.closest('[data-entity]') : null;
    if (!target) return;
    this.dispatchEvent(
      new CustomEvent('hass-more-info', {
        detail: { entityId: target.getAttribute('data-entity') },
        bubbles: true,
        composed: true,
      })
    );
  }
}

// Guarded: a user may briefly have both the bundled card and a standalone one.
if (!customElements.get(EDITOR_TAG)) customElements.define(EDITOR_TAG, RensonAreanCardEditor);
if (!customElements.get(CARD_TAG)) customElements.define(CARD_TAG, RensonAreanCard);

window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === CARD_TAG)) {
  const lang = languageOf({ language: document.documentElement.lang || navigator.language });
  window.customCards.push({
    type: CARD_TAG,
    name: t(lang, 'card_name'),
    description: t(lang, 'card_description'),
  });
}
