// 16–19 · VERSE 2: the bakery at dawn, the paper plane, the history triptych, the patron.
(() => {
  // ---------------------------------------------------------------- private helpers
  const clipIn = path => { for (const k of RISO.inks) { k.ctx.save(); k.ctx.clip(path); } };
  const clipOut = () => { for (const k of RISO.inks) k.ctx.restore(); };
  // verse 2 sets its words on the paper sidewalk band at the foot of the frame (every camera keeps that band at y ≈ 965–1035)
  const V2LYRIC = { slot: 'll', ink: 'black', accentInk: 'pink', size: 56, maxW: 1680, y: 1020 };
  const bandCY = z => 1000 - 425 / z;       // camera centre y that puts world y 1000 (sidewalk top) at screen y 965
  // don't carry the chorus's last line into the verse
  const lyr = (t, o = V2LYRIC) => { const st = lyricState(t); return st && st.L.t0 < 46.5 ? false : o; };

  // one gorgeous loaf: yellow, a halftone crust (pink over yellow prints vermilion), paper scores
  function loaf(x, y, s = 1, r = 0, seed = 0) {
    save(); translate(x, y); rotate(r); scale(s);
    const body = cut(blob([[-80, 6], [-70, -22], [-30, -36], [30, -36], [72, -24], [84, 4], [60, 26], [-60, 26]], 5), 500 + seed, 1, .5);
    paint(P(body), { yellow: 1 });
    ink(P(body), { pink: c => { const g = c.createLinearGradient(0, -36, 0, 30); g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(.45, 'rgba(0,0,0,.08)'); g.addColorStop(1, 'rgba(0,0,0,.62)'); return g; } });
    for (let i = -1; i <= 1; i++) knock(P([[i * 36 - 14, -26], [i * 36 + 14, -4]], false), ['yellow', 'pink'], 1, { stroke: 7 });
    restore();
  }
  // steam: paper curls rising and swaying
  function steam(x, y, t, t0, n = 3, h = 200, seed = 0) {
    for (let i = 0; i < n; i++) {
      const age = t - t0 - i * .12; if (age < 0) continue;
      const u = clamp(age / 1.4); if (u >= 1) continue;
      const pts = [];
      for (let k = 0; k <= 10; k++) { const v = k / 10; pts.push([x + (i - 1) * 34 + Math.sin(v * 5 + age * 4 + i) * 22 * v, y - v * h * (.3 + u)]); }
      knock(P(ribbon(pts, 3, 14 * (1 - u), seed + i)), null);
    }
  }
  function sun(x, y, r) {
    ink(P(circle(x, y, r * 2.8, 48)), { pink: radial(x, y, r, r * 2.8, .55, 1.6) });
    knock(P(cut(circle(x, y, r, 48), 510, 1)), null);
  }
  // a black cat strolling the empty sidewalk (the street is empty; the cat is the proof)
  function cat(x, y, s, ph, dir = -1) {
    save(); translate(x, y); scale(s * dir, s);
    const b = Math.abs(Math.sin(ph * TAU)) * 3;
    paint(P(cut(ellipse(0, -38 - b, 44, 17), 520, .8)), 'black');
    paint(P(cut(circle(44, -58 - b, 15, 18), 521, .6)), 'black');
    paint(P([[34, -68 - b], [38, -84 - b], [46, -70 - b]]), 'black'); paint(P([[48, -70 - b], [56, -83 - b], [58, -66 - b]]), 'black');
    paint(P(ribbon([[-40, -44 - b], [-60, -64], [-58, -92 + Math.sin(ph * TAU * 2) * 6], [-48, -104]], 7, 4, 522)), 'black');
    for (let i = 0; i < 4; i++) { const lx = [-28, -14, 18, 30][i], a = Math.sin(ph * TAU + (i % 2 ? Math.PI : 0) + (i > 1 ? .8 : 0)) * .45; paint(P(ribbon([[lx, -30 - b], [lx + Math.sin(a) * 26, -2]], 7, 6, 523 + i)), 'black'); }
    knock(P(circle(50, -61 - b, 3.2, 8)), ['black']);
    restore();
  }
  // the photo card (a little ad: pink border, the loaf) morphing into a paper plane. u = fold 0..1. Local: nose +x.
  function planeOrCard(x, y, s, ang, u) {
    save(); translate(x, y); rotate(ang); scale(s);
    const card = [[-62, -46], [62, -46], [62, 46], [-62, 46]];
    const plane = [[-58, -30], [64, 0], [-58, 16], [-40, -2]];
    const e = E.io3(u), pts = card.map((p, i) => [lerp(p[0], plane[i][0], e), lerp(p[1], plane[i][1], e)]);
    knock(P(pts), null); ink(P(pts), 'black', { stroke: 3.5 });
    if (e < .5) {            // the photo: a pink frame and the loaf
      const k = 1 - e * 2;
      ink(P(rect(-50 * k, -36 * k, 100 * k, 72 * k)), 'pink', { stroke: 5 * k });
      if (k > .2) paint(P(ellipse(0, 4 * k, 34 * k, 12 * k, -.1)), { yellow: 1 });
    } else {                 // the plane: a crease, a wing edge, a pink stripe (the ad)
      const k = (e - .5) * 2;
      ink(P([[-58, -30], [64, 0], [-40, -2]], false), 'black', { stroke: 3 });
      ink(P([[-40, -2], [64, 0]], false), 'black', { stroke: 2.5 * k });
      paint(P([[-44, -20 * k], [10, -9 * k], [8, -4 * k], [-42, -12 * k]]), { pink: 1 });
    }
    restore();
  }
  // dashed flight trail behind a path fn(u)
  function trail(fn, u, span = .35, spec = 'black') {
    const pts = []; for (let k = 0; k <= 30; k++) { const v = u - span * (1 - k / 30); if (v > 0) pts.push(fn(v)); }
    if (pts.length > 1) ink(P(pts, false), spec, { stroke: 4, dash: [14, 14] });
  }

  // ---------------------------------------------------------------- the dawn street set (world coords)
  // our building's storefront at a larger scale: facade x 960..2800, awning 455..545, window 1030..1730 x 575..935,
  // door 1790..1960, sidewalk 1000..1060, street below. Distant skyline to the left, pink, under a yellow dawn.
  const WIN = [1030, 575, 700, 360], DOOR = [1790, 560, 170, 440];
  function dawnSet(t, o = {}) {
    flood('yellow', 1);
    sun(o.sunX ?? 420, o.sunY ?? 700, 105);
    // distant skyline (pink)
    const sk = [[-900, 560], [-620, 470], [-380, 600], [-160, 520], [80, 640], [300, 560], [560, 610], [760, 500]];
    sk.forEach(([x, top], i) => {
      const w = 200 + hash(i * 3.3) * 60;
      paint(P(cut(rect(x, top, w, 1100 - top), 530 + i, 1.2)), { pink: 1 });
      for (let k = 0; k < 6; k++) if (hash(i * 11 + k) > .55) knock(P(rect(x + 30 + (k % 2) * 90, top + 50 + Math.floor(k / 2) * 110, 40, 60)), ['pink']);
    });
    // our building (blue), upper windows catching the dawn
    paint(P(cut(rect(960, -600, 1900, 1660), 540, 1.4)), { blue: 1 });
    for (let r = 0; r < 3; r++) for (let c = 0; c < 9; c++) {
      const x = 1030 + c * 200, y = -300 + r * 240, lit = hash(r * 17 + c * 3) > .45;
      const wp = P(cut(rect(x, y, 96, 150), 560 + r * 9 + c, .8));
      knock(wp, ['blue']); if (!lit) ink(wp, { yellow: 1 });
      ink(P(rect(x + 44, y, 8, 150)), 'blue');
    }
    paint(P(rect(940, 425, 1940, 32)), 'black');
    // awning: pink and paper stripes, scalloped hem, a black shadow
    const ax = 990, aw = 1000, n = 14;
    for (let i = 0; i < n; i++) {
      const x0 = ax + i * aw / n, x1 = ax + (i + 1) * aw / n;
      const sh = P(cut([[x0, 457], [x1, 457], [x1, 530], [(x0 + x1) / 2, 548], [x0, 530]], 570 + i, .6, .3));
      if (i % 2) paint(sh, { pink: 1 }); else knock(sh, null);
    }
    ink(P([[ax, 457], [ax + aw, 457]], false), 'black', { stroke: 6 });
    // shop window: the interior, clipped
    const wp = P(cut(rect(...WIN), 580, .8));
    knock(wp, null);
    clipIn(wp);
    paint(P(rect(WIN[0] - 10, WIN[1] - 10, WIN[2] + 20, WIN[3] + 20)), { pink: 1 });
    // shelves of bread, back right
    for (const sy of [650, 745]) { paint(P(rect(1480, sy, 260, 9)), 'black'); for (let k = 0; k < 3; k++) loaf(1520 + k * 80, sy - 14, .42, 0, sy + k); }
    // the oven: a black arch, fire in its mouth
    paint(P(cut(blob([[1045, 950], [1045, 700], [1080, 630], [1170, 605], [1260, 630], [1300, 700], [1300, 950]], 5), 590, 1)), 'black');
    const mouth = P(cut(blob([[1095, 880], [1095, 780], [1135, 735], [1210, 735], [1250, 780], [1250, 880]], 4), 591, .8));
    knock(mouth, ['black']); paint(mouth, { yellow: 1 });
    clipIn(mouth);
    for (let k = 0; k < 7; k++) { const fx = 1100 + k * 24, fh = 40 + 30 * Math.abs(noise1(t * 6 + k * 3)); paint(P([[fx - 16, 885], [fx + 4 + jit(k, 4), 885 - fh], [fx + 18, 885]]), { pink: 1 }); }
    clipOut();
    if (o.interior) o.interior();
    clipOut();
    // glass glints
    knock(P([[1060, 700], [1160, 600]], false), ['pink'], 1, { stroke: 12 }); knock(P([[1090, 720], [1190, 620]], false), ['pink'], 1, { stroke: 4 });
    // window frame + sill
    paint(P(cut(rect(...WIN), 581, .8)), 'black', { stroke: 18 });
    paint(P(rect(1005, 935, 750, 30)), 'black');
    // door
    const dp = P(cut(rect(...DOOR), 600, .8));
    if (o.doorOpen) {
      knock(dp, null); paint(dp, { yellow: 1 });
      ink(P([[DOOR[0], 1000], [DOOR[0] + DOOR[2], 1000], [DOOR[0] + DOOR[2] + 160, 1090], [DOOR[0] - 160, 1090]]), { yellow: .5 });
      paint(P(cut([[DOOR[0], DOOR[1]], [DOOR[0] - 70, DOOR[1] + 30], [DOOR[0] - 70, 1000 + 18], [DOOR[0], 1000]], 601)), 'black');
    } else {
      paint(dp, 'black');
      const dg = P(rect(DOOR[0] + 20, DOOR[1] + 26, DOOR[2] - 40, 190));
      knock(dg, ['black']); paint(dg, { pink: 1 });
      // the OPEN sign, still on at dawn, hung in the door glass
      paint(P(rrect(DOOR[0] + 26, DOOR[1] + 92, DOOR[2] - 52, 64, 6)), 'black');
      openSign(DOOR[0] + DOOR[2] / 2, DOOR[1] + 124, 26, [1, 1, 1, 1], { darkInks: ['black'] });
      paint(P(circle(DOOR[0] + DOOR[2] - 28, 790, 9)), { yellow: 1 });
    }
    // sidewalk (paper) and street (black)
    knock(P(rect(-1200, 1000, 4200, 90)), null);
    paint(P(rect(-1200, 1086, 4200, 12)), 'black');
    paint(P(rect(-1200, 1098, 4200, 400)), 'black');
  }

  // ---------------------------------------------------------------- 16 · Tiny shop on a side street, one good loaf of bread
  // Reads: (1) dawn, a tiny bakery, the sign still on, an empty street (a cat strolls); (2) the baker pulls one
  // gorgeous loaf from the oven on "one good loaf" (48.5); steam; (3) she turns and holds it up on "bread" (49.3);
  // (4) looks out at the empty street, and sighs (49.9–50.4).
  const PULL = 48.49, TURN = 49.2;
  function bakerPose(t) {
    const pull = E.back(seg(t, PULL, PULL + .42)), ant = E.io2(seg(t, PULL - .25, PULL)) * (1 - pull);
    if (t < TURN) {
      const lean = .12 + .1 * ant - .34 * pull;
      return { face: -1, x: 1500 + 130 * pull, lean, aN: [1.45, .05], aF: [1.3, .2], eyes: pull > .1 ? 'wide' : 'dot', mouth: pull > .1 && pull < .9 ? .4 : 0, peel: 1, peelOut: pull };
    }
    // "bread": the peel is set down, the loaf goes up (pride), then it sinks with her (the sigh)
    const up = E.back(seg(t, TURN - .02, TURN + .28)), down = E.io3(seg(t, 49.75, 50.15)), sigh = E.io2(seg(t, 49.9, 50.35));
    return { face: -1, x: 1630, lean: -.08 * up + .14 * sigh, sq: .06 * sigh - .05 * wobble(t, TURN + .2, 3, 8), bob: 10 * sigh, head: -.18 * up * (1 - down) + .3 * sigh,
      aN: [lerp(lerp(1.3, 2.35, up), 1.05, down), lerp(-.1, -.35, up)], aF: [lerp(lerp(1.2, 2.2, up), .95, down), lerp(0, -.2, up)],
      eyes: sigh > .3 ? 'closed' : up > .2 && down < .5 ? 'happy' : 'dot', mouth: up > .3 && down < .3 ? .6 : 0, smile: sigh > .2 ? 0 : 1, loafUp: 1, sigh };
  }
  function drawBaker(t, o = {}) {
    const b = { ...bakerPose(t), ...o };
    const holdLoaf = p => {
      if (b.peel) {          // the peel: handle in her hands, the blade (with the loaf) reaching into the oven
        const L = 112, out = b.peelOut;
        ink(P([[p[0] - 10, p[1] + 4], [p[0] + L, p[1] + 10]], false), 'black', { stroke: 9 });
        paint(P(ellipse(p[0] + L + 30, p[1] + 12, 52, 8)), 'black');
        if (out > .2) loaf(p[0] + L + 30, p[1] - 12, .75, .02, 1);
      } else if (b.loafUp) loaf(p[0] + 30, p[1] - 30, 1.05, -.05, 1);
      if (b.phone) { paint(P(rrect(p[0] - 6, p[1] - 46, 44, 76, 7)), 'black'); knock(P(rrect(p[0] - 1, p[1] - 40, 34, 62, 4)), null, b.phone > 1 ? 1 : 0); b.phoneAt = toScreen(p[0] + 16, p[1] - 8); }
    };
    figure(CAST.baker, b.x, 1010, 1.3, { ...b, hold: holdLoaf });
    return b;
    if (b.peel && b.peelOut > .15) steam(b.x - 330, 780, t, PULL + .3, 3, 190, 11);
    if (!b.peel && b.loafUp && t > TURN) steam(b.x - 170, 700, t, TURN + .25, 2, 140, 21);
    if (b.sigh > .2) {       // a little sigh cloud drifting from her mouth
      const u = seg(t, 49.95, 50.43);
      const sx = b.x - 110 - u * 70, sy = 690 - u * 50, r = 26 + u * 22;
      knock(P(cut(blob([[sx - r, sy], [sx - r * .4, sy - r * .8], [sx + r * .5, sy - r * .7], [sx + r, sy], [sx + r * .3, sy + r * .6], [sx - r * .6, sy + r * .5]], 4), 610, .6)), null);
    }
  }
  function s16_bakery(t, lt, dur) {
    const u = E.io2(clamp(lt / 1.2)), v = E.io3(seg(t, 47.55, 48.3));
    const back = E.io2(seg(t, 49.85, 50.43));
    const z = lerp(lerp(lerp(.94, 1.0, u), 1.5, v), 1.12, back), cx = lerp(lerp(lerp(1060, 1110, u), 1390, v), 1300, back), cy = bandCY(z);
    save(); cam(cx, cy, z);
    dawnSet(t, { sunY: 740 - 30 * u, interior: () => drawBaker(t) });
    if (v < 1) cat(lerp(2300, 1990, seg(t, 46.6, 47.6)), 1002, .95, t < 47.6 ? t * 1.6 : 0, -1);
    restore();
    // in: the flash of the chorus resolves as a halftone dissolve into the print
    const d = seg(lt, 0, .42);
    if (d < 1) knock(P(rect(0, 0, W, H)), null, 1 - E.out2(d));
    return { lyric: lyr(t) };
  }

  // ---------------------------------------------------------------- 17 · one little ad and the whole town's fed!
  // (a) 50.43–51.40 snap: phone up, flash on "one" (50.66), the photo rises out and folds into a paper plane;
  // (b) 51.40–52.37 the plane loops over the rooftops, windows fly open, heads pop up;
  // (c) 52.37–54.30 a queue floods the street, loaves arc over the crowd on beats, the baker beams. Out: a newspaper.
  const SNAP = 50.66, LAUNCH = 51.36;
  function s17a(t) {
    const u = seg(t, 50.43, 51.4);
    const z = lerp(1.5, 1.66, E.io2(u)); save(); cam(lerp(1390, 1440, E.io2(u)), bandCY(z), z);
    const raise = E.back(seg(t, 50.43, 50.62));
    let B = null;
    dawnSet(t, { sunY: 700, interior: () => {
      loaf(1420, 918, .95, 0, 2);
      B = drawBaker(t, { face: -1, x: 1640, lean: .12 * raise, aN: [lerp(.3, 1.45, raise), lerp(0, .75, raise)], aF: [.4, -.2], eyes: t > SNAP && t < SNAP + .18 ? 'closed' : 'dot', loafUp: 0, peel: 0, sigh: 0, mouth: 0, smile: 1, sq: 0, bob: 0, head: .25 * raise, phone: 1 });
    } });
    const sp = B && B.phoneAt ? B.phoneAt : [W / 2, H / 2];
    restore();
    // flash on "one" (screen space, at the phone)
    const f = seg(t, SNAP, SNAP + .22);
    if (f > 0 && f < 1) { const r = 40 + 360 * E.out3(f); knock(P(circle(sp[0], sp[1], r + 120)), null, radial(sp[0], sp[1], r * .6, r + 120, 1 - f, 1)); knock(P(starPts(sp[0], sp[1], r * .9, r * .18, 8)), null, 1 - f); }
    // the photo: rises out of the phone toward us (screen space), then folds into a plane and launches up-right
    const rise = E.out3(seg(t, SNAP + .06, 50.98)), fold = seg(t, 50.98, 51.26), go = E.inBack(seg(t, 51.24, 51.42));
    if (t > SNAP + .06) {
      const cx = lerp(sp[0], 880, rise) + go * 1100, cy = lerp(sp[1], 400, rise) - go * 700;
      planeOrCard(cx, cy, lerp(.6, 3.2, rise) * (1 - go * .3), lerp(.3, 0, rise) + lerp(0, -.62, E.io2(seg(t, 51.1, 51.3))), fold);
    }
    return { lyric: V2LYRIC };
  }
  // flight path over the rooftops (screen coords): up from below, a loop, then a flat swoop past the windows
  const B_END = 52.61;
  const flight = u => {
    if (u < .22) { const v = E.out2(u / .22); return [lerp(380, 820, v), lerp(1080, 570, v)]; }
    if (u < .5) { const v = (u - .22) / .28; return [820 + Math.sin(-v * TAU) * 170, 400 + Math.cos(v * TAU) * 170]; }
    const v = (u - .5) / .5; return [lerp(820, 2150, v), lerp(570, 560, v) - Math.sin(v * Math.PI) * 50];
  };
  const FL0 = LAUNCH + .04, FL1 = 52.46, flightU = t => seg(t, FL0, FL1);
  const WINX = [1180, 1380, 1580];
  // each shutter opens as the plane passes it
  const SHUT = WINX.map(x => { let u = .5; while (u < 1 && flight(u)[0] < x) u += .002; return [x, FL0 + u * (FL1 - FL0) - .02]; });
  function s17b(t) {
    const u = flightU(t);
    flood('yellow', 1);
    sun(330, 800, 105);
    // the facade across the street: shutters fly open as the plane passes; heads pop out
    paint(P(cut(rect(1070, 300, 900, 900), 620, 1.2)), { blue: 1 });
    paint(P(rect(1050, 282, 940, 26)), 'black');
    for (let r = 0; r < 2; r++) for (let c = 0; c < 4; c++) { const x = 1120 + c * 200, y = 640 + r * 190; if (y < 900) { knock(P(rect(x, y, 110, 140)), ['blue']); paint(P(rect(x, y, 110, 140)), 'black'); } }
    SHUT.forEach(([x, t0], i) => {
      const o = E.back(seg(t, t0, t0 + .2)), y = 380, w = 128, h = 180;
      knock(P(rect(x - w / 2, y, w, h)), ['blue']);
      paint(P(rect(x - w / 2, y, w, h)), o > 0 ? { yellow: 1 } : 'black');
      const hp = E.back(seg(t, t0 + .04, t0 + .26));
      if (hp > 0) head(CAST.anon, x - 4, y + h + 44 - hp * 110, 1.45, { var: [0, 3, 2][i], eyes: 'wide', face: -1, mouth: .55, look: [1, -.5], seed: i * 7, blush: 0 });
      paint(P(rect(x - w / 2 - 10, y + h, w + 20, 18)), 'black');
      const sw = (w / 2) * (1 - o * .82), sx = (w / 2 - sw) * 1.25 * o;
      paint(P(cut(rect(x - w / 2 - sx, y, sw, h), 630 + i)), 'black');
      paint(P(cut(rect(x + w / 2 - sw + sx, y, sw, h), 640 + i)), 'black');
      for (let k = 1; k < 4; k++) { knock(P([[x - w / 2 - sx + 5, y + k * h / 4], [x - w / 2 - sx + sw - 5, y + k * h / 4]], false), ['black'], 1, { stroke: 3 }); knock(P([[x + w / 2 - sw + sx + 5, y + k * h / 4], [x + w / 2 + sx - 5, y + k * h / 4]], false), ['black'], 1, { stroke: 3 }); }
    });
    // rooftops in the foreground (black): chimneys, a water tower; a paper parapet cap carries the words
    paint(P(cut([[-100, 1100], [-100, 830], [160, 830], [160, 770], [220, 770], [220, 830], [560, 830], [580, 870], [900, 870], [900, 815], [980, 815], [980, 870], [1200, 870], [1200, 900], [2000, 900], [2000, 1100]], 650, 1.4)), 'black');
    paint(P(cut(rect(640, 700, 120, 110), 651)), 'black'); paint(P(cut([[630, 700], [700, 660], [770, 700]], 652)), 'black');
    for (const dx of [650, 700, 745]) paint(P(rect(dx, 800, 7, 80)), 'black');
    knock(P(rect(-20, 962, W + 40, 84)), null);
    paint(P(rect(-20, 1046, W + 40, 40)), 'black');
    // the plane and its dotted trail
    if (u > 0 && u < 1) {
      trail(flight, u, .42);
      const p = flight(u), q = flight(Math.min(1, u + .01)), a = Math.atan2(q[1] - p[1], q[0] - p[0]);
      planeOrCard(p[0], p[1], 1.9, a, 1);
    }
    return { lyric: V2LYRIC };
  }
  // the queue: people walk in from both sides to places in line; each catches a loaf on a beat
  const QUEUE = Array.from({ length: 11 }, (_, i) => {
    const fromLeft = i % 3 !== 1, qx = 1650 - i * 125 - (i > 5 ? 20 : 0);
    return { qx, x0: fromLeft ? -250 - i * 60 : 2800 + i * 50, t0: 52.45 + i * .05, arrive: 52.9 + i * .06 + hash(i) * .15, var: i, s: .92 + hash(i * 7) * .14, catchAt: null };
  });
  const TOSS = [52.85, 53.33, 53.82];
  const catcher = [1, 4, 7];
  TOSS.forEach((tb, k) => { QUEUE[catcher[k]].catchAt = tb + .46; });
  function s17c(t) {
    const u = E.io2(seg(t, B_END, 54.3));
    const z = lerp(1.0, .95, u); save(); cam(lerp(1200, 1230, u), bandCY(z), z);
    dawnSet(t, { sunY: 640, doorOpen: true, interior: () => {} });
    // the baker in the doorway: tosses on the beats, beaming
    const tk = TOSS.findIndex(tb => t < tb + .3), tb = TOSS[Math.max(0, tk < 0 ? TOSS.length - 1 : tk)];
    const wind = E.io2(seg(t, tb - .22, tb)), fling = E.out3(seg(t, tb, tb + .16));
    figure(CAST.baker, 1870, 1004, 1.15, { face: -1, eyes: 'happy', mouth: .55 + .3 * pulse(t, 5), lean: -.08 * wind + .12 * fling,
      aN: [lerp(lerp(.9, -.6, wind), 2.6, fling), lerp(-.6, .1, fling)], aF: [2.3 + .25 * Math.sin(t * 7), .3], bob: -6 * pulse(t, 7) });
    // the crowd
    const order = [...QUEUE].sort((a, b) => a.qx - b.qx);
    for (const q of order) {
      const walkU = seg(t, q.t0, q.arrive), x = lerp(q.x0, q.qx, E.out2(walkU)), walking = walkU < 1;
      const caught = q.catchAt && t > q.catchAt, reach = q.catchAt ? E.back(seg(t, q.catchAt - .3, q.catchAt)) : 0;
      const f = walking ? (q.x0 < q.qx ? 1 : -1) : 1;
      const pose = walking ? { walk: t * 1.9 + q.var * .37 } : { bob: -5 * pulse(t, 6, 1, q.var * .13), aN: reach > 0 ? [lerp(.2, 2.7, reach), .2] : [.15, .3], aF: caught ? [2.2, .5] : [-.1, .2] };
      const fo = { var: q.var, face: f, eyes: caught ? 'happy' : 'dot', mouth: caught ? .5 : 0, seed: q.var * 13, ...pose };
      // a cut-out sticker: a yellow border (the same figure, a touch larger) so black reads on black
      for (const [dx, dy] of [[-5, 0], [5, 0], [0, -5], [0, 4]]) figure(CAST.anon, x + dx, 1004 + dy, q.s, { ...fo, ink: { yellow: 1 }, eyes: 'none', mouth: 0, smile: 0, blush: 0 });
      figure(CAST.anon, x, 1004, q.s, { ...fo, hold: caught ? p => loaf(p[0] + 10, p[1] - 30, .7, -.3, q.var) : null });
    }
    // loaves in flight: from her hand to the catcher, an arc on each beat
    TOSS.forEach((tb, k) => {
      const v = seg(t, tb + .02, tb + .46); if (v <= 0 || v >= 1) return;
      const q = QUEUE[catcher[k]], p = arcPt([1770, 800], [q.qx + 60 * q.s, 1004 - 300 * q.s], 260, v);
      loaf(p[0], p[1], .85, v * 4 + k, k);
    });
    restore();
    // out: a newspaper page sweeps in from the right (54.05 -> 54.30), the history begins
    const w = E.in3(seg(t, 54.02, 54.3));
    if (w > 0) newspaperPage(lerp(W + 200, 0, w), 0, lerp(-.08, 0, w));
    return { lyric: V2LYRIC };
  }
  function s17_plane(t, lt, dur) { return t < LAUNCH + .04 ? s17a(t) : t < B_END ? s17b(t) : s17c(t); }

  // a full newspaper page: paper, a masthead bar, columns of black "type", a halftone photo block
  function newspaperPage(x, y, r) {
    save(); translate(x, y); rotate(r);
    const page = P(rect(0, -40, W + 80, H + 80));
    knock(page, null);
    paint(P(rect(60, 40, W - 120, 110)), 'black');
    knock(P(rect(90, 70, W - 180, 50)), ['black']);
    paint(P(rect(60, 175, W - 120, 8)), 'black');
    paint(P(rect(60, 210, 820, 90)), 'black');
    ink(P(rect(60, 330, 820, 520)), { yellow: 1 }); ink(P(rect(60, 330, 820, 520)), { black: linear(60, 330, 880, 850, .7, .15) });
    for (let c = 0; c < 3; c++) for (let l = 0; l < 26; l++) { const lx = 930 + c * 320, ly = 215 + l * 30, lw = 280 - (hash(c * 50 + l) > .8 ? 120 : 0); paint(P(rect(lx, ly, lw, 10)), 'black'); }
    for (let l = 0; l < 6; l++) paint(P(rect(60, 880 + l * 30, 820 - (l === 5 ? 300 : 0), 10)), 'black');
    restore();
  }

  // ---------------------------------------------------------------- 18 · Penny papers, radio, the TV in the den
  // Three comic panels slam in on the three nouns (54.48, 55.26, 56.16), each one read in its own ink pair.
  const PANELS = [
    { x: 80, y: 105, w: 560, h: 790, r: -.025, land: 54.44, from: [0, -1100] },
    { x: 680, y: 150, w: 560, h: 790, r: .018, land: 55.22, from: [0, 1100] },
    { x: 1280, y: 105, w: 560, h: 790, r: -.012, land: 56.12, from: [1000, 0] },
  ];
  function panel(i, t, k = 1, pull = null) {
    const p = PANELS[i], land = E.back(seg(t, p.land - .16, p.land + .1));
    if (land <= 0) return;
    const off = pull || [p.from[0] * (1 - land), p.from[1] * (1 - land)];
    const cx = p.x + p.w / 2 + off[0], cy = p.y + p.h / 2 + off[1];
    save(); translate(cx, cy); rotate(p.r * (1 + (1 - land) * 3)); scale(k); translate(-p.w / 2, -p.h / 2);
    // drop shadow (black offset card), then the panel
    paint(P(rect(14, 16, p.w, p.h)), 'black');
    const box = P(rect(0, 0, p.w, p.h));
    knock(box, null);
    clipIn(box);
    [panelNews, panelRadio, panelTV][i](t, p.w, p.h, t - p.land);
    clipOut();
    paint(box, 'black', { stroke: 12 });
    restore();
  }
  function panelNews(t, w, h, age) {
    paint(P(rect(0, 0, w, h)), { yellow: 1 });
    // brick coursing (black hairlines) and a lamppost
    for (let r = 0; r < 5; r++) ink(P([[0, 60 + r * 88], [w, 60 + r * 88]], false), 'black', { stroke: 2 });
    paint(P(rect(470, 120, 16, h)), 'black'); paint(P(cut(blob([[440, 150], [455, 95], [500, 95], [515, 150]], 3), 700)), 'black');
    paint(P(rect(0, h - 80, w, 80)), 'black');
    const shout = .35 + .6 * pulse(t, 6);
    const flip = seg(t, 54.74, 55.18);
    figure(CAST.newsboy, 220, h - 80, 1.75, { face: 1, mouth: shout, eyes: 'dot', lean: -.08 + .05 * pulse(t, 6), bob: -6 * pulse(t, 6),
      aN: [2.05 + .1 * Math.sin(t * 9), .45], aF: [.9 - .5 * E.out3(seg(t, 54.7, 54.8)), -1.2],
      hold: p => {       // the paper, held high and shaken
        save(); translate(p[0] + 62, p[1] - 58); rotate(.22 + .06 * Math.sin(t * 14));
        knock(P(rect(-70, -95, 140, 190)), null); ink(P(rect(-70, -95, 140, 190)), 'black', { stroke: 4 });
        paint(P(rect(-58, -82, 116, 26)), 'black');
        for (let l = 0; l < 7; l++) paint(P(rect(-58, -44 + l * 18, l % 3 === 2 ? 60 : 116, 6)), 'black');
        restore();
      },
      holdF: p => {      // the penny: flipped up on the beat, spinning
        if (flip <= 0 || flip >= 1) { if (flip <= 0) coin(p[0] + 8, p[1] - 6, 1, 1); return; }
        const q = arcPt([p[0] + 8, p[1] - 6], [p[0] + 8, p[1] - 6], 190, flip);
        coin(q[0], q[1], Math.cos(flip * TAU * 3), 1);
      } });
  }
  function coin(x, y, sx, s) {
    save(); translate(x, y); scale(Math.abs(sx) < .12 ? .12 : sx, 1); scale(s);
    paint(P(circle(0, 0, 26, 28)), { yellow: 1, pink: 1 }); ink(P(circle(0, 0, 26, 28)), 'black', { stroke: 4 }); ink(P(circle(0, 0, 17, 20)), 'black', { stroke: 2 });
    restore();
  }
  function panelRadio(t, w, h, age) {
    paint(P(rect(0, 0, w, h)), { blue: 1 });
    const fl = h - 90;
    paint(P(rect(0, fl, w, 90)), 'black');
    // a rug
    paint(P(cut(ellipse(250, fl + 20, 230, 26), 710)), { yellow: 1 });
    // sound: arcs from the speaker, one wave per beat
    const sp = [405, fl - 230];
    for (let k = 0; k < 3; k++) {
      const v = frac(beatPos(t) + k / 3), r = 70 + v * 300;
      knock(P(arcPts(sp[0], sp[1], r, Math.PI - .75, Math.PI + .75, 20), false), ['blue'], 1, { stroke: 10 * (1 - v) + 2 });
    }
    // the cathedral radio
    const rx = 350, ry = fl - 320;
    paint(P(cut(blob([[rx, ry + 340], [rx, ry + 130], [rx + 30, ry + 40], [rx + 100, ry], [rx + 170, ry + 40], [rx + 200, ry + 130], [rx + 200, ry + 340]], 5), 720)), { yellow: 1 });
    const gr = P(cut(blob([[rx + 40, ry + 220], [rx + 40, ry + 130], [rx + 65, ry + 70], [rx + 100, ry + 52], [rx + 135, ry + 70], [rx + 160, ry + 130], [rx + 160, ry + 220]], 4), 721));
    paint(gr, 'black');
    for (let k = 0; k < 5; k++) paint(P(rect(rx + 58 + k * 20, ry + 70, 7, 150)), { yellow: 1 });
    knock(P(circle(rx + 100, ry + 280, 26)), null); ink(P([[rx + 100, ry + 280], [rx + 100 + Math.cos(t * 1.3) * 20, ry + 280 - 18]], false), 'black', { stroke: 4 });
    // the family, sitting on the rug, listening (turning to each other on the beat)
    const sit = (Ch, x, s, o) => figure(Ch, x, fl + (Ch.legH[0] + Ch.legH[1] - 6) * s, s, { lF: [1.45, .05], lN: [1.5, .0], aN: [.7, .9], aF: [.5, .9], ...o });
    sit(CAST.anon, 30, 1.3, { var: 1, ink: { black: 1 }, head: .08 * Math.sin(beatPos(t) * Math.PI), lean: -.05 });
    sit(CAST.anon, 125, 1.22, { var: 3, ink: { black: 1 }, lean: .05, head: -.1 });
    sit(CAST.kid, 215, 1.35, { ink: { black: 1 }, lean: .12 + .05 * pulse(t, 5), bob: 0, aN: [2.2 + .3 * pulse(t, 6), .2] });
  }
  function panelTV(t, w, h, age) {
    paint(P(rect(0, 0, w, h)), { pink: 1 });
    const fl = h - 130;
    paint(P(rect(0, fl, w, 130)), { blue: 1 });
    // the TV on its legs, rabbit ears, a test pattern; its glow thins the pink
    const tx0 = 320, ty0 = fl - 330;
    knock(P(circle(tx0 + 110, ty0 + 120, 420)), ['pink'], radial(tx0 + 110, ty0 + 120, 120, 420, .8, 1.4));
    ink(P([[tx0 + 110, ty0 + 10], [tx0 + 40, ty0 - 110]], false), 'black', { stroke: 5 }); ink(P([[tx0 + 110, ty0 + 10], [tx0 + 190, ty0 - 100]], false), 'black', { stroke: 5 });
    paint(P(cut(rrect(tx0, ty0, 220, 250, 26), 730)), { blue: 1 });
    for (const lx of [tx0 + 30, tx0 + 170]) paint(P([[lx, ty0 + 245], [lx + 20, ty0 + 245], [lx + (lx > tx0 + 100 ? 40 : -20), fl + 30], [lx + (lx > tx0 + 100 ? 28 : -32), fl + 30]]), 'black');
    const scr = P(rrect(tx0 + 22, ty0 + 22, 176, 150, 18));
    paint(scr, 'black');
    clipIn(scr);
    const bars = [null, 'pink', 'blue', { pink: 1, blue: 1 }, null, 'black'], bw = 176 / 6, jig = Math.floor(jit(3, 1.2)) * 2;
    bars.forEach((b, k) => { const r = P(rect(tx0 + 22 + k * bw + jig, ty0 + 22, bw + 1, 110)); if (b === null) knock(r, null); else { knock(r, null); ink(r, b); } });
    for (let k = 0; k < 6; k++) { const r = P(rect(tx0 + 22 + k * bw, ty0 + 132, bw + 1, 40)); knock(r, null); if (k % 2) ink(r, 'black'); }
    clipOut();
    paint(P(circle(tx0 + 200, ty0 + 210, 9)), 'black'); paint(P(circle(tx0 + 170, ty0 + 210, 9)), 'black');
    // the kid, lying on her belly, chin in hands, feet kicking on the beat
    const by = fl + 12, kick = beatPos(t) * Math.PI;
    for (const [ph, dx] of [[0, 0], [Math.PI, 14]]) {
      const a = .5 + .45 * Math.sin(kick + ph);
      paint(P(ribbon([[90 + dx, by - 22], [30 + dx, by - 18], [30 + dx - Math.cos(a) * 70, by - 18 - Math.sin(a) * 70]], 22, 16, 740 + dx)), { blue: 1 });
    }
    paint(P(cut(blob([[80, by - 2], [85, by - 52], [200, by - 64], [236, by - 40], [230, by - 2]], 4), 741)), { blue: 1 });
    paint(P(ribbon([[215, by - 44], [250, by - 4], [262, by - 70]], 18, 14, 742)), { blue: 1 });
    head(CAST.kid, 268, by - 108, 1.25, { ink: { blue: 1 }, eyes: 'wide', look: [1, 0], head: .1 * Math.sin(t * 2.2), blush: 0, smile: 1 });
  }
  // captions: the line's words printed under their panels as they're sung
  const HIST = () => LINES.find(l => l.text.startsWith('Penny'));
  const CAPS = [[0, 1], [2], [3, 4, 5, 6, 7]];
  function captions(t, alpha = 1, dy = 0) {
    const L = HIST(); if (!L || alpha <= 0) return;
    CAPS.forEach((idx, pi) => {
      const p = PANELS[pi]; let x = p.x + 6;
      for (const i of idx) {
        const wd = L.words[i]; if (!wd) continue;
        const S = shape(wd.w, { font: 'arch', size: 64, wdth: 74, wght: 800 }), a = t - (wd.t0 - .05);
        if (a >= 0) { const u = clamp(a / .2); drawText(S, x, 1005 + (1 - E.back(u)) * 30 + dy, 'black'); }
        x += S.width + 64 * .26;
      }
    });
  }
  function s18_history(t, lt, dur) {
    knock(P(rect(0, 0, W, H)), null);
    for (let i = 0; i < 3; i++) panel(i, t);
    captions(t);
    // in: the newspaper page from S17 slides on off to the left
    const w = E.in2(seg(t, 54.3, 54.52));
    if (w < 1) newspaperPage(lerp(0, -W - 300, w), 0, lerp(0, .05, w));
    return { lyric: false };
  }

  // ---------------------------------------------------------------- 19 · every time the world got free, somebody paid for it then
  // Reads: (1) the three panels fold into the middle and their objects become one phone in a hand (by "got" 58.74);
  // (2) its screen lights on "free" (58.98); (3) a hand from above brings a coin (59.34) and drops it in on "paid"
  // (60.06); (4) every light in the city comes on (60.5–61.1); (5) the band stops: black (61.9).
  const PH = [1120, 500];
  function s19_patron(t, lt, dur) {
    // night comes in behind the collapsing panels (a blue iris from the centre)
    const irisU = E.in2(seg(t, 57.9, 58.45));
    knock(P(rect(0, 0, W, H)), null);
    if (irisU > 0) paint(P(circle(W / 2, H / 2, irisU * 1250, 64)), { blue: 1 });
    // city skyline along the bottom; its windows wake after the coin
    const wake = t - 60.2;
    const tops = [760, 700, 820, 660, 740, 690, 800, 720, 650, 780];
    tops.forEach((top, i) => {
      const x = -40 + i * 200, w = 190;
      if (irisU < .55) return;
      paint(P(cut(rect(x, top + 90 * (1 - E.out3(clamp((irisU - .55) / .45))), w, 500), 800 + i, 1.2)), 'black');
      for (let k = 0; k < 8; k++) {
        const wx = x + 30 + (k % 3) * 52, wy = top + 40 + Math.floor(k / 3) * 70, d = Math.abs(wx + 20 - PH[0]) / 900;
        const on = wake > d * .7 + hash(i * 9 + k) * .25;
        if (wy > 1080) continue;
        if (on) { knock(P(rect(wx, wy, 30, 44)), ['black']); paint(P(rect(wx, wy, 30, 44)), { yellow: 1 }); }
      }
    });
    // stars come on too
    if (wake > 0) for (let i = 0; i < 40; i++) { const x = hash(i * 3.1) * W, y = hash(i * 7.7) * 560; if (wake > hash(i * 5.5) * .9 && !(x < 820 && y < 380)) knock(P(starPts(x, y, 7 + hash(i) * 6, 2.2)), ['blue']); }
    // the panels fold to the centre
    const col = E.in3(seg(t, 57.9, 58.5));
    if (col < 1) for (let i = 0; i < 3; i++) {
      const p = PANELS[i], c = [p.x + p.w / 2, p.y + p.h / 2];
      panel(i, 58.5, 1 - col, [lerp(0, PH[0] - c[0], col), lerp(0, PH[1] - c[1], col)]);
    }
    // the phone appears on "got" (58.74) with a pop; lights on "free" (58.98)
    const pop = E.back(seg(t, 58.62, 58.86)), lit = seg(t, 58.96, 59.1), glow = lit * (1 + .8 * E.out3(seg(t, 60.1, 60.9)) - .3 * E.in2(seg(t, 61.2, 61.9)));
    const jig = wobble(t, 60.1, 5, 7) * .08;
    if (pop > 0) {
      if (lit > 0) {
        knock(P(circle(PH[0], PH[1], 900)), ['blue'], radial(PH[0], PH[1], 150, 420 + 380 * glow, .85 * clamp(glow), 1.3));
        ink(P(circle(PH[0], PH[1], 900)), { yellow: radial(PH[0], PH[1], 120, 300 + 300 * glow, .5 * clamp(glow), 1.4) });
      }
      save(); translate(PH[0], PH[1] + 240); scale(1.3 * pop * (1 + jig), 1.3 * pop * (1 - jig)); translate(-PH[0], -(PH[1] + 240));
      // the kid's pink sleeve and hand, from below
      paint(P(ribbon([[PH[0] + 60, 1180], [PH[0] + 30, 950], [PH[0] + 10, PH[1] + 220]], 110, 96, 810)), { pink: 1 });
      paint(P(rrect(PH[0] - 130, PH[1] - 240, 260, 480, 34)), 'black');
      const scr = P(rrect(PH[0] - 112, PH[1] - 205, 224, 410, 12));
      if (lit > 0) {
        knock(scr, null);
        // a page on the screen: an image block and lines of text-bars
        clipIn(scr);
        paint(P(rect(PH[0] - 92, PH[1] - 180, 184, 120)), { yellow: 1 }); paint(P(ellipse(PH[0], PH[1] - 118, 40, 40)), { pink: 1 });
        for (let l = 0; l < 7; l++) paint(P(rect(PH[0] - 92, PH[1] - 34 + l * 30, l % 3 === 2 ? 110 : 184, 10)), 'black');
        clipOut();
      } else paint(scr, { blue: 1, black: 1 });
      // the coin slot on its top edge
      paint(P(rrect(PH[0] - 46, PH[1] - 232, 92, 14, 7)), { blue: 1, black: 1 });
      knock(P(rrect(PH[0] - 40, PH[1] - 229, 80, 7, 3)), null);
      paint(P(rrect(PH[0] - 40, PH[1] - 229, 80, 7, 3)), 'black');
      // her fingers wrapping the sides
      for (let k = 0; k < 3; k++) paint(P(cut(rrect(PH[0] - 150, PH[1] + 90 + k * 46, 44, 38, 16), 820 + k)), { pink: 1 });
      paint(P(cut(rrect(PH[0] + 106, PH[1] + 120, 46, 70, 18), 824)), { pink: 1 });
      restore();
    }
    // the patron's hand: a black sleeve with a paper cuff, from above, holding a coin
    const down = E.out3(seg(t, 59.3, 59.82)), hesit = E.io2(seg(t, 59.82, 60.0)), up = E.in2(seg(t, 60.22, 60.7));
    const TOP = PH[1] + 240 - 1.3 * 472;
    const hy = lerp(-420, TOP - 225, down) - 14 * hesit + 12 * E.out3(seg(t, 60.0, 60.08)) - up * 800;
    if (hy > -400) {
      const hx = PH[0] + 20;
      save(); translate(hx, hy); scale(1.45); translate(-hx, -hy);
      paint(P(ribbon([[hx + 70, hy - 700], [hx + 40, hy - 150], [hx + 10, hy - 20]], 120, 110, 830)), 'black');
      knock(P(rect(hx - 50, hy - 70, 120, 30)), ['black']); ink(P(rect(hx - 50, hy - 70, 120, 30)), 'black', { stroke: 3 });
      paint(P(cut(blob([[hx - 48, hy - 40], [hx + 64, hy - 42], [hx + 70, hy + 30], [hx + 20, hy + 70], [hx - 30, hy + 60], [hx - 56, hy + 10]], 4), 831)), 'black');
      paint(P(ribbon([[hx - 30, hy + 50], [hx - 22, hy + 96]], 24, 20, 832)), 'black');
      paint(P(ribbon([[hx + 24, hy + 56], [hx + 14, hy + 98]], 22, 18, 833)), 'black');
      restore();
    }
    // the coin: pinched, released on "paid", falls into the slot
    const drop = seg(t, 60.04, 60.14);
    if (t < 60.14 && hy > -400) {
      const cy = t < 60.04 ? hy + 160 : lerp(hy + 160, TOP + 12, E.in2(drop));
      save(); translate(PH[0] - 4, cy); scale(1.3, 1.3);
      paint(P(ellipse(0, 0, 38, 38 * (t < 60.04 ? 1 : lerp(1, .25, drop)))), { yellow: 1 }); ink(P(ellipse(0, 0, 38, 38 * (t < 60.04 ? 1 : lerp(1, .25, drop)))), 'black', { stroke: 4 });
      ink(P(ellipse(0, 0, 26, 26 * (t < 60.04 ? 1 : lerp(1, .25, drop)))), 'black', { stroke: 2 });
      restore();
    }
    // clink: a paper spark at the slot
    const ck = seg(t, 60.12, 60.4);
    if (ck > 0 && ck < 1) knock(P(starPts(PH[0], TOP, 40 + 80 * E.out3(ck), 10, 6)), ['blue', 'black'], 1 - ck);
    // out: the band stops -> black
    if (t >= 61.9) { flood('black', 1); knock(P(rect(0, 0, W, H)), ['pink', 'yellow']); }
    return { lyric: t >= 61.9 ? false : { slot: 'ul', ink: 'knock', accentInk: 'knock', size: 66, maxW: 640 } };
  }

  SHOT_FN['16'] = s16_bakery;
  SHOT_FN['17'] = s17_plane;
  SHOT_FN['18'] = s18_history;
  SHOT_FN['19'] = s19_patron;
})();
