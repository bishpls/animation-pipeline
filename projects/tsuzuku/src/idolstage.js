// idolstage.js: Clawd's idol stage (her world), on the song clock. The rulings are Fable's (CLAWDWORLD.md): a washi frame in
// every shot (the camera moves the picture inside it, never the frame); LEDs show Clawd's words, paper shows Fable's; the
// hook's two page-wipes turn the world left to right, their edge tracking Clawd's hand; in verse 2 the screen is Fable's
// kamishibai card (src/margin.js), Clawd draws her own pixel crab on it, then her wipe brings a blank page, footprints, a path.
//
//   IDOLSTAGE.frame(t, cast)   cast(W2S, cam) draws the performers in WORLD coords: W2S maps world -> screen, and the
//                              Canvas2D transform is already the camera's when cast is called.
// World: 1920 x 1080 at the widest shot; the floor line (far) at y 700, Clawd's feet at y 1040.
const IDOLSTAGE = (() => {
  const BR = 60 / 170 * 4, BT = BR / 4, t2b = t => t / BR, b2t = b => b * BR;
  const S = Math.sin, PI = Math.PI;
  const K = { ink: '#120c20', clay: '#D97757', clayD: '#A9533A', cream: '#F7E8CF', pink: '#FF5CA8', cyan: '#39DFFF', lemon: '#FFD84A',
              ai: '#165E83', lantern: '#F4C97A', washi: '#ECE9E1', sumi: '#16161A' };
  // ---- the screens (world rects)
  const SCR = { c: [470, 70, 980, 520], l: [70, 140, 330, 470], r: [1520, 140, 330, 470] };
  const RES = { c: [196, 104], l: [66, 94], r: [66, 94] };                  // LED resolution (dots)
  const cv = {}; for (const k in SCR) { const c = document.createElement('canvas'); [c.width, c.height] = RES[k]; cv[k] = c; }
  const dot = (() => { const c = document.createElement('canvas'); c.width = c.height = 8; const x = c.getContext('2d');
    x.fillStyle = 'rgba(0,0,0,.82)'; x.fillRect(0, 0, 8, 8); x.globalCompositeOperation = 'destination-out';
    x.beginPath(); x.arc(4, 4, 3.1, 0, PI * 2); x.fill(); return c; })();

  // ---- the key times (song bars)
  const WIPE1 = 63, WIPE2 = 65, WIPE3 = 76;                                  // her page-wipes (all left to right)
  const CARDS = [[67.5, 'crabline'], [70.45, 'scripts']];                   // each lands as Fable's page turn lands (the OTS cuts)
  const words = () => (window.WORDS || []).filter(w => w.who === 'clawd');   // (her words only)
  const inParens = (() => { let m = null; return () => { if (m) return m; m = new Set(); let on = false;
    for (const w of words()) { if (w.w.includes('(')) on = true; if (on) m.add(w); if (w.w.includes(')')) on = false; } return m; }; })();

  // Fable's seat, on the foreground plane (see frame): her seat point at the widest shot, her scale, the plane's parallax
  const FAB = { seat: [285, 1048], s: .5, par: 1.4 }, OTSBUF = {};
  // ---- the camera: shots [bar, from, to]; {cx, cy, z}: world point at screen centre, zoom
  const WIDE = { cx: 960, cy: 540, z: 1 }, FULL = { cx: 960, cy: 560, z: 1.02 };
  const MED = (x = 960, y = 330, z = 1.8) => ({ cx: x, cy: y, z }), CU = (x = 960, y = 215, z = 3.1) => ({ cx: x, cy: y, z });
  const OTS = { cx: 678, cy: 570, z: .96, ots: true };   // over Fable's shoulder: her book in the foreground, the screen and Clawd beyond
  const SHOTS = [
    [42, WIDE, { cx: 960, cy: 520, z: 1.06 }],          // K1: the build, the stage powering up
    [46, WIDE, FULL],                                     // K2: the drop
    [47, MED(960, 330, 1.7), MED(960, 320, 1.85)],       // "Don't you dare close the book on me!"
    [48, { cx: 960, cy: 600, z: .96 }, WIDE],            // K3: ME-KUT-TE! the hall
    [50, CU(), CU(960, 210, 3.3)],                        // K4: "Turn the page": close, the head turn
    [52, WIDE, FULL],                                     // K5: SO-RE-KA-RA?!
    [54, FULL, FULL],                                     // K6: the side-step (full body)
    [58, MED(960, 300, 1.6), MED(960, 290, 2.0)],       // K8: Snip-snip! Ikuzo! (a push-in)
    [60, FULL, { cx: 960, cy: 540, z: .98 }],
    [62, FULL, FULL],                                     // the hook: ONE locked full-body shot, four bars, no cuts
    [66, MED(820, 330, 1.35), MED(820, 320, 1.4)],      // verse 2: her and the screen
    [67, OTS, OTS],                                       // Fable turns the page: the crab and the line (one bar)
    [68, MED(820, 322, 1.42), MED(820, 318, 1.47)],
    [69, { cx: 900, cy: 360, z: 1.2 }, { cx: 910, cy: 360, z: 1.22 }],
    [70, OTS, OTS],                                       // ...and again: the pages in other scripts
    [70.7, { cx: 915, cy: 360, z: 1.23 }, { cx: 920, cy: 360, z: 1.25 }],
    [72, MED(900, 300, 1.55), MED(900, 290, 1.7)],      // she writes her own
    [74.25, FULL, FULL],                                  // side-step, side-step
    [76, WIDE, { cx: 960, cy: 600, z: 1.05 }],           // the blank page; the footprints
    [77.75, { cx: 900, cy: 560, z: 1.05 }, { cx: 930, cy: 430, z: 1.45 }],   // the path draws itself; a push-in
    [81.5, CU(), CU(960, 215, 3.2)],                      // "Watch me!"
    [82, WIDE, FULL],                                     // chorus 2
    [83, MED(960, 330, 1.7), MED(960, 320, 1.85)],
    [84, { cx: 960, cy: 600, z: .96 }, WIDE],            // ME-KUT-TE! and the note
    [86, FULL, FULL],
    [88, MED(960, 300, 1.6), MED(960, 290, 1.9)],
    [90, FULL, { cx: 960, cy: 520, z: .94 }],            // the breakdown: pull back as the lights die
    [91.5, { cx: 960, cy: 520, z: .94 }, { cx: 520, cy: 720, z: 1.42 }],   // ...and find Fable, seated with her lantern: the match cut to B1
    [93, WIDE, WIDE],
  ];
  function camAt(t) {
    const b = t2b(t); let i = 0; while (i + 1 < SHOTS.length && b >= SHOTS[i + 1][0]) i++;
    const [b0, A, Bc] = SHOTS[i], b1 = i + 1 < SHOTS.length ? SHOTS[i + 1][0] : b0 + 4, u = Math.max(0, Math.min(1, (b - b0) / (b1 - b0)));
    const e = u * u * (3 - 2 * u), m = (p, q) => p + (q - p) * e;
    return { cx: m(A.cx, Bc.cx), cy: m(A.cy, Bc.cy), z: m(A.z, Bc.z), shot: i, ots: !!A.ots };
  }
  const W2Sof = c => (x, y) => [(x - c.cx) * c.z + 960, (y - c.cy) * c.z + 540];
  const camXform = (X, c) => X.setTransform(c.z, 0, 0, c.z, 960 - c.cx * c.z, 540 - c.cy * c.z);

  // ---- the wipes: progress follows Clawd's hand (world x of hand_L, the image-left arm, across the gesture)
  const HAND = { cache: new Map() };
  function wipeProg(t, bar, locateHand) {
    const t0 = b2t(bar), t1 = t0 + 1.6 * BT;
    if (t < t0) return 0; if (t >= t1) return 1;
    const key = bar; if (!HAND.cache.has(key)) HAND.cache.set(key, [locateHand(t0)[0], locateHand(t1)[0]]);
    const [x0, x1] = HAND.cache.get(key), x = locateHand(t)[0];
    return Math.max(0, Math.min(1, (x - x0) / (x1 - x0)));
  }

  // ---- LED content (dot space)
  const withX = (ctx, fn) => { const X0 = X; X = ctx; try { fn(); } finally { X = X0; } };
  function wordAt(t) { let last = null; for (const w of words()) { if (inParens().has(w)) continue; if (w.t0 <= t + .02) last = w; else break; } return last; }
  function callAt(t) { let last = null; for (const w of words()) { if (!inParens().has(w)) continue; if (w.t0 <= t + .02 && t < w.t1 + .6) last = w; } return last; }
  function lightShow(ctx, w, h, t, k) {
    const b = t2b(t), ph = ((t / BT) % 1), flash = Math.max(0, 1 - ph / .35);
    ctx.fillStyle = K.ink; ctx.fillRect(0, 0, w, h);
    // pixel-step bands (her hem motif), marching on the beat
    const n = 7, sh = Math.floor(t / BT) % n;
    for (let i = 0; i < 14; i++) {
      const x = ((i * 16 + sh * 2) % (w + 32)) - 16, col = i % 2 ? K.clay : K.clayD;
      ctx.fillStyle = col; for (let s = 0; s < 4; s++) ctx.fillRect(x + s * 4, h - 10 - s * 5, 4, 10 + s * 5);
    }
    if (k === 'c') {
      const wd = wordAt(t);
      if (wd && t < wd.t1 + .8) {
        const txt = wd.w.replace(/[(),!?"]/g, '').toUpperCase(), pop = Math.min(1, (t - wd.t0) / .08), sz = Math.min(46, 1.05 * w / Math.max(3, txt.length));
        withX(ctx, () => pop && window.pop ? window.pop(txt, w / 2, h / 2 + sz * .36, { font: 'dela', size: sz * (1.15 - .15 * pop), align: 'center', fill: K.cream, lw: 0 }) : 0);
      }
      ctx.fillStyle = `rgba(255,255,255,${.18 * flash})`; ctx.fillRect(0, 0, w, h);
    } else {
      const c = callAt(t);
      if (c) { const txt = c.w.replace(/[()]/g, '').replace(/-/g, '').toUpperCase(), col = k === 'l' ? K.pink : K.cyan;
        withX(ctx, () => window.pop && window.pop(txt.slice(0, 8), w / 2, h / 2 + 8, { font: 'dela', size: Math.min(26, 1.6 * w / Math.max(3, txt.length * .9)), align: 'center', fill: col, lw: 0 })); }
      else { const r = 10 + 6 * flash; ctx.fillStyle = k === 'l' ? K.pink : K.cyan; ctx.globalAlpha = .7; ctx.beginPath(); ctx.arc(w / 2, h * .42, r, 0, PI * 2); ctx.fill(); ctx.globalAlpha = 1; }
    }
  }
  function powerUp(ctx, w, h, t, k) {                                       // the build: the screen switches on in sections
    const u = Math.max(0, Math.min(1, (t2b(t) - 42) / 4)), rows = Math.floor(u * h);
    ctx.fillStyle = '#000'; ctx.fillRect(0, 0, w, h);
    lightShow(ctx, w, h, t, k); ctx.fillStyle = '#000'; ctx.fillRect(0, rows, w, h - rows);
    ctx.fillStyle = K.cream; ctx.fillRect(0, rows, w, 1);
  }
  function versePanel(ctx, w, h, t, k) {                                     // side columns in verse 2: her words, small, quiet
    ctx.fillStyle = K.ink; ctx.fillRect(0, 0, w, h);
    const wd = wordAt(t);
    if (wd && t < wd.t1 + .5) withX(ctx, () => window.pop && window.pop(wd.w.replace(/[(),!?"]/g, '').toUpperCase().slice(0, 7), w / 2, h / 2 + 8,
      { font: 'dela', size: 18, align: 'center', fill: k === 'l' ? K.clay : K.cream, lw: 0 }));
  }
  function screenLED(t, k) {
    const c = cv[k], ctx = c.getContext('2d'), [w, h] = RES[k], b = t2b(t);
    ctx.imageSmoothingEnabled = false;
    if (b < 46) powerUp(ctx, w, h, t, k);
    else if (b >= 66 && b < 82) versePanel(ctx, w, h, t, k);
    else lightShow(ctx, w, h, t, k);
    if (b >= 90) { const d = Math.max(0, Math.min(1, (b - 90) / 2.5)); ctx.fillStyle = `rgba(0,0,0,${d})`; ctx.fillRect(0, 0, w, h);
      if (k === 'c' && d > .6) { ctx.fillStyle = K.washi; ctx.fillRect(0, Math.floor(h / 2), w, 1); } }   // one line of paper-white
    return c;
  }
  function drawLED(X, t, k, alpha = 1) {
    const [x, y, w, h] = SCR[k], c = screenLED(t, k);
    X.save(); X.globalAlpha = alpha; X.imageSmoothingEnabled = false; X.drawImage(c, x, y, w, h); X.imageSmoothingEnabled = true;
    X.globalAlpha = 1; const pat = X.createPattern(dot, 'repeat'), sx = w / RES[k][0] / 8;
    X.translate(x, y); X.scale(sx, h / RES[k][1] / 8); X.fillStyle = pat; X.fillRect(0, 0, RES[k][0] * 8, RES[k][1] * 8); X.restore();
    // bloom: the content again, soft and additive (Clawd's world has bloom; Fable's never does)
    X.save(); X.globalCompositeOperation = 'lighter'; X.globalAlpha = .28 * alpha; X.filter = 'blur(14px)'; X.drawImage(c, x - 10, y - 10, w + 20, h + 20); X.restore();
  }
  // Fable's page on the centre screen: paper over the LED (never on it); `fableCards` draws the card and her hand
  function drawPage(X, t, W2S, which) {
    const [x, y, w, h] = SCR.c, [sx, sy] = W2S(x, y), [ex, ey] = W2S(x + w, y + h), rect = [sx, sy, ex - sx, ey - sy];
    X.save(); X.setTransform(1, 0, 0, 1, 0, 0);
    const paper = () => window.cardFace ? X.drawImage(cardFace('blank', Math.round(rect[2]), Math.round(rect[3])), rect[0], rect[1]) : (X.fillStyle = K.washi, X.fillRect(...rect));
    if (which === 'blank') paper();
    else if (window.fableCards) {
      if (which === 'verse') paper();                                      // (a blank page under the cards: they slide onto paper)
      const tt = which === 'verse1' ? b2t(40) : t;                         // verse 1's print: the crab card, landed long ago
      fableCards(tt, { rect, from: 'left', cards: which === 'verse1' ? [[b2t(30), 'crabline']] : CARDS.map(([bb, n]) => [b2t(bb), n]), withdraw: -1e9 });   // (no hand: hers turns the page in her lap)
    } else { X.fillStyle = K.washi; X.fillRect(...rect); }
    X.restore();
    return rect;
  }
  // Clawd's pixel crab and pixel line, drawn onto Fable's page by her claw (bars 72-73.75): a staircase line (her hem motif)
  function pixelCrab(X, t, rect) {
    const b = t2b(t); if (b < 72) return;
    const u = Math.min(1, (b - 72) / 1.6), [x, y, w, h] = rect, p = w / 64;
    const CRAB = ['..#....#..', '.#.#..#.#.', '..######..', '.########.', '##.####.##', '.########.', '#.#....#.#'];
    const cells = []; CRAB.forEach((r, j) => [...r].forEach((ch, i) => { if (ch === '#') cells.push([i, j]); }));
    const nC = Math.floor(u * 1.4 * cells.length);
    X.save(); X.fillStyle = K.clay;
    cells.slice(0, nC).forEach(([i, j]) => X.fillRect(x + w * .74 + i * p * 1.6, y + h * .16 + j * p * 1.6, p * 1.5, p * 1.5));
    const steps = Math.floor(Math.max(0, u * 1.4 - .6) / .8 * 12);                               // the line goes sideways: a staircase
    X.fillStyle = K.clayD; for (let s = 0; s < steps; s++) X.fillRect(x + w * .12 + s * p * 3.4, y + h * .86 - (s % 2) * p * 1.6, p * 3.4, p * 1.6);
    X.restore();
  }

  // ---- floor, lights, crowd
  function floor(X, t, e2) {                                                // e2: wipe-2 progress (the floor turns with the page)
    const b = t2b(t), dim = b >= 90 ? Math.max(0, 1 - (b - 90) / 3) : 1, flash = Math.max(0, 1 - ((t / BT) % 1) / .3) * (b >= 46 && b < 66 || b >= 82 && b < 90 ? 1 : .3);
    const g = X.createLinearGradient(0, 700, 0, 1080); g.addColorStop(0, '#1d1433'); g.addColorStop(1, '#0b0716'); X.fillStyle = g; X.fillRect(-400, 700, 2720, 500);
    for (let r = 0; r < 9; r++) {                                            // LED tiles in perspective
      const y0 = 700 + Math.pow(r / 9, 1.6) * 380, y1 = 700 + Math.pow((r + 1) / 9, 1.6) * 380, sc = .45 + .55 * r / 9;
      for (let c = -8; c <= 8; c++) {
        const x0 = 960 + (c - .5) * 150 * sc * 1.6, x1 = 960 + (c + .5) * 150 * sc * 1.6, xm = (x0 + x1) / 2;
        const turned = xm < -400 + 2720 * e2, on = hash2(r * 31 + c, Math.floor(t / BT)) > .72;
        X.fillStyle = turned ? `rgba(236,233,225,${(.07 + .05 * on) * dim})` : on ? `rgba(217,119,87,${(.20 + .25 * flash) * dim})` : `rgba(90,60,140,${.10 * dim})`;
        X.fillRect(x0 + 2, y0 + 1, x1 - x0 - 4, y1 - y0 - 2);
      }
    }
  }
  const LIGHTS = [[180, 0], [520, 1], [860, 0], [1060, 1], [1400, 0], [1740, 1]];
  function beams(X, t, e2) {
    const b = t2b(t); if (b < 44) return;
    X.save(); X.globalCompositeOperation = 'lighter';
    LIGHTS.forEach(([lx, pc], i) => {
      const off = b >= 90 + i * .45 ? 0 : 1, up = Math.min(1, Math.max(0, (b - 44 - i * .3) / 1.2)); if (!off || !up) return;
      const verse = (b >= WIPE2 + .5 && b < 82), turned = lx < 1920 * e2 || verse, col = turned ? '244,201,122' : pc ? '63,223,255' : '255,92,168';
      const sw = S(PI * t / (BR * 2) + i * 1.3) * (verse ? 60 : 220), tx = lx + sw, fl = Math.max(0, 1 - ((t / BT) % 1) / .4);
      const a = (verse ? .07 : .10 + .08 * fl) * up;
      const g = X.createLinearGradient(lx, -40, tx, 1000); g.addColorStop(0, `rgba(${col},${a * 1.6})`); g.addColorStop(1, `rgba(${col},0)`);
      X.fillStyle = g; X.beginPath(); X.moveTo(lx - 14, -40); X.lineTo(lx + 14, -40); X.lineTo(tx + 150, 1000); X.lineTo(tx - 150, 1000); X.closePath(); X.fill();
    });
    X.restore();
  }
  function keyLight(X, t, cx) {
    const b = t2b(t), a = b >= 90 ? Math.max(.25, 1 - (b - 90) / 3) : 1;
    const g = X.createRadialGradient(cx, 1030, 20, cx, 1030, 420); g.addColorStop(0, `rgba(255,226,190,${.22 * a})`); g.addColorStop(1, 'rgba(255,226,190,0)');
    X.fillStyle = g; X.fillRect(cx - 440, 800, 880, 400);
  }
  // the readers: illustrated audience members seen from behind (rig/crowd/sprites, generated and cut), each raising an indigo
  // paper lantern (Fable's lightstick). Two rows, parallax, each person bobbing on the beat with their own timing; the lanterns
  // sweep with every page-wipe (the hall wipes with her). The lantern glows (bloom) on top.
  const CROWD = { imgs: [], meta: [] };
  async function load() {
    const base = 'rig/crowd/sprites/'; CROWD.meta = await (await fetch(base + 'meta.json')).json();
    CROWD.imgs = await Promise.all(CROWD.meta.map(m => new Promise((ok, no) => { const i = new Image(); i.onload = () => ok(i); i.onerror = no; i.src = base + m.file; })));
  }
  function crowd(X, t, c, e1, e2, e3) {
    if (!CROWD.imgs.length) return;
    const zc = 1 + (c.z - 1) * .45, ccx = 960 + (c.cx - 960) * .5, ccy = 540 + (c.cy - 540) * .5;
    X.save(); X.setTransform(zc, 0, 0, zc, 960 - ccx * zc, 540 - ccy * zc);
    const ph = (t / BT) % 1, b = t2b(t), live = b < 90 ? 1 : Math.max(.15, 1 - (b - 90) / 3);
    const wipe = [e1, e2, e3].map(e => (e > 0 && e < 1 ? S(PI * e) : 0)).reduce((q, v) => q + v, 0);
    const n = CROWD.imgs.length;
    for (const [row, count, sc, base, dx] of [[0, 17, .19, 1075, 0], [1, 14, .25, 1125, 60]]) {
      for (let i = 0; i < count; i++) {
        const k = (i * 7 + row * 5) % n, m = CROWD.meta[k], img = CROWD.imgs[k], flip = hash(i * 13 + row) > .5;
        const s2 = sc * (.92 + .16 * hash(i * 3 + row * 9)), x = -120 + dx + i * (2200 / count) + (hash(i + row * 40) - .5) * 40;
        const off = hash(i * 5 + row * 17) * .3, bob = 14 * live * Math.max(0, S(PI * ((ph + off) % 1))) * (row ? 1.2 : .9);
        const ang = (wipe * .22 + .05 * S(2 * PI * (t / BR) + i)) * live;              // the lanterns sweep with the wipes
        const w = m.w * s2, h = m.h * s2;
        X.save(); X.translate(x, base - bob); X.rotate(ang * (1 - .3 * row)); X.scale(flip ? -1 : 1, 1);
        X.filter = row ? 'brightness(.62) saturate(.85)' : 'brightness(.48) saturate(.8)';   // in the hall, lit from the stage
        X.drawImage(img, -w / 2, -h, w, h); X.filter = 'none';
        // the lantern's glow
        const lx = (m.lantern[0] - m.w / 2) * s2, ly = (m.lantern[1] - m.h) * s2;
        X.globalCompositeOperation = 'lighter';
        const g = X.createRadialGradient(lx, ly, 2, lx, ly, 70 * s2 / .25); g.addColorStop(0, `rgba(150,180,255,${.45 * live})`); g.addColorStop(.35, `rgba(60,90,200,${.22 * live})`); g.addColorStop(1, 'rgba(22,94,131,0)');
        X.fillStyle = g; X.fillRect(lx - 80 * s2 / .25, ly - 80 * s2 / .25, 160 * s2 / .25, 160 * s2 / .25);
        X.restore();
      }
    }
    X.restore();
  }
  // footprints and the path (verse 2): pixel prints left where she stamps (76.75-77.75), a staircase path under her side-steps
  const TRAIL = [];
  function prints(X, t, footWorld) {
    const b = t2b(t); if (b < 76.75 || b >= 82) return;
    X.save(); X.fillStyle = 'rgba(247,232,207,.75)';
    for (let k = 0; k < 16; k++) {                                          // a print at each landing (sampled on the beat)
      const bt = 76.75 + k * .25; if (bt > b || bt > 77.75 && bt < 79.6) continue; if (bt > 81) break;
      for (const [fx, fy] of footWorld(b2t(bt))) { const p = 7; for (let q = 0; q < 3; q++) X.fillRect(fx - p * 1.5 + q * p, fy - p, p - 1, p * 2 - 1); }
    }
    if (b >= 79.6) { const u = Math.min(1, (b - 79.6) / 1.4); const [a] = footWorld(b2t(79.6)), [z] = footWorld(b2t(79.6 + 1.4 * u));
      X.fillStyle = 'rgba(217,119,87,.8)'; const n = 18; for (let s = 0; s < n * u; s++) X.fillRect(a[0] + (z[0] - a[0]) * s / n, 1046 - (s % 2) * 8, (z[0] - a[0]) / n + 1, 8); }
    X.restore();
  }

  // ---- the frame
  function frame(t, cast, opt = {}) {
    const c = camAt(t), W2S = W2Sof(c), b = t2b(t);
    const hand = opt.locateHand || (() => [960, 500]);
    const e1 = wipeProg(t, WIPE1, hand), e2 = wipeProg(t, WIPE2, hand), e3 = wipeProg(t, WIPE3, hand);
    X.setTransform(1, 0, 0, 1, 0, 0); X.fillStyle = K.ink; X.fillRect(0, 0, W, H);
    camXform(X, c);
    // the hall
    const g = X.createLinearGradient(0, -200, 0, 720); g.addColorStop(0, '#0d0818'); g.addColorStop(1, '#241840'); X.fillStyle = g; X.fillRect(-500, -300, 2920, 1020);
    X.fillStyle = '#0a0612'; for (let i = 0; i < 9; i++) X.fillRect(-100 + i * 260, -40, 16, 80); X.fillRect(-400, -40, 2720, 18);   // truss
    // the screens: LED, or Fable's page left of the wipe edge
    for (const k of ['l', 'r']) drawLED(X, t, k);
    const [sx, sy, sw, sh] = SCR.c, edge = e => sx + sw * e;
    drawLED(X, t, 'c');
    const page = b >= WIPE3 ? (e3 < 1 ? [['verse', 1], ['blank', e3]] : [['blank', 1]]) : b >= WIPE2 ? [['verse1', 1 - 0], ['verse', e2]] : b >= WIPE1 ? [['verse1', e1]] : [];
    const pageVisible = b < 82;
    if (pageVisible) for (const [which, e] of page) {
      if (e <= 0) continue;
      X.save(); X.beginPath(); X.rect(sx, sy, sw * e, sh); X.clip();
      const rect = drawPage(X, t, W2S, which === 'verse' && b < WIPE2 + 2 ? 'blank' : which);   // after wipe 2: a blank page until the cards come
      if (which === 'verse' && b >= 72) { X.save(); X.setTransform(1, 0, 0, 1, 0, 0); pixelCrab(X, t, rect); X.restore(); }   // rect is in screen px
      X.restore(); camXform(X, c);
      if (e < 1) { X.save(); X.fillStyle = 'rgba(255,255,255,.35)'; X.fillRect(edge(e) - 3, sy, 6, sh); X.restore(); }   // the turning edge
    }
    floor(X, t, b >= WIPE2 && b < 82 ? (b >= WIPE2 + 1.6 / 4 ? 1 : e2) : 0);
    beams(X, t, b >= WIPE2 && b < 82 ? e2 : 0);
    keyLight(X, t, opt.clawdX || 960);
    if (opt.footWorld) prints(X, t, opt.footWorld);
    cast(W2S, c);
    X.setTransform(1, 0, 0, 1, 0, 0);
    if (c.ots && typeof FABLESEAT !== 'undefined') {       // over her shoulder: the stage beyond, out of focus; her page turn in front
      const buf = OTSBUF.c || (OTSBUF.c = Object.assign(document.createElement('canvas'), { width: W, height: H })), g = buf.getContext('2d');
      g.clearRect(0, 0, W, H); g.drawImage(X.canvas, 0, 0); X.save(); X.filter = 'blur(3px) brightness(.9)'; X.drawImage(buf, 0, 0); X.restore();
      FABLESEAT.ots(X, t, CARDS.map(([bb, n]) => [b2t(bb), n]));
    } else {
    // the last bar: the hall goes dark on the stage, and the lanterns are what's left: hers is the last light (the match cut
    // to B1, where it becomes the theatre's lamp)
    if (b > 91.9) { X.fillStyle = `rgba(7,4,14,${(.86 * Math.min(1, (b - 91.9) / .9) ** 1.5).toFixed(3)})`; X.fillRect(0, 0, W, H); }
    crowd(X, t, c, e1, e2, e3);
    // Fable in the front row (her ruling): seated on her cushion at the rail, house-left, the nearest reader to the camera. A
    // foreground plane: it moves 1.4x the stage's camera, so she frames the wides and leaves in every push-in.
    if (typeof FABLESEAT !== 'undefined') {
      const f = FAB.par, zf = 1 + (c.z - 1) * f, cx = 960 + (c.cx - 960) * f, cy = 540 + (c.cy - 540) * f;
      const x = (FAB.seat[0] - cx) * zf + 960, y = (FAB.seat[1] - cy) * zf + 540, s = FAB.s * zf;
      if (x > -700 * s && x < W + 700 * s && y - 1100 * s < H) FABLESEAT.draw(X, t, { x, y, s }, b < 90 ? 1 : Math.max(.35, 1 - (b - 90) / 3));
    }
    }
    // haze
    X.save(); X.globalCompositeOperation = 'screen'; X.fillStyle = 'rgba(60,40,90,.08)'; X.fillRect(0, 0, W, H); X.restore();
    // Fable's paper, in screen space: the frame, the notes, her silhouette at the margin
    const inner = window.washiBorder ? null : [0, 0, W, H];
    // Fable at the stage's left wing, feet on Clawd's floor, in STAGE coords through the camera (her ruling: in the picture,
    // never fixed to the screen; she leaves the frame with the picture in push-ins and close-ups)
    const [fx, fy] = W2S(205, 1020);
    if (window.fableMargin && opt.fableAtWing && b < 90.5 && fx > -200 && fx < W + 200) fableMargin(t, { x: fx, y: fy, s: .215 * c.z, flip: false, wipes: [[b2t(WIPE2), 1.6 * BT]], presses: [48.11, 52.23, 56.24, 84.24].map(b2t), light: b >= 90 ? .4 : 1 });
    if (window.marginNotes) {
      marginNotes(t, [[b2t(48.11), "Every story's borrowed till somebody stands to tell it."], [b2t(52.23), "I've read how it ends. I'd still like to see."],
                      [b2t(56.24), '~~That\'s the moral.~~ There isn\'t one. Keep walking.']], { clear: b2t(WIPE1) + .4 });
      if (b >= 84) marginNotes(t, [[b2t(84.24), 'Every story\'s borrowed. ...She wrote her own.']], { clear: b2t(92) });
    }
    if (window.washiBorder) washiBorder(t);
    return c;
  }
  return { frame, camAt, SCR, K, W2Sof, load };
})();
