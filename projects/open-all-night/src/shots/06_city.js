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
  // where the kid's phone screen is (world coords) in her stopped pose: measured once with a dry-run draw
  let _kp = null;
  function kidPhone(S, ky) {
    if (_kp) return _kp;
    save(); resetT();
    figure(CAST.kid, 610, ky, S, { aF: [-.15, .25], aN: [1.1, -1.5], lF: [.05, 0], lN: [-.05, 0], seed: 20,
      hold: (p) => { save(); translate(p[0], p[1]); rotate(-.2); _kp = toScreen(16, -26); restore(); } });
    restore(); risoClear();
    return _kp;
  }
  function s20_poster(t, lt, dur) {
    // the lamp buzzes on out of the black (the breakdown's first beat)
    const lampOn = t < 62.14 ? 0 : t < 62.19 ? 1 : t < 62.27 ? 0 : t < 62.33 ? .7 : t < 62.40 ? 0 : 1;
    const push = E.inExpo(seg(t, 64.98, 65.60));
    const walkU = E.out3(seg(t, 62.45, 64.0));
    const S = 1.6, kx = lerp(-220, 610, walkU), ky = 1015;
    const phoneP = kidPhone(S, ky);                                            // measured from the rig (her pose is fixed once she stops)
    const cz = 1.0 + .05 * E.io2(lt / dur);
    // zoom to a point: the phone's screen position glides to centre while the zoom grows
    const Z = cz * lerp(1, 70, push), u = E.io2(push);
    const s0 = [W / 2 + (phoneP[0] - W / 2) * cz, H / 2 + (phoneP[1] - H / 2) * cz], sp = [lerp(s0[0], W / 2, u), lerp(s0[1], H / 2, u)];
    save(); cam(phoneP[0] - (sp[0] - W / 2) / Z, phoneP[1] - (sp[1] - H / 2) / Z, Z);
    flood('blue', 1);
    const lamp = [1500, 250];
    const cone = [[lamp[0] - 34, lamp[1] + 22], [lamp[0] + 34, lamp[1] + 22], [lamp[0] + 560, 1100], [lamp[0] - 1100, 1100]];
    // bricks show only where the lamp light falls (light reveals texture; the dark keeps the type clean)
    if (lampOn > 0) {
      save(); for (const k of RISO.inks) k.ctx.clip(P(cone));
      for (let r = 0; r < 18; r++) {
        const y = 200 + r * 58;
        paint(P([[-400, y], [2400, y]], false), 'black', { stroke: 3 });
        for (let c = 0; c < 24; c++) { const x = -300 + c * 124 + (r % 2) * 62 + jit(r * 40 + c, 1.5); paint(P([[x, y], [x, y + 58]], false), 'black', { stroke: 3 }); }
      }
      restore();
      knock(P(cone), ['blue', 'black'], radial(lamp[0], lamp[1], 30, 1150, .8 * lampOn, 1.2));
      ink(P(cone), { yellow: radial(lamp[0], lamp[1], 20, 760, .45 * lampOn, 1.4) });
    }
    paint(P(cut(rect(-400, 1015, 2800, 300), 2001, 1.5)), 'black');            // pavement
    paint(P(cut(rect(1760, 150, 28, 900), 2002)), 'black');                    // post
    paint(P(ribbon([[1774, 180], [1720, 160], [1600, 190], [1530, 230]], 18, 14, 2003)), 'black');
    paint(P(cut(blob([[lamp[0] - 72, lamp[1] + 22], [lamp[0] - 42, lamp[1] - 30], [lamp[0] + 42, lamp[1] - 30], [lamp[0] + 72, lamp[1] + 22]], 4), 2004)), 'black');
    if (lampOn > 0) knock(P(ellipse(lamp[0], lamp[1] + 24, 60, 12)), null);
    // the poster: one plain ad (the bakery's sun-and-loaf), pasted on the bricks, a corner lifting in the wet
    const px = 900, py = 400, pw = 360, ph = 480, lift = Math.sin(lt * 2.1) * 12;
    knock(P(cut([[px, py], [px + pw, py], [px + pw + 6, py + ph - 60], [px + pw - 30 + lift, py + ph], [px, py + ph]], 2005, 1.2)), null);
    paint(P(cut(rect(px + 22, py + 22, pw - 44, ph - 44), 2006, .8)), { pink: 1 }, { stroke: 10 });
    paint(P(cut(circle(px + pw / 2, py + 190, 100, 40), 2007)), { yellow: 1 });
    for (let i = 0; i < 10; i++) { const a = i / 10 * TAU + lt * .3; paint(P([[px + pw / 2 + Math.cos(a) * 118, py + 190 + Math.sin(a) * 118], [px + pw / 2 + Math.cos(a) * 140, py + 190 + Math.sin(a) * 140]], false), { yellow: 1 }, { stroke: 7 }); }
    const loaf = P(cut(ellipse(px + pw / 2, py + 340, 120, 38, -.08), 2008));
    paint(loaf, { yellow: 1 }); ink(loaf, { pink: 1 }, { stroke: 5 });
    for (let k = -2; k <= 2; k++) knock(P([[px + pw / 2 + k * 42 - 10, py + 322], [px + pw / 2 + k * 42 + 12, py + 356]], false), ['yellow'], 1, { stroke: 5 });
    // the kid: walks in, stops, looks up at the poster, phone low in her hand
    const stopped = t > 64.0, lookUp = E.back(seg(t, 63.9, 64.3));
    figure(CAST.kid, kx, ky, S, {
      walk: stopped ? undefined : t * 1.7, lF: stopped ? [.05, 0] : undefined, lN: stopped ? [-.05, 0] : undefined,
      aF: stopped ? [-.15, .25] : undefined, aN: [1.1, -1.5],
      head: -.5 * lookUp, look: [.3, -1 * lookUp], eyes: t > 64.75 ? 'happy' : 'dot', seed: 20,
      hold: (p) => { save(); translate(p[0], p[1]); rotate(-.2); paint(P(rrect(-4, -58, 40, 64, 6)), 'black'); knock(P(rrect(0, -54, 32, 52, 4)), null); restore(); },
    });
    // the heart rises from her on "ads"
    const hu = seg(t, 64.7, 65.6);
    if (hu > 0) paint(P(cut(heartPts(kx + 40 + Math.sin(hu * 9) * 16, ky - 420 - hu * 200, 36 * E.back2(clamp(hu * 4))), 2009, .5)), { pink: 1 });
    rain(t, 120, -200, -100, 2300, 1250, 3, ['blue']);
    if (lampOn === 0 && t < 62.45) flood('black', 1);                         // before the lamp: the dark
    restore();
    // out: into the glass: the screen's paper fills the frame
    const g = t > 65.52 ? 1 : 0;
    if (g > 0) knock(P(rect(0, 0, W, H)), null, g);
    return { lyric: t < 62.6 ? false : { slot: 'uc', y: 150, font: 'serif', wdth: null, wght: null, size: 120, lh: 1.0, ink: 'knock', accentInk: 'knock', maxW: 1080 } };
  }

  // ---------------------------------------------------------------- 22 · so here's one! (here's one!)
  // Reads: (1) risers (half-gears) rise from below carrying the cast (67.56–68.0); (2) on "one!" (68.20) everyone sings,
  // arms up, a pink sunburst behind; (3) on "(here's one!)" (68.74) a second burst, a bounce, the stamp.
  function s22_choir(t, lt, dur) {
    const b2 = t > 68.74 ? Math.exp(-(t - 68.74) * 5) : 0;
    const hit1 = t > 68.2 ? Math.exp(-(t - 68.2) * 5) : 0;
    const z = 1.03 + .04 * E.io2(lt / dur) + .025 * (hit1 + b2);
    save(); cam(W / 2, H / 2 + 10, z);
    flood('blue', 1);
    // a paper spotlight grows behind the choir as they rise; on "one!" it bursts into pink Saul Bass rays
    const cx = W / 2, cy = 700;
    const spot = E.out3(seg(t, 67.56, 68.05));
    const burst = E.out5(seg(t, 68.17, 68.38));
    const rr = 2600 * burst;
    if (burst > 0) knock(P(circle(cx, cy, rr)), ['blue']);
    knock(P(cut(circle(cx, cy, 120 + 430 * spot + 60 * (hit1 + b2), 72), 2210, 2)), ["blue"]);
    if (burst > 0) {
      const n = 20;
      for (let i = 0; i < n; i++) {
        const a0 = i / n * TAU + lt * .22, a1 = a0 + TAU / n * .5;
        paint(P([[cx, cy], [cx + Math.cos(a0) * rr, cy + Math.sin(a0) * rr], [cx + Math.cos(a1) * rr, cy + Math.sin(a1) * rr]]), { pink: 1 });
      }
      knock(P(circle(cx, cy, 620)), ['pink'], radial(cx, cy, 80, 560 + 160 * (hit1 + b2), 1, 1.1));
    }
    // risers: black half-gears rising staggered from below; the cast lands on them and sings
    const cast = [[CAST.newsboy, 1.75, 1], [CAST.dad, 1.3, 1], [CAST.kid, 2.0, 1], [CAST.grandma, 1.45, -1], [CAST.baker, 1.35, -1]];
    // arm choreography per singer: [near, far] targets on "one!" (varied, never twins), and an extra lift on "(here's one!)"
    const armsOn = [[[2.9, -.2], [.3, .2]], [[2.5, -.5], [2.7, -.3]], [[3.0, -.1], [2.6, -.2]], [[1.6, -1.9], [.6, -.8]], [[2.2, -.9], [2.8, -.2]]];
    cast.forEach(([ch, s, f], i) => {
      const x = 250 + i * 355, d = [.1, .05, 0, .07, .12][i];
      const rise = E.back(seg(t, 67.52 + d, 67.92 + d));
      const R = 120, top = [880, 860, 830, 860, 880][i];
      const gy = lerp(1400, top + R, rise);
      const pts = [];
      for (let k = 0; k <= 40; k++) { const a = Math.PI + k / 40 * Math.PI, r2 = R + ((k % 4) < 2 ? 18 : 0); pts.push([x + Math.cos(a) * r2, gy + Math.sin(a) * r2]); }
      paint(P(cut([...pts, [x + R, 1400], [x - R, 1400]], 2200 + i, 1)), 'black');
      knock(P(circle(x, gy, 20)), ['black']);
      const land = wobble(t, 67.92 + d, 3, 7) * .14;
      const sing = t < 68.17 ? .12 : .5 + .5 * Math.max(Math.exp(-(t - 68.2) * 2.5), b2);
      const up = E.back(seg(t, 68.08 + i * .03, 68.3 + i * .03)), [aN1, aF1] = armsOn[i];
      const lift = b2 * .25;
      figure(ch, x, gy - R - 14 - 22 * b2 * (i % 2 ? 1 : .6), s, {
        face: f, sq: land, mouth: sing, eyes: t > 68.17 ? (i % 2 ? 'happy' : 'closed') : 'dot', head: -.22 * up - .05 * b2,
        aN: [lerp(.15, aN1[0] + lift, up), lerp(.25, aN1[1], up)], aF: [lerp(-.15, aF1[0] + lift * .5, up), lerp(.25, aF1[1], up)], seed: 50 + i * 9,
      });
    });
    restore();
    return { lyric: { slot: 'uc', y: 120, size: 104, ink: t < 68.2 ? 'knock' : 'black', accentInk: 'pink', stamp: 'black', stampX: 1260, stampY: 290 } };
  }

  // ---------------------------------------------------------------- 23 · Everybody sing it back!
  // Reads: (1) a wall of lit windows, a singer in every one, mouths on the beat (69.52–70.2); (2) the camera pulls back:
  // the whole city is singing (70.2–71.1); (3) light floods the frame to paper white (71.1–71.72) -> the sunrise hook.
  const CITY23 = (() => {           // building list: [x, width, floors, cols, seed]
    const out = [], R = rng(23);
    let x = -2600;
    while (x < 4600) { const w = 380 + R() * 360, fl = 5 + Math.floor(R() * 7), cols = Math.max(3, Math.round(w / 120)); out.push([x, w, fl, cols, out.length]); x += w + 30 + R() * 60; }
    return out;
  })();
  function s23_city(t, lt, dur) {
    const u = E.io3(seg(t, 69.62, 71.25));
    const Z = Math.exp(lerp(Math.log(3.1), Math.log(.46), u));
    save(); cam(960 + 40 * u, lerp(470, 280, u), Z);
    nightSky({ stars: 140, w: 8000, ox: 3000, h: 3000, oy: 1800, seed: 23 });
    const ground = 1000, fh = 96;
    for (const [bx, bw, fl, cols, sd] of CITY23) {
      const top = ground - fl * fh - 40;
      const vis = toScreen(bx, top), vis2 = toScreen(bx + bw, ground);
      if (vis2[0] < -50 || vis[0] > W + 50) continue;
      paint(P(cut(rect(bx, top, bw, ground - top + 400), 2300 + sd, 1.2, .5)), 'black');
      const cw = bw / cols;
      for (let f = 0; f < fl; f++) for (let c = 0; c < cols; c++) {
        const wx = bx + c * cw + cw * .18, wy = top + 40 + f * fh + 14, ww = cw * .64, wh = fh * .66;
        const sp = toScreen(wx, wy); if (sp[0] < -100 || sp[0] > W + 100 || sp[1] < -100 || sp[1] > H + 100) continue;
        const id = sd * 131 + f * 17 + c;
        if (hash(id) < .12) continue;                                               // a few dark windows
        paint(P(rect(wx, wy, ww, wh)), { yellow: 1 });
        const px = ww * Z;                                                           // level of detail by screen size
        const bob = Math.sin((beatPos(t) + hash(id + 5)) * Math.PI) * 3;
        if (px > 34) {
          const hs = ww / 125, open = .35 + .65 * pulse(t, 5, 1, hash(id) * .5), sInk = hash(id + 9) > .5 ? { pink: 1 } : { blue: 1 };
          save(); for (const k of RISO.inks) { k.ctx.save(); k.ctx.clip(P(rect(wx, wy, ww, wh))); }
          head(CAST.anon, wx + ww * (.4 + .2 * hash(id + 1)), wy + wh * .56 + bob, hs, { var: Math.floor(hash(id + 2) * 5), face: hash(id + 3) > .5 ? 1 : -1, ink: sInk, mouth: open, eyes: hash(id + 4) > .5 ? 'closed' : 'happy', head: -.25 - .1 * open, seed: id % 97 });
          paint(P(rrect(wx + ww * .18, wy + wh * .86, ww * .64, wh * .3, ww * .1)), sInk);   // shoulders
          for (const k of RISO.inks) k.ctx.restore(); restore();
        } else if (px > 7) {
          const hx = wx + ww * (.38 + .24 * hash(id + 1)), hy = wy + wh * .55 + bob;
          const sI = hash(id + 9) > .5 ? { pink: 1 } : { blue: 1 };
          paint(P(circle(hx, hy, wh * .2, 10)), sI);
          paint(P(rect(hx - wh * .3, hy + wh * .2, wh * .6, wh * .3)), sI);
        }
      }
    }
    paint(P(rect(-4000, ground, 12000, 2000)), 'black');
    restore();
    // out: the song's riser: light swells from the centre to paper white by the downbeat
    const wo = E.in3(seg(t, 71.0, 71.66));
    if (wo > 0) { const r = 40 + wo * 2400; knock(P(circle(W / 2, H / 2, r + 300)), null, radial(W / 2, H / 2, r, r + 300, 1, .7)); knock(P(circle(W / 2, H / 2, r, 64)), null); }
    return { lyric: { slot: 'uc', y: 150, size: 112, ink: 'knock', accentInk: 'knock' } };
  }

  // ---------------------------------------------------------------- 25 · Every window, every door, every kid gets a light! (sunrise)
  // Reads: (1) close on a blue facade against a yellow sunrise; windows light in a wave on "window" (75.32);
  // (2) pull back: doors along the street open in a wave on "door" (76.40); (3) the street is a crowd of thousands,
  // their lights igniting left to right on "every kid gets a light" (76.84–78.46); a pink sun rising behind it all.
  const CITY25 = (() => { const out = [], R = rng(25); let x = -3200; while (x < 5200) { const w = 300 + R() * 420, fl = 4 + Math.floor(R() * 6); out.push([x, w, fl, Math.max(3, Math.round(w / 110)), out.length]); x += w + 20 + R() * 50; } return out; })();
  const FAR25 = (() => { const out = [], R = rng(52); let x = -4200; while (x < 6200) { const w = 200 + R() * 380, h = 300 + R() * 700; out.push([x, w, h]); x += w + R() * 30; } return out; })();
  function s25_skyline(t, lt, dur) {
    const u = E.io3(seg(t, 75.5, 78.6));
    const Z = Math.exp(lerp(Math.log(2.3), Math.log(.74), u)), cy = lerp(390, 720, u), cx = 960 + 120 * u;
    const ground = 1000;
    // sky: yellow; the sun: a pink disc with paper stripes across its lower half, rising
    flood('yellow', 1);
    const layerCam = (par) => { save(); cam(cx * par + 960 * (1 - par), cy * par + 540 * (1 - par), 1 + (Z - 1) * par); };
    layerCam(.35);
    const sunY = 760 - 90 * E.out2(lt / dur), sunR = 420;
    paint(P(cut(circle(960, sunY, sunR, 96), 2501, 2)), { pink: 1 });
    for (let k = 0; k < 7; k++) { const y = sunY + 40 + k * 46, hgt = 6 + k * 4.5; knock(P(rect(960 - sunR - 20, y, sunR * 2 + 40, hgt)), ['pink']); }
    restore();
    // far skyline: pink cut paper (haze), a little parallax
    layerCam(.6);
    for (const [x, w, h] of FAR25) paint(P(cut(rect(x, ground - h + 120, w, h + 400), 2502 + x, 1.5)), { pink: 1, yellow: 1 });
    restore();
    // near skyline: blue blocks; windows wake in a wave (paper), doors along the street open in a second wave
    layerCam(1);
    for (const [bx, bw, fl, cols, sd] of CITY25) {
      const fh = 78, top = ground - fl * fh - 40;
      const a = toScreen(bx, top), b = toScreen(bx + bw, ground); if (b[0] < -40 || a[0] > W + 40) continue;
      paint(P(cut(rect(bx, top, bw, ground - top + 60), 2550 + sd, 1.2, .5)), { blue: 1 });
      const cw = bw / cols;
      for (let f = 0; f < fl; f++) for (let c = 0; c < cols; c++) {
        const wx = bx + c * cw + cw * .24, wy = top + 36 + f * fh + 10, ww = cw * .52, wh = fh * .58;
        const sx = toScreen(wx, wy)[0], L = skyWave(t, 75.2, sx + hash(sd * 7 + f * 3 + c) * 260);
        if (L > 0) knock(P(rect(wx, wy, ww * L + ww * (1 - L) * .0, wh)), ['blue']);
        else paint(P(rect(wx, wy, ww, wh)), { blue: 1, black: 1 });
      }
      // a door
      const dx = bx + bw * .4, dw = Math.min(96, bw * .24), open = skyWave(t, 76.35, toScreen(dx, 0)[0]);
      paint(P(rect(dx, ground - 160, dw, 160)), { blue: 1, black: 1 });
      if (open > 0) { knock(P(rect(dx, ground - 160, dw, 160)), null); paint(P(rect(dx, ground - 160, dw * (1 - .85 * Math.min(1, E.back(open))), 160)), { pink: 1 }); }
    }
    // the street: a crowd of thousands, their lights igniting left to right
    paint(P(rect(-6000, ground, 14000, 1400)), { pink: 1 });
    for (let row = 0; row < 4; row++) {
      const y = ground + 80 + row * 105, n = 150 - row * 22, s = 1.9 + row * .7;
      for (let i = 0; i < n; i++) {
        const x = -3300 + (i + hash(row * 7 + i) * .8) * (8600 / n) + (row % 2) * 12;
        const sp = toScreen(x, y); if (sp[0] < -60 || sp[0] > W + 60 || sp[1] > H + 80) continue;
        const L = skyWave(t, 76.84, sp[0] + hash(i * 3 + row) * 180, 1100);
        const hb = Math.sin((beatPos(t) * 2 + hash(i + row * 50)) * Math.PI) * 2 * s;
        const hr = 9 * s, hy = y - 24 * s + hb;
        paint(P(circle(x, hy, hr, 10)), 'black');
        paint(P(rrect(x - hr * 1.5, hy + hr * .7, hr * 3, hr * 3, hr * .8, 3)), 'black');
        if (L > 0) {
          const lx = x + (hash(i + row) > .5 ? 1 : -1) * hr * 1.1, ly = hy - hr * 2.4 * E.back(L);
          paint(P([[x, hy + hr], [lx, ly]], false), 'black', { stroke: hr * .45 });
          knock(P(circle(lx, ly, hr * 2.6)), ['pink', 'yellow'], radial(lx, ly, hr * .5, hr * 2.6, .6 * L, 1.5));
          ink(P(circle(lx, ly, hr * 2)), { yellow: radial(lx, ly, hr * .4, hr * 2, .5 * L, 1.5) });
          paint(P(rrect(lx - hr * .6, ly - hr * .95, hr * 1.2, hr * 1.9, hr * .2, 3)), 'black');
          knock(P(rect(lx - hr * .42, ly - hr * .76, hr * .84, hr * 1.4 * Math.min(1, L * 1.5))), null);
        }
      }
    }
    restore();
    return { lyric: { slot: 'uc', y: 140, size: 80, ink: 'black', accentInk: 'pink', maxW: 1800 } };
  }

  // ---------------------------------------------------------------- 28 · keep it open, keep it open all night!
  // Reads: (1) the kid's building, an OPEN sign blinking on in every window (83.78–84.6); (2) pull back: every building in
  // the city has them, a second wave on the second "keep it open" (85.7–86.3); (3) "all night!": everything flares; flash (86.94).
  const CITY28 = (() => { const out = [], R = rng(28); let x = -5200; while (x < 7200) { const w = 360 + R() * 380, fl = 5 + Math.floor(R() * 8); if (x < -300 || x > 1500) out.push([x, w, fl, Math.max(3, Math.round(w / 120)), out.length]); x += w + 40 + R() * 70; } return out; })();
  function miniSign(x, y, w, h, on) {
    if (on <= 0) return;                                                   // dark glass
    const pw = w * .82, ph = h * .5, cx = x + w / 2, cy = y + h / 2;
    knock(P(circle(cx, cy, w * .9)), ['blue'], radial(cx, cy, w * .3, w * .9, .6 * on, 1.5));
    paint(P(rrect(cx - pw / 2, cy - ph / 2, pw, ph, ph * .3)), { pink: 1 });
    if (w * RISO.inks[0].ctx.getTransform().a > 22) knock(P(rect(cx - pw * .3, cy - ph * .1, pw * .6, ph * .2)), ['pink']);   // a hint of the word
  }
  // a lit OPEN panel for a window seen up close: a solid pink sign with the word knocked out in paper
  function windowSign(x, y, w, h) {
    const cx = x + w / 2, cy = y + h / 2, pw = w * .88, ph = h * .6;
    paint(P(cut(rrect(cx - pw / 2, cy - ph / 2, pw, ph, ph * .28), (x * 7 + y) % 97, .6, .3)), { pink: 1 });
    const L = fitShape('OPEN', pw * .74, { font: 'arch', size: ph * .6, wdth: 90, wght: 800, track: .03 });
    drawText(L, cx, cy + L.cap / 2, null, { align: 'center', knock: true, knockInks: ['pink'] });
  }
  function s28_signs(t, lt, dur) {
    const u = E.io3(seg(t, 84.35, 86.8));
    const Z = Math.exp(lerp(Math.log(1.25), Math.log(.22), u)) * (1 + .05 * pulse(t, 6, 1));
    const [kx, ky] = [BLDG.x + BLDG.w / 2, 380];
    save(); cam(lerp(kx, 960, u * .4), lerp(ky, -480, u), Z);
    nightSky({ stars: 160, w: 16000, ox: 7000, h: 7000, oy: 5500, seed: 28 });
    // the neighbours, far and near: black blocks, a mini OPEN sign in every window, waves of switching on
    const wave2 = (x) => clamp((t - 85.7 - Math.abs(x - kx) / 5200) / .1);
    for (const [bx, bw, fl, cols, sd] of CITY28) {
      const fh = 150, top = 1080 - 260 - fl * fh;
      paint(P(cut(rect(bx, top, bw, 1400), 2800 + sd, 2)), 'black');
      const cw = bw / cols;
      for (let f = 0; f < fl; f++) for (let c = 0; c < cols; c++) {
        const wx = bx + c * cw + cw * .2, wy = top + 30 + f * fh + 22, ww = cw * .6, wh = fh * .56;
        paint(P(rect(wx, wy, ww, wh)), { blue: 1 });                           // dark glass
        const on = wave2(wx + hash(sd + f * 3 + c) * 900) * (t > 86.72 ? 1 : .9);
        miniSign(wx, wy, ww, wh, on);
      }
    }
    // the kid's building: its OPEN signs switch on window by window on the first "keep it open"
    building({ sign: [1, 1, 1, 1], lit: () => 0, glow: false, inWindow: (f, c, x, y, w, h) => {
      const k = (7 - f) * 4 + ((f % 2) ? 3 - c : c), on = t > 83.7 + k * .022 ? 1 : 0;
      const flick = on && t < 83.7 + k * .022 + .06 ? 0 : on;
      if (w * Z > 70) { if (flick) windowSign(x, y, w, h); }
      else miniSign(x, y, w, h, flick);
    } });
    paint(P(rect(-9000, 1080, 20000, 3000)), 'black');
    restore();
    // "all night!": flare, then the flash on "night!" (86.94) decaying in halftone
    const fl = t >= 86.94 ? Math.max(0, 1 - (t - 86.94) / .3) : 0;
    if (fl > 0) knock(P(rect(0, 0, W, H)), null, t < 87.02 ? 1 : fl);
    return { lyric: { slot: 'uc', y: 150, size: 110, ink: 'knock', accentInk: 'knock', maxW: 1700 } };
  }

  SHOT_FN['23'] = s23_city;
  SHOT_FN['25'] = s25_skyline;
  SHOT_FN['28'] = s28_signs;
  SHOT_FN['12'] = s12_procession;
  SHOT_FN['20'] = s20_poster;
  SHOT_FN['22'] = s22_choir;
})();
