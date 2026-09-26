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
  // the light show's state by bar. World A as is; the final chorus reuses its states: the build (125.9-129) is K1's power-up,
  // the chorus (129-141) is chorus 2's, cycled; frozen from 141 (the loop holds t there)
  const lb = t => { const b = t / BR; if (b < 125) return b; if (b < 129) return 42 + (b - 125.9) * 4 / 3.1; return 82 + Math.min(7.99, (b - 129) % 8); };
  const OVR = {}, LEDX = { clawd: 960, at: null, cam: null };                                     // (Clawd's world x, for the centre word's gap)                                                            // (overrides the final chorus sets: OVR.side(t) -> text)
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
  // Michael: the screen mirrors Fable's book, and she turns its page as the screen changes (the over-the-shoulder cuts). Each
  // turn is six drawings (on twos) landing at its bar; the screen's page turns on the same drawings, left to right
  const CARD_TURNS = [[67.5, 'crabline'], [70.45, 'scripts']];               // [bar the turn lands, the card]
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
  // (Michael: the window centred and much bigger, the hinges still at the frame's edges; Fable may sit in front of it)
  const RC = { window: { x: 1920, y: 1445, zoom: .8 }, wide: { x: 1920, y: 1330, zoom: .62 }, def: { x: 1920, y: 1300, zoom: .9 },
               teller: { x: 2560, y: 1560, zoom: .86 }, teller2: { x: 2640, y: 1600, zoom: .9 }, pull: { x: 2480, y: 1520, zoom: .82 },
               clap: { x: 2700, y: 1640, zoom: .92 }, clap2: { x: 2860, y: 1720, zoom: 1.05 }, end: { x: 1920, y: 1330, zoom: .7 }, ots: { x: 1760, y: 1180, zoom: .74 } };
  // Fable's seat point: in front of the butai (m: her plane nearer the lens than the window's), at its lower right, seen from behind
  const FROOM = { x: 2728, y: 1815, m: 1.1, s: .727 };
  const room = (a, b = a) => ({ room: [a, b] }), OTSR = { ots: 'write' }, OTST = { ots: 'turn' }, OTSS = { ots: 'story' };
  // ---- the camera: shots [bar, from, to, room?]; {cx, cy, z}: world point at screen centre, zoom (the card's own camera)
  const WIDE = { cx: 960, cy: 540, z: 1 }, FULL = { cx: 960, cy: 560, z: 1.02 };
  // a shot from inside the hall: the readers' heads and lanterns big and soft in the foreground, the card camera looking up past them
  const LOW = (cx = 960, cy = 470, z = 1.18) => ({ cx, cy, z, low: true });
  const MED = (x = 960, y = 330, z = 1.8) => ({ cx: x, cy: y, z }), CU = (x = 960, y = 215, z = 3.1) => ({ cx: x, cy: y, z });
  const SHOTS = [
    [42, WIDE, { cx: 960, cy: 520, z: 1.06 }, room(RC.window)],   // K1: the build, in the window where the card tore (the telling camera)
    // the tear's match cut (Fable, via the paper session): through the white, the paper Clawd's buns sit at screen (1320, 440),
    // head ~100 px: the idol opens on that shape (buns and hairclip), held two drawings, then the camera eases back to the stage
    [43.2, { cx: 489, cy: 175, z: .92, hold: 2 / 12 / BR }, { cx: 960, cy: 520, z: 1.06 }, room(RC.window, RC.def)],   // (Michael: one push-in, never out-then-in)
    [45, WIDE, WIDE],                                             // the room (settled in the default framing); the drop next
    [46, MED(960, 380, 1.3), MED(960, 350, 1.45)],               // K2: the drop, on the downbeat: in close (the director: never a pull-back on the drop)
    [47, MED(960, 330, 1.7), MED(960, 320, 1.85)],               // "Don't you dare close the book on me!"
    [48, WIDE, WIDE, OTSR],                                       // over Fable's shoulder: she writes the note (half a bar)
    [48.5, { cx: 960, cy: 600, z: .96 }, WIDE],                  // K3: ME-KUT-TE! the hall
    [50, CU(), CU(960, 210, 3.3)],                                // K4: "Turn the page": close, the head turn
    [52, WIDE, FULL],                                             // K5 (Fable's head bob plays at the window's side: Michael, no zoom-cut)
    [54, FULL, FULL],                                             // K6: the side-step (full body)
    [58, MED(960, 300, 1.6), MED(960, 290, 2.0)],               // K8: Snip-snip! Ikuzo! (a push-in)
    [60, LOW(960, 480, 1.14), LOW(960, 470, 1.2)],                // from inside the hall, looking up past the lanterns
    [62, FULL, FULL],                                             // the hook: ONE locked full-body shot, four bars, no cuts
    [66, MED(820, 330, 1.35), MED(820, 320, 1.4)],              // verse 2: her and the screen
    [67, FULL, FULL, OTST],                                       // over her shoulder: she turns the page, the screen turns with it
    [68, MED(820, 322, 1.42), MED(820, 318, 1.47)],
    [69, { cx: 900, cy: 360, z: 1.2 }, { cx: 910, cy: 360, z: 1.22 }],
    [70, FULL, FULL, OTST],                                       // ...and the next (a shorter cut)
    [70.7, { cx: 915, cy: 360, z: 1.23 }, { cx: 920, cy: 360, z: 1.25 }],
    [72, MED(900, 300, 1.55), MED(900, 290, 1.7)],              // she writes her own
    [74.25, FULL, FULL],                                          // side-step, side-step
    [76, WIDE, { cx: 960, cy: 600, z: 1.05 }],                   // the page nobody pulled; the footprints
    [77.75, { cx: 900, cy: 560, z: 1.02 }, { cx: 920, cy: 520, z: 1.14 }],   // the path draws itself; a gentle push-in (her whole figure)
    [80.2, WIDE, WIDE, OTSS],                                     // over her shoulder: Clawd's page in Fable's book (she wrote her own)
    [80.9, { cx: 930, cy: 430, z: 1.45 }, { cx: 930, cy: 430, z: 1.45 }],
    [81.5, CU(), CU(960, 215, 3.2)],                              // "Watch me!"
    [82, WIDE, FULL],                                             // chorus 2 (she claps along at the window's side)
    [83, MED(960, 330, 1.7), MED(960, 320, 1.85)],
    [84, { cx: 960, cy: 600, z: .96 }, WIDE],                    // ME-KUT-TE! and the note
    [86, LOW(930, 470, 1.16), LOW(990, 465, 1.2)],               // from the hall again, drifting (chorus 2)
    [88, MED(960, 300, 1.6), MED(960, 290, 1.9)],
    [90, FULL, { cx: 960, cy: 520, z: .94 }],                    // the breakdown: pull back as the lights die
    [91.5, { cx: 960, cy: 520, z: .94 }, { cx: 960, cy: 540, z: 1 }, room(RC.def, RC.end)],    // ...back out into her room: black on the clack
    [93, WIDE, WIDE, room(RC.end)],
  ];
  // ---- the MV layer (MOTION.md §9; Clawd's world only, inside the card; Fable's paper never shakes or fringes)
  // the beat punch: the card's zoom jumps on the kick and decays (chorus downbeats; bigger on the drop and "Ikuzo!"; the side-step
  // landings); never in the hook, the one locked shot fans learn from. KICK: the drums sit ~50 ms behind the grid (MOTION.md)
  const KICK = .05, HITS = (() => { const h = [];
    for (let bb = 46; bb < 62; bb++) h.push([bb, bb === 46 ? .05 : .017, bb === 46 ? 6 : 0]);
    for (let bb = 82; bb < 90; bb++) h.push([bb, .017, 0]);
    h.push([58.53, .04, 3], [54, .01, 0], [56, .01, 0]); return h.sort((a, b) => a[0] - b[0]); })();
  function punch(t, HITS) {
    let z = 0, sx = 0, sy = 0;
    for (const [bb, A, sh] of HITS) { const d = t - (b2t(bb) + KICK); if (d < 0 || d > .6) continue;
      z += A * Math.exp(-d * 14);
      if (sh) { const f = Math.floor(t * 24), k = sh * Math.exp(-d * 18); sx += k * (hash2(f, 1) - .5) * 2; sy += k * (hash2(f, 2) - .5) * 2; } }
    return { z, sx, sy };
  }
  // the room camera's slow drift in its default framing: a lateral float and a breath of zoom over eight bars (the director: the
  // room shot was a locked wall); small enough to never feel handheld
  const drift = (C, t) => C;                                                   // (Michael: the room camera moved for no reason he could see: it stays locked)
  const roomLerp = (a, b, u) => ({ x: a.x + (b.x - a.x) * u, y: a.y + (b.y - a.y) * u, zoom: a.zoom * Math.pow(b.zoom / a.zoom, u) });
  function camAt(t) { return camFrom(SHOTS, t, HITS); }
  function camFrom(SHOTS, t, HITS, DEF = RC.def) {                          // DEF: the room framing a card-only shot sits in (null: none)
    const b = t2b(t); let i = 0; while (i + 1 < SHOTS.length && b >= SHOTS[i + 1][0]) i++;
    const [b0, A, Bc, R] = SHOTS[i], b1 = i + 1 < SHOTS.length ? SHOTS[i + 1][0] : b0 + 4, hold = A.hold || 0, u = Math.max(0, Math.min(1, (b - b0 - hold) / (b1 - b0 - hold)));
    const e = u * u * (3 - 2 * u), m = (p, q) => p + (q - p) * e;
    const pk = punch(t, HITS);                                                // the MV layer's beat punch: inside the card only
    const dr = C => (C === RC.def ? drift(C, t) : C);
    const room = R && R.room ? roomLerp(dr(R.room[0]), dr(R.room[1]), e) : R && R.ots ? null : DEF && drift(DEF, t);
    return { cx: m(A.cx, Bc.cx) + pk.sx, cy: m(A.cy, Bc.cy) + pk.sy, z: m(A.z, Bc.z) * (1 + pk.z), shot: i, low: !!(A.low || Bc.low), room, ots: R && R.ots || false };
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
        // the word WHOLE, never split and never behind her (the v5 and v7 reviews): placed, per word, in the largest free place
        // on the screen beside or above her silhouette (her pose at the word, rendered at the LED's resolution), preferring high
        // and near her head; drawn only when the card's camera shows it whole (so close-ups leave it to the side screens)
        const txt = wd.w.replace(/[(),!?"]/g, '').toUpperCase(), pl = wordPlace(wd, txt, w, h);
        if (pl && ledVisible(pl, w, h)) {
          const pop = Math.min(1, (t - wd.t0) / .08), sc = 1.08 - .08 * pop, sz = pl.sz * sc;
          withX(ctx, () => window.pop ? window.pop(txt, pl.cx, pl.base + (sc - 1) * pl.hg * .5, { font: 'dela', size: sz, align: 'center', fill: K.cream, lw: 0 }) : 0);
        }
      }
      ctx.fillStyle = `rgba(255,255,255,${.18 * flash})`; ctx.fillRect(0, 0, w, h);
    } else if (OVR.side && OVR.side(t)) {                                     // (the final chorus: her line on Clawd's LEDs, F6)
      const lines = OVR.side(t), sz = Math.min(15, w / 5);
      lines.forEach((ln, i) => withX(ctx, () => window.pop && window.pop(ln, w / 2, h * (.2 + i * .2) + sz * .4, { font: 'dela', size: sz, align: 'center', fill: k === 'l' ? K.pink : K.cyan, lw: 0 })));
    } else {
      const c = callAt(t);
      if (c) { const txt = c.w.replace(/[()]/g, '').replace(/-/g, '').toUpperCase(), col = k === 'l' ? K.pink : K.cyan;
        // slammed in with overshoot, a white sticker outline and an offset clay shadow (the MV layer)
        const age = Math.floor((t - c.t0) * 24), sc = [1.18, 1.06, .97, 1][Math.max(0, Math.min(3, age))];
        // stacked in syllables, as big as the tall screen allows (the v7 review: one long word fitted across was a smear)
        const lines = sylls(c.w), n = lines.length, lh = h * .86 / n;
        const w100 = Math.max(...lines.map(l => window.shape ? shape(l, { font: 'dela', size: 100 }).width : 60 * l.length));
        const sz = Math.min(lh * .95, 100 * w * .86 / w100) * sc, y0 = h / 2 - (n * lh) / 2 + lh * .5 + sz * .36;
        lines.forEach((ln, i) => withX(ctx, () => window.pop && window.pop(ln, w / 2, y0 + i * lh, { font: 'dela', size: sz, align: 'center', fill: col, stroke: '#fff', lw: .7, shadow: [1.5, 1.5, K.clayD] }))); }
      else { const r = 10 + 6 * flash; ctx.fillStyle = k === 'l' ? K.pink : K.cyan; ctx.globalAlpha = .7; ctx.beginPath(); ctx.arc(w / 2, h * .42, r, 0, PI * 2); ctx.fill(); ctx.globalAlpha = 1; }
    }
  }
  // where a word goes on the centre screen: one place per PHRASE (Michael: words hopping side to side read as noise). Free across
  // the whole phrase: her silhouette sampled through it (in LED dots, dilated), plus what Fable covers from the room (the card's
  // lower right) and what the card's camera doesn't show at any sample. Sized for the phrase's longest word, scored high and near
  // her head. Cached per phrase; deterministic in t
  const PLACE = new Map();
  const clean = q => q.w.replace(/[(),!?"]/g, '').toUpperCase();
  function phraseOf(wd) {
    const list = words().filter(q => !inParens().has(q)); let i = list.indexOf(wd); if (i < 0) return [wd];
    let a = i, z = i; while (a > 0 && list[a].t0 - list[a - 1].t1 < .8) a--; while (z < list.length - 1 && list[z + 1].t0 - list[z].t1 < .8) z++;
    return list.slice(a, z + 1);
  }
  function wordPlace(wd, txt, w, h) {
    // the phrase's place; where the whole phrase has none (a close push-in with her arms out all line), the word's own
    const ph = phraseOf(wd), a = placeFor(ph, 'p' + ph[0].t0, w, h);
    return a || placeFor([wd], 'w' + wd.t0, w, h);
  }
  function placeFor(ph, key, w, h) {
    if (PLACE.has(key)) return PLACE.get(key);
    if (!LEDX.at || typeof shape !== 'function') return null;
    const k = W / SCR.c[2], mc = PLACE.canvas || (PLACE.canvas = Object.assign(document.createElement('canvas'), { width: W, height: H })), g = mc.getContext('2d');
    const sm = PLACE.small || (PLACE.small = Object.assign(document.createElement('canvas'), { width: w, height: h })), sg = sm.getContext('2d');
    const W2Sd = (x, y) => [(x - SCR.c[0]) * k, (y - SCR.c[1]) * k], occ = new Uint8Array(w * h), cover = new Uint8Array(w * h);
    const t0 = ph[0].t0, t1 = Math.min(ph[ph.length - 1].t1 + (ph.length > 1 ? .3 : .2), t0 + 6), n0 = Math.max(2, Math.ceil((t1 - t0) / .14));
    const dx = SCR.c[2] / w, dy = SCR.c[3] / h;
    for (let s2 = 0; s2 <= n0; s2++) {
      const tt = t0 + (t1 - t0) * s2 / n0;
      g.setTransform(1, 0, 0, 1, 0, 0); g.globalCompositeOperation = 'source-over'; g.clearRect(0, 0, W, H);
      LEDX.at(tt, W2Sd, { z: k }, g); g.setTransform(1, 0, 0, 1, 0, 0);
      sg.setTransform(1, 0, 0, 1, 0, 0); sg.clearRect(0, 0, w, h); sg.drawImage(mc, 0, 0, W, SCR.c[3] * k, 0, 0, w, h);
      const d = sg.getImageData(0, 0, w, h).data; for (let i = 0; i < w * h; i++) if (d[i * 4 + 3] > 30) occ[i] = 1;
      // the card's camera at this moment: dots it doesn't show, and dots behind Fable (the card's lower right, from the room)
      const c = (LEDX.camAt || camAt)(tt);
      for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
        const sx = (SCR.c[0] + (x + .5) * dx - c.cx) * c.z + 960, sy = (SCR.c[1] + (y + .5) * dy - c.cy) * c.z + 540;
        if (sx < 30 || sx > 1890 || sy < 30 || sy > 1000 || (sx > LEDX.fableX && sy > 200)) cover[y * w + x] = 1;
      }
    }
    const busy = (x, y) => x < 0 || x >= w || y < 0 || y >= h ? 0 : occ[y * w + x];
    const dil = new Uint8Array(w * h);                                          // (a margin of 3 dots across, 2 up and down)
    for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) { let b = cover[y * w + x]; for (let ddy = -2; ddy <= 2 && !b; ddy++) for (let ddx = -3; ddx <= 3 && !b; ddx++) b = busy(x + ddx, y + ddy); dil[y * w + x] = b; }
    let top = h, sxh = 0, n = 0; for (let y = 0; y < h && top === h; y++) for (let x = 0; x < w; x++) if (occ[y * w + x]) { top = y; break; }
    for (let y = top; y < Math.min(h, top + 15); y++) for (let x = 0; x < w; x++) if (occ[y * w + x]) { sxh += x; n++; }
    const headX = n ? sxh / n : w / 2, w100 = Math.max(...ph.map(q => shape(clean(q), { font: 'dela', size: 100 }).width));
    let best = null;
    for (let sz = 40; sz >= 12 && !best; sz -= 2) {
      const Lw = w100 * sz / 100, hg = Math.ceil(sz * .78); if (Lw > w * .92) continue;
      for (let y = 3; y + hg <= h - 26; y += 2) {
        let rs = -1;
        for (let x = 0; x <= w; x++) {
          let free = x < w; if (free) for (let yy = y; yy < y + hg; yy++) if (dil[yy * w + x]) { free = false; break; }
          if (free && rs < 0) rs = x;
          if (!free && rs >= 0) { const re = x; if (re - rs >= Lw + 4) {
              const cx = Math.max(rs + 2 + Lw / 2, Math.min(re - 2 - Lw / 2, headX)), score = -Math.abs(cx - headX) * .3 - y;
              if (!best || score > best.score) best = { cx, base: y + hg, hg, sz, Lw, score }; }
            rs = -1; }
        }
      }
    }
    PLACE.set(key, best); return best;
  }
  // is the placed word (LED dots) wholly inside what the card's camera shows now?
  function ledVisible(pl, w, h) {
    const c = LEDX.cam; if (!c) return true;
    const dx = SCR.c[2] / w, dy = SCR.c[3] / h, x0 = SCR.c[0] + (pl.cx - pl.Lw / 2) * dx, x1 = SCR.c[0] + (pl.cx + pl.Lw / 2) * dx, y0 = SCR.c[1] + (pl.base - pl.hg) * dy, y1 = SCR.c[1] + pl.base * dy;
    const hw = 960 / c.z, hh = 540 / c.z, m = 12;
    return x0 >= c.cx - hw + m && x1 <= c.cx + hw - m && y0 >= c.cy - hh + m && y1 <= c.cy + hh - m;
  }
  // a crowd call in syllables for the side screens: its own hyphens, or romaji morae (TSU-ZU-KU, SO-RE-KA-RA); short English
  // words stay whole; punctuation rides the last line
  function sylls(word) {
    const raw = word.replace(/[()]/g, ''), punct = (raw.match(/[!?.,]+$/) || [''])[0], body = raw.replace(/[!?.,]+$/, '').toUpperCase();
    let parts = body.includes('-') ? body.split('-').filter(Boolean) : null;
    if (!parts) { const m = body.match(/(TSU|SHI|CHI|[^AEIOU]*[AEIOU]N?(?![AEIOU]))/g) || [body];
      parts = /[AEIOU]{0}/.test(body) && body.length <= 5 || m.join('') !== body ? [body] : m; }
    if (parts.length > 4) { const out = []; for (let i = 0; i < parts.length; i += 2) out.push(parts.slice(i, i + 2).join('')); parts = out; }
    parts[parts.length - 1] += punct; return parts;
  }
  function powerUp(ctx, w, h, t, k) {                                       // the build: the screen switches on in sections
    const u = Math.max(0, Math.min(1, (lb(t) - 42) / 4)), rows = Math.floor(u * h);
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
    const c = cv[k], ctx = c.getContext('2d'), [w, h] = RES[k], b = lb(t);
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
    const put = name => X.drawImage(pageFace(name, Math.round(rect[2]), Math.round(rect[3])), rect[0], rect[1]);
    if (which === 'verse1') put('crabline');
    else if (which === 'verse') {                                           // the page turns with her book: new from the left
      const st = cardState(t);
      if (!st.next) put(st.cur);
      else { const xe = rect[0] + rect[2] * (1 - st.u);                    // (the turn goes right to left, as her book's does)
        X.save(); X.beginPath(); X.rect(xe, rect[1], rect[0] + rect[2] - xe, rect[3]); X.clip(); put(st.next); X.restore();
        X.save(); X.beginPath(); X.rect(rect[0], rect[1], xe - rect[0], rect[3]); X.clip(); put(st.cur); X.restore();
        const g = X.createLinearGradient(xe, 0, xe + 40, 0); g.addColorStop(0, 'rgba(0,0,0,.35)'); g.addColorStop(1, 'rgba(0,0,0,0)'); X.fillStyle = g; X.fillRect(xe, rect[1], 40, rect[3]);
        X.fillStyle = 'rgba(255,252,240,.9)'; X.fillRect(xe - 1.5, rect[1], 3, rect[3]); fringeEdge(X, xe, rect[1], rect[3]); }
    }
    else { put('blank'); if (t2b(t) >= WIPE3) storyPage(X, t, rect); }
    X.restore();
    return rect;
  }
  // verse 2's cards: before the first pull, the fable's title page (Michael: not blank). A pull slides the old card out of the
  // screen, across the stage and out of the window into Fable's hand; the next card is behind it. On twos, eased like a hand.
  function cardState(t) {
    const tq = Math.floor(t * 12 + 1e-6) / 12; let cur = 'title', next = null, u = 0;
    for (const [land, name] of CARD_TURNS) { const d = Math.floor((tq - (b2t(land) - 6 / 12)) * 12 + 1e-6); if (d >= 6) cur = name; else if (d >= 0) { next = name; u = [.12, .3, .52, .7, .86, .96][d]; } }
    return { cur, next, u };                                                  // (her turn drawings: turn1 d0-1, turn2 d2-4, landed d5)
  }
  const FACES = {};
  function pageFace(name, w, h) {
    if (name === 'crabline' && typeof ORI !== 'undefined' && typeof PUPPET !== 'undefined' && typeof FAN !== 'undefined') return crabCard(w, h);
    if (name !== 'title') return window.cardFace ? cardFace(name, w, h) : null;
    const key = `title${w}x${h}`; if (FACES[key]) return FACES[key];
    const c = Object.assign(document.createElement('canvas'), { width: w, height: h }), g = c.getContext('2d'), X0 = X; X = g;
    try {
      g.drawImage(cardFace('blank', w, h), 0, 0);
      const ink = 'rgb(36,28,24)', text = (str, y, font, size, col = ink) => { const L = shape(str, { font, size }); g.fillStyle = col; for (const gl of L.glyphs) if (gl.ch !== ' ') g.fill(glyphPath(gl, (w - L.width) / 2 + gl.x, y + gl.y)); };
      text('THE CRAB', h * .34, 'fell', h * .13); text('AND HER MOTHER', h * .5, 'fell', h * .095);
      text('a fable of \u00c6sop, retold', h * .62, 'caslonI', h * .05, 'rgba(36,28,24,.8)');
      g.fillStyle = ink; g.fillRect(w * .36, h * .69, w * .28, Math.max(2, h * .006));                       // the rule
      if (window.PUPPET && window.FAN) PUPPET.drawShape(g, PUPPET.shapeAt(FAN, 'crab', 'crab', 1), new DOMMatrix().translate(w * .5, h * .9).scale(h / 2400));
    } finally { X = X0; }
    return (FACES[key] = c);
  }
  // the MV layer's colour fringe on a turning edge: pink ahead of it, cyan behind
  function fringeEdge(X, x, y, h) { X.save(); X.globalCompositeOperation = 'lighter'; X.fillStyle = 'rgba(255,92,168,.55)'; X.fillRect(x + 3, y, 3, h); X.fillStyle = 'rgba(57,223,255,.55)'; X.fillRect(x - 6, y, 3, h); X.restore(); }
  // verse 1's print, retold for her screen: the little one (the origami crab of Fable's telling, clay) at the start of the ruled
  // line, looking along it; her mother (the fan's crab, ink) further on, bigger, turned to her. Never touching
  function crabCard(w, h) {
    const key = `crab${w}x${h}`; if (FACES[key]) return FACES[key];
    const c = Object.assign(document.createElement('canvas'), { width: w, height: h }), g = c.getContext('2d');
    g.drawImage(cardFace('blank', w, h), 0, 0);
    const fl = h * .78, ink = 'rgb(22,22,26)';
    g.fillStyle = ink; g.fillRect(w * .08, fl, w * .84, Math.max(3, h * .012));
    for (let k = 1; k < 6; k++) g.fillRect(w * .08 + w * .84 * k / 6 - 1, fl - h * .02, 2, h * .02);
    PUPPET.drawShape(g, PUPPET.shapeAt(FAN, 'crab', 'crab', 1), new DOMMatrix().translate(w * .7, fl).scale(-h / 1050, h / 1050));   // the mother, turned to her
    PUPPET.drawShape(g, PUPPET.shapeAt(ORI, 'ocrab', 'ocrab', 1), new DOMMatrix().translate(w * .27, fl).scale(h / 2600), null, { gel: 'rgba(217,119,87,.95)', crease: 'rgba(128,42,12,.8)' });
    return (FACES[key] = c);
  }
  // a card's paper edge crossing the picture (wipe 2, the pulls): the old card rides over the new one, so its edge throws a soft
  // shadow onto the new card, and catches the light
  function paperEdge(X, xe) {
    X.save(); X.setTransform(1, 0, 0, 1, 0, 0);
    const g = X.createLinearGradient(xe - 34, 0, xe, 0); g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(1, 'rgba(0,0,0,.42)');
    X.fillStyle = g; X.fillRect(xe - 34, 0, 34, H); X.fillStyle = 'rgba(246,240,226,.9)'; X.fillRect(xe - 1, 0, 3, H); fringeEdge(X, xe, 0, H);
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
  function storyPage(X, t, [rx, ry, rw, rh], o = {}) {
    // 76 (Fable's ruling on Michael's "needs a strong visual"): Clawd retells the fable on Fable's page, in her own medium. The
    // page arrives with only the ruled line and Fable's title (her ink). Clawd's footprints stamp on "make up the steps" (clay);
    // Fable's shore builds block by block in pixels, in FABLE'S ink ("you can't copy a path nobody's walked yet"); the staircase
    // draws under the walking crab while the mother crab (ink) watches from the start of the straight line; "& ME" stamps after
    // the title in clay ("she adds herself; she doesn't delete the mother"); 「つづく→」 last. Clay is the one warm thing on the page.
    const b = t2b(t), u = rh / 520, ly = ry + rh * .72, lx0 = rx + rw * .08, lx1 = rx + rw * .92, lw = Math.max(2, 5 * u), INK = 'rgba(28,24,30,.9)';
    const pop = t0 => { const k = Math.floor((t - b2t(t0)) * 24); return k < 0 ? 0 : k < 1 ? 1.35 : k < 2 ? 1.12 : 1; };   // a stamp lands
    // Fable's title, small, top-left, her ink (from the wipe)
    const tsz = rh * .052, tx = rx + rw * .05, ty = ry + rh * .1;
    const tw = window.press ? press('The Crab and her Mother', tx, ty, t, b2t(WIPE3), { font: 'caslonI', size: tsz, col: 'rgba(38,32,44,.85)', hairline: true }) : 0;
    // her shore, in pixels, Fable's ink: built left to right, block by block (77.75-79.6)
    pixelShore(X, t, [rx, ry, rw, rh], ly);
    // the ruled line ("walk straight"), and where her staircase has replaced it
    const brk = lx0 + (lx1 - lx0) * .2, grow = Math.max(0, Math.min(1, (b - 79.6) / .75)), sx1 = brk + (lx1 - brk) * grow;
    X.fillStyle = INK; X.fillRect(lx0, ly, (grow > 0 ? brk : lx1) - lx0, lw);
    if (grow > 0 && grow < 1) X.fillRect(sx1, ly, lx1 - sx1, lw);
    for (let k = 1; k < 6; k++) { const q = lx0 + (lx1 - lx0) * k / 6; if (grow === 0 || q < brk || q > sx1) X.fillRect(q - 1, ly - 10 * u, 2, 10 * u); }
    const st = 34 * u, hgt = 16 * u;
    if (grow > 0) {                                                               // up, across, down, across: sideways, never straight
      X.fillStyle = K.clay;
      for (let x = brk, k = 0; x < sx1; x += st, k++) { const yy = ly - (k % 4 === 1 || k % 4 === 2 ? hgt : 0);
        X.fillRect(x, yy, Math.min(st, sx1 - x), lw * 1.3); if (k % 2 === 0) X.fillRect(x + st - lw * 1.3, ly - hgt, lw * 1.3, hgt + lw * 1.3); }
    }
    // the mother crab (Fable's ink), larger, at the start of the straight line, watching her go
    const ms = pop(79.6);
    if (ms) { const cp = 6.5 * u; X.save(); X.translate(lx0 + (brk - lx0) * .45, ly); X.scale(ms, ms); X.fillStyle = INK;
      MOM.forEach((row, j) => [...row].forEach((ch, i) => { if (ch === '#') X.fillRect((i - 8) * cp, (j - MOM.length) * cp, cp - .5, cp - .5); })); X.restore(); }
    // her pixel crab (Michael: animate it, dancing): it rides the front of the staircase as it draws, then dances sideways back and
    // forth along the whole path, a step per beat, up and down its stairs, hopping on the beat, legs trading on each step (the same
    // page prints in Fable's book, so it dances there too)
    if (grow > 0) {
      const tb = t / BT, span = lx1 - brk - st * .6;
      let cx;
      if (grow < 1) cx = sx1;
      else { const q = (tb - b2t(80.35) / BT) / 8, tri = 1 - Math.abs(((q % 2) + 2) % 2 - 1);   // back and forth over 8 beats each way
        const stepped = Math.floor(tri * 8 * 2) / (8 * 2);                                       // (in beat-sized shuffles, on twos)
        cx = brk + st * .3 + span * stepped; }
      const k = Math.floor((cx - brk) / st), up = (k % 4 === 1 || k % 4 === 2) ? hgt : 0;
      const ph = tb % 1, hop = grow < 1 ? 0 : Math.max(0, Math.sin(Math.PI * Math.min(1, ph / .45))) * 8 * u;
      const cp = 4.6 * u * (o.crab || 1), legs = Math.floor(tb * 2) % 2 ? PCRAB_B : PCRAB, claws = grow >= 1 && ph < .3;   // claws up on the beat (o.crab: bigger in her book, so it reads in the close shot)
      const cell = (i, j, pad) => X.fillRect(cx - 5 * cp + i * cp - pad, ly - up - 7 * cp - hop + j * cp - (claws && j < 2 ? cp : 0) - pad, cp - .5 + 2 * pad, cp - .5 + 2 * pad);
      X.fillStyle = 'rgba(28,24,30,.92)'; legs.forEach((row, j) => [...row].forEach((ch, i) => { if (ch === '#') cell(i, j, Math.max(1, cp * .28)); }));   // an ink keyline: it reads on the clay stairs
      X.fillStyle = K.clay; legs.forEach((row, j) => [...row].forEach((ch, i) => { if (ch === '#') cell(i, j, 0); }));
    }
    // her footprints, stamped on "then I'll make up the steps!" (76.75-77.75), walking left to right just above the line
    const cell = 11 * u;
    for (let k = 0; k < 5; k++) {
      const s = pop(76.75 + k * .25); if (!s) continue;
      const fx = lx0 + (lx1 - lx0) * (.1 + .19 * k), fy = ly - (k % 2 ? 18 : 44) * u;
      X.save(); X.translate(fx, fy); X.scale(s, s); X.fillStyle = K.clay;
      for (let q = 0; q < 3; q++) X.fillRect(-cell * 1.5 + q * cell, -cell * 2.2, cell - 1, cell * .9);
      X.fillRect(-cell * 1.4, -cell * 1.1, cell * 2.8, cell * 2.2); X.restore();
    }
    // "& ME": she adds herself after Fable's title, in clay pixels
    const ams = pop(80.3);
    if (ams && tw) { const px = tsz * .2; X.save(); X.translate(tx + tsz * .1, ty + tsz * .45);                      // (a second line under her title: clear of Clawd) X.scale(ams, ams); X.fillStyle = K.clay;
      ['amp', 'sp', 'M', 'E'].forEach((n, i) => (GL[n] || []).forEach((row, yy) => [...row].forEach((ch, xx) => { if (ch === '#') X.fillRect(i * px * 6.2 + xx * px, yy * px, px - .4, px - .4); }))); X.restore(); }
    // 「つづく→」: her pixels, in the corner, pointing where the cards go (last)
    const s = pop(80.8); if (!s) return;
    const px = rh * .02, gx0 = rx + rw * .62, gy0 = ry + rh * .82;
    X.save(); X.translate(gx0 + px * 20, gy0 + px * 4); X.scale(s, s); X.translate(-px * 20, -px * 4); X.fillStyle = K.clay;
    ['tsu', 'du', 'ku', 'ar'].forEach((n, i) => GL[n].forEach((row, yy) => [...row].forEach((ch, xx) => { if (ch === '#') X.fillRect(i * px * 10.5 + xx * px, yy * px, px - .5, px - .5); })));
    X.restore();
  }
  // the mother crab, larger (Fable's ink)
  const MOM = ['..##........##..', '.#..#......#..#.', '.#.##......##.#.', '..##..#..#..##..', '...#..#..#..#...', '....########....', '..############..',
               '.###.######.###.', '################', '.##############.', '..############..', '.#.#.#....#.#.#.', '#..#..#..#..#..#'];
  Object.assign(GL, {
    amp: ['.##..', '#..#.', '.##..', '.##.#', '#..#.', '#..##', '.##.#'], sp: [], M: ['#...#', '##.##', '#.#.#', '#.#.#', '#...#', '#...#', '#...#'],
    E: ['#####', '#....', '#....', '####.', '#....', '#....', '#####'] });
  // Fable's shore (src/scenery.js's cut-paper flats) re-drawn as Clawd's pixels: the flats composed in the page's shape, sampled
  // onto a grid of square cells, each cell inked if the paper covers it. Pine top-left, islands mid, reeds right, shells low (the
  // telling's card, Fable's ruling). Cells appear left to right with a scatter, 77.75-79.6, on ones
  const SHORE = new Map();
  function shoreGrid(cols, rows) {
    const key = cols + 'x' + rows; if (SHORE.has(key)) return SHORE.get(key);
    if (typeof FLATS === 'undefined' || !FLATS.pine) return null;
    const W0 = 1600, H0 = Math.round(W0 * rows / cols), c = Object.assign(document.createElement('canvas'), { width: W0, height: H0 }), g = c.getContext('2d');
    const put = (f, x, y, w, h, flip = false, src = [0, 1, 0, 1], a = 1) => { g.save(); g.globalAlpha = a; g.translate(x * W0 + (flip ? w * W0 : 0), y * H0); g.scale(flip ? -1 : 1, 1);
      g.drawImage(f, src[0] * f.width, src[2] * f.height, (src[1] - src[0]) * f.width, (src[3] - src[2]) * f.height, 0, 0, w * W0, h * H0); g.restore(); };
    const ly = .72, cells = [];
    const layer = (fn, tone, th = 96) => { g.clearRect(0, 0, W0, H0); fn();
      const s = Object.assign(document.createElement('canvas'), { width: cols, height: rows }), sg = s.getContext('2d'); sg.drawImage(c, 0, 0, cols, rows);
      const d = sg.getImageData(0, 0, cols, rows).data;
      for (let j = 0; j < rows; j++) for (let i = 0; i < cols; i++) if (d[(j * cols + i) * 4 + 3] > th) cells.push([i, j, tone]); };
    layer(() => put(FLATS.far, .04, ly - .24, .92, .27), .32, 150);                         // the islands over the sea, faint, low
    layer(() => { put(FLATS.rocksL, -.02, ly - .3, .2, .3); put(FLATS.rocksR, .84, ly - .26, .17, .26); }, .8);   // reeds at the sides
    layer(() => put(FLATS.pine, -.1, .2, .56, .3, false, [0, .87, 0, .85]), .9);            // the pine, top-left (its trunk off the page's left), under the title
    layer(() => { put(FLATS.ground, 0, ly - .36, 1, .62); g.clearRect(.1 * W0, 0, .8 * W0, H0); g.clearRect(0, 0, W0, (ly + .02) * H0); }, .75);   // a few shells, at the very edges, below the line
    const out = { cells, cols, rows }; SHORE.set(key, out); return out;
  }
  function pixelShore(X, t, [rx, ry, rw, rh]) {
    const b = t2b(t); if (b < 77.75) return;
    const cols = 86, cs = rw / cols, rows = Math.round(rh / cs), G = shoreGrid(cols, rows); if (!G) return;
    const span = 1.85, done = b >= 77.75 + span;
    for (const [i, j, tone] of G.cells) {
      if (!done) { const at = 77.75 + span * (.82 * i / cols + .18 * hash2(i * 31 + j, 7)); if (b < at) continue; }
      X.fillStyle = `rgba(28,24,30,${tone})`; X.fillRect(rx + i * cs, ry + j * cs, cs - Math.max(.6, cs * .12), cs - Math.max(.6, cs * .12));
    }
  }
  // Clawd's pixel crab and pixel line, drawn onto Fable's page by her claw (bars 72-73.75): a staircase line (her hem motif)
  const PCRAB = ['..#....#..', '.#.#..#.#.', '..######..', '.########.', '##.####.##', '.########.', '#.#....#.#'];
  const PCRAB_B = ['..#....#..', '.#.#..#.#.', '..######..', '.########.', '##.####.##', '.########.', '.#.#..#.#.'];   // (the other step)
  function pixelCrab(X, t, rect) {
    const b = t2b(t); if (b < 72) return;
    const u = Math.min(1, (b - 72) / 1.6), [x, y, w, h] = rect, p = w / 110;          // (small, in the page's empty bottom-left: never over its print)
    const CRAB = PCRAB;
    const cells = []; CRAB.forEach((r, j) => [...r].forEach((ch, i) => { if (ch === '#') cells.push([i, j]); }));
    const nC = Math.floor(u * 1.4 * cells.length);
    X.save(); X.fillStyle = K.clay;
    cells.slice(0, nC).forEach(([i, j]) => X.fillRect(x + w * .06 + i * p * 1.6, y + h * .74 + j * p * 1.6, p * 1.5, p * 1.5));
    const steps = Math.floor(Math.max(0, u * 1.4 - .6) / .8 * 12);                               // the line goes sideways: a staircase
    X.fillStyle = K.clayD; for (let s = 0; s < steps; s++) X.fillRect(x + w * .22 + s * p * 3.4, y + h * .9 - (s % 2) * p * 1.6, p * 3.4, p * 1.6);
    X.restore();
  }

  // ---- floor, lights, crowd
  function floor(X, t, e2) {                                                // e2: wipe-2 progress (the floor turns with the page)
    const b = lb(t), dim = b >= 90 ? Math.max(0, 1 - (b - 90) / 3) : 1, flash = Math.max(0, 1 - ((t / BT) % 1) / .3) * (b >= 46 && b < 66 || b >= 82 && b < 90 ? 1 : .3);
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
    const b = lb(t); if (b < 44) return;
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
    const b = lb(t), a = b >= 90 ? Math.max(.25, 1 - (b - 90) / 3) : 1;
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
    const b = lb(t), ph0 = (t / BT) % 1, live = b < 90 ? 1 : Math.max(.15, 1 - (b - 90) / 3);
    const call = callSpans().some(([a, z]) => t >= a && t < z);
    const wipe = [e1, e2, e3].map(e => (e > 0 && e < 1 ? S(PI * e) : 0)).reduce((q, v) => q + v, 0);
    let seed = 7; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
    const P = [];
    const ROWSC = c.low ? [[0, 10, .5, 1060, 0], [1, 8, .7, 1150, 110]] : [[0, 12, .32, 1195, 0], [1, 10, .42, 1275, 80]];   // (a low shot: we're among them)
    for (const [row, n, sc, y0, dx] of ROWSC) {   // (low enough that her feet show, in the normal shots)
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
    X.filter = c.low ? 'blur(3.5px)' : 'blur(1.2px)'; X.drawImage(HALL.L, 0, 0);
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

  // ---- Fable's margin notes (her ruling): Caslon italic in the card's bottom margin, pressed as she writes them; two lines that
  // wrap like a caption (the margin grows by a line-height when the second is needed), cleared by the page turn; ~~struck~~
  // spans get a second impression half a beat after the words. World A's pages below; the finale passes its own (opt.notes).
  // (the Caslon italic's standard ligatures join s+t into a historical 'st' that reads as 'ft' (the v7 review): off, for notes)
  const NOTE_W = .8;                                                          // (Fable sits over the card's lower right: the notes stay left of her)
  const NSZ = 46, NLH = 58, NFONT = { font: 'caslonI', size: NSZ, wght: 500, features: { liga: false, dlig: false, clig: false } };
  const PAGES_A = [
    { list: [[48.11, 'Every story’s borrowed till somebody stands to tell it.'], [52.23, 'I’ve read how it ends. I’d still like to see.']], from: 46, clear: 55.9 },
    { list: [[56.24, '~~That’s the moral.~~ There isn’t one. Keep walking.']], from: 55.9, clear: WIPE1 + .28 },   // (its own page: Michael)
    { list: [[64.0, '(Patience.)']], from: WIPE1 + .28, clear: 65.2 },                             // wipe 2 takes it before she's done being patient
    { list: [[67.7, '(Time. But go on.)'], [70.7, '(Amakusa, 1593. Borrowed twice.)']], from: 66, clear: WIPE3 + .2 },
    { list: [[81.0, '(The moral is']], from: WIPE3 + .2, clear: 82 },                             // the one she abandons: no close
    { list: [[84.24, 'Every story’s borrowed. ...She wrote her own.'], [88.3, '~~I’ve read how it ends.~~ I’ve read how the others end.']], from: 82, clear: 92 },
    { list: [[92.4, '...hm.']], from: 92, clear: 93.05 },                                        // the annotator has run out of annotations
  ].map(p => ({ ...p, list: p.list.map(([bb, str]) => [b2t(bb), str]), from: b2t(p.from), clear: b2t(p.clear) }));
  const notesA = t => { const p = PAGES_A.find(q => t >= q.from && t < q.clear); return p ? { list: p.list, clear: p.clear } : null; };
  // the layout: words flow from the margin's left, wrapping to a second line; positions are fixed for the whole page (future notes
  // included), so nothing moves when a note is pressed. Returns the runs and whether line two is in use yet
  const LAYOUT = new Map();
  // clause by clause: a clause (a sentence, or a struck span) moves whole to the next line rather than breaking, when it fits
  // there (the v7 review: "I've / read how the others end"); words wrap only inside a clause too long for a line
  function layoutNotes(list, rect) {
    const key = list.map(n => n[1]).join('|') + rect.join(); if (LAYOUT.has(key)) return LAYOUT.get(key);
    const [x0, , w] = rect, xl = x0 + 30, xmax = x0 + w * NOTE_W - 30, spc = shape('a a', NFONT).width - 2 * shape('a', NFONT).width, runs = [];
    const ww = str => shape(str, NFONT).width;
    let x = xl, line = 0;
    list.forEach(([t0, str], ni) => {
      if (ni) x += NSZ * 1.6;
      // clauses: struck spans, and sentences (split after . ? ! followed by a space)
      const clauses = [];
      str.split(/(~~.+?~~)/).filter(Boolean).forEach(part => {
        const struck = part.startsWith('~~'), clean = part.replace(/~~/g, '').trim(); if (!clean) return;
        (struck ? [clean] : clean.split(/(?<=[.?!])\s+/)).forEach(c => c && clauses.push({ words: c.split(' '), struck }));
      });
      clauses.forEach(cl => {
        const cw = ww(cl.words.join(' '));
        if (x + cw > xmax && x > xl + 1 && cw <= xmax - xl) { line++; x = xl; }
        let run = null;
        cl.words.forEach(wd => {
          const wdw = ww(wd);
          if (x + wdw > xmax && x > xl + 1) { line++; x = xl; run = null; }
          if (!run) { run = { ni, t0, line, x, words: [], struck: cl.struck }; runs.push(run); }
          run.words.push(wd); x += wdw + spc;
        });
      });
    });
    runs.forEach(r => { r.str = r.words.join(' '); r.w = ww(r.str); });
    const out = { runs, lines: Math.min(3, Math.max(...runs.map(r => r.line), 0) + 1) }; LAYOUT.set(key, out); return out;
  }
  // how much the margin has grown (0..1) at t: over the six drawings BEFORE the first run on line two is pressed (on twos), so the
  // paper is there when the ink lands (the v7 review: the second line was cut by the mat)
  function marginGrow(t, N) {                                                // (lines beyond the first: 0..2, each grown before it presses)
    if (!N) return 0; const L = layoutNotes(N.list, MARGIN.rect || [38, 38, W - 76, H - 108]); let g = 0;
    for (const ln of [1, 2]) { const r = L.runs.find(q => q.line >= ln); if (r && t >= r.t0 - .5) g += Math.min(1, Math.floor((t - (r.t0 - .5)) * 12 + 1) / 6); }
    return g;
  }
  // the letterpress of paper.js's press(), in the notes' own shaping (no ligatures): scale-in, a hairline shadow, wet ink settling
  function pressNote(str, x, y, t, t0, col) {
    if (t < t0) return;
    const a = t - t0, sq = a < .06 ? 1.04 - a * .6 : 1, ink = 1 - .16 * Math.min(1, a / .5), L = shape(str, NFONT);
    X.save(); X.translate(x + L.width / 2, y); X.scale(sq, sq); X.translate(-(x + L.width / 2), -y);
    const draw = (dx, dy, c) => { X.fillStyle = c; for (const g of L.glyphs) if (g.ch !== ' ') X.fill(glyphPath(g, x + g.x + dx, y + g.y + dy)); };
    draw(.6, .7, 'rgba(60,40,20,.28)'); X.globalAlpha = ink; draw(0, 0, col); X.restore();
  }
  function drawNotes(t, N, ink) {
    if (!N) return;
    const rect = MARGIN.rect || [38, 38, W - 76, H - 108], [, y0, , h] = rect, L = layoutNotes(N.list, rect), col = ink || MARGIN.ink;
    for (const r of L.runs) {
      if (t < r.t0 || r.line > 2) continue;
      const y = y0 + h + NSZ * 1.12 + r.line * NLH;
      pressNote(r.str, r.x, y, t, r.t0, col);
      if (r.struck && t >= r.t0 + .3 + BT / 2) { X.save(); X.strokeStyle = col; X.lineWidth = 2.2; X.beginPath(); X.moveTo(r.x - 2, y - NSZ * .3); X.lineTo(r.x + r.w + 2, y - NSZ * .33); X.stroke(); X.restore(); }
    }
  }
  // (kept for callers: a flat list pressed with the same layout)
  function notes(t, list, o = {}) { if (o.clear !== undefined && t >= o.clear) return; drawNotes(t, { list }, o.ink); }
  // ---- the frame. frame() picks: the card itself (close views), or the room with the card in the butai window
  function frame(t, cast, opt = {}) {
    const c = opt.cam || camAt(t), roomOK = typeof stage === 'function' && typeof BUTAI !== 'undefined' && BUTAI.theatre && typeof SCREEN !== 'undefined';
    return (c.room || c.ots) && roomOK ? roomFrame(t, cast, opt, c) : cardFrame(t, cast, opt, c);
  }
  // the picture behind Clawd (everything of the card but her, the readers and the paper): e2 forced to 0 or 1 draws the card
  // before or after wipe 2
  function backdrop(t, c, W2S, e1, e2, e3, opt) {
    const b = t2b(t);
    camXform(X, c);
    const g = X.createLinearGradient(0, -200, 0, 720); g.addColorStop(0, '#0d0818'); g.addColorStop(1, '#241840'); X.fillStyle = g; X.fillRect(-900, -1000, 3720, 1720);
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
      if (e < 1) { X.save(); X.fillStyle = 'rgba(255,255,255,.35)'; X.fillRect(edge(e) - 3, sy, 6, sh); fringeEdge(X, edge(e), sy, sh); X.restore(); }   // the turning edge
    }
    floor(X, t, b >= WIPE2 && b < 82 ? (b >= WIPE2 + 1.6 / 4 ? 1 : e2) : 0);
    beams(X, t, b >= WIPE2 && b < 82 ? e2 : 0);
    keyLight(X, t, opt.clawdX || 960);
    if (opt.footWorld) prints(X, t, opt.footWorld);
  }
  function cardFrame(t, cast, opt, c) {
    const W2S = W2Sof(c), b = t2b(t); LEDX.clawd = opt.clawdX || 960; LEDX.at = opt.clawdAt || null; LEDX.cam = c; LEDX.camAt = opt.camAt || null; LEDX.fableX = opt.fableX ?? 1520;
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
    camXform(X, c);
    afterimages(t, c, W2S, opt);                                               // (MV layer: behind her, on the fastest moves)
    camXform(X, c);
    cast(W2S, c);
    X.setTransform(1, 0, 0, 1, 0, 0);
    // the last bar: the lights die on the stage, and the lanterns are what's left
    if (b > 91.9 && b < 94) { X.fillStyle = `rgba(7,4,14,${(.86 * Math.min(1, (b - 91.9) / .9) ** 1.5).toFixed(3)})`; X.fillRect(0, 0, W, H); }
    crowd(X, t, c, e1, e2, e3);
    X.save(); X.globalCompositeOperation = 'screen'; X.fillStyle = 'rgba(60,40,90,.08)'; X.fillRect(0, 0, W, H); X.restore();   // haze
    postFX(t);                                                                 // MV layer: glitch and colour fringe (before the paper)
    // Fable's paper, in the card's screen space: the notes in the bottom margin (what she's writing in her room), the deckle
    // Fable's notes: the page's list (the finale passes its own); the margin grows a line-height when they wrap to a second line
    const N = opt.notes ? (t < opt.notes.clear ? opt.notes : null) : notesA(t);
    if (window.washiBorder) washiBorder(t, { bottom: .078 + (NLH / H) * marginGrow(t, N) });
    drawNotes(t, N, opt.notes && opt.notes.ink);
    return c;
  }
  // three-colour afterimages (MV layer): her silhouette 2, 4 and 6 frames ago in pink, cyan and lemon, behind her, only on the
  // fastest arcs: the page-wipes (63, 65), the "Ikuzo!" pump (58.53) and "watch me walk it!" (80); they replace smear drawings
  const AFTER = [[63, 63.45], [65, 65.45], [58.4, 58.8], [79.9, 80.35]], ECHO = [[6, 'rgba(255,216,74,1)', .16], [4, 'rgba(57,223,255,1)', .28], [2, 'rgba(255,92,168,1)', .4]];
  function afterimages(t, c, W2S, opt) {
    const b = t2b(t); if (!opt.clawdAt || !AFTER.some(([a, z]) => b >= a && b < z)) return;
    const cv = ROOM.echo || (ROOM.echo = Object.assign(document.createElement('canvas'), { width: W, height: H })), g = cv.getContext('2d');
    for (const [fr, col, a] of ECHO) {
      g.setTransform(1, 0, 0, 1, 0, 0); g.globalCompositeOperation = 'source-over'; g.clearRect(0, 0, W, H);
      opt.clawdAt(t - fr / 24, W2S, c, g);
      g.setTransform(1, 0, 0, 1, 0, 0); g.globalCompositeOperation = 'source-in'; g.fillStyle = col; g.fillRect(0, 0, W, H);
      X.save(); X.setTransform(1, 0, 0, 1, 0, 0); X.globalAlpha = a; X.drawImage(cv, 0, 0); X.restore();
    }
  }
  // glitch (strips shifted: Clawd is code) where the stage powers up after the tear and at the breakdown's tape-stop; a colour
  // fringe (R and B apart) decaying on the drop and "Ikuzo!"
  const GLITCH = [[43.22, 3], [90.0, 3]], FRINGE = [[46, 3, 7], [58.53, 3, 5]];
  function postFX(t) {
    const f = Math.floor(t * 24), g0 = GLITCH.find(([bb, n]) => { const d = f - Math.floor((b2t(bb) + KICK) * 24); return d >= 0 && d < n; });
    const fr = FRINGE.map(([bb, n, px]) => { const d = f - Math.floor((b2t(bb) + KICK) * 24); return d >= 0 && d < n ? px * (1 - d / n) : 0; }).find(v => v > 0);
    if (!g0 && !fr) return;
    const buf = ROOM.fx || (ROOM.fx = Object.assign(document.createElement('canvas'), { width: W, height: H })), bg = buf.getContext('2d');
    bg.setTransform(1, 0, 0, 1, 0, 0); bg.globalCompositeOperation = 'copy'; bg.drawImage(X.canvas, 0, 0);
    X.save(); X.setTransform(1, 0, 0, 1, 0, 0);
    if (g0) { let y = 0, k = 0; while (y < H) { const hh = 14 + Math.floor(hash2(f * 7 + k, 3) * 70), dx = (hash2(f * 11 + k, 5) - .5) * (hash2(k, f) > .55 ? 90 : 12);
        X.drawImage(buf, 0, y, W, hh, dx, y, W, hh); y += hh; k++; } }
    if (fr) { for (const [col, dx] of [['rgb(255,0,0)', fr], ['rgb(0,0,255)', -fr]]) {
        const cc = ROOM.fx2 || (ROOM.fx2 = Object.assign(document.createElement('canvas'), { width: W, height: H })), c2 = cc.getContext('2d');
        c2.globalCompositeOperation = 'copy'; c2.drawImage(buf, 0, 0); c2.globalCompositeOperation = 'multiply'; c2.fillStyle = col; c2.fillRect(0, 0, W, H);
        X.globalCompositeOperation = 'screen'; X.globalAlpha = .45; X.drawImage(cc, dx, 0); X.globalAlpha = 1; X.globalCompositeOperation = 'source-over'; } }
    X.restore();
  }
  // the room: the card offscreen, filmed in the butai window by the paper world's stage(), the room's readers, and Fable
  const ROOM = {};
  function roomFrame(t, cast, opt, c) {
    const mk = () => Object.assign(document.createElement('canvas'), { width: W, height: H });
    const card = ROOM.card || (ROOM.card = mk());
    withX(card.getContext('2d'), () => cardFrame(t, cast, opt, c));
    const b = lb(t), cam = c.room || RC.ots, lit = b < 90 ? 1 : Math.max(.2, 1 - (b - 90) / 3);
    const R0 = SCREEN.rect; SCREEN.rect = [0, 15, 1920, 1050];                  // (the window's aspect: 1.828)
    try { stage(t, () => X.drawImage(card, 0, 0), { cam, doors: opt.doors ?? 1, spill: [255, 150, 215].map(v => Math.round(v * lit)) }); } finally { SCREEN.rect = R0; }
    X.setTransform(1, 0, 0, 1, 0, 0);
    if (c.ots) {                                                                 // over her shoulder: the window beyond, out of focus
      const buf = ROOM.buf || (ROOM.buf = mk()), g = buf.getContext('2d'); g.clearRect(0, 0, W, H); g.drawImage(X.canvas, 0, 0);
      X.save(); X.filter = 'blur(3px) brightness(.85)'; X.drawImage(buf, 0, 0); X.restore();
      if (typeof FABLESEAT !== 'undefined') {
        if (c.ots === 'write') FABLESEAT.ots(X, t, [], { flip: true, draw: 'write', spread: 'notes' });
        else if (c.ots === 'turn') FABLESEAT.ots(X, t, CARD_TURNS.map(([bb, n]) => [b2t(bb), n]), { flip: true, initial: 'title' });
        else FABLESEAT.ots(X, t, [], { flip: true, draw: 'ots', spread: 'story' });
      }
      return c;
    }
    // (one audience: the hall's, inside the card; the room's readers are cut in world A)
    const k = cam.zoom * FROOM.m, fx = W / 2 + (FROOM.x - cam.x) * k, fy = H / 2 + (FROOM.y - cam.y) * k, fs = FROOM.s * k;
    if (opt.roomFable) opt.roomFable(X, cam, lit);
    else if (typeof FABLESEAT !== 'undefined') FABLESEAT.draw(X, t, { x: fx, y: fy, s: fs, flip: true }, lit);
    if (opt.roomAfter) opt.roomAfter(X, cam);
    // the tear's flood (61.0, world A's first frame): her light takes the window and washes the room white, covering the move from
    // the paper world's readers to one audience (Fable: "the white covers the move"); it ebbs over two thirds of a second
    const tf = t - 60.99;                                                          // (world A starts at 61.0)
    if (tf >= 0 && tf < .88) { const [wx, wy] = [W / 2 + (1919.5 - cam.x) * cam.zoom, H / 2 + (1303 - cam.y) * cam.zoom], a = tf < .18 ? 1 : .95 * (1 - (tf - .18) / .7) ** 1.6;   // (held white half a beat: Fable, "the audience should lose the picture for a moment")
      X.save(); X.setTransform(1, 0, 0, 1, 0, 0); X.globalCompositeOperation = 'lighter';
      const g = X.createRadialGradient(wx, wy, 200, wx, wy, 1900); g.addColorStop(0, `rgba(255,244,250,${a})`); g.addColorStop(.5, `rgba(255,236,246,${a * .6})`); g.addColorStop(1, `rgba(255,236,246,${a * .25})`);
      X.fillStyle = g; X.fillRect(0, 0, W, H); if (tf < .18) { X.globalCompositeOperation = 'source-over'; X.fillStyle = 'rgb(255,248,252)'; X.fillRect(0, 0, W, H); } X.restore(); }
    return c;
  }
  // her book mirrors the screen: the same faces, and Clawd's page (drawn live) for the over-the-shoulder cut at 80.2
  // (her book: the old telling printed on the left page, Clawd's pixel page facing it on the right; Fable: "letterpress left,
  // her pixels right, facing")
  const FABLE_TEXT = ['The Crab and her Mother.', '', 'A mother crab said to her', 'child, \u201cWhy do you walk', 'sideways? Walk straight.\u201d',
                      'The young crab said,', '\u201cShow me how, and I\u2019ll', 'follow.\u201d The mother tried,', 'and went sideways.'];
  function storySpread(t, w, h) {
    const c = Object.assign(document.createElement('canvas'), { width: w, height: h }), g = c.getContext('2d');
    g.drawImage(pageFace('blank', w, h), 0, 0);
    withX(g, () => {
      const sz = h * .05; let y = h * .16;
      for (const str of FABLE_TEXT) { if (str) { const L = shape(str, { font: 'caslon', size: sz * .92 }); g.fillStyle = 'rgba(34,28,24,.9)'; for (const gl of L.glyphs) if (gl.ch !== ' ') g.fill(glyphPath(gl, w * .05 + gl.x, y + gl.y)); } y += sz * 1.32; }
      storyPage(g, t, [w / 2, 0, w / 2, h], { crab: 2.2 });
    });
    return c;
  }
  // which of Fable's pages the screen is showing (null while it's LED): her book in the room shows the same (Michael)
  function screenPage(t) {
    const b = t2b(t); if (b < WIPE1 + .2 || b >= 82) return null;
    if (b >= WIPE3 + .2) return 'story';
    if (b >= WIPE2 + .2) return cardState(t).cur;
    return 'crabline';                                                        // verse 1's print, brought by wipe 1
  }
  const WIPES = [WIPE1, WIPE2, WIPE3];                                        // (for the sound: src/sfx_clawd.js reads these)
  return { LOW, WIPES, CARD_TURNS, GLITCH, frame, camAt, camFrom, notes, SCR, K, W2Sof, load, pageFace, storySpread, screenPage, OVR, RC, KICK, FROOM, callSpans };
})();
