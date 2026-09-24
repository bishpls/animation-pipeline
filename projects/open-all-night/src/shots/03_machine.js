// 07–10, 13, 21, 26 · the machine and the eye
(() => {
  LOOPS.eyetest = t => {
    flood('black', 1);
    eye(560, 400, 420, { open: 1, look: [Math.sin(t * 3), 0], iris: { pink: 1 }, lid: 'knock' });
    eye(1420, 400, 380, { open: .4, iris: { blue: 1 }, lid: 'knock' });
    ink(P(rect(0, 700, W, 380)), { pink: 1 }); knock(P(rect(0, 700, W, 380)), ['black']);
    eye(500, 890, 300, { open: 1, squint: .6, iris: { blue: 1 }, look: [.8, 0] });
    eye(1400, 890, 300, { open: 0 });
  };
  LOOPS.eyetest.len = 2;

  // ---------------------------------------------------------------- shared bits
  // a fixed-pitch timecode (digits don't jitter as they change)
  function timecode(v, x, y, size, spec, o = {}) {
    const s = v.toFixed(3), adv = size * .56;
    let cx = x - (s.length * adv + size * .5);
    for (const ch of s) { type(ch, cx + (ch === '.' ? adv * .25 : 0), y, { font: 'arch', size, wdth: 88, wght: 700, ink: spec, knock: o.knock, knockInks: o.knockInks }); cx += ch === '.' ? adv * .55 : adv; }
    type('s', cx + size * .12, y, { font: 'serif', size: size * 1.05, ink: spec, knock: o.knock, knockInks: o.knockInks });
  }
  // a loaded web page (as reflected in the pupil): header, hero image, text lines
  function webPage(cx, cy, w, h, seed = 0) {
    const x = cx - w / 2, y = cy - h / 2;
    knock(P(rrect(x, y, w, h, w * .04)), null);
    paint(P(rect(x, y, w, h * .14)), { pink: 1 });
    for (let i = 0; i < 3; i++) knock(P(circle(x + w * (.06 + i * .05), y + h * .07, h * .025, 10)), ['pink']);
    paint(P(rect(x + w * .07, y + h * .22, w * .52, h * .42)), { yellow: 1 });
    paint(P(circle(x + w * .43, y + h * .36, h * .07, 16)), { pink: 1 });
    paint(P([[x + w * .07, y + h * .64], [x + w * .25, y + h * .44], [x + w * .38, y + h * .64]]), { blue: 1 });
    for (let i = 0; i < 4; i++) paint(P(rect(x + w * .65, y + h * (.24 + i * .1), w * (i === 3 ? .16 : .27), h * .035)), 'black');
    for (let i = 0; i < 3; i++) paint(P(rect(x + w * .07, y + h * (.72 + i * .08), w * (i === 2 ? .5 : .86), h * .035)), 'black');
  }
  // a coin: yellow disc, paper rim, flipping (spin = radians)
  function coin(x, y, r, spin) {
    const sx = Math.max(.08, Math.abs(Math.cos(spin)));
    const edge = P(ellipse(x, y, r * sx, r, 0, 36));
    paint(edge, { yellow: 1 });
    ink(P(ellipse(x, y, r * sx * .78, r * .78, 0, 36)), 'black', { stroke: r * .06 });
    if (sx > .35) knock(P(ellipse(x - r * sx * .25, y - r * .25, r * sx * .16, r * .16, 0, 16)), ['yellow']);
    ink(edge, 'black', { stroke: r * .07 });
  }

  // ---------------------------------------------------------------- 08–09 · the blink, slowed (one continuous scene)
  const BLINK_T = 26.16, SNAP = 28.60, EYE = [960, 560], ER = 780;
  const openAt = t => kf(t, [[BLINK_T, 1], [27.1, .9, 'io2'], [27.9, .76, 'lin'], [28.4, .6, 'io2'], [SNAP - .05, .5, 'lin'], [SNAP, 0, 'in2'], [SNAP + .1, 0], [SNAP + .24, 1.06, 'out3'], [SNAP + .36, 1, 'io2']]);
  const winnerX = EYE[0] + 450;
  function bidders(g, t) {
    const lowerY = x => { const L = g.lower, u = clamp((x - L[0][0]) / (L[L.length - 1][0] - L[0][0])) * (L.length - 1), i = Math.min(L.length - 2, Math.floor(u)); return lerp(L[i][1], L[i + 1][1], u - i); };
    const rows = [{ n: 17, dy: -175, s: 1.0, d: .07 }, { n: 13, dy: -30, s: 1.45, d: 0 }];
    const won = t >= 28.38 && t < SNAP;
    let winDraw = null;
    rows.forEach((R, ri) => {
      for (let i = 0; i < R.n; i++) {
        const u = (i + .5 + (ri % 2) * .35) / R.n, x = lerp(EYE[0] - ER * .95, EYE[0] + ER * .95, u), base = lowerY(x) + R.dy * (ER / 780);
        const appear = 27.02 + u * .48 + R.d + hash(i * 7 + ri) * .05;       // a wave left to right on "mar-ket ap-pears"
        const a = t - appear; if (a < 0) continue;
        const pop = E.back(clamp(a / .16)), s = R.s * (ER / 780) * 1.25;
        const hy = base + (1 - pop) * 90 * s;
        // bidding: paddles jab up on off-beats at machine speed; after the win they all come down except the winner
        const isWin = ri === 1 && Math.abs(x - winnerX) < ER * 1.9 / R.n / 2;
        const jab = won ? (isWin ? .55 : .05) : .6 + .4 * Math.max(0, Math.sin(t * 19 + hash(i * 3.3 + ri) * 9));
        const hr = 17 * s;
        const side = hash(i + ri * 5) > .5 ? 1 : -1, sh = [x + side * hr * 1.1, hy + hr * 1.4];
        const tip = [sh[0] + side * hr * .5, hy - hr * (1.5 + 2.4 * jab)];
        const draw = () => {
        paint(P(cut(blob([[x - hr * 1.7, hy + hr * 3.2], [x - hr * 1.5, hy + hr * 1.2], [x, hy + hr * .8], [x + hr * 1.5, hy + hr * 1.2], [x + hr * 1.7, hy + hr * 3.2]], 3), i * 11 + ri, .6, .3)), 'black');
        paint(P(circle(x, hy, hr, 16)), 'black');
        paint(P(ribbon([sh, tip], hr * .5, hr * .4)), 'black');
        const pc = isWin && won ? { pink: 1 } : hash(i * 1.7 + ri) > .8 ? { blue: 1 } : { yellow: 1 };
        paint(P([[tip[0] - hr * .1, tip[1]], [tip[0] + hr * .1, tip[1]], [tip[0] + hr * .1, tip[1] - hr * .9], [tip[0] - hr * .1, tip[1] - hr * .9]]), 'black');
        const pr = hr * (isWin && won ? 1.6 : 1.25);
        paint(P(cut(circle(tip[0], tip[1] - hr * 1.6, pr, 18), i * 13 + ri, .5, .3)), pc);
        if (isWin && won) { knock(P(circle(tip[0], tip[1] - hr * 1.6, pr + 9, 24)), null, 1, { stroke: 7 }); for (let k = 0; k < 8; k++) { const a = k / 8 * TAU + t * 2; paint(P([[tip[0] + Math.cos(a) * pr * 1.5, tip[1] - hr * 1.6 + Math.sin(a) * pr * 1.5], [tip[0] + Math.cos(a) * pr * 2.1, tip[1] - hr * 1.6 + Math.sin(a) * pr * 2.1]], false), { pink: 1 }, { stroke: 6 }); } }
        };
        if (isWin && won) winDraw = draw; else draw();
        if (isWin) bidders.win = [tip[0], tip[1] - hr * 1.6];
      }
    });
    if (winDraw) winDraw();
  }
  function blinkScene(t) {
    const open = openAt(t);
    const pull = E.out3(seg(t, 25.86, 26.12));                      // match cut: from the gear hub / iris, pull back
    const push = E.io2(seg(t, 26.2, 27.9)) * .22 + E.io2(seg(t, 27.9, SNAP - .02)) * .08;
    const snapBack = t > SNAP ? E.out3(seg(t, SNAP, SNAP + .25)) : 0;
    const into = E.inExpo(seg(t, 29.52, 29.70));                     // out: into the reflected page
    let zoom = lerp(2.6, 1, pull) * (1 + push * (1 - snapBack)) * lerp(1, 7, into);
    const shakeA = t > SNAP && t < SNAP + .3 ? (1 - seg(t, SNAP, SNAP + .3)) * 14 : 0;
    const dil = t < SNAP ? lerp(1, 1.18, seg(t, 26.2, 28.4)) : lerp(1.18, 1.62, E.back(seg(t, SNAP + .15, SNAP + .5)));
    const g0 = { ix: EYE[0], iy: EYE[1] + ER * .02, pr: ER * .43 * .44 * dil };
    const camY = lerp(g0.iy, EYE[1] + 80, push / .3 * (1 - snapBack));
    save(); cam(lerp(g0.ix, g0.ix, 0) + noise1(t * 60) * shakeA, lerp(camY, g0.iy, into) + noise1(t * 60 + 5) * shakeA, zoom);
    flood('black', 1);
    const squint = t > 29.35 ? .28 * E.back(seg(t, 29.35, 29.6)) : 0;
    const g = eye(EYE[0], EYE[1], ER, {
      open, squint, iris: { pink: 1 }, lid: { pink: 1 }, pupil: dil, spin: t < BLINK_T ? (BLINK_T - t) * .8 : 0,
      inWhite: (g) => { if (t < SNAP) bidders(g, t); },
      inPupil: (g) => { if (t > SNAP + .12) webPage(g.px, g.py, g.pr * 1.25, g.pr * .92); },
    });
    // the coin: flips up from the winning paddle and drops into the pupil just before the blink
    if (t >= 28.38 && t < SNAP + .02 && bidders.win) {
      const u = seg(t, 28.38, SNAP + .02), p = arcPt(bidders.win, [EYE[0] + 40, EYE[1] - ER * .12], 200, E.out2(u));
      coin(p[0], p[1], 40 + 110 * E.in2(u), t * 22);
    }
    restore();
    // the timecode: slow time made visible
    const tc = t < BLINK_T ? 0 : t < SNAP ? .1 * Math.pow(seg(t, BLINK_T, SNAP), 2.3) : .1;
    const flash = t > SNAP && t < SNAP + .3;
    if (into < .2) timecode(tc, W - 90, 120, 58, null, { knock: true, knockInks: flash && BF(t) % 2 ? ['black'] : null });
    if (flash && BF(t) % 2) ink(P(rect(W - 460, 50, 380, 90)), { pink: 0 });
  }
  function s08_blink(t) { blinkScene(t); return { lyric: { slot: 'lc', ink: t < 26.02 ? 'black' : 'knock', accentInk: 'knock', stamp: 'pink', size: 62, maxW: 1500 } }; }
  function s09_sold(t) { blinkScene(t); return { lyric: { slot: 'lc', ink: 'knock', accentInk: 'knock', stamp: 'pink', size: 62, maxW: 1500 } }; }


  // ---------------------------------------------------------------- 07 · underneath: the drip falls through the building into the wires
  // gear geometry: teeth around a disc; slots like iris striations; a hole
  function gearPts(cx, cy, R, n, a0, tooth = .12) {
    const p = [];
    for (let i = 0; i < n; i++) {
      const a = a0 + i / n * TAU, da = TAU / n;
      p.push([cx + Math.cos(a) * R, cy + Math.sin(a) * R], [cx + Math.cos(a + da * .12) * R * (1 + tooth), cy + Math.sin(a + da * .12) * R * (1 + tooth)],
        [cx + Math.cos(a + da * .45) * R * (1 + tooth), cy + Math.sin(a + da * .45) * R * (1 + tooth)], [cx + Math.cos(a + da * .57) * R, cy + Math.sin(a + da * .57) * R]);
    }
    return p;
  }
  function gear(cx, cy, R, n, a0, spec, o = {}) {
    paint(P(gearPts(cx, cy, R, n, a0, o.tooth)), spec);
    if (o.slots) for (let i = 0; i < o.slots; i++) { const a = a0 + i / o.slots * TAU, w = i % 2 ? R * .035 : R * .07; ink(P([[cx + Math.cos(a) * R * .5, cy + Math.sin(a) * R * .5], [cx + Math.cos(a) * R * (i % 2 ? .78 : .88), cy + Math.sin(a) * R * (i % 2 ? .78 : .88)]], false), 'black', { stroke: w }); }
    else for (let i = 0; i < 5; i++) { const a = a0 + i / 5 * TAU; paint(P(circle(cx + Math.cos(a) * R * .58, cy + Math.sin(a) * R * .58, R * .16, 16)), 'black'); }
    ink(P(circle(cx, cy, R * .96, 48)), 'black', { stroke: R * (o.slots ? .09 : .05) });
    paint(P(circle(cx, cy, R * (o.hole || .3), 32)), 'black');
  }
  const DRIP_HIT = 24.62, GEAR_T = 25.60, CAB_Y = 1905, GC = [1400, 2250], GR = 200;
  const dripY = t => kf(t, [[23.33, 30], [DRIP_HIT, CAB_Y - 22, 'in2']]);
  function cable(y0, amp, ph) { const p = []; for (let x = -600; x <= 2800; x += 60) p.push([x, y0 + Math.sin(x / 520 + ph) * amp]); return p; }
  const CABLES = [[1790, 30, 0], [1850, 22, 2], [CAB_Y, 14, 4.2], [1975, 26, 1], [2060, 34, 3]];
  function s07_under(t, lt, dur) {
    const u = seg(t, 23.33, DRIP_HIT), dy = dripY(Math.min(t, DRIP_HIT));
    let cy = t < DRIP_HIT ? dy + lerp(250, -60, u) : CAB_Y - 82 + E.io2(seg(t, DRIP_HIT, 25.5)) * 120;
    let cx = 960 + E.io3(seg(t, 24.9, 25.84)) * (GC[0] - 960);
    const hitK = t > DRIP_HIT ? Math.exp(-(t - DRIP_HIT) * 9) : 0;
    const push = E.inExpo(seg(t, 25.62, 25.84));
    cy = lerp(cy, GC[1], E.io3(seg(t, 25.2, 25.84)));
    const zoom = lerp(1, 4.35, push) * (1 + .03 * hitK);
    save(); cam(cx + noise1(t * 50) * 18 * hitK, cy + noise1(t * 50 + 3) * 18 * hitK, zoom);
    flood('blue', 1);
    // --- the building in section (dark rooms at night): floorboards, the neighbour asleep, the bakery, the street
    paint(P(rect(-600, -600, 3200, 600)), 'blue');
    const planks = y => { paint(P(cut(rect(-600, y, 3200, 70), y)), 'black'); for (let x = -560; x < 2600; x += 170) knock(P([[x, y + 8], [x, y + 62]], false), ['black'], 1, { stroke: 3 }); knock(P([[-600, y + 35], [2600, y + 35]], false), ['black'], 1, { stroke: 2.5 }); };
    planks(0);
    paint(P(cut(rect(1320, 170, 260, 230), 71)), 'black'); knock(P(cut(rect(1340, 190, 220, 190), 72)), ['black']); paint(P(circle(1500, 250, 30, 24)), { yellow: 1 });   // window + moon
    paint(P(cut(rect(430, 330, 46, 270), 73)), 'black');                                  // headboard
    paint(P(cut(rect(430, 470, 700, 50), 74)), 'black'); paint(P(rect(1100, 470, 30, 130)), 'black'); paint(P(rect(440, 520, 26, 80)), 'black');
    knock(P(cut(blob([[480, 470], [490, 425], [560, 410], [640, 425], [650, 470]], 4), 75)), ['black', 'blue']);      // pillow
    paint(P(cut(circle(575, 420, 34, 24), 76)), 'black');                                                                // a sleeping head
    paint(P(cut(blob([[620, 472], [640, 420], [760, 400], [900, 425], [1000, 405], [1110, 440], [1120, 472]], 5), 77)), { black: 1 });   // blanket
    knock(P([[660, 440], [1100, 445]], false), ['black'], 1, { stroke: 3, dash: [14, 12] });
    for (let k = 0; k < 3; k++) { const zt = frac(t * .9 + k / 3), zx = 620 + zt * 60, zyy = 360 - zt * 120; type('z', zx, zyy, { font: 'serif', size: 40 + zt * 30, knock: zt < .85, knockInks: ['blue'] }); }
    planks(600);
    // the bakery at night: oven glow, the baker kneading
    const ov = [300, 850, 300, 260];
    paint(P(cut(rect(ov[0] - 30, ov[1] - 40, ov[2] + 60, ov[3] + 390), 76)), 'black');
    knock(P(cut(rrect(ov[0], ov[1], ov[2], ov[3], 120), 77)), ['black', 'blue']); ink(P(rect(ov[0], ov[1], ov[2], ov[3])), { yellow: 1, pink: .0 });
    knock(P(circle(ov[0] + 150, ov[1] + 150, 700)), ['blue'], radial(ov[0] + 150, ov[1] + 150, 120, 700, .8, 1.6));
    const knead = Math.abs(Math.sin(t * 7.8));
    figure(CAST.baker, 1000, 1200, 1.1, { ink: { black: 1 }, aN: [1.3 + .25 * knead, -.9], aF: [1.2 + .25 * knead, -.8], lean: .15 * knead, eyes: 'closed', blush: 0 });
    paint(P(cut(rect(1080, 1020, 420, 40), 78)), 'black'); paint(P(cut(ellipse(1250, 1010, 110, 36 - 10 * knead, 0, 24), 79)), { yellow: 1 });   // table + dough
    // the street: pavement, a manhole, then the dark underground
    paint(P(cut(rect(-600, 1200, 3200, 110), 80)), 'black');
    knock(P([[-600, 1206], [2600, 1206]], false), ['black'], 1, { stroke: 4, dash: [60, 40] });
    paint(P(rect(-600, 1310, 3200, 1600)), 'black');
    for (let i = 0; i < 26; i++) { const x = -500 + hash(i * 3.7) * 3000, y = 1350 + hash(i * 1.9) * 300; paint(P(cut(ellipse(x, y, 30 + hash(i) * 50, 18 + hash(i + 1) * 20, hash(i + 2), 12), 90 + i, 2)), { blue: 1, black: 1 }); }
    // --- the wires: thick blue cables; a spark where the drip lands; pink pulses racing out on the eighths
    CABLES.forEach(([y0, amp, ph], ci) => {
      const pts = cable(y0, amp, ph);
      paint(P(ribbon(pts, 26 + ci * 3, 26 + ci * 3, 100 + ci)), { blue: 1 });
      knock(P(pts.map(([x, y]) => [x, y - 7]), false), ['blue'], 1, { stroke: 3 });
      if (t > DRIP_HIT) {
        const age = t - DRIP_HIT;
        for (let k = 0; k < 10; k++) {
          const born = k * BEAT / 2 + ci * .03; if (age < born) continue;
          const d = (age - born) * 1500;
          for (const dir of [-1, 1]) {
            const x = 960 + dir * d; if (x < -600 || x > 2800) continue;
            const y = y0 + Math.sin(x / 520 + ph) * amp;
            paint(P(ellipse(x, y, 34, 12 + ci, 0, 16)), { pink: 1 });
            knock(P(ellipse(x, y - 2, 14, 3, 0, 8)), ['pink']);
          }
        }
      }
    });
    // --- the gears: blue gears ticking on the beat; the big pink one (it becomes the iris)
    const kick = t > GEAR_T ? E.back(seg(t, GEAR_T, GEAR_T + .2)) : 0, bt = beatPos(t);
    const tickA = (Math.floor(bt) + E.back(clamp(frac(bt) / .15))) * .12 + kick * .6;
    gear(GC[0] - 355, GC[1] - 50, 150, 14, -tickA * 1.33, { blue: 1 });
    gear(GC[0] + 300, GC[1] + 170, 120, 11, -tickA * 1.66, { blue: 1 });
    gear(GC[0] - 120, GC[1] + 290, 90, 9, tickA * 2.2, { blue: 1 });
    gear(GC[0], GC[1], GR, 18, tickA, { pink: 1 }, { slots: 28, hole: .44 * .44 * 1.02 / .43 * .43 });
    gear(520, 2230, 130, 12, tickA * 1.5, { blue: 1 }); gear(700, 2380, 80, 8, -tickA * 2.4, { blue: 1 });
    // --- the drip: blue drop with a paper glint, stretched by its speed; then the spark
    if (t < DRIP_HIT) {
      const v = clamp(u * 1.6), x = 960, y = dy;
      const drop = [[x, y - 40 - 90 * v], [x + 20, y - 6], [x + 22, y + 12], [x, y + 30], [x - 22, y + 12], [x - 20, y - 6]];
      paint(P(blob(drop, 5)), { blue: 1 }); ink(P(blob(drop, 5)), 'black', { stroke: 5 }); knock(P(ellipse(x - 7, y + 4, 5, 10, .3, 10)), null);
    } else if (t < DRIP_HIT + .35) {
      const a = t - DRIP_HIT, r = 40 + a * 700, k = 1 - a / .35;
      knock(P(circle(960, CAB_Y, r * 1.6)), ['black', 'blue'], radial(960, CAB_Y, 10, r * 1.6, k, 1));
      paint(P(starPts(960, CAB_Y, r * 1.1, r * .22, 8)), { pink: 1, yellow: 1 });
      knock(P(starPts(960, CAB_Y, r * .5, r * .12, 8)), null);
    }
    restore();
    // speed lines while falling (screen space)
    const sp = Math.sin(Math.PI * clamp(u * 1.1)) * (t < DRIP_HIT ? 1 : 0);
    if (sp > .2) for (let i = 0; i < 14; i++) { const x = 80 + hash(i * 7.3) * 1760, len = 200 + 400 * sp * hash(i + 3), y = frac(hash(i) - t * 3) * (H + len) - len; knock(P([[x, y], [x, y + len]], false), null, 1, { stroke: 3 + 4 * hash(i + 9) }); }
    return { lyric: { slot: 'ul', ink: 'knock', accentInk: 'knock', size: 62, y: 180, maxW: 1750 } };
  }
  SHOT_FN['07'] = s07_under;


  // ---------------------------------------------------------------- 10 · every little window, every open door
  const S10 = { cols: 6, rows: 3, x0: 170, y0: 250, cw: 265, rh: 190, doorY: 840 };
  const winTimes = [29.70, 29.77, 29.84, 29.95, 30.06, 30.17, 30.26];     // syllables: ev-e-ry lit-tle win-dow
  const doorTimes = [30.36, 30.36, 30.58, 30.58, 30.80, 30.80];
  function s10_open(t, lt, dur) {
    const pull = E.out3(seg(t, 29.70, 30.25));
    const cwin = [S10.x0 + 2.5 * S10.cw + S10.cw * .5, S10.y0 + S10.rh * 1 + S10.rh * .4];
    const zoom = lerp(3.2, 1, pull), cx = lerp(cwin[0] - S10.cw * .5, W / 2, pull), cy = lerp(cwin[1], H / 2, pull);
    const flash = E.in2(seg(t, 30.80, 30.97));
    save(); cam(cx, cy, zoom);
    flood('blue', 1);
    paint(P(cut(rect(40, 40, W - 80, 1200), 501, 1.5)), 'black');                 // the facade
    for (let r = 0; r < S10.rows; r++) for (let c = 0; c < S10.cols; c++) {
      const x = S10.x0 + c * S10.cw + S10.cw * .12, y = S10.y0 + r * S10.rh + S10.rh * .1, w = S10.cw * .76, h = S10.rh * .72;
      const k = Math.min(winTimes.length - 1, Math.floor((c + r * 1.4) / 1.25));
      const ot = (r === 1 && c === 2) ? 29.66 : winTimes[k] + hash(r * 9 + c) * .03, o = E.back2(seg(t, ot, ot + .16));
      const room = P(cut(rect(x, y, w, h), 510 + r * 9 + c, .8));
      if (o > .02) {
        knock(room, null);                                                    // the lit room: paper
        if (t - ot > .06) ink(room, { yellow: 1 });                        // a paper flash as it opens, then lamplight
        const who = (r * 5 + c * 3) % 5;                                      // who's up at this hour
        const bx = x + w * .5, by = y + h;
        if (who === 0) head(CAST.anon, bx, by - h * .35, .9, { var: r + c, face: c % 2 ? 1 : -1, ink: { black: 1 } });
        if (who === 1) { paint(P(cut(rect(bx - 40, by - 34, 80, 34), 520 + c)), 'black'); paint(P(cut(circle(bx - 10, by - 70, 26, 16), 521 + c)), 'black'); }  // a reader at a desk
        if (who === 2) { paint(P(cut(blob([[bx - 30, by], [bx - 26, by - 40], [bx - 34, by - 70], [bx - 20, by - 62], [bx + 20, by - 62], [bx + 34, by - 70], [bx + 26, by - 40], [bx + 30, by]], 3), 522 + r)), 'black'); }  // a cat
        if (who === 3) { paint(P(cut(rect(bx + 10, by - 60, 70, 46), 523)), 'black'); knock(P(rect(bx + 16, by - 54, 58, 34)), ['black']); ink(P(rect(bx + 16, by - 54, 58, 34)), { pink: 1 }); }  // a screen glowing
        // light pouring down the facade (halftone yellow)
        const beam = [[x, by], [x + w, by], [x + w + 60, by + 150], [x - 60, by + 150]];
        knock(P(beam), ['black'], linear(0, by, 0, by + 150, .85 * o, 0));
        ink(P(beam), { yellow: linear(0, by, 0, by + 150, .6 * o, 0) });
      }
      // shutters: two blue panels hinged at the frame edges, swinging open (x-scale -> 0, past it, a sliver)
      const sw = w / 2, sh = Math.abs(Math.cos(o * Math.PI / 2 * 1.05)) * sw;
      for (const side of [0, 1]) {
        const hx = side ? x + w : x, px = side ? hx - sh : hx, ww = sh;
        if (o < .98 || ww > 2) {
          const sp = P(cut(rect(side ? hx - (o < 1 ? sh : 0) : hx - (o > 0 ? 0 : 0), y, Math.max(2, ww), h), 530 + r * 9 + c + side, .6));
          const opened = o > .5;
          const X0 = opened ? (side ? hx : hx - Math.max(2, ww)) : px;
          const panel = P(cut(rect(X0, y, Math.max(2, ww), h), 540 + side + r * 9 + c, .6));
          paint(panel, { blue: 1 });
          for (let s = 1; s < 5; s++) knock(P([[X0 + 3, y + h * s / 5], [X0 + Math.max(2, ww) - 3, y + h * s / 5]], false), ['blue'], 1, { stroke: 2.5 });
        }
      }
      paint(P(rect(x - 10, y + h, w + 20, 14)), { pink: 1 });                  // sill
    }
    // the ground floor: six doors
    for (let d = 0; d < 6; d++) {
      const x = S10.x0 + d * S10.cw + S10.cw * .22, y = S10.doorY, w = S10.cw * .56, h = 250;
      const o = E.back(seg(t, doorTimes[d] + (d % 2) * .04, doorTimes[d] + (d % 2) * .04 + .18));
      const frame = P(cut(rect(x, y, w, h), 560 + d, .8));
      if (o > .02) {
        knock(frame, null);
        const spill = [[x, y + h], [x + w, y + h], [x + w + 180 * o, y + h + 260], [x - 180 * o, y + h + 260]];
        knock(P(spill), null, linear(0, y + h, 0, y + h + 260, o, .2 * o));
      }
      const dw = w * Math.abs(Math.cos(o * Math.PI / 2 * 1.02));
      paint(P(cut(rect(x, y, Math.max(3, dw), h), 570 + d, .6)), { pink: 1 });
      knock(P(circle(x + Math.max(3, dw) * .82, y + h * .55, 7, 10)), ['pink']);
      paint(P(rect(x - 12, y - 16, w + 24, 16)), { yellow: 1 });
    }
    restore();
    if (t > 30.985) flood('black', 1);                                      // the band stops: a held black beat
    return { lyric: t > 30.985 ? false : { slot: 'uc', ink: 'knock', accentInk: 'knock', size: 88, y: 150, maxW: 1800, wdth: 70 } };
  }
  SHOT_FN['10'] = s10_open;


  // ---------------------------------------------------------------- 13 / 26 · the glance (chorus 1) and the wink (final chorus)
  function stampBox(txt, x, y, size, spec, age, rot = -.08) {
    if (age < 0) return;
    const S = shape(txt, { font: 'arch', size, wdth: 100, wght: 900 }), th = 1 + .35 * (1 - E.out3(clamp(age / .14))), pad = size * .22;
    save(); translate(x, y); rotate(rot); scale(th); translate(-S.width / 2, S.cap / 2);
    paint(P(rrect(-pad, -S.cap - pad, S.width + pad * 2, S.cap + pad * 2, 8)), spec, { stroke: 7 });
    drawText(S, 0, 0, null, { knock: false, per: () => ({ spec }) });
    restore();
  }
  function glanceScene(t, lt, dur, mode) {
    const L = LINES.find(l => l.i === (mode === 'wink' ? 24 : 11));
    const words = L.words.filter(w => !w.adlib), ad = L.words.filter(w => w.adlib);
    const tG = words[words.length - 1].t0, tAd = ad.length ? ad[0].t0 : tG + .7, t0 = L.t0 - .3;
    const EC = mode === 'wink' ? [900, 640] : [960, 565], R = mode === 'wink' ? 380 : 340;
    // camera: settle in; at the end (13 only) push into the pupil
    const into = mode === 'glance' ? E.inExpo(seg(t, t0 + dur - .42, t0 + dur - .02)) : 0;
    const openIn = E.back(seg(t, t0 + .02, t0 + .3));
    let look = kf(t, [[tG - .12, 0], [tG - .02, -.14, 'io2'], [tG + .07, .85, 'outExpo'], [tAd - .02, .85], [tAd + .07, -.7, 'outExpo'], [tAd + .5, -.7], [tAd + .62, 0, 'io3']]);
    let open = openIn, squint = 0;
    if (mode === 'wink') { open = kf(t, [[t0, openIn], [tG - .02, 1], [tG + .06, 0, 'in2'], [tG + .22, 0], [tG + .36, 1, 'out3']]) * (t < tG ? openIn : 1); squint = kf(t, [[tG + .2, 0], [tG + .36, .35, 'out3'], [tAd + .6, .35]]); look = 0; }
    const g0 = { px: EC[0] + look * R * .42, py: EC[1] + R * .02 };
    const bump = mode === 'wink' ? .07 * wobble(t, tG, 3, 6) + .05 * Math.exp(-Math.max(0, t - tG) * 5) * (t > tG ? 1 : 0) : 0;
    const zoom = lerp(1, 18, into) * (1 + bump), drift = 1 + .04 * E.io2(clamp(lt / dur));
    save(); cam(lerp(W / 2, g0.px, E.io3(clamp(into * 3))), lerp(H / 2, g0.py, E.io3(clamp(into * 3))), zoom * drift);
    if (mode === 'wink') {                                            // dawn: a pink sky, a yellow horizon, the sun rising
      flood('pink', 1);
      ink(P(rect(-400, 560, W + 800, 360)), { yellow: linear(0, 920, 0, 560, .9, 0) });     // dawn glow over the horizon: halftone orange
      paint(P(rect(-400, 915, W + 800, 600)), { yellow: 1 });
    } else {
      flood('pink', 1);
      const dk = P(cut(circle(EC[0], EC[1], 415, 96), 601, 2));     // the sun-disk behind the eye
      paint(dk, { yellow: 1 });
      for (let i = 0; i < 24; i++) { const a = i / 24 * TAU + t * .15; ink(P([[EC[0] + Math.cos(a) * 425, EC[1] + Math.sin(a) * 425], [EC[0] + Math.cos(a) * 700, EC[1] + Math.sin(a) * 700]], false), { yellow: 1 }, { stroke: i % 2 ? 6 : 14 }); }
    }
    // the lyric: a badge ring around the eye, one word per sung word
    const ringR = mode === 'wink' ? 480 : 485, size = mode === 'wink' ? 72 : 76;
    let total = 0; for (const w of words) total += shape(w.w.toUpperCase(), { font: 'arch', size, wdth: 86, wght: 900 }).width / ringR + .5 * size / ringR;
    ringText(words, EC[0], EC[1], ringR, -total / 2 + .02 * Math.sin(t * .7), { t, size, wdth: 86, ink: 'black' });
    eye(EC[0], EC[1], R, { open, squint, look: [look, 0], iris: mode === 'wink' ? { pink: 1 } : { blue: 1 }, pupil: 1 + .15 * pulse(t, 5, 1), spin: t * .3 });
    // the penny: flips out of the eye's corner on the glance
    if (t > tG) {
      const a = t - tG;
      if (mode === 'glance') {
        const u = clamp(a / .9), p = arcPt([EC[0] + R * .95, EC[1]], [EC[0] + 720, EC[1] - 120], 420, E.out2(u));
        if (u < 1) coin(p[0], p[1], 72, a * 20);
        else { const u2 = clamp((a - .9) / .5), p2 = [EC[0] + 720, EC[1] - 120 + E.in2(u2) * 900]; coin(p2[0], p2[1], 72, a * 20); }
      } else {                                                          // the wink throws a penny up to become the sun
        const u = E.io3(clamp(a / 1.1)), sx = lerp(EC[0] + R * .8, 1560, u), sy = lerp(EC[1] - R * .2, 240, u), r = lerp(40, 150, u), spin = (1 - u) * a * 24;
        if (u > .6) { knock(P(circle(sx, sy, r * 3.2)), ['pink'], radial(sx, sy, r, r * 3.2, .8 * (u - .6) / .4, 1.3)); for (let i = 0; i < 16; i++) { const q = i / 16 * TAU + t * .2; paint(P([[sx + Math.cos(q) * r * 1.25, sy + Math.sin(q) * r * 1.25], [sx + Math.cos(q) * r * (1.6 + .3 * (i % 2)), sy + Math.sin(q) * r * (1.6 + .3 * (i % 2))]], false), { yellow: 1 }, { stroke: 8 }); } }
        if (u < .95) coin(sx, sy, r, spin); else paint(P(cut(circle(sx, sy, r, 64), 611, 1.5)), { yellow: 1 });
      }
    }
    restore();
    if (ad.length && into < .3) stampBox(ad.map(w => w.w).join(' ').toUpperCase(), mode === 'wink' ? 1540 : 1540, mode === 'wink' ? 1010 : 960, 64, 'black', t - tAd, -.09);
    return { lyric: false };
  }
  function s13_glance(t, lt, dur) { return glanceScene(t, lt, dur, 'glance'); }
  function s26_wink(t, lt, dur) { return glanceScene(t, lt, dur, 'wink'); }
  SHOT_FN['13'] = s13_glance; SHOT_FN['26'] = s26_wink;


  // ---------------------------------------------------------------- 21 · the little gears behind the glass
  function s21_machine(t, lt, dur) {
    const bp = beatPos(t), tick = Math.floor(bp) + E.back(clamp(frac(bp) / .16));
    const a1 = tick * .11;
    const G1 = [620, 520, 300, 24], G2 = [1062, 314, 170, 14], G3 = [1130, 702, 210, 17], G4 = [1458, 644, 110, 9];
    const a2 = -a1 * G1[2] / G2[2] + .12, a3 = a1 * G1[2] / G3[2] + .05, a4 = -a3 * G3[2] / G4[2] + .2;
    const dolly = E.io2(clamp(lt / dur)), up = E.in3(seg(t, 67.2, 67.56));
    save(); cam(lerp(820, 1120, dolly), lerp(560, 520, dolly) - up * 500, lerp(1.08, 1.16, dolly));
    flood('blue', 1);
    // the pulse track: a pink line snaking through the works, pulses racing along it
    const track = [[-300, 180], [200, 160], [380, 260], [880, 120], [1300, 150], [1500, 300], [1700, 420], [2300, 380]];
    const tp = blob(track.concat(track.slice(1, -1).reverse()), 8).slice(0, 8 * (track.length - 1));
    ink(P(tp, false), { black: 1 }, { stroke: 18 });
    for (let k = 0; k < 6; k++) { const u = frac(t * .55 + k / 6), i = Math.floor(u * (tp.length - 1)), p = tp[i]; paint(P(circle(p[0], p[1], 13, 12)), { pink: 1 }); knock(P(circle(p[0] - 3, p[1] - 3, 4, 8)), ['pink']); }
    // the gears: black, a paper rim line, pink hubs; the big ones keep an eye on things
    const blackGear = ([x, y, R, n], a, eyeO) => {
      paint(P(gearPts(x, y, R, n, a, .1)), 'black');
      knock(P(circle(x, y, R * .84, 64)), ['black'], 1, { stroke: 3 });
      for (let i = 0; i < 6; i++) { const q = a + i / 6 * TAU; knock(P(ellipse(x + Math.cos(q) * R * .56, y + Math.sin(q) * R * .56, R * .17, R * .12, q, 16)), ['black']); }
      paint(P(circle(x, y, R * .34, 40)), { pink: 1 });
      if (eyeO) { const bl = frac(t * .45 + eyeO) < .08 ? 0 : 1; eye(x, y, R * .3, { open: bl, iris: { blue: 1 }, look: [Math.sin(t * 1.3 + eyeO * 5) * .7, 0], lashes: 5, crease: false }); }
      else paint(P(circle(x, y, R * .1, 16)), 'black');
    };
    blackGear(G1, a1, .1); blackGear(G2, a2); blackGear(G3, a3, .6); blackGear(G4, a4);
    // the paddle wheel: little bidders riding a wheel, raising paddles as they come over the top
    const PW = [1560, 250, 150], pa = -tick * .2;
    paint(P(circle(PW[0], PW[1], PW[2] * .2, 20)), 'black');
    for (let i = 0; i < 8; i++) {
      const q = pa + i / 8 * TAU, tip = [PW[0] + Math.cos(q) * PW[2], PW[1] + Math.sin(q) * PW[2]];
      paint(P([[PW[0], PW[1]], tip], false), 'black', { stroke: 8 });
      const top = clamp(-Math.sin(q));                                  // raise the paddle near the top
      paint(P(circle(tip[0], tip[1], 16, 14)), 'black');
      const pp = [tip[0] + 8, tip[1] - 30 - 30 * top];
      paint(P([[tip[0] + 8, tip[1]], pp], false), 'black', { stroke: 6 });
      paint(P(circle(pp[0], pp[1] - 12, 14 + 4 * top, 14)), i === 3 ? { pink: 1 } : { yellow: 1 });
    }
    // the coin belt
    paint(P(cut(rect(-300, -40, 2600, 40), 701)), 'black');                            // an overhead conveyor of coins
    for (let x = -300; x < 2300; x += 170) { paint(P(circle(x, -20, 26, 20)), 'black'); knock(P(circle(x, -20, 26, 20)), ['black'], 1, { stroke: 3 }); }
    for (let k = 0; k < 14; k++) { const x = -300 + frac(k / 14 + t * .12) * 2600; paint(P([[x, 0], [x, 26]], false), 'black', { stroke: 4 }); coin(x, 52, 28, .3 + k); }
    restore();
    // through the glass: paper sheen streaks wipe away as we pass the screen
    const g = seg(t, 65.60, 66.05);
    if (g < 1) for (let i = 0; i < 3; i++) { const x = lerp(-400, 2600, E.in2(g)) + i * 260 - 400, w = [140, 50, 24][i]; knock(P([[x, -50], [x + w, -50], [x + w - 500, H + 50], [x - 500, H + 50]]), null, 1); }
    return { lyric: { slot: 'll', ink: 'knock', accentInk: 'knock', size: 64, y: 1010, maxW: 1400 } };
  }
  SHOT_FN['21'] = s21_machine;

  SHOT_FN['08'] = s08_blink; SHOT_FN['09'] = s09_sold;
})();
