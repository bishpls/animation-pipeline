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
  const openAt = t => kf(t, [[BLINK_T, 1], [27.9, .5, 'io2'], [SNAP - .05, .36, 'lin'], [SNAP, 0, 'in2'], [SNAP + .1, 0], [SNAP + .24, 1.06, 'out3'], [SNAP + .36, 1, 'io2']]);
  const winnerX = EYE[0] + 360;
  function bidders(g, t) {
    const lowerY = x => { const L = g.lower, u = clamp((x - L[0][0]) / (L[L.length - 1][0] - L[0][0])) * (L.length - 1), i = Math.min(L.length - 2, Math.floor(u)); return lerp(L[i][1], L[i + 1][1], u - i); };
    const rows = [{ n: 34, dy: -250, s: .55, d: .1 }, { n: 28, dy: -150, s: .75, d: .05 }, { n: 22, dy: -50, s: 1, d: 0 }];
    const won = t >= 28.38 && t < SNAP;
    rows.forEach((R, ri) => {
      for (let i = 0; i < R.n; i++) {
        const u = (i + .5 + (ri % 2) * .35) / R.n, x = lerp(EYE[0] - ER * .95, EYE[0] + ER * .95, u), base = lowerY(x) + R.dy * (ER / 780);
        const appear = 27.08 + u * .5 + R.d + hash(i * 7 + ri) * .06;       // a wave left to right on "mar-ket ap-pears"
        const a = t - appear; if (a < 0) continue;
        const pop = E.back(clamp(a / .16)), s = R.s * (ER / 780) * 1.25;
        const hy = base + (1 - pop) * 90 * s;
        // bidding: paddles jab up on off-beats at machine speed; after the win they all come down except the winner
        const isWin = ri === 2 && Math.abs(x - winnerX) < ER * 1.9 / R.n / 2;
        const jab = won ? (isWin ? 1.25 : .15) : .6 + .4 * Math.max(0, Math.sin(t * 19 + hash(i * 3.3 + ri) * 9));
        const hr = 17 * s;
        paint(P(cut(blob([[x - hr * 1.7, hy + hr * 3.2], [x - hr * 1.5, hy + hr * 1.2], [x, hy + hr * .8], [x + hr * 1.5, hy + hr * 1.2], [x + hr * 1.7, hy + hr * 3.2]], 3), i * 11 + ri, .6, .3)), 'black');
        paint(P(circle(x, hy, hr, 16)), 'black');
        const side = hash(i + ri * 5) > .5 ? 1 : -1, sh = [x + side * hr * 1.1, hy + hr * 1.4];
        const tip = [sh[0] + side * hr * .5, hy - hr * (1.5 + 2.4 * jab)];
        paint(P(ribbon([sh, tip], hr * .5, hr * .4)), 'black');
        const pc = isWin && won ? { pink: 1 } : hash(i * 1.7 + ri) > .8 ? { blue: 1 } : { yellow: 1 };
        paint(P([[tip[0] - hr * .1, tip[1]], [tip[0] + hr * .1, tip[1]], [tip[0] + hr * .1, tip[1] - hr * .9], [tip[0] - hr * .1, tip[1] - hr * .9]]), 'black');
        const pr = hr * (isWin && won ? 1.25 : .95);
        paint(P(cut(circle(tip[0], tip[1] - hr * 1.6, pr, 18), i * 13 + ri, .5, .3)), pc);
        if (isWin && won) knock(P(circle(tip[0], tip[1] - hr * 1.6, pr * 2.3)), ['black'], radial(tip[0], tip[1] - hr * 1.6, pr, pr * 2.3, .9, 1.2));
        if (isWin) bidders.win = [tip[0], tip[1] - hr * 1.6];
      }
    });
  }
  function blinkScene(t) {
    const open = openAt(t);
    const pull = E.out5(seg(t, 25.84, 26.12));                      // match cut: from the gear hub / iris, pull back
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
    if (t >= 28.38 && t < SNAP && bidders.win) {
      const u = seg(t, 28.38, SNAP - .02), p = arcPt(bidders.win, [g.px, g.py], 160, E.in2(u));
      coin(p[0], p[1], 34 * (1 - u * .4), t * 26);
    }
    restore();
    // the timecode: slow time made visible
    const tc = t < BLINK_T ? 0 : t < SNAP ? .1 * Math.pow(seg(t, BLINK_T, SNAP), 2.3) : .1;
    const flash = t > SNAP && t < SNAP + .3;
    if (into < .2) timecode(tc, W - 90, 120, 58, flash && BF(t) % 2 ? 'yellow' : { pink: 1 });
  }
  function s08_blink(t) { blinkScene(t); return { lyric: { slot: 'lc', ink: 'knock', accentInk: 'pink', stamp: 'pink', size: 62, maxW: 1500 } }; }
  function s09_sold(t) { blinkScene(t); return { lyric: { slot: 'lc', ink: 'knock', accentInk: 'pink', stamp: 'yellow', size: 62, maxW: 1500, stampX: 1320, stampY: 150 } }; }

  SHOT_FN['08'] = s08_blink; SHOT_FN['09'] = s09_sold;
})();
