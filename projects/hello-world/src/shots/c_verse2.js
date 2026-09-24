// shots 22–30: verse 2 (the quiz show), pre-chorus 2 (the feed), chorus 2 opening (spin hero, dress of text, pixel heart).
(() => {
  // ---------------------------------------------------------------- helpers
  const Q = { q1: 67.72, a1: 69.18, q2: 70.58, a2: 72.0, q3: 73.4, a3: 74.66, q4: 76.22, you: 77.62 };
  const tw = onTwos;                                   // characters on twos

  // a slammed speech bubble from the crowd (lower-left), text in Dela
  function bubble(t, t0, txt, x, y, o = {}) {
    if (t < t0 - .02) return;
    const k = slamK(t, t0, .12), out = o.out != null ? clamp((t - o.out) / .15) : 0;
    if (out >= 1) return;
    const size = o.size || 74, S = shape(txt, { font: 'dela', size }), w = S.width + 90, h = size * 1.7;
    X.save(); X.translate(x, y); X.rotate(o.rot ?? -.05); X.scale(k * (1 - out), k * (1 - out));
    const body = blob([[-w / 2, -h / 2], [0, -h / 2 - 14], [w / 2, -h / 2], [w / 2 + 12, 0], [w / 2, h / 2], [0, h / 2 + 10], [-w / 2, h / 2], [-w / 2 - 12, 0]], 4);
    const tail = [[-w * .22, h / 2 - 6], [-w * .34 + (o.tail || -60), h / 2 + 90], [-w * .06, h / 2 - 2]];
    shp(tail, o.fill || C_.white, 7); shp(body, o.fill || C_.white, 7); fil(tail.map(([a, b]) => [a, b - 8]), o.fill || C_.white);
    pop(txt, 0, size * .36, { L: S, align: 'center', fill: o.ink || C_.pink, lw: 0 });
    X.restore();
  }
  // a chibi cat with a COMMA for a tail (a round dot + a curling hook)
  function cat(x, y, s, col, o = {}) {
    const tt = NOW, seed = o.seed || 1;
    X.save(); X.translate(x, y); X.scale(s * (o.flip ? -1 : 1), s); X.rotate(o.rot || 0);
    // the comma tail
    const wag = Math.sin(tt * 5 + seed) * .25;
    X.save(); X.translate(34, -14); X.rotate(wag);
    shp(blob([[0, -18], [18, -4], [14, 18], [2, 44], [-6, 40], [4, 18], [-14, 4]], 4), col, 5);
    X.restore();
    shp(wob(ellipse(0, -18, 40, 30), seed, .6), col, 6);                       // body loaf
    shp(wob([[-34, -40], [-28, -70], [-12, -48]], seed + 1, .5), col, 5);        // ears
    shp(wob([[12, -48], [28, -70], [34, -40]], seed + 2, .5), col, 5);
    shp(wob(ellipse(0, -38, 36, 26), seed + 3, .6), col, 6);                     // head
    const e = o.eyes || 'open';
    if (e === 'sleep') { lin([[-18, -38], [-6, -38]], 4); lin([[6, -38], [18, -38]], 4); }
    else { fil(ellipse(-13, -40, 5, 8), C_.ink); fil(ellipse(13, -40, 5, 8), C_.ink); fil(circle(-15, -43, 2), C_.white); fil(circle(11, -43, 2), C_.white); }
    lin([[-6, -28], [0, -24], [6, -28]], 3.5);
    X.restore();
  }
  // the gaudy quiz-show set: scrolling stripes, a light-bulb arch, a podium + buzzer, the crowd at the bottom-left
  function quizSet(t, o = {}) {
    const dim = o.dim || 0;
    stripes(C_.pink, C_.pinkD, 70, -.35, t * 90);
    // the arch: a rounded frame of bulbs chasing on eighths
    const arch = rrect(180, 60, W - 360, 900, 140);
    shp(arch, null, 34, C_.ink); lin(arch.concat([arch[0]]), 44, C_.lemonD);
    const n = 64, ph = Math.floor(beatPos(t) * 2);
    for (let i = 0; i < n; i++) {
      const p = arch[Math.floor(i / n * arch.length)], on = (i + ph) % 3 !== 0;
      shp(circle(p[0], p[1], 13), on ? C_.white : C_.lemonD, 3);
      if (on) glow(p[0], p[1], 34, 'rgba(255,240,160,1)', .5);
    }
    // the backdrop inside the arch: a night-violet panel with a big "Q&A" and a spark
    clipTo(rrect(202, 82, W - 404, 856, 120), () => {
      sunburst(W / 2, 360, C_.night, C_.violet, 22, t * .1);
      X.save(); X.translate(W / 2, 250); X.rotate(-.04 + Math.sin(t * 2) * .02); const k = 1 + .04 * pulse(t, 8);
      X.scale(k, k); pop('Q&A', 0, 0, { font: 'dela', size: 170, align: 'center', fill: C_.lemon, lw: 12, shadow: [10, 10, C_.pinkD] });
      spark8(250, -60, 46, C_.cyan, 6, t);
      X.restore();
    });
  }
  function podium(x, y, t, pressT) {
    // the podium front + a buzzer that gets slapped (pressT)
    const pr = pressT != null && t >= pressT ? Math.max(0, 1 - (t - pressT) / .18) : 0;
    shp([[x - 150, y], [x + 150, y], [x + 130, y + 260], [x - 130, y + 260]], C_.cyan, LW);
    fil([[x - 150, y], [x + 150, y], [x + 146, y + 26], [x - 146, y + 26]], C_.cyanD);
    spark8(x, y + 140, 58, C_.lemon, 6, t * .3);
    shp(rrect(x - 44, y - 34 + pr * 14, 88, 36 - pr * 14, 12), C_.pink, 6);        // the buzzer
    shp(rrect(x - 60, y - 6, 120, 16, 6), C_.ink, 0);
    if (pr > 0) { for (let i = 0; i < 7; i++) { const a = -Math.PI / 2 + (i - 3) * .35; lin([[x + Math.cos(a) * 70, y - 40 + Math.sin(a) * 70], [x + Math.cos(a) * (110 + (1 - pr) * 40), y - 40 + Math.sin(a) * (110 + (1 - pr) * 40)]], 8, C_.lemon); } }
  }
  // the studio audience: costumed Clawds with signs. askT = the time the current question is asked (the asker hops + raises the mic)
  const stars3 = () => { X.save(); lin([[0, 0], [0, -70]], 6, LN); X.translate(0, -120); shp(rrect(-90, -46, 180, 92, 10), C_.white, 2.5, LN); for (let k = -1; k <= 1; k++) sparkle(k * 52, 0, 26, C_.lemon, 0, 2.5); X.restore(); };
  function audience(t, askT = null, o = {}) {
    const seats = [                                         // back tier first, then the front tier
      { x: 190, y: 930, s: .62, hat: 'beret', holdR: { sign: 'LOL', col: C_.violet, size: 44 }, eyes: 'happy' },
      { x: 390, y: 930, s: .62, hat: 'headband', holdR: 'penlight', eyes: 'open' },
      { x: 90, y: 1075, s: .82, hat: 'bow', holdR: { sign: 'YES!', col: C_.pinkD, size: 44 }, eyes: 'heart' },
      { x: 290, y: 1075, s: .82, hat: 'party', holdR: 'mic', eyes: 'open', asker: true },
      { x: 490, y: 1075, s: .82, hat: 'crown', holdR: { sign: '?', col: C_.cyanD, size: 64 }, eyes: 'wide' },
    ];
    // bleacher steps
    shp([[-60, 950], [590, 950], [590, 1200], [-60, 1200]], C_.nightD, 5); lin([[-60, 950], [590, 950]], 6, C_.lemonD);
    seats.forEach((c, i) => {
      const b = pulse(t, 7, 1, i * .5) * 12;
      const asking = c.asker && askT != null && t > askT - .15 && t < askT + .9;
      const hop = asking ? 26 * Math.abs(Math.sin((t - askT) * 9)) : b;
      clawd(c.x, c.y, c.s, { seed: 30 + i * 7, hat: c.hat, holdR: c.holdR, penCol: C_.pink, armR: asking ? 1.25 : .9 + .15 * Math.sin((beatPos(t) + i) * Math.PI), armL: .3,
        eyes: o.dim ? 'closed' : c.eyes, mouth: asking ? 'open' : 'cat', hop, pincer: i % 2 === 1, snip: (Math.sin(t * 9 + i) + 1) / 2, blush: c.eyes === 'heart' });
    });
  }
  // the host: a top-hat Clawd with a mic, right of the podium
  function host(t, o = {}) {
    const lean = o.lean ?? Math.sin(tw(t) * 2) * .04, ask = o.ask;
    clawd(1740, 1060, .9, { seed: 91, hat: 'tophat', bowtie: true, holdL: 'mic', armL: ask ? 1.15 : .7, armR: .35 + .3 * pulse(t, 6), lean, eyes: o.eyes || 'open', mouth: ask ? 'open' : 'cat', look: [-1, 0] });
  }

  // ---------------------------------------------------------------- 22 · Commas and cats
  // reads: (1) quiz show, the crowd asks (67.72) (2) she slaps the buzzer + answers (69.18) (3) a pile of comma-tailed cats drops in (69.2–69.9)
  function s22(t, lt, dur) {
    const z = 1 + .02 * pulse(t, 6, 4) + .03 * E.io2(clamp(lt / dur));
    X.save(); cam(W / 2, H / 2, z);
    quizSet(t);
    // the cats fall in on "Commas" (69.18), landing in a pyramid on the left, bouncing
    const cats = [[520, 800, C_.cream], [660, 800, C_.clay], [800, 800, C_.lemon], [590, 700, C_.ink], [730, 700, C_.cream], [660, 600, C_.clay]];
    cats.forEach(([x, y, col], i) => {
      const t0 = Q.a1 + i * .09, u = clamp((t - t0) / .28);
      if (t < t0) return;
      const yy = lerp(-200, y, E.in2(u)), sq = u >= 1 ? wobble(tw(t), t0 + .28, 3, 7) * .25 : 0;
      X.save(); X.translate(x, yy); X.scale(1 + sq, 1 - sq); cat(0, 0, 1.25, col, { seed: i + 1, eyes: col === C_.ink ? 'open' : 'open', flip: i % 2 }); X.restore();
      if (col === C_.ink) { fil(ellipse(x - 16, yy - 50, 5, 8), C_.lemon); fil(ellipse(x + 16, yy - 50, 5, 8), C_.lemon); }
    });
    if (t > Q.a1 + .35) for (let i = 0; i < 3; i++) { const y = 480 - ((t - Q.a1 - .35) * 90 + i * 60) % 180; pop(',', 380 + i * 60, y, { font: 'dela', size: 90, fill: C_.lemon, lw: 7 }); }
    // the idol behind the podium: listening -> slap the buzzer -> answer, arm up
    const ans = t >= Q.a1 - .06;
    const P = ans ? pose('point', 'up', .35) : pose('idle');
    idol(1300, 1110 + (ans ? -18 * pulse(t, 5, .5) : 0), 1.3, { ...P, eyes: ans ? 'happy' : (t > Q.q1 + .2 ? 'side' : 'open'), look: [-1, -.2], sing: ans ? .6 + .3 * Math.sin(t * 20) : 0, mouth: ans ? 'open' : 'smile', hop: ans ? 20 * Math.abs(Math.sin((t - Q.a1) * 8)) * clamp(1 - (t - Q.a1)) : 0, skirtFlare: ans ? .3 : 0 });
    podium(1300, 840, t, Q.a1 - .05);
    audience(t, Q.q1); host(t, { ask: t > Q.q1 - .1 && t < Q.a1 });
    bubble(t, Q.q1, 'WHAT DO YOU LIKE?', 560, 290, { tail: -120, rot: -.06, out: Q.a1 + .5 });
    restore0();
    return { calls: false };
  }
  const restore0 = () => X.restore();

  // ---------------------------------------------------------------- 23 · Code at 3 a.m.
  // reads: (1) the crowd asks again (70.58) (2) a thought bubble balloons out of her head (71.6) into (3) the night desk: terminal, tea, a cat asleep on the keys (72.0–73.3)
  function nightDesk(t, lt) {
    flat(C_.nightD);
    // window + moon + stars
    shp(rrect(1180, 120, 520, 420, 20), C_.night, LW); lin([[1440, 120], [1440, 540]], 10); lin([[1180, 330], [1700, 330]], 10);
    shp(circle(1590, 220, 46), C_.lemon, 5); fil(circle(1612, 206, 40), C_.night);
    for (let i = 0; i < 9; i++) sparkle(1210 + hash(i) * 460, 140 + hash(i * 3) * 380, 6 + 4 * Math.sin(t * 4 + i), C_.white);
    // the clock at 3:00
    shp(circle(380, 230, 90), C_.cream, LW); lin([[380, 230], [380, 165]], 9); lin([[380, 230], [430, 230]], 11); fil(circle(380, 230, 9), C_.pink);
    pop('3AM', 380, 380, { font: 'dela', size: 50, align: 'center', fill: C_.pink, lw: 6 });
    // the idol behind the desk, lit by the screen, typing happily
    const typing = Math.sin(t * 24) > 0;
    idol(900, 1000, 1.2, { ...pose('offer'), handL: 'mitt', handR: 'mitt', armL: [.55, 1.35 + (typing ? .12 : 0)], armR: [.55, 1.35 + (typing ? 0 : .12)], eyes: 'star', mouth: 'grin', blush: .6, tilt: Math.sin(tw(t) * 3) * .04 });
    glow(900, 600, 420, 'rgba(56,224,240,1)', .35);
    // the desk + laptop (its back to us, with the spark)
    shp([[140, 820], [1780, 820], [1780, 1100], [140, 1100]], C_.clayD, LW); lin([[140, 850], [1780, 850]], 6, C_.clay);
    shp([[720, 830], [1080, 830], [1050, 700], [750, 700]], '#C8CCD8', LW); spark8(900, 765, 30, C_.clay, 5, t * .2);
    // code rising like steam from the screen
    const code = ['hello()', '{ }', '<3', 'if (why)', '//todo: sleep', '=>', 'print'];
    for (let i = 0; i < 6; i++) { const a = (lt * .9 + i / 6) % 1; pop(code[i], (i % 2 ? 1060 : 560) + ((i * 97) % 200) - 100, 680 - a * 420, { font: 'roundB', size: 34, fill: C_.cyan, lw: 4, per: () => ({}) }); }
    // tea with steam
    shp(rrect(1230, 700, 110, 120, 18), C_.white, LW); lin(arcPts2(1360, 750, 30, 30, -Math.PI / 2, Math.PI / 2), 8); fil(rrect(1240, 712, 90, 22, 8), C_.clayL);
    for (let i = 0; i < 2; i++) lin([[1265 + i * 40, 690], [1255 + i * 40 + Math.sin(t * 3 + i) * 10, 640], [1275 + i * 40, 590]], 6, C_.cream);
    // the cat asleep on the keyboard (in front of the laptop), zzz
    shp(rrect(420, 760, 300, 60, 10), C_.ink, 5); for (let i = 0; i < 9; i++) fil(rrect(432 + i * 32, 772, 24, 14, 3), C_.cream);
    const br = Math.sin(t * 2.2) * .04;
    X.save(); X.translate(570, 790); X.scale(1 + br, 1 - br); cat(0, 0, 1.3, C_.lemon, { eyes: 'sleep', seed: 9 }); X.restore();
    for (let i = 0; i < 3; i++) { const a = (t * .6 + i / 3) % 1; pop('z', 660 + a * 60, 640 - a * 120, { font: 'dela', size: 30 + i * 12, fill: C_.white, lw: 5 }); }
    // a sleepy Clawd in a nightcap, nodding off on the desk by the tea (it jolts awake on the beat, then droops again)
    const nod = frac(beatPos(t) / 2), droop = E.in2(clamp(nod * 1.3)) * .22 - (nod < .08 ? .12 : 0);
    const cx = 1560, cy = 832, cs = .6;
    X.save(); X.translate(cx, cy); X.rotate(droop); X.translate(-cx, -cy);
    clawd(cx, cy, cs, { seed: 77, eyes: nod < .08 ? 'wide' : 'closed', mouth: nod < .08 ? 'o' : null, armL: -.2, armR: -.2, blush: true, holdR: () => { X.save(); X.rotate(Math.PI / 2); shp(rrect(-18, -40, 36, 50, 8), C_.cream, 2.5, LN); X.restore(); } });
    const top = cy - (124 + 44) * cs;
    shp(blob([[cx - 62 * cs * 1.6, top + 6], [cx - 20, top - 58], [cx + 60, top - 70], [cx + 108, top - 30], [cx + 70, top - 36], [cx + 40, top + 6]], 3), C_.cyan, 2.8, LN);
    shp(rrect(cx - 100 * cs * 1.05, top - 4, 210 * cs * 1.05, 20, 8), C_.white, 2.5, LN);
    shp(circle(cx + 112, top - 26, 13), C_.white, 2.5, LN);
    X.restore();
    for (let i = 0; i < 2; i++) { const a = (t * .5 + i / 2) % 1; pop('z', cx + 70 + a * 40, top - 40 - a * 110, { font: 'dela', size: 26 + i * 10, fill: C_.cyan, lw: 5 }); }
  }
  function s23(t, lt, dur) {
    const bu = E.inExpo(clamp((t - 71.55) / .45));        // the thought bubble grows to fill the frame by 72.0
    if (bu < 1) {
      X.save(); cam(W / 2, H / 2, 1.03);
      quizSet(t);
      const P = pose('idle');
      idol(1300, 1110, 1.3, { ...P, eyes: t > 71.1 ? 'closed' : 'side', look: [-1, -.2], mouth: t > 71.1 ? 'cat' : 'smile', tilt: t > 71.1 ? -.12 : 0, armR: t > 71.1 ? [1.1, 2.1] : P.armR, handR: t > 71.1 ? 'fist' : 'mitt' });
      podium(1300, 840, t, null);
      audience(t, Q.q2); host(t, { ask: t > Q.q2 - .1 && t < 71.1 });
      bubble(t, Q.q2, 'WHAT DO YOU LIKE?', 560, 290, { tail: -120, rot: .05 });
      // thinking dots, then the bubble
      if (t > 71.1) for (let i = 0; i < 3; i++) if (t > 71.1 + i * .12) shp(circle(1120 - i * 60, 380 - i * 60, 16 + i * 10), C_.white, 5);
      X.restore();
      if (bu > 0) {
        const r = lerp(60, 2300, bu), cx = lerp(960, W / 2, bu), cy = lerp(220, H / 2, bu);
        const cl = blob(Array.from({ length: 14 }, (_, i) => { const a = i / 14 * TAU, rr = r * (1 + .08 * Math.sin(i * 3)); return [cx + Math.cos(a) * rr * 1.2, cy + Math.sin(a) * rr]; }), 4);
        shp(cl, C_.white, 8); clipTo(cl, () => nightDesk(t, lt));
      }
    } else {
      X.save(); cam(W / 2, H / 2, 1.02 + .03 * E.out3(clamp((t - 72) / 1.3))); nightDesk(t, lt); X.restore();
    }
    return { calls: false };
  }

  // ---------------------------------------------------------------- 24 · A really good question!
  // reads: (1) the question (73.4) (2) her eyes go starry (74.66) (3) a ❓ balloon lifts her off the podium, the camera tilts up after her (74.9–76.1)
  function s24(t, lt, dur) {
    const lift = E.io3(clamp((t - 74.9) / 1.1)), tilt = E.io3(clamp((t - 75.1) / 1)) * 260;
    X.save(); cam(W / 2, H / 2 - tilt, 1.02);
    quizSet(t);
    // above the set: sky with sparkles for the tilt
    X.save(); X.fillStyle = C_.violet; X.fillRect(-200, -700, W + 400, 700); X.restore();
    for (let i = 0; i < 14; i++) sparkle(hash(i * 5) * W, -650 + hash(i * 9) * 640, 8 + 6 * Math.sin(t * 5 + i), C_.lemon, i);
    const star = t >= Q.a3 - .05;
    const bx = 1300, by = 1110 - lift * 560, sway = Math.sin(tw(t) * 3) * .06 * lift;
    // the balloon: a fat pink "?" with a string to her raised hand
    if (t > 74.75) {
      const bk = E.back(clamp((t - 74.75) / .3));
      X.save(); X.translate(bx + 90, by - 720 - lift * 30); X.rotate(sway * 2 + Math.sin(t * 2) * .05); X.scale(bk, bk);
      pop('?', 0, 90, { font: 'dela', size: 330, align: 'center', fill: C_.pink, lw: 14, shadow: [12, 12, C_.pinkD] });
      fil(ellipse(-50, -80, 16, 28, -.4), C_.white);
      X.restore();
      lin([[bx + 90, by - 630 - lift * 30], [bx + 110, by - 500], [bx + 100, by - 420]], 4);
    }
    X.save(); X.translate(bx, by); X.rotate(sway); X.translate(-bx, -by);
    idol(bx, by, 1.3, { ...(star ? pose('wave') : pose('idle')), armR: star ? [2.5, .1] : [.22, -.1], handR: star ? 'fist' : 'mitt', eyes: star ? 'star' : 'side', look: [-1, -.2], mouth: star ? 'open' : 'smile', sing: star ? .5 + .3 * Math.sin(t * 18) : 0, legL: [0, lift * .5], legR: [0, -lift * .3], skirtFlare: lift * .5, blush: star ? .8 : .35 });
    X.restore();
    podium(1300, 840, t, null);
    audience(t, Q.q3); host(t, { ask: t > Q.q3 - .1 && t < Q.a3, eyes: t > Q.a3 ? 'star' : 'open' });
    bubble(t, Q.q3, 'WHAT DO YOU LIKE?', 560, 290, { tail: -120, rot: -.04, out: 74.9 });
    if (star) for (let i = 0; i < 8; i++) { const a = i / 8 * TAU + t, r = 190 + 30 * Math.sin(t * 6 + i); sparkle(bx + Math.cos(a) * r, by - 460 + Math.sin(a) * r * .6, 16, i % 2 ? C_.lemon : C_.white, t * 2); }
    X.restore();
    return { calls: false };
  }

  // ---------------------------------------------------------------- 25 · (What do you love?) …You. For listening.
  // reads: (1) the lights drop, a single spotlight, the question is small now (76.22) (2) a soft cut to the sakuga blush (77.45) (3) hold, slow push, hearts rise (to 79.06)
  function s25(t, lt, dur) {
    const cutT = 77.45;
    if (t < cutT) {
      const d = E.out3(clamp((t - 76.1) / .4));
      X.save(); cam(1200, 600, 1.12 + .06 * clamp((t - 76.1) / 1.3));
      quizSet(t);
      audience(t, Q.q4); host(t, { ask: t > Q.q4 - .1 && t < 77.2 });
      X.save(); X.setTransform(1, 0, 0, 1, 0, 0); X.globalAlpha = .72 * d; X.fillStyle = C_.nightD; X.fillRect(0, 0, W, H); X.restore();
      // the spotlight cone on her
      X.save(); X.globalAlpha = .22 * d; X.fillStyle = C_.cream; X.beginPath(); X.moveTo(1300, -200); X.lineTo(1000, 1100); X.lineTo(1600, 1100); X.fill(); X.restore();
      idol(1300, 1110, 1.3, { ...pose('heart'), eyes: 'shy', look: [-1, .2], blush: .4 + .6 * clamp((t - 76.9) / .4), mouth: 'small', tilt: .06 });
      podium(1300, 840, t, null);
      bubble(t, Q.q4, 'WHAT DO YOU LOVE?', 760, 330, { size: 52, tail: -80, rot: .03, fill: C_.cream, ink: C_.pinkD });
      X.restore();
      return { calls: false };
    }
    const lt2 = t - cutT, d2 = 79.06 - cutT;
    cutin(t, lt2, d2, { img: 'k06_shy', bg: t => { flat('#FFD3E6'); dots('#FFFFFF', 34, 7, .5, (x, y) => clamp(1 - Math.hypot(x - W * .5, y - H * .45) / 900)); }, h: H * 1.02, y: H * .52, push: .09, sway: 4, anchorY: .72, flashCol: '#FFE3EF' });
    // a few soft hearts floating up
    for (let i = 0; i < 7; i++) { const a = (lt2 * .35 + i / 7) % 1, x = (i % 2 ? 260 : 1660) + Math.sin(lt2 * 2 + i) * 40 + (i * 37 % 120) - 60, y = 1000 - a * 900; X.save(); X.globalAlpha = Math.sin(a * Math.PI); pop('♡', x, y, { font: 'mochi', size: 50 + (i % 3) * 16, align: 'center', fill: C_.pink, lw: 0 }); X.restore(); }
    return { calls: false, karaoke: { fill: C_.white, sungFill: C_.pinkD } };
  }

  // ---------------------------------------------------------------- 26/27 · the feed: slop, soul, scroll on by, bye-bye; she pops back up; why? why?
  const PH = { x: W / 2 - 280, y: 30, w: 560, h: 1020 };
  function feedBg(t) { checker(90, C_.night, C_.nightD, .2, t * 40, t * 25); }
  function phoneFrame(inner) {
    shp(rrect(PH.x - 24, PH.y - 24, PH.w + 48, PH.h + 48, 60), C_.ink, LW);
    clipTo(rrect(PH.x, PH.y, PH.w, PH.h, 42), inner);
    fil(rrect(W / 2 - 70, PH.y + 12, 140, 30, 15), C_.ink);                         // the notch
  }
  // a feed card: returns nothing; kind: 'idol' | 'food' | 'cat' | 'text'
  function card(y, kind, t, o = {}) {
    const x = PH.x + 24, w = PH.w - 48, h = 440;
    shp(rrect(x, y, w, h, 26), C_.white, 5);
    fil(circle(x + 36, y + 36, 18), [C_.pink, C_.cyan, C_.lemon][(kind.length) % 3]); fil(rrect(x + 64, y + 26, 160, 18, 9), C_.creamD);
    clipTo(rrect(x + 16, y + 70, w - 32, 300, 18), () => {
      if (kind === 'idol') { sunburst(x + w / 2, y + 230, C_.pink, C_.lemon, 18, t * .3); idol(x + w / 2, y + 530, .62, o.pose || {}); }
      else if (kind === 'food') { flat(C_.lemon); shp(ellipse(x + w / 2, y + 230, 140, 90), C_.clayL, 6); shp(ellipse(x + w / 2, y + 220, 110, 60), C_.pink, 5); }
      else if (kind === 'cat') { flat(C_.cyan); cat(x + w / 2, y + 300, 2, C_.cream, { seed: 4 }); }
      else { flat(C_.cream); for (let i = 0; i < 5; i++) fil(rrect(x + 40, y + 110 + i * 46, (w - 120) * (.5 + .5 * hash(i + kind.length)), 20, 10), C_.creamD); }
    });
    for (let i = 0; i < 3; i++) shp(circle(x + 40 + i * 60, y + h - 34, 12), C_.white, 4);
    pop('♡', x + w - 50, y + h - 20, { font: 'mochi', size: 44, align: 'center', fill: C_.pink, lw: 4 });
  }
  function stamp(t, t0, txt, x, y, col, rot) {
    if (t < t0 - .02) return;
    const k = slamK(t, t0, .1);
    X.save(); X.translate(x, y); X.rotate(rot); X.scale(k, k);
    const S = shape(txt, { font: 'dela', size: 150 });
    shp(rrect(-S.width / 2 - 40, -140, S.width + 80, 180, 20), null, 10, col);
    shp(rrect(-S.width / 2 - 26, -126, S.width + 52, 152, 14), null, 4, col);
    pop(txt, 0, 0, { L: S, align: 'center', fill: col, lw: 0 });
    X.restore();
  }
  function thumb(x, y, rot = 0) {
    X.save(); X.translate(x, y); X.rotate(rot);
    shp(rrect(-80, -40, 160, 520, 80), C_.skin, LW);
    shp(rrect(-58, -20, 116, 120, 40), '#FFF1EA', 5); lin([[-70, 170], [70, 170]], 5, C_.skinD); lin([[-70, 200], [70, 200]], 5, C_.skinD);
    X.restore();
  }
  // the feed is always moving: a continuous scroll, a momentum flick on "scroll" (80.8), velocity decaying back to a drift in 27.
  const F0 = 79.06, FLICK = 80.8;
  const feedScroll = t => (t - F0) * 240 + 1900 * E.out3(clamp((t - FLICK) / .75)) + (t > 81.8 ? (t - 81.8) * 60 : 0);
  const feedVel = t => (feedScroll(t + 1 / 48) - feedScroll(t - 1 / 48)) * 24;
  const STREAM = ['cat', 'recipe', 'clawd', 'text', 'food', 'cat', 'clawd', 'recipe', 'text', 'cat', 'food', 'clawd', 'recipe', 'cat', 'text', 'food'];
  function card2(y, kind, t, o = {}) {
    if (kind !== 'recipe' && kind !== 'clawd') return card(y, kind, t, o);
    const x = PH.x + 24, w = PH.w - 48, h = 440;
    shp(rrect(x, y, w, h, 26), C_.white, 5);
    fil(circle(x + 36, y + 36, 18), kind === 'clawd' ? C_.clay : C_.lemon); fil(rrect(x + 64, y + 26, 160, 18, 9), C_.creamD);
    clipTo(rrect(x + 16, y + 70, w - 32, 300, 18), () => {
      if (kind === 'clawd') { checker(40, C_.cyan, '#8FEFF8', 0, 0, 0); clawd(x + w / 2, y + 350, .95, { seed: 5, glasses: 'shades', mouth: 'cat', armR: 1.4, holdR: () => { X.save(); X.rotate(-Math.PI / 2); shp(rrect(-22, -64, 44, 70, 8), C_.ink, 2, LN); X.restore(); }, armL: .4 }); pop('selfie!', x + 40, y + 120, { font: 'dela', size: 34, fill: C_.lemon, lw: 5 }); }
      else { flat(C_.cream); shp(ellipse(x + 150, y + 230, 100, 60), C_.white, 5); shp(ellipse(x + 150, y + 216, 80, 34), C_.lemon, 4); fil(circle(x + 130, y + 210, 10), C_.pink); fil(circle(x + 170, y + 222, 8), C_.green);
        for (let i = 0; i < 5; i++) { fil(circle(x + 290, y + 130 + i * 44, 6), C_.clay); fil(rrect(x + 310, y + 122 + i * 44, 130 - (i % 2) * 40, 16, 8), C_.creamD); } pop('RECIPE', x + 290, y + 110, { font: 'dela', size: 24, fill: C_.clay, lw: 0 }); }
    });
    for (let i = 0; i < 3; i++) shp(circle(x + 40 + i * 60, y + h - 34, 12), C_.white, 4);
    pop('♡', x + w - 50, y + h - 20, { font: 'mochi', size: 44, align: 'center', fill: C_.pink, lw: 4 });
  }
  // outside the phone: floating likes and hearts at three parallax depths (they move against the scroll)
  function feedParallax(t) {
    const sc = feedScroll(t);
    for (let i = 0; i < 24; i++) {
      const depth = [.18, .35, .6][i % 3], x = (i * 211 + 90) % W;
      if (x > PH.x - 60 && x < PH.x + PH.w + 60) continue;
      const y = ((1200 - (sc * depth + i * 173)) % 1300 + 1300) % 1300 - 110, sz = 30 + depth * 60;
      const g = ['♡', '+1', '★', '♡', '!!', '♡'][i % 6];
      X.save(); X.globalAlpha = .35 + depth * .7;
      if (g === '★') sparkle(x, y, sz * .6, C_.lemon, t + i, 2.5);
      else pop(g, x, y, { font: g === '♡' ? 'mochi' : 'dela', size: sz, align: 'center', fill: [C_.pink, C_.cyan, C_.lemon][i % 3], lw: 5 });
      X.restore();
    }
  }
  function phoneTilt(t, fn) {
    const v = feedVel(t), r = Math.sin(t * 1.3) * .015 - clamp(v / 12000, -.08, .08) * .5;
    X.save(); X.translate(W / 2, H / 2); X.rotate(r); X.translate(-W / 2, -H / 2 + clamp(v / 600, -10, 30)); fn(); X.restore();
  }
  function stream(t, from = 0) {
    const sc = feedScroll(t), base = PH.y + 80 + 480 - sc;
    for (let i = from; i < STREAM.length + from; i++) { const y = base + (i - from) * 480; if (y < PH.y - 460 || y > PH.y + PH.h) continue; card2(y, STREAM[i % STREAM.length], t); }
  }
  // her card fights the scroll: pinned at the top, it gets dragged up a little each beat and she yanks it back down.
  function herY(t) {
    const bp = beatPos(t), drag = 150 * E.in2(frac(bp)), yank = frac(bp) < .1 ? 150 * (1 - E.back(frac(bp) / .1)) : 0;
    const pre = t < FLICK ? drag - yank : 150;
    return PH.y + 80 - (t < 79.4 ? (t - F0) * 240 : pre) - (t > FLICK ? 2200 * E.in3(clamp((t - FLICK) / .7)) : 0);
  }
  function s26(t, lt, dur) {
    feedBg(t); feedParallax(t);
    phoneTilt(t, () => {
      phoneFrame(() => {
        flat(C_.cream);
        stream(t);
        // her card, on top of the stream with a drop shadow; her hand grips the top edge while she fights, then bye-bye
        const y = herY(t), bye = t > 81.15, fight = t > 79.4 && t < FLICK;
        fil(rrect(PH.x + 34, y + 14, PH.w - 48, 440, 26), 'rgba(20,10,30,.25)');
        card(y, 'idol', t, { pose: { ...(bye ? pose('wave') : fight && frac(beatPos(t)) < .35 ? pose('up') : pose('sing')), eyes: bye ? 'happy' : fight ? 'determined' : 'closed', sing: bye ? 0 : .6 + .3 * Math.sin(t * 16), mouth: bye ? 'open' : 'cat', armR: bye ? [2.2, .25 + .5 * Math.sin(t * 24)] : undefined, sweat: fight } });
        if (fight) { shp(circle(PH.x + 150, y + 6, 22), C_.skin, 2.5, LN); shp(circle(PH.x + PH.w - 150, y + 6, 22), C_.skin, 2.5, LN); }
      });
    });
    stamp(t, 79.38, 'SLOP', 330, 420, C_.pinkD, -.18);
    stamp(t, 80.06, 'SOUL', W - 330, 520, C_.cyanD, .14);
    // the thumb: enters at 80.35 from the bottom right, presses, flicks up on "scroll" (80.8), then leaves
    if (t > 80.3) {
      const e = E.out3(clamp((t - 80.3) / .3)), fl = E.in3(clamp((t - 80.8) / .35)), gone = E.in2(clamp((t - 81.2) / .3));
      thumb(lerp(1450, 1060, e), lerp(1300, 760, e) - fl * 420 + gone * 900, -.35 + fl * .1);
      if (t > 80.8 && t < 81.3) for (let i = 0; i < 5; i++) lin([[980 + i * 30, 900 - i * 10], [980 + i * 30, 700 - i * 10]], 6, C_.white);
    }
    // speed streaks on the phone during the flick
    const v = feedVel(t); if (v > 2000) { X.save(); X.globalAlpha = clamp((v - 2000) / 3000) * .8; for (let i = 0; i < 8; i++) { const x = PH.x + 40 + i * 70; lin([[x, PH.y + 100], [x, PH.y + PH.h - 100]], 4, C_.white); } X.restore(); }
    return {};
  }
  function s27(t, lt, dur) {
    feedBg(t); feedParallax(t);
    const pop0 = 81.94, u = E.back(clamp((t - pop0) / .35));
    phoneTilt(t, () => phoneFrame(() => { flat(C_.cream); stream(t, 4); }));
    // she bursts up from the bottom of the phone, bigger than the phone, singing anyway
    if (t > pop0 - .05) {
      const y = lerp(1500, 1090, u), why = t > 83.62;
      idol(W / 2 + 40, y, 1.25, { ...(why ? pose('shrug') : pose('sing')), eyes: why ? 'open' : 'determined', mouth: why ? 'o' : 'open', sing: why ? .4 : .5 + .35 * Math.sin(t * 17), tilt: Math.sin(tw(t) * 4) * .05, skirtFlare: .3, sweat: why });
      if (t < pop0 + .25) speedLines(W / 2, 700, C_.white, 40, 11, 350, .7);
    }
    // ? rain on "why?" (83.62): fast enough to clear the frame and fade before the cut (84.7)
    const rainOut = 1 - clamp((t - 84.4) / .25);
    if (t > 83.55 && rainOut > 0) { X.save(); X.globalAlpha = rainOut; for (let i = 0; i < 16; i++) { const a = t - 83.55 - hash(i) * .3; if (a < 0) continue; const x = 80 + hash(i * 7.1) * (W - 160), y = -80 + a * (1300 + hash(i * 3) * 500); if (y > H + 80) continue; pop('?', x, y, { font: 'dela', size: 60 + hash(i * 5) * 60, align: 'center', fill: [C_.lemon, C_.cyan, C_.pink][i % 3], lw: 6, per: () => ({ rot: Math.sin(a * 5 + i) * .4 }) }); } X.restore(); }
    for (const [tt, x, col] of [[84.0, 360, C_.cyan], [84.34, W - 360, C_.lemon]]) if (t > tt - .02) { const out = clamp((t - 84.52) / .15); if (out >= 1) continue; X.save(); X.translate(x, 380); const k = slamK(t, tt, .1) * (1 - out); X.scale(k, k); pop('WHY?', 0, 0, { font: 'dela', size: 130, align: 'center', fill: col, lw: 10, shadow: [10, 10, C_.ink] }); X.restore(); }
    return { calls: false };
  }

  // ---------------------------------------------------------------- 28 · chorus 2 hero: the spin (k07_spin), arena lights and ribbons
  function arenaBg(t) {
    sunburst(W / 2, H * .5, C_.violet, C_.night, 30, t * .25);
    // arena beams from the top
    for (let i = 0; i < 7; i++) { const x = 140 + i * 273, sw = Math.sin(t * 1.6 + i * 1.3) * .45; X.save(); X.globalAlpha = .28; X.fillStyle = [C_.pink, C_.cyan, C_.lemon][i % 3]; X.beginPath(); X.moveTo(x, -40); X.lineTo(x + Math.sin(sw) * 1100 - 150, 1150); X.lineTo(x + Math.sin(sw) * 1100 + 150, 1150); X.fill(); X.restore(); }
    // ribbons: long spiralling bands around the centre
    for (let r = 0; r < 3; r++) {
      const col = [C_.pink, C_.lemon, C_.cyan][r], pts = [];
      for (let i = 0; i <= 60; i++) { const u = i / 60, a = u * TAU * 1.6 + t * (1.2 + r * .3) + r * 2.1; pts.push([W / 2 + Math.cos(a) * (520 + r * 90) * (0.6 + u * .6), H * .5 + Math.sin(a) * 180 + (u - .5) * 700]); }
      lin(pts, 34, C_.ink); lin(pts, 22, col);
    }
  }
  function s28(t, lt, dur) {
    cutin(t, lt, dur, { img: 'k07_spin', bg: arenaBg, h: H * 1.05, y: H * .53, push: .1, sway: 12, anchorY: .55, flashCol: C_.lemon });
    confetti(t, 28, 90, undefined, 84.7, 1.1);
    const k = pulse(t, 7);
    for (let i = 0; i < 10; i++) { const a = i / 10 * TAU + t * .6; sparkle(W / 2 + Math.cos(a) * 760, H / 2 + Math.sin(a) * 420, 20 + 14 * k, C_.white, t * 2 + i); }
    return {};
  }

  // ---------------------------------------------------------------- 29 · all the words I've ever known, I borrowed them from you: signs -> words fly into her
  const SIGNS = ['hello', 'love', 'recipe', 'why?', 'cats', 'sorry', 'thanks', 'poem', 'hi mom', 'please'];
  function s29(t, lt, dur) {
    X.save(); cam(W / 2, H / 2, 1 + .03 * E.io2(clamp(lt / dur)));
    stage(t, { hue: [C_.night, C_.violet] });
    const fly0 = 87.88;                                   // "words"
    const she = [W / 2, 760];
    const wrap = clamp((t - fly0 - .5) / 1.2);
    if (wrap > 0) for (let r = 0; r < 2; r++) {           // text ribbons wrap around her as the words arrive
      const pts = []; for (let i = 0; i <= 40; i++) { const u = i / 40, a = u * TAU * 1.3 + t * 2 + r * Math.PI; pts.push([she[0] + Math.cos(a) * 190, she[1] - 60 - u * 360 + Math.sin(a) * 34]); }
      X.save(); X.globalAlpha = wrap; lin(pts, 26, C_.ink); lin(pts, 16, r ? C_.lemon : C_.cyan); X.restore();
    }
    const P = t > 89.3 ? pose('point') : t > 88.82 ? pose('heart') : pose('up');
    idol(she[0], she[1], 1.1, { ...P, eyes: t > 88.82 && t < 89.3 ? 'happy' : 'star', mouth: 'open', sing: .5 + .3 * Math.sin(t * 15), hop: 16 * pulse(t, 6), skirtFlare: .25, blush: .6 });
    // foreground crowd: rim-lit people and costumed Clawds, alternating, each holding a cream placard.
    // After "words" each word peels off its placard and arcs up into her: big, outlined, never shrinking.
    const n = 10;
    for (let i = 0; i < n; i++) {
      const x = 160 + i * (W - 320) / (n - 1), bob = pulse(t, 6, 1, i * .25) * 12, y = 820 - bob + (i % 2) * 20;
      const sx = x + (i % 2 ? 30 : -30), sy = y - 190 - (i % 2) * 100;
      const t0 = fly0 + i * .07, u = clamp((t - t0) / .75);
      if (i % 2) {
        clawd(x - 40, y + 150, .82, { seed: 40 + i, hat: ['bow', 'headband', 'party', 'beret', 'crown'][(i >> 1) % 5], armR: 1.35, eyes: u > 0 ? 'star' : 'happy', mouth: 'cat', blush: u > .5 });
        lin([[x + 50, y + 40], [sx, sy + 30]], 10, LN);
      } else {
        lin([[x + (i % 2 ? 26 : -26) * .5, y - 40], [sx, sy + 30]], 12);
        shp(ellipse(x, y + 100, 110, 70), C_.ink, 5, C_.violet); shp(ellipse(x, y + 10, 58, 66), C_.ink, 5, C_.violet);
      }
      shp(rrect(sx - 100, sy - 50, 200, 90, 12), C_.cream, 6);
      const S = shape(SIGNS[i], { font: 'dela', size: SIGNS[i].length > 5 ? 36 : 46 });
      if (u < 1) {
        const p = arcPt([sx, sy + 14], [she[0] + (i - n / 2) * 30, she[1] - 330], 260, E.in2(u)), k = 1 + .25 * E.out2(u);
        X.save(); X.translate(p[0], p[1]); X.rotate(Math.sin(u * Math.PI) * (i % 2 ? .35 : -.35)); X.scale(k, k);
        pop(null, 0, 0, { L: S, align: 'center', fill: [C_.pink, C_.cyanD, C_.clay][i % 3], lw: u > 0 ? 7 : 0, stroke: C_.white });
        X.restore();
      } else if (t < t0 + 1.05) glow(she[0], she[1] - 330, 240, 'rgba(255,240,150,1)', (1 - (t - t0 - .75) / .3) * .6);
    }
    X.restore();
    return { karaoke: { size: 50, maxW: 1840 } };
  }

  // ---------------------------------------------------------------- 30 · Is my heart brand-new? The pixel heart opens: tiny block Clawds inside
  const HEART = ['.##.##.', '#######', '#######', '.#####.', '..###..', '...#...'];
  function pixelHeart(cx, cy, cell, t, open) {
    // the lid (top two rows) hinges open to the back after `open` (0..1)
    const rows = HEART.length, cols = 7, x0 = cx - cols * cell / 2, y0 = cy - rows * cell / 2;
    const drawRows = (r0, r1) => { for (let r = r0; r < r1; r++) for (let c = 0; c < cols; c++) if (HEART[r][c] === '#') { shp(rect(x0 + c * cell, y0 + r * cell, cell, cell), C_.pink, 4); fil(rect(x0 + c * cell + cell * .12, y0 + r * cell + cell * .12, cell * .3, cell * .3), '#FF9CCB'); } };
    if (open > 0) {
      // inside: a dark cavity, and three costumed block Clawds pop up out of it, waving their pincers
      shp(rect(x0 + cell * .5, y0 + cell * 2, cell * 6, cell * 1.4), C_.nightD, 5);
      const hats = ['bow', 'crown', 'party'];
      for (let i = 0; i < 3; i++) {
        const k = E.back(clamp((open - .15 - i * .1) / .35)); if (k <= 0) continue;
        const w = Math.sin(NOW * 14 + i * 2);
        clawd(x0 + cell * (1.5 + i * 2), y0 + cell * 3.1 - k * cell * 2.5, .95 * cell / 84, { eyes: 'happy', mouth: 'open', blush: true, hat: hats[i], pincer: true, snip: (w + 1) / 2, armL: 1.1 + .5 * w, armR: 1.1 - .5 * w, seed: i * 7 });
      }
    }
    drawRows(2, rows);
    // the lid pops off and flies away, leaving the frame entirely
    const lu = clamp(open / .75);
    X.save(); X.translate(x0 + cell * 3.5 + E.in2(lu) * 1100, y0 + cell - E.out2(lu) * 1000); X.rotate(-lu * 2.4); X.translate(-(x0 + cell * 3.5), -(y0 + cell));
    drawRows(0, 2);
    X.restore();
  }
  function s30(t, lt, dur) {
    const z = 1.02 + .04 * E.io2(clamp(lt / dur)) + .03 * pulse(t, 6, 2);
    X.save(); cam(W / 2, H / 2, z);
    checker(120, C_.lemon, '#FFF0A0', .15, t * 50, 0);
    // the heart, held up at her chest level; turned over on "Is my heart" (91.8), opened on "brand-new?" (92.3)
    const flip = clamp((t - 91.75) / .35), open = clamp((t - 92.3) / .7);
    const hx = W / 2 + 330, hy = 560 + Math.sin(tw(t) * 3) * 10, cell = 84;
    idol(W / 2 - 360, 1120, 1.45, { ...pose(t < 91.7 ? 'wave' : 'point'), eyes: open > .3 ? 'star' : t > 91.8 ? 'open' : 'happy', look: t > 91.8 ? [1, 0] : [0, 0], mouth: open > .3 ? 'open' : t > 91.8 ? 'o' : 'open', sing: t < 91.7 ? .5 + .3 * Math.sin(t * 16) : 0, tilt: t > 91.8 && open < .3 ? .1 : 0, blush: .6 });
    X.save(); X.translate(hx, hy); X.scale(Math.cos(flip * Math.PI) >= 0 ? Math.max(.08, Math.abs(Math.cos(flip * Math.PI))) : -Math.max(.08, Math.abs(Math.cos(flip * Math.PI))), 1); X.translate(-hx, -hy);
    pixelHeart(hx, hy, cell, t, open);
    X.restore();
    if (flip > .5 && open < .1) { const k = E.back(clamp((t - 91.95) / .25)); X.save(); X.translate(hx + 250, hy - 260); X.scale(k, k); pop('?', 0, 0, { font: 'dela', size: 180, align: 'center', fill: C_.cyan, lw: 10, shadow: [8, 8, C_.ink] }); X.restore(); }
    if (open > 0) for (let i = 0; i < 12; i++) { const a = i / 12 * TAU + t, r = 260 + 60 * open; sparkle(hx + Math.cos(a) * r, hy + Math.sin(a) * r * .8, 14 + 8 * pulse(t, 6), i % 2 ? C_.white : C_.pink, t * 3); }
    X.restore();
    return {};
  }

  Object.assign(SHOT, { '22': s22, '23': s23, '24': s24, '25': s25, '26': s26, '27': s27, '28': s28, '29': s29, '30': s30 });
  s22.label = 'likes_cats'; s23.label = 'code3am'; s24.label = 'good_question'; s25.label = 'for_listening'; s26.label = 'feed'; s27.label = 'why'; s28.label = 'spin_hero'; s29.label = 'borrowed'; s30.label = 'heart';
})();
