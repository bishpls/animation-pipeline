// 12, 20, 22, 23, 25, 28 · the procession, the poster, the choir, the city
(() => {
  // ---------------------------------------------------------------- shared private helpers
  const EIGHTH = BEAT / 2;
  // a phone held up: black body, paper screen; when lit, the flood around it thins toward paper (light is paper)
  function phone(p, ang, s, lit, floods = ['blue', 'pink']) {
    if (lit > 0) {
      const R = 150 * s * (.6 + .4 * lit);
      knock(P(circle(p[0], p[1] - 20 * s, R)), floods, radial(p[0], p[1] - 20 * s, 8 * s, R, .95 * lit, 1.2));
      ink(P(circle(p[0], p[1] - 20 * s, R * .7)), { yellow: radial(p[0], p[1] - 20 * s, 6 * s, R * .7, .55 * lit, 1.4) });
    }
    save(); translate(p[0], p[1]); rotate(ang - Math.PI / 2 + .3); scale(s);
    paint(P(rrect(-15, -52, 30, 50, 5)), 'black');
    if (lit > 0) knock(P(rrect(-11, -48, 22, 40, 3)), null);
    restore();
  }
  function heartPts(cx, cy, r) {
    const p = [];
    for (let i = 0; i < 40; i++) { const a = i / 40 * TAU, x = 16 * Math.sin(a) ** 3, y = -(13 * Math.cos(a) - 5 * Math.cos(2 * a) - 2 * Math.cos(3 * a) - Math.cos(4 * a)); p.push([cx + x * r / 16, cy + y * r / 16]); }
    return p;
  }
  // paper rain: short diagonal streaks, stable per drop, falling fast (a drawing every other frame: on twos)
  function rain(t, n, x0, y0, w, h, seed = 1, which = ['blue', 'black']) {
    const tt = onTwos(t);
    for (let i = 0; i < n; i++) {
      const sp = 1400 + 500 * hash(seed + i * 1.7), ph = hash(seed + i * 3.1);
      const x = x0 + hash(seed + i * 7.3) * w, y = y0 + ((ph * h + tt * sp) % h);
      const L = 26 + 30 * hash(i + seed);
      knock(P([[x, y], [x - L * .25, y + L]], false), which, 1, { stroke: 2.2 });
    }
  }
  // a generic city block for the wide shots. win(f, c, x, y, w, h) draws each window's contents.
  function miniBlock(x, ground, w, floors, cols, seed, spec, win) {
    const fh = 64, top = ground - floors * fh - 30;
    paint(P(cut(rect(x, top, w, ground - top + 40), seed, 1, .4)), spec);
    if (hash(seed * 1.3) > .5) paint(P(cut(rect(x + w * .6, top - 40, w * .22, 40), seed + 1)), spec);   // rooftop box
    const cw = w / cols;
    for (let f = 0; f < floors; f++) for (let c = 0; c < cols; c++) {
      const wx = x + c * cw + cw * .25, wy = top + 30 + f * fh + fh * .18;
      win(f, c, wx, wy, cw * .5, fh * .6, seed * 31 + f * 7 + c);
    }
  }
  const skyWave = (t, t0, x, speed = 2400) => clamp((t - t0 - x / speed) / .08);   // a wave sweeping left to right

  // ---------------------------------------------------------------- 12 · Every window, every door, every kid gets a light!
  // Reads: (1) a street of facades; windows pop yellow in a cascade (34.24–35.6); (2) doors swing open, light spills out
  // (35.96–36.9); (3) kids march in along the pavement; each lifts a phone and it lights, one per eighth note (37.4–38.8);
  // (4) the last light glints (-> the eye's catch-light).
  function s12_procession(t, lt, dur) {
    const down = E.io3(seg(t, 36.75, 37.4));
    const push = lerp(1, 1.06, down) * (1 + .025 * E.io2(lt / dur)) + .012 * pulse(t, 7, 1);
    const truck = lerp(0, 60, E.io2(lt / dur));
    save(); cam(W / 2 + truck, lerp(H / 2, 590, down), push);
    flood('pink', 1);
    // facades: a continuous blue street front with a roofline that steps
    const roof = [[-200, 330], [260, 330], [260, 300], [700, 300], [700, 345], [1180, 345], [1180, 290], [1640, 290], [1640, 330], [2200, 330]];
    paint(P(cut([...roof, [2200, 900], [-200, 900]], 1201, 1.4, .5)), { blue: 1 });
    for (const [a, b] of [[260, 700], [1180, 1640]]) paint(P(cut(rect(a, 300 - 18, b - a, 18), 1202 + a)), 'black');   // cornices
    // windows: two floors x 12, lit in a cascade on eighths from "Every window"
    const order = [5, 2, 9, 0, 7, 11, 3, 6, 1, 10, 4, 8];
    for (let f = 0; f < 2; f++) for (let c = 0; c < 12; c++) {
      const x = -120 + c * 185, y = 400 + f * 170, w = 100, h = 118, sd = 1210 + f * 12 + c;
      const k = order.indexOf(c) + f * 3, tl = 34.2 + (k % 12) * EIGHTH * .75;
      const pop = E.back2(clamp((t - tl) / .14));
      const sh = P(cut(rect(x, y, w, h), sd, .8, .4));
      paint(sh, 'black');
      if (pop > 0) {
        const g = 1 + .12 * (1 - Math.min(1, pop));
        const lr = P(cut(rect(x + w / 2 - w / 2 * pop * g, y + h / 2 - h / 2 * pop * g, w * pop * g, h * pop * g), sd + 1, .8, .4));
        paint(lr, { yellow: 1 });
        knock(P(rect(x + w * .12, y + h * .12, w * .2, h * .76)), ['yellow'], pop > .9 ? 1 : 0);   // a paper glint on the glass
      }
      paint(P(rect(x + w / 2 - 4, y, 8, h)), 'blue');
      paint(P(rect(x - 10, y + h, w + 20, 12)), 'black');                                    // sill
    }
    // ground floor: doors swing open on "every door" (35.96 .. 36.6), light spills onto the pavement
    const doorT = [35.96, 36.12, 36.28, 36.44, 36.60, 36.76];
    paint(P(cut(rect(-200, 900, 2400, 300), 1250, 1.2)), 'black');                            // pavement
    for (let d = 0; d < 6; d++) {
      const x = -60 + d * 370, y = 720, w = 120, h = 180, sd = 1260 + d;
      const op = E.back(clamp((t - doorT[d]) / .22));
      paint(P(cut(rect(x - 14, y - 14, w + 28, h + 14), sd)), 'black');                     // frame
      if (op > 0) {
        // the doorway: light (paper + yellow) and the spill across the pavement
        paint(P(rect(x, y, w, h)), { yellow: 1 });
        knock(P(rect(x + 16, y + 16, w - 32, h - 16)), null);
        const sp = Math.min(1, op);
        const spill = [[x, y + h], [x + w, y + h], [x + w + 120 * sp, y + h + 190 * sp], [x - 120 * sp, y + h + 190 * sp]];
        paint(P(cut(spill, sd + 5, 1)), { yellow: 1 });
        knock(P(spill), ['yellow'], linear(0, y + h, 0, y + h + 190, 0, .9));
      }
      // the door leaf: swings in (foreshortens) toward the hinge side
      const leafW = w * Math.max(.08, 1 - Math.min(1, op) * .92) * (op > 1 ? 1 : 1);
      paint(P(cut(rect(x, y, leafW, h), sd + 9, .6, .3)), op > 0 ? { pink: 1, black: 1 } : { pink: 1 });
      if (op <= 0) paint(P(circle(x + w - 22, y + h * .55, 7)), 'black');
    }
    // the procession: kids march in from the left, each lifts a phone that lights on an eighth note
    const N = 8, lightT0 = 37.40;
    for (let i = N - 1; i >= 0; i--) {
      const ch = [CAST.kid, CAST.newsboy, CAST.kid, CAST.kid, CAST.newsboy, CAST.kid, CAST.kid, CAST.newsboy][i];
      const s = [1.62, 1.44, 1.7, 1.52, 1.4, 1.66, 1.55, 1.46][i];
      const enter = E.out3(clamp((t - 36.7 - i * .05) / .75));
      const x = lerp(-400 - i * 40, 1560 - i * 205, enter) + (t - 37.6) * 25, y = 1080 + (i % 2) * 14;
      const tl = lightT0 + (N - 1 - i) * EIGHTH;           // the leader (rightmost) lights first
      const lit = E.out3(clamp((t - tl) / .12));
      const raise = kf(t, [[tl - .22, [.35, -.4]], [tl, [3.05 + .12 * hash(i), -.12], "back"]]);
      if (enter <= 0) continue;
      figure(ch, x, y, s, { ink: { black: 1 }, walk: t * 1.9 + i * .31, aN: raise, look: lit > 0 ? [.4, -1] : [0, 0], head: lit > 0 ? -.18 : 0, mouth: lit > .5 ? .5 + .4 * pulse(t, 6, .5, i * .13) : 0, seed: i * 17,
        hold: (p, a) => phone(p, a, 1.15, lit) });
    }
    // out: the leader's light glints into a four-point star (-> the catch-light of the eye in 13)
    const gl = E.in3(seg(t, 38.55, 38.95));
    if (gl > 0) {
      const lp = toScreen(1560 + (t - 37.6) * 25 + 40, 1080 - 1.62 * 290);
      restore(); save();
      const r = 30 + gl * 1400;
      knock(P(starPts(lp[0], lp[1], r, r * .12, 4)), null);
      knock(P(circle(lp[0], lp[1], r * .35)), null, radial(lp[0], lp[1], r * .05, r * .35, 1, .8));
    }
    restore();
    return { lyric: { slot: 'uc', y: 140, size: 74, ink: 'black', accentInk: 'blue', maxW: 1800, stamp: 'yellow' } };
  }

  // ---------------------------------------------------------------- 20 · Nobody ever wrote a love song for the ads
  // Reads: (1) out of the black, a streetlamp buzzes on over a wet brick wall: one plain poster; rain (62.04–62.7);
  // (2) the thesis lyric, big serif (62.72–64.86); (3) the kid walks in, stops under the poster, looks up (63.2–64.3);
  // (4) a tiny heart rises (64.6); (5) push into the glass of her phone (65.0–65.6).
  function s20_poster(t, lt, dur) {
    const lampOn = t < 62.12 ? 0 : t < 62.17 ? 1 : t < 62.24 ? 0 : t < 62.3 ? .6 : t < 62.36 ? 0 : 1;
    const push = E.inExpo(seg(t, 64.95, 65.60));
    // kid path: walks in from the left, stops under the poster
    const walkU = E.out3(seg(t, 62.4, 64.0));
    const kx = lerp(-200, 690, walkU), ky = 1010;
    const phoneP = [kx + 70, ky - 225];
    const cz = 1.0 + .06 * E.io2(lt / dur);
    const tx0 = lerp(W / 2, phoneP[0], push), ty0 = lerp(H / 2, phoneP[1], push);
    save(); cam(tx0, ty0, cz * lerp(1, 26, push));
    flood('blue', 1);
    // brick courses: black mortar lines, staggered, hand-cut
    for (let r = 0; r < 20; r++) {
      const y = -60 + r * 62;
      paint(P([[-400, y], [2400, y]], false), 'black', { stroke: 3 });
      for (let c = 0; c < 22; c++) { const x = -300 + c * 130 + (r % 2) * 65 + jit(r * 40 + c, 1.5); paint(P([[x, y], [x, y + 62]], false), 'black', { stroke: 3 }); }
    }
    // the pavement
    paint(P(cut(rect(-400, 1010, 2800, 300), 2001, 1.5)), 'black');
    // lamp light: a cone from the lamp head top-right, paper where it's brightest
    const lamp = [1330, 150];
    if (lampOn > 0) {
      const cone = [[lamp[0] - 30, lamp[1] + 20], [lamp[0] + 30, lamp[1] + 20], [lamp[0] + 520, 1100], [lamp[0] - 900, 1100]];
      knock(P(cone), ['blue', 'black'], radial(lamp[0], lamp[1], 30, 1100, .78 * lampOn, 1.25));
      ink(P(cone), { yellow: radial(lamp[0], lamp[1], 20, 700, .45 * lampOn, 1.4) });
    }
    // the lamp post and head
    paint(P(cut(rect(1620, 60, 26, 1000), 2002)), 'black');
    paint(P(ribbon([[1633, 90], [1580, 70], [1450, 100], [1370, 140]], 18, 14, 2003)), 'black');
    paint(P(cut(blob([[lamp[0] - 70, lamp[1] + 20], [lamp[0] - 40, lamp[1] - 30], [lamp[0] + 40, lamp[1] - 30], [lamp[0] + 70, lamp[1] + 20]], 4), 2004)), 'black');
    if (lampOn > 0) knock(P(ellipse(lamp[0], lamp[1] + 22, 58, 12)), null);
    // the poster: one plain ad (the bakery's loaf), pasted on the bricks, a corner lifting in the wet
    const px = 840, py = 330, pw = 360, ph = 480;
    const lift = .03 * Math.sin(lt * 2.1);
    knock(P(cut([[px, py], [px + pw, py], [px + pw + 6, py + ph - 60], [px + pw - 30 + lift * 400, py + ph], [px, py + ph]], 2005, 1.2)), null);
    paint(P(cut(rect(px + 22, py + 22, pw - 44, ph - 44), 2006, .8)), { pink: 1 }, { stroke: 10 });
    paint(P(cut(circle(px + pw / 2, py + 190, 100, 40), 2007)), { yellow: 1 });                                  // a sun
    for (let i = 0; i < 10; i++) { const a = i / 10 * TAU + lt * .3; paint(P([[px + pw / 2 + Math.cos(a) * 118, py + 190 + Math.sin(a) * 118], [px + pw / 2 + Math.cos(a) * 140, py + 190 + Math.sin(a) * 140]], false), { yellow: 1 }, { stroke: 7 }); }
    paint(P(cut(ellipse(px + pw / 2, py + 340, 120, 38, -.08), 2008)), { yellow: 1, pink: .0 });                 // the loaf
    paint(P(cut(ellipse(px + pw / 2, py + 340, 120, 38, -.08), 2008)), { yellow: 1, pink: 1 }, { stroke: 5 });
    for (let k = -2; k <= 2; k++) knock(P([[px + pw / 2 + k * 42 - 10, py + 322], [px + pw / 2 + k * 42 + 12, py + 356]], false), ['yellow'], 1, { stroke: 5 });
    // the kid: walks in, stops, looks up at the poster (head back), phone held low; the rain on her
    const stopped = t > 64.0;
    const lookUp = E.back(seg(t, 63.9, 64.3));
    figure(CAST.kid, kx, ky, 1.25, {
      walk: stopped ? undefined : t * 1.7, lF: stopped ? [.05, 0] : undefined, lN: stopped ? [-.05, 0] : undefined,
      aF: stopped ? [-.15, .25] : undefined, aN: [.9 + .1 * lookUp, -1.5],
      head: -.55 * lookUp, look: [.3, -1 * lookUp], eyes: t > 64.7 ? 'happy' : 'dot', seed: 20,
      hold: (p, a) => { save(); translate(p[0], p[1]); rotate(-.2); paint(P(rrect(-4, -58, 40, 64, 6)), 'black'); knock(P(rrect(0, -54, 32, 52, 4)), null); ink(P(rrect(0, -54, 32, 52, 4)), { yellow: .35 }); restore(); },
    });
    // the heart rises from her on "ads" (64.66)
    const hu = seg(t, 64.6, 65.6);
    if (hu > 0) {
      const hs = 22 * E.back2(clamp(hu * 4)), hx = kx + 40 + Math.sin(hu * 9) * 14, hy = ky - 330 - hu * 190;
      paint(P(cut(heartPts(hx, hy, hs), 2009, .5)), { pink: 1 });
    }
    rain(t, 110, -200, -100, 2300, 1250, 3, ['blue']);
    restore();
    // out: the glass of her phone fills the frame (S21 finds the gears behind it)
    if (push > .6) knock(P(rect(0, 0, W, H)), ['black'], clamp((push - .6) / .4) > .5 ? 0 : 0);
    return { lyric: { slot: 'uc', y: 130, font: 'serif', wdth: null, wght: null, size: 112, lh: 1.02, ink: 'knock', accentInk: 'pink', maxW: 1500 },
      print: lampOn === 0 && t < 62.4 ? {} : {} };
  }

  // ---------------------------------------------------------------- 22 · so here's one! (here's one!)
  // Reads: (1) risers (half-gears) rise from below carrying the cast (67.56–68.0); (2) on "one!" (68.20) everyone sings,
  // arms up, a pink sunburst behind; (3) on "(here's one!)" (68.74) a second burst, a bounce, the stamp.
  function s22_choir(t, lt, dur) {
    const b1 = pulse(t, 5, 99, (68.20 - OFFSET) / BEAT), b2 = t > 68.74 ? Math.exp(-(t - 68.74) * 5) : 0;
    const z = 1 + .05 * E.io2(lt / dur) + .03 * (b1 * (t > 68.2 ? 1 : 0) + b2);
    save(); cam(W / 2, H / 2 + 20, z);
    flood('blue', 1);
    // the sunburst: Saul Bass rays, pink, turning; bursts brighter (paper centre) on the two hits
    const hit = (t > 68.2 ? Math.exp(-(t - 68.2) * 4) : 0) + b2;
    const burst = E.out5(seg(t, 68.18, 68.4));
    if (burst > 0) {
      const cx = W / 2, cy = 760, n = 18, rr = 2400 * burst;
      for (let i = 0; i < n; i++) {
        const a0 = i / n * TAU + lt * .25, a1 = a0 + TAU / n * .5;
        paint(P([[cx, cy], [cx + Math.cos(a0) * rr, cy + Math.sin(a0) * rr], [cx + Math.cos(a1) * rr, cy + Math.sin(a1) * rr]]), { pink: 1 });
      }
      knock(P(circle(cx, cy, 700)), null, radial(cx, cy, 60, 520 + 200 * hit, .9 * (.6 + .4 * Math.min(1, hit)), 1.3));
    }
    // risers: black half-gears (the machine's gears, now a choir stand), rising staggered from below
    const cast = [[CAST.newsboy, 1.25, 1], [CAST.dad, 1.0, 1], [CAST.kid, 1.45, 1], [CAST.grandma, 1.05, -1], [CAST.baker, 1.05, -1]];
    cast.forEach(([ch, s, f], i) => {
      const x = 260 + i * 350, rise = E.back(seg(t, 67.5 + [.1, .05, 0, .07, .12][i], 67.95 + [.1, .05, 0, .07, .12][i]));
      const gy = lerp(1400, 900 - [40, 80, 120, 80, 40][i], rise);
      // gear stand
      const R = 180, teeth = 12;
      const pts = [];
      for (let k = 0; k <= teeth * 4; k++) { const a = Math.PI + k / (teeth * 4) * Math.PI, rr = R + ((k % 4) < 2 ? 22 : 0); pts.push([x + Math.cos(a) * rr, gy + Math.sin(a) * rr + R * .15]); }
      paint(P(cut([...pts, [x + R, 1300], [x - R, 1300]], 2200 + i, 1)), 'black');
      knock(P(circle(x, gy + R * .15, 26)), ['black']);
      // the singer, landing with a squash, singing on the hits
      const land = t > 67.95 ? wobble(t, 67.98 + i * .04, 3, 7) * .12 : 0;
      const sing = t < 68.18 ? .15 : .55 + .45 * Math.max(Math.exp(-(t - 68.2) * 3), b2);
      const arms = E.back(seg(t, 68.1 + i * .02, 68.3 + i * .02));
      const arms2 = b2 > 0 ? .25 * b2 : 0;
      figure(ch, x, gy - R + 8 + (b2 > 0 ? -18 * b2 : 0), s, {
        face: f, sq: land, mouth: sing, eyes: t > 68.18 ? (i % 2 ? 'happy' : 'closed') : 'dot', head: -.2 * arms,
        aN: [lerp(.2, 2.6 + arms2, arms), lerp(.3, -.4, arms)], aF: [lerp(-.2, 2.3 + arms2, arms), lerp(.3, -.3, arms)], seed: 50 + i * 9,
      });
    });
    restore();
    return { lyric: { slot: 'uc', y: 110, size: 104, ink: 'knock', accentInk: 'yellow', stamp: 'yellow', stampX: 1230, stampY: 330 } };
  }

  SHOT_FN['12'] = s12_procession;
  SHOT_FN['20'] = s20_poster;
  SHOT_FN['22'] = s22_choir;
})();
