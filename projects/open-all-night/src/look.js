// look.js: OPEN ALL NIGHT's visual language. Four riso inks on warm stock; cut-paper shapes; Swiss type.
// Light is paper showing through ink (knockouts). Glow is a halftoned halo. Nothing is a digital gradient.

const FONT_FILES = {
  arch: 'Archivo.ttf',                 // wdth 62–125, wght 100–900: the workhorse grotesk, condensed for hooks
  any: 'Anybody.ttf',                  // wdth 50–150: extreme width for kinetic stretch moments
  serif: 'InstrumentSerif-Italic.ttf', // the human voice: italic serif accents
  serifR: 'InstrumentSerif-Regular.ttf',
  brico: 'BricolageGrotesque.ttf',
  shoulders: 'BigShouldersDisplay.ttf',
};

const LOOK = {
  riso: {
    paper: '#f1eadb',
    cell: 9,
    misreg: 1.8,
    inks: [
      { name: 'blue', hex: '#3148d0', angle: 15 },    // night, the machine
      { name: 'pink', hex: '#ff4d9d', angle: 75 },    // fluorescent pink: the neon, joy
      { name: 'yellow', hex: '#ffcc22', angle: 0 },   // lamplight, windows
      { name: 'black', hex: '#1d1a22', angle: 45 },   // key: silhouettes, type
    ],
  },
};

// ------------------------------------------------------------------ geometry
const pt = (x, y) => [x, y];
function circle(cx, cy, r, n = 64, a0 = 0) { const p = []; for (let i = 0; i < n; i++) { const a = a0 + i / n * TAU; p.push([cx + Math.cos(a) * r, cy + Math.sin(a) * r]); } return p; }
function ellipse(cx, cy, rx, ry, rot = 0, n = 64) { const p = []; const c = Math.cos(rot), s = Math.sin(rot); for (let i = 0; i < n; i++) { const a = i / n * TAU, x = Math.cos(a) * rx, y = Math.sin(a) * ry; p.push([cx + x * c - y * s, cy + x * s + y * c]); } return p; }
function rect(x, y, w, h) { return [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]; }
function rrect(x, y, w, h, r, n = 6) {
  const p = [], cs = [[x + w - r, y + r, -Math.PI / 2], [x + w - r, y + h - r, 0], [x + r, y + h - r, Math.PI / 2], [x + r, y + r, Math.PI]];
  for (const [cx, cy, a0] of cs) for (let i = 0; i <= n; i++) { const a = a0 + i / n * Math.PI / 2; p.push([cx + Math.cos(a) * r, cy + Math.sin(a) * r]); }
  return p;
}
function arcPts(cx, cy, r, a0, a1, n = 24) { const p = []; for (let i = 0; i <= n; i++) { const a = lerp(a0, a1, i / n); p.push([cx + Math.cos(a) * r, cy + Math.sin(a) * r]); } return p; }
const tx = (pts, dx, dy) => pts.map(([x, y]) => [x + dx, y + dy]);
const sc = (pts, s, cx = 0, cy = 0, sy = s) => pts.map(([x, y]) => [cx + (x - cx) * s, cy + (y - cy) * sy]);
const rot = (pts, a, cx = 0, cy = 0) => { const c = Math.cos(a), s = Math.sin(a); return pts.map(([x, y]) => [cx + (x - cx) * c - (y - cy) * s, cy + (x - cx) * s + (y - cy) * c]); };

// Hand-cut edges: every edge is subdivided and wanders a little (stable per shape), and boils per drawing.
// amp = wander in px, boil = per-drawing jitter in px. seed makes each piece of paper its own.
function cut(pts, seed = 0, amp = 1.6, boil = .7, step = 26) {
  const out = [], n = pts.length;
  let s = 0;
  for (let i = 0; i < n; i++) {
    const a = pts[i], b = pts[(i + 1) % n], L = Math.hypot(b[0] - a[0], b[1] - a[1]);
    const m = Math.max(1, Math.ceil(L / step)), nx = -(b[1] - a[1]) / (L || 1), ny = (b[0] - a[0]) / (L || 1);
    for (let k = 0; k < m; k++) {
      const u = k / m, d = noise1(seed * 7.31 + (s + u * L) / 70) * amp + jit(seed * 31 + i * 7 + k, boil, NOW);
      out.push([lerp(a[0], b[0], u) + nx * d, lerp(a[1], b[1], u) + ny * d]);
    }
    s += L;
  }
  return out;
}
// a thick hand-drawn line (open polyline) as a filled ribbon: w0 -> w1 taper
function ribbon(pts, w0, w1 = w0, seed = 0) {
  const L = [], R = [], n = pts.length;
  for (let i = 0; i < n; i++) {
    const a = pts[Math.max(0, i - 1)], b = pts[Math.min(n - 1, i + 1)], d = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
    const nx = -(b[1] - a[1]) / d, ny = (b[0] - a[0]) / d, w = lerp(w0, w1, i / (n - 1)) / 2 + jit(seed + i, .5, NOW);
    L.push([pts[i][0] + nx * w, pts[i][1] + ny * w]); R.push([pts[i][0] - nx * w, pts[i][1] - ny * w]);
  }
  return L.concat(R.reverse());
}

// ------------------------------------------------------------------ neon
// Neon printed on a night flood: blue knocked back around the tube (the light), a halftoned pink halo,
// the tube in solid ink, and a paper-white hot core. on = 0..1 brightness (flicker), 0 = dead glass.
function neon(pathPts, w, on = 1, o = {}) {
  const col = o.ink || 'pink', flood = o.flood || 'blue', p = P(pathPts, false);
  const pass = (name, mode, blur, width, a) => {
    const c = layer(name); c.save(); c.globalCompositeOperation = mode; c.filter = blur ? `blur(${blur}px)` : 'none';
    c.strokeStyle = `rgba(0,0,0,${a})`; c.lineWidth = width; c.lineCap = c.lineJoin = 'round'; c.stroke(p); c.restore();
  };
  if (on > .02) {
    const dark = o.darkInks || [flood, 'black'];
    for (const d of dark) { pass(d, 'destination-out', w * 2.4, w * 4.5, .55 * on); pass(d, 'destination-out', w * .8, w * 2.2, on); }
    pass(col, 'source-over', w * 1.3, w * 3.4, .62 * on);                       // halo: dense near the glass, dots dissolving outward
    pass(col, 'source-over', w * 3.5, w * 7, .28 * on);
  }
  ink(p, { [col]: 1 }, { stroke: w });
  if (on > .5) knock(p, [col], 1, { stroke: w * .26 });                        // the hot core: a hard paper-white line (a partial knock would halftone the tube)
  else ink(p, { black: .6 }, { stroke: w * .72 });                               // dead glass
}

// The OPEN sign. Letters are monoline tube paths in a unit box (cap height 1). (cx, cy) = centre; s = cap height px.
const SIGN_LETTERS = {
  O: () => ellipse(.31, 0, .31, .5, 0, 48).concat([[.62, 0]]),
  P: () => [[0, .5], [0, -.5], [.22, -.5]].concat(arcPts(.22, -.22, .28, -Math.PI / 2, Math.PI / 2, 16)).concat([[0, .06]]),
  E: () => [[.5, -.5], [0, -.5], [0, .5], [.5, .5]],
  E2: () => [[0, 0], [.4, 0]],
  N: () => [[0, .5], [0, -.5], [.52, .5], [.52, -.5]],
};
function openSign(cx, cy, s, on = [1, 1, 1, 1], o = {}) {
  const w = s * .12, gap = s * .2, widths = [.62, .5, .5, .52];
  const total = widths.reduce((a, b) => a + b, 0) * s + gap * 3;
  let x = cx - total / 2;
  const L = (f) => f().map(([u, v]) => [x + u * s, cy + v * s]);
  ['O', 'P', 'E', 'N'].forEach((ch, i) => {
    neon(L(SIGN_LETTERS[ch]), w, on[i], o);
    if (ch === 'E') neon(L(SIGN_LETTERS.E2), w, on[i], o);
    x += widths[i] * s + gap;
  });
  if (o.border != null) {        // the classic rounded border tube, in a second ink
    const bw = total + s * .9, bh = s * 1.75;
    neon(rrect(cx - bw / 2, cy - bh / 2, bw, bh, s * .22, 8).concat([[cx + bw / 2 - s * .22, cy - bh / 2]]), w * .8, o.border, { ...o, ink: o.borderInk || 'yellow' });
  }
  return total;
}
