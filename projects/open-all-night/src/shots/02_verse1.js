// 03–06 · VERSE 1: the kid, the stars, grandma in Rome, the sink.
(() => {
  // ---------------------------------------------------------------- 03 · Two a.m. and a kid can't sleep
  // Reads: (1) a dark bedroom, light leaking from under a blanket; (2) the blanket slides down: a kid, wide awake,
  // face lit by a tablet; (3) she glances at the clock (2:00) and back; (4) the tablet light blooms up.
  function s03_kid(t, lt, dur) {
    const z = 1.0 + .06 * E.io2(lt / dur);
    save(); cam(930, 560, z);
    flood('blue', 1);
    // window, upper right: the building across the street, the moon
    const wx = 1230, wy = 80, ww = 540, wh = 440;
    for (const k of RISO.inks) { k.ctx.save(); k.ctx.clip(P(rect(wx, wy, ww, wh))); }
    const mdisk = P(cut(circle(wx + 420, wy + 110, 48, 40), 32)); knock(mdisk, ['blue']); ink(mdisk, { yellow: .2 });
    paint(P(cut(rect(wx + 40, wy + 190, 290, 400), 33)), 'black');
    for (let i = 0; i < 6; i++) { const x = wx + 72 + (i % 3) * 82, y = wy + 225 + Math.floor(i / 3) * 105; knock(P(rect(x, y, 40, 58)), ['black']); if (hash(i * 5 + 1) > .45) paint(P(rect(x, y, 40, 58)), { yellow: 1 }); }
    for (const k of RISO.inks) k.ctx.restore();
    paint(P(cut(rect(wx - 20, wy - 20, ww + 40, wh + 40), 34)), 'black', { stroke: 26 });
    paint(P(rect(wx + ww / 2 - 8, wy, 16, wh)), 'black'); paint(P(rect(wx, wy + wh * .45, ww, 14)), 'black');
    // the clock: paper face, black hands at 2:00, a pink second hand that ticks on the beat
    const ck = [250, 240], cr = 118;
    knock(P(cut(circle(ck[0], ck[1], cr, 48), 35, .8)), null);
    paint(P(cut(circle(ck[0], ck[1], cr, 48), 35, .8)), 'black', { stroke: 16 });
    for (let i = 0; i < 12; i++) { const a = i / 12 * TAU; ink(P([[ck[0] + Math.sin(a) * cr * .76, ck[1] - Math.cos(a) * cr * .76], [ck[0] + Math.sin(a) * cr * .88, ck[1] - Math.cos(a) * cr * .88]], false), 'black', { stroke: i % 3 ? 4 : 9 }); }
    const hand = (a, l, w, spec) => paint(P([[ck[0] - Math.sin(a) * 14, ck[1] + Math.cos(a) * 14], [ck[0] + Math.sin(a) * l, ck[1] - Math.cos(a) * l]], false), spec, { stroke: w });
    hand(2 / 12 * TAU, cr * .5, 14, 'black'); hand(0, cr * .74, 9, 'black');
    const bt = beatPos(t), tick = Math.floor(bt) + E.back(clamp(frac(bt) / .12));
    hand(tick / 60 * TAU + 1.1, cr * .82, 4.5, 'pink');
    paint(P(circle(ck[0], ck[1], 10)), 'pink');
    // floor + bed
    paint(P(cut(rect(-100, 950, W + 200, 300), 36)), 'black');
    paint(P(cut(blob([[400, 1100], [400, 540], [430, 470], [520, 470], [550, 540], [550, 1100]], 4), 37)), 'black');   // headboard
    paint(P(cut(rect(520, 790, 1500, 170), 38)), 'black');                                                             // mattress side
    // pillow (paper, with a yellow halftone where the tablet lights it)
    const pil = cut(blob([[540, 800], [530, 700], [610, 640], [860, 630], [900, 700], [880, 800]], 5), 40, 1.2);
    knock(P(pil), null);
    // the kid: the blanket slides down on "and a kid" (9.34): she is wide awake, lit from below by the tablet
    const reveal = E.back(seg(t, 9.30, 9.75));
    const hx = 720, hy = 700;
    const look = t < 10.1 ? [0, 0] : t < 10.95 ? [-1, -.6] : [0, 0];
    const turn = kf(t, [[10.05, 0], [10.2, -.4, 'out3'], [10.9, -.4], [11.05, 0, 'out3']]);
    head(CAST.kid, hx, hy, 2.3, { head: -Math.PI / 2 + .3 + turn, eyes: t < 9.42 ? 'closed' : 'wide', look, light: reveal > .5 ? 1 : 0, blush: 0, smile: t > 11.05 ? 1 : 0 });
    // blanket: a pink mountain with quilting stitches; its top edge slides down past her face
    const edge = lerp(hx - 150, hx + 115, reveal), breath = Math.sin(lt * 2.4) * 8;
    const bl = [[edge, 800], [edge - 20, 690 - breath], [edge + 70, 610 - breath], [1150, 600 - breath], [1420, 540], [1590, 600], [2000, 640], [2000, 820], [edge, 830]];
    const blP = P(cut(blob(bl, 5), 41, 1.6, .8));
    paint(blP, { pink: 1 });
    for (let i = 0; i < 6; i++) knock(P([[edge + 200 + i * 190, 600 + Math.sin(i * 1.7) * 20], [edge + 170 + i * 190, 820]], false), ['pink'], 1, { stroke: 4, dash: [12, 14] });
    // the tablet over her face; its light is paper, its halo halftone yellow
    const tp = [hx + 230, hy - 250], glow = .72 + .12 * Math.sin(lt * 11) * Math.sin(lt * 3.7) + reveal * .15;
    const R0 = 560;
    knock(P(circle(tp[0], tp[1] + 80, R0)), ['blue'], radial(tp[0], tp[1] + 80, 40, R0, .75 * glow, 1.3));
    ink(P(circle(tp[0], tp[1] + 80, R0)), { yellow: radial(tp[0], tp[1] + 80, 30, R0 * .75, .5 * glow, 1.3) });
    if (reveal < .5) knock(blP, ['pink'], radial(hx + 40, hy + 30, 10, 320, .55 * glow, 1.5));      // light leaking through the blanket
    // her arm from under the blanket, holding it up
    paint(P(ribbon([[hx + 200, 690], [hx + 250, hy - 130], [tp[0] + 10, tp[1] + 60]], 34, 26, 42)), { pink: 1 });
    save(); translate(tp[0], tp[1]); rotate(.22);
    paint(P(rrect(-150, -105, 300, 210, 18)), 'black');
    knock(P(rrect(-134, -89, 268, 178, 8)), null);
    restore();
    paint(P(cut(circle(tp[0] + 22, tp[1] + 72, 22, 14), 43)), { pink: 1 });          // thumb over the edge
    const sc = toScreen(tp[0], tp[1]);
    restore();
    // out: the tablet's light swells to fill the frame (a paper iris with a halftone fringe) -> the ceiling of stars
    const bl2 = E.in3(seg(t, 11.12, 11.72));
    if (bl2 > 0) { const r = 60 + bl2 * 2300; knock(P(circle(sc[0], sc[1], r + 260)), null, radial(sc[0], sc[1], r, r + 260, 1, .7)); knock(P(circle(sc[0], sc[1], r, 64)), null); }
    return { lyric: { slot: 'll', ink: 'knock', accentInk: 'yellow', y: 1030, size: 64 } };
  }


  // ---------------------------------------------------------------- 04 · she's learning all the stars for free
  // Reads: (1) the tablet's white light contracts, revealing a ceiling of stars; (2) the kid points, and the Big Dipper
  // draws itself star to star on the eighths; (3) the dipper flares on "stars"; (4) its pointer stars shoot a line to
  // Polaris, which blazes on "free"; (5) Polaris rings like a call and swells pink to fill the frame (Grandma calling).
  const DIPPER = [[640, 330], [790, 352], [930, 410], [1060, 482], [1090, 628], [1300, 650], [1320, 500]];
  const DSEG = [[0, 1], [1, 2], [2, 3], [3, 4], [4, 5], [5, 6], [6, 3]];
  const POLARIS = [1372, 150];
  const e8 = k => beatT(24 + k * .5);            // eighth notes from beat 24 (12.20 s)
  function star4(x, y, r, k = .28) { return starPts(x, y, r, r * k, 4); }
  function s04_stars(t, lt, dur) {
    const z = 1.0 + .05 * E.io2(lt / dur), drift = lt * 10;
    save(); cam(W / 2 + drift * .5, H / 2 - drift * .3, z);
    flood('blue', 1);
    // field stars: paper knockouts, a few in yellow; stable per id, a few twinkle per drawing
    const R = rng(404);
    for (let i = 0; i < 140; i++) {
      const x = R() * 2100 - 90, y = R() * 1000 - 60, r = 1.6 + R() ** 3 * 5.5, yel = R() > .8;
      if (hash(i * 7.7 + BF(t) * .31) > .93) continue;
      const pts = r > 4.5 ? star4(x, y, r * 1.8) : circle(x, y, r, 8);
      knock(P(pts), ['blue']); if (yel) ink(P(pts), { yellow: 1 });
    }
    // a ringed planet drifting upper right
    const pl = [1700 - lt * 14, 300 + Math.sin(lt * .9) * 6];
    const ring = (front) => { const pts = arcPts(0, 0, 1, front ? 0 : Math.PI, front ? Math.PI : TAU, 30).map(([a, b]) => [pl[0] + a * 150 * Math.cos(-.35) - b * 34 * Math.sin(-.35), pl[1] + a * 150 * Math.sin(-.35) + b * 34 * Math.cos(-.35)]); paint(P(pts, false), 'pink', { stroke: 12 }); };
    ring(false);
    paint(P(cut(circle(pl[0], pl[1], 78, 48), 44, 1.2)), { yellow: 1 });
    ink(P(circle(pl[0], pl[1], 78, 48)), { pink: linear(pl[0] - 78, pl[1] - 60, pl[0] + 78, pl[1] + 60, 0, .75) });
    knock(P([[pl[0] - 70, pl[1] - 20], [pl[0] + 72, pl[1] - 32]], false), ['yellow'], 1, { stroke: 5 });
    ring(true);
    // the dipper, drawn segment by segment on eighths; the pen head is a spark her finger aims at
    let pen = DIPPER[0];
    DSEG.forEach(([a, b], k) => {
      const u = E.out3(seg(t, e8(k), e8(k) + .22));
      if (u <= 0) return;
      const pa = DIPPER[a], pb = DIPPER[b], pe = [lerp(pa[0], pb[0], u), lerp(pa[1], pb[1], u)];
      paint(P([pa, pe], false), 'yellow', { stroke: 5 });
      if (u < 1) pen = pe; else if (k === DSEG.length - 1) pen = null;
    });
    const flare = pulse(t, 5, 100, beatPos(13.62)) * (t >= 13.62 ? 1 : 0);        // the dipper flares on "stars"
    DIPPER.forEach((p, i) => {
      const lit = t >= (i === 0 ? e8(0) : e8(DSEG.findIndex(([a, b]) => b === i))) ;
      const pop = lit ? 1 + .9 * (1 - E.out3(seg(t, i === 0 ? e8(0) : e8(DSEG.findIndex(([a, b]) => b === i)) + .2, (i === 0 ? e8(0) : e8(DSEG.findIndex(([a, b]) => b === i))) + .45))) : .55;
      const r = (lit ? 17 : 8) * pop * (1 + .6 * flare);
      if (lit) knock(P(circle(p[0], p[1], r * 3.5)), ['blue'], radial(p[0], p[1], r * .5, r * 3.5, .7, 1.6));
      knock(P(star4(p[0], p[1], r)), null); if (lit) ink(P(circle(p[0], p[1], r * .3, 10)), { yellow: 1 });
    });
    if (pen) { knock(P(star4(pen[0], pen[1], 26)), null); ink(P(circle(pen[0], pen[1], 9, 10)), { yellow: 1 }); }
    // the pointer stars shoot a dotted line to Polaris, which blazes on "free" (14.34)
    const pu = E.out3(seg(t, 14.05, 14.36));
    if (pu > 0) {
      const a = DIPPER[5], b = POLARIS, n = 12;
      for (let i = 0; i < n * pu; i++) { const q = [lerp(a[0], b[0], (i + .5) / n * 1.0), lerp(a[1], b[1], (i + .5) / n)]; paint(P(circle(q[0], q[1], 5, 8)), 'yellow'); }
    }
    const pz = t >= 14.34 ? E.back2(seg(t, 14.34, 14.62)) : .3;
    const ring2 = seg(t, 15.02, 15.59);
    const pr = 26 * pz + 10 * pulse(t, 4) * (t > 14.6 ? 1 : 0);
    const halo = t >= 14.34 ? 1 : .2;
    knock(P(circle(POLARIS[0], POLARIS[1], pr * 7)), ['blue'], radial(POLARIS[0], POLARIS[1], pr * .6, pr * 7, .85 * halo, 1.5));
    ink(P(circle(POLARIS[0], POLARIS[1], pr * 5)), { yellow: radial(POLARIS[0], POLARIS[1], pr * .3, pr * 5, .7 * halo, 1.4) });
    for (let i = 0; i < 8 && t >= 14.34; i++) {                        // rays
      const ang = i / 8 * TAU + lt * .3, L = pr * (i % 2 ? 2.4 : 4.2) * pz;
      paint(P([[POLARIS[0] + Math.cos(ang) * pr * 1.1, POLARIS[1] + Math.sin(ang) * pr * 1.1], [POLARIS[0] + Math.cos(ang) * L, POLARIS[1] + Math.sin(ang) * L]], false), 'yellow', { stroke: i % 2 ? 4 : 6 });
    }
    knock(P(star4(POLARIS[0], POLARIS[1], pr * 1.5, .22)), null);
    const psc = toScreen(POLARIS[0], POLARIS[1]);
    // the kid, foreground lower left: head tipped back, pointing; the tablet glowing in her lap
    const aim = pen || (t < 14.3 ? DIPPER[3] : POLARIS);
    const kx = 330, ky = 905;
    const sh = [kx + 150, ky + 170];
    const ang = Math.atan2(aim[1] - sh[1], aim[0] - sh[0]) + Math.sin(lt * 7) * .015;
    const reach = 330, el = [sh[0] + Math.cos(ang - .25) * reach * .52, sh[1] + Math.sin(ang - .25) * reach * .52];
    const hd = [sh[0] + Math.cos(ang) * reach, sh[1] + Math.sin(ang) * reach];
    paint(P(cut(blob([[kx - 260, 1200], [kx - 220, ky + 90], [kx - 60, ky + 60], [kx + 170, ky + 110], [kx + 260, 1200]], 5), 45, 1.4)), { pink: 1 });
    head(CAST.kid, kx, ky, 3.2, { head: -.75, eyes: t > 14.34 ? 'wide' : 'dot', look: [.6, -1], blush: 0, mouth: t > 14.34 && t < 15.0 ? .7 : 0 });
    paint(P(ribbon([sh, el, hd], 46, 34, 46)), { pink: 1 });
    paint(P(cut(circle(hd[0], hd[1], 26, 16), 47, .6)), { pink: 1 });
    paint(P(ribbon([hd, [hd[0] + Math.cos(ang) * 58, hd[1] + Math.sin(ang) * 58]], 17, 13, 48)), { pink: 1 });   // the pointing finger
    restore();
    // in: the white light from the tablet contracts into it (paper iris with a halftone fringe)
    const inU = E.out3(seg(t, 11.72, 12.28));
    if (inU < 1) { const r = lerp(2300, 0, inU), c = [470, 1060]; knock(P(circle(c[0], c[1], r + 240)), null, radial(c[0], c[1], r, r + 240, 1, .7)); knock(P(circle(c[0], c[1], r, 64)), null); }
    // out: Polaris rings like an incoming call, then swells pink to fill the frame (Rome is calling)
    if (ring2 > 0) {
      const wob = Math.sin(ring2 * 44) * .22 * (1 - ring2);
      const grow = E.inExpo(seg(t, 15.2, 15.59)), r = 105 + grow * 2400;
      save(); translate(psc[0], psc[1]); rotate(wob);
      paint(P(cut(circle(0, 0, r, 64), 49, 1)), { pink: 1 });
      if (grow < .3) { const k = (1 - grow / .3) * E.back(seg(t, 15.02, 15.2)); rotate(-wob); head(CAST.grandma, -8, 14, 1.75 * k, { eyes: 'happy', mouth: .6, face: -1 }); }
      restore();
      for (let i = 0; i < 3 && grow < .2; i++) { const a = ring2 * 3 - i * .33; if (a > 0 && a < 1) ink(P(arcPts(psc[0], psc[1], 80 + a * 90, -.9, .9, 12), false), { pink: 1 - a > .4 ? 1 : 0 }, { stroke: 6 }); }
    }
    return { lyric: t < 12.26 ? false : { slot: 'ul', ink: 'knock', accentInk: 'knock', y: 175, size: 64 } };
  }

  // ---------------------------------------------------------------- 05 · Grandma's laughing on a call from Rome
  // Reads: (1) the pink call opens into a split screen: Rome in the morning (pink), 2 a.m. here (blue); (2) Grandma
  // waves; (3) both laugh, on alternating beats; (4) a dotted flight line hops from the Colosseum to the kid's window
  // on "call from Rome"; (5) the night panel swallows the frame -> the kitchen.
  function clipTo(pts) { const p = P(pts); for (const k of RISO.inks) { k.ctx.save(); k.ctx.clip(p); } }
  function unclip() { for (const k of RISO.inks) k.ctx.restore(); }
  const laughK = (t, t0, phase, decay = 7) => (t < t0 ? 0 : pulse(t, decay, 1, phase) * (.55 + .45 * Math.exp(-(t - t0) * .5)));
  function colosseum(x, y, w, h, spec) {
    paint(P(cut([[x, y + h], [x, y + h * .2], [x + w * .12, y], [x + w * .78, y - h * .05], [x + w, y + h * .35], [x + w, y + h]], 61, 1.2)), spec);
    for (let r = 0; r < 3; r++) for (let c = 0; c < 7; c++) {
      const ax = x + w * (.07 + c * .128), ay = y + h * (.2 + r * .27), aw = w * .07, ah = h * .17;
      if (r === 0 && c > 5) continue;
      knock(P(rrect(ax, ay, aw, ah, aw * .48, 5)), Object.keys(spec));
    }
  }
  function s05_call(t, lt, dur) {
    const inU = E.back(seg(t, 15.59, 15.95)), outU = E.inExpo(seg(t, 19.08, 19.46));
    const seam = lerp(W + 20, 960, inU) - outU * 1010;
    const lp = lt;                                       // push-in drift, opposite per panel (parallax)
    // ---- left panel: Rome, morning (pink)
    clipTo(rect(-10, -10, seam + 10, H + 20));
    save(); translate(seam - 960, 0);
    flood('pink', 1);
    const sun = P(cut(circle(210 - lp * 4, 190, 88, 48), 62, 1)); knock(P(circle(210 - lp * 4, 190, 260)), ['pink'], radial(210 - lp * 4, 190, 88, 260, .55, 1.6)); knock(sun, null); ink(sun, { yellow: .45 });
    colosseum(40 - lp * 8, 690, 420, 250, { black: 1 });
    // grandma: waves on "Grandma's", laughs from "laughing" on the beats, hand to her chest
    const gl = laughK(t, 16.45, 0);
    const wave = t < 16.45 ? Math.sin((t - 15.7) * TAU * 2.07) : 0;
    const gHead = -.08 - gl * .42, gBob = -gl * 16;
    figure(CAST.grandma, 540, 1150, 2.75, {
      head: gHead, bob: gBob / 2.75, lean: -gl * .06, eyes: t < 16.45 ? 'dot' : 'happy', mouth: t < 16.45 ? (t > 15.95 ? .35 : 0) : .4 + gl * .6,
      aN: t < 16.45 ? [2.5, -.9 + wave * .35] : [1.2 - gl * .2, -1.9], aF: [.9, -1.6] });
    restore(); unclip();
    // ---- right panel: 2 a.m. (blue), the kid in bed-light, tablet held up
    clipTo(rect(seam, -10, W - seam + 10, H + 20));
    save(); translate(Math.max(0, seam - 960) * 0, 0);
    flood('blue', 1);
    const wx = 1440 + lp * 5, wy = 70;
    const mdisk = P(cut(circle(wx + 250, wy + 120, 52, 40), 63)); knock(mdisk, ['blue']); ink(mdisk, { yellow: .2 });
    paint(P(cut(rect(wx - 20, wy - 20, 460, 420), 64)), 'black', { stroke: 22 });
    paint(P(rect(wx + 200, wy, 16, 380)), 'black'); paint(P(rect(wx, wy + 170, 420, 14)), 'black');
    const kl = laughK(t, 16.7, .5, 8);
    const tabP = [1180, 640];
    knock(P(circle(tabP[0], tabP[1], 420)), ['blue'], radial(tabP[0], tabP[1], 40, 420, .6, 1.4));
    figure(CAST.kid, 1450, 1215, 3.3, {
      face: -1, head: -.05 - kl * .3, bob: -kl * 12 / 3.3, eyes: t < 16.7 ? 'dot' : 'happy', mouth: t < 16.7 ? 0 : .3 + kl * .7,
      aN: [1.55, -.9], aF: [1.3, -1.0],
      hold: p => { save(); translate(p[0] + 4, p[1] - 18); rotate(.12); paint(P(rrect(-12, -46, 24, 92, 5)), 'black'); restore(); } });
    restore(); unclip();
    // seam: a black cut between the two worlds
    paint(P(cut(rect(seam - 8, -20, 16, H + 40), 65, .8)), 'black');
    // laugh ticks by each mouth on their beats
    const ticks = (cx, cy, k, dir, key) => { if (k < .25) return; for (let i = 0; i < 3; i++) { const a = (-.6 + i * .6) + (dir < 0 ? Math.PI : 0), r0 = 40, r1 = 40 + 50 * k; paint(P([[cx + Math.cos(a) * r0 * dir * dir, cy + Math.sin(a) * r0], [cx + Math.cos(a) * r1, cy + Math.sin(a) * r1]], false), 'black', { stroke: 7 }); } };
    ticks(seam - 960 + 820, 330 + -gl * 30, gl, 1, 1);
    if (seam > 1000 || outU === 0) ticks(1130 + (seam - 960) * 0, 400 - kl * 20, kl, -1, 2);
    // the flight line: dotted, from the Colosseum over the seam to her window, on "call from Rome"
    const fu = seg(t, 17.35, 18.5);
    if (fu > 0 && outU < .3) {
      const a = [260 + (seam - 960), 640], b = [wx + 150, wy + 330], n = 26;
      const pt = u => { const q = arcPt(a, b, 420, u); return q; };
      for (let i = 0; i < n * E.io2(fu); i++) { const q = pt(i / n); paint(P(circle(q[0], q[1], 7, 10)), 'yellow'); }
      const hu = E.io2(fu), q = pt(hu), q2 = pt(Math.min(1, hu + .02)), ang = Math.atan2(q2[1] - q[1], q2[0] - q[0]);
      if (fu < 1) { save(); translate(q[0], q[1]); rotate(ang); paint(P([[30, 0], [-22, -18], [-10, 0], [-22, 18]]), 'yellow'); restore(); }
      else { const pop = 1 - E.out3(seg(t, 18.5, 18.8)); if (pop > 0) knock(P(starPts(b[0], b[1], 40 * pop + 10, 10, 4)), null); }
    }
    // the call bar: black strip with the lyric knocked out, two little buttons
    paint(P(rect(-10, 950, W + 20, 140)), 'black');
    for (const [x, c] of [[1720, 'knock'], [1805, 'pink']]) { if (c === 'knock') knock(P(circle(x, 1015, 26)), null); else paint(P(circle(x, 1015, 26)), 'pink'); }
    return { lyric: { slot: 'lc', ink: 'knock', accentInk: 'knock', y: 1036, size: 60, maxW: 1300 } };
  }

  SHOT_FN['03'] = s03_kid;
  SHOT_FN['05'] = s05_call;
  SHOT_FN['04'] = s04_stars;
})();
