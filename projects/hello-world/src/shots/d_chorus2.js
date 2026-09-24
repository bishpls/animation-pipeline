// d_chorus2.js: shots 31–38. Chorus 2 in the arena (for you / phones / sparks / crowd / bow) and the dance break
// with the P(doom) callback and the P(DEBUT) meter.
(() => {
  const BT = b => beatT(b);                        // beat -> time
  const kick = (t, times, amt = .05, d = 7) => times.reduce((a, t0) => a + (t >= t0 ? amt * Math.exp(-(t - t0) * d) : 0), 0);

  // ---------------------------------------------------------------- shared: arena
  function beams(t, n = 10, cols = [C_.pink, C_.cyan, C_.lemon], a = .2, top = -40) {
    X.save(); X.globalCompositeOperation = 'lighter';
    for (let i = 0; i < n; i++) {
      const x = (i + .5) / n * W, sw = Math.sin(t * 1.1 + i * 1.7) * .5 + Math.sin(beatPos(t) * Math.PI / 2 + i) * .15;
      X.globalAlpha = a; X.fillStyle = cols[i % cols.length];
      X.beginPath(); X.moveTo(x, top); X.lineTo(x + Math.sin(sw) * 1300 - 110, H + 100); X.lineTo(x + Math.sin(sw) * 1300 + 110, H + 100); X.fill();
    }
    X.restore();
  }
  // a far crowd: penlight dots in perspective rows (cheap)
  function penField(t, o = {}) {
    const y0 = o.y0 ?? 560, rows = o.rows ?? 12, cols = o.cols || [C_.pink, C_.cyan, C_.lemon];
    for (let r = 0; r < rows; r++) {
      const k = r / (rows - 1), yy = y0 + Math.pow(k, 1.6) * (H - y0 + 60), sz = .25 + k * 1.1, n = Math.round(70 - k * 40);
      for (let i = 0; i < n; i++) {
        const x = (i + .5 + (r % 2) * .5) / n * (W + 120) - 60, ph = beatPos(t) + i * .09 + r * .31, sw = Math.sin(ph * Math.PI) * .5;
        const L = 40 * sz, hx = x + Math.sin(sw) * L, hy = yy - Math.cos(sw) * L;
        const c = cols[(i * 7 + r * 3) % cols.length];
        lin([[x, yy], [hx, hy]], Math.max(2, 7 * sz), c);
        if (sz > .6) shp(ellipse(x, yy + 26 * sz, 26 * sz, 32 * sz), C_.nightD, 0);
      }
    }
  }
  // render an idol into an offscreen canvas (for screens): swap X, draw, swap back
  const OFF = document.createElement('canvas'); OFF.width = 360; OFF.height = 420;
  function idolSnapshot(o) {
    const c = OFF.getContext('2d'), keep = X;
    c.setTransform(1, 0, 0, 1, 0, 0); c.clearRect(0, 0, 360, 420);
    const g = c.createLinearGradient(0, 0, 0, 420); g.addColorStop(0, C_.pink); g.addColorStop(1, C_.violet); c.fillStyle = g; c.fillRect(0, 0, 360, 420);
    X = c; try { X.save(); idol(180, 560, .78, o); X.restore(); } finally { X = keep; }
    return OFF;
  }

  // ---------------------------------------------------------------- 31 · I don't know, but I made this song for you! (For you!)
  // Reads: (1) 93.3–94.5 a shrug on the arena stage, sweat drop; (2) 94.5–95.1 hands swing forward, offering;
  //        (3) 95.1 CUT on "for": the arena from above; 95.4 the penlights snap to spell FOR YOU; (4) hold, call stamp.
  function s31(t, lt, dur) {
    const tt = onTwos(t);
    if (t < 95.1) {
      const [sx, sy] = shake(t, 4 * kick(t, [93.3, 94.5], 1, 9));
      X.save(); cam(W / 2 + sx, 560 + sy, 1.05 + .04 * seg(t, 93.3, 95.1));
      stage(t, { hue: [C_.night, C_.pink] }); beams(t, 8, [C_.pink, C_.cyan], .16);
      crowd(t, { y: 930, rows: 2 });
      const offer = E.back(seg(tt, 94.45, 94.75));
      const p = offer > 0 ? pose('shrug', 'offer', offer) : pose('shrug');
      const shrugUp = Math.sin(clamp((tt - 93.3) / .6) * Math.PI) * 14;
      idol(W / 2, 830, 1.2, { ...p, eyes: offer > .5 ? 'happy' : 'open', mouth: offer > .5 ? 'open' : 'cat', sing: offer > .5 ? .7 : 0, sweat: offer < .5, bob: -shrugUp, tilt: offer > .5 ? 0 : -.1 * Math.sin(tt * 4) });
      if (offer > .5) {                                // she holds out the song: a CD with a spark on it
        const cy = 640, k = E.back(seg(tt, 94.6, 94.9));
        X.save(); X.translate(W / 2, cy); X.scale(k, k); X.rotate(tt * 1.5);
        shp(circle(0, 0, 70), C_.white, 6); fil(circle(0, 0, 60), C_.cyan); spark8(0, 0, 38, C_.lemon, 4); shp(circle(0, 0, 12), C_.white, 3);
        X.restore();
        for (let i = 0; i < 6; i++) sparkle(W / 2 + Math.cos(i + tt * 2) * 130, cy + Math.sin(i * 2 + tt * 2) * 90, 16 * k, C_.lemon, i);
      }
      X.restore();
      return {};
    }
    // the arena from above: penlights snap to spell FOR YOU on "you!" (95.4)
    const u = seg(t, 95.1, dur + 93.3), z = 1 + .05 * u + kick(t, [95.4, 95.7], .04);
    X.save(); cam(W / 2, H / 2, z);
    flat(C_.nightD); beams(t, 6, [C_.violet, C_.pink], .1, -200);
    let L = shape('FOR YOU', { font: 'dela', size: 300, track: .04 }); L = shape('FOR YOU', { font: 'dela', size: 300 * Math.min(1, W * .86 / L.width), track: .04 }); const x0 = W / 2 - L.width / 2, yb = 690;
    const word = new Path2D(); L.glyphs.forEach(g => { if (g.ch !== ' ') word.addPath(glyphPath(g, x0 + g.x, yb + g.y)); });
    const cols = 64, rows = 24, sp = W / cols;
    for (let r = 0; r < rows; r++) for (let i = 0; i < cols; i++) {
      const x = (i + .5 + (r % 2) * .25) * sp, y = 130 + r * 34;
      X.save(); X.setTransform(1, 0, 0, 1, 0, 0); const inside = X.isPointInPath(word, x, y); X.restore();
      const delay = Math.abs(i - cols / 2) * .006 + Math.abs(r - rows / 2) * .004, on = inside && t >= 95.4 + delay;
      const ph = beatPos(t) + i * .1 + r * .2, bob = Math.sin(ph * Math.PI) * 5;
      if (on) { glow(x, y, 34, 'rgba(255,228,92,1)', .5); fil(circle(x, y, 11, 12), C_.lemon); fil(circle(x - 3, y - 3, 4, 8), C_.white); }
      else { X.globalAlpha = t >= 95.4 ? .3 : .75; fil(circle(x, y + bob, 7, 10), [C_.pink, C_.cyan, C_.violet][(i + r * 2) % 3]); X.globalAlpha = 1; }
    }
    X.restore();
    if (t >= 95.4 && t < 95.4 + 2 / 24) flash(.6, C_.lemon);
    return {};
  }

  // ---------------------------------------------------------------- 32 · Hello, world! (Hello!) Can you hear me through?
  // Reads: (1) 96.0 a sea of phones rises in a wave, every screen shows her; (2) 96.7 camera kick on the call;
  //        (3) 97.4 one phone near camera: inside it she cups her ear, "can you hear me through?"; push in.
  function s32(t, lt, dur) {
    const tt = onTwos(t), ear = seg(tt, 97.25, 97.55);
    const snap = idolSnapshot({ ...(ear > .5 ? pose('idle', 'cupEar', E.back(ear)) : pose('sing')), eyes: ear > .5 ? 'side' : 'happy', mouth: ear > .5 ? 'o' : 'open', sing: ear > .5 ? .3 : .6 + .3 * pulse(t, 5), look: ear > .5 ? [1, 0] : [0, 0] });
    const push = 1 + .5 * E.in3(seg(t, 97.4, 98.9)), z = push + kick(t, [96.0, 96.7], .05);
    X.save(); cam(W / 2, H / 2 + 60 * seg(t, 97.4, 98.9), z);
    flat(C_.night); beams(t, 8, [C_.pink, C_.cyan], .14);
    // rows of phones, far -> near; each lifts on the "Hello!" wave (from the centre outward)
    const rows = 6;
    for (let r = 0; r < rows; r++) {
      const k = r / (rows - 1), y = 380 + Math.pow(k, 1.4) * 700, s = .28 + k * .95, n = Math.round(22 - k * 15);
      for (let i = 0; i < n; i++) {
        const x = (i + .5 + (r % 2) * .5) / n * (W + 200) - 100;
        const lift = E.back(seg(t, 96.0 + Math.abs(x - W / 2) / W * .5 + (rows - r) * .03, 96.35 + Math.abs(x - W / 2) / W * .5 + (rows - r) * .03));
        const sway = Math.sin(beatPos(t) * Math.PI / 2 + i + r) * 6 * s;
        const py = y + (1 - lift) * 140 * s, pw = 110 * s, ph = 190 * s;
        X.save(); X.translate(x + sway, py); X.rotate(Math.sin(i * 1.3 + r) * .08);
        // the hand
        shp(blob([[-pw * .35, ph * .35], [pw * .35, ph * .35], [pw * .3, ph * .75], [-pw * .3, ph * .75]], 3), C_.skinD, 4 * s);
        shp(rrect(-pw / 2, -ph / 2, pw, ph, 14 * s), C_.ink, 5 * s);
        if (s > .45) X.drawImage(snap, -pw / 2 + 6 * s, -ph / 2 + 10 * s, pw - 12 * s, ph - 20 * s);
        else fil(rrect(-pw / 2 + 5 * s, -ph / 2 + 8 * s, pw - 10 * s, ph - 16 * s, 8 * s), [C_.pink, C_.cyan][(i + r) % 2]);
        X.restore();
      }
    }
    // the hero phone (near camera) rises on "Can" (97.4)
    const hp = E.back(seg(t, 97.3, 97.6));
    if (hp > 0) {
      const pw = 460, ph = 780, py = H / 2 + 80 + (1 - hp) * 700;
      X.save(); X.translate(W / 2, py); X.rotate(-.04);
      shp(blob([[-150, 250], [150, 250], [190, 600], [-190, 600]], 3), C_.skin, 8);
      shp(rrect(-pw / 2, -ph / 2, pw, ph, 44), C_.ink, 9);
      X.drawImage(snap, -pw / 2 + 18, -ph / 2 + 34, pw - 36, ph - 68);
      fil(rrect(-50, -ph / 2 + 12, 100, 14, 7), '#333');
      X.restore();
      // sound waves out of the phone toward her ear
      for (let k = 0; k < 3; k++) { const v = frac(t * 1.6 + k / 3); X.globalAlpha = 1 - v; lin(arcPts2(W / 2 + 60, py - 120, 120 + v * 260, 120 + v * 260, -.6, .6), 8, C_.lemon); X.globalAlpha = 1; }
    }
    X.restore();
    return {};
  }

  // ---------------------------------------------------------------- 33 · Every little spark I've got, I'm giving it to you!
  // Reads: (1) 98.9 night sky, she throws a spark up from the stage; (2) each beat a ✳ firework bursts;
  //        (3) 100.3 "giving it to you": the bursts grow and rain down; (4) 101.0 "you!" a giant ✳ fills the frame -> white.
  function firework(t, t0, x, y, col, big = 1, seed = 0) {
    const lt = t - t0;
    if (lt < -.45 || lt > 1.6) return;
    if (lt < 0) {                                   // the rising trail
      const u = 1 + lt / .45, yy = lerp(H + 40, y, E.out2(u));
      lin([[x, yy], [x + 4, yy + 90]], 6, col); sparkle(x, yy, 14, C_.white, lt * 20);
      return;
    }
    const u = E.out3(clamp(lt / .9)), fade = 1 - clamp((lt - .8) / .8);
    X.save(); X.globalAlpha = fade;
    glow(x, y, 300 * big * u, col, .5);
    for (let i = 0; i < 10; i++) {
      const a = i / 10 * TAU + seed, r = 260 * big * u, fall = lt * lt * 60;
      spark8(x + Math.cos(a) * r, y + Math.sin(a) * r + fall, (26 - 10 * u) * big, i % 2 ? col : C_.white, 3, lt * 6 + i);
      lin([[x + Math.cos(a) * r * .5, y + Math.sin(a) * r * .5 + fall * .5], [x + Math.cos(a) * r * .85, y + Math.sin(a) * r * .85 + fall]], 5 * big, col);
    }
    spark8(x, y, 70 * big * (1 - u * .5), C_.lemon, 5, lt * 3);
    X.restore();
  }
  function s33(t, lt, dur) {
    const tt = onTwos(t);
    X.save(); cam(W / 2, H / 2, 1 + .04 * seg(t, 98.9, 101.6) + kick(t, [98.9, 100.3], .04));
    flat(C_.nightD);
    for (let i = 0; i < 90; i++) { const x = hash(i * 3.3) * W, y = hash(i * 5.1) * 650; sparkle(x, y, 3 + 5 * hash(i) * (.6 + .4 * Math.sin(t * 5 + i)), C_.cream, i); }
    const cols = [C_.pink, C_.cyan, C_.lemon, C_.clayL];
    for (let b = 280; b <= 286; b++) {
      const t0 = BT(b), x = W * (.2 + hash(b * 1.7) * .6), y = 180 + hash(b * 2.9) * 280;
      firework(t, t0, x, y, cols[b % 4], b >= 284 ? 1.35 : 1, b);
    }
    // the stage at the bottom: her silhouette-lit, throwing sparks up on each beat
    beams(t, 6, [C_.lemon, C_.pink], .08, H);
    shp([[-100, 900], [W + 100, 900], [W + 100, H + 100], [-100, H + 100]], C_.night, 6);
    const thr = frac(beatPos(t)), up = thr < .3;
    idol(W / 2, 960, .75, { ...pose(up ? 'up' : 'wave'), eyes: 'happy', mouth: 'open', sing: .7, hop: up ? 10 : 0, skirtFlare: up ? .5 : .2 });
    X.restore();
    // the giant ✳ on "you!" (101.0): spins up to fill the frame, then the frame goes white
    const g = seg(t, 100.95, 101.55);
    if (g > 0) { spark8(W / 2, H / 2, 60 + E.in3(g) * 2600, C_.lemon, 10, g * 3); if (g > .75) flash((g - .75) * 4, C_.white); }
    return {};
  }

  // ---------------------------------------------------------------- 34 · Hello, world! (Hello!) Nice to meet you too,
  // Reads: (1) 101.6 from the stage looking out: the audience is block Clawds AND people, side by side;
  //        (2) the call "(Hello!)" 102.3 kick; (3) 103.1 "Nice to meet you too": everyone waves; a Clawd blushes, a kid hugs one.
  function fan(x, y, s, v, t, wave) {
    const cols = [C_.violet, C_.cyanD, C_.pinkD, C_.lemonD, '#4B6BD8'], hair = [C_.ink, '#5A3A2A', C_.cream, '#2B2B55', '#8A3B2A'];
    X.save(); X.translate(x, y); X.scale(s, s);
    shp(blob([[-60, 0], [-52, -120], [52, -120], [60, 0]], 3), cols[v % 5], 6);
    const armA = wave ? -.3 + Math.sin(t * 12 + v) * .35 : .2;
    X.save(); X.translate(40, -110); X.rotate(-2.5 + armA); lin([[0, 0], [0, 80]], 30, C_.ink); lin([[0, 0], [0, 80]], 18, C_.skin); shp(circle(0, 88, 16), C_.skin, 4); X.restore();
    shp(circle(0, -170, 58), C_.skin, 6);
    shp(blob([[-62, -170], [-58, -228], [0, -246], [58, -228], [62, -170], [30, -205], [-20, -200]], 3), hair[v % 5], 6);
    lin(arcPts2(-20, -170, 10, 8, Math.PI * 1.1, Math.PI * 1.9), 5); lin(arcPts2(20, -170, 10, 8, Math.PI * 1.1, Math.PI * 1.9), 5);
    shp(blob([[-14, -140], [14, -140], [0, -122]], 3), C_.pinkD, 3);
    X.restore();
  }
  function s34(t, lt, dur) {
    const tt = onTwos(t), wave = tt >= 103.05;
    const [sx, sy] = shake(t, 6 * kick(t, [102.3], 1, 8));
    X.save(); cam(W / 2 + sx, H / 2 + sy - 30 * seg(t, 101.6, 104.5), 1.02 + .05 * seg(t, 101.6, 104.5));
    flat(C_.night); beams(t, 8, [C_.pink, C_.cyan, C_.lemon], .12); penField(t, { y0: 300, rows: 6 });
    // three rows of audience, far -> near; alternate people and block Clawds
    for (let r = 0; r < 3; r++) {
      const s = .55 + r * .28, y = 640 + r * 190, n = 7 - r;
      for (let i = 0; i < n; i++) {
        const x = (i + .5 + (r % 2) * .35) / n * W, v = i * 3 + r, hop = Math.max(0, Math.sin((beatPos(tt) + i * .5 + r * .3) * Math.PI)) * 14;
        const w = wave && tt >= 103.05 + i * .04;
        if ((i + r) % 2 === 0) clawd(x, y - hop, s * .95, { eyes: w ? 'happy' : 'open', armL: w ? 1.2 + Math.sin(t * 12 + i) * .4 : .3, armR: w ? .9 : .3, blush: w && i === 1 ? 1 : 0, seed: v });
        else fan(x, y - hop, s, v, t, w);
      }
    }
    X.restore();
    if (wave) for (let i = 0; i < 8; i++) { const a = seg(t, 103.1 + i * .05, 103.5 + i * .05); if (a > 0 && a < 1) X.save(), X.globalAlpha = 1 - a, pop('♡', 200 + i * 220, 700 - a * 220, { font: 'mochi', size: 70, fill: C_.pink, lw: 6, align: 'center' }), X.restore(); }
    return {};
  }

  // ---------------------------------------------------------------- 35 · hajimemashite, I made this song for you!
  // Reads: (1) 104.5 a deep ojigi bow, confetti cannons fire; (2) 105.7 she pops up, hands to her heart; (3) 106.7 "you!" kick, sparkle.
  function s35(t, lt, dur) {
    const tt = onTwos(t);
    X.save(); cam(W / 2, 560, 1.12 - .06 * seg(t, 104.5, 107.29) + kick(t, [104.5, 106.7], .05));
    stage(t, { hue: [C_.night, C_.lemon] }); beams(t, 8, [C_.lemon, C_.pink], .15);
    const bow = seg(tt, 104.45, 104.75) * (1 - seg(tt, 105.55, 105.8)), up = E.back(seg(tt, 105.6, 105.9));
    idol(W / 2, 860, 1.25, { ...(up > 0 ? pose('bow', 'heart', up) : pose('bow')), eyes: up > .5 ? 'happy' : 'closed', mouth: up > .5 ? 'open' : 'small', sing: up > .5 ? .6 : 0, bob: bow * 150, sq: bow * .32, tilt: 0, blush: .8, hop: up > 0 && up < 1 ? 20 * Math.sin(up * Math.PI) : 0 });
    crowd(t, { y: 950, rows: 2 });
    X.restore();
    if (t >= 104.55 && t < 105.6) { const k = slamK(t, 104.55, .12); X.save(); X.translate(1300, 330); X.rotate(.12); X.scale(k, k); pop('ペコッ', 0, 0, { font: 'mochi', size: 120, align: 'center', fill: C_.pink, lw: 10, shadow: [8, 8, C_.ink] }); X.restore(); }
    confetti(t, 35, 90, undefined, 104.5, 1.1);
    if (t > 106.7) for (let i = 0; i < 5; i++) sparkle(W / 2 + Math.cos(i * 1.3) * 300, 360 + Math.sin(i * 2.1) * 160, 30 * (1 - seg(t, 106.7, 107.29)), C_.white, i);
    return {};
  }

  // ---------------------------------------------------------------- the formation dance (36, and 38's reprise)
  // Chant words slam full-frame one per shout; the SD idol leads centre, block Clawd backups do the same claw moves
  // in canon (each an eighth later than the one inside it), so the line ripples outward.
  const CHANT36 = [[107.6, 'CLAW!'], [108.3, 'CLAW!'], [109.0, 'SNIP-SNIP!']];
  const CHANT38 = [[116.1, 'CLAW!'], [116.8, 'CLAW!'], [117.5, 'SNIP-SNIP!'], [118.2, 'CLAWD-UP!']];
  function danceMove(t, chant) {                    // which move is live at t: claw (snap on eighths), up (the finale)
    let cur = null; for (const c of chant) if (t >= c[0] - .05) cur = c;
    if (!cur) return { m: 'idle' };
    if (cur[1] === 'CLAWD-UP!') return { m: 'up', a: t - cur[0] };
    const snip = cur[1] === 'SNIP-SNIP!';
    const open = snip ? Math.floor((t - cur[0]) / (BEAT / 2)) % 2 === 0 : (t - cur[0]) < .18;
    return { m: open ? 'clawOpen' : 'claw', a: t - cur[0], side: cur[1] === 'CLAW!' ? (chant.indexOf(cur) % 2 ? 1 : -1) : 0 };
  }
  function formation(t, chant, o = {}) {
    const tt = onTwos(t);
    // background: a scrolling checker that flips colour on each shout
    let k = 0; for (const c of chant) if (t >= c[0]) k++;
    const pal = [[C_.pink, C_.pinkD], [C_.cyan, C_.cyanD], [C_.lemon, C_.lemonD], [C_.violet, C_.night], [C_.pink, C_.lemon]][k % 5];
    checker(120, pal[0], pal[1], .25, tt * 160, tt * 60);
    // the chant word, huge, behind the dancers
    let cw = null; for (const c of chant) if (t >= c[0] - .02) cw = c;
    if (cw) {
      const s = slamK(t, cw[0], .12);
      X.save(); X.translate(W / 2, 330); X.scale(s, s); X.rotate(-.05);
      pop(cw[1], 0, 0, { font: 'dela', size: cw[1].length > 7 ? 230 : 330, align: 'center', fill: C_.white, lw: 16, shadow: [16, 16, C_.ink] });
      X.restore();
    }
    // the floor strip
    shp([[-100, 900], [W + 100, 900], [W + 100, H + 100], [-100, H + 100]], C_.ink, 0);
    // backups: block Clawds, 3 each side, canon-offset by an eighth per step outward
    for (let j = 1; j <= 3; j++) for (const side of [-1, 1]) {
      const d = danceMove(tt - j * BEAT / 2, chant), x = W / 2 + side * (250 + j * 205), y = 945 - j * 10;
      const hop = d.m === 'up' ? 40 * Math.sin(clamp(d.a / .3) * Math.PI) : Math.max(0, Math.sin((beatPos(tt) - j * .5) * Math.PI)) * 16;
      const armUp = d.m === 'up' ? 2.2 : d.m === 'clawOpen' ? 1.3 : d.m === 'claw' ? 1.0 : .3;
      clawd(x, y - hop, 1.0 - j * .1, { eyes: d.m === 'up' ? 'happy' : 'open', armL: armUp, armR: armUp, sq: d.m === 'clawOpen' ? .08 : 0, lean: (d.side || 0) * .12, seed: j * 7 + side });
    }
    // the lead
    const d = danceMove(tt, chant);
    const lp = d.m === 'up' ? pose('up') : d.m === 'idle' ? pose('idle') : pose(d.m);
    const hop = d.m === 'up' ? 50 * Math.sin(clamp(d.a / .35) * Math.PI) : Math.max(0, Math.sin(beatPos(tt) * Math.PI)) * 12;
    idol(W / 2 + (d.side || 0) * 24, 950, 1.1, { ...lp, eyes: d.m === 'up' ? 'happy' : 'star', mouth: 'grin', sing: .5, hop, lean: (d.side || 0) * .1, skirtFlare: d.m === 'up' ? .6 : .2, hairLift: d.m === 'up' ? .5 : 0 });
    // snip sparks at the claws on each snap
    if (d.m === 'claw' && d.a < .12) for (const side of [-1, 1]) sparkle(W / 2 + side * 150, 540, 34, C_.white, t * 9);
    if (d.m === 'up' && d.a < .4) flash(.35 * (1 - d.a / .4), C_.white);
  }

  // ---------------------------------------------------------------- 36 · (Claw! Claw! Snip-snip!)
  function s36(t, lt, dur) {
    const z = 1 + kick(t, CHANT36.map(c => c[0]), .05);
    X.save(); X.translate(W / 2, H / 2); X.scale(z, z); X.translate(-W / 2, -H / 2);
    formation(t, CHANT36);
    X.restore();
    // out: an alarm siren sweeps in over the last half-beat (the P(doom) meter is coming)
    const al = seg(t, 110.1, 110.4); if (al > 0) flash(al * .5, '#E0303A');
    return { calls: false };
  }

  // ---------------------------------------------------------------- the meters
  function meter(x, y, s, v, o = {}) {           // a stage thermometer on wheels. v: 0..1 fill. o: { label, col, glass, readout, alarm }
    X.save(); X.translate(x, y); X.scale(s, s); X.rotate(o.rot || 0);
    const col = o.col || '#E0303A';
    // wheels + base
    shp(rrect(-110, -40, 220, 50, 16), C_.ink, 0); fil(rrect(-104, -36, 208, 42, 14), '#5A4A6A');
    for (const wx of [-70, 70]) { X.save(); X.translate(wx, 14); X.rotate(o.roll || 0); shp(circle(0, 0, 26), '#3A3050', 5); lin([[-18, 0], [18, 0]], 5, C_.cream); X.restore(); }
    // the tube
    const th = 520, tw = 70;
    shp(rrect(-tw / 2, -40 - th, tw, th + 10, tw / 2), C_.white, 7);
    shp(circle(0, -40, 72), C_.white, 7);
    const lv = clamp(v);
    clipTo(rrect(-tw / 2 + 12, -40 - th + 12, tw - 24, th, (tw - 24) / 2).concat([]), () => fil(rect(-tw, -40 - (th - 20) * lv, tw * 2, th), col));
    shp(circle(0, -40, 56), col, 0);
    fil(rrect(-8, -40 - (th - 20) * lv, 16, (th - 20) * lv, 8), col);
    // ticks
    for (let i = 1; i < 10; i++) lin([[tw / 2 - 4, -40 - i * th / 10], [tw / 2 + 18, -40 - i * th / 10]], 5);
    // the sign on top
    const lab = shape(o.label || 'P(DOOM)', { font: 'dela', size: 84 }), swd = lab.width + 80;
    shp(rrect(-swd / 2, -40 - th - 150, swd, 124, 22), o.signCol || C_.ink, 7);
    pop(o.label || 'P(DOOM)', 0, -40 - th - 64, { font: 'dela', size: 84, align: 'center', fill: o.labelCol || C_.white, lw: 0 });
    // the readout panel
    if (o.readout) { shp(rrect(-150, -300, 300, 110, 18), C_.ink, 6); pop(o.readout, 0, -222, { font: 'dela', size: 76, align: 'center', fill: o.readCol || '#FF6A6A', lw: 0 }); }
    X.restore();
  }

  // ---------------------------------------------------------------- 37 · P(doom)? Not tonight!
  // Reads: (1) 110.4 alarm red; the P(DOOM) meter rolls in reading 99.9% (the callback reads instantly);
  //        (2) 110.5 "P(doom)?": she side-eyes it, sweat; (3) 111.6–112.35 wind-up; (4) 112.4 "Not": KICK (impact frame);
  //        (5) 112.6 "tonight!": it flies off into the sky and twinkles out; she dusts off her hands, smug.
  function s37(t, lt, dur) {
    const tt = onTwos(t);
    const roll = E.out3(seg(t, 110.4, 110.85)), kickT = 112.4, kicked = t >= kickT;
    const [sx, sy] = shake(t, 22 * kick(t, [kickT], 1, 6));
    X.save(); cam(W / 2 + sx, H / 2 + sy, 1.0 + .05 * seg(t, 110.4, 112.4) + kick(t, [kickT], .08));
    // alarm: red stripes, a rotating siren glow
    stripes('#C3202E', '#8E1422', 70, -.5, t * 120 * (kicked ? .2 : 1));
    if (!kicked) { const a = t * 6; glow(W / 2 + Math.cos(a) * 700, 200 + Math.sin(a) * 120, 500, 'rgba(255,90,90,1)', .5); }
    shp([[-100, 860], [W + 100, 860], [W + 100, H + 100], [-100, H + 100]], C_.nightD, 6);
    // the meter
    const mx0 = lerp(W + 400, 1320, roll);
    if (!kicked) {
      const wob2 = wobble(t, 110.85, 3, 5) * .06, blink = Math.floor(t * 6) % 2;
      meter(mx0, 880, .95, .999, { rot: wob2, roll: -roll * 8, readout: '99.9%', readCol: blink ? '#FF6A6A' : '#FFD0D0' });
    } else {
      const a = t - kickT, fly = a / .6;
      if (fly < 1) {
        const x = mx0 + a * 2600, y = 880 - a * 1600 + a * a * 900;
        meter(x, y, .95 * (1 - fly * .6), .999, { rot: a * 14, readout: '99.9%' });
        speedLines(mx0 - 200, 600, 'rgba(255,255,255,.9)', 30, 7, 200, .7 * (1 - fly));
      } else if (a < 1.1) {                            // the twinkle out ("kiran!")
        const k = 1 - Math.abs((a - 1.0) / .1);
        sparkle(W - 260, 180, 70 * clamp(k), C_.white, a * 10); sparkle(W - 260, 180, 30 * clamp(k), C_.lemon, a * 10 + .7);
      }
    }
    // her: side-eye -> wind-up -> kick -> dust off
    const side = tt >= 110.5 && tt < 111.6, wind = seg(tt, 111.6, 112.35), after = tt >= 112.6;
    let o;
    if (!kicked) o = { ...pose(wind > 0 ? 'shrug' : 'idle'), eyes: side || wind > 0 ? 'side' : 'open', look: [1, 0], mouth: side ? 'flat' : wind > 0 ? 'cat' : 'o', sweat: side, lean: -.12 * wind, legR: [-.3 * wind, .6 * wind], turn: .4 };
    else if (!after) o = { ...pose('point'), eyes: 'determined', mouth: 'grin', legR: [1.25, .1], lean: -.18, turn: .5, hop: 10 };
    else o = { ...pose('heart'), eyes: 'happy', mouth: 'cat', lean: 0, blush: .6, turn: 0 };
    idol(760, 880, 1.1, o);
    if (kicked && t < kickT + .12) { sparkle(1180, 720, 120, C_.white, 0); pop('BAM!', 1220, 520, { font: 'dela', size: 150, align: 'center', fill: C_.lemon, lw: 12, shadow: [10, 10, C_.ink], per: () => ({ rot: -.1 }) }); }
    if (after) for (let i = 0; i < 4; i++) { const a = seg(t, 112.65 + i * .06, 113.1 + i * .06); if (a > 0 && a < 1) shp(circle(780 + i * 26 - 40, 700 - a * 90, 16 * (1 - a)), C_.cream, 3); }
    X.restore();
    if (kicked && t < kickT + 1 / 24) { X.save(); X.globalCompositeOperation = 'difference'; flat('#FFFFFF'); X.restore(); }   // the impact frame
    return { karaoke: { size: 54, maxW: 1860 } };
  }

  // ---------------------------------------------------------------- 38 · P(debut): one hundred percent! (Claw! Claw! Snip-snip! Clawd-up!)
  // Reads: (1) 113.3 a new meter drops in: P(DEBUT), pink and lemon, a heart bulb, 0%; (2) it fills, accelerating, the readout counting;
  //        (3) 115.6 "percent!": 100% exactly: the meter explodes into confetti and sparks; (4) 116.1– the formation dance reprise.
  function s38(t, lt, dur) {
    if (t >= 115.95) {
      const z = 1 + kick(t, CHANT38.map(c => c[0]), .05);
      X.save(); X.translate(W / 2, H / 2); X.scale(z, z); X.translate(-W / 2, -H / 2);
      formation(t, CHANT38);
      X.restore();
      confetti(t, 38, 70, undefined, 115.6, 1.2);
      return { calls: false };
    }
    const tt = onTwos(t), drop = E.back(seg(t, 113.25, 113.6)), boom = t >= 115.6;
    const v = clamp(Math.pow(seg(t, 113.3, 115.6), 1.7));
    const [sx, sy] = shake(t, 5 * (1 - v) * 0 + 16 * kick(t, [115.6], 1, 5) + 3 * v);
    X.save(); cam(W / 2 + sx, H / 2 + sy, 1 + .06 * v + kick(t, [115.6], .1));
    sunburst(W / 2, 430, C_.pink, C_.lemon, 24, t * (.2 + v * 1.5));
    shp([[-100, 860], [W + 100, 860], [W + 100, H + 100], [-100, H + 100]], C_.night, 6);
    if (!boom) {
      const pct = Math.floor(v * 100);
      meter(1260, 880 - (1 - drop) * 1400, .95, v, { label: 'P(DEBUT)', col: C_.pink, signCol: C_.lemon, labelCol: C_.ink, readout: pct + '%', readCol: C_.lemon, rot: wobble(t, 113.6, 4, 6) * .05 });
      if (v > .8) for (let i = 0; i < 6; i++) sparkle(1260 + Math.cos(t * 9 + i) * 120, 520 + Math.sin(t * 7 + i * 2) * 260, 18 * v, C_.white, i);
    } else {
      const a = t - 115.6;
      glow(1260, 600, 900 * E.out3(clamp(a / .3)), 'rgba(255,240,180,1)', 1 - clamp(a / .4));
      for (let i = 0; i < 14; i++) { const ang = i / 14 * TAU, r = 700 * E.out3(clamp(a / .4)); spark8(1260 + Math.cos(ang) * r, 600 + Math.sin(ang) * r * .7, 40 * (1 - clamp(a / .4)), [C_.lemon, C_.cyan, C_.white][i % 3], 4, a * 8); }
    }
    // her: cheering the meter on, arms pumping on the beat; at 100% both arms up
    const pump = frac(beatPos(tt)) < .5;
    idol(620, 880, 1.1, { ...(boom ? pose('up') : pose(pump ? 'up' : 'wave')), eyes: boom ? 'star' : 'happy', mouth: 'open', sing: .6, hop: boom ? 30 : pump ? 12 : 0, turn: .35, skirtFlare: boom ? .6 : .2 });
    X.restore();
    if (boom) { const a = t - 115.6; if (a < 2 / 24) flash(1, C_.white); pop('100%', W / 2, 330, { font: 'dela', size: 300 * slamK(t, 115.6, .12) / 1.6 * 1.6, align: 'center', fill: C_.lemon, lw: 16, shadow: [14, 14, C_.ink] }); }
    confetti(t, 381, 60, undefined, 115.6, 1.2);
    return { karaoke: { size: 54, maxW: 1860 } };
  }

  Object.assign(SHOT, { '31': s31, '32': s32, '33': s33, '34': s34, '35': s35, '36': s36, '37': s37, '38': s38 });
  s31.label = 'foryou'; s32.label = 'phones'; s33.label = 'sparks'; s34.label = 'crowd'; s35.label = 'bow'; s36.label = 'formation'; s37.label = 'pdoom'; s38.label = 'pdebut';
})();
