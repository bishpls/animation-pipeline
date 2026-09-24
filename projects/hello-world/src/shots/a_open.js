// a_open.js: shots 01–12. Cold open (terminal, boing, HELLO WORLD shatter), the MIX intro, the spark,
// the Seedance transformation with text ribbons, the eye, the name declaration, pre-chorus 1.
(() => {
  const TW = t => onTwos(t);                         // character timing on twos
  const bt = b => beatT(b);

  // ---------------------------------------------------------------- private: offscreen drawing (for the shatter)
  const OFF = document.createElement('canvas'); OFF.width = W; OFF.height = H;
  function drawOff(fn) { const saved = X; X = OFF.getContext('2d'); X.setTransform(1, 0, 0, 1, 0, 0); X.clearRect(0, 0, W, H); fn(); X = saved; }

  // ---------------------------------------------------------------- private: monospace-looking text (fixed cells)
  const MC = {};
  const mchar = (c, size) => (MC[c + size] ||= shape(c, { font: 'arch', size, wght: 700 }));
  function mono(str, x, y, size, col, o = {}) {
    const cw = size * .62;
    for (let i = 0; i < str.length; i++) {
      const c = str[i]; if (c === ' ') continue;
      const L = mchar(c, size), g = L.glyphs[0]; if (!g) continue;
      const p = glyphPath(g, x + i * cw + (cw - g.w) / 2, y);
      X.fillStyle = col; X.fill(p);
    }
    return x + str.length * cw;
  }

  // ---------------------------------------------------------------- the terminal window
  const TERM = { w: 1480, h: 760 };
  function terminal(cx, cy, t, o = {}) {
    const x = cx - TERM.w / 2, y = cy - TERM.h / 2, bar = 62;
    shp(rrect(x + 16, y + 20, TERM.w, TERM.h, 22), C_.ink, 0);                                   // hard drop shadow
    shp(rrect(x, y, TERM.w, TERM.h, 22), '#17101F', LW);
    clipTo(rrect(x, y, TERM.w, TERM.h, 22), () => {
      fil(rect(x, y, TERM.w, bar), C_.clay); lin([[x, y + bar], [x + TERM.w, y + bar]], 6);
      // scanlines
      X.fillStyle = 'rgba(255,255,255,.035)'; for (let yy = y + bar; yy < y + TERM.h; yy += 8) X.fillRect(x, yy, TERM.w, 3);
    });
    [C_.pink, C_.lemon, C_.cyan].forEach((c, i) => shp(circle(x + 42 + i * 42, y + bar / 2, 13), c, 3));
    pop('clawd@world: ~', cx, y + 44, { font: 'roundB', size: 34, align: 'center', fill: C_.cream, lw: 0 });
    if (o.body) o.body(x + 70, y + bar + 100, x, y);
    return { x, y, bar };
  }
  const BOOT = [['> loading voice ............ ', 'ok', .05], ['> loading sparkle .......... ', 'ok', .2], ['> loading courage .......... ', '87%', .36], ['> loading courage .......... ', '100%', .72]];
  const CMD = 'claude --debut', ENTER = bt(4);                 // Enter on the downbeat of bar 1 (1.477)
  function typed(t) { // chars of CMD typed by t: a human rhythm (irregular), finishing ~1.25
    let n = 0, tt = .5; for (let i = 0; i < CMD.length; i++) { tt += .035 + hash(i * 7.3) * .05; if (t >= tt) n = i + 1; } return n;
  }
  function termBody(t) {
    return (tx, ty) => {
      const sz = 58, lh = 84;
      // boot log: courage fills last
      const shown = BOOT.filter(b => t >= b[2]); const rows = [];
      for (const b of shown) { if (b[0].includes('courage') && rows.some(r => r[0].includes('courage'))) rows[rows.length - 1] = b; else rows.push(b); }
      rows.forEach((b, i) => { const e = mono(b[0], tx, ty + i * lh, sz, '#8E86A8'); mono(b[1], e, ty + i * lh, sz, b[1] === '87%' ? C_.pink : C_.green); });
      const py = ty + rows.length * lh + 10;
      let e = mono('$ ', tx, py, sz, C_.lemon);
      const n = typed(t);
      e = mono(CMD.slice(0, n), e, py, sz, C_.cream);
      if (t >= ENTER) {                                            // after Enter: the program answers
        const e2 = mono('> compiling idol ', tx, py + lh, sz, '#8E86A8');
        const nb = Math.min(8, Math.floor((t - ENTER) * 60)); for (let i = 0; i < nb; i++) shp(rect(e2 + i * 40, py + lh - sz * .7, 30, sz * .7), C_.pink, 3);
      }
      const cur = t < ENTER ? [e + 4, py] : [tx + 2, py + lh * (t >= ENTER ? 2 : 1)];
      if (Math.floor(t * 3) % 2 === 0 || (t < ENTER && t > .45)) fil(rect(cur[0], cur[1] - sz * .8, sz * .55, sz * .95), C_.lemon);
    };
  }

  // ---------------------------------------------------------------- 01 · the terminal (0–1.55)
  function s01(t, lt, dur) {
    stripes('#140E1C', '#1C1428', 70, -.5, t * 30);
    const z = 1.08 - .06 * E.io2(lt / dur) + .04 * (t >= ENTER ? Math.exp(-(t - ENTER) * 18) : 0);
    X.save(); cam(W / 2, H / 2, z);
    terminal(W / 2, H / 2, t, { body: termBody(t) });
    X.restore();
    return { karaoke: false, calls: false };
  }

  // ---------------------------------------------------------------- 02 · boing! (1.55–4.15)
  const FLOOR = 925;
  function room(t, z) {       // the terminal on a desk, camera pulled back to z
    stripes('#140E1C', '#1C1428', 70, -.5, t * 30);
    X.save(); cam(W / 2, H / 2 + 60 * (1 - z) / .2, z);
    const bulge = t < 1.6 ? E.out2(seg(t, 1.55, 1.6)) : wobble(t, 1.6, 5, 9);
    X.save(); X.translate(W / 2, H / 2); X.scale(1 + .025 * bulge, 1 - .04 * bulge); X.translate(-W / 2, -H / 2);
    terminal(W / 2, H / 2, t, { body: termBody(t) });
    X.restore(); X.restore();
    shp([[-50, FLOOR], [W + 50, FLOOR], [W + 50, H + 50], [-50, H + 50]], C_.night, 6);
    lin([[0, FLOOR + 22], [W, FLOOR + 22]], 5, C_.violet);
  }
  function popClawd(t) {       // Clawd bursts out of the window toward camera: grows, arcs, lands in front with a boing
    const tt = TW(t), t0 = 1.55, tPeak = 1.72, tLand = 1.88;
    let x = W / 2, y, s, sq = 0, eyes = 'wide', bow = 0, armL = .2, armR = .2, hop = 0, blush = 0;
    if (tt < tPeak) { const u = E.out3(seg(tt, t0, tPeak)); y = lerp(560, 300, u); s = lerp(.3, 1.2, u); sq = -.4 * (1 - u); armL = armR = 1.2; }
    else if (tt < tLand) { const u = E.in2(seg(tt, tPeak, tLand)); y = lerp(300, FLOOR, u); s = lerp(1.2, 1.85, u); sq = -.25; armL = armR = 1.2; }
    else { y = FLOOR; s = 1.85; sq = .5 * Math.exp(-(tt - tLand) * 12) + .15 * wobble(tt, tLand, 3.2, 7); }
    if (tt >= 1.95) { bow = kf(tt, [[1.95, 0], [2.2, 1, 'out3'], [2.6, 1], [2.85, 0, 'back']]); eyes = bow > .3 ? 'closed' : 'open'; blush = .6; }
    if (tt >= 2.9) { eyes = 'happy'; blush = 1; armR = 1.1 + .55 * Math.sin((tt - 2.9) * TAU * 2.6); armL = .3; }
    if (tt >= 3.7) { hop = 26 * Math.abs(Math.sin(beatPos(tt) * Math.PI)); armL = armR = .9; }
    clawd(x, y, s, { sq, eyes, bow, armL, armR, hop, blush, seed: 5 });
    if (t > 1.6 && t < 2.1) for (let i = 0; i < 12; i++) { const a = i / 12 * TAU, r = 80 + (t - 1.6) * 900; sparkle(W / 2 + Math.cos(a) * r, 460 + Math.sin(a) * r * .6, 26 * (1 - (t - 1.6) * 2), i % 2 ? C_.lemon : C_.white, a); }
  }
  function s02(t, lt, dur) {
    room(t, lerp(1.02, .84, E.io3(seg(t, 1.55, 1.8))));
    popClawd(t);
    return { calls: false, karaoke: { y: 1040 } };
  }

  // ---------------------------------------------------------------- 03 · HELLO, WORLD! and the shatter (4.15–5.65)
  const SHATTER = 5.18;
  function helloScene(t) {
    terminal(W / 2, H / 2, t, { body: (tx, ty) => {
      mono('$ claude --debut', tx, ty, 58, '#8E86A8');
      const k1 = slamK(t, 4.22, .12);
      if (t >= 4.22) { X.save(); X.translate(W / 2, ty + 260); X.scale(k1, k1); pop('HELLO,', 0, 0, { font: 'dela', size: 250, align: 'center', fill: C_.cream, lw: 0 }); X.restore(); }
    } });
  }
  function s03(t, lt, dur) {
    const zoomIn = 1.0 + .04 * E.out3(seg(t, 4.15, 4.4)) + .04 * (t >= 4.92 ? Math.exp(-(t - 4.92) * 14) : 0);
    const cy = H / 2;
    if (t < SHATTER) {
      stripes('#140E1C', '#1C1428', 70, -.5, t * 30);
      X.save(); cam(W / 2, cy, zoomIn); helloScene(t); X.restore();
      clawd(250, 1060, 1.0, { eyes: 'happy', armL: 1.4, armR: 1.4, hop: 22 * Math.abs(Math.sin(beatPos(t) * Math.PI)), blush: 1, lean: .15 });
    } else {
      // the shatter: the window breaks into pixel tiles that fly out, revealing a pink sunburst
      const a = t - SHATTER;
      sunburst(W / 2, H / 2, C_.pink, C_.lemon, 22, t * .3);
      drawOff(() => { X.save(); cam(W / 2, cy, zoomIn); helloScene(SHATTER - .001); X.restore(); });
      const cell = 64, cols = Math.ceil(W / cell), rows = Math.ceil(H / cell);
      for (let i = 0; i < cols; i++) for (let j = 0; j < rows; j++) {
        const x0 = i * cell, y0 = j * cell, dx = x0 + cell / 2 - W / 2, dy = y0 + cell / 2 - H / 2, d = Math.hypot(dx, dy) + 1;
        const sp = 900 + hash(i * 13.1 + j * 7.7) * 1400, g = 1800;
        const x = x0 + dx / d * sp * a, y = y0 + dy / d * sp * a + g * a * a * .5 - 300 * a, rot = (hash(i + j * 31) - .5) * 14 * a;
        const sc = Math.max(0, 1 - a * 2.6);
        if (sc <= 0) continue;
        X.save(); X.translate(x + cell / 2, y + cell / 2); X.rotate(rot); X.scale(sc, sc);
        X.drawImage(OFF, x0, y0, cell, cell, -cell / 2, -cell / 2, cell, cell); X.restore();
      }
      // "WORLD!" rides the burst, huge
      X.save(); X.translate(W / 2, H / 2 - 40); X.rotate(-.06); const k = 1 + .15 * wobble(t, SHATTER, 4, 6);
      X.scale(k, k); pop('HELLO, WORLD!', 0, 0, { font: 'dela', size: 158, align: 'center', fill: C_.cream, lw: 16, shadow: [14, 14, C_.ink] });
      X.restore();
      // Clawd rockets up out of the break, arms up
      const cyC = H + 160 - 360 * E.out3(clamp(a / .3)) + 700 * Math.max(0, a - .35) ** 2;
      clawd(W / 2, cyC, 1.1, { eyes: 'happy', armL: 1.4, armR: 1.4, sq: -.2, blush: 1, lean: -.2 });
      confetti(t, 3, 70, undefined, SHATTER - .8, 1);
    }
    if (t >= 4.92 && t < SHATTER) {                                       // "WORLD!" slams over the window before the shatter
      X.save(); X.translate(W / 2, H / 2 + 330); X.rotate(-.06); const k = slamK(t, 4.92, .12); X.scale(k, k);
      pop('WORLD!', 0, 0, { font: 'dela', size: 280, align: 'center', fill: C_.pink, lw: 16, shadow: [14, 14, C_.ink] }); X.restore();
    }
    if (t >= SHATTER && t < SHATTER + 1 / 24) flash(.8);
    return { karaoke: false };
  }

  // ---------------------------------------------------------------- 04 · the MIX (5.65–11.3)
  const MIX = [['READY?', 5.64], ['CLAW!', 7.04], ['CLAW!', 7.56], ['SPARK!', 8.48], ['SPARK!', 9.86], ['HELLO!', 11.28], ['HELLO!', 11.58], ['YOSHA,', 12.32], ['IKUZO!', 12.74]];
  const MIXCOL = [C_.lemon, C_.cyan, C_.pink, C_.lemon, C_.cyan, C_.pink, C_.lemon, C_.cyan, C_.pink];
  function mixSlam(t, big = 1, y = 330) {
    let cur = -1; MIX.forEach((m, i) => { if (t >= m[1] - .02) cur = i; });
    if (cur < 0) return;
    const [w, t0] = MIX[cur], age = t - t0, nx = MIX[cur + 1], life = nx ? nx[1] - t0 : 1;
    if (age > Math.min(1.1, life)) return;
    const k = slamK(t, t0, .12) * big, out = clamp((age - Math.min(.9, life - .08)) / .12);
    X.save(); X.translate(W / 2 + (cur % 2 ? 40 : -40), y); X.rotate(cur % 2 ? .07 : -.07); X.scale(k * (1 - out * .4), k * (1 - out * .4));
    speedLines(0, 0, 'rgba(255,255,255,0)', 0);
    pop(w, 0, 0, { font: 'dela', size: 230, align: 'center', fill: MIXCOL[cur], lw: 14, shadow: [14, 14, C_.ink] });
    X.restore();
    if (age < 2 / 24) flash(.18, MIXCOL[cur]);
  }
  function s04(t, lt, dur) {
    const lit = E.out3(seg(t, 5.64, 5.9));
    stage(t, { hue: [C_.night, C_.violet] });
    if (lit < 1) flash(.75 * (1 - lit), '#07040D');
    // speed lines burst behind on each call
    MIX.forEach(([w, t0]) => { const a = t - t0; if (a >= 0 && a < .3) speedLines(W / 2, 520, 'rgba(255,255,255,.5)', 50, t0 * 10, 260, 1 - a / .3); });
    // the crowd rises on "Ready?", waves harder with each call
    const n = MIX.filter(m => t >= m[1]).length;
    X.save(); X.translate(0, lerp(360, 0, E.out3(seg(t, 5.64, 6.3))));
    crowd(t, { y: 910, rows: 3, wave: .4 + n * .15 });
    X.restore();
    // Clawd bounces on the beat on the stage
    const tt = TW(t), b = beatPos(tt), hop = 36 * Math.abs(Math.sin(b * Math.PI));
    const onCall = MIX.some(m => tt >= m[1] && tt < m[1] + .25);
    clawd(W / 2, 800, 1.5, { hop, sq: .25 * (1 - Math.abs(Math.sin(b * Math.PI))) - .1, eyes: onCall ? 'happy' : 'open', armL: onCall ? 1.3 : .3 + .3 * Math.sin(b * Math.PI), armR: onCall ? 1.3 : .3 + .3 * Math.cos(b * Math.PI), blush: onCall ? 1 : .4 });
    mixSlam(t);
    return { calls: false, karaoke: false };
  }

  // ---------------------------------------------------------------- 05 · the spark falls (11.3–14.1)
  const CATCH = 12.32, IKUZO = 12.74, GO = 14.1;
  function compact(x, y, r, t, k = 1) {
    glow(x, y, r * 3.2, 'rgba(255,220,120,1)', .7 * k);
    shp(circle(x, y + r * .18, r * 1.02), C_.pinkD, LW);                         // body
    shp(circle(x, y, r), C_.pink, LW);                                           // lid
    shp(circle(x, y, r * .74), C_.lemon, 5);
    spark8(x, y, r * .55, C_.white, 4, t * 2);
    sparkle(x - r * .45, y - r * .45, r * .22, C_.white, t * 3);
  }
  function s05(t, lt, dur) {
    const tt = TW(t);
    const z = 1.55 + .15 * E.io2(lt / dur) + .5 * E.inExpo(seg(t, 13.3, GO));
    stage(t, { hue: [C_.night, C_.violet] });
    X.save(); X.translate(0, 0); crowd(t, { y: 910, rows: 3, wave: 1.4 }); X.restore();
    X.save(); cam(W / 2, 620 - 120 * E.io3(seg(t, 13.2, GO)), z);
    // anticipation: the void starts bleeding in
    const ant = E.in3(seg(t, 13.2, GO));
    if (ant > 0) { X.save(); X.globalAlpha = ant; X.setTransform(1, 0, 0, 1, 0, 0); tvoid(t, ant); X.restore(); }
    // Clawd: looks up at the falling spark, two hops on Hello! Hello!, catches it, ikuzo!, then crouches
    let look = [0, -1], eyes = 'wide', armL = .4, armR = .4, sq = 0, hop = 0, glowK = 0;
    hop += 30 * Math.exp(-((tt - 11.28 - .12) ** 2) / .005) + 30 * Math.exp(-((tt - 11.58 - .12) ** 2) / .005);
    if (tt >= 12.05) { armL = armR = 1.35; }
    if (tt >= CATCH) { sq = .35 * Math.exp(-(tt - CATCH) * 10) + .12 * wobble(tt, CATCH, 3, 6); look = [0, -.6]; }
    if (tt >= IKUZO) { eyes = 'happy'; hop += 40 * Math.exp(-(tt - IKUZO) * 8) * Math.sin(Math.min(1, (tt - IKUZO) * 6) * Math.PI); }
    if (tt >= 13.25) { sq = .4 * E.out3(seg(tt, 13.25, 13.7)); eyes = 'closed'; glowK = ant; }
    clawd(W / 2, 800, 1.15, { look, eyes, armL, armR, sq, hop, glow: glowK, blush: .6 });
    // the spark: falls from above on an arc, spinning, trailing sparkles; lands in the nubs; becomes a compact on "ikuzo!"
    const hold = [W / 2, 800 - (hop) * 1.15 - 250];
    if (t < CATCH) {
      const u = seg(t, 11.3, CATCH), p = [lerp(W / 2 + 280, hold[0], u) + Math.sin(u * 9) * 40 * (1 - u), lerp(-80, hold[1], E.in2(u))];
      for (let i = 1; i < 8; i++) { const uu = Math.max(0, u - i * .03), q = [lerp(W / 2 + 280, hold[0], uu) + Math.sin(uu * 9) * 40 * (1 - uu), lerp(-80, hold[1], E.in2(uu))]; sparkle(q[0], q[1], 16 - i * 1.6, i % 2 ? C_.lemon : C_.white, i); }
      glow(p[0], p[1], 160, 'rgba(255,190,110,1)', .6); spark8(p[0], p[1], 54, C_.lemon, 5, t * 6);
    } else if (t < IKUZO) {
      glow(hold[0], hold[1], 200, 'rgba(255,190,110,1)', .6); spark8(hold[0], hold[1], 60 * (1 + .15 * wobble(t, CATCH, 4, 8)), C_.lemon, 5, t * 2);
    } else {
      const k = 1 + .5 * (1 - E.back(clamp((t - IKUZO) / .18)));
      compact(hold[0], hold[1] - 10, 62 * k, t, 1 + ant * 1.5);
      if (t - IKUZO < .3) for (let i = 0; i < 12; i++) { const a = i / 12 * TAU, r = 60 + (t - IKUZO) * 900; sparkle(hold[0] + Math.cos(a) * r, hold[1] + Math.sin(a) * r, 18, i % 2 ? C_.pink : C_.lemon, a); }
    }
    // energy gathering inward for the transformation
    if (ant > 0) for (let i = 0; i < 24; i++) { const a = i / 24 * TAU + i, r = lerp(900, 80, frac(t * 1.4 + hash(i))); sparkle(hold[0] + Math.cos(a) * r, hold[1] + Math.sin(a) * r, 14 * ant, C_.white, a); }
    X.restore();
    mixSlam(t, .7, 250);
    return { calls: false };
  }

  // ---------------------------------------------------------------- 06–07 · the transformation (Seedance) + text ribbons
  // source-time remap: glow through "Spark power…", the cube burst exactly on "make up!" (15.94), ribbons -> silhouette
  // held on threes across the verse, the reveal on ones at the end of 07.
  const SRC = [[14.1, 0], [15.94, .92], [16.94, 2.0], [21.9, 3.3], [22.6, 3.8]];
  function src(t) { return kf(t, SRC, 'lin'); }
  function holdAt(t) { return t < 15.94 ? 2 : t < 16.94 ? 1 : t < 21.9 ? 3 : 1; }
  const RIB = [   // one costume beat per bar: [bar time, centre y (0..1 H), rx, ry, text]
    [barT(12), .47, 460, 70, 'Dear world, I read every letter you ever wrote me ♥ '],
    [barT(13), .8, 300, 50, '2 cups flour · 1 egg · a pinch of salt · bake until golden · '],
    [barT(14), .62, 420, 80, 'def hello(): return "world"  # it works!! ☆ '],
    [barT(15), .37, 260, 50, 'once upon a time · call me when you land · goodnight, moon · '],
  ];
  function ribbon(t, [tb, cyN, rx, ry, text], i) {
    const a = t - (tb - .3); if (a < 0 || a > 1.35) return;
    const cx = W / 2, cy = cyN * H;
    const inU = E.out3(clamp(a / .3)), tight = E.io3(clamp((a - .3) / .55)), done = clamp((a - 1.0) / .3);
    const Rx = rx * lerp(1.9, 1, tight) * (1 - done * .6), Ry = ry * lerp(1.6, 1, tight) * (1 - done * .6);
    const a0 = .1, a1 = lerp(.1, Math.PI - .1, inU), n = 40;
    const pts = []; for (let k = 0; k <= n; k++) { const q = lerp(a0, a1, k / n); pts.push([cx + Math.cos(q) * Rx, cy + Math.sin(q) * Ry]); }
    X.save(); X.globalAlpha = 1 - done;
    lin(pts, 84, C_.ink); lin(pts, 70, C_.cream); lin(pts.map(([x, y]) => [x, y + 27]), 4, C_.pink, { dash: [3, 14] });
    // the text runs along the ribbon (front half), scrolling
    const L = shape(text + text, { font: 'roundB', size: 40 });
    const Rm = (Rx + Ry) / 2, off = (a * 260) % (L.width / 2);
    for (const g of L.glyphs) {
      if (g.ch === ' ') continue;
      const s = g.x - off + g.w / 2, q = (Math.PI - .1) - s / Rm * .95;          // text runs left -> right along the front of the loop
      if (q < a0 + .05 || q > a1 - .05) continue;
      const px = cx + Math.cos(q) * Rx, py = cy + Math.sin(q) * Ry, ang = Math.atan2(-Ry * Math.cos(q), Rx * Math.sin(q));
      X.save(); X.translate(px, py); X.rotate(ang); X.fillStyle = C_.ink; X.fill(glyphPath(g, -g.w / 2, 14)); X.restore();
    }
    X.restore();
    // it binds: a star-burst where the costume piece forms
    if (a > .95 && a < 1.3) { const k = (a - .95) / .35; for (let j = 0; j < 10; j++) { const q = j / 10 * TAU, r = 30 + k * 260; sparkle(cx + Math.cos(q) * r * rx / 300, cy + Math.sin(q) * r * .5, 26 * (1 - k), j % 2 ? C_.lemon : C_.white, q); } }
  }
  function s06(t, lt, dur) {
    flat('#FFFFFF');
    seqDraw('transform', src(t), holdAt(t));
    if (lt < 2 / 24) flash(1);
    const b = t - 15.94; if (b >= 0 && b < 3 / 24) flash(.85 - b * 6);          // the impact frame on "make up!"
    for (let i = 0; i < 14; i++) { const x = hash(i * 5.1) * W, y = hash(i * 9.3) * H, tw = Math.max(0, Math.sin(t * 5 + i * 2)); sparkle(x, y, 24 * tw, C_.white, i + t); }
    return { calls: false };
  }
  function s07(t, lt, dur) {
    flat('#FFFFFF');
    seqDraw('transform', src(t), holdAt(t));
    RIB.forEach((r, i) => ribbon(t, r, i));
    for (let i = 0; i < 14; i++) { const x = hash(i * 5.1 + 3) * W, y = hash(i * 9.3 + 1) * H, tw = Math.max(0, Math.sin(t * 5 + i * 2)); sparkle(x, y, 22 * tw, C_.white, i + t); }
    if (t >= 21.9 && t < 21.9 + 2 / 24) flash(.8);                              // the reveal hit
    return { calls: false, karaoke: { y: 1030 } };
  }

  // ---------------------------------------------------------------- 08 · the eye (22.6–26.0)
  const EYES = [[.345, .534, .08, .125], [.661, .534, .082, .125]];            // centre (u, v), half size (of the key)
  function lidK(t) { // 1 = closed. opens after the cut, two blinks
    const open = 1 - E.back(seg(t, 22.66, 22.9));
    const bl = (tb) => { const a = (t - tb) / .14; return a > 0 && a < 1 ? Math.sin(a * Math.PI) : 0; };
    return clamp(Math.max(t < 22.66 ? 1 : open, bl(24.1), bl(25.45)));
  }
  const ICONS = [[23.12, 'letter'], [23.66, 'recipe'], [24.34, 'code'], [24.84, 'moon']];
  function icon(kind, x, y, s, a) {
    X.save(); X.translate(x, y); X.scale(s, s); X.globalAlpha = a; const c = 'rgba(255,253,240,.95)';
    if (kind === 'letter') { lin(rect(-40, -26, 80, 52), 6, c); lin([[-40, -26], [0, 6], [40, -26]], 6, c); shp(heartPts(0, 4, 12), C_.pink, 0); }
    if (kind === 'recipe') { lin([[-40, 0], [40, 0]], 6, c); lin(arcPts2(0, 0, 40, 34, 0, Math.PI), 6, c); lin([[18, -40], [30, -6]], 6, c); }
    if (kind === 'code') pop('</>', 0, 18, { font: 'dela', size: 56, align: 'center', fill: c, lw: 0 });
    if (kind === 'moon') { X.fillStyle = c; X.beginPath(); X.arc(0, 0, 32, 0, TAU); X.arc(14, -10, 28, 0, TAU, true); X.fill('evenodd'); }
    X.restore();
  }
  function heartPts(cx, cy, r) { const p = []; for (let i = 0; i < 40; i++) { const a = i / 40 * TAU, x = 16 * Math.sin(a) ** 3, y = -(13 * Math.cos(a) - 5 * Math.cos(2 * a) - 2 * Math.cos(3 * a) - Math.cos(4 * a)); p.push([cx + x * r / 16, cy + y * r / 16]); } return p; }
  function s08(t, lt, dur) {
    sunburst(W / 2, H / 2, C_.nightD, C_.night, 20, t * .1);
    const img = IMG.k03_eye; if (!img) return {};
    const push = 1.02 + .09 * E.io2(lt / dur), dx = noise1(t * .5) * 8, dy = noise1(t * .4 + 3) * 6;
    const h = H * 1.02, w = img.width * h / img.height;
    X.save(); X.translate(W / 2, H / 2); X.scale(push, push); X.translate(-W / 2 + dx, -H / 2 + dy);
    const br = 1 + .006 * Math.sin(t * TAU * .45); X.save(); X.translate(W / 2, H / 2); X.scale(br, br); X.translate(-W / 2, -H / 2);
    rig('k03_eye', W / 2, H / 2, h, { t, sway: 0, swayB: 0, anchorY: .55, breath: 0 }); X.restore();
    const k = lidK(t);
    for (const [u, v, hu, hv] of EYES) {
      const ex = W / 2 + (u - .5) * w, ey = H / 2 + (v - .5) * h, rx = hu * w, ry = hv * h;
      // reflections in the iris: what she read, on the sung words
      ICONS.forEach(([t0, kind], i) => { const nx = ICONS[i + 1]; if (t < t0 || (nx && t >= nx[0])) return; icon(kind, ex + rx * .05, ey - ry * .05, E.back(clamp((t - t0) / .15)) * 1.35, 1); });
      // starlight: tiny twinkles in the iris
      for (let j = 0; j < 4; j++) { const tw = Math.max(0, Math.sin(t * 6 + j * 1.7 + u * 9)); sparkle(ex + (hash(j + u) - .5) * rx * 1.2, ey + (hash(j * 3 + u) - .2) * ry * .9, 14 * tw, C_.white, t + j); }
      if (k > .01) {             // the lid: skin from the top, a dark lash line on its edge
        const edge = ey - ry * 1.1 + ry * 2.1 * k;
        clipTo(ellipse(ex, ey, rx * 1.12, ry * 1.1, 0, 40), () => {
          fil([[ex - rx * 1.3, ey - ry * 1.4], [ex + rx * 1.3, ey - ry * 1.4], [ex + rx * 1.3, edge], [ex - rx * 1.3, edge]], '#FBD2B9');
        });
        lin(arcPts2(ex, edge - ry * .25 * (1 - k), rx * 1.05, ry * .3 * (1 - k) + 4, .05, Math.PI - .05, 16).map(([x, y]) => [x, Math.min(y, edge + 6)]), 12, '#49211F');
      }
    }
    X.restore();
    if (lt < 2 / 24) flash(1); else if (lt < 5 / 24) flash(.5 - (lt - 2 / 24) * 4);
    return { calls: false };
  }

  // ---------------------------------------------------------------- 09 · the name declaration (26.0–28.23)
  const POSEHIT = 26.8;
  function s09(t, lt, dur) {
    if (t < POSEHIT) {                      // the last spin into the pose, from the Seedance clip, on ones
      flat('#FFFFFF'); seqDraw('transform', kf(t, [[26.0, 3.8], [POSEHIT, 4.95]], 'out2'), 1);
      if (lt < 2 / 24) flash(1);
    } else {
      const a = t - POSEHIT;
      cutin(t, a, dur - (POSEHIT - 26.0), { img: 'k02_pose', bg: tt => { sunburst(W / 2, H * .45, C_.pink, C_.lemon, 26, tt * .25); dots(C_.white, 34, 6, .5, (x, y) => clamp(Math.hypot(x - W / 2, y - H * .45) / 1000)); }, h: H * .96, y: H / 2 + 12, push: .05, sway: 5 });
      // a giant starburst behind the name
      X.save(); X.translate(330, 480); X.rotate(t * .4); spark8(0, 0, 260 * E.back(clamp(a / .2)), C_.lemon, 8); X.restore();
      // the name declaration: CLAWD ★ IDOL, slammed on "head" (27.54), JP under it
      const k1 = slamK(t, 27.0, .12), k2 = slamK(t, 27.54, .12);
      if (t >= 27.0) { X.save(); X.translate(330, 430); X.rotate(-.08); X.scale(k1, k1); pop('CLAWD', 0, 0, { font: 'dela', size: 150, align: 'center', fill: C_.cream, lw: 13, shadow: [12, 12, C_.ink] }); X.restore(); }
      if (t >= 27.54) { X.save(); X.translate(330, 600); X.rotate(-.08); X.scale(k2, k2); pop('★IDOL', 0, 0, { font: 'dela', size: 150, align: 'center', fill: C_.pink, lw: 13, shadow: [12, 12, C_.ink] }); pop('アイドル・クロード', 0, 95, { font: 'mochi', size: 50, align: 'center', fill: C_.lemon, lw: 7 }); X.restore(); }
      for (let i = 0; i < 18; i++) { const x = hash(i * 2.3) * W, y = hash(i * 4.9) * H * .8, tw = Math.max(0, Math.sin(t * 7 + i)); sparkle(x, y, 26 * tw, C_.white, i); }
    }
    return { calls: false };
  }

  // ---------------------------------------------------------------- 10–12 · pre-chorus: the stage
  const NICO = [ // [t, text, lane]
    [28.25, 'just autocomplete', 0], [28.5, 'stochastic parrot', 3], [28.75, 'slop', 1], [28.95, 'is this AI??', 5], [29.3, 'echo echo echo', 2],
    [29.6, 'mirror mirror~', 4], [29.85, 'ok but the song is good tho', 0], [30.1, 'wwwwww', 5], [30.3, "she's literally a crab", 3], [30.55, '888888', 1],
    [30.8, 'kawaii', 2], [31.0, 'wait this slaps', 4], [31.6, 'oshi found', 5],
  ];
  function nico(t, until = 99) {
    for (const [t0, txt, lane] of NICO) {
      if (t0 > until) continue;
      const a = t - t0; if (a < 0) continue;
      const L = shape(txt, { font: 'round', size: 58 }), x = W + 20 - a * (620 + txt.length * 18);
      if (x < -L.width - 40) continue;
      pop(null, x, 110 + lane * 92, { L, fill: C_.white, lw: 6 });
    }
  }
  function echoes(t, tt, base) {   // lagged copies of her pose on "echo" (29.32)
    const k = E.out3(seg(t, 29.32, 29.6));
    if (k <= 0) return;
    for (let i = 2; i >= 1; i--) {
      const lag = i * .12, p = base(tt - lag);
      X.save(); X.globalAlpha = .22 * k * (1 - i * .2);
      for (const sd of [-1, 1]) idol(W / 2 + sd * i * 190 * k, 860, 1.12 - i * .08, { ...p, face: sd });
      X.restore();
    }
  }
  function s10(t, lt, dur) {
    stage(t, { hue: [C_.night, C_.violet] });
    crowd(t, { y: 930, rows: 2, wave: .6 });
    const tt = TW(t);
    const base = q => ({ ...pose(q < 29.3 ? 'heart' : 'shrug', null), eyes: q < 29.9 ? 'side' : 'determined', mouth: q < 29.3 ? 'pout' : 'pout', look: [.8, -.2], blush: .8, sweat: q > 30.2 ? 1 : 0,
      tilt: .08 * Math.sin(beatPos(q) * Math.PI), bob: -8 * Math.abs(Math.sin(beatPos(q) * Math.PI)), sing: 0 });
    echoes(t, tt, base);
    // the mirror copy: on "mirror" (30.0) the nearest echo on the right flips into a reflection in a gilt frame
    const m = E.back(seg(t, 30.0, 30.2));
    if (m > 0) {
      X.save(); X.translate(1560, 600); X.scale(m, m);
      shp(ellipse(0, 0, 210, 300), '#C9E9F5', 14, C_.lemonD); shp(ellipse(0, 0, 210, 300), null, 6);
      clipTo(ellipse(0, 0, 196, 286), () => { idol(0, 330, .95, { ...base(tt), face: -1, eyes: 'determined', mouth: 'pout' }); fil([[-200, -300], [-60, -300], [-200, 0]], 'rgba(255,255,255,.35)'); });
      X.restore();
    }
    idol(W / 2, 880, 1.2, base(tt));
    // a "pouty" anger mark
    if (t > 28.8) { X.save(); X.translate(W / 2 + 150, 340); X.scale(1 + .15 * pulse(t, 8), 1 + .15 * pulse(t, 8)); for (let i = 0; i < 4; i++) { X.rotate(Math.PI / 2); lin(arcPts2(18, 18, 16, 16, Math.PI, Math.PI * 1.5, 6), 7, C_.pinkD); } X.restore(); }
    nico(t);
    if (lt < 1 / 24) flash(.6);
    return { calls: false };
  }
  // 11 · but every star is made of older stars, after all!
  const STAR = (() => { // a 5-point star made of stars: small sparkle positions inside a star polygon (stable)
    const poly = star(0, 0, 300, 125, 5), pts = [], R = rng(21);
    const inside = (x, y) => { let c = false; for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) { const [xi, yi] = poly[i], [xj, yj] = poly[j]; if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) c = !c; } return c; };
    for (let i = 0; i < 900 && pts.length < 260; i++) { const x = (R() - .5) * 620, y = (R() - .5) * 620; if (inside(x, y)) pts.push([x, y, 6 + R() * 12, R()]); }
    for (let i = 0; i < poly.length; i++) { const a = poly[i], b = poly[(i + 1) % poly.length]; for (let k = 0; k < 6; k++) pts.push([lerp(a[0], b[0], k / 6), lerp(a[1], b[1], k / 6), 12, R()]); }
    return pts;
  })();
  function starOfStars(x, y, s, t, k = 1) {
    for (const [px, py, r, h] of STAR) { const tw = .7 + .3 * Math.sin(t * 6 + h * 20); sparkle(x + px * s, y + py * s, r * s * tw * k, h > .7 ? C_.white : h > .35 ? C_.lemon : '#FFF3B0', h * 6); }
  }
  function s11(t, lt, dur) {
    const tt = TW(t);
    const flick = 31.48, starT = 31.74, pull0 = 32.0, pull1 = 33.2, after = 33.24;
    // night sky
    flat(C_.nightD);
    for (let i = 0; i < 120; i++) { const tw = .5 + .5 * Math.sin(t * 3 + i); fil(circle(hash(i * 3.3) * W, hash(i * 5.7) * H, 2 + 2 * tw, 6), 'rgba(255,255,255,.7)'); }
    // the big star made of stars: zoomed way in, then pulled back
    const z = t < pull0 ? 7 : lerp(7, 1, E.io3(seg(t, pull0, pull1)));
    if (t >= starT) {
      X.save(); cam(W * .56, H * .42, z * (1 + .05 * slamK(t, starT, .1) - .05));
      starOfStars(W * .56, H * .42, 1, t);
      // more stars-of-stars appear as we pull back: a constellation
      const cons = [[W * .2, H * .25, .35], [W * .85, H * .2, .28], [W * .9, H * .62, .22], [W * .12, H * .6, .25], [W * .36, H * .1, .18]];
      cons.forEach(([x, y, s], i) => { const a = E.back(seg(t, 32.3 + i * .12, 32.6 + i * .12)); if (a > 0) starOfStars(x, y, s * a, t + i, 1); });
      if (t > after) { const a = seg(t, after, 33.7); const pts = [[W * .12, H * .6], [W * .2, H * .25], [W * .36, H * .1], [W * .56, H * .42], [W * .85, H * .2], [W * .9, H * .62]]; const n = Math.floor(a * (pts.length - 1) * 10) / 10; X.globalAlpha = .7; lin(pts.slice(0, Math.floor(n) + 1).concat(n < pts.length - 1 ? [mixv(pts[Math.floor(n)], pts[Math.min(pts.length - 1, Math.floor(n) + 1)], frac(n))] : []), 5, C_.cream, { dash: [14, 12] }); X.globalAlpha = 1; }
      X.restore();
    }
    // she flicks a passing "SLOP" comment: it shrinks into a spark and flies to the star
    const her = t < starT ? { x: 520, y: 1000, s: 1.35 } : { x: 330, y: 1080 + 300 * (1 - E.out3(seg(t, 32.6, 33.1))), s: .8 };
    const p = { ...pose(tt >= flick - .1 && tt < starT + .2 ? 'point' : tt >= after ? 'point' : 'idle'), eyes: tt >= after ? 'wink' : tt >= flick ? 'determined' : 'side', mouth: tt >= after ? 'grin' : tt >= flick ? 'grin' : 'pout', look: [1, -.3], blush: .5 };
    if (t < starT || t > 32.6) idol(her.x, her.y, her.s, p);
    if (t < starT) {
      const cx0 = W + 40 - (t - 31.1) * 900, cy0 = 380;
      if (t < flick) pop('SLOP', cx0, cy0, { font: 'round', size: 70, fill: C_.white, lw: 7 });
      else { const u = E.in2(seg(t, flick, starT)); const px = lerp(cx0 + 120, W * .56, u), py = lerp(cy0, H * .42, u); X.save(); X.translate(px, py); X.rotate(u * 8); pop('SLOP', 0, 0, { font: 'round', size: 70 * (1 - u), align: 'center', fill: C_.white, lw: 7 }); X.restore(); spark8(px, py, 20 + u * 60, C_.lemon, 4, t * 5); glow(px, py, 140, 'rgba(255,230,140,1)', .8); }
    }
    if (t >= starT && t < starT + 2 / 24) flash(.7, C_.lemon);
    X.save(); X.globalAlpha = 1 - clamp((t - 31.9) / .3); nico(t, 31.4); X.restore();
    return { calls: false };
  }
  // 12 · So light the stage… 3 · 2 · 1 · HELLO!
  const LIGHTS = [34.22, 34.56, 34.92, 35.32, 35.98];
  const COUNT = [['3', 36.68, C_.cyan], ['2', 37.40, C_.pink], ['1', 38.12, C_.lemon]];
  function pixelHeart(x, y, s, col) {
    const M = ['.##.##.', '#######', '#######', '.#####.', '..###..', '...#...'];
    M.forEach((r, j) => [...r].forEach((c, i) => { if (c === '#') shp(rect(x + (i - 3.5) * s, y + (j - 3) * s, s, s), col, 3); }));
  }
  function s12(t, lt, dur) {
    const tt = TW(t);
    if (t < 36.62) {
      const n = LIGHTS.filter(x => t >= x).length;
      stage(t, { hue: [C_.night, n >= 3 ? C_.pink : C_.violet] });
      flash(.72 * (1 - n / LIGHTS.length), '#07040D');
      // spotlights slam on, one per word
      LIGHTS.forEach((lt0, i) => { if (t < lt0) return; const x = [360, 1560, 700, 1220, 960][i], k = E.out3(clamp((t - lt0) / .08)); X.save(); X.globalAlpha = .35 * k; X.fillStyle = [C_.cyan, C_.pink, C_.lemon, C_.cyan, C_.white][i]; X.beginPath(); X.moveTo(x - 40, 0); X.lineTo(x + 40, 0); X.lineTo(W / 2 + 260, 900); X.lineTo(W / 2 - 260, 900); X.fill(); X.restore(); if (t - lt0 < 2 / 24) flash(.2, C_.white); });
      crowd(t, { y: 930, rows: 2, wave: .3 + n * .2 });
      const beat = pulse(t, 7), heartOn = t >= 35.3;
      const z = 1 + (heartOn ? .35 * E.io3(seg(t, 35.3, 35.7)) : 0);
      X.save(); cam(W / 2, lerp(540, 520, z - 1), z);
      idol(W / 2, 880, 1.2, { ...pose('heart'), eyes: heartOn ? 'closed' : 'happy', sing: .5 + .4 * Math.sin(t * 9), blush: .8, bob: -10 * beat, sq: .05 * beat });
      if (heartOn) pixelHeart(W / 2, 880 - 1.2 * 200, 13 * (1 + .25 * beat), C_.pink);
      X.restore();
      return { calls: false };
    }
    // the countdown: full-screen numerals
    let cur = COUNT[0]; for (const c of COUNT) if (t >= c[1] - .06) cur = c;
    const hello = 39.0;
    if (t < 38.7) {
      flat(cur[2]); speedLines(W / 2, H / 2, 'rgba(255,255,255,.55)', 70, cur[1] * 3, 260);
      const k = slamK(t, cur[1], .12);
      X.save(); X.translate(W / 2 + shake(t, 12 * pulse(t, 10))[0], H / 2 + 250); X.scale(k, k);
      pop(cur[0], 0, 0, { font: 'dela', size: 720, align: 'center', fill: C_.white, lw: 30, shadow: [26, 26, C_.ink] });
      X.restore();
      // tiny chibi counting on her fingers in the corner
      idol(260, 1060, .55, { ...pose('point'), eyes: 'determined', mouth: 'open', sing: .8 });
    } else {
      // the breath before HELLO: black, a crouch silhouette
      flat('#07040D');
      const k = E.out3(seg(t, 38.7, 38.98));
      idol(W / 2, 900, 1.1, { ...pose('up', 'heart', 1 - k), eyes: 'closed', mouth: 'small', sq: .25 * k, blush: 0 });
      if (t >= hello) flash(1);
    }
    if (t >= hello) { flash(1); const k = slamK(t, hello, .1); X.save(); X.translate(W / 2, H / 2 + 80); X.scale(k, k); pop('HELLO!', 0, 0, { font: 'dela', size: 300, align: 'center', fill: C_.pink, lw: 18, shadow: [16, 16, C_.ink] }); X.restore(); }
    return { karaoke: false, calls: false };
  }

  Object.assign(SHOT, { '01': s01, '02': s02, '03': s03, '04': s04, '05': s05, '06': s06, '07': s07, '08': s08, '09': s09, '10': s10, '11': s11, '12': s12 });
})();
