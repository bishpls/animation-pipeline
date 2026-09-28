// SO BACK: the hard-edit kit (plain Canvas2D at 1080x1920). The grammar of a hyperpop edit, as pure functions of t:
// flash frames, zoom punches, shake, RGB split, grades, grain, subject outlines, stutters, type slams.
const SB_FONTS = { dela: 'DelaGothicOne-Regular.ttf', any: 'Anybody.ttf', frak: 'UnifrakturMaguntia.ttf', arch: 'Archivo.ttf',
  ramp: 'RampartOne.ttf', big: 'BigShouldersDisplay.ttf' };
const bt = b => Math.round(beatT(b) * 1e6) / 1e6;          // time of beat b (0 = first downbeat, 0.05 s); rounded: float sums missed exact frames
const PAL = { ink: '#07060c', white: '#fbf8ff', lime: '#c8ff2e', pink: '#ff2e9a', cyan: '#2ee6ff', violet: '#7a2eff',
  gold: '#ffd84d', grey: '#9a9aa6' };

// offscreen canvases, reused per frame
const BUF = {};
function buf(name, w = W, h = H, clear = true) {
  let b = BUF[name];
  if (!b) { const c = document.createElement('canvas'); c.width = w; c.height = h; b = BUF[name] = { c, x: c.getContext('2d') }; }
  if (b.c.width !== w || b.c.height !== h) { b.c.width = w; b.c.height = h; }
  b.x.setTransform(1, 0, 0, 1, 0, 0); b.x.globalAlpha = 1; b.x.globalCompositeOperation = 'source-over'; b.x.filter = 'none';
  if (clear) b.x.clearRect(0, 0, b.c.width, b.c.height);
  return b;
}

// a zoom punch: 1 + amt on the beat, easing back over `d` seconds (use with cam/translate around the subject)
const punch = (t, t0, amt = .12, d = .22) => (t < t0 || t > t0 + d ? 1 : 1 + amt * (1 - E.out3((t - t0) / d)));
// the latest event time <= t in a list
const last = (t, ts) => { let r = -1e9; for (const x of ts) if (x <= t && x > r) r = x; return r; };

// RGB split: redraw canvas `src` with its red and blue channels pushed apart by (dx, dy) px, onto X. Each channel is scaled up
// about the centre just enough (1 + 2|d|/size) that its shifted copy still covers the frame: no coloured bars at the edges.
function rgbSplit(src, dx, dy = 0) {
  dx *= .6; dy *= .6;                                          // (the rough cut's critique: the split read as an eyesore)
  if (Math.abs(dx) < .5 && Math.abs(dy) < .5) { X.drawImage(src, 0, 0); return; }
  const c = buf('rgbc'), sx = 1 + 2 * Math.abs(dx) / W, sy = 1 + 2 * Math.abs(dy) / H, s = Math.max(sx, sy);
  X.save(); X.setTransform(1, 0, 0, 1, 0, 0); X.fillStyle = '#000'; X.fillRect(0, 0, W, H); X.globalCompositeOperation = 'lighter';
  for (const [col, ox, oy] of [['#f00', -dx, -dy], ['#0f0', 0, 0], ['#00f', dx, dy]]) {
    c.x.clearRect(0, 0, W, H);
    const k = col === '#0f0' ? 1 : s;
    c.x.setTransform(k, 0, 0, k, W / 2 * (1 - k) + ox, H / 2 * (1 - k) + oy); c.x.drawImage(src, 0, 0); c.x.setTransform(1, 0, 0, 1, 0, 0);
    c.x.globalCompositeOperation = 'multiply'; c.x.fillStyle = col; c.x.fillRect(0, 0, W, H);
    c.x.globalCompositeOperation = 'source-over';
    X.drawImage(c.c, 0, 0);
  }
  X.restore();
}

// film grain: a noise tile regenerated per frame (seeded by frame), overlaid
function grain(t, amt = .08, size = 256) {
  const f = Math.floor(t * FPS), g = buf('grain', size, size, false);
  if (g.f !== f) {
    const d = g.x.createImageData(size, size), a = d.data;
    let s = (f * 9301 + 49297) >>> 0;
    for (let i = 0; i < a.length; i += 4) { s = (s * 1664525 + 1013904223) >>> 0; const v = s >>> 24; a[i] = a[i + 1] = a[i + 2] = v; a[i + 3] = 255; }
    g.x.putImageData(d, 0, 0); g.f = f;
  }
  X.save(); X.setTransform(1, 0, 0, 1, 0, 0); X.globalAlpha = amt; X.globalCompositeOperation = 'overlay';
  X.fillStyle = X.createPattern(g.c, 'repeat'); X.fillRect(0, 0, W, H); X.restore();
}

// a subject outline for a keyed (transparent) canvas: dilate by stamping the alpha at N offsets, tinted
function outline(src, col = '#fff', w = 10, n = 16) {
  const o = buf('outl');
  for (let i = 0; i < n; i++) { const a = i / n * TAU; o.x.drawImage(src, Math.cos(a) * w, Math.sin(a) * w); }
  o.x.globalCompositeOperation = 'source-in'; o.x.fillStyle = col; o.x.fillRect(0, 0, W, H);
  X.drawImage(o.c, 0, 0);
}

// type: the engine's glyph outlines as a Path2D (centred on x), for fills, strokes and gradients
function tpath(str, x, y, o) {
  const L = shape(str, o), x0 = o.align === 'left' ? x : o.align === 'right' ? x - L.width : x - L.width / 2;
  const p = new Path2D();
  L.glyphs.forEach((g, i) => { if (g.ch !== ' ') p.addPath(glyphPath(g, x0 + g.x, y + g.y + (o.dy ? o.dy(i) : 0))); });
  return { p, L, x0 };
}
// chrome: a hard-stop metal gradient, a dark keyline and a hot outer stroke
function chrome(str, x, y, o = {}) {
  const size = o.size || 150, { p } = tpath(str, x, y, { font: o.font || 'dela', size, track: o.track || 0, wdth: o.wdth, wght: o.wght });
  const g = X.createLinearGradient(0, y - size * .8, 0, y + size * .1);
  [[0, '#ffffff'], [.42, '#c9d3ff'], [.5, '#3a2a6e'], [.56, '#ff9ad8'], [.8, '#ffffff'], [1, '#b8fff6']].forEach(([k, c]) => g.addColorStop(k, c));
  X.save(); X.lineJoin = 'round';
  X.save(); X.translate(size * .05, size * .07); X.fillStyle = 'rgba(7,6,12,.85)'; X.strokeStyle = 'rgba(7,6,12,.85)'; X.lineWidth = size * .3; X.stroke(p); X.fill(p); X.restore();
  X.strokeStyle = PAL.ink; X.lineWidth = size * .3; X.stroke(p);
  X.strokeStyle = o.outer || PAL.pink; X.lineWidth = size * .22; X.stroke(p);
  X.strokeStyle = PAL.ink; X.lineWidth = size * .09; X.stroke(p);
  X.fillStyle = g; X.fill(p); X.restore();
}
// a plain slammed word: fill + keyline
function slam(str, x, y, o = {}) {
  const size = o.size || 120, { p } = tpath(str, x, y, { font: o.font || 'dela', size, track: o.track || 0, wdth: o.wdth, wght: o.wght, align: o.align });
  X.save(); X.lineJoin = 'round';
  if (o.stroke !== 0) { X.strokeStyle = o.stroke || PAL.ink; X.lineWidth = o.lw || size * .14; X.stroke(p); }
  X.fillStyle = o.fill || PAL.white; X.fill(p); X.restore();
}

// a slate for an unbuilt shot (name, what, time, bar, beat, section)
const SLATE_COL = { cold: PAL.pink, over: '#4a4a58', turn: PAL.violet, drop: PAL.lime, drop2: PAL.cyan, end: PAL.gold };
function slate(name, what) {
  const f = (t, lt, dur) => {
    const sec = sectionAt(t); X.fillStyle = SLATE_COL[sec] || '#333'; X.fillRect(0, 0, W, H);
    const k = pulse(t, 8);
    X.fillStyle = `rgba(255,255,255,${.25 * k})`; X.fillRect(0, 0, W, H);
    slam(name, W / 2, 820, { size: 110, fill: PAL.white });
    txt2(what, W / 2, 930);
    txt2(`${t.toFixed(2)}s  bar ${Math.floor(barPos(t)) + 1}  beat ${Math.floor(beatPos(t))}  (${sec})`, W / 2, 1010);
  };
  Object.defineProperty(f, 'name', { value: name });
  return f;
}
function txt2(s, x, y) { const { p } = tpath(s, x, y, { font: 'arch', size: 34, wght: 600 }); X.fillStyle = PAL.white; X.fill(p); }
