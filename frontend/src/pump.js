/* Heat pump drawing: pure functions, no DOM needed (runs in the browser and in Node).
 * Coordinates are in "unit space": x = width (0..W, left to right),
 * y = height (0 = bottom, H = top), z = depth (0 = front, -D = back).
 * The camera looks from the front left, slightly from above (yaw -32, pitch 14).
 */
export const WP = (() => {
  const W = 110, H = 75, D = 38;
  const GEO = { W, H, D, pipeY: H * 0.42, pipeZ: -D * 0.5, cableY: H * 0.75, pipeLen: 92,
    fanCx: W * 0.45, fanCy: H * 0.47, fanR: H * 0.38 };
  const COLORS = { cold: '#2b7fd6', hot: '#d9372b', elec: 'var(--wp-elec, #e0a526)', gold: 'var(--wp-gold, #c9a34a)', green: '#1d9e75',
    orange: '#e8762b', bodyFront: '#22252a', bodySide: '#2b2e33', bodyTop: '#3a3e45' };

  function makeProjection({ cx = 400, cy = 280, scale = 1.45, yaw = -32, pitch = 14 } = {}) {
    const a = yaw * Math.PI / 180, b = pitch * Math.PI / 180;
    return function P(x, y, z) {
      x -= W / 2; y -= H / 2; z += D / 2;
      const xr = x * Math.cos(a) - z * Math.sin(a), zr = x * Math.sin(a) + z * Math.cos(a);
      const yr = y * Math.cos(b) - zr * Math.sin(b), z2 = y * Math.sin(b) + zr * Math.cos(b);
      const s = 900 / (520 - z2) * scale;
      return [cx + xr * s, cy - yr * s];
    };
  }

  const f1 = v => v.toFixed(1);
  const mk = P => {
    const pts = a => a.map(p => P(...p).map(f1).join(',')).join(' ');
    return {
      pts,
      poly: (a, fill, extra = '') => `<polygon points="${pts(a)}" fill="${fill}" ${extra}/>`,
      line: (a, col, w, extra = '') => `<polyline points="${pts(a)}" fill="none" stroke="${col}" stroke-width="${w}" ${extra}/>`,
      circ: (cx, cy, r, z, n = 56) => { const c = []; for (let k = 0; k < n; k++) { const t = k / n * 2 * Math.PI; c.push([cx + r * Math.cos(t), cy + r * Math.sin(t), z]); } return c; }
    };
  };

  /* Ankerpunten waaraan de kaart labels en animaties hangt (schermcoördinaten). */
  function anchors(P) {
    const G = GEO;
    const lid = [[0, H, 0], [W, H, 0], [W, H, -D], [0, H, -D]].map(p => P(...p));
    const body = [[0, 0, 0], [W, 0, 0], [0, H, 0], [W, H, 0], [0, 0, -D], [0, H, -D], [W, H, -D]].map(p => P(...p));
    return {
      leftPipeEnd: P(-G.pipeLen, G.pipeY, G.pipeZ),
      leftPipeEntry: P(0, G.pipeY, G.pipeZ),
      rightPipeEnd: P(W + G.pipeLen, G.pipeY, G.pipeZ),
      cableEnd: P(-G.pipeLen, G.cableY, G.pipeZ),
      fanCenter: P(G.fanCx, G.fanCy, 0.6),
      top: Math.min(...lid.map(p => p[1])),
      bbox: { x0: Math.min(...body.map(p => p[0])), x1: Math.max(...body.map(p => p[0])), y0: Math.min(...lid.map(p => p[1])), y1: Math.max(...body.map(p => p[1])) }
    };
  }

  /* Ventilatorbladen (opnieuw tekenen per animatieframe). */
  function blades(P, angle, hq = false) {
    const { poly } = mk(P), { fanCx: cx, fanCy: cy, fanR: r } = GEO;
    let o = '';
    for (let k = 0; k < 5; k++) {
      const t = angle + k * 2 * Math.PI / 5;
      const pt = (rr, tt) => [cx + r * rr * Math.cos(tt), cy + r * rr * Math.sin(tt), hq ? -0.3 : 0.5];
      o += hq
        ? poly([[cx, cy, -0.3], pt(0.95, t), pt(0.86, t + 0.38), pt(0.55, t + 0.62)], '#3a3f47', 'stroke="#555b64" stroke-width="0.7"')
        : poly([[cx, cy, 0.5], pt(0.93, t), pt(0.8, t + 0.55)], '#2a2d32');
    }
    return o;
  }

  /* Schets-stijl (zoals in de goedgekeurde layout). */
  function sketch(P, { hot, cold, flowClass = '' }) {
    const { poly, line, circ } = mk(P), G = GEO;
    const lt = [[-G.pipeLen, G.pipeY, G.pipeZ], [0, G.pipeY, G.pipeZ]], rt = [[W / 2, G.pipeY, G.pipeZ], [W + G.pipeLen, G.pipeY, G.pipeZ]];
    let s = '';
    s += `<g id="wp-pipe-right">${line(rt, '#111', 13)}${line(rt, hot, 9)}${line(rt, 'rgba(255,255,255,.55)', 3, `class="wp-flow ${flowClass}"`)}</g>`;
    [8, W - 22].forEach(x => { s += poly([[x, -10, 4], [x + 14, -10, 4], [x + 14, 0, 4], [x, 0, 4]], '#16181b'); s += poly([[x, -10, -D], [x, -10, 4], [x, 0, 4], [x, 0, -D]], '#0c0d0f'); });
    s += poly([[0, 0, 0], [0, 0, -D], [0, H, -D], [0, H, 0]], COLORS.bodySide);
    for (let i = 1; i < 9; i++) s += line([[0, 3, -D * i / 9], [0, H - 3, -D * i / 9]], '#1a1c1f', 1.4);
    for (let j = 1; j < 7; j++) s += line([[0, H * j / 7, -2], [0, H * j / 7, -D + 2]], '#1a1c1f', 1);
    s += poly([[0, 0, 0], [W, 0, 0], [W, H, 0], [0, H, 0]], COLORS.bodyFront);
    for (let x = 4; x < W; x += 3.2) s += line([[x, 1, .2], [x, H - 4, .2]], x % 6.4 < 3.2 ? '#30343a' : '#191b1e', 1.8);
    s += poly(circ(G.fanCx, G.fanCy, G.fanR, .4), '#141619', 'stroke="#3b3f46" stroke-width="2"');
    s += `<g id="wp-fan">${blades(P, 0)}</g>` + poly(circ(G.fanCx, G.fanCy, G.fanR * .2, .6), '#2f3338');
    s += poly([[0, H, 0], [W, H, 0], [W, H, -D], [0, H, -D]], COLORS.bodyTop) + line([[0, H, 0], [W, H, 0]], '#4c515a', 1.5);
    s += line([[W - 24, H - 5, .3], [W - 8, H - 5, .3]], COLORS.gold, 3);
    s += `<g id="wp-pipe-left">${line(lt, '#111', 13)}${line(lt, cold, 9)}${line(lt, 'rgba(255,255,255,.55)', 3, `class="wp-flow ${flowClass}"`)}</g>`;
    s += `<g id="wp-cable">${line([[-G.pipeLen, G.cableY, G.pipeZ], [0, G.cableY, G.pipeZ]], COLORS.elec, 3)}</g>`;
    return s;
  }

  /* Uitgewerkte stijl: verlopen, lamellen met diepte, gaaspaneel met lamellenpakket, schaduw. */
  function detailed(P, { hot, cold, flowClass = '', id = 'wp' }) {
    const { pts, poly, line, circ } = mk(P), G = GEO;
    const sc = (p) => P(...p);
    let d = '', s = '';
    d += `<linearGradient id="${id}-front" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2d3137"/><stop offset="1" stop-color="#16181b"/></linearGradient>`;
    d += `<linearGradient id="${id}-fin" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#4a4f58"/><stop offset=".35" stop-color="#2f333a"/><stop offset="1" stop-color="#1a1c20"/></linearGradient>`;
    d += `<linearGradient id="${id}-top" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#5a6069"/><stop offset="1" stop-color="#3a3e45"/></linearGradient>`;
    d += `<linearGradient id="${id}-side" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#30343a"/><stop offset="1" stop-color="#1d1f23"/></linearGradient>`;
    d += `<linearGradient id="${id}-coil" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#8a714a"/><stop offset="1" stop-color="#4a3c27"/></linearGradient>`;
    d += `<linearGradient id="${id}-gold" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#a8842f"/><stop offset=".5" stop-color="#ecd08a"/><stop offset="1" stop-color="#b8923a"/></linearGradient>`;
    d += `<radialGradient id="${id}-hub" cx=".35" cy=".35" r=".8"><stop offset="0" stop-color="#4b5058"/><stop offset="1" stop-color="#1d1f23"/></radialGradient>`;
    d += `<filter id="${id}-blur" x="-20%" y="-50%" width="140%" height="200%"><feGaussianBlur stdDeviation="9"/></filter>`;

    // Pijp: cilinder met schaduw, kleur en glanslijn; buitenste uiteinde loopt uit (doorlopende leiding).
    // near = bij de unit, far = buiten. flowReverse: stroming van far naar near.
    const pipe = (pid, near, far, col, flow, flowReverse = false) => {
      const a = sc(near), b = sc(far);
      const ff = [a[0] + (b[0] - a[0]) * .7, a[1] + (b[1] - a[1]) * .7];
      const ext = [b[0] + (b[0] - a[0]) * .2, b[1] + (b[1] - a[1]) * .2];
      d += `<linearGradient id="${pid}-fade" gradientUnits="userSpaceOnUse" x1="${f1(ff[0])}" y1="${f1(ff[1])}" x2="${f1(b[0])}" y2="${f1(b[1])}"><stop offset="0" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>`;
      d += `<mask id="${pid}-mask" maskUnits="userSpaceOnUse" x="-2000" y="-2000" width="5000" height="5000"><rect x="-2000" y="-2000" width="5000" height="5000" fill="#fff"/><line x1="${f1(ff[0])}" y1="${f1(ff[1])}" x2="${f1(ext[0])}" y2="${f1(ext[1])}" stroke="#000" stroke-width="34"/><line x1="${f1(ff[0])}" y1="${f1(ff[1])}" x2="${f1(b[0])}" y2="${f1(b[1])}" stroke="url(#${pid}-fade)" stroke-width="34"/></mask>`;
      const L = (dy, c, w, extra = '', rev = false) => { const [p, q] = rev ? [b, a] : [a, b]; return `<line x1="${f1(p[0])}" y1="${f1(p[1] + dy)}" x2="${f1(q[0])}" y2="${f1(q[1] + dy)}" stroke="${c}" stroke-width="${w}" ${extra}/>`; };
      return `<g id="${pid}" mask="url(#${pid}-mask)">${L(0, '#0b0c0e', 15)}${L(0.5, 'rgba(0,0,0,.35)', 12)}${L(0, col, 11)}${L(-1.5, 'rgba(255,255,255,.18)', 5)}${L(-3.2, 'rgba(255,255,255,.55)', 1.6, 'stroke-linecap="round"')}${L(0, 'rgba(255,255,255,.6)', 3, `class="wp-flow ${flow}"`, flowReverse)}</g>`;
    };

    // Grondschaduw
    const sh = [[-4, -10, 8], [W + 6, -10, 8], [W + 6, -10, -D - 6], [-4, -10, -D - 6]];
    s += `<polygon points="${pts(sh)}" fill="rgba(0,0,0,.45)" filter="url(#${id}-blur)"/>`;

    // Rechterleiding (komt achter de unit vandaan)
    s += pipe(`${id}-pipe-right`, [W / 2, G.pipeY, G.pipeZ], [W + G.pipeLen, G.pipeY, G.pipeZ], hot, flowClass);

    // Voeten: rubber blokken met aluminium rail
    [8, W - 22].forEach(x => {
      s += poly([[x, -10, -D - 2], [x, -10, 5], [x, 0, 5], [x, 0, -D - 2]], '#0b0c0d');
      s += poly([[x, -10, 5], [x + 14, -10, 5], [x + 14, 0, 5], [x, 0, 5]], '#18191b');
      s += poly([[x, 0, 0], [x + 14, 0, 0], [x + 14, 0, 5], [x, 0, 5]], '#232427');
      s += poly([[x + 4, 0.1, 0], [x + 10, 0.1, 0], [x + 10, 0.1, 5], [x + 4, 0.1, 5]], '#9aa0a8');
      s += line([[x + 4, -2, 5.05], [x + 10, -2, 5.05]], 'rgba(255,255,255,.12)', 1);
    });

    // Zijpaneel met gaaspatroon en zichtbaar lamellenpakket erachter
    s += poly([[0, 0, 0], [0, 0, -D], [0, H, -D], [0, H, 0]], `url(#${id}-side)`);
    const cols = 7, rows = 12, z0 = -2.5, zw = (D - 5) / cols, y0 = 3.5, rh = (H - 9) / rows;
    let seed = 7; const rnd = () => (seed = (seed * 9301 + 49297) % 233280) / 233280;
    for (let i = 0; i < cols; i++) for (let j = -1; j < rows; j++) {
      const off = (i % 2) * 0.5, ya = y0 + (j + off + 0.1) * rh, yb = ya + rh * (0.72 + rnd() * 0.12);
      const lo = Math.max(ya, y0), hi = Math.min(yb, H - 5.5); if (hi - lo < 1.5) continue;
      const za = z0 - i * zw - zw * 0.14, zb = za - zw * (0.62 + rnd() * 0.08);
      s += poly([[-0.05, lo, za], [-0.05, lo, zb], [-0.05, hi, zb], [-0.05, hi, za]], `url(#${id}-coil)`, 'stroke="rgba(0,0,0,.5)" stroke-width=".6"');
    }
    s += line([[-0.1, 2, -D / 2], [-0.1, H - 4, -D / 2]], '#15171a', 2);
    s += line([[0, 0, 0], [0, H, 0]], 'rgba(255,255,255,.10)', 1.2);

    // Voorkant
    s += poly([[0, 0, 0], [W, 0, 0], [W, H, 0], [0, H, 0]], `url(#${id}-front)`);
    // Ventilator (verzonken, achter de lamellen)
    const { fanCx: fx, fanCy: fy, fanR: fr } = G;
    s += poly(circ(fx, fy, fr * 1.04, 0.05), '#0c0d0f', 'stroke="#3b4048" stroke-width="1.5"');
    s += `<g id="${id}-fan">${blades(P, 0.3, true)}</g>`;
    [0.35, 0.55, 0.75, 0.95].forEach(k => s += line([...circ(fx, fy, fr * k, -0.1, 64), circ(fx, fy, fr * k, -0.1, 64)[0]], 'rgba(120,127,137,.6)', 0.8));
    for (let k = 0; k < 8; k++) { const t = k * Math.PI / 4 + 0.2; s += line([[fx, fy, -0.1], [fx + fr * Math.cos(t), fy + fr * Math.sin(t), -0.1]], 'rgba(120,127,137,.6)', 0.8); }
    s += poly(circ(fx, fy, fr * 0.19, 0.1), `url(#${id}-hub)`);
    // Verticale lamellen met diepte
    for (let x = 3; x < W - 3; x += 3.0) {
      s += poly([[x, 2, 0], [x, 2, 0.8], [x, H - 4, 0.8], [x, H - 4, 0]], '#0f1012');
      s += poly([[x, 2, 0.8], [x + 1.7, 2, 0.8], [x + 1.7, H - 4, 0.8], [x, H - 4, 0.8]], `url(#${id}-fin)`);
    }
    // Deksel met overstek
    s += poly([[-1, H - 3, 1.5], [W + 1, H - 3, 1.5], [W + 1, H + 1.5, 1.5], [-1, H + 1.5, 1.5]], '#2b2f34');
    s += poly([[-1, H - 3, 1.5], [-1, H - 3, -D - 1], [-1, H + 1.5, -D - 1], [-1, H + 1.5, 1.5]], '#24272b');
    s += poly([[-1, H + 1.5, 1.5], [W + 1, H + 1.5, 1.5], [W + 1, H + 1.5, -D - 1], [-1, H + 1.5, -D - 1]], `url(#${id}-top)`);
    s += line([[-1, H + 1.5, 1.5], [W + 1, H + 1.5, 1.5]], 'rgba(255,255,255,.22)', 1.2);
    s += line([[-1, H + 1.5, 1.5], [-1, H + 1.5, -D - 1]], 'rgba(255,255,255,.14)', 1);
    // Renson-herkenning: goud streepje
    s += poly([[W - 27, H - 7.5, 0.9], [W - 9, H - 7.5, 0.9], [W - 9, H - 5.8, 0.9], [W - 27, H - 5.8, 0.9]], `url(#${id}-gold)`);

    // Doorvoerrubbers, linkerleiding en kabel
    const grommet = (y, r) => { const c = []; for (let k = 0; k < 32; k++) { const t = k / 32 * 2 * Math.PI; c.push([-0.2, y + r * Math.sin(t), G.pipeZ + r * Math.cos(t)]); } return poly(c, '#0b0c0d', 'stroke="#2e3136" stroke-width="1"'); };
    s += grommet(G.pipeY, 3.6) + grommet(G.cableY, 2.2);
    s += pipe(`${id}-pipe-left`, [0, G.pipeY, G.pipeZ], [-G.pipeLen, G.pipeY, G.pipeZ], cold, flowClass, true);
    {
      const c0 = sc([0, G.cableY, G.pipeZ]), c1 = sc([-G.pipeLen, G.cableY, G.pipeZ]);
      const cf = [c0[0] + (c1[0] - c0[0]) * .7, c0[1] + (c1[1] - c0[1]) * .7];
      d += `<linearGradient id="${id}-cable-fade" gradientUnits="userSpaceOnUse" x1="${f1(cf[0])}" y1="${f1(cf[1])}" x2="${f1(c1[0])}" y2="${f1(c1[1])}"><stop offset="0" stop-color="${COLORS.elec}"/><stop offset="1" stop-color="${COLORS.elec}" stop-opacity="0"/></linearGradient>`;
      d += `<linearGradient id="${id}-cable-fade-d" gradientUnits="userSpaceOnUse" x1="${f1(cf[0])}" y1="${f1(cf[1])}" x2="${f1(c1[0])}" y2="${f1(c1[1])}"><stop offset="0" stop-color="#3a2c0a"/><stop offset="1" stop-color="#3a2c0a" stop-opacity="0"/></linearGradient>`;
      const ln2 = (p, q, c, w) => `<line x1="${f1(p[0])}" y1="${f1(p[1])}" x2="${f1(q[0])}" y2="${f1(q[1])}" stroke="${c}" stroke-width="${w}"/>`;
      s += `<g id="${id}-cable">${ln2(c0, cf, '#3a2c0a', 5.5)}${ln2(cf, c1, `url(#${id}-cable-fade-d)`, 5.5)}${ln2(c0, cf, COLORS.elec, 3.5)}${ln2(cf, c1, `url(#${id}-cable-fade)`, 3.5)}${ln2([c0[0], c0[1] - 1], [cf[0], cf[1] - 1], 'rgba(255,255,255,.35)', 0.8)}</g>`;
    }
    return { defs: d, body: s };
  }

  return { GEO, COLORS, makeProjection, anchors, blades, sketch, detailed };
})();
