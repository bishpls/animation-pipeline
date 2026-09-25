// bridge.js: the bridge's paper half, song 131.0-156.2 (BEATS B1-B4; Fable's rulings). The hyoshigi stops the story and the
// lamp's sway with it. Fable alone on her zabuton, the fan in her lap; Clawd's puppet set down at the edge, rod leaning, never
// struck. "I've read them all": the fan becomes the fox, the crow, the boy who cried, the wings and the falling figure, each
// landing on its word. "I know the moral before the page": she puts each shape back into the fan; "That's the job": it folds.
// Meanwhile the scenery is struck plane by plane, far to near, one per line, each a card pulled sideways; every plane gone lets
// more light through, so the vellum ends bare and hot, the brightest it has been. "You stand in the dark": the camera pulls
// back past the butai's wood. B5 (the ink close-up, LOOPS.inkcloseup) follows at 156.2.
{
  const S0 = 131.0, CLACK = 131.29, FLOOR = 962, f = 1 / 12;
  const w = n => ((window.WORDS || []).find(x => x.t0 > 131 && x.t0 < 157 && x.w.toLowerCase().startsWith(n)) || {}).t0;   // a word's onset
  // the strikes, one per line of the monologue, in the breath after it: [key, start, direction]
  const STRIKES = [['far', 134.9, 1], ['rocksL', 148.85, -1], ['rocksR', 148.85, 1], ['pine', 150.92, 1], ['ground', 154.25, 1]];
  const PULLU = [.015, .06, .16, .32, .55, .82, 1];                    // a tug, then the slide, accelerating (drawings)
  const pulled = (ts, t0) => ts < t0 ? 0 : PULLU[Math.min(PULLU.length - 1, Math.floor((ts - t0) * 12 + 1e-6))];
  const HOT = [[0, '#FFF7E6'], [.3, '#FDE6B8'], [.7, '#EDB878'], [1, '#93643A']];
  const mixHex = (a, b, u) => '#' + [1, 3, 5].map(i => Math.round(parseInt(a.substr(i, 2), 16) * (1 - u) + parseInt(b.substr(i, 2), 16) * u).toString(16).padStart(2, '0')).join('');
  // the fan: morphs land ON their words (a morph is three held cards, finishing 4 drawings after its key)
  const land = t => t - 4 * f;
  let GAL = null, REW = null;
  const build = () => {
    const fox = w('fox'), crow = w('crow'), boy = w('boy'), flew = w('flew'), sun = w('sun'), all = w('all'), job = w('job'), page = w('page');
    GAL = PUPPET.morphs([[0, 'fan_closed'], [land(all), 'fan_open'], [land(fox), 'fox'], [land(crow), 'crow'], [land(boy), 'boy'], [land(flew), 'wings'], [land(sun), 'falling']]);
    // put back, one card each (hold 1), from the falling figure to the open fan by "page", then folded on "job"
    const r0 = w('moral') - 2 * f;
    REW = PUPPET.morphs([[0, 'falling'], [r0, 'wings'], [r0 + 3 * f, 'boy'], [r0 + 6 * f, 'crow'], [r0 + 9 * f, 'fox'], [land(page) + 1 * f, 'fan_open'], [land(job), 'fan_closed']], { hold: 1 });
    return { fox, crow, boy, flew, sun, all, moral: w('moral'), job, stand: w('stand') };
  };
  let WT = null;
  const seq = tt => tt < WT.moral - 2 * f ? GAL(tt) : REW(tt);
  const LAP = { forearm: 40, hand: 25, upperarm: 6 }, EYE = { forearm: -12, hand: 8, upperarm: 0 };
  let arm = null, head = null;
  const poses = () => {
    const L = 5 * f;                                                    // the arm arrives a little before its noun
    arm = PUPPET.snap([[0, LAP], [WT.all - 8 * f, EYE],
      [WT.fox - L - 4 * f, { forearm: 34, hand: -12, upperarm: 14 }],   // the fox at lap height, looking up
      [WT.crow - L - 4 * f, { upperarm: -50, forearm: 62, hand: -25 }],  // the crow held up and out
      [WT.boy - L - 4 * f, { forearm: 8, hand: -2, upperarm: 3 }],
      [WT.flew - L - 4 * f, { upperarm: -60, forearm: 30, hand: -5 }],   // the wings high
      [land(WT.sun), { upperarm: -65, forearm: 90, hand: 0 }],          // he pitches over; her hand drops forward into the catch: he hangs by the ankles, clear of her sleeve
      [WT.moral - 6 * f, { forearm: 14, hand: -6, upperarm: 6 }],       // brought in to chest height to be put away (the open fan clear of her face)
      [WT.job + 6 * f, LAP]]);                                          // folded, back in her lap
    head = PUPPET.snap([[0, { head: 7 }], [WT.all - 7 * f, { head: 0 }], [WT.fox - L - 3 * f, { head: 8 }], [WT.crow - L - 3 * f, { head: -4 }],
      [WT.boy - L - 3 * f, { head: 2 }], [WT.flew - L - 3 * f, { head: -7 }], [land(WT.sun) + f, { head: 9 }], [WT.moral - 5 * f, { head: 2 }],
      [WT.job + 7 * f, { head: 7 }], [WT.stand, { head: 4 }]]);
  };
  const BLINKS = [133.4, 142.6, 146.3, 151.7, 155.2];
  const poseAt = tt => { const q = Math.floor(tt * 12 + 1e-6) / 12, p = { ...arm(q), ...head(q), _ghost: {} }; p.hair = -(p.head || 0) * .85; return p; };
  const T = { x: 560, y: 960, s: .2, origin: [1150, 2760] };
  // Clawd's puppet, set down at the edge: leaning, head down, rod leaning, the eye slits still lit
  const CP = { x: 1640, y: FLOOR, s: .16, origin: [1076, 2800] }, CPOSE = { skirt: 11, head: 15, upperarm_L: -41, forearm_L: -6, upperarm_R: 18, forearm_R: 6, _ghost: {} };   // arms hanging plumb (the lean undone)
  // on the clack the story stops, and so does she: her rod lifts her out of the story's place, carries her to the edge, sets
  // her down; she goes limp against the frame (whole, inside the window: put away, not lost)
  const LIMP = { skirt: 11, head: 15, upperarm_L: -41, forearm_L: -6, upperarm_R: 18, forearm_R: 6 };
  const setDown = PUPPET.snap([[0, { x: 1400, y: 0, skirt: 0, head: 0, upperarm_L: 0, forearm_L: 0, upperarm_R: 0, forearm_R: 0 }],
    [CLACK + f, { x: 1520, y: -36 }], [CLACK + 4 * f, { x: CP.x, y: 0 }], [CLACK + 6 * f, LIMP]], { overshoot: .08 });
  const clawdAt = ts => { const k = setDown(ts); return { pose: { ...k, _ghost: {} }, T: { ...CP, x: k.x, y: FLOOR + k.y }, lean: ts >= CLACK + 5 * f ? -70 : 0 }; };
  function scene(ts) {
    const strike = {}; let bright = 0;
    for (const [k, t0, dir] of STRIKES) { const u = pulled(ts, t0); strike[k] = [u, dir]; bright += u * (k.startsWith('rocks') ? .5 : 1); }
    const b = bright / 4, stops = HOT.map(([k, c], i) => [k, mixHex(FABLE_LAMP[i][1], c, b)]);
    X.fillStyle = '#0d0b0a'; X.fillRect(0, 0, W, H);
    screen(ts, { stops, tex: .32 - .08 * b, power: 1 + .12 * b });
    shore(ts, { floor: FLOOR, still: CLACK, strike });
    const p = poseAt(ts);
    const blink = BLINKS.some(b0 => ts >= b0 && ts < b0 + 2 * f);
    shadow(c => {
      seatedRibbon(c, poseAt, T, ts);
      c.globalCompositeOperation = 'source-over';
      if (strike.ground[0] > 0) { c.fillStyle = 'rgb(22,22,26)'; c.fillRect(150, FLOOR, 1620, 10); }   // the plain rail the beach lay on
      const cl = clawdAt(ts);
      CLAWDP.draw(c, cl.pose, cl.T, { gel: CLAWD_GEL, misreg: [1.5, 1], rods: [{ part: 'torso', at: [1076, 1200], w: 5, lean: cl.lean }, { part: 'claw_R', at: [1640, 1600], w: 2.5, lean: cl.lean ? 26 : 0 }] });
      FABLE.draw(c, p, T, { props: [fanProp(seq, ts)], cover: blink ? { head: [[1496, 491]] } : {}, rods: FABLE_RODS });
    }, 0);
    pageVellum(ts); pageStrip(ts);                                    // the page (Fable)
    X.save(); X.globalCompositeOperation = 'overlay'; X.globalAlpha = .16; X.fillStyle = X.createPattern(GRAIN[Math.floor(ts * 12) % 4], 'repeat'); X.fillRect(0, 0, W, H); X.restore();
  }
  // B4: "You stand in the dark," the camera pulls back past the wood, in drawings, and holds
  const BACK = 152.46, BACKN = 12;
  LOOPS.bridge = t => {
    if (!WT) { WT = build(); poses(); }
    const ts = S0 + Math.floor(t * 12 + 1e-6) / 12;
    const e = ts < BACK ? 0 : Math.min(1, Math.floor((ts - BACK) * 12 + 1e-6) / BACKN), ee = e * e * (3 - 2 * e);
    stage(ts, scene, { cam: camLerp(CAM_WINDOW, CAM_WIDE, ee), doors: 1 });
    audience(ts, { y: H + 330 - 210 * ee, lift: 120, scale: .52 * (1 - .35 * ee) });
  };
  LOOPS.bridge.len = 156.2 - S0;

  // ---- after the close-up: the bare hot vellum, nothing left of the shore but the rail -----------------------------------
  function bare(ts, draw) {
    X.fillStyle = '#0d0b0a'; X.fillRect(0, 0, W, H);
    screen(ts, { stops: HOT, tex: .24, power: 1.12 });
    shadow(c => {
      c.globalCompositeOperation = 'source-over'; c.fillStyle = 'rgb(22,22,26)'; c.fillRect(150, FLOOR, 1620, 10);
      CLAWDP.draw(c, CPOSE, CP, { gel: CLAWD_GEL, misreg: [1.5, 1], rods: [{ part: 'torso', at: [1076, 1200], w: 5, lean: -70 }, { part: 'claw_R', at: [1640, 1600], w: 2.5, lean: 26 }] });
      draw(c);
    }, 0);
    pageVellum(ts); pageStrip(ts);                                    // the page (Fable)
    X.save(); X.globalCompositeOperation = 'overlay'; X.globalAlpha = .16; X.fillStyle = X.createPattern(GRAIN[Math.floor(ts * 12) % 4], 'repeat'); X.fillRect(0, 0, W, H); X.restore();
  }
  // B6 (159.53-161.0), the held note, "So I'm putting down the book": the fan opens and becomes the book, and she holds it in
  // her lap, as B7 (the ink standing-up) finds her: seated with the book, still
  {
    const S0 = 159.53, CHEST = { forearm: 14, hand: -6, upperarm: 6 };
    const fan = PUPPET.morphs([[0, 'fan_closed'], [S0 + 1 * f, 'fan_open'], [land(160.46), 'book']]);
    const arm6 = PUPPET.snap([[0, LAP], [S0 + 1 * f, CHEST], [160.55, LAP]]), head6 = PUPPET.snap([[0, { head: 7 }], [S0 + 2 * f, { head: 3 }], [160.6, { head: 8 }]]);
    const pose6 = tt => { const q = Math.floor(tt * 12 + 1e-6) / 12, p = { ...arm6(q), ...head6(q), _ghost: {} }; p.hair = -p.head * .85; return p; };
    LOOPS.bridgeB6 = t => {
      const ts = S0 + Math.floor(t * 12 + 1e-6) / 12;
      stage(ts, tt => bare(tt, c => { seatedRibbon(c, pose6, T, tt); FABLE.draw(c, pose6(tt), T, { props: [fanProp(fan, tt)], rods: FABLE_RODS }); }), { cam: CAM_WINDOW, doors: 1 });
      audience(ts, { y: H + 330, lift: 120 });
    };
    LOOPS.bridgeB6.len = 161.0 - S0;
  }
  // B8-B9 (166.0 to the build, 176.47). She stands beside her zabuton (not on it, in geta), the book open face-up on the rail
  // behind her heels. The held note ends as the camera pulls back to the wood: a frame to step through. Her near hand half-rises
  // toward the book as if to take it back, stops, drops. "Mukashi mukashi was a long time ago. This is now.": seven slow steps
  // to the frame's edge beside Clawd's puppet, feet together on "now"; she looks down at her. "Sorekara?": four quicker steps,
  // off the screen toward the lamp as she goes (her shadow greys and softens), passing behind Clawd's cellophane (her
  // silhouette seen through the orange, the only colour on her in the paper world), out through the frame, the ribbon last.
  {
    const S0 = 166.0, S1 = 176.47, B = 60 / 170 * 4, BEAT = B / 2, NOTE = 159.53, beat = k => NOTE + k * BEAT;
    const X0 = 960, BOOKX = 800, TS = { x: X0, y: FLOOR, s: .2, origin: [1100, 3700] };   // (.2: her head clears the window's top)
    const b0 = Math.ceil((168.62 - NOTE) / BEAT), steps = [];
    for (let i = 0; i < 7; i++) steps.push({ t: beat(b0 + i), foot: i % 2 ? 'h' : 'v', close: i === 6, S: 82 });
    const b1 = Math.round((175.06 - NOTE) / BEAT), OUT = beat(b1);
    for (let i = 0; i < 4; i++) steps.push({ t: OUT + i * BEAT / 2, dur: BEAT / 2, foot: i % 2 ? 'h' : 'v', S: 110 });
    const walk = makeWalk(steps, 82, BEAT, TS.s);
    // the one gesture: toward the book behind her (the arm back, the hand low), held, dropped; then the first step
    const reach = PUPPET.snap([[0, { upperarm: 0, forearm: 0, hand: 0, head: -3 }], [167.25, { upperarm: 24, forearm: 10, hand: 12, head: 8 }],
      [168.05, { upperarm: 0, forearm: 0, hand: 0, head: 0 }]]);
    const look = PUPPET.snap([[0, { head: 0 }], [steps[6].t + BEAT, { head: 14 }], [OUT - 1 / 12, { head: 0 }]]);
    const poseS = tt => { const q = Math.floor(tt * 12 + 1e-6) / 12, w = walk(q), r = reach(q), p = { ...w, _ghost: {} };
      p.upperarm = (w.upperarm || 0) + r.upperarm; p.forearm = r.forearm; p.hand = r.hand; p.head = q < 168.5 ? r.head : look(q).head;
      p.hair = -(p.head + (p.torso || 0)) * .85; return p; };
    const TAILS_S = [{ len: 2500, w: 118, rest: [97, 100, 104, 107, 108, 105, 100] }, { len: 2150, w: 104, rest: [100, 104, 108, 111, 110, 104, 99] }];
    const HIDE_SEATED = ['lower', 'torso', 'head', 'hair', 'upperarm', 'forearm', 'hand'];
    const BACK2 = 166.0, BACK2N = 20;                                 // the pull-back to the wood, in drawings, as the held note ends
    const depthAt = q => q < OUT ? 0 : Math.min(.16, .04 * Math.floor((q - OUT) * 12 + 1e-6));   // off the screen, a drawing at a time
    function scene(tt) {
      X.fillStyle = '#0d0b0a'; X.fillRect(0, 0, W, H);
      screen(tt, { stops: HOT, tex: .24, power: 1.12 });
      shadow(c => {                                                  // the screen plane: the rail, what she left, Clawd's puppet
        c.globalCompositeOperation = 'source-over'; c.fillStyle = 'rgb(22,22,26)'; c.fillRect(150, FLOOR, 1620, 10);
        FABLE.draw(c, { _ghost: {} }, T, { hide: HIDE_SEATED });
        PUPPET.drawShape(c, PUPPET.shapeAt(FAN, 'book', 'book', 1), new DOMMatrix().translate(BOOKX, FLOOR).scale(.15));
        CLAWDP.draw(c, CPOSE, CP, { gel: CLAWD_GEL, misreg: [1.5, 1], rods: [{ part: 'torso', at: [1076, 1200], w: 5, lean: -70 }, { part: 'claw_R', at: [1640, 1600], w: 2.5, lean: 26 }] });
      }, 0);
      // her own plane: held nearer the lamp as she leaves, placed so her shadow's feet stay on the rail
      const d = depthAt(tt), [lx, ly] = SCREEN.lamp, sp = 1 / (1 - d * .5), p = poseS(tt);
      const T2 = { ...TS, x: lx + (TS.x + p.dx - lx) / sp - p.dx, y: ly + (FLOOR - ly) / sp };
      shadow(c => {
        TAILS_S.forEach((tl, i) => {
          const pts = PUPPET.stiff(FABLE_S, poseS, T2, { part: 'head', at: [900, 820], rest: tl.rest, len: tl.len, drag: .1 }, tt);
          c.setTransform(1, 0, 0, 1, 0, 0); c.globalCompositeOperation = i ? 'multiply' : 'source-over';
          c.fillStyle = FABLE_GEL; c.fill(P(PUPPET.strip(pts, tl.w * T2.s, .85, tl.w * .9 * T2.s)));
        });
        c.globalCompositeOperation = 'source-over';
        drawStanding(c, p, T2, { rods: [{ part: 'torso', at: [1060, 1700], w: 7 }] });
      }, d, { penumbra: true, alpha: 1 - d * 1.1 });
      pageVellum(tt); pageStrip(tt);
      X.save(); X.globalCompositeOperation = 'overlay'; X.globalAlpha = .16; X.fillStyle = X.createPattern(GRAIN[Math.floor(tt * 12) % 4], 'repeat'); X.fillRect(0, 0, W, H); X.restore();
    }
    LOOPS.bridgeB8 = t => {
      const ts = S0 + Math.floor(t * 12 + 1e-6) / 12;
      const e = Math.min(1, Math.floor((ts - BACK2) * 12 + 1e-6) / BACK2N), ee = e * e * (3 - 2 * e);
      stage(ts, scene, { cam: camLerp(CAM_WINDOW, CAM_WIDE, ee), doors: 1 });
      audience(ts, { y: H + 330 - 210 * ee, lift: 120, scale: .52 * (1 - .35 * ee) });
    };
    LOOPS.bridgeB8.len = S1 - S0;
  }
}
