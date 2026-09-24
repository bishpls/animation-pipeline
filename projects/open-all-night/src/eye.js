// eye.js: the Eye. A Saul-Bass-style graphic eye printed in riso: paper white, an ink iris with gear-like striations,
// a black pupil, a heavy tapered lid line with lashes, a lid crease. Plus two helpers other shots can use.
//
//   const g = eye(x, y, r, o)         (x, y) = centre of the eye, r = half-width (corner to corner = 2r)
//     o.open     0..1   upper lid (1 = open, 0 = shut)            o.squint 0..1  lower lid rises (a smile / wink)
//     o.look     [dx, dy] -1..1 where the iris points            o.pupil  scale of the pupil (1 = normal, 1.6 = dilated)
//     o.iris     ink spec for the iris ({ pink: 1 })             o.irisLine ink for the striations (default 'black')
//     o.lid      ink spec of lid line + lashes ('black'), or 'knock' for paper lines on a dark field         o.lashes  number of lashes (9), 0 for none
//     o.white    ink spec printed on the eye white (default none = paper)
//     o.crease   true: the lid fold line above the eye           o.spin   rotation of the iris striations (radians)
//     o.inWhite(g)  draw inside the eye opening (clipped), after the white, before the iris
//     o.inPupil(g)  draw inside the pupil (clipped): reflections, worlds. g.px, g.py, g.pr
//     o.noIris   skip the iris (for a white full of other things)
//   returns g = { cx, cy, r, ix, iy, ir, px, py, pr, opening: Path2D, upper: pts, lower: pts }
//
//   clipInks(path, fn)                run fn with every ink clipped to a Path2D
//   ringText(words, cx, cy, R, a0, o) set words around a circle, clockwise from angle a0 (0 = 12 o'clock).
//     words: [{ w, t0 }] (each word prints on at t0; use LINES[i].words), o: { t, font, size, wdth, wght, ink|knock, gap }

function clipInks(path, fn) {
  for (const k of RISO.inks) { k.ctx.save(); k.ctx.clip(path); }
  try { fn(); } finally { for (const k of RISO.inks) k.ctx.restore(); }
}

function eyeCurves(r, open, squint = 0, n = 28) {
  const up = [], lo = [];
  for (let i = 0; i <= n; i++) {
    const u = i / n, x = lerp(-r, r, u);
    const s = Math.sin(Math.PI * Math.pow(u, .92));             // peak a touch toward the outer corner
    const loOpen = r * .40 * Math.pow(Math.sin(Math.PI * u), .9);
    const loY = lerp(loOpen, -r * .08 * Math.sin(Math.PI * u), squint);   // squint: the lower lid rises and flattens
    const upOpen = -r * .56 * Math.pow(s, .8);
    const upY = lerp(loY - r * .012 * Math.sin(Math.PI * u), upOpen, clamp(open));
    up.push([x, upY]); lo.push([x, loY]);
  }
  return { up, lo };
}

function eye(x, y, r, o = {}) {
  const lidPaint = (path) => (o.lid === 'knock' ? knock(path, null) : paint(path, o.lid || 'black'));
  const open = o.open ?? 1, squint = o.squint || 0;
  const { up, lo } = eyeCurves(r, open, squint);
  const U = up.map(([a, b]) => [x + a, y + b]), Lo = lo.map(([a, b]) => [x + a, y + b]);
  const opening = P(U.concat(Lo.slice().reverse()));
  const look = o.look || [0, 0];
  const ir = r * .43, ix = x + look[0] * r * .42, iy = y + look[1] * r * .14 + r * .02;
  const pr = ir * .44 * (o.pupil ?? 1), px = ix + look[0] * ir * .06, py = iy + look[1] * ir * .06;
  const g = { cx: x, cy: y, r, ix, iy, ir, px, py, pr, opening, upper: U, lower: Lo };
  const gap = Math.max(...U.map((p, i) => Lo[i][1] - p[1]));
  if (gap > 1.5) {
    knock(opening, null);                                      // the white of the eye is paper
    clipInks(opening, () => {
      if (o.white) ink(opening, o.white);
      if (o.inWhite) o.inWhite(g);
      if (!o.noIris) {
        paint(P(circle(ix, iy, ir, 72)), o.iris || { pink: 1 });
        // striations: alternating black spokes, like a gear, from the pupil to the rim
        const n = 28, sp = o.spin || 0;
        for (let i = 0; i < n; i++) {
          const a = sp + i / n * TAU, w = i % 2 ? ir * .035 : ir * .07;
          ink(P([[ix + Math.cos(a) * pr * 1.25, iy + Math.sin(a) * pr * 1.25], [ix + Math.cos(a) * ir * (i % 2 ? .78 : .9), iy + Math.sin(a) * ir * (i % 2 ? .78 : .9)]], false), o.irisLine || 'black', { stroke: w });
        }
        ink(P(circle(ix, iy, ir * .97, 72)), o.irisLine || 'black', { stroke: ir * .09 });   // limbal ring
        paint(P(cut(circle(px, py, pr, 48), 901, .6, .3)), 'black');
        if (o.inPupil) clipInks(P(circle(px, py, pr * .96, 48)), () => o.inPupil(g));
        // highlights: paper
        knock(P(circle(ix - ir * .38, iy - ir * .38, ir * .16, 24)), null);
        knock(P(circle(ix - ir * .12, iy - ir * .58, ir * .06, 12)), null);
      }
    });
  }
  // lower lid line (thin), upper lid line (heavy, tapered), lashes, crease
  lidPaint(P(ribbon(Lo, r * .012, r * .012, 910)));
  const heavy = U.map((p, i) => { const u = i / (U.length - 1), w = r * (.018 + .07 * Math.sin(Math.PI * Math.pow(u, .8))); return [p, w]; });
  const L = [], R = [];
  for (let i = 0; i < heavy.length; i++) {
    const [p, w] = heavy[i], a = heavy[Math.max(0, i - 1)][0], b = heavy[Math.min(heavy.length - 1, i + 1)][0];
    const d = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1, nx = (b[1] - a[1]) / d, ny = -(b[0] - a[0]) / d;
    L.push([p[0] + nx * w * .15, p[1] + ny * w * .15]); R.push([p[0] - nx * w * .85, p[1] - ny * w * .85]);
  }
  lidPaint(P(L.concat(R.reverse())));
  const nl = o.lashes ?? 9;
  for (let k = 0; k < nl; k++) {
    const u = .22 + k / Math.max(1, nl - 1) * .72, i = Math.round(u * (U.length - 1)), p = U[i];
    const a = U[Math.max(0, i - 1)], b = U[Math.min(U.length - 1, i + 1)], d = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
    const tx = (b[0] - a[0]) / d, ty = (b[1] - a[1]) / d, nx = ty, ny = -tx;   // outward normal (up when open)
    const flip = open < .25 ? -1 : 1;                             // shut: lashes hang down
    const len = r * (.1 + .06 * Math.sin(Math.PI * u)), sk = (u - .5) * len * .9;
    const tip = [p[0] + nx * len * flip + tx * sk, p[1] + ny * len * flip + ty * sk];
    lidPaint(P([[p[0] - r * .014, p[1]], [tip[0], tip[1]], [p[0] + r * .014, p[1]]]));
  }
  if (o.crease !== false) {
    const C = up.map(([a, b], i) => [x + a * .9, y + lerp(-r * .1, -r * .74, Math.pow(Math.sin(Math.PI * i / (up.length - 1)), .8)) + (1 - open) * r * .38]);
    lidPaint(P(ribbon(C.slice(4, -3), r * .012, r * .006, 912)));
  }
  return g;
}

function ringText(words, cx, cy, R, a0, o = {}) {
  const t = o.t ?? NOW, size = o.size || 70, gapA = (o.gap ?? .5) * size / R;
  let a = a0;
  for (const w of words) {
    const S = shape(w.w.toUpperCase(), { font: o.font || 'arch', size, wdth: o.wdth ?? 90, wght: o.wght ?? 900 });
    const age = t - (w.t0 - .05), on = age >= 0;
    for (const g of S.glyphs) {
      const ang = a + (g.x + g.w / 2) / R;
      if (on && g.ch !== ' ') {
        const u = clamp(age / .18), sc = 1 + .6 * (1 - E.out3(u));
        save(); translate(cx, cy); rotate(ang); translate(0, -R);
        const p = glyphPath(g, -g.w / 2, S.cap / 2, sc);
        if (o.knock) knock(p, o.knockInks || null); else paint(p, o.ink || 'black');
        restore();
      }
    }
    a += S.width / R + gapA;
  }
  return a;
}
