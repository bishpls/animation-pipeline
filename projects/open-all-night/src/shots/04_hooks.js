// 11, 14, 15, 24, 27 · hook type and the world (owns src/hook.js, src/globe.js)
(() => {
  // A justified poster block: rows of text fitted to one width, block height solved to `maxH`, centred at (cx, cy).
  function posterBlock(rows, cx, cy, maxW, maxH, gap = .07) {
    const probe = rows.map(r => fitRow(r.txt, 1000, r));
    const capSum = probe.reduce((a, L) => a + L.cap, 0);
    const w = Math.min(maxW, 1000 * maxH / (capSum * (1 + gap * (rows.length - 1) / rows.length * 1.0) + 1e-6));
    const Ls = rows.map(r => fitRow(r.txt, w, r));
    const g = Ls.reduce((a, L) => a + L.cap, 0) * gap;
    const H0 = Ls.reduce((a, L) => a + L.cap, 0) + g * (rows.length - 1);
    let y = cy - H0 / 2;
    return Ls.map(L => { y += L.cap; const o = { L, x: cx - w / 2, y, w }; y += g; return o; });
  }

  // ---------------------------------------------------------------- 11 · KEEP IT OPEN ALL NIGHT (chorus 1)
  // Reads: pink smash on the downbeat, rays burst; KEEP / IT / OPEN / ALL NIGHT! land on the syllables;
  // O-P-E-N swing open like doors with yellow light behind; the choir stamps (ALL NIGHT!).
  function s11_hook(t, lt, dur) {
    const W9 = LINES[9].words, T = { keep: W9[0].t0, it: W9[1].t0, open: W9[2].t0, all: W9[3].t0, night: W9[4].t0, ad: W9[5].t0 };
    const beats = [0, 1, 2, 3].map(i => beatT(Math.ceil(beatPos(32.9)) + i));
    const k = kick(t, [31.07, T.keep, T.it, T.open, T.all, T.night], 1) + kick(t, beats, .45, 11);
    const [sx, sy] = [noise1(t * 31) * 7 * k, noise1(t * 29 + 5) * 7 * k];
    save(); cam(W / 2 + sx, H / 2 + sy, 1 + .018 * k + .03 * E.out2(lt / dur));
    paint(P(rect(-200, -200, W + 400, H + 400)), { pink: 1 });
    // rays: burst out from behind the block on the downbeat, then turn slowly
    const grow = E.out5(seg(t, 31.07, 31.55));
    const rays = 18, rr = 1700 * grow;
    for (let i = 0; i < rays; i++) {
      const a0 = lt * .09 + i / rays * TAU, a1 = a0 + TAU / rays * .42;
      knock(P([[W / 2, H / 2], [W / 2 + Math.cos(a0) * rr, H / 2 + Math.sin(a0) * rr], [W / 2 + Math.cos(a1) * rr, H / 2 + Math.sin(a1) * rr]]), ['pink'], radial(W / 2, H / 2, 150, rr, .55, .6));
    }
    const B = posterBlock([{ txt: 'KEEP IT', wdth: 100, space: .16 }, { txt: 'OPEN', wdth: 125 }, { txt: 'ALL NIGHT!', wdth: 72, space: .1 }], W / 2, H / 2 + 6, 1600, 840, .085);
    slamWords(B[0].L, B[0].x, B[0].y, t, [T.keep, T.it], 'black', { from: 1.5, rot: -.05 });
    // OPEN: closed black doors slam in, then swing open one by one on eighth notes, light behind
    const so = slamT(t, T.open, { from: 1.35 });
    if (so.vis) {
      const L = B[1].L, px = B[1].x + L.width / 2, py = B[1].y - L.cap / 2;
      save(); translate(px, py); scale(so.sc); translate(-px, -py);
      doorLetters(L, B[1].x, B[1].y, t, T.open + .14, { stagger: BEAT / 4, dur: .38, light: { yellow: 1 }, field: ['pink'] });
      restore();
    }
    // ALL NIGHT!: paper, with a black offset shadow (second-colour drop, poster style)
    const off = B[2].L.cap * .045;
    slamWords(B[2].L, B[2].x + off, B[2].y + off, t, [T.all, T.night], { black: 1 }, { from: 1.5, rot: .04 });
    slamWords(B[2].L, B[2].x, B[2].y, t, [T.all, T.night], null, { knock: true, from: 1.5, rot: .04 });
    restore();
    stampAt('ALL NIGHT!', 1330, 700, t, T.ad, { size: 84, ink: 'black', fill: { black: 1 }, knockText: true, rot: -.11, hold: .95 });
    return { lyric: false };
  }

  // rotating poster rays knocked into a flood (continuity across the chorus)
  function rays(cx, cy, lt, grow = 1, n = 18, field = ['pink'], a = .55) {
    const rr = 1900 * grow;
    for (let i = 0; i < n; i++) {
      const a0 = lt * .09 + i / n * TAU, a1 = a0 + TAU / n * .42;
      knock(P([[cx, cy], [cx + Math.cos(a0) * rr, cy + Math.sin(a0) * rr], [cx + Math.cos(a1) * rr, cy + Math.sin(a1) * rr]]), field, radial(cx, cy, 150, rr, a, .6));
    }
  }
  const WORLD_ARCS = t0 => [['nyc', 'rome'], ['nyc', 'lon'], ['nyc', 'sao'], ['nyc', 'lag'], ['rome', 'nai'], ['nyc', 'mex'], ['rome', 'bom'], ['lon', 'jnb'], ['nyc', 'la']]
    .map(([a, b], i) => ({ a, b, t0: t0 + i * .07, dur: .55 + .1 * (i % 3), keep: i === 0 }));

  // ---------------------------------------------------------------- 14 · and the whole world's yours tonight
  // Reads: the pupil we pushed into opens out: it is the Earth at night; lights spread from New York on "whole";
  // arcs fly to Rome and everywhere on "world's"; every city pings on "yours"; the globe bounces on "tonight".
  const S14_END = { x: 620, y: 540, R: 390 };                       // where S14 leaves the globe (S15 matches it)
  function s14_world(t, lt, dur) {
    const W12 = LINES[12].words, T = W12.map(w => w.t0);          // and the whole world's yours tonight
    const out = E.outExpo(clamp(lt / .75));
    const bounce = 1 + .07 * wobble(t, T[5], 2.2, 5) + .03 * wobble(t, T[4], 3, 7);
    const R = lerp(1500, S14_END.R, out) * bounce, cx = lerp(W / 2, S14_END.x, out), cy = S14_END.y;
    paint(P(rect(0, 0, W, H)), { pink: 1 });
    rays(cx, cy, lt + 1, clamp(out * 1.3));
    knock(P(circle(cx, cy, R * 1.45)), ['pink'], radial(cx, cy, R * .98, R * 1.45, .75, 1.6));   // the glow of a lit planet
    globe(cx, cy, R, { lon0: -38 + lt * 13, lat0: 22, t, lights: E.out2(seg(t, T[2] - .05, T[3] + .2)), from: 'nyc',
      arcs: WORLD_ARCS(T[3]), pingAll: T[4], arcW: 2 });
    // the words: a justified block, right of the globe
    const rows = [[0, 1], [2, 3], [4], [5]], x0 = 1085, w = 740;
    const Ls = rows.map(r => fitRow(r.map(i => W12[i].w.toUpperCase().replace(',', '')).join(' '), w, { wdth: 62, space: .1 }));
    const gap = 22, Htot = Ls.reduce((a, L) => a + L.cap, 0) + gap * 2;
    let y = H / 2 - Htot / 2;
    Ls.forEach((L, ri) => { y += L.cap; slamWords(L, x0, y, t, rows[ri].map(i => T[i]), 'black', { from: 1.45, rot: ri % 2 ? .04 : -.04 }); y += gap; });
    return { lyric: false };
  }

  // ---------------------------------------------------------------- 15 · keep it open all night!
  // Reads: pull back: the globe slides into place as the O of the OPEN sign; P, E, N flick on with the syllables;
  // the border lights on "all"; a flash on "night!" to the dawn yellow.
  function signLayout(s, cx, cy) {
    const gap = s * .2, widths = [.84, .5, .5, .52], total = widths.reduce((a, b) => a + b, 0) * s + gap * 3;
    let x = cx - total / 2; const xs = [];
    widths.forEach(w => { xs.push(x); x += w * s + gap; });
    return { xs, total, s, cy };
  }
  function s15_sign(t, lt, dur) {
    const W13 = LINES[13].words, T = W13.map(w => w.t0);            // keep it open all night!
    const S = signLayout(285, W / 2, 505);
    const oR = S.s * .4, oc = [S.xs[0] + S.s * .42, S.cy];
    // camera: starts matching S14's last frame (the globe at S14_END), pulls back to reveal the sign
    const z0 = S14_END.R / oR, u = E.io3(clamp(lt / .62));
    const z = lerp(z0, 1, u), c0 = [oc[0] - (S14_END.x - W / 2) / z0, oc[1] - (S14_END.y - H / 2) / z0];
    save(); cam(lerp(c0[0], W / 2, u), lerp(c0[1], H / 2, u), z);
    paint(P(rect(-3000, -3000, 7000, 7000)), { pink: 1 });
    rays(oc[0], oc[1], lt + 4, lerp(1, .5, u));
    knock(P(circle(oc[0], oc[1], oR * 1.45)), ['pink'], radial(oc[0], oc[1], oR * .98, oR * 1.45, .75 * (1 - u), 1.6));
    const flick = (t0, on = 1) => (t < t0 ? 0 : t < t0 + .04 ? on : t < t0 + .08 ? 0 : on);
    const tube = { ink: 'yellow', flood: 'pink', darkInks: ['pink'] };
    globe(oc[0], oc[1], oR, { lon0: -38 + (lt + 3.12) * 13, lat0: 22, t, lights: 1, dotR: 1 });
    neon(circle(oc[0], oc[1], oR + S.s * .08, 64).concat([[oc[0] + oR + S.s * .08, oc[1]]]), S.s * .1, flick(T[0]), tube);
    const L = (k, f) => f().map(([a, b]) => [S.xs[k] + a * S.s, S.cy + b * S.s]);
    neon(L(1, SIGN_LETTERS.P), S.s * .12, flick(T[1]), tube);
    neon(L(2, SIGN_LETTERS.E), S.s * .12, flick(T[2]), tube); neon(L(2, SIGN_LETTERS.E2), S.s * .12, flick(T[2]), tube);
    neon(L(3, SIGN_LETTERS.N), S.s * .12, flick(T[2] + BEAT / 2), tube);
    const bw = S.total + S.s * .8, bh = S.s * 1.8, border = rrect(W / 2 - bw / 2, S.cy - bh / 2, bw, bh, S.s * .22, 8).concat([[W / 2 + bw / 2 - S.s * .22, S.cy - bh / 2]]);
    neon(border, S.s * .09, flick(T[3]), tube);
    const top = fitRow('KEEP IT', 560, { wdth: 100, space: .16 }), bot = fitRow('ALL NIGHT!', 900, { wdth: 72, space: .1 });
    slamWords(top, W / 2 - 280, S.cy - bh / 2 - 44, t, [T[0], T[1]], 'black', { from: 1.4 });
    const off = bot.cap * .05, by = S.cy + bh / 2 + 40 + bot.cap;
    slamWords(bot, W / 2 - 450 + off, by + off, t, [T[3], T[4]], { black: 1 }, { from: 1.4 });
    slamWords(bot, W / 2 - 450, by, t, [T[3], T[4]], null, { knock: true, from: 1.4 });
    restore();
    // night! lands, then on the next eighth: a paper flash, then the dawn yellow
    const f = t - (T[4] + BEAT / 2 - .02);
    if (f > 0 && f < .085) knock(P(rect(0, 0, W, H)), null);
    else if (f >= .085) paint(P(rect(0, 0, W, H)), { yellow: 1 });
    return { lyric: false };
  }

  // ---------------------------------------------------------------- 24 · KEEP IT OPEN ALL NIGHT (final chorus, key change)
  // Reads: out of the paper-white, dawn breaks (a yellow iris with rays); KEEP and IT strobe full-frame on their own
  // colours; OPEN lands and its letters are lit windows with the whole cast dancing inside; ALL NIGHT! below; stamp.
  const DANCERS = [['kid', 1.05], ['dad', .62], ['grandma', .7], ['baker', .64]];
  function dancePose(t, i) {
    const b = beatPos(t) + i * .5, ph = frac(b), side = Math.floor(b) % 2 ? 1 : -1;
    const up = E.out3(clamp(ph / .3)) * (1 - E.in2(clamp((ph - .55) / .45)));
    return { bob: -Math.abs(Math.sin(b * Math.PI)) * 14, lean: side * .08 * up, aN: [lerp(1.2, 2.9, up), .25], aF: [lerp(-1.1, -2.8, up * (i % 2 ? 1 : .6)), -.25],
      lN: [side * .2 * up, -.2 * up], lF: [-side * .15 * up, -.1], eyes: 'happy', mouth: .4 + .5 * up };
  }
  function s24_hook2(t, lt, dur) {
    const W22 = LINES[22].words, T = { keep: W22[0].t0, it: W22[1].t0, open: W22[2].t0, all: W22[3].t0, night: W22[4].t0, ad: W22[5].t0 };
    const beats = [0, 1, 2, 3, 4].map(i => beatT(Math.ceil(beatPos(73.5)) + i));
    const k = kick(t, [T.keep, T.it, T.open, T.all, T.night], 1.2) + kick(t, beats, .5, 11);
    const [sx, sy] = [noise1(t * 31) * 8 * k, noise1(t * 29 + 5) * 8 * k];
    if (t < T.keep - .05) {                                      // dawn out of the white: a yellow iris opening with rays
      const u = E.out3(seg(t, 71.72, T.keep - .05)), r = 60 + u * 1300;
      paint(P(circle(W / 2, H / 2, r, 96)), { yellow: 1 });
      for (let i = 0; i < 16; i++) { const a0 = i / 16 * TAU + t * .3, a1 = a0 + TAU / 32; paint(P([[W / 2, H / 2], [W / 2 + Math.cos(a0) * r, H / 2 + Math.sin(a0) * r], [W / 2 + Math.cos(a1) * r, H / 2 + Math.sin(a1) * r]]), { pink: 1 }); }
      return { lyric: false };
    }
    if (t < T.open - .05) {                                      // KEEP (yellow), IT (blue): full-frame strobe words
      const isKeep = t < T.it - .05, field = isKeep ? { yellow: 1 } : { blue: 1 };
      save(); cam(W / 2 + sx, H / 2 + sy, 1 + .03 * k);
      paint(P(rect(-100, -100, W + 200, H + 200)), field);
      const L = fitRow(isKeep ? 'KEEP' : 'IT', isKeep ? 1700 : 900, { wdth: isKeep ? 100 : 125 });
      const y = H / 2 + L.cap / 2;
      slamText(L, W / 2, y, t, isKeep ? T.keep : T.it, isKeep ? 'black' : null, { align: 'center', knock: !isKeep, from: 1.25 });
      restore();
      return { lyric: false };
    }
    save(); cam(W / 2 + sx, H / 2 + sy, 1 + .02 * k + .025 * E.out2(clamp((t - T.open) / 2)));
    paint(P(rect(-200, -200, W + 400, H + 400)), { pink: 1 });
    for (let i = 0; i < 18; i++) { const a0 = t * .12 + i / 18 * TAU, a1 = a0 + TAU / 18 * .45, rr = 1900; paint(P([[W / 2, H / 2], [W / 2 + Math.cos(a0) * rr, H / 2 + Math.sin(a0) * rr], [W / 2 + Math.cos(a1) * rr, H / 2 + Math.sin(a1) * rr]]), { yellow: 1 }); }
    const B = posterBlock([{ txt: 'KEEP IT', wdth: 100, space: .16 }, { txt: 'OPEN', wdth: 125 }, { txt: 'ALL NIGHT!', wdth: 72, space: .1 }], W / 2, H / 2 + 6, 1640, 900, .07);
    // KEEP IT settles in small from the strobe (no slam: it already landed)
    const sk = slamT(t, T.open, { from: 1.25 });
    save(); const px = W / 2, py = B[0].y - B[0].L.cap / 2; translate(px, py); scale(sk.sc); translate(-px, -py);
    drawText(B[0].L, B[0].x, B[0].y, null, { knock: true }); drawText(B[0].L, B[0].x, B[0].y, 'black'); restore();
    // OPEN: a giant yellow marquee; the whole cast dance in front of it as black cut-paper silhouettes
    const so = slamT(t, T.open, { from: 1.35 }), L = B[1].L;
    if (so.vis) {
      const cx = B[1].x + L.width / 2, cy = B[1].y - L.cap / 2;
      save(); translate(cx, cy); scale(so.sc); translate(-cx, -cy);
      const off2 = L.cap * .035;
      L.glyphs.forEach(g => { if (g.ch !== ' ') paint(glyphPath(g, B[1].x + g.x + off2, B[1].y + off2), { black: 1 }); });
      L.glyphs.forEach(g => { if (g.ch !== ' ') paint(glyphPath(g, B[1].x + g.x, B[1].y), { blue: 1 }); });
      let di = 0;
      L.glyphs.forEach(g => {
        if (g.ch === ' ') return;
        const [who] = DANCERS[di % 4], ci = di++;
        const pop = E.back(seg(t, T.open + .1 + ci * BEAT / 4, T.open + .32 + ci * BEAT / 4));
        if (pop <= 0) return;
        const hTarget = L.cap * .78, sc = hTarget / (CAST[who].legH[0] + CAST[who].legH[1] + CAST[who].torsoH + CAST[who].headR * 2.2);
        figure(CAST[who], B[1].x + g.x + g.w * .5, B[1].y + L.cap * .03 + (1 - pop) * L.cap * .5, sc, { ...dancePose(t, ci), face: ci % 2 ? -1 : 1, seed: ci * 11, ink: { yellow: 1 } });
      });
      restore();
    }
    const off = B[2].L.cap * .05;
    slamWords(B[2].L, B[2].x + off, B[2].y + off, t, [T.all, T.night], { black: 1 }, { from: 1.5, rot: .04 });
    slamWords(B[2].L, B[2].x, B[2].y, t, [T.all, T.night], null, { knock: true, from: 1.5, rot: .04 });
    restore();
    stampAt('ALL NIGHT!', 1350, 745, t, T.ad, { size: 84, ink: 'black', fill: { black: 1 }, knockText: true, rot: -.11, hold: .8 });
    return { lyric: false };
  }

  // ---------------------------------------------------------------- 27 · and the whole world's yours tonight (sunrise)
  // Reads: the S14 poster, mirrored and dawning: the globe right, the words left in paper on the morning blue;
  // the terminator sweeps across; each city pings at its sunrise; everything pings on "yours".
  function s27_world2(t, lt, dur) {
    const W25 = LINES[25].words, T = W25.map(w => w.t0);          // and the whole world's yours tonight
    const cx = 1330, cy = 540, R = 400 * (1 + .06 * wobble(t, T[5], 2.2, 5)) * (1 + .03 * pulse(t, 8));
    const lon0 = -30 + lt * 8, sun = lerp(lon0 - 125, lon0 + 40, E.io2(clamp(lt / 2.1)));
    paint(P(rect(0, 0, W, H)), { blue: 1 });
    for (let i = 0; i < 22; i++) { const a0 = lt * .1 + i / 22 * TAU, a1 = a0 + TAU / 22 * .45, rr = 2000; paint(P([[cx, cy], [cx + Math.cos(a0) * rr, cy + Math.sin(a0) * rr], [cx + Math.cos(a1) * rr, cy + Math.sin(a1) * rr]]), { yellow: 1 }); }
    knock(P(circle(cx, cy, R * 1.5)), ['blue', 'yellow'], radial(cx, cy, R * .98, R * 1.5, .9, 1.4));
    // each city pings as the sunrise reaches it (the day edge is at sun + 90)
    const pings = Object.entries(CITIES).map(([city, [la, lo]]) => {
      let d = ((lo - 90 - (lon0 - 125)) % 360 + 540) % 360 - 180;           // crude: time the edge passes this longitude
      const tt = 81.36 + clamp(d / 165, 0, 1) * 2.1 * .75;
      return { city, t0: tt };
    });
    globe(cx, cy, R, { lon0, lat0: 20, t, sun, lights: 1, pings, pingAll: T[4], arcs: WORLD_ARCS(T[3] - .2), arcW: 2, day: { yellow: 1 }, landDay: { pink: 1 } });
    // the words: left, knocked out of the morning blue
    const rows = [[0, 1], [2, 3], [4], [5]], x0 = 120, w = 740;
    const Ls = rows.map(r => fitRow(r.map(i => W25[i].w.toUpperCase().replace(',', '')).join(' '), w, { wdth: 62, space: .1 }));
    const gap = 22, Htot = Ls.reduce((a, L) => a + L.cap, 0) + gap * 3;
    let y = H / 2 - Htot / 2;
    Ls.forEach((L, ri) => {
      y += L.cap; const off = Math.max(5, L.cap * .05), tt = rows[ri].map(i => T[i]), o = { from: 1.45, rot: ri % 2 ? .04 : -.04 };
      slamWords(L, x0 + off, y + off, t, tt, { black: 1 }, o);
      slamWords(L, x0, y, t, tt, null, { ...o, knock: true });
      y += gap;
    });
    return { lyric: false };
  }

  SHOT_FN['11'] = s11_hook; SHOT_FN['14'] = s14_world; SHOT_FN['15'] = s15_sign; SHOT_FN['24'] = s24_hook2; SHOT_FN['27'] = s27_world2;

  // test board: node engine/render.mjs projects/open-all-night --loop=globeTest --sheet=0.5,1.5
  LOOPS.globeTest = t => {
    paint(P(rect(0, 0, W, H)), { pink: 1 });
    globe(480, 540, 400, { lon0: -30 + t * 20, t, lights: clamp(t), arcs: [{ a: 'nyc', b: 'rome', t0: .2, dur: .8, keep: true }, { a: 'nyc', b: 'tok', t0: .4, dur: .8 }] });
    globe(1440, 540, 400, { lon0: 60, t, sun: 60 + 70 - t * 40, lights: 1, pingAll: .3 });
  };
  LOOPS.globeTest.len = 2;
})();
