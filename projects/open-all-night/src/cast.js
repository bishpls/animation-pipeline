// cast.js: cut-paper puppets, one ink each (like a one-colour print), with paper-line details and black accents.
//
// figure(CAST.kid, x, y, s, pose): (x, y) = the ground point between the feet; s = scale (1 = design size).
// Local space faces +x; pose.face = -1 mirrors. Angles are radians. For a limb, 0 = hanging straight down and
// + swings it toward the facing direction; the second number bends the elbow or knee.
//   lean, bob (px), head (tilt), look [dx, dy], eyes 'dot'|'closed'|'happy'|'wide'|'wink', mouth 0..1 (sing), smile 0..1
//   aF/aN: [shoulder, elbow] far/near arm    lF/lN: [hip, knee] far/near leg    walk: phase (0..1 per stride)
//   hold: fn(p, ang) called at the near hand (draw held props there); holdF: at the far hand
//   light: 0..1 face lit from below by a screen     ink: override the character ink
// Separation: near limbs cut a paper gap around themselves, as layered paper does.

// Catmull-Rom closed curve through control points -> polygon (corner points: repeat them to keep them sharp)
function blob(cp, n = 6) {
  const out = [], m = cp.length;
  for (let i = 0; i < m; i++) {
    const p0 = cp[(i - 1 + m) % m], p1 = cp[i], p2 = cp[(i + 1) % m], p3 = cp[(i + 2) % m];
    for (let k = 0; k < n; k++) {
      const t = k / n, t2 = t * t, t3 = t2 * t;
      out.push([0, 1].map(j => .5 * (2 * p1[j] + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2 + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3)));
    }
  }
  return out;
}
const R2 = (p, a) => { const c = Math.cos(a), s = Math.sin(a); return [p[0] * c - p[1] * s, p[0] * s + p[1] * c]; };
const V = (o, p, a = 0) => { const q = R2(p, a); return [o[0] + q[0], o[1] + q[1]]; };

const CAST = {};
// shared anatomy builder: proportions + per-character shape functions
function makeChar(d) { return Object.assign({ neck: 10, limbW: [17, 12], legW: [20, 14], hand: 11, shoe: [26, 12], shoeInk: { black: 1 } }, d); }

CAST.kid = makeChar({
  ink: { pink: 1 }, legH: [44, 40], torsoH: 74, armL: [40, 36], headR: 40, limbW: [14, 10], legW: [15, 12], hand: 9, shoe: [20, 10],
  torso: (h) => blob([[-26, 0], [-30, -h * .5], [-22, -h], [22, -h], [30, -h * .5], [28, 0]], 5),     // pajama top (boxy, soft)
  torsoDetail(h, ink) { knock(P([[-4, -h + 4], [3, -h * .6], [0, -h * .1]], false), ['pink'], 1, { stroke: 3 }); for (const y of [.35, .6, .82]) knock(P(circle(8, -h * y, 3, 8)), ['pink']); },
  head(r, o) {       // big round head, a small upturned nose, the afro puff behind
    const puff = cut(circle(-r * .8, -r * .66, r * .8, 40), 3, 1.4, .6);
    o.after = () => {                    // black hair: a cap of hair over the crown and the puff behind it, a pink hair tie
      paint(P(cut(blob([[-r * .95, r * .05], [-r * .8, -r * .8], [r * .1, -r * 1.06], [r * .7, -r * .78], [r * .35, -r * .62], [-r * .35, -r * .45], [-r * .6, r * .1]], 5), 4, 1)), { black: 1 });
      paint(P(puff), { black: 1 });
      paint(P(cut(ellipse(-r * .38, -r * .58, r * .13, r * .3, .6, 12), 5, .5)), { pink: 1 });
    };
    const face = blob([[-r * .9, -r * .2], [-r * .6, -r * .9], [r * .2, -r * 1.02], [r * .82, -r * .55], [r * .98, -r * .05], [r * 1.12, r * .12], [r * .95, r * .3], [r * .8, r * .72], [r * .1, r * .98], [-r * .6, r * .7]], 5);
    return face;
  },
  face: { eye: [.55, -.12], mouth: [.62, .52], cheek: [.35, .42] },
});
CAST.dad = makeChar({
  ink: { blue: 1 }, legInk: { blue: 1, black: .0 }, trouserInk: { blue: 1, black: 1 }, legH: [74, 72], torsoH: 118, armL: [64, 60], headR: 34, limbW: [20, 14], legW: [24, 18], shoe: [34, 14],
  torso: (h) => blob([[-30, 4], [-34, -h * .45], [-44, -h * .92], [-30, -h], [34, -h], [46, -h * .9], [36, -h * .45], [32, 4]], 4),
  torsoDetail(h) { knock(P([[-14, -h + 2], [0, -h + 22], [16, -h + 2]], false), ['blue'], 1, { stroke: 3.5 }); knock(P([[2, -h + 22], [2, -8]], false), ['blue'], 1, { stroke: 2.5 }); knock(P(rrect(10, -h * .74, 16, 14, 3)), ['blue'], 1, { stroke: 2.5 }); },
  head(r, o) {       // long face, a strong nose, a flat cap (black) with a brim
    const face = blob([[-r * .85, -r * .1], [-r * .7, -r * .85], [r * .3, -r * .98], [r * .78, -r * .5], [r * .84, -r * .1], [r * 1.34, r * .22], [r * 1.34, r * .22], [r * .86, r * .36], [r * .8, r * .8], [r * .2, r * 1.12], [-r * .55, r * .8]], 5);
    o.after = () => { paint(P(cut(blob([[-r * 1.0, -r * .35], [-r * .8, -r * 1.2], [r * .3, -r * 1.3], [r * .95, -r * .75], [r * 1.55, -r * .62], [r * 1.5, -r * .45], [r * .7, -r * .42]], 4), 7, 1)), { blue: 1, black: 1 }); };
    return face;
  },
  face: { eye: [.42, -.2], mouth: [.66, .56] },
});
CAST.grandma = makeChar({
  ink: { yellow: 1 }, legH: [48, 46], torsoH: 96, armL: [50, 46], headR: 36, limbW: [17, 12], legW: [16, 12], shoe: [24, 11],
  torso: (h) => blob([[-50, 6], [-46, -h * .45], [-36, -h * .88], [-18, -h], [22, -h], [40, -h * .86], [48, -h * .4], [52, 6]], 5),   // cardigan to a full skirt
  torsoDetail(h) { knock(P([[-10, -h + 3], [2, -h * .45], [-4, 2]], false), ['yellow'], 1, { stroke: 3.5 }); knock(P([[-44, -h * .3], [48, -h * .3]], false), ['yellow'], 1, { stroke: 3 }); },
  head(r, o) {       // round, a button nose, a cloud of white curls (knocked out, outlined in yellow), round glasses
    const face = blob([[-r * .85, 0], [-r * .6, -r * .85], [r * .3, -r * .95], [r * .88, -r * .4], [r * 1.08, r * .1], [r * .92, r * .3], [r * .78, r * .76], [r * .1, r * 1.0], [-r * .6, r * .7]], 5);
    o.after = () => {
      for (let i = 0; i < 9; i++) {
        const a = -Math.PI * 1.08 + i / 8 * Math.PI * .95, c = [Math.cos(a) * r * .98 - r * .12, -r * .15 + Math.sin(a) * r * 1.0];
        const cl = cut(circle(c[0], c[1], r * .34, 18), 20 + i, .8);
        knock(P(cl)); ink(P(cl), this.ink, { stroke: 3 });
      }
      const g = [r * .5, -r * .12];
      ink(P(circle(g[0], g[1], r * .28, 20)), { black: 1 }, { stroke: 3.2 });
      ink(P([[g[0] - r * .28, g[1]], [-r * .1, g[1] - r * .05]], false), { black: 1 }, { stroke: 3 });
    };
    return face;
  },
  face: { eye: [.5, -.12], mouth: [.64, .5], cheek: [.36, .38] },
});
CAST.baker = makeChar({
  ink: { blue: 1 }, legH: [50, 48], torsoH: 118, armL: [52, 50], headR: 38, limbW: [22, 16], legW: [22, 17], shoe: [28, 12],
  torso: (h) => blob([[-52, 6], [-62, -h * .45], [-44, -h * .9], [-14, -h], [18, -h], [48, -h * .88], [64, -h * .42], [54, 6]], 5),
  torsoDetail(h) {       // the apron: a paper shape with ties
    knock(P(cut(blob([[-34, 2], [-40, -h * .45], [-20, -h * .8], [22, -h * .8], [42, -h * .45], [38, 2]], 4), 5, 1)));
    knock(P([[-48, -h * .5], [-68, -h * .38]], false), null, 1, { stroke: 4 });
  },
  head(r, o) {
    const face = blob([[-r * .85, 0], [-r * .65, -r * .85], [r * .3, -r * .95], [r * .85, -r * .45], [r * 1.02, r * .05], [r * 1.12, r * .2], [r * .9, r * .36], [r * .82, r * .72], [r * .1, r * 1.02], [-r * .62, r * .74]], 5);
    o.after = () => {    // baker's cap: a paper puff with a blue band
      const cap = cut(blob([[-r * .9, -r * .55], [-r * 1.25, -r * 1.25], [-r * .7, -r * 1.9], [r * .1, -r * 2.05], [r * .9, -r * 1.75], [r * 1.1, -r * 1.1], [r * .85, -r * .55]], 5), 11, 1.2);
      knock(P(cap)); ink(P(cap), this.ink, { stroke: 3 });
      ink(P(rect(-r * .88, -r * .78, r * 1.74, r * .2)), this.ink);
    };
    return face;
  },
  face: { eye: [.48, -.15], mouth: [.62, .5], cheek: [.34, .36] },
});
CAST.newsboy = makeChar({
  ink: { black: 1 }, legH: [50, 46], torsoH: 80, armL: [44, 40], headR: 32, limbW: [15, 11], legW: [18, 13], shoe: [24, 11],
  torso: (h) => blob([[-24, 4], [-28, -h * .5], [-24, -h], [24, -h], [28, -h * .5], [26, 4]], 4),
  torsoDetail(h) { knock(P([[-14, -h], [-10, 2]], false), ['black'], 1, { stroke: 3 }); knock(P([[12, -h], [8, 2]], false), ['black'], 1, { stroke: 3 }); },
  head(r, o) {
    const face = blob([[-r * .85, 0], [-r * .62, -r * .82], [r * .3, -r * .95], [r * .82, -r * .45], [r * .95, r * .05], [r * 1.18, r * .25], [r * .92, r * .36], [r * .8, r * .74], [r * .1, r * 1.0], [-r * .6, r * .7]], 5);
    o.after = () => { paint(P(cut(blob([[-r * 1.05, -r * .3], [-r * .95, -r * 1.25], [r * .4, -r * 1.35], [r * 1.05, -r * .75], [r * 1.5, -r * .55], [r * 1.4, -r * .4], [r * .6, -r * .4]], 4), 13, 1)), { black: 1, blue: 1 }); };
    return face;
  },
  face: { eye: [.45, -.12], mouth: [.62, .52] },
});
// crowd: one of several silhouettes in one ink (var picks hair/hat/body)
CAST.anon = makeChar({
  ink: { black: 1 }, legH: [62, 58], torsoH: 96, armL: [54, 50], headR: 32, limbW: [17, 12], legW: [19, 14],
  torso: (h, v) => (v % 3 === 1 ? blob([[-42, 4], [-30, -h * .6], [-24, -h], [24, -h], [30, -h * .6], [42, 4]], 4) : blob([[-26, 4], [-32, -h * .5], [-30, -h], [30, -h], [32, -h * .5], [26, 4]], 4)),
  head(r, o) {
    const v = o.var || 0;
    const face = blob([[-r * .85, 0], [-r * .62, -r * .85], [r * .3, -r * .95], [r * .82, -r * .45], [r * .95, r * .05], [r * 1.15, r * .25], [r * .9, r * .36], [r * .8, r * .74], [r * .1, r * 1.0], [-r * .6, r * .7]], 5);
    o.after = () => {
      const k = v % 5, I = o.inkOv || this.ink;
      if (k === 0) paint(P(cut(circle(-r * .25, -r * .3, r * 1.02, 28), v, 1)), I);
      if (k === 1) { paint(P(cut(rect(-r * 1.2, -r * .9, r * 2.5, r * .22), v)), I); paint(P(cut(rrect(-r * .75, -r * 1.75, r * 1.5, r * .95, r * .2), v + 1)), I); }
      if (k === 2) paint(P(cut(blob([[-r * 1.1, r * .9], [-r * 1.05, -r * .6], [-r * .3, -r * 1.1], [r * .6, -r * .9], [r * .5, -r * .4], [-r * .4, -r * .2], [-r * .5, r * .9]], 4), v, 1)), I);
      if (k === 3) { paint(P(cut(circle(-r * .5, -r * 1.05, r * .45, 18), v)), I); paint(P(cut(circle(-r * .15, -r * .35, r * .9, 24), v + 2)), I); }
      if (k === 4) paint(P(cut(blob([[-r * .95, -r * .2], [-r * .7, -r * 1.05], [r * .5, -r * 1.1], [r * .9, -r * .5], [r * .2, -r * .7]], 4), v, 1)), I);
    };
    return face;
  },
  face: { eye: [.45, -.12], mouth: [.62, .52] },
});

// ------------------------------------------------------------------ the rig
function limbPts(a, l1, l2, [s, e]) {
  const k = [a[0] + Math.sin(s) * l1, a[1] + Math.cos(s) * l1];
  return [a, k, [k[0] + Math.sin(s + e) * l2, k[1] + Math.cos(s + e) * l2]];
}
function drawLimb(pts, w0, w1, spec, seed, gapInk = null) {
  const [a, k, h] = pts;
  const path = [a, [lerp(a[0], k[0], .5), lerp(a[1], k[1], .5)], k, [lerp(k[0], h[0], .5), lerp(k[1], h[1], .5)], h];
  const rib = ribbon(path, w0, w1, seed);
  if (gapInk) knock(P(rib), gapInk, 1, { stroke: 4.5 });      // paper gap: the near limb is a separate piece of paper
  paint(P(rib), spec);
  paint(P(circle(k[0], k[1], (w0 + w1) / 4, 12)), spec);      // round the joint
}
function walkPose(ph) {
  const s = Math.sin(ph * TAU), c = Math.cos(ph * TAU);
  return { lF: [s * .42, -Math.max(0, c) * .9 - .05], lN: [-s * .42, -Math.max(0, -c) * .9 - .05], aF: [-s * .45, .35], aN: [s * .45, .35], bob: -Math.abs(c) * 5 };
}
function figure(Ch, x, y, s = 1, o = {}) {
  const seed = o.seed ?? 0;
  const f = o.face ?? 1, I = o.ink || Ch.ink, legI = o.ink || Ch.trouserInk || I, inks = Object.keys(I);
  if (o.walk != null) o = { ...walkPose(o.walk), ...o };
  const sq = o.sq || 0;
  save(); translate(x, y + (o.bob || 0) * s); scale(s * (1 + sq * .4) * f, s * (1 - sq * .4));
  const [l1, l2] = Ch.legH, hip = [0, -(l1 + l2) + 6], lean = o.lean || 0, th = Ch.torsoH;
  const neckP = V(hip, [0, -th], lean);
  const shF = V(hip, [-12, -th + 14], lean), shN = V(hip, [12, -th + 14], lean);
  const aF = o.aF || [-.12, .25], aN = o.aN || [.12, .25], lF = o.lF || [.04, 0], lN = o.lN || [-.04, 0];
  // far side (overprinted with a black tint = in shadow, one step back)
  const shade = Object.fromEntries([...Object.entries(I), ['black', Math.max(I.black || 0, .45)]]);
  const legF = limbPts([hip[0] - 8, hip[1]], l1, l2, lF);
  drawLimb(legF, Ch.legW[0], Ch.legW[1], legI, seed + 1);
  shoe(legF[2], Ch, 1, lF, seed + 2);
  const armF = limbPts(shF, Ch.armL[0], Ch.armL[1], aF);
  drawLimb(armF, Ch.limbW[0], Ch.limbW[1], I, seed + 3);
  paint(P(circle(armF[2][0], armF[2][1], Ch.hand, 12)), I);
  if (o.holdF) o.holdF(armF[2], aF[0] + aF[1]);
  // near leg, torso
  const legN = limbPts([hip[0] + 8, hip[1]], l1, l2, lN);
  drawLimb(legN, Ch.legW[0], Ch.legW[1], legI, seed + 4);
  shoe(legN[2], Ch, 1, lN, seed + 5);
  save(); translate(hip[0], hip[1]); rotate(lean);
  paint(P(cut(Ch.torso(th, o.var || 0), seed + 6, 1.1, .6)), I);
  if (Ch.torsoDetail) Ch.torsoDetail(th, I);
  restore();
  // head
  const r = Ch.headR, hc = V(neckP, [0, -Ch.neck - r * .8], lean);
  paint(P(ribbon([V(neckP, [0, 8], lean), hc], r * .5, r * .45, seed + 7)), I);
  save(); translate(hc[0], hc[1]); rotate(lean * .5 + (o.head || 0));
  drawHead(Ch, I, r, seed, o);
  restore();
  // near arm on top, with a paper gap
  const armN = limbPts(shN, Ch.armL[0], Ch.armL[1], aN);
  drawLimb(armN, Ch.limbW[0], Ch.limbW[1], I, seed + 12, inks);
  knock(P(circle(armN[2][0], armN[2][1], Ch.hand + 2.2, 12)), inks);
  paint(P(cut(circle(armN[2][0], armN[2][1], Ch.hand, 12), seed + 13, .5, .3)), I);
  if (o.hold) o.hold(armN[2], aN[0] + aN[1]);
  restore();
}
// the head alone, at the current transform's origin (head centre), facing +x. Used by figure() and head().
function drawHead(Ch, I, r, seed, o) {
  const inks = Object.keys(I);
  const ho = { var: o.var, inkOv: o.ink };
  const face = cut(Ch.head.call({ ...Ch, ink: I }, r, ho), seed + 8, .9, .5);
  paint(P(face), I);
  if (ho.after) ho.after();
  if (o.light > .3) { save(); const cl = new Path2D(); cl.addPath(P(face)); layer(inks[0]); for (const k of RISO.inks) k.ctx.clip(cl); const lp = cut(circle(r * 1.05, r * 1.0, r * 1.02, 32), seed + 9, .8); knock(P(lp), inks); ink(P(lp), { yellow: 1 }); restore(); }
  const F = Ch.face, ex = F.eye[0] * r + (o.look ? o.look[0] * r * .08 : 0), ey = F.eye[1] * r + (o.look ? o.look[1] * r * .08 : 0);
  const eyes = o.eyes || 'dot';
  if (F.cheek && o.blush !== 0) ink(P(circle(F.cheek[0] * r, F.cheek[1] * r, r * .14, 14)), { pink: I.pink ? 0 : .9, yellow: I.pink ? .0 : 0, black: I.pink ? .25 : 0 });
  if (eyes === 'dot') ink(P(cut(circle(ex, ey, r * .1, 12), seed + 10, .3, .2)), 'black');
  else if (eyes === 'wide') { knock(P(circle(ex, ey, r * .17, 16)), inks); ink(P(circle(ex + r * .05, ey, r * .09, 12)), 'black'); }
  else if (eyes === 'closed') ink(P(arcPts(ex, ey - r * .06, r * .12, .25, Math.PI - .25, 8), false), 'black', { stroke: r * .06 });
  else if (eyes === 'happy') ink(P(arcPts(ex, ey + r * .08, r * .12, Math.PI + .25, TAU - .25, 8), false), 'black', { stroke: r * .065 });
  else if (eyes === 'wink') ink(P([[ex - r * .12, ey], [ex + r * .12, ey]], false), 'black', { stroke: r * .06 });
  const mx = F.mouth[0] * r, my = F.mouth[1] * r;
  if (o.mouth > .05) { const m = clamp(o.mouth); ink(P(cut(ellipse(mx, my, r * (.1 + .07 * m), r * (.05 + .2 * m), .2, 16), seed + 11, .3, .2)), 'black'); }
  else ink(P(arcPts(mx - r * .05, my - r * .12, r * .16, .5, 1.9 - (o.smile === 0 ? .6 : 0), 8), false), 'black', { stroke: r * .05 });
}
// a head on its own (close-ups, heads peeking out of blankets, faces in windows): (x, y) = head centre, s = scale
function head(Ch, x, y, s = 1, o = {}) {
  const I = o.ink || Ch.ink;
  save(); translate(x, y); scale(s * (o.face ?? 1), s); rotate(o.head || 0);
  drawHead(Ch, I, Ch.headR, o.seed ?? 0, { ...o, head: 0 });
  restore();
}
function shoe(p, Ch, f, leg, seed) {
  const [w, h] = Ch.shoe;
  paint(P(cut(blob([[-w * .35, -h * .7], [w * .45, -h * .6], [w * .75, -h * .05], [w * .7, h * .2], [-w * .4, h * .2]], 4).map(([a, b]) => [p[0] + a, p[1] + b]), seed, .5, .3)), Ch.shoeInk);
}
