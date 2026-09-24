// picto.js: the "fig." plates. Engraved museum-specimen pictograms of each word's literal root meaning.
//
//   PICTO[name](cx, cy, s, t, lt, ground, o = {})
//     (cx, cy)  plate centre, world coords        s  scale (1 = the plate fits ~760×760 px)
//     t         film time                          lt seconds since the plate arrived on screen (reveal, then idle)
//     ground    the band's flood ink ('slate' | 'ochre' | 'ox' | 'black') or null for bone paper
//     o         per-plate options (salary: o.stampAt = lt at which the MYTH? stamp lands, default 4.5)
//   names: window, companion, muscle, disaster, clue, salary, brainrot, goodbye
//
// Engraving rules: line art is PAPER (knocked out of every ink) on an ink ground, BLACK on bare paper. Fills are opaque
// inks chosen to contrast with the ground; shading is a tint of a line-screen ink (ochre/slate print as hatch lines).
// Every line engraves in over the first ~0.8 s (a stroke drawn along its length), then something idles gently.
(() => {
  // ---------------------------------------------------------------- helpers (unit space: the plate spans ±380)
  let G = null;                                            // the current ground ink
  const INKS = ['ochre', 'slate', 'ox', 'black'];
  const pick = (...order) => order.find(k => k !== G) || order[0];    // first ink in order that isn't the ground
  const lineMode = () => (G ? 'paper' : 'ink');
  // a stroke. mode 'paper' knocks every ink (paper-white line), 'ink' prints black (or o.spec)
  function line(pts, w, o = {}) {
    if (pts.length < 2) return;
    const p = P(pts, !!o.close);
    const mode = o.mode || lineMode();
    if (mode === 'paper') knock(p, null, 1, { stroke: w });
    else paint(p, o.spec || (G === 'black' ? 'ox' : 'black'), { stroke: w });
  }
  const fill = (pts, spec) => paint(P(pts), spec);
  const tint = (pts, spec) => ink(P(pts), spec);                   // overprint tint (hatch / dots)
  // the first u (0..1) of a polyline, by length: engraving in
  function part(pts, u) {
    if (u >= 1) return pts; if (u <= 0) return [];
    let L = 0; const seg = [];
    for (let i = 1; i < pts.length; i++) { const d = Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]); seg.push(d); L += d; }
    const out = [pts[0]]; let acc = 0, want = L * u;
    for (let i = 1; i < pts.length; i++) {
      if (acc + seg[i - 1] >= want) { const k = (want - acc) / seg[i - 1]; out.push([lerp(pts[i - 1][0], pts[i][0], k), lerp(pts[i - 1][1], pts[i][1], k)]); return out; }
      acc += seg[i - 1]; out.push(pts[i]);
    }
    return out;
  }
  function blob(cp, n = 6) {   // Catmull-Rom closed curve through control points
    const out = [], m = cp.length;
    for (let i = 0; i < m; i++) {
      const p0 = cp[(i - 1 + m) % m], p1 = cp[i], p2 = cp[(i + 1) % m], p3 = cp[(i + 2) % m];
      for (let k = 0; k < n; k++) { const t = k / n, t2 = t * t, t3 = t2 * t; out.push([0, 1].map(j => .5 * (2 * p1[j] + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2 + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3))); }
    }
    return out;
  }
  const rev = (lt, d0 = 0, d1 = .8) => E.out3(seg(lt, d0, d1));    // reveal progress with a stagger
  const spiral = (cx, cy, r0, r1, turns, a0 = 0, n = 60) => { const p = []; for (let i = 0; i <= n; i++) { const u = i / n, a = a0 + u * turns * TAU, r = lerp(r0, r1, u); p.push([cx + Math.cos(a) * r, cy + Math.sin(a) * r]); } return p; };
  const bez = (a, b, c, d, n = 24) => { const p = []; for (let i = 0; i <= n; i++) { const u = i / n, v = 1 - u; p.push([0, 1].map(j => v * v * v * a[j] + 3 * v * v * u * b[j] + 3 * v * u * u * c[j] + u * u * u * d[j])); } return p; };
  const quad = (a, b, c, n = 20) => { const p = []; for (let i = 0; i <= n; i++) { const u = i / n, v = 1 - u; p.push([0, 1].map(j => v * v * a[j] + 2 * v * u * b[j] + u * u * c[j])); } return p; };
  function clipTo(pts, fn) { const cp = P(pts); for (const k of RISO.inks) { k.ctx.save(); k.ctx.clip(cp); } fn(); for (const k of RISO.inks) k.ctx.restore(); }
  // parallel hatch lines across a box, angle a, spacing sp (engraved shading, drawn in the current line mode)
  function hatch(box, a, sp, w, o = {}) {
    const [x0, y0, x1, y1] = box, cx = (x0 + x1) / 2, cy = (y0 + y1) / 2, R = Math.hypot(x1 - x0, y1 - y0) / 2;
    const ca = Math.cos(a), sa = Math.sin(a);
    for (let d = -R; d <= R; d += sp) line([[cx - sa * d - ca * R, cy + ca * d - sa * R], [cx - sa * d + ca * R, cy + ca * d + sa * R]], w, o);
  }
  // several overlapping parts as ONE silhouette: a thick black underlay stroke per part, then the fills on top,
  // so only the outer outline shows (no seams where parts overlap)
  function silhouette(parts, spec, w = 9, u = 1) {
    const oc = G === 'black' ? 'ox' : 'black';
    for (const p of parts) paint(P(p), oc, { stroke: w * 2 });
    for (const p of parts) paint(P(p), spec);
  }
  function plate(cx, cy, s, ground, fn) {
    const prev = G; G = ground || null;
    save(); translate(cx, cy); scale(s);
    fn();
    restore(); G = prev;
  }
  // a small caption plaque in the plate's corner ("fig." number is added by the caller if wanted)
  const PICTO = {};

  // ---------------------------------------------------------------- window: the wind-eye
  PICTO.window = (cx, cy, s, t, lt, ground) => plate(cx, cy, s, ground, () => {
    const u = rev(lt, 0, .7), ue = rev(lt, .25, 1.05);
    // wind streamlines drifting across behind the panes
    const drift = lt * 40;
    clipTo(rect(-300, -300, 600, 600), () => {
      for (let i = 0; i < 6; i++) {
        const y = -250 + i * 100, ph = (drift + i * 97) % 700 - 350;
        const pts = []; for (let k = 0; k <= 16; k++) { const x = -420 + k * 55 + ph * .3; pts.push([x, y + Math.sin(k * .7 + i + lt * 1.2) * 12]); }
        line(part(pts, u), 3, { mode: lineMode() });
      }
    });
    // the window frame: four panes, sill
    const fu = u;
    line(part([[-300, -300], [300, -300], [300, 300], [-300, 300], [-300, -300]], fu), 16);
    line(part([[0, -300], [0, 300]], fu), 10); line(part([[-300, 0], [300, 0]], fu), 10);
    line(part([[-340, 320], [340, 320]], fu), 12);
    // the eye is drawn over the mullions: re-knock a clean rim around it
    // the eye: almond lids, iris, pupil, highlight
    const lidU = [], lidL = [];
    for (let i = 0; i <= 30; i++) { const x = -210 + i * 14; const k = 1 - (x / 210) ** 2; lidU.push([x, -118 * k]); lidL.push([x, 92 * k]); }
    const white = lidU.concat(lidL.slice().reverse());
    if (ue > 0) {
      knock(P(white), null, 1);                                           // the white of the eye is paper
      clipTo(white, () => {
        const blink = Math.max(0, 1 - Math.abs(((lt - 2.2) % 5.5) - .12) / .12);   // one slow blink, every 5.5 s
        fill(circle(0, 4, 76 * ue, 48), { [pick('ochre', 'ox', 'slate')]: 1 });
        for (let k = 0; k < 18; k++) { const a = k / 18 * TAU; line([[Math.cos(a) * 38, 4 + Math.sin(a) * 38], [Math.cos(a) * 72 * ue, 4 + Math.sin(a) * 72 * ue]], 2.5, { mode: 'ink', spec: 'black' }); }
        fill(circle(0, 4, 34 * ue, 32), 'black');
        knock(P(circle(-20, -16, 12 * ue, 16)), null);
        if (blink > 0) fill(rect(-230, -130, 460, 250 * blink), { [G || 'black']: 1 });
      });
      line(white, 7, { close: true, mode: 'ink', spec: G === 'black' ? 'ox' : 'black' });
      line(white, 2.5, { close: true });
    }
    // lashes that curl out into wind swirls
    for (let i = 0; i < 7; i++) {
      const x = -150 + i * 50, k = 1 - (x / 210) ** 2, y = -118 * k;
      const dir = x / 210, len = 70 + 30 * (1 - Math.abs(dir));
      const tipX = x + dir * 70 + (i - 3) * 6, tipY = y - len;
      const sw = .15 * Math.sin(lt * 1.6 + i);                               // swirls breathe
      const curl = spiral(tipX + (dir >= 0 ? 16 : -16), tipY + 4, 22, 3, 1.2, (dir >= 0 ? Math.PI : 0) + sw, 26);
      const lash = quad([x, y], [x + dir * 30, y - len * .7], [tipX, tipY]).concat(curl);
      line(part(lash, rev(lt, .4 + i * .05, 1.2 + i * .05)), 4.5);
    }
  });

  // ---------------------------------------------------------------- companion: the bread-fellow
  PICTO.companion = (cx, cy, s, t, lt, ground) => plate(cx, cy, s, ground, () => {
    const u = rev(lt, 0, .8);
    const tear = E.out3(seg(lt, .5, 1.5)) * 50 + Math.sin(lt * 1.4) * 4 * seg(lt, 1.5, 2.3);
    const crust = pick('ochre', 'ox'), handInk = pick('black', 'slate');
    for (const side of [-1, 1]) {
      save(); translate(side * tear, 0); rotate(side * tear * .003);
      // half a round loaf (a boule): the outer dome, the torn face ragged along x = 0
      const pts = [];
      for (let i = 0; i <= 28; i++) { const a = -Math.PI / 2 + i / 28 * Math.PI; pts.push([side * (Math.cos(a) * 200), Math.sin(a) * 165]); }
      for (let i = 1; i < 12; i++) pts.push([side * (6 + 18 * hash(i * 7.3 + side)), lerp(165, -165, i / 12)]);
      const shape = cut(pts, side > 0 ? 3 : 4, 1.2, .4);
      silhouette([shape], { [crust]: 1 }, 5);
      // the crumb: the torn face, pale and pocked
      const face = cut([[side * 8, -150], [side * 70, -120], [side * 95, -40], [side * 95, 50], [side * 70, 130], [side * 8, 150]], side > 0 ? 5 : 6, 1.4);
      knock(P(face), null);
      for (let k = 0; k < 14; k++) { const x = side * (22 + hash(k * 3 + side) * 60), y = -110 + hash(k * 5 + side) * 220; fill(ellipse(x, y, 4 + hash(k) * 7, 3 + hash(k + 1) * 5, hash(k + 2) * 3, 10), 'black'); }
      // crust shading (hatch) and three scores
      clipTo(shape, () => tint(rect(side > 0 ? 110 : -210, -170, 100, 340), { slate: G === 'slate' ? 0 : .6 }));
      for (let k = 0; k < 3; k++) line(part([[side * (185 - k * 34), -60 + k * 40], [side * (140 - k * 34), -110 + k * 40]], u), 6, { mode: 'paper' });
      // the hand: a solid silhouette gripping the crust from outside: palm, four finger pads, a thumb over the top
      const hx = side * 205;
      const hand = [
        cut([[hx - side * 10, -60], [hx + side * 60, -80], [hx + side * 140, -40], [hx + side * 150, 60], [hx + side * 60, 90], [hx - side * 10, 60]], 70 + side, 1),
        ...[-40, 0, 40, 78].map((y, k) => ellipse(hx - side * 22, y, 34, 17, 0, 18)),
        ribbon([[hx + side * 30, -70], [hx - side * 20, -120], [hx - side * 70, -130]], 34, 26, 80 + side),
        rect(Math.min(hx + side * 130, hx + side * 330), -50, 200, 100),                   // the sleeve
      ];
      silhouette(hand, { [handInk]: 1 }, 4);
      knock(P([[hx + side * 130, -50], [hx + side * 130, 50]], false), null, 1, { stroke: 5 });   // cuff line
      restore();
    }
    for (let k = 0; k < 7; k++) {
      const period = 1.4, ph = (lt - .9 + k * .21) % period; if (lt < .9 || ph < 0) continue;
      const x = (hash(k * 1.7) - .5) * 60, y = 160 + ph * ph * 260;
      fill(rect(x - 6, y - 6, 12, 12), { [crust]: 1 });
    }
  });

  // ---------------------------------------------------------------- muscle: the little mouse
  PICTO.muscle = (cx, cy, s, t, lt, ground) => plate(cx, cy, s, ground, () => {
    const u = rev(lt, 0, .8), flex = .5 + .5 * Math.sin(lt * 2.2);
    const bulge = 1 + .08 * flex * seg(lt, .8, 1.2);
    const skin = pick('ochre', 'ox');
    // the arm: a flexed silhouette: shoulder at left, upper arm across, forearm up, fist on top
    const arm = cut(blob([
      [-360, 200], [-350, 60], [-300, -10], [-220, -60 - 55 * bulge], [-110, -95 - 70 * bulge], [0, -60 - 40 * bulge],   // shoulder, biceps
      [60, -110], [80, -210], [70, -265], [95, -320], [165, -345], [235, -320], [255, -255], [225, -200],                  // forearm up, fist
      [190, -170], [205, -60], [180, 60], [110, 140], [-60, 150], [-220, 200],                                              // forearm back, elbow, underarm
    ], 5), 11, 1.4, .4);
    silhouette([arm], { [skin]: 1 }, 5);
    for (const [x, y] of [[100, -318], [128, -330], [158, -334], [188, -328]]) line([[x, y], [x + 8, y + 26]], 3.5, { mode: 'ink', spec: 'black' });   // knuckles
    clipTo(arm, () => { const sh = ellipse(-60, 190, 380, 120, -.12, 40); tint(sh, { slate: G === 'slate' ? 0 : .55 }); });   // shading under the arm, a curved underside
    // the x-ray: the biceps window (paper) with a mouse inside
    const xr = ellipse(-110, -40 - 30 * bulge, 150 * bulge, 70 * bulge, -.08, 40);
    const xu = rev(lt, .4, 1.1);
    if (xu > 0) {
      knock(P(xr), null);
      clipTo(xr, () => {
        hatch([-270, -160, 50, 60], .5, 16, 1.5, { mode: 'ink', spec: 'black' });
        knock(P(xr), null, .6);
        // the mouse: body, head, ear, eye; it breathes with the flex
        const mx = -110, my = -38 - 30 * bulge, mb = 1 + .06 * flex;
        fill(ellipse(mx - 10, my + 6, 70 * mb, 40 * mb, 0, 30), 'black');
        fill(ellipse(mx + 62, my - 2, 34, 24, -.2, 24), 'black');
        fill(circle(mx + 44, my - 30, 17, 16), 'black'); knock(P(circle(mx + 44, my - 30, 8, 12)), ['black']);
        fill(circle(mx + 96, my + 2, 5, 8), 'black');
        knock(P(circle(mx + 66, my - 8, 4.5, 10)), ['black']);
        line([[mx + 88, my - 4], [mx + 118, my - 16]], 1.5, { mode: 'ink' }); line([[mx + 88, my], [mx + 120, my + 4]], 1.5, { mode: 'ink' });
      });
      line(xr.concat([xr[0]]), 5, { mode: 'ink', spec: 'black' });
    }
    // the tail: curls out of the arm's outline, swishing
    const sw = Math.sin(lt * 2.6) * 18;
    const tail = bez([-200, -30], [-300, -70], [-330, -200 + sw], [-230, -230 + sw]).concat(spiral(-200, -215 + sw, 30, 6, .9, Math.PI, 16));
    line(part(tail, rev(lt, .9, 1.6)), 6, { mode: G ? 'paper' : 'ink' });
    // motion ticks of the flex
    for (let k = 0; k < 3; k++) { const a = -2.4 + k * .35, r0 = 230, r1 = 260 + 10 * flex; line([[-110 + Math.cos(a) * r0, -60 + Math.sin(a) * r0], [-110 + Math.cos(a) * r1, -60 + Math.sin(a) * r1]], 5); }
  });

  // ---------------------------------------------------------------- disaster: the bad star
  PICTO.disaster = (cx, cy, s, t, lt, ground) => plate(cx, cy, s, ground, () => {
    const u = rev(lt, 0, .7), split = E.out3(seg(lt, .7, 1.5)) * 22 + Math.sin(lt * 1.3) * 3 * seg(lt, 1.5, 2);
    const star = []; for (let i = 0; i < 10; i++) { const a = -Math.PI / 2 + i / 10 * TAU, r = i % 2 ? 110 : 250; star.push([Math.cos(a) * r, Math.sin(a) * r - 20]); }
    // the crack: a jagged line down through the star
    const crack = [[20, -300], [-10, -170], [30, -100], [-20, -20], [25, 50], [-15, 130], [10, 260]];
    const col = pick('ochre', 'ox');
    for (const side of [-1, 1]) {
      const half = side < 0 ? [[-400, -320]].concat(crack).concat([[-400, 300]]) : [[400, -320]].concat(crack).concat([[400, 300]]);
      save(); translate(side * split, side * split * .3); rotate(side * split * .004);
      clipTo(half, () => {
        const sp = cut(star, side > 0 ? 21 : 22, 1.2, .4);
        fill(sp, { [col]: 1 });
        clipTo(sp, () => tint(rect(side > 0 ? 0 : -260, 20, 260, 240), { slate: G === 'slate' ? 0 : .55 }));
        line(part(sp.concat([sp[0]]), u), 7, { mode: 'ink', spec: G === 'black' ? 'ox' : 'black' });
        for (let i = 0; i < 5; i++) { const a = -Math.PI / 2 + i / 5 * TAU; line(part([[0, -20], [Math.cos(a) * 200, Math.sin(a) * 200 - 20]], u), 3, { mode: 'paper' }); }   // engraved ridges
      });
      restore();
    }
    // the crack's edge, and falling sparks (tiny stars) dropping out of it, looping
    line(part(crack, rev(lt, .6, 1.0)), 4, { mode: 'ink', spec: 'black' });
    for (let k = 0; k < 6; k++) {
      const period = 2.2, ph = (lt - 1.0 + k * .37) % period; if (lt < 1.0) continue;
      const x = (hash(k * 2.1) - .5) * 80 + ph * (hash(k) - .5) * 60, y = 120 + ph * ph * 60 + ph * 40, r = 16 * (1 - ph / period);
      const sp = []; for (let i = 0; i < 8; i++) { const a = i / 8 * TAU + ph * 3, rr = i % 2 ? r * .4 : r; sp.push([x + Math.cos(a) * rr, y + Math.sin(a) * rr]); }
      fill(sp, { [col]: 1 });
    }
  });

  // ---------------------------------------------------------------- clue: Ariadne's thread
  PICTO.clue = (cx, cy, s, t, lt, ground) => plate(cx, cy, s, ground, () => {
    const u = rev(lt, 0, .7);
    // the labyrinth: concentric square walls with gaps (engraved, hatched walls), the thread winding out through it
    const wall = pick('slate', 'ochre');
    const walls = [[260, 0], [200, 1], [140, 2], [80, 3]];
    for (const [r, i] of walls) {
      const gap = [[1, -1], [-1, 1], [1, 1], [-1, -1]][i];
      const sq = [[-r, -r], [r, -r], [r, r], [-r, r], [-r, -r]];
      line(part(sq, u), 18, { mode: G ? 'paper' : 'ink', spec: 'black' });
      // the doorway: knock a gap in the wall
      const gx = gap[0] * r, gy = gap[1] * r * .3;
      if (G) fill(rect(gx - 14, gy - 26, 28, 52), { [G]: 1 }); else knock(P(rect(gx - 14, gy - 26, 28, 52)), null);
    }
    // the ball of thread, top left, outside the maze
    const bx = -290, by = -300, br = 64, spin = lt * .5;
    fill(circle(bx, by, br, 40), { [pick('ox', 'ochre')]: 1 });
    clipTo(circle(bx, by, br, 40), () => {
      for (let k = 0; k < 7; k++) { const e = ellipse(bx, by, br * 1.05, br * (.2 + k * .12), spin + k * .45, 40); line(e.concat([e[0]]), 2.5, { mode: 'paper' }); }
    });
    line(circle(bx, by, br, 40).concat([[bx + br, by]]), 4, { mode: 'ink', spec: 'black' });
    // the thread: from the ball down into the maze and out of the centre: unwinding over time
    const path = [[bx + 40, by + 55], [-240, -230], [-230, -230], [-230, 230], [230, 230], [230, -170], [-170, -170], [-170, 170], [170, 170], [170, -110], [-110, -110], [-110, 110], [110, 110], [110, -50], [-50, -50], [-50, 30], [0, 30]];
    const tu = clamp(.25 + .75 * E.io2(seg(lt, .5, 3.2)) + .03 * Math.sin(lt * 2));
    const thread = part(path, tu);
    line(thread, 5, { mode: G ? 'paper' : 'ink', spec: 'ox' });
    if (thread.length) { const e = thread[thread.length - 1]; fill(circle(e[0], e[1], 9, 12), { [pick('ox', 'ochre')]: 1 }); }
  });

  // ---------------------------------------------------------------- salary: salt, and a myth
  PICTO.salary = (cx, cy, s, t, lt, ground, o = {}) => plate(cx, cy, s, ground, () => {
    const u = rev(lt, 0, .8), stampAt = o.stampAt ?? 4.5;
    // salt crystals: little cubes in a pile (paper tops, hatched sides)
    const cube = (x, y, a) => {
      const top = [[x, y - a * .5], [x + a * .87, y], [x, y + a * .5], [x - a * .87, y]];
      const left = [[x - a * .87, y], [x, y + a * .5], [x, y + a * 1.5], [x - a * .87, y + a]];
      const right = [[x + a * .87, y], [x, y + a * .5], [x, y + a * 1.5], [x + a * .87, y + a]];
      knock(P(top.concat(left).concat(right)), null);
      tint(left, { slate: G === 'slate' ? 0 : .45 }); tint(right, { slate: G === 'slate' ? 0 : .7 });
      if (G === 'slate') { tint(left, { black: .3 }); tint(right, { black: .5 }); }
      for (const f of [top, left, right]) line(f.concat([f[0]]), 3, { mode: 'ink', spec: 'black' });
    };
    const pile = [[-200, 200, 44], [-110, 210, 40], [-20, 205, 46], [-160, 140, 42], [-70, 140, 40], [-115, 80, 38], [60, 215, 36], [-250, 230, 30], [120, 235, 28], [15, 150, 34]];
    pile.sort((a, b) => a[1] - b[1]).forEach(([x, y, a], i) => { if (rev(lt, i * .05, .5 + i * .05) > .3) cube(x - 40, y - 60 + (1 - rev(lt, i * .05, .5 + i * .05)) * -40, a); });
    // the Roman legionary helmet: bowl, brim, cheek guard, crest (ox plume)
    const hx = 150, hy = -110, hu = rev(lt, .3, 1.1);
    const plume = pick('ox', 'ochre');
    const crest = [];
    for (let i = 0; i <= 14; i++) { const a = Math.PI + i / 14 * Math.PI; crest.push([hx + Math.cos(a) * 170, hy - 90 + Math.sin(a) * 110]); }
    const crestShape = cut(crest.concat([[hx + 150, hy - 70], [hx - 150, hy - 70]]), 31, 2);
    fill(crestShape, { [plume]: 1 });
    for (let k = 0; k < 12; k++) { const a = Math.PI + (k + .5) / 12 * Math.PI; line([[hx + Math.cos(a) * 60, hy - 80 + Math.sin(a) * 30], [hx + Math.cos(a) * 165, hy - 90 + Math.sin(a) * 105]], 3, { mode: 'paper' }); }
    const bowl = cut([[hx - 150, hy + 40], [hx - 150, hy - 20], [hx - 110, hy - 90], [hx, hy - 118], [hx + 110, hy - 90], [hx + 150, hy - 20], [hx + 150, hy + 40]], 32, 1);
    fill(bowl, { [pick('ochre', 'slate')]: 1 });
    clipTo(bowl, () => tint(rect(hx + 40, hy - 120, 120, 170), { slate: G === 'slate' ? 0 : .6 }));
    // the brim, flaring into a neck guard at the back (the galea's silhouette), and a brow band
    const brim = cut([[hx - 175, hy + 36], [hx + 150, hy + 36], [hx + 215, hy + 70], [hx + 250, hy + 110], [hx + 150, hy + 82], [hx - 165, hy + 66]], 33, 1);
    fill(brim, { [pick('ochre', 'slate')]: 1 });
    clipTo(brim, () => tint(rect(hx + 120, hy + 30, 140, 90), { slate: G === 'slate' ? 0 : .6 }));
    for (const f of [bowl, brim]) line(part(f.concat([f[0]]), hu), 5, { mode: 'ink', spec: 'black' });
    line([[hx - 150, hy + 10], [hx + 150, hy + 10]], 4, { mode: 'ink', spec: 'black' });
    for (let k = 0; k < 7; k++) fill(circle(hx - 120 + k * 40, hy + 10, 6, 10), 'black');      // rivets on the brow band
    // the stamp: MYTH? in oxblood, slammed on the helmet as the narrator says "Probably not"
    const sa = lt - stampAt;
    if (sa >= 0) {
      const thump = 1 + .6 * (1 - E.out3(clamp(sa / .14)));
      save(); translate(hx - 10, hy + 10); rotate(-.2); scale(thump);
      const L = shape('MYTH?', { font: 'arch', size: 96, wdth: 100, wght: 900 });
      const sc = G === 'ox' ? 'black' : 'ox';
      ink(P(rrect(-L.width / 2 - 26, -L.cap / 2 - 24, L.width + 52, L.cap + 48, 10)), { [sc]: 1 }, { stroke: 9 });
      knock(P(rrect(-L.width / 2 - 14, -L.cap / 2 - 12, L.width + 28, L.cap + 24, 6)), null, .0);
      drawText(L, 0, L.cap / 2, { [sc]: 1 }, { align: 'center', per: (g, i) => ({ dx: hash(i * 3.3) * 3 - 1.5 }) });
      // stamp ink is uneven: knock a few specks
      for (let k = 0; k < 14; k++) knock(P(circle((hash(k * 7.1) - .5) * L.width, (hash(k * 3.9) - .5) * L.cap, 2 + hash(k) * 4, 8)), [sc]);
      restore();
    }
  });

  // ---------------------------------------------------------------- brainrot: Walden, 1854
  PICTO.brainrot = (cx, cy, s, t, lt, ground) => plate(cx, cy, s, ground, () => {
    const u = rev(lt, 0, .8);
    const tree = pick('slate', 'black'), wood = pick('ochre', 'ox');
    // the quote, top: IM Fell italic, set as two lines
    const qu = rev(lt, .6, 1.4);
    const q1 = shape('…will not any endeavour', { font: 'fellI', size: 86 }), q2 = shape('to cure the brain-rot…', { font: 'fellI', size: 86 });
    const qspec = G ? null : 'black';
    const per = (g, i, n) => (i / n <= qu ? {} : { skip: true });
    if (qu > 0) {
      drawText(q1, 0, -350, qspec, { align: 'center', knock: !!G, per });
      drawText(q2, 0, -255, qspec, { align: 'center', knock: !!G, per });
    }
    // pines behind the cabin: stacked triangles, gently swaying
    const pine = (x, y, h, k) => { const sway = Math.sin(lt * 1.1 + k) * 4; for (let j = 0; j < 3; j++) { const w = h * (.42 - j * .09), yy = y - j * h * .25; fill(cut([[x - w, yy], [x + sway, yy - h * .45], [x + w, yy]], 40 + k * 3 + j, 1), { [tree]: 1 }); } fill(rect(x - 6, y, 12, 30), { [tree]: 1 }); };
    pine(-250, 90, 220, 1); pine(-170, 60, 260, 2); pine(210, 80, 240, 3); pine(290, 100, 200, 4); pine(-320, 110, 170, 5);
    // the cabin: roof, walls, door, window, chimney with a curl of smoke
    const cab = [-120, 150];
    const roof = cut([[cab[0] - 20, -20 + 30], [cab[0] + 130, -110 + 30], [cab[0] + 280, -20 + 30]], 50, 1);
    const walls = cut(rect(cab[0], 10, 260, 150), 51, 1);
    fill(walls, { [wood]: 1 });
    for (let k = 1; k < 6; k++) line([[cab[0], 10 + k * 25], [cab[0] + 260, 10 + k * 25]], 2.5, { mode: 'ink', spec: 'black' });   // clapboards
    fill(roof, 'black');
    fill(rect(cab[0] + 190, -80, 30, 60), 'black');
    const smoke = []; for (let k = 0; k <= 20; k++) { const y = -90 - k * 9; smoke.push([cab[0] + 205 + Math.sin(k * .6 - lt * 2) * 10 * (k / 20), y]); }
    line(part(smoke, rev(lt, .8, 1.6)), 4, { mode: G ? 'paper' : 'ink', spec: 'black' });
    knock(P(rect(cab[0] + 40, 55, 50, 105)), null); line(rect(cab[0] + 40, 55, 50, 105).concat([[cab[0] + 40, 55]]), 4, { mode: 'ink', spec: 'black' });
    knock(P(rect(cab[0] + 150, 50, 60, 50)), null); ink(P(rect(cab[0] + 150, 50, 60, 50)), { ochre: .6 });
    line([[cab[0] + 180, 50], [cab[0] + 180, 100]], 3, { mode: 'ink', spec: 'black' }); line([[cab[0] + 150, 75], [cab[0] + 210, 75]], 3, { mode: 'ink', spec: 'black' });
    line(part(walls.concat([walls[0]]), u), 4, { mode: 'ink', spec: 'black' });
    // the pond: an ellipse of paper with engraved ripples
    const pond = ellipse(40, 240, 330, 50, 0, 48);
    knock(P(pond), null); tint(pond, { slate: G === 'slate' ? 0 : .4 });
    for (let k = 0; k < 4; k++) { const rr = ((lt * .25 + k / 4) % 1); const e = ellipse(-30, 240, 30 + rr * 200, 4 + rr * 30, 0, 32); if (rr < .9) line(e.concat([e[0]]), 2.2, { mode: 'ink', spec: 'black' }); }
    line(pond.concat([pond[0]]), 3, { mode: 'ink', spec: 'black' });
    // caption: WALDEN, 1854
    const cap = shape('WALDEN, 1854', { font: 'roman', size: 50, wght: 700, track: .18 });
    drawText(cap, 0, 350, G ? null : 'black', { align: 'center', knock: !!G, per: (g, i, n) => (i / n <= rev(lt, 1.0, 1.6) ? {} : { skip: true }) });
  });

  // ---------------------------------------------------------------- goodbye: a raised hand, waving
  PICTO.goodbye = (cx, cy, s, t, lt, ground) => plate(cx, cy, s, ground, () => {
    const u = rev(lt, 0, .8), wave = Math.sin(lt * 3.2) * .22 * seg(lt, .8, 1.3);
    const skin = pick('ochre', 'ox');
    // the flourish below: an engraved calligraphic swash (a ribbon with thick-thin), drawing in
    const sw = bez([-300, 250], [-120, 150], [60, 380], [260, 230]).concat(spiral(250, 210, 30, 4, 1.2, Math.PI * .3, 20));
    const swp = part(sw, rev(lt, .5, 1.5));
    if (swp.length > 2) {
      const w = swp.map((p, i) => 4 + 12 * Math.sin(i / sw.length * Math.PI));
      const L2 = [], R2 = [];
      for (let i = 0; i < swp.length; i++) { const a = swp[Math.max(0, i - 1)], b = swp[Math.min(swp.length - 1, i + 1)], d = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1, nx = -(b[1] - a[1]) / d, ny = (b[0] - a[0]) / d; L2.push([swp[i][0] + nx * w[i] / 2, swp[i][1] + ny * w[i] / 2]); R2.push([swp[i][0] - nx * w[i] / 2, swp[i][1] - ny * w[i] / 2]); }
      if (G) knock(P(L2.concat(R2.reverse())), null); else fill(L2.concat(R2.reverse()), 'black');
    }
    // the hand: palm, four fingers splayed, thumb; pivots at the wrist
    save(); translate(0, 190); rotate(wave); translate(0, -190);
    const fingers = [[-95, -.32, 190], [-35, -.1, 225], [25, .08, 215], [80, .3, 175]];
    const palm = cut([[-120, 20], [-110, -90], [110, -90], [125, 10], [95, 150], [-85, 150]], 61, 1.2);
    const parts = [palm];
    fingers.forEach(([x, a, len], i) => {
      const fx = x, fy = -80, tx = fx + Math.sin(a) * len, ty = fy - Math.cos(a) * len;
      parts.push(ribbon([[fx, fy], [lerp(fx, tx, .5), lerp(fy, ty, .5)], [tx, ty]], 52, 44, 70 + i));
      parts.push(circle(tx, ty, 22, 16));
    });
    parts.push(ribbon([[-105, 40], [-170, -20], [-210, -80]], 56, 44, 80)); parts.push(circle(-210, -80, 22, 16));
    const wrist = cut([[-80, 140], [80, 140], [70, 260], [-70, 260]], 62, 1);
    parts.push(wrist);
    silhouette(parts, { [skin]: 1 }, 5);
    clipTo(palm, () => tint(rect(10, -100, 130, 260), { slate: G === 'slate' ? 0 : .5 }));
    line(bez([-80, 10], [-30, 40], [30, 30], [80, -20]), 3.5, { mode: 'ink', spec: 'black' });
    line(bez([-60, 70], [-10, 60], [40, 80], [70, 110]), 3.5, { mode: 'ink', spec: 'black' });
    fingers.forEach(([x, a, len]) => { const kx = x + Math.sin(a) * len * .45, ky = -80 - Math.cos(a) * len * .45; line([[kx - 14, ky + 2], [kx + 14, ky - 2]], 3, { mode: 'ink', spec: 'black' }); });
    fill(rect(-80, 240, 160, 30), 'black');                                              // a cuff
    restore();
    // motion arcs by the fingertips on each swing
    const side = Math.sign(Math.cos(lt * 3.2)) || 1, amt = Math.abs(Math.cos(lt * 3.2)) * seg(lt, .8, 1.3);
    for (let k = 0; k < 3; k++) { const r = 330 + k * 26; line(arcPts(0, 190, r, -Math.PI / 2 + side * (.25 + k * .04), -Math.PI / 2 + side * (.25 + k * .04 + .22 * amt), 10), 5 - k); }
  });

  window.PICTO = PICTO;

  // ---------------------------------------------------------------- test boards
  const NAMES = ['window', 'companion', 'muscle', 'disaster', 'clue', 'salary', 'brainrot', 'goodbye'];
  const GROUNDS = ['slate', null, 'ochre', 'ox', 'black', null, 'slate', 'ochre'];
  LOOPS.picto = t => {
    const cw = W / 2, ch = H / 4;
    NAMES.forEach((n, i) => {
      const x = (i % 2) * cw, y = Math.floor(i / 2) * ch, g = GROUNDS[i];
      if (g) paint(P(rect(x, y, cw, ch)), g);
      PICTO[n](x + cw / 2, y + ch / 2, .6, t, t, g, { stampAt: 2.2 });
      type(n, x + 20, y + 40, { font: 'arch', size: 28, wght: 700, ink: g ? null : 'black', knock: !!g });
    });
  };
  LOOPS.picto.len = 6;
  // one plate full size on its ground: ?loop=p_window etc.
  NAMES.forEach((n, i) => {
    LOOPS['p_' + n] = t => { const g = GROUNDS[i]; if (g) flood(g, 1); PICTO[n](W / 2, H / 2, 1.2, t, t, g, { stampAt: 2.2 }); };
    LOOPS['p_' + n].len = 6;
  });
})();
