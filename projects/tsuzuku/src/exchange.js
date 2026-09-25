// exchange.js: the exchange, song 36.0-61.0 (BEATS X2-X8), after the unfold. The book is a card: the shore, the mother and the
// ruler are on it; the teller is not (she doesn't travel) and neither is the visitor (Clawd's puppet, who refuses the ending).
// X3 "...and the mother tried.": straight, here, is toward the lamp: she swells and softens; "And the mother went sideways.":
// she veers back to the screen and scuttles off. "Hm.": cut to Fable's profile, one dry dip. X4 "And that's where the book
// ends.": the fan opens and snaps shut; "Every time.": hiki-nuki, the card pulled half out and held. X5 "So? Sorekara?! And
// then?!": Clawd hops. X6-X7: the card held half out, still; the build: Clawd's eye slits burn, her cellophane glows from
// inside. X8 "Says who?": the card tears at her; stage light floods the rip.
{
  const FLOOR = 962, f = 1 / 12, S0 = 36.0, S1 = 61.0, T = { x: 560, y: 960, s: .2, origin: [1150, 2760] };
  const CX = 1250, CS = .16, beat8 = 60 / 85 / 2;                     // Clawd's puppet where she unfolded; the lute's 6/8 eighths
  const LAP = { forearm: 40, hand: 25, upperarm: 6 }, EYE = { forearm: -12, hand: 8, upperarm: 0 };
  let K = null;
  function keys() {
    const W = window.WORDS || [], w = (n, a = 36, b = 62) => (W.find(x => x.t0 > a && x.t0 < b && x.w.toLowerCase().replace(/[^a-z]/g, '') === n) || {}).t0;
    const k = { tried: w('and', 37.5, 38.5), sideways: w('and', 40, 41), hm: w('hm'), sideways2: w('sideways', 44, 46), that: w('thats', 46, 48), ends: w('ends'),
      every: w('every'), so: w('so', 50, 51.5), sorekara: w('sorekara'), then: w('then', 52.5, 53.5), oh: w('oh'), ending: w('thats', 56.5, 57.5), says: w('says'), who: w('who', 60, 61) };
    k.close = k.hm - f; k.back = w('and', 46.5, 47) - 7 * f;           // the close-up: from just before "Hm." to just before "And that's"
    k.tear = k.says;
    K = k;
    K.fan = PUPPET.morphs([[0, 'fan_closed'], [k.that - 3 * f, 'fan_open'], [k.ends + f, 'fan_closed']], { hold: 1 });
    K.arm = PUPPET.snap([[0, { forearm: 12, hand: -6, upperarm: 0 }], [k.that - 6 * f, EYE], [k.every - 2 * f, { forearm: -4, hand: -22, upperarm: -14 }],   // the fan's tip sweeps the card out
      [k.every + 8 * f, { forearm: 12, hand: -6, upperarm: 0 }], [k.tear, { forearm: 20, hand: 0, upperarm: 8 }]]);
    K.head = PUPPET.snap([[0, { head: 9 }], [k.tried, { head: 5 }], [k.sideways + .3, { head: 3 }], [k.hm, { head: 11 }], [k.hm + 3 * f, { head: 5 }],
      [k.so, { head: 7 }], [k.oh, { head: 3 }], [k.tear + f, { head: -5 }]]);
    K.clawd = PUPPET.snap([[0, { head: 0, upperarm_L: 0, forearm_L: 0, upperarm_R: 0, forearm_R: 0 }], [k.tried, { head: 6 }], [k.sideways + .5, { head: 10 }],
      [k.every, { head: -4 }], [k.so, { head: -6, upperarm_R: -60, forearm_R: -20 }], [k.sorekara, { upperarm_L: 95, forearm_L: 30, upperarm_R: -95, forearm_R: -30, head: -8 }],
      [k.then + .5, { upperarm_L: 0, forearm_L: 0, upperarm_R: 0, forearm_R: 0, head: 4 }], [k.says - 2 * f, { head: -9, upperarm_L: 70, forearm_L: 10, upperarm_R: -70, forearm_R: -10 }]]);
    K.hops = [[k.so, 50], [k.sorekara, 85], [k.then, 60]];
  }
  const fablePose = tt => { const q = Math.floor(tt * 12 + 1e-6) / 12, p = { ...K.arm(q), ...K.head(q), _ghost: {} }; p.hair = -(p.head || 0) * .85; return p; };
  const jawAt = ts => { for (const w of (window.WORDS || [])) if (w.who === 'clawd' && w.t0 > 36 && ts >= w.t0 && ts < w.t1) return (ts - w.t0) / Math.max(.08, w.t1 - w.t0) < .7 ? 9 : 4; return 0; };
  const hopAt = ts => {                                                // Reiniger hops (clawdpaper.js): dip, tucked in the air, dip, stand
    const p = { dy: 0, thigh_L: 0, thigh_R: 0, shin_L: 0, shin_R: 0, 'shin_L.y': 0, 'shin_R.y': 0 };
    for (const [t0, h] of K.hops) { const d = Math.floor((ts - t0) * 12 + 1e-6);
      if (d === 0 || d === 5) { p.dy = 10; p.thigh_L = -5; p.thigh_R = 5; p.shin_L = 8; p.shin_R = -8; }
      else if (d >= 1 && d <= 4) { p.dy = -h * Math.sin(Math.PI * d / 5); p.thigh_L = 4; p.thigh_R = -4; p['shin_L.y'] = -70; p['shin_R.y'] = -70; } }
    return p;
  };
  // the card's pull (px to the right): on "Every time." it's pulled most of the way out in 12 drawings and held there, still,
  // until she tears it. Michael: the reeds must clear Fable and leave Clawd in the open; the clump (~460 px) can't fit in the
  // ~320 px between them, so the card goes until its reeds are past her. (The later tugs read as the scenery creeping.)
  const PULL = 1320;
  function pullAt(ts) {
    if (ts < K.every) return 0;
    const u = Math.min(1, Math.floor((ts - K.every) * 12 + 1e-6) / 12), e = u * u * (3 - 2 * u);
    return PULL * e;
  }
  // the mother, in card coordinates (X3): tried straight (toward the lamp, stiff steps on the eighths); veered sideways, off right
  function mother(ts) {
    let x = 1520, d = 0, y = 0, rock = 0;
    if (ts >= K.tried && ts < K.sideways) { const k = Math.floor((ts - K.tried) / beat8); d = Math.min(.5, k * .075); rock = k % 2 ? 2 : -2; y = -6 * (k % 2); }
    else if (ts >= K.sideways) { const k = Math.floor((ts - K.sideways) / (beat8 / 2)); d = Math.max(0, .5 - k * .14); x = 1520 + Math.max(0, k - 3) * 30; rock = 5 * (k % 2 ? 1 : -1); y = -10 * (k % 2); }
    return { x, d, y, rock };
  }
  let CARD = null;
  // the book's card: everything on it rendered to its own layer (white = no shadow), multiplied onto the screen at its pull
  function card(ts) {
    if (!CARD) CARD = mkCanvas(W, H);
    const g = CARD.getContext('2d'); g.setTransform(1, 0, 0, 1, 0, 0); g.globalCompositeOperation = 'source-over'; g.filter = 'none'; g.globalAlpha = 1; g.fillStyle = '#fff'; g.fillRect(0, 0, W, H);
    const Xs = X; X = g;
    try {
      shore(ts, { floor: FLOOR });
      shadow(c => { c.globalCompositeOperation = 'source-over'; VERSE_LINE(c, ts); }, 0);   // the ruler (the mother is drawn below, moving)
      const m = mother(ts), [lx, ly] = SCREEN.lamp, sp = 1 / (1 - Math.min(m.d, .8) * .5);
      if (m.x < 2000) shadow(c => { c.globalCompositeOperation = 'source-over';
        PUPPET.drawShape(c, PUPPET.shapeAt(FAN, 'crab', 'crab', 1), new DOMMatrix().translate(lx + (m.x - lx) / sp, ly + (FLOOR + m.y - ly) / sp).rotate(m.rock).scale(.364)); }, m.d, { penumbra: true, alpha: 1 - m.d * .6 });
    } finally { X = Xs; }
  }
  // the tear (X8): a ragged line through the card at Clawd; the halves part, drawings apart; the stage light through the gap
  // (in card coordinates: the tear runs through what's left of the card in the window, right beside her)
  let TEAR = null;
  const tearLine = () => {                                           // a slow wander, and on it the fine zigzag of torn fibre
    const pts = [], x0 = 150 + 70; let x = 0, i = 0;
    for (let y = 150; y <= 1090; y += 9, i++) { x += ((y * 7919) % 23 - 11) * .55; x = Math.max(-60, Math.min(60, x)); pts.push([x0 + x + (i % 2 ? 1 : -1) * (1 + (i * 53) % 5) + ((i * 37) % 7 - 3), y]); }   // (an irregular zigzag, not a saw)
    return pts;
  };
  const gapAt = ts => ts < K.tear ? 0 : [0, 14, 40, 90, 170, 280, 420, 600, 820, 1100, 1500][Math.min(10, Math.floor((ts - K.tear) * 12 + 1e-6))];
  function composite(ts) {
    if (!TEAR) TEAR = tearLine();
    const pull = pullAt(ts), gap = gapAt(ts), [sx, sy, sw, sh] = SCREEN.rect;
    const half = (side, dx) => {
      X.save(); X.beginPath();
      if (side < 0) { X.moveTo(0, 0); for (const [x, y] of TEAR) X.lineTo(x + pull + dx, y); X.lineTo(0, 1100); }
      else { X.moveTo(W + 2000, 0); for (const [x, y] of TEAR) X.lineTo(x + pull + dx, y); X.lineTo(W + 2000, 1100); }
      X.closePath(); X.clip();
      X.beginPath(); X.rect(Math.max(sx, sx + pull + dx), sy, sw, sh); X.clip();              // the card's own extent (its left edge travels)
      X.globalCompositeOperation = 'multiply'; X.drawImage(CARD, pull + dx, 0);
      X.globalCompositeOperation = 'source-over'; X.fillStyle = 'rgba(22,22,26,.06)'; X.fillRect(sx + pull + dx, sy, sw, sh);   // its tissue
      X.restore();
    };
    if (gap === 0) { half(-1, 0); half(1, 0); } else { half(-1, -gap / 2); half(1, gap / 2); }
    if (pull > 0) {                                                    // the card's leading edge and its shadow on the bare vellum
      const ex = sx + pull; X.save(); X.fillStyle = 'rgba(40,30,24,.5)'; X.fillRect(ex - 2, sy, 2, sh);
      const gr = X.createLinearGradient(ex - 26, 0, ex, 0); gr.addColorStop(0, 'rgba(0,0,0,0)'); gr.addColorStop(1, 'rgba(0,0,0,.16)'); X.fillStyle = gr; X.fillRect(ex - 26, sy, 26, sh); X.restore();
    }
    if (gap > 0) {
      const gapPath = () => { X.beginPath(); for (const [x, y] of TEAR) X.lineTo(x + pull - gap / 2, y); for (const [x, y] of [...TEAR].reverse()) X.lineTo(x + pull + gap / 2, y); X.closePath(); };
      // her light through the rip, as hot and soft as it likes: the core fills the gap exactly; the bloom spills, fainter
      X.save(); X.globalCompositeOperation = 'lighter';
      gapPath(); X.filter = `blur(${24 + gap * .08}px)`; X.fillStyle = 'rgba(255,120,190,.3)'; X.fill();
      X.filter = `blur(${44 + gap * .1}px)`; X.fillStyle = 'rgba(90,220,255,.22)'; X.fill();
      X.filter = 'none'; gapPath(); X.fillStyle = 'rgba(255,240,248,.95)'; X.fill(); X.restore();
      // the card's torn edges: crisp and ragged, a hairline of white fibre along each, a shadow on the card side (Fable)
      for (const side of [-1, 1]) {
        const ex = pull + side * gap / 2;
        X.save(); X.beginPath(); TEAR.forEach(([x, y], i) => i ? X.lineTo(x + ex - side * 5, y) : X.moveTo(x + ex - side * 5, y));
        X.globalCompositeOperation = 'multiply'; X.strokeStyle = 'rgba(60,44,34,.55)'; X.lineWidth = 8; X.filter = 'blur(2px)'; X.stroke(); X.restore();
        X.save(); X.globalCompositeOperation = 'lighter'; X.strokeStyle = 'rgba(255,250,240,.95)'; X.lineWidth = 1.6;
        X.beginPath(); TEAR.forEach(([x, y], i) => i ? X.lineTo(x + ex, y) : X.moveTo(x + ex, y)); X.stroke();
        X.lineWidth = 1; X.beginPath();                                  // fibres standing off the tear
        TEAR.forEach(([x, y], i) => { if (i % 2) return; for (let k = 0; k < 2; k++) { const r = ((i * 31 + k * 17) % 13) / 13, yy = y + k * 8, L = 3 + r * 7; X.moveTo(x + ex, yy); X.lineTo(x + ex + side * L, yy + (r - .5) * 6); } });
        X.stroke(); X.restore();
      }
    }
  }
  function flood(ts, rect) {                                           // the stage light fills the paper world (it washes paper and ink out; the black and the gels survive)
    const gap = gapAt(ts), [sx, sy, sw, sh] = rect || SCREEN.rect;
    if (gap > 400) { X.save(); X.globalCompositeOperation = 'lighter'; X.fillStyle = `rgba(255,240,248,${Math.min(1, (gap - 400) / 1100)})`; X.fillRect(sx, sy, sw, sh); X.restore(); }
  }
  function scene(ts) {
    X.fillStyle = '#0d0b0a'; X.fillRect(0, 0, W, H);
    screen(ts, { stops: FABLE_LAMP, tex: .32 });
    pageVellum(ts);                                                    // the margin ink is on the vellum, under everything that comes off it
    card(ts); composite(ts); flood(ts);
    // the teller and the visitor, off the card; the stage floor under them
    const pf = fablePose(ts), hop = hopAt(ts), build = Math.min(1, Math.max(0, (ts - 56.5) / (K.tear - 56.5)));
    const pc = { ...K.clawd(Math.floor(ts * 12 + 1e-6) / 12), ...hop, jaw: jawAt(ts), _ghost: {} };
    shadow(c => {
      c.globalCompositeOperation = 'source-over'; c.fillStyle = 'rgb(22,22,26)'; c.fillRect(150, FLOOR, 1620, 12);
      seatedRibbon(c, fablePose, T, ts);
      FABLE.draw(c, pf, T, { props: [fanProp(K.fan, ts)], rods: FABLE_RODS });
      CLAWDP.draw(c, pc, { x: CX, y: FLOOR + hop.dy, s: CS, origin: [1076, 2800] }, { gel: CLAWD_GEL, misreg: [1.5, 1],
        rods: [{ part: 'torso', at: [1076, 1200], w: 5 }, { part: 'claw_R', at: [1640, 1600], w: 2.5, lean: 30 }] });
    }, 0);
    if (build > 0) {                                                   // X7: her eye slits burn; her cellophane lights from inside, not from the lamp
      const M = CLAWDP.world(pc, { x: CX, y: FLOOR + hop.dy, s: CS, origin: [1076, 2800] }), eye = [[956, 704], [1187, 713]].map(([a, b]) => M.head.transformPoint(new DOMPoint(a, b)));
      X.save(); X.globalCompositeOperation = 'lighter';
      for (const e of eye) { const r = 10 + 26 * build, gr = X.createRadialGradient(e.x, e.y, 0, e.x, e.y, r); gr.addColorStop(0, `rgba(255,236,200,${.9 * build})`); gr.addColorStop(1, 'rgba(255,160,90,0)'); X.fillStyle = gr; X.fillRect(e.x - r, e.y - r, 2 * r, 2 * r); }
      const b0 = M.torso.transformPoint(new DOMPoint(1076, 1200)), R = 150 + 60 * build, gb = X.createRadialGradient(b0.x, b0.y, 0, b0.x, b0.y, R);
      gb.addColorStop(0, `rgba(255,150,70,${.32 * build})`); gb.addColorStop(1, 'rgba(255,120,50,0)'); X.fillStyle = gb; X.fillRect(b0.x - R, b0.y - R, 2 * R, 2 * R); X.restore();
    }
    X.save(); X.globalCompositeOperation = 'overlay'; X.globalAlpha = .16; X.fillStyle = X.createPattern(GRAIN[Math.floor(ts * 12) % 4], 'repeat'); X.fillRect(0, 0, W, H); X.restore();
  }
  // the camera: the window; "Hm." cuts to her profile (the camera close to the frame, the paper grain large)
  const CAM_HM = { x: 1672, y: 1303, zoom: 2.4 };                    // her profile at the left of the frame, looking into the space; the margin notes out of it
  LOOPS.exchange = t => {
    if (!K) keys();
    const ts = S0 + Math.floor(t * 12 + 1e-6) / 12, close = ts >= K.close && ts < K.back;
    const g = gapAt(ts), wash = g > 400 ? Math.min(1, (g - 400) / 1100) : 0;   // the strip washes out with everything else (Fable)
    stage(ts, scene, { cam: close ? CAM_HM : CAM_WINDOW, doors: 1, page: ts, pageWash: wash });
    if (!close) readers(ts, CAM_WINDOW);
  };
  LOOPS.exchange.len = S1 - S0;
}
