// look.js: WORDS ARE FOSSILS. Letterpress and engraving: bone stock, four inks, ink squeeze, deboss, line-screen tints.
// Oxblood and black print as dot screens; slate and ochre as line screens (engraving hatch). Strata are solid ink bands.
const FONT_FILES = {
  slab: 'AlfaSlabOne.ttf',             // wood type: today's words
  roman: 'Cinzel.ttf',                 // carved Roman capitals: Latin
  black: 'UnifrakturMaguntia.ttf',     // blackletter: medieval forms
  fell: 'IMFellEnglish.ttf', fellI: 'IMFellEnglish-Italic.ttf',   // early modern print
  gara: 'EBGaramond.ttf', garaI: 'EBGaramond-Italic.ttf',          // glosses, captions
  arch: 'Archivo.ttf',                 // museum labels, gauge
};
const LOOK = {
  riso: {
    paper: '#ece3cf', cell: 7, misreg: 1.1, squeeze: 1, deboss: 1,
    inks: [
      { name: 'ochre', hex: '#c9892c', angle: 0, screen: 'line' },
      { name: 'slate', hex: '#3b4c60', angle: 45, screen: 'line' },
      { name: 'ox', hex: '#8c2c23', angle: 15 },
      { name: 'black', hex: '#1c1a17', angle: 45 },
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

