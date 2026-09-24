// engine/type.js: real typography as ink. Variable-font glyph outlines (fontkit) -> Path2D, kerned layout,
// per-glyph kinetic control. Text is just more shapes: it prints, knocks out, halftones and misregisters like everything else.
//
//   await loadFont('arch', '../../engine/fonts/Archivo.ttf')
//   const L = shape('KEEP IT OPEN', { font: 'arch', size: 180, wdth: 62, wght: 900, track: -.02 })
//   drawText(L, x, y, 'black', { align: 'center', per: (g, i) => ({ dy: -40 * pop, rot: .1, sc: 1, alpha: 1 }) })
//   type('hello', x, y, { font, size, ... , ink: { pink: 1 } })      one-call version
// Coordinates: (x, y) is the left/centre/right of the BASELINE. Sizes are in px (em size).

const FONTS = {};
async function loadFont(name, url) {
  const buf = await (await fetch(url)).arrayBuffer();
  const base = fontkit.create(new Uint8Array(buf));
  FONTS[name] = { base, vars: new Map(), glyphs: new Map(), axes: base.variationAxes || {} };
}
function fontInst(name, axes) {
  const F = FONTS[name]; if (!F) throw new Error('font not loaded: ' + name);
  const a = {};
  for (const [k, v] of Object.entries(axes)) if (v != null && F.axes[k]) a[k] = Math.round(clamp(v, F.axes[k].min, F.axes[k].max) * (k === 'wght' ? .2 : 1)) / (k === 'wght' ? .2 : 1);
  const key = JSON.stringify(a);
  if (!F.vars.has(key)) F.vars.set(key, Object.keys(a).length ? F.base.getVariation(a) : F.base);
  return { f: F.vars.get(key), key, F };
}
function glyphUnitPath(F, key, g) {
  const id = key + '|' + g.id;
  if (!F.glyphs.has(id)) {
    const p = new Path2D();
    for (const c of g.path.commands) {
      const a = c.args;
      if (c.command === 'moveTo') p.moveTo(a[0], -a[1]);
      else if (c.command === 'lineTo') p.lineTo(a[0], -a[1]);
      else if (c.command === 'quadraticCurveTo') p.quadraticCurveTo(a[0], -a[1], a[2], -a[3]);
      else if (c.command === 'bezierCurveTo') p.bezierCurveTo(a[0], -a[1], a[2], -a[3], a[4], -a[5]);
      else if (c.command === 'closePath') p.closePath();
    }
    F.glyphs.set(id, p);
  }
  return F.glyphs.get(id);
}
// layout a string: glyph unit paths + positions in px. track is in em.
function shape(str, o = {}) {
  const { f, key, F } = fontInst(o.font || 'arch', { wdth: o.wdth, wght: o.wght, opsz: o.opsz });
  const s = o.size || 100, k = s / f.unitsPerEm, tr = (o.track || 0) * s, sp = (o.space ?? .06) * s;
  const run = f.layout(o.upper ? str.toUpperCase() : str);
  const glyphs = []; let x = 0;
  run.glyphs.forEach((g, i) => {
    const pos = run.positions[i], adv = pos.xAdvance * k;
    const ch = String.fromCodePoint(...(g.codePoints.length ? g.codePoints : [32]));
    glyphs.push({ path: glyphUnitPath(F, key, g), x: x + pos.xOffset * k, y: -pos.yOffset * k, w: adv, ch, k, bb: g.bbox });
    x += adv + (i < run.glyphs.length - 1 ? tr : 0) + (ch === ' ' ? sp : 0);
  });
  return { glyphs, width: x, size: s, k, asc: f.ascent * k, desc: -f.descent * k, cap: (f.capHeight || f.ascent * .7) * k, xh: (f.xHeight || f.ascent * .5) * k };
}
// the Path2D of one glyph placed at (x, y) (baseline-left), scaled by sc about its centre, rotated by rot
function glyphPath(g, x, y, sc = 1, rot = 0, sx = 1) {
  const cx = x + g.w / 2, cy = y - g.k * 350;           // pivot: roughly the glyph's optical centre
  const m = new DOMMatrix().translate(cx, cy).rotate(rot / D2R).scale(sc * sx, sc).translate(-cx, -cy).translate(x, y).scale(g.k, g.k);
  const p = new Path2D(); p.addPath(g.path, m); return p;
}
// draw a laid-out run. spec = ink spec (see ink()), or o.knock = true to knock out.
// o.per(g, i, n) -> { dx, dy, rot, sc, sx, alpha, skip, spec } animates glyphs individually.
function drawText(L, x, y, spec, o = {}) {
  const x0 = o.align === 'center' ? x - L.width / 2 : o.align === 'right' ? x - L.width : x;
  const n = L.glyphs.length;
  const whole = new Path2D();
  L.glyphs.forEach((g, i) => {
    if (g.ch === ' ') return;
    const a = o.per ? o.per(g, i, n) || {} : {};
    if (a.skip || a.sc === 0) return;
    const p = glyphPath(g, x0 + g.x + (a.dx || 0), y + g.y + (a.dy || 0), a.sc ?? 1, a.rot || 0, a.sx ?? 1);
    if (a.spec || a.alpha != null) {
      const sp = a.spec || spec, al = a.alpha ?? 1;
      if (o.knock) knock(p, o.knockInks, al);
      else ink(p, typeof sp === 'string' ? { [sp]: al } : Object.fromEntries(Object.entries(sp).map(([k, v]) => [k, typeof v === 'number' ? v * al : v])));
    } else whole.addPath(p);
  });
  if (o.knock) knock(whole, o.knockInks); else if (spec) ink(whole, spec, o.stroke ? { stroke: o.stroke } : {});
  return { x0, x1: x0 + L.width, w: L.width, cap: L.cap };
}
function type(str, x, y, o = {}) { return drawText(shape(str, o), x, y, o.ink || 'black', o); }
// fit a run to a width by adjusting wdth (variable) then size
function fitShape(str, maxW, o = {}) {
  let L = shape(str, o);
  if (L.width <= maxW) return L;
  const F = FONTS[o.font || 'arch'];
  if (F.axes.wdth && o.fitWdth !== false) {
    for (let w = (o.wdth || 100) - 4; w >= F.axes.wdth.min; w -= 4) { L = shape(str, { ...o, wdth: w }); if (L.width <= maxW) return L; }
  }
  return shape(str, { ...o, size: o.size * maxW / L.width, wdth: F.axes.wdth ? F.axes.wdth.min : o.wdth });
}
