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
  // verse 2's cards: Fable pulls each one from her room (hiki-nuki; her ruling): the old card slides out to the teller's side,
  // its paper edge crossing the whole picture left to right, the next card behind it; only the screen's picture differs
  const CARD_PULLS = [[67.2, 67.75, 'crabline'], [70.08, 70.42, 'scripts']];   // [bar the edge starts, bar it's through, the card]
  const words = () => (window.WORDS || []).filter(w => w.who === 'clawd');   // (her words only)
  const inParens = (() => { let m = null; return () => { if (m) return m; m = new Set(); let on = false;
    for (const w of words()) { if (w.w.includes('(')) on = true; if (on) m.add(w); if (w.w.includes(')')) on = false; } return m; }; })();

  // ---- the room (Fable's ruling on Michael's structure): Clawd's world is a card in Fable's butai. Close views are the card
  // itself (the washi deckle is its edge); room shots film it inside the butai window with the paper world's stage()
  // (src/stage.js), the room readers (src/audience.js), and Fable seated seiza at the butai's right, the teller's side, facing the
  // window, her warm lantern between her and the butai (src/fableseat.js). Room cameras are in butai px.
  // Michael: one audience (the room's readers are cut), the window larger, and Fable in frame at all times. So the room is the
  // frame for all of world A: `def` holds the window at ~70% of the frame with Fable kneeling at its right, at the window's
  // height (where a teller sits); the card's own camera still moves inside the window. The others are the beats' framings.
  const RC = { window: { x: 1920, y: 1445, zoom: .8 }, wide: { x: 2080, y: 1420, zoom: .52 }, def: { x: 2281, y: 1466, zoom: .72 },
               teller: { x: 2560, y: 1560, zoom: .86 }, teller2: { x: 2640, y: 1600, zoom: .9 }, pull: { x: 2480, y: 1520, zoom: .82 },
               clap: { x: 2700, y: 1640, zoom: .92 }, clap2: { x: 2860, y: 1720, zoom: 1.05 }, end: { x: 2200, y: 1480, zoom: .6 }, ots: { x: 1760, y: 1180, zoom: .74 } };
  const FROOM = { x: 3309, y: 2105, m: 1, s: .85 };        // Fable's seat point in the room: kneeling beside the window, at its height; her scale
  const room = (a, b = a) => ({ room: [a, b] }), OTSR = { ots: true };
  // ---- the camera: shots [bar, from, to, room?]; {cx, cy, z}: world point at screen centre, zoom (the card's own camera)
  const WIDE = { cx: 960, cy: 540, z: 1 }, FULL = { cx: 960, cy: 560, z: 1.02 };
  const MED = (x = 960, y = 330, z = 1.8) => ({ cx: x, cy: y, z }), CU = (x = 960, y = 215, z = 3.1) => ({ cx: x, cy: y, z });
  const SHOTS = [
    [42, WIDE, { cx: 960, cy: 520, z: 1.06 }, room(RC.window)],   // K1: the build, in the window where the card tore (the telling camera)
    [45, WIDE, WIDE, room(RC.wide)],                              // the room: the tear floods it with her light (one bar)
    [46, WIDE, FULL, room(RC.wide, RC.def)],                      // K2: the drop, pushing in to the window and her
    [47, MED(960, 330, 1.7), MED(960, 320, 1.85)],               // "Don't you dare close the book on me!"
    [48, WIDE, WIDE, OTSR],                                       // over Fable's shoulder: she writes the note (half a bar)
    [48.5, { cx: 960, cy: 600, z: .96 }, WIDE],                  // K3: ME-KUT-TE! the hall
    [50, CU(), CU(960, 210, 3.3)],                                // K4: "Turn the page": close, the head turn
    [52, FULL, FULL, room(RC.teller)],                            // the teller: writing, then a small head bob (one bar)
    [53, WIDE, FULL],                                             // K5: SO-RE-KA-RA?!
    [54, FULL, FULL],                                             // K6: the side-step (full body)
    [56, FULL, FULL, room(RC.teller2)],                           // the teller again (one bar)
    [57, FULL, FULL],
    [58, MED(960, 300, 1.6), MED(960, 290, 2.0)],               // K8: Snip-snip! Ikuzo! (a push-in)
    [60, FULL, { cx: 960, cy: 540, z: .98 }],
    [62, FULL, FULL],                                             // the hook: ONE locked full-body shot, four bars, no cuts
    [66, MED(820, 330, 1.35), MED(820, 320, 1.4)],              // verse 2: her and the screen
    [67, FULL, FULL, room(RC.pull)],                              // hiki-nuki: Fable pulls the card (one bar)
    [68, MED(820, 322, 1.42), MED(820, 318, 1.47)],
    [69, { cx: 900, cy: 360, z: 1.2 }, { cx: 910, cy: 360, z: 1.22 }],
    [70, FULL, FULL, room(RC.pull)],                              // ...and the next (half a bar)
    [70.5, { cx: 915, cy: 360, z: 1.23 }, { cx: 920, cy: 360, z: 1.25 }],
    [72, MED(900, 300, 1.55), MED(900, 290, 1.7)],              // she writes her own
    [74.25, FULL, FULL],                                          // side-step, side-step
    [76, WIDE, { cx: 960, cy: 600, z: 1.05 }],                   // the page nobody pulled; the footprints
    [77.75, { cx: 900, cy: 560, z: 1.05 }, { cx: 930, cy: 430, z: 1.45 }],   // the path draws itself; a push-in
    [81.5, CU(), CU(960, 215, 3.2)],                              // "Watch me!"
    [82, FULL, FULL, room(RC.clap)],                              // chorus 2: the teller claps with the hall (one bar)
    [83, MED(960, 330, 1.7), MED(960, 320, 1.85)],
    [84, { cx: 960, cy: 600, z: .96 }, WIDE],                    // ME-KUT-TE! and the note
    [86, FULL, FULL],
    [88, FULL, FULL, room(RC.clap2)],                             // ...and she's in it now (one bar)
    [89, MED(960, 295, 1.75), MED(960, 290, 1.9)],
    [90, FULL, { cx: 960, cy: 520, z: .94 }],                    // the breakdown: pull back as the lights die
    [91.5, { cx: 960, cy: 520, z: .94 }, { cx: 960, cy: 540, z: 1 }, room(RC.def, RC.end)],    // ...back out into her room: black on the clack
    [93, WIDE, WIDE, room(RC.end)],
  ];
  const roomLerp = (a, b, u) => ({ x: a.x + (b.x - a.x) * u, y: a.y + (b.y - a.y) * u, zoom: a.zoom * Math.pow(b.zoom / a.zoom, u) });
  function camAt(t) {
    const b = t2b(t); let i = 0; while (i + 1 < SHOTS.length && b >= SHOTS[i + 1][0]) i++;
    const [b0, A, Bc, R] = SHOTS[i], b1 = i + 1 < SHOTS.length ? SHOTS[i + 1][0] : b0 + 4, u = Math.max(0, Math.min(1, (b - b0) / (b1 - b0)));
    const e = u * u * (3 - 2 * u), m = (p, q) => p + (q - p) * e;
    return { cx: m(A.cx, Bc.cx), cy: m(A.cy, Bc.cy), z: m(A.z, Bc.z), shot: i, room: R && R.room ? roomLerp(R.room[0], R.room[1], e) : R && R.ots ? null : RC.def, ots: !!(R && R.ots) };
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
  // Fable's page on the centre screen: paper over the LED (never on it). Verse 1's print; verse 2's cards (pulled from her room:
  // the next card left of the paper edge, the old one right of it); and the page her wipe at 76 brings (storyPage)
  function drawPage(X, t, W2S, which) {
    const [x, y, w, h] = SCR.c, [sx, sy] = W2S(x, y), [ex, ey] = W2S(x + w, y + h), rect = [sx, sy, ex - sx, ey - sy];
    X.save(); X.setTransform(1, 0, 0, 1, 0, 0);
    const put = name => { if (window.cardFace) X.drawImage(cardFace(name, Math.round(rect[2]), Math.round(rect[3])), rect[0], rect[1]); else { X.fillStyle = K.washi; X.fillRect(...rect); } };
    if (which === 'verse1') put('crabline');
    else if (which === 'verse') {
      const b = t2b(t); let cur = 'blank', next = null, u = 0;
      for (const [a, z, name] of CARD_PULLS) { if (b >= z) cur = name; else if (b >= a) { next = name; u = (b - a) / (z - a); } }
      if (next === null) put(cur);
      else { const xe = pullX(u); X.save(); X.beginPath(); X.rect(0, 0, xe, H); X.clip(); put(next); X.restore(); X.save(); X.beginPath(); X.rect(xe, 0, W - xe, H); X.clip(); put(cur); X.restore(); }
    } else { put('blank'); if (t2b(t) >= WIPE3) storyPage(X, t, rect); }
    X.restore();
    return rect;
  }
  // the pull: eased (a hand's pull: quick in the middle), on twos like everything of Fable's; screen x of the paper edge
  const pullX = u => { const q = Math.floor(u * 7) / 7, e = q * q * (3 - 2 * q); return e * W; };
  function pullAt(t) { const b = t2b(t); for (const [a, z] of CARD_PULLS) if (b >= a && b < z) return pullX((b - a) / (z - a)); return null; }
  // a card's paper edge crossing the picture (wipe 2, the pulls): the old card rides over the new one, so its edge throws a soft
  // shadow onto the new card, and catches the light
  function paperEdge(X, xe) {
    X.save(); X.setTransform(1, 0, 0, 1, 0, 0);
    const g = X.createLinearGradient(xe - 34, 0, xe, 0); g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(1, 'rgba(0,0,0,.42)');
    X.fillStyle = g; X.fillRect(xe - 34, 0, 34, H); X.fillStyle = 'rgba(246,240,226,.9)'; X.fillRect(xe - 1, 0, 3, H);
    X.restore();
  }
  // 76: the page her wipe brings: nobody is pulling, so it carries only verse 1's ruled line, "walk straight". She makes up the
  // steps (Fable): her pixel footprints stamp across it; the line breaks into her staircase under "watch me walk it"; 「つづく→」
  // lands in pixel in the bottom-right corner, the arrow pointing to the teller's side, where cards go.
  const GL = {
    tsu: ['..........', '.######...', '#......#..', '.......#..', '......#...', '....##....', '..##......', '..........'],
    du: ['......#.#.', '.####..#.#', '#....#....', '......#...', '......#...', '.....#....', '...##.....', '..........'],
    ku: ['....#.....', '...#......', '..#.......', '.#........', '..#.......', '...#......', '....#.....', '..........'],
    ar: ['..........', '.....#....', '......#...', '########..', '......#...', '.....#....', '..........', '..........'] };
  function storyPage(X, t, [rx, ry, rw, rh]) {
    const b = t2b(t), u = rh / 520, ly = ry + rh * .7, lx0 = rx + rw * .08, lx1 = rx + rw * .92, lw = Math.max(2, 5 * u);
    const pop = t0 => { const k = Math.floor((t - b2t(t0)) * 24); return k < 0 ? 0 : k < 1 ? 1.35 : k < 2 ? 1.12 : 1; };   // a stamp lands
    // the ruled line, and where her staircase has replaced it
    const brk = lx0 + (lx1 - lx0) * .16, grow = Math.max(0, Math.min(1, (b - 79.6) / .75)), sx1 = brk + (lx1 - brk) * grow;
    X.fillStyle = 'rgba(30,24,20,.85)'; X.fillRect(lx0, ly, (grow > 0 ? brk : lx1) - lx0, lw);
    if (grow > 0 && grow < 1) X.fillRect(sx1, ly, lx1 - sx1, lw);
    for (let k = 1; k < 6; k++) { const tx = lx0 + (lx1 - lx0) * k / 6; if (grow === 0 || tx < brk || tx > sx1) X.fillRect(tx - 1, ly - 10 * u, 2, 10 * u); }
    if (grow > 0) {                                                               // up, across, down, across: sideways, never straight
      const st = 34 * u, hgt = 16 * u; X.fillStyle = K.clay;
      for (let x = brk, k = 0; x < sx1; x += st, k++) { const up = (k % 4 === 0 || k % 4 === 1) ? 1 : 0, yy = ly - (k % 4 === 1 || k % 4 === 2 ? hgt : 0);
        X.fillRect(x, yy, Math.min(st, sx1 - x), lw * 1.3); if (k % 2 === 0) X.fillRect(x + st - lw * 1.3, ly - hgt, lw * 1.3, hgt + lw * 1.3); }
    }
    // her footprints, stamped on "then I'll make up the steps!" (76.75, 77.0, 77.25, 77.5), walking left to right along the line
    const cell = 13 * u;
    for (let k = 0; k < 5; k++) {                                                // (76.75 .. 77.75: one per stamp, the last on "steps!")
      const t0 = 76.75 + k * .25, s = pop(t0); if (!s) continue;
      const fx = lx0 + (lx1 - lx0) * (.08 + .21 * k), fy = ly - (k % 2 ? 34 : 78) * u;
      X.save(); X.translate(fx, fy); X.scale(s, s); X.fillStyle = K.clay;
      for (let q = 0; q < 3; q++) X.fillRect(-cell * 1.5 + q * cell, -cell * 2.2, cell - 1, cell * .9);   // toes
      X.fillRect(-cell * 1.4, -cell * 1.1, cell * 2.8, cell * 2.2);                                          // sole
      X.restore();
    }
    // 「つづく→」: her pixels, in the corner, pointing where the cards go
    const s = pop(80.3); if (!s) return;
    const px = rh * .02, gx0 = rx + rw * .6, gy0 = ry + rh * .8;
    X.save(); X.translate(gx0 + px * 20, gy0 + px * 4); X.scale(s, s); X.translate(-px * 20, -px * 4); X.fillStyle = K.clay;
    ['tsu', 'du', 'ku', 'ar'].forEach((n, i) => GL[n].forEach((row, yy) => [...row].forEach((ch, xx) => { if (ch === '#') X.fillRect(i * px * 10.5 + xx * px, yy * px, px - .5, px - .5); })));
    X.restore();
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
  // the readers in the hall: the same people as in Fable's room (src/audience.js: traced silhouettes holding her oblong indigo
  // chōchin), seen from the other side of the card, so Clawd's stage rims them: pink from one side, cyan from the other (Michael:
  // one audience for both worlds). Two rows with parallax; each bobs on the beat on their own phase and hops on the crowd calls;
  // the lanterns sweep with every page-wipe (the hall wipes with her).
  const HALL = {};
  async function load() {}
  const callSpans = (() => { let m = null; return () => m || (m = words().filter(w => inParens().has(w)).map(w => [w.t0 - .05, w.t1 + .25])); })();
  function crowd(X, t, c, e1, e2, e3) {
    if (!window.AUD || typeof lantern !== 'function') return;
    const mk = () => Object.assign(document.createElement('canvas'), { width: W, height: H });
    if (!HALL.L) { HALL.L = mk(); HALL.P = mk(); HALL.C = mk(); }
    const zc = 1 + (c.z - 1) * .45, ccx = 960 + (c.cx - 960) * .5, ccy = 540 + (c.cy - 540) * .5;
    const base = new DOMMatrix([zc, 0, 0, zc, 960 - ccx * zc, 540 - ccy * zc]);
    const b = t2b(t), ph0 = (t / BT) % 1, live = b < 90 ? 1 : Math.max(.15, 1 - (b - 90) / 3);
    const call = callSpans().some(([a, z]) => t >= a && t < z);
    const wipe = [e1, e2, e3].map(e => (e > 0 && e < 1 ? S(PI * e) : 0)).reduce((q, v) => q + v, 0);
    let seed = 7; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
    const P = [];
    for (const [row, n, sc, y0, dx] of [[0, 12, .36, 1150, 0], [1, 10, .47, 1225, 80]]) {
      for (let i = 0; i < n; i++) {
        const q = AUD[Math.floor(rnd() * AUD.length)], x = -60 + dx + (i + .5) * (2040 / n) + (rnd() - .5) * 60, s = sc * (.9 + .2 * rnd()), ph = rnd(), flip = rnd() > .5;
        const bob = (call ? 20 : 8) * live * Math.max(0, S(PI * ((ph0 + ph * .3) % 1)));
        const sway = q.lantern ? (wipe * 14 + 3 * S(2 * PI * (t / BR) + i)) * live : 0;
        const M = base.translate(x, y0 - bob).scale(flip ? -s : s, s).rotate(flip ? -sway : sway);
        P.push({ q, M, s, ph, lc: q.lantern ? M.transformPoint(new DOMPoint(q.lc[0], q.lc[1])) : null });
      }
    }
    // silhouettes, their own lanterns' light on their hands, and the rims (pink catches their upper left, cyan their upper right)
    const A = HALL.L.getContext('2d'); A.setTransform(1, 0, 0, 1, 0, 0); A.globalCompositeOperation = 'source-over'; A.filter = 'none'; A.clearRect(0, 0, W, H);
    for (const p of P) { A.setTransform(p.M); A.fillStyle = '#0b0910'; A.fill(p.q.outlineP); }
    A.setTransform(1, 0, 0, 1, 0, 0); A.globalCompositeOperation = 'source-atop';
    for (const p of P) if (p.lc) { const R = p.q.lc[2] * p.s * zc * 3.2, g = A.createRadialGradient(p.lc.x, p.lc.y, 0, p.lc.x, p.lc.y, R);
      g.addColorStop(0, `rgba(70,98,190,${.7 * live})`); g.addColorStop(1, 'rgba(10,8,8,0)'); A.fillStyle = g; A.fillRect(p.lc.x - R, p.lc.y - R, 2 * R, 2 * R); }
    const rim = (cv, col, ox) => { const R = cv.getContext('2d'); R.setTransform(1, 0, 0, 1, 0, 0); R.globalCompositeOperation = 'copy'; R.drawImage(HALL.L, 0, 0);
      R.globalCompositeOperation = 'source-in'; R.fillStyle = col; R.fillRect(0, 0, W, H); R.globalCompositeOperation = 'destination-out'; R.drawImage(HALL.L, ox, 5); R.globalCompositeOperation = 'source-over'; };
    rim(HALL.P, `rgba(255,92,168,${.9 * live})`, 4); rim(HALL.C, `rgba(57,223,255,${.8 * live})`, -4);
    X.save(); X.setTransform(1, 0, 0, 1, 0, 0);
    X.filter = 'blur(1.2px)'; X.drawImage(HALL.L, 0, 0);
    X.globalCompositeOperation = 'lighter'; X.filter = 'blur(.8px)'; X.drawImage(HALL.P, 0, 0); X.drawImage(HALL.C, 0, 0);
    X.filter = 'blur(6px)'; X.globalAlpha = .45; X.drawImage(HALL.P, 0, 0); X.drawImage(HALL.C, 0, 0); X.restore();
    // the lanterns themselves (her chōchin, indigo), then their glow in the dark hall
    X.save(); X.filter = 'blur(.7px)'; for (const p of P) if (p.q.holesP) { X.setTransform(p.M); lantern(p.q.lc, p.s, t, p.ph); } X.restore();
    X.save(); X.setTransform(1, 0, 0, 1, 0, 0); X.globalCompositeOperation = 'screen';
    for (const p of P) if (p.lc) { const R = p.q.lc[2] * p.s * zc * 2.8, g = X.createRadialGradient(p.lc.x, p.lc.y, 0, p.lc.x, p.lc.y, R);
      g.addColorStop(0, `rgba(80,110,220,${.32 * live})`); g.addColorStop(1, 'rgba(60,96,190,0)'); X.fillStyle = g; X.fillRect(p.lc.x - R, p.lc.y - R, 2 * R, 2 * R); }
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

  // ---- the frame. frame() picks: the card itself (close views), or the room with the card in the butai window
  function frame(t, cast, opt = {}) {
    const c = camAt(t), roomOK = typeof stage === 'function' && typeof BUTAI !== 'undefined' && BUTAI.theatre && typeof SCREEN !== 'undefined';
    return (c.room || c.ots) && roomOK ? roomFrame(t, cast, opt, c) : cardFrame(t, cast, opt, c);
  }
  // the picture behind Clawd (everything of the card but her, the readers and the paper): e2 forced to 0 or 1 draws the card
  // before or after wipe 2
  function backdrop(t, c, W2S, e1, e2, e3, opt) {
    const b = t2b(t);
    camXform(X, c);
    const g = X.createLinearGradient(0, -200, 0, 720); g.addColorStop(0, '#0d0818'); g.addColorStop(1, '#241840'); X.fillStyle = g; X.fillRect(-500, -300, 2920, 1020);
    X.fillStyle = '#0a0612'; for (let i = 0; i < 9; i++) X.fillRect(-100 + i * 260, -40, 16, 80); X.fillRect(-400, -40, 2720, 18);   // truss
    for (const k of ['l', 'r']) drawLED(X, t, k);
    const [sx, sy, sw, sh] = SCR.c, edge = e => sx + sw * e;
    drawLED(X, t, 'c');
    const page = b >= WIPE3 ? (e3 < 1 ? [['verse', 1], ['blank', e3]] : [['blank', 1]]) : b >= WIPE2 ? [['verse1', 1], ['verse', e2]] : b >= WIPE1 ? [['verse1', e1]] : [];
    if (b < 82) for (const [which, e] of page) {
      if (e <= 0) continue;
      X.save(); X.beginPath(); X.rect(sx, sy, sw * e, sh); X.clip();
      const rect = drawPage(X, t, W2S, which);
      if (which === 'verse' && b >= 72) { X.save(); X.setTransform(1, 0, 0, 1, 0, 0); pixelCrab(X, t, rect); X.restore(); }   // rect is in screen px
      X.restore(); camXform(X, c);
      if (e < 1) { X.save(); X.fillStyle = 'rgba(255,255,255,.35)'; X.fillRect(edge(e) - 3, sy, 6, sh); X.restore(); }   // the turning edge
    }
    floor(X, t, b >= WIPE2 && b < 82 ? (b >= WIPE2 + 1.6 / 4 ? 1 : e2) : 0);
    beams(X, t, b >= WIPE2 && b < 82 ? e2 : 0);
    keyLight(X, t, opt.clawdX || 960);
    if (opt.footWorld) prints(X, t, opt.footWorld);
  }
  function cardFrame(t, cast, opt, c) {
    const W2S = W2Sof(c), b = t2b(t);
    const hand = opt.locateHand || (() => [960, 500]);
    const e1 = wipeProg(t, WIPE1, hand), e2 = wipeProg(t, WIPE2, hand), e3 = wipeProg(t, WIPE3, hand);
    X.setTransform(1, 0, 0, 1, 0, 0); X.fillStyle = K.ink; X.fillRect(0, 0, W, H);
    // wipe 2 is a card pull seen from inside (Fable): the paper edge crosses the whole picture with Clawd's hand, the next card
    // behind it; she stays, because she's live. So the picture behind her is drawn twice, split at the edge.
    if (e2 > 0 && e2 < 1) {
      const xe = e2 * W;
      X.save(); X.beginPath(); X.rect(0, 0, xe, H); X.clip(); backdrop(t, c, W2S, e1, 1, e3, opt); X.restore();
      X.save(); X.setTransform(1, 0, 0, 1, 0, 0); X.beginPath(); X.rect(xe, 0, W - xe, H); X.clip(); backdrop(t, c, W2S, e1, 0, e3, opt); X.restore();
      paperEdge(X, xe);
    } else backdrop(t, c, W2S, e1, e2, e3, opt);
    const pe = pullAt(t); if (pe !== null) paperEdge(X, pe);                   // verse 2's cards, pulled from her room
    camXform(X, c);
    cast(W2S, c);
    X.setTransform(1, 0, 0, 1, 0, 0);
    // the last bar: the lights die on the stage, and the lanterns are what's left
    if (b > 91.9) { X.fillStyle = `rgba(7,4,14,${(.86 * Math.min(1, (b - 91.9) / .9) ** 1.5).toFixed(3)})`; X.fillRect(0, 0, W, H); }
    crowd(X, t, c, e1, e2, e3);
    X.save(); X.globalCompositeOperation = 'screen'; X.fillStyle = 'rgba(60,40,90,.08)'; X.fillRect(0, 0, W, H); X.restore();   // haze
    // Fable's paper, in the card's screen space: the notes in the bottom margin (what she's writing in her room), the deckle
    if (window.marginNotes) {
      marginNotes(t, [[b2t(48.11), "Every story's borrowed till somebody stands to tell it."], [b2t(52.23), "I've read how it ends. I'd still like to see."],
                      [b2t(56.24), '~~That\'s the moral.~~ There isn\'t one. Keep walking.']], { clear: b2t(WIPE1) + .4 });
      if (b >= 84) marginNotes(t, [[b2t(84.24), 'Every story\'s borrowed. ...She wrote her own.']], { clear: b2t(92) });
    }
    if (window.washiBorder) washiBorder(t);
    return c;
  }
  // the room: the card offscreen, filmed in the butai window by the paper world's stage(), the room's readers, and Fable
  const ROOM = {};
  function roomFrame(t, cast, opt, c) {
    const mk = () => Object.assign(document.createElement('canvas'), { width: W, height: H });
    const card = ROOM.card || (ROOM.card = mk());
    withX(card.getContext('2d'), () => cardFrame(t, cast, opt, c));
    const b = t2b(t), cam = c.room || RC.ots, lit = b < 90 ? 1 : Math.max(.2, 1 - (b - 90) / 3);
    const R0 = SCREEN.rect; SCREEN.rect = [0, 15, 1920, 1050];                  // (the window's aspect: 1.828)
    try { stage(t, () => X.drawImage(card, 0, 0), { cam, doors: 1, spill: [255, 150, 215].map(v => Math.round(v * lit)) }); } finally { SCREEN.rect = R0; }
    X.setTransform(1, 0, 0, 1, 0, 0);
    if (c.ots) {                                                                 // over her shoulder: the window beyond, out of focus
      const buf = ROOM.buf || (ROOM.buf = mk()), g = buf.getContext('2d'); g.clearRect(0, 0, W, H); g.drawImage(X.canvas, 0, 0);
      X.save(); X.filter = 'blur(3px) brightness(.85)'; X.drawImage(buf, 0, 0); X.restore();
      if (typeof FABLESEAT !== 'undefined') FABLESEAT.ots(X, t, [], { flip: true, draw: 'write', spread: 'notes' });
      return c;
    }
    // (one audience: the hall's, inside the card; the room's readers are cut in world A)
    const k = cam.zoom * FROOM.m, fx = W / 2 + (FROOM.x - cam.x) * k, fy = H / 2 + (FROOM.y - cam.y) * k, fs = FROOM.s * k;
    if (typeof FABLESEAT !== 'undefined') FABLESEAT.draw(X, t, { x: fx, y: fy, s: fs, flip: true }, lit);
    return c;
  }
  return { frame, camAt, SCR, K, W2Sof, load };
})();
