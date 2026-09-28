// SO BACK: the film's own look on top of engine/hardedit.js: its palette, its beat helper, its type helpers and slates.
const SB_FONTS = { dela: 'DelaGothicOne-Regular.ttf', any: 'Anybody.ttf', frak: 'UnifrakturMaguntia.ttf', arch: 'Archivo.ttf',
  ramp: 'RampartOne.ttf', big: 'BigShouldersDisplay.ttf' };
const bt = b => Math.round(beatT(b) * 1e6) / 1e6;          // time of beat b (0 = first downbeat, 0.05 s); rounded: float sums missed exact frames
const PAL = { ink: '#07060c', white: '#fbf8ff', lime: '#c8ff2e', pink: '#ff2e9a', cyan: '#2ee6ff', violet: '#7a2eff',
  gold: '#ffd84d', grey: '#9a9aa6' };

// the hard-edit grammar (buf, scene, zoomAt, punch, present, rgbSplit, grain, vignette, NEG) is engine/hardedit.js;
// SO BACK's splits run at 60% (the rough cut's critique: the split read as an eyesore)
HARDEDIT.split = .6;
const last = lastHit;

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
