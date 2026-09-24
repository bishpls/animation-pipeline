// pop.js: the chibi register's drawing kit (Canvas2D, plain mode). PSG rules: thick ink outlines, flat fills,
// bold graphic backgrounds, no gradients (except light effects), drawings held on twos.
const C_ = {
  clay: '#D97757', clayD: '#B4563A', clayL: '#EE9A78', cream: '#F6E7C8', creamD: '#E3C99A', ink: '#1B1418',
  pink: '#FF4FA3', pinkD: '#D6307F', cyan: '#38E0F0', cyanD: '#16A9C2', lemon: '#FFE45C', lemonD: '#F2B92F',
  night: '#2A1B4A', nightD: '#170E2C', violet: '#7B4BFF', white: '#FFFDF7', skin: '#FFE2CF', skinD: '#F2B9A0', boot: '#FFFFFF', bootD: '#D9DDE8',
  hem: '#4A2A22', eye: '#F4B81E', eyeD: '#C27A0B', green: '#6EDC7A',
};
const FONT_FILES = {
  round: 'MPLUSRounded1c-Black.ttf', roundB: 'MPLUSRounded1c-ExtraBold.ttf', dela: 'DelaGothicOne-Regular.ttf',
  mochi: 'MochiyPopOne.ttf', rampart: 'RampartOne.ttf', mono: 'Archivo.ttf', arch: 'Archivo.ttf',
};
const LW = 7;                       // the house line weight at 1x

// ------------------------------------------------------------------ geometry (pure)
function circle(cx, cy, r, n = 48, a0 = 0) { const p = []; for (let i = 0; i < n; i++) { const a = a0 + i / n * TAU; p.push([cx + Math.cos(a) * r, cy + Math.sin(a) * r]); } return p; }
function ellipse(cx, cy, rx, ry, rot = 0, n = 48) { const p = [], c = Math.cos(rot), s = Math.sin(rot); for (let i = 0; i < n; i++) { const a = i / n * TAU, x = Math.cos(a) * rx, y = Math.sin(a) * ry; p.push([cx + x * c - y * s, cy + x * s + y * c]); } return p; }
function rect(x, y, w, h) { return [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]; }
function rrect(x, y, w, h, r, n = 5) {
  r = Math.min(r, w / 2, h / 2); const p = [], cs = [[x + w - r, y + r, -Math.PI / 2], [x + w - r, y + h - r, 0], [x + r, y + h - r, Math.PI / 2], [x + r, y + r, Math.PI]];
  for (const [cx, cy, a0] of cs) for (let i = 0; i <= n; i++) { const a = a0 + i / n * Math.PI / 2; p.push([cx + Math.cos(a) * r, cy + Math.sin(a) * r]); }
  return p;
}
function star(cx, cy, r, ri, n = 5, rot = -Math.PI / 2) { const p = []; for (let i = 0; i < n * 2; i++) { const a = rot + i / (n * 2) * TAU, rr = i % 2 ? ri : r; p.push([cx + Math.cos(a) * rr, cy + Math.sin(a) * rr]); } return p; }
function blob(cp, n = 6) {          // Catmull-Rom closed curve through control points
  const out = [], m = cp.length;
  for (let i = 0; i < m; i++) {
    const p0 = cp[(i - 1 + m) % m], p1 = cp[i], p2 = cp[(i + 1) % m], p3 = cp[(i + 2) % m];
    for (let k = 0; k < n; k++) { const t = k / n, t2 = t * t, t3 = t2 * t; out.push([0, 1].map(j => .5 * (2 * p1[j] + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2 + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3))); }
  }
  return out;
}
const tx = (pts, dx, dy) => pts.map(([x, y]) => [x + dx, y + dy]);
function P(pts, close = true) { if (pts instanceof Path2D) return pts; const p = new Path2D(); if (!pts.length) return p; p.moveTo(pts[0][0], pts[0][1]); for (let i = 1; i < pts.length; i++) p.lineTo(pts[i][0], pts[i][1]); if (close) p.closePath(); return p; }
// boil: a tiny per-drawing wobble on outlines (hand-drawn life). amp in px.
function wob(pts, seed, amp = 1.2) { return pts.map(([x, y], i) => [x + jit(seed * 97 + i * 3.1, amp), y + jit(seed * 57 + i * 7.3, amp)]); }

// ------------------------------------------------------------------ drawing
// fill + outside outline in one call: the PSG shape
function shp(pts, fill, lw = LW, ink = C_.ink, o = {}) {
  const p = P(pts, o.close !== false);
  X.lineJoin = 'round'; X.lineCap = 'round';
  if (lw > 0 && ink) { X.strokeStyle = ink; X.lineWidth = lw * 2; X.stroke(p); }
  if (fill) { X.fillStyle = fill; X.fill(p); }
  if (o.inner) { X.strokeStyle = ink; X.lineWidth = o.inner; X.stroke(p); }
  return p;
}
const fil = (pts, fill) => { X.fillStyle = fill; X.fill(P(pts)); };
function lin(pts, w, col = C_.ink, o = {}) { X.lineJoin = 'round'; X.lineCap = o.cap || 'round'; X.strokeStyle = col; X.lineWidth = w; if (o.dash) X.setLineDash(o.dash); X.stroke(P(pts, false)); if (o.dash) X.setLineDash([]); }
function clipTo(pts, fn) { X.save(); X.clip(P(pts)); fn(); X.restore(); }
function cam(cx, cy, zoom = 1, rot = 0) { X.translate(W / 2, H / 2); X.rotate(rot); X.scale(zoom, zoom); X.translate(-cx, -cy); }
function shake(t, amt, freq = 30) { return [amt * noise1(t * freq), amt * noise1(t * freq + 77)]; }

// ------------------------------------------------------------------ backgrounds
function flat(col) { X.save(); X.setTransform(1, 0, 0, 1, 0, 0); X.fillStyle = col; X.fillRect(0, 0, W, H); X.restore(); }
function sunburst(cx, cy, a, b, n = 20, rot = 0, R = 3000) {
  X.fillStyle = a; X.fillRect(-R, -R, R * 3, R * 3);
  X.fillStyle = b; X.beginPath();
  for (let i = 0; i < n; i++) { const a0 = rot + i / n * TAU, a1 = a0 + TAU / n / 2; X.moveTo(cx, cy); X.lineTo(cx + Math.cos(a0) * R, cy + Math.sin(a0) * R); X.lineTo(cx + Math.cos(a1) * R, cy + Math.sin(a1) * R); X.closePath(); }
  X.fill();
}
function checker(size, a, b, rot = 0, sx = 0, sy = 0) {
  X.save(); X.setTransform(1, 0, 0, 1, 0, 0); X.fillStyle = a; X.fillRect(0, 0, W, H);
  X.translate(W / 2, H / 2); X.rotate(rot); X.fillStyle = b;
  const n = Math.ceil(Math.hypot(W, H) / size / 2) + 2, ox = ((sx % (size * 2)) + size * 2) % (size * 2), oy = ((sy % (size * 2)) + size * 2) % (size * 2);
  X.beginPath();
  for (let i = -n; i <= n; i++) for (let j = -n; j <= n; j++) if ((i + j) % 2 === 0) X.rect(i * size + ox - size * 2, j * size + oy - size * 2, size, size);
  X.fill(); X.restore();
}
function dots(col, spacing = 26, r = 5, rot = .4, fade = null) {   // halftone field; fade(x, y) -> 0..1 scales the dot
  X.save(); X.setTransform(1, 0, 0, 1, 0, 0); X.fillStyle = col; X.beginPath();
  const c = Math.cos(rot), s = Math.sin(rot), n = Math.ceil(Math.hypot(W, H) / spacing);
  for (let i = -n; i <= n; i++) for (let j = -n; j <= n; j++) {
    const x = W / 2 + (i * c - j * s) * spacing, y = H / 2 + (i * s + j * c) * spacing;
    if (x < -20 || y < -20 || x > W + 20 || y > H + 20) continue;
    const k = fade ? fade(x, y) : 1; if (k <= .02) continue;
    X.moveTo(x + r * k, y); X.arc(x, y, r * k, 0, TAU);
  }
  X.fill(); X.restore();
}
function stripes(a, b, w = 60, rot = -.5, scroll = 0) {
  X.save(); X.setTransform(1, 0, 0, 1, 0, 0); X.fillStyle = a; X.fillRect(0, 0, W, H); X.translate(W / 2, H / 2); X.rotate(rot); X.fillStyle = b;
  const n = Math.ceil(Math.hypot(W, H) / w); X.beginPath();
  for (let i = -n; i <= n; i += 2) X.rect(i * w + (scroll % (w * 2)), -2000, w, 4000);
  X.fill(); X.restore();
}
function speedLines(cx, cy, col = C_.white, n = 60, seed = 0, rIn = 380, alpha = 1) {    // radial focus lines
  X.save(); X.setTransform(1, 0, 0, 1, 0, 0); X.globalAlpha = alpha; X.fillStyle = col;
  const b = BF(NOW);
  for (let i = 0; i < n; i++) {
    const a = hash(seed + i * 1.7 + b * .13) * TAU, w = .004 + hash(i * 3.3 + b) * .012, r0 = rIn * (.8 + hash(i + b * 7) * .6);
    X.beginPath(); X.moveTo(cx + Math.cos(a) * r0, cy + Math.sin(a) * r0);
    X.lineTo(cx + Math.cos(a - w) * 2600, cy + Math.sin(a - w) * 2600); X.lineTo(cx + Math.cos(a + w) * 2600, cy + Math.sin(a + w) * 2600); X.fill();
  }
  X.restore();
}

// ------------------------------------------------------------------ effects
function sparkle(x, y, r, col = C_.white, rot = 0, lw = 0) { const p = star(x, y, r, r * .22, 4, rot); if (lw) shp(p, col, lw); else fil(p, col); }
function spark8(x, y, r, col = C_.lemon, lw = 4, rot = 0) { shp(star(x, y, r, r * .38, 8, rot), col, lw); }     // the Claude spark
function confetti(t, seed, n = 60, cols = [C_.pink, C_.lemon, C_.cyan, C_.cream, C_.clay], t0 = 0, spread = 1) {
  const age = t - t0; if (age < 0) return;
  for (let i = 0; i < n; i++) {
    const R = hash(seed + i * 9.1), x0 = W / 2 + (hash(seed + i * 3.7) - .5) * W * 1.4 * spread, vy = 180 + R * 260, sw = hash(i * 5.3 + seed);
    const y = -60 - hash(i * 7.9 + seed) * H * .8 + vy * age, x = x0 + Math.sin(age * (2 + sw * 3) + i) * 40;
    if (y > H + 40) continue;
    X.save(); X.translate(x, y); X.rotate(age * (3 + sw * 5) + i); X.scale(1, Math.cos(age * (5 + sw * 4) + i));
    X.fillStyle = cols[i % cols.length]; X.fillRect(-9, -5, 18, 10); X.restore();
  }
}
function flash(k, col = '#fff') { if (k <= 0) return; X.save(); X.setTransform(1, 0, 0, 1, 0, 0); X.globalAlpha = clamp(k); X.fillStyle = col; X.fillRect(0, 0, W, H); X.restore(); }
function glow(x, y, r, col, a = .8) { const g = X.createRadialGradient(x, y, 0, x, y, r); g.addColorStop(0, col); g.addColorStop(1, 'rgba(0,0,0,0)'); X.save(); X.globalAlpha = a; X.globalCompositeOperation = 'lighter'; X.fillStyle = g; X.fillRect(x - r, y - r, r * 2, r * 2); X.restore(); }

// ------------------------------------------------------------------ type (fontkit outlines, drawn into X)
// pop(str, x, y, { font, size, fill, stroke, lw, align, track, per(g, i, n) -> {dx, dy, sc, rot, fill, skip} , shadow:[dx,dy,col] })
function pop(str, x, y, o = {}) {
  const L = o.L || shape(str, { font: o.font || 'round', size: o.size || 100, track: o.track || 0, wdth: o.wdth, wght: o.wght, space: o.space });
  const x0 = o.align === 'center' ? x - L.width / 2 : o.align === 'right' ? x - L.width : x;
  const n = L.glyphs.length, paths = [];
  L.glyphs.forEach((g, i) => {
    if (g.ch === ' ') return;
    const a = o.per ? o.per(g, i, n) || {} : {};
    if (a.skip) return;
    paths.push([glyphPath(g, x0 + g.x + (a.dx || 0), y + g.y + (a.dy || 0), a.sc ?? 1, a.rot || 0), a.fill || o.fill || C_.cream]);
  });
  X.lineJoin = 'round';
  if (o.shadow) { X.save(); X.translate(o.shadow[0], o.shadow[1]); X.fillStyle = o.shadow[2]; for (const [p] of paths) { if (o.lw !== 0) { X.strokeStyle = o.shadow[2]; X.lineWidth = (o.lw ?? o.size * .09) * 2; X.stroke(p); } X.fill(p); } X.restore(); }
  if (o.lw !== 0) { X.strokeStyle = o.stroke || C_.ink; X.lineWidth = (o.lw ?? (o.size || 100) * .09) * 2; for (const [p] of paths) X.stroke(p); }
  for (const [p, f] of paths) { X.fillStyle = f; X.fill(p); }
  return { x0, x1: x0 + L.width, w: L.width, L };
}
// a slam: scale 1.6 -> 1 with overshoot over .14 s, starting at t0
const slamK = (t, t0, d = .14) => (t < t0 ? 0 : 1 + .6 * (1 - E.back(clamp((t - t0) / d))));

// ------------------------------------------------------------------ images (keys: chroma-keyed PNGs), rig-drawn
const IMG = {};
function loadImg(name, url) { return new Promise((ok, bad) => { const i = new Image(); i.onload = () => { IMG[name] = i; ok(); }; i.onerror = () => bad(new Error('img ' + url)); i.src = url; }); }
// Draw an illustration with a cheap Live2D-ish warp: horizontal strips offset by a sway field (hair/cloth move more
// the higher up / further from the anchor), plus breathing (a vertical stretch between two lines).
// o: { t, sway: px, swayFreq, anchorY (0..1, the still line: hips), breath: 0..1 amp, x, y, h (height in px), flip, alpha }
function rig(name, cx, cy, h, o = {}) {
  const img = IMG[name]; if (!img) return;
  const s = h / img.height, w = img.width * s, t = o.t ?? NOW;
  const strips = 90, sh = img.height / strips, ay = o.anchorY ?? .62;
  X.save(); X.translate(cx, cy); if (o.rot) X.rotate(o.rot); if (o.flip) X.scale(-1, 1); if (o.alpha != null) X.globalAlpha = o.alpha;
  const br = (o.breath ?? .006) * Math.sin(t * TAU * (o.breathHz ?? .45));
  let yAcc = -h / 2;
  for (let i = 0; i < strips; i++) {
    const v = (i + .5) / strips, d = Math.abs(v - ay) / Math.max(ay, 1 - ay);
    const sway = (o.sway ?? 6) * d * d * Math.sin(t * TAU * (o.swayFreq ?? .6) - v * 2.2) + (o.swayB ?? 0) * d * Math.sin(t * TAU * 1.7 + v * 5);
    const stretch = 1 + (v < ay ? br * 1.5 : 0);
    const dh = sh * s * stretch;
    X.drawImage(img, 0, i * sh, img.width, sh + .6, -w / 2 + sway, yAcc + (v < ay ? -br * h * .4 : 0), w, dh + .8);
    yAcc += sh * s;
  }
  X.restore();
}
