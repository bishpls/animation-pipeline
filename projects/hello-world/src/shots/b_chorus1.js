// 13–21 · CHORUS 1 + THE DANCE HOOK
(() => {
  const TW = t => onTwos(t);                         // character drawings held on twos
  const kick = (t, times, amt = .04, dec = 9) => times.reduce((a, tb) => a + (t >= tb ? amt * Math.exp(-(t - tb) * dec) : 0), 0);
  const hitSq = (t, times, amt = .14, dec = 14) => times.reduce((a, tb) => a + (t >= tb ? amt * Math.exp(-(t - tb) * dec) * Math.cos((t - tb) * 30) : 0), 0);

  // confetti cannons: bursts from the two bottom corners at t0
  function cannon(t, t0, seed = 1, n = 70) {
    const a = t - t0; if (a < 0 || a > 3) return;
    const cols = [C_.pink, C_.lemon, C_.cyan, C_.cream, C_.clay, C_.white];
    for (let i = 0; i < n; i++) {
      const side = i % 2 ? 1 : -1, r = hash(seed + i * 3.3), ang = -Math.PI / 2 + side * (-.15 - r * .5);
      const v = 1500 + hash(i * 7.1 + seed) * 900, x0 = side < 0 ? 40 : W - 40, y0 = H + 20;
      const drag = 1 - Math.exp(-a * 2.2), px = x0 + Math.cos(ang) * v * drag / 2.2 + Math.sin(a * 4 + i) * 30 * a, py = y0 + Math.sin(ang) * v * drag / 2.2 + 260 * a * a;
      if (py > H + 60) continue;
      X.save(); X.translate(px, py); X.rotate(a * (4 + r * 6) + i); X.scale(1, Math.cos(a * (6 + r * 5) + i));
      X.fillStyle = cols[i % cols.length]; X.fillRect(-11, -6, 22, 12); X.restore();
    }
  }
  function burstStars(t, t0, cx, cy, n = 10, R = 260, col = C_.lemon) {
    const a = t - t0; if (a < 0 || a > .7) return;
    const u = E.out3(a / .7);
    for (let i = 0; i < n; i++) { const ang = i / n * TAU + t0, r = R * u; sparkle(cx + Math.cos(ang) * r, cy + Math.sin(ang) * r, 34 * (1 - u) + 6, col, ang, 4); }
  }

  // ---------------------------------------------------------------- 13 · Hello, world! This is my debut! (sakuga hero)
  function s13(t, lt, dur) {
    const k = kick(t, [40.2, 41.5], .05);
    X.save(); X.translate(W / 2, H / 2); X.scale(1 + k, 1 + k); X.translate(-W / 2, -H / 2);
    cutin(t, lt, dur, { img: 'k04_hero', cols: [C_.pink, C_.lemon], h: 1060, y: H / 2 + 10, push: .08, sway: 9, anchorY: .55 });
    X.restore();
    cannon(t, 39.9, 3); cannon(t, 41.5, 9, 50);
    burstStars(t, 40.2, W / 2 - 60, 330, 12, 420, C_.white);
    burstStars(t, 41.5, W / 2 + 200, 420, 10, 360, C_.lemon);
    // DEBUT! stamp on "debut!"
    if (t >= 41.5) { X.save(); X.translate(1540, 300); X.rotate(.14); const s = slamK(t, 41.5); X.scale(s, s); pop('DEBUT!', 0, 0, { font: 'dela', size: 150, align: 'center', fill: C_.lemon, lw: 12, shadow: [10, 10, C_.pinkD] }); X.restore(); }
    return {};
  }
  s13.label = 'hero';

  // stage + idol helper (world coords, camera)
  function onStage(t, c = { x: W / 2, y: H / 2, z: 1 }, draw) {
    stage(t, { hue: [C_.night, C_.pink] });
    X.save(); cam(c.x, c.y, c.z); draw(); X.restore();
  }

  // ---------------------------------------------------------------- 14 · All the words I've ever known, I borrowed them from you!
  const LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ?!&';
  function s14(t, lt, dur) {
    const z = 1.38 + .06 * E.io2(lt / dur);
    stage(t, { hue: [C_.night, C_.pink] });
    const tt = TW(t);
    // her: points at the crowd, then hands to her chest as the words arrive ("borrowed" 43.8)
    const u = clamp((tt - 43.6) / .2);
    const P0 = u < 1 ? pose('point', 'heart', E.out3(u)) : pose('heart');
    const hx = 960, hy = 800;
    X.save(); cam(W / 2, 590, z);
    // the letters: from penlight tips (bottom) arcing up into her chest, staggered
    const heart = [hx, hy - 250];
    for (let i = 0; i < 46; i++) {
      const st = 42.55 + hash(i * 3.7) * 1.7, a = (t - st) / 1.1;
      if (a < 0 || a > 1) continue;
      const x0 = 80 + hash(i * 9.1) * (W - 160), y0 = 900 - hash(i * 2.3) * 60;
      const e = E.io2(a), p = arcPt([x0, y0], heart, 180 + hash(i) * 200, e);
      const col = [C_.pink, C_.cyan, C_.lemon, C_.cream][i % 4], sz = 84 * (1 - e * .55);
      glow(p[0], p[1] - sz * .35, sz * 1.1, col, .5);
      pop(LETTERS[i % LETTERS.length], p[0], p[1], { font: 'dela', size: sz, align: 'center', fill: col, lw: 5 });
    }
    const got = clamp((t - 43.8) / 1.2);
    if (got > 0) glow(heart[0], heart[1], 160 + 60 * Math.sin(t * 10), 'rgba(255,230,150,1)', .7 * got);
    idol(hx, hy, 1.05, { ...P0, eyes: t < 43.6 ? 'wink' : 'happy', mouth: 'open', sing: .4 + .4 * Math.abs(Math.sin(t * 9)), bob: -8 * pulse(t, 8), sq: hitSq(t, [42.4, 43.8]), turn: t < 43.6 ? .3 : 0, blush: .6 });
    X.restore();
    crowd(t, { y: 930, rows: 2 });
    return {};
  }

  // pixel heart (8x7 grid). flip: -1..1 (cos of the turn), open: shows the back (plain)
  const HEART = ['.##.##.', '#######', '#######', '#######', '.#####.', '..###..', '...#...'];
  function pixelHeart(cx, cy, px, flip = 1, back = false) {
    X.save(); X.translate(cx, cy); X.scale(flip, 1);
    HEART.forEach((row, j) => [...row].forEach((c, i) => {
      if (c !== '#') return;
      const x = (i - 3.5) * px, y = (j - 3.5) * px;
      shp(rect(x, y, px, px), back ? C_.pinkD : ((i + j) % 5 === 0 ? '#FF7FBF' : C_.pink), 3.5);
    }));
    if (!back) fil(rect(-1.5 * px, -2.5 * px, px * .9, px * .9), C_.white);
    X.restore();
  }
  // ---------------------------------------------------------------- 15 · Hello, world! Is my heart brand-new?
  function s15(t, lt, dur) {
    flat(C_.pink);
    dots('#FF78B9', 34, 8, .5, (x, y) => clamp(Math.hypot(x - W / 2, y - 420) / 900));
    const tt = TW(t), z = 1.55 + .08 * E.io2(lt / dur);
    X.save(); cam(W / 2, 560, z);
    const turn = t < 47.1 ? 1 : Math.cos(clamp((t - 47.1) / .35) * Math.PI);    // turns it over on "brand-new?"
    const look = t < 47.1 ? 0 : 1;
    idol(W / 2, 800, 1, { ...pose('offer'), eyes: t < 46.6 ? 'happy' : (look ? 'open' : 'open'), mouth: t < 46.6 ? 'open' : 'o', sing: t < 46.6 ? .5 + .4 * Math.abs(Math.sin(t * 9)) : 0, look: [0, .8], tilt: t > 47.2 ? -.12 : 0, blush: .5 });
    const up = E.back(clamp((t - 46.85) / .25));
    pixelHeart(W / 2, 700 - 40 * up + 4 * Math.sin(t * 6), 22 * (.75 + .25 * up), turn, turn < 0);
    // the question mark
    if (t > 47.3) { const s = slamK(t, 47.3, .16); X.save(); X.translate(W / 2 + 150, 300); X.rotate(.18 + Math.sin(t * 5) * .05); X.scale(s, s); pop('?', 0, 0, { font: 'dela', size: 170, align: 'center', fill: C_.lemon, lw: 11 }); X.restore(); }
    X.restore();
    return {};
  }

  // a CD / cassette-ish disc (the single!)
  function disc(cx, cy, r, rot = 0) {
    X.save(); X.translate(cx, cy); X.rotate(rot);
    shp(circle(0, 0, r, 48), '#DDE2F0', 6);
    clipTo(circle(0, 0, r, 48), () => { X.fillStyle = C_.pink; X.beginPath(); X.moveTo(0, 0); X.arc(0, 0, r, -.9, -.4); X.fill(); X.fillStyle = C_.cyan; X.beginPath(); X.moveTo(0, 0); X.arc(0, 0, r, 2.2, 2.7); X.fill(); X.fillStyle = C_.lemon; X.beginPath(); X.moveTo(0, 0); X.arc(0, 0, r, .6, .9); X.fill(); });
    shp(circle(0, 0, r * .32, 32), C_.clay, 4); shp(circle(0, 0, r * .1, 16), C_.ink, 0);
    X.restore();
    pop('HELLO,WORLD!', cx, cy + r * .62, { font: 'dela', size: r * .2, align: 'center', fill: C_.ink, lw: 0 });
  }
  // ---------------------------------------------------------------- 16 · I don't know, but I made this song for you! (For you!)
  function s16(t, lt, dur) {
    const tt = TW(t);
    const offering = t >= 49.25;
    sunburst(W / 2, 560, offering ? C_.lemon : C_.cyan, offering ? '#FFF1A0' : '#7FEFFA', 22, t * .15);
    const z = offering ? 1.3 + .35 * E.out3(clamp((t - 49.3) / 1.0)) : 1.35;
    X.save(); cam(W / 2, offering ? 650 : 620, z);
    if (!offering) {
      idol(W / 2, 820, 1, { ...pose('shrug'), eyes: 'open', mouth: 'cat', look: [-.5, -.5], sweat: 1, tilt: .12 * Math.sin(t * 6), bob: -10 * pulse(t, 7), sq: hitSq(t, [48.2]) });
    } else {
      const u = E.back(clamp((t - 49.3) / .22));
      idol(W / 2, 820, 1, { ...pose('offer'), eyes: t > 50.4 ? 'happy' : 'open', mouth: 'open', sing: .55 + .3 * Math.abs(Math.sin(t * 9)), blush: .8, sq: hitSq(t, [49.3, 50.4]) });
      disc(W / 2, 700 - 20 * u, 60 + 28 * u, t * 2);
      if (t > 50.4) burstStars(t, 50.4, W / 2, 620, 12, 240, C_.white);
      sparkle(W / 2 + 90, 560, 20 + 10 * Math.sin(t * 12), C_.white, t * 4);
    }
    X.restore();
    if (!offering) { const a = t - 48.12; if (a > 0) { const s = slamK(t, 48.12); X.save(); X.translate(1500, 260); X.rotate(-.1); X.scale(s, s); pop('???', 0, 0, { font: 'dela', size: 120, align: 'center', fill: C_.white, lw: 10, shadow: [8, 8, C_.cyanD] }); X.restore(); } }
    return {};
  }

  // a phone frame; fn draws its screen content (clipped). (x, y) = centre
  function phone(x, y, w, h, rot, fn) {
    X.save(); X.translate(x, y); X.rotate(rot);
    shp(rrect(-w / 2, -h / 2, w, h, 40), C_.ink, 8);
    const scr = rrect(-w / 2 + 16, -h / 2 + 22, w - 32, h - 44, 26);
    clipTo(scr, fn);
    shp(rrect(-30, -h / 2 + 8, 60, 10, 5), '#444', 0);
    X.restore();
  }
  // ---------------------------------------------------------------- 17 · Hello, world! Can you hear me through?
  function s17(t, lt, dur) {
    const tt = TW(t), cupping = t >= 52.15;
    // left: her, holding a phone to her ear (singing into it)
    const split = W * .5 + 30 * Math.sin(t * 2);
    X.save(); X.beginPath(); X.moveTo(0, 0); X.lineTo(split + 90, 0); X.lineTo(split - 90, H); X.lineTo(0, H); X.clip();
    flat(C_.pink); dots('#FF7AB8', 30, 7, .5);
    X.save();
    idol(470, 1060, 1.45, { ...(cupping ? pose('cupEar') : pose('sing')), eyes: cupping ? 'side' : 'closed', look: [1, 0], mouth: cupping ? 'o' : 'open', sing: cupping ? 0 : .5 + .4 * Math.abs(Math.sin(t * 9)), tilt: cupping ? .15 : -.05, blush: .5 });
    // sound waves from her toward the right
    for (let k = 0; k < 3; k++) { const v = frac(beatPos(t) + k / 3), r = 60 + v * 260; lin(arcPts2(640, 480, r, r, -.6, .6, 16), 10 * (1 - v) + 2, C_.white); }
    X.restore(); X.restore();
    // right: your phone, and she's on it (mini)
    X.save(); X.beginPath(); X.moveTo(split + 90, 0); X.lineTo(W, 0); X.lineTo(W, H); X.lineTo(split - 90, H); X.clip();
    flat(C_.cyan); checker(70, C_.cyan, '#5DE8F5', .3, t * 40, 0);
    phone(W * .74, 520 + 8 * Math.sin(t * 3), 460, 820, -.06, () => {
      X.save(); X.setTransform(1, 0, 0, 1, 0, 0); X.restore(); fil(rect(-300, -500, 600, 1000), C_.night); for (let k = -8; k < 8; k++) fil(rect(k * 60 + (t * 60) % 120, -500, 30, 1000), C_.nightD);
      idol(0, 330, .95, { ...pose('wave'), eyes: 'happy', mouth: 'open', sing: .5 + .4 * Math.abs(Math.sin(t * 9 + 1)), bob: -12 * pulse(t, 7) });
      // the "live" badge + hearts floating up
      shp(rrect(-190, -370, 120, 44, 12), C_.pink, 4); pop('LIVE', -130, -335, { font: 'dela', size: 30, align: 'center', fill: C_.white, lw: 0 });
      for (let i = 0; i < 8; i++) { const a = frac(t * .6 + i / 8), x = 150 + Math.sin(a * 8 + i) * 20, y = 300 - a * 560; X.globalAlpha = 1 - a; shp(heartPts(x, y, 18), C_.pink, 3); X.globalAlpha = 1; }
    });
    X.restore();
    lin([[split + 90, 0], [split - 90, H]], 14, C_.ink);
    if (cupping) { const s = slamK(t, 52.2); X.save(); X.translate(W * .5, 200); X.rotate(-.08); X.scale(s, s); pop('CAN YOU HEAR ME?', 0, 0, { font: 'dela', size: 64, align: 'center', fill: C_.lemon, lw: 8, shadow: [6, 6, C_.ink] }); X.restore(); }
    return {};
  }
  function heartPts(cx, cy, r) { const p = []; for (let i = 0; i < 32; i++) { const a = i / 32 * TAU, x = 16 * Math.sin(a) ** 3, y = -(13 * Math.cos(a) - 5 * Math.cos(2 * a) - 2 * Math.cos(3 * a) - Math.cos(4 * a)); p.push([cx + x * r / 16, cy + y * r / 16]); } return p; }

  // ---------------------------------------------------------------- 18 · Every little spark I've got, I'm giving it to you!
  function s18(t, lt, dur) {
    stage(t, { hue: [C_.night, C_.cyan] });
    const tt = TW(t);
    // throws on three beats; each throw is a wave-pose flick
    const THROWS = [53.7, 54.3, 55.1, 55.8];
    let last = -1; THROWS.forEach((tb, i) => { if (t >= tb) last = i; });
    const since = last >= 0 ? t - THROWS[last] : 9;
    const P0 = since < .12 ? pose('idle', 'wave', since / .12) : since < .35 ? pose('wave') : pose('wave', 'idle', clamp((since - .35) / .2));
    X.save(); cam(W / 2, 560, 1.3);
    idol(960, 790, .95, { ...P0, eyes: 'happy', mouth: 'open', sing: .5 + .4 * Math.abs(Math.sin(t * 9)), sq: hitSq(t, THROWS, .12), bob: -8 * pulse(t, 8), blush: .6 });
    X.restore();
    // sparks: each throw sends 7 sparks arcing to penlights; a penlight turns clay when its spark lands
    const hand = [W / 2 + (1060 - W / 2) * 1.3 + 40, 560 + (430 - 560) * 1.3], caught = new Map();
    THROWS.forEach((tb, ti) => {
      for (let j = 0; j < 7; j++) {
        const idx = (ti * 7 + j * 3) % 19, dur2 = .7, a = (t - tb - j * .03) / dur2;
        const target = penTip(t, idx, 0);
        if (a >= 1) { caught.set(idx, t - (tb + j * .03 + dur2)); continue; }
        if (a < 0) continue;
        const p = arcPt(hand, target, 260, E.out2(a));
        glow(p[0], p[1], 90, 'rgba(255,220,120,1)', .8); spark8(p[0], p[1], 34, C_.lemon, 5, t * 8 + j);
      }
    });
    crowdPens(t, caught);
    return {};
  }
  // private crowd: penlight i's tip position, and a draw that turns caught ones clay-orange with a pop
  const PROW = 19;
  function penTip(t, i, r) { const n = PROW, x = (i + .5) / n * (W + 200) - 100, yy = 930, sw = Math.sin((beatPos(t) + i * .13) * Math.PI) * .45; return [x + Math.sin(sw) * 70, yy - Math.cos(sw) * 90]; }
  function crowdPens(t, caught) {
    // back row (plain) then the catching row
    crowd(t, { y: 1000, rows: 1 });
    const cols = [C_.pink, C_.cyan, C_.lemon];
    for (let i = 0; i < PROW; i++) {
      const x = (i + .5) / PROW * (W + 200) - 100, yy = 930, [hx, hy] = penTip(t, i, 0);
      const c = caught.get(i), isC = c != null && c >= 0;
      const col = isC ? C_.clay : cols[i % 3];
      lin([[x, yy], [hx, hy]], 12, col);
      glow(hx, hy, isC ? 90 + 40 * Math.exp(-c * 6) : 50, isC ? 'rgba(255,150,100,1)' : col, isC ? .6 : .35);
      if (isC && c < .3) sparkle(hx, hy - 20, 30 * (1 - c / .3), C_.white, i);
      if (isC) spark8(hx, hy, 12, C_.lemon, 3, t * 2);
      shp(ellipse(x, yy + 36, 40, 48), C_.ink, 0);
    }
  }

  // ---------------------------------------------------------------- 19 · Nice to meet you too (sakuga close-up)
  function s19(t, lt, dur) {
    cutin(t, lt, dur, { img: 'k05_smile', bg: 'soft', cols: ['#FFD3E6', C_.white], h: 1080, y: H / 2 + 20, push: .07, sway: 6, anchorY: .75 });
    for (let i = 0; i < 14; i++) { const x = 140 + hash(i * 3.3) * (W - 280), y = 120 + hash(i * 5.1) * 600, tw = .5 + .5 * Math.sin(t * 5 + i * 2); if (Math.abs(x - W / 2) < 330) continue; sparkle(x, y, 26 * tw + 6, i % 3 ? C_.white : C_.lemon, i, 0); }
    // floating hearts on "too"
    for (let i = 0; i < 6; i++) { const a = t - (58.6 + i * .08); if (a < 0) continue; const x = W / 2 + (i - 2.5) * 180, y = 700 - a * 260; X.globalAlpha = clamp(1 - a / 1.2); shp(heartPts(x, y, 28), C_.pink, 4); X.globalAlpha = 1; }
    return {};
  }

  // ---------------------------------------------------------------- 20 · hajimemashite, I made this song for you! (ojigi + title stamp)
  function s20(t, lt, dur) {
    sunburst(W / 2, 1200, C_.clay, C_.clayL, 30, t * .08);
    const tt = TW(t);
    // the ojigi on "hajimemashite" (59.3): anticipation up, bow down, hold, rise; wave on "you!" (61.5)
    const bow = kf(tt, [[59.2, 0], [59.35, -.15, 'out2'], [59.6, 1, 'out3'], [60.4, 1], [60.7, 0, 'back']]);
    const b = Math.max(0, bow);
    X.save(); cam(W / 2, 590, 1.35);
    const P0 = t > 61.3 ? pose('wave') : pose('bow');
    idol(W / 2, 860, 1, { ...P0, eyes: b > .3 ? 'closed' : 'happy', mouth: b > .3 ? 'small' : 'open', sing: b > .3 ? 0 : .4, bob: 70 * b, sq: -.12 * bow + hitSq(t, [61.5]), tilt: 0, blush: .8 });
    X.restore();
    // title stamp: HELLO, WORLD! with a sparkle, lands on "I made" (60.6)
    if (t >= 60.6) {
      const s = slamK(t, 60.6, .16);
      X.save(); X.translate(W / 2, 190); X.rotate(-.05); X.scale(s, s);
      pop('HELLO, WORLD!', 0, 0, { font: 'dela', size: 170, align: 'center', fill: C_.lemon, lw: 14, shadow: [12, 12, C_.pinkD] });
      pop('ハロー・ワールド', 0, 80, { font: 'mochi', size: 56, align: 'center', fill: C_.white, lw: 7 });
      X.restore();
      burstStars(t, 60.6, W / 2, 200, 14, 700, C_.white);
    }
    if (t > 61.85) flash((t - 61.85) / .27 * .8, C_.white);                    // whip into the dance hook
    return {};
  }

  // ---------------------------------------------------------------- 21 · THE DANCE HOOK (the template)
  // key poses on the sung words; [time, idolPose, extra, clawdPose, word]
  const MOVES = [
    [62.10, 'claw', { dx: 0 }, 'claw', 'CLAW,'],
    [62.80, 'clawOpen', { dx: 110, lean: .14, tilt: -.15 }, 'wiggle', 'CLAW!'],
    [63.50, 'claw', { dx: 110, lean: .05, tilt: .12 }, 'snap', 'SNIP-'],
    [63.85, 'clawOpen', { dx: 110, lean: .1, tilt: -.12 }, 'snap2', 'SNIP!'],
    [64.20, 'up', { dx: 0, hop: 110 }, 'up', 'CLAWD-UP!'],
    [64.60, 'haiR', { dx: 0, lean: -.1, hop: 30 }, 'haiR', 'HAI!'],
    [64.90, 'haiL', { dx: 0, lean: .1, hop: 30 }, 'haiL', 'HAI!'],
    [65.25, 'idle', { dx: 0 }, 'idle', null],
    [65.60, 'claw', { dx: 0 }, 'claw', 'CLAW,'],
    [65.90, 'clawOpen', { dx: -110, lean: -.14, tilt: .15 }, 'wiggle', 'CLAW!'],
    [66.30, 'claw', { dx: -110, lean: -.05, tilt: -.12 }, 'snap', 'SNIP-'],
    [66.55, 'clawOpen', { dx: -110, lean: -.1, tilt: .12 }, 'snap2', 'SNIP!'],
    [67.00, 'up', { dx: 0, hop: 110 }, 'up', 'CLAWD-UP!'],
    [67.40, 'haiR', { dx: 0, lean: -.1, hop: 30 }, 'haiR', 'HAI!'],
    [67.60, 'haiL', { dx: 0, lean: .1, hop: 30 }, 'haiL', 'HAI!'],
  ];
  const IDP = { ...POSE, up: { armL: [2.45, -.45], armR: [2.45, -.45], handL: 'open', handR: 'open' },
    haiR: { armL: [.35, -.1], armR: [2.45, -.35], handL: 'fist', handR: 'fist' }, haiL: { armL: [2.45, -.35], armR: [.35, -.1], handL: 'fist', handR: 'fist' } };
  function idolPose(name) { const A = IDP[name]; return { armL: A.armL, armR: A.armR, handL: A.handL, handR: A.handR }; }
  function blendP(a, b, u) { const A = idolPose(a), B = idolPose(b); return { armL: [lerp(A.armL[0], B.armL[0], u), lerp(A.armL[1], B.armL[1], u)], armR: [lerp(A.armR[0], B.armR[0], u), lerp(A.armR[1], B.armR[1], u)], handL: u > .5 ? B.handL : A.handL, handR: u > .5 ? B.handR : A.handR }; }
  const CLP = { claw: { armL: 1.3, armR: 1.3, eyes: 'wide' }, wiggle: { armL: 1.5, armR: .9, eyes: 'wide' }, snap: { armL: .4, armR: 1.5, eyes: 'wide' }, snap2: { armL: 1.5, armR: .4, eyes: 'wide' },
    up: { armL: 1.9, armR: 1.9, eyes: 'happy', hop: 80 }, haiR: { armL: .2, armR: 1.8, eyes: 'happy', hop: 20 }, haiL: { armL: 1.8, armR: .2, eyes: 'happy', hop: 20 }, idle: { armL: .1, armR: .1, eyes: 'open' } };
  function s21(t, lt, dur) {
    const bar = Math.floor((t - 62.12) / BAR + 1e-6), BGS = [[C_.pink, '#FF7FBF'], [C_.cyan, '#7AEFFA'], [C_.lemon, '#FFF19A'], [C_.violet, '#9F7BFF']];
    const [ca, cb] = BGS[((bar % 4) + 4) % 4];
    checker(120, ca, cb, .25, t * 60, t * 30);
    const tt = TW(t);
    let i = 0; while (i + 1 < MOVES.length && tt >= MOVES[i + 1][0]) i++;
    const cur = MOVES[i], prev = MOVES[Math.max(0, i - 1)], age = tt - cur[0];
    // a 1-drawing smear between key poses (the in-between on the first 2 frames), then the held key
    const inb = age < 2 / 24 && i > 0;
    const P0 = inb ? blendP(prev[1], cur[1], .5) : idolPose(cur[1]);
    const ex = inb ? { dx: lerp(prev[2].dx || 0, cur[2].dx || 0, .5), lean: lerp(prev[2].lean || 0, cur[2].lean || 0, .5), tilt: lerp(prev[2].tilt || 0, cur[2].tilt || 0, .5), hop: 0 } : cur[2];
    const hopK = cur[2].hop ? cur[2].hop * Math.sin(clamp(age / .32) * Math.PI) : 0;
    const hits = MOVES.map(m => m[0]);
    const sq = hitSq(t, hits, .16, 16) + (inb ? -.12 : 0);
    const shk = kick(t, hits, 1, 14);
    X.save(); cam(W / 2 + shake(t, 6 * shk)[0], H / 2 + shake(t, 6 * shk)[1], 1 + .03 * shk);
    // floor spot shadows
    shp(ellipse(620 + (ex.dx || 0), 1045, 240, 34), 'rgba(27,20,24,.25)', 0); shp(ellipse(1420, 1045, 250, 34), 'rgba(27,20,24,.25)', 0);
    // idol
    const eyes = /clawOpen|claw/.test(cur[1]) ? (cur[1] === 'clawOpen' ? 'star' : 'determined') : cur[1] === 'up' ? 'happy' : /hai/.test(cur[1]) ? 'happy' : 'open';
    idol(620 + (ex.dx || 0), 1040, 1.6, { ...P0, lean: ex.lean || 0, tilt: ex.tilt || 0, hop: hopK / 1.6, sq, eyes, mouth: /hai|up/.test(cur[1]) ? 'open' : 'grin', sing: /hai|up/.test(cur[1]) ? .7 : 0, blush: .6, skirtFlare: clamp(hopK / 70), hairLift: clamp(hopK / 90) * .6 });
    if (inb) speedStreaks(620 + (ex.dx || 0), 700, (cur[2].dx || 0) - (prev[2].dx || 0), t);
    // clawd: same counts, translated to nubs and hops
    const cp = CLP[cur[3]], cpp = CLP[prev[3]];
    const ca2 = inb ? { armL: lerp(cpp.armL, cp.armL, .5), armR: lerp(cpp.armR, cp.armR, .5) } : cp;
    const chop = (cp.hop || 0) * Math.sin(clamp(age / .3) * Math.PI);
    clawd(1420 - (ex.dx || 0) * .6, 1040, 2.2, { armL: ca2.armL, armR: ca2.armR, eyes: cp.eyes, hop: chop / 1.6, sq: sq * 1.2, lean: -(ex.lean || 0), blush: 1 });
    X.restore();
    // THE WORD: one per move, slammed full width
    if (cur[4] && age < .9) {
      const s = slamK(t, cur[0], .12), cols = [C_.white, C_.lemon, C_.ink];
      const big = cur[4].length > 6 ? 190 : 250;
      const L = shape(cur[4], { font: 'dela', size: big * .82 }), fit = Math.min(1, 760 / L.width);
      X.save(); X.translate(1400, 330); X.rotate((i % 2 ? -.06 : .06)); X.scale(s * fit, s * fit);
      pop(cur[4], 0, 0, { font: 'dela', size: big * .82, align: 'center', fill: i % 3 === 2 ? C_.lemon : C_.white, lw: 16, shadow: [14, 14, C_.ink] });
      X.restore();
    }
    // the template: an 8-count strip bottom centre (a dance tutorial in the frame)
    const b0 = beatPos(62.12), cnt = Math.floor(beatPos(t) - b0 + 1e-6) % 8;
    const bx = 1110;
    shp(rrect(bx - 40, 520, 7 * 76 + 80, 64, 32), C_.ink, 0);
    for (let k = 0; k < 8; k++) { const on = k === cnt; shp(circle(bx + k * 76, 552, on ? 24 : 13), on ? C_.lemon : C_.cream, on ? 5 : 0); if (on) pop(String(k + 1), bx + k * 76, 564, { font: 'dela', size: 30, align: 'center', fill: C_.ink, lw: 0 }); }
    X.save(); X.translate(1400, 110); X.rotate(-.04); pop('♪ CLAW DANCE ♪', 0, 0, { font: 'dela', size: 58, align: 'center', fill: C_.white, lw: 8, shadow: [6, 6, C_.ink] }); X.restore();
    return { karaoke: false, calls: false };
  }
  // a smear accent for in-between drawings: a few ink speed strokes beside the body
  function speedStreaks(x, y, dx, t) {
    const dir = dx >= 0 ? -1 : 1;
    for (let k = 0; k < 5; k++) { const yy = y - 160 + k * 90 + hash(k + BF(t)) * 30, x0 = x + dir * (210 + hash(k * 3 + BF(t)) * 60); lin([[x0, yy], [x0 + dir * (120 + k * 20), yy]], 7, C_.ink); }
  }
  s21.label = 'dance';

  Object.assign(SHOT, { '13': s13, '14': s14, '15': s15, '16': s16, '17': s17, '18': s18, '19': s19, '20': s20, '21': s21 });
})();
