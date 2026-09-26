// bridge.js: the bridge's paper half, song 131.29-156.2 (BEATS B1-B4; Fable's rulings). The hyoshigi stops the story and the
// lamp's sway with it; the lamp itself comes down out of the sky into her lap ("one lantern; it's the lamp": the hall's match
// cut lands here, same seiza, lantern at the same knee). Fable alone on her zabuton, the fan in her lap; Clawd's puppet set down at the edge, rod leaning, never
// struck. "I've read them all": the fan becomes the fox, the crow, the boy who cried, the wings and the falling figure, each
// landing on its word. "I know the moral before the page": she puts each shape back into the fan; "That's the job": it folds.
// Meanwhile the scenery is struck plane by plane, far to near, one per line, each a card pulled sideways; every plane gone lets
// more light through, so the vellum ends bare and hot, the brightest it has been. "You stand in the dark": the camera pulls
// back past the butai's wood. B5 (the ink close-up, LOOPS.inkcloseup) follows at 156.2.
{
  const CLACK = 131.29, S0 = CLACK, FLOOR = 962, f = 1 / 12;
  const w = n => ((window.WORDS || []).find(x => x.t0 > 131 && x.t0 < 157 && x.w.toLowerCase().startsWith(n)) || {}).t0;   // a word's onset
  // the strikes, one per line of the monologue, in the breath after it, on its last four lines (Michael: keep the shore in shot
  // through the gallery, then strike it in close succession toward the end): [key, start, direction]
  const STRIKES = [['far', 148.85, 1], ['rocksL', 150.92, -1], ['rocksR', 150.92, 1], ['pine', 154.25, 1], ['ground', 155.62, 1]];
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
    return { fox, crow, boy, flew, sun, all, moral: w('moral'), job, stand: w('stand'), dark: w('dark') };
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
  // the lamp (Fable: "one lantern; it's the lamp"): on the clack it comes out of the sky into her lap, at her right knee (the
  // camera side); on "You stand" she sets it down in front of her knees, at the cushion's right front edge. It lights the
  // vellum from where it is: a pool, dimmer than the sky lamp; the flats' shadows fall from it, longer, upward.
  // (Michael: not on her lap, where it sat in the fan's space all through the gallery; on the floor beside her, image-left,
  // behind her back, out of the story's two-thirds. Seated, she can't reach the floor, so it stays there until she stands.)
  const FLOORSPOT = [400, FLOOR], LSC = 1.4, LEAN = 25;
  const lanternAt = ts => ({ x: FLOORSPOT[0], y: FLOORSPOT[1], held: false });
  const lampOf = L => [L.x, L.y - (7 + CHO.h / 2) * LSC];
  const bailAt = L => [L.x, L.y - 7 * LSC - CHO.h * LSC - 5 * LSC - CHO.w * .2 * LSC], grip = L => { const b = bailAt(L); return [b[0], b[1] - 14 * LSC]; };
  // the vellum lit from the lamp where it is: a pool, dimmer than the sky lamp was, that opens as the planes go
  const POOL = [[0, '#FFF1D6'], [.22, '#F2CB8E'], [.55, '#B98A52'], [1, '#5A3C22']];   // (a lamp's falloff: no rim)
  // her monologue as margin notes (Fable: "what's left on the bare vellum before the close-up is what I know"): Caslon italic,
  // the lighter ink, each word pressed as she says it; lines as she breathes them. Still there after the close-up (B6).
  const NOTE_LINES = [6, 8, 4, 8, 7, 3, 5, 3];                       // words per line (the gallery split after "crow," and "cried,"; 44 words)
  let NOTES = null;
  function bridgeNotes(ts) {
    if (!NOTES) { const ws = (window.WORDS || []).filter(w => w.who === 'fable' && w.t0 > 131.5 && w.t0 < 156); if (ws.length < 44) return;
      NOTES = []; let k = 0, y = 232;
      for (const n of NOTE_LINES) { let x = 176; for (const w of ws.slice(k, k + n)) { NOTES.push({ w: w.w, t0: w.t0, x, y }); x += shape(w.w + ' ', { font: 'caslonI', size: 27 }).width; } k += n; y += 34; } }
    for (const n of NOTES) inkVellum(n.w, n.x, n.y, ts, n.t0, { size: 27 });
  }
  const poseAt = tt => { const q = Math.floor(tt * 12 + 1e-6) / 12, p = { ...arm(q), ...head(q), _ghost: {} };
    p.hair = -(p.head || 0) * .85; return p; };
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
    const b = bright / 4, stops = HOT.map(([k, c], i) => [k, mixHex(POOL[i][1], c, b)]), L = lanternAt(ts), lamp = lampOf(L);
    X.fillStyle = '#0d0b0a'; X.fillRect(0, 0, W, H);
    screen(ts, { stops, tex: .32 - .08 * b, power: 1.05 + .3 * b, lamp });
    shore(ts, { floor: FLOOR, still: CLACK, strike, lamp });
    const p = poseAt(ts);
    const blink = BLINKS.some(b0 => ts >= b0 && ts < b0 + 2 * f);
    // "You stand in the dark,": her head turns back to the lamp behind her, snapped (the head card flipped about her neck), and
    // holds through "and you know." (Fable: "I look at the light I'm about to leave.")
    const back = WT.dark && ts >= WT.dark, NECK = [1248, 823];
    let Tb = null; if (back) { const nx = FABLE.world(p, T).torso.transformPoint(new DOMPoint(...NECK)).x, Tf = { ...T, flip: -1 };
      const fx = FABLE.world(p, Tf).torso.transformPoint(new DOMPoint(...NECK)).x; Tb = { ...Tf, x: T.x + nx - fx }; }
    shadow(c => {
      seatedRibbon(c, poseAt, T, ts);
      c.globalCompositeOperation = 'source-over';
      if (strike.ground[0] > 0) { c.fillStyle = 'rgb(22,22,26)'; c.fillRect(150, FLOOR, 1620, 10); }   // the plain rail the beach lay on
      const cl = clawdAt(ts);
      CLAWDP.draw(c, cl.pose, cl.T, { gel: CLAWD_GEL, misreg: [1.5, 1], rods: [{ part: 'torso', at: [1076, 1200], w: 5, lean: cl.lean }, { part: 'claw_R', at: [1640, 1600], w: 2.5, lean: cl.lean ? 26 : 0 }] });
      FABLE.draw(c, p, T, { props: [fanProp(seq, ts)], cover: blink && !back ? { head: [[1496, 491]] } : {}, rods: FABLE_RODS, hide: back ? ['head', 'hair'] : [] });
      if (back) FABLE.draw(c, { ...p, head: 10, hair: -8.5 }, Tb, { hide: ['cushion', 'lower', 'torso', 'upperarm', 'forearm', 'hand'] });   // her head, turned back and down to it
    }, 0);
    chochin(L.x, L.y, LSC, { gold: true });                           // the brightest thing in the window
    pageVellum(ts); bridgeNotes(ts);                                  // (the strip: stage())
    X.save(); X.globalCompositeOperation = 'overlay'; X.globalAlpha = .16; X.fillStyle = X.createPattern(GRAIN[Math.floor(ts * 12) % 4], 'repeat'); X.fillRect(0, 0, W, H); X.restore();
  }
  // B1 opens on the hall's last frame, matched (the stage session's numbers at 131.29: crown (900, 108), seat (866, 947)): the
  // camera close on her, the grain large; it holds while Clawd's puppet is set down, then eases out to the telling camera
  const CAM_MATCH = { x: 1486, y: 1334, zoom: 1.742 }, MATCH_HOLD = CLACK + 8 * f, MATCH_N = 20;
  // B4: "You stand in the dark," the camera pulls back past the wood, in drawings, and holds
  const BACK = 152.46, BACKN = 12;
  LOOPS.bridge = t => {
    if (!WT) { WT = build(); poses(); }
    const ts = S0 + Math.floor(t * 12 + 1e-6) / 12;
    const e = ts < BACK ? 0 : Math.min(1, Math.floor((ts - BACK) * 12 + 1e-6) / BACKN), ee = e * e * (3 - 2 * e);
    const m = Math.min(1, Math.max(0, Math.floor((ts - MATCH_HOLD) * 12 + 1e-6) / MATCH_N)), mm = m * m * (3 - 2 * m);
    const cam = ts < BACK ? camLerp(CAM_MATCH, CAM_WINDOW, mm) : camLerp(CAM_WINDOW, CAM_WIDE, ee); stage(ts, scene, { cam, doors: 1, page: ts });
    readers(ts, cam);
  };
  LOOPS.bridge.len = 156.2 - S0;

  // ---- after the close-up: the bare hot vellum, nothing left of the shore but the rail -----------------------------------
  const FLOOR_L = { x: FLOORSPOT[0], y: FLOORSPOT[1], held: false };
  function bare(ts, draw) {
    X.fillStyle = '#0d0b0a'; X.fillRect(0, 0, W, H);
    screen(ts, { stops: HOT, tex: .24, power: 1.02, lamp: lampOf(FLOOR_L) });
    shadow(c => {
      c.globalCompositeOperation = 'source-over'; c.fillStyle = 'rgb(22,22,26)'; c.fillRect(150, FLOOR, 1620, 10);
      CLAWDP.draw(c, CPOSE, CP, { gel: CLAWD_GEL, misreg: [1.5, 1], rods: [{ part: 'torso', at: [1076, 1200], w: 5, lean: -70 }, { part: 'claw_R', at: [1640, 1600], w: 2.5, lean: 26 }] });
      draw(c);
    }, 0);
    chochin(FLOOR_L.x, FLOOR_L.y, LSC, { gold: true });
    pageVellum(ts); bridgeNotes(ts);                                  // (the strip: stage())
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
      readers(ts, CAM_WINDOW);
    };
    LOOPS.bridgeB6.len = 161.0 - S0;
  }
  // B8-B9 (166.0-177.8). She stands where she stood up, facing what she set down: the book, and the lamp on the floor beside it
  // (Fable). She bows; her hand goes to the book and hovers one beat over it (the not-knowing), then takes the lamp by its stick
  // instead (the decision). She straightens, turns, and "Mukashi mukashi was a long time ago. This is now." walks seven steps to
  // the frame's edge with the light hanging from her hand; the pool travels with her. At the stop she sets it at Clawd's feet
  // (its light on her from below), rises, and rests her hand on her head: a rest, not a pat. "Sorekara?" lifts the hand; the
  // lamp comes up in one snap on the first step, and four quicker steps take her and the light off the window's right edge.
  // The window goes dark but for Clawd's eye slits, lit from inside. Then she is in the room beside the butai: hood up, the
  // lantern lit in her hand, her face lit from below (C2's picture in silhouette; the prologue's kuroko from the front).
  {
    const S0 = 166.0, S1 = 177.8, B = 60 / 170 * 4, BEAT = B / 2, NOTE = 159.53, beat = k => NOTE + k * BEAT;
    const X0 = 1060, BOOKX = 950, TS0 = { x: X0, y: FLOOR, s: .2, origin: [1100, 3700] };   // (the lamp and the book at her feet, as the ink stand-up left them)
    const b0 = Math.ceil((168.62 - NOTE) / BEAT), steps = [];
    for (let i = 0; i < 7; i++) steps.push({ t: beat(b0 + i), foot: i % 2 ? 'h' : 'v', close: i === 6, S: 74 });   // (to within arm's reach of her head)
    const b1 = Math.round((175.06 - NOTE) / BEAT), OUT = beat(b1);
    for (let i = 0; i < 4; i++) steps.push({ t: OUT + i * BEAT / 2, dur: BEAT / 2, foot: i % 2 ? 'h' : 'v', S: 150 });   // on the eighths: off the right edge by 176.47
    const walk = makeWalk(steps, 74, BEAT, TS0.s), STOP = steps[6].t + BEAT;
    // the beats of her hands
    const BOW = 166.5, HOVER = 166.85, TAKE = HOVER + BEAT, UP = TAKE + 3 * f, TURN = UP + 3 * f;
    const SETD = STOP + f, RISE = SETD + 5 * f, REST = RISE + 2 * f, GRAB = OUT - f;
    const CARRY = { upperarm: 10, forearm: -34, hand: 0 };
    const bowAt = PUPPET.snap([[0, { torso: 0 }], [BOW, { torso: 44 }], [UP, { torso: 0 }], [SETD, { torso: 44 }], [RISE, { torso: 0 }], [GRAB, { torso: 30 }], [OUT + f, { torso: 0 }]], { inbetween: 1, overshoot: 0 });   // (paper: one drawing down, one up)
    const headAt = PUPPET.snap([[0, { head: 6 }], [BOW, { head: 14 }], [UP, { head: 4 }], [TURN + f, { head: 0 }], [STOP, { head: 14 }], [OUT, { head: 0 }]]);
    const flipAt = q => q < TURN ? -1 : 1;
    const Tq = q => ({ ...TS0, flip: flipAt(q) });                  // (the walk's dx/dy live in the pose)
    const L0 = { x: 830, y: FLOOR };                                   // the lamp at her feet, its stick leaning toward her
    const stickTopFloor = (L, lean) => { const h = CHO.h * LSC, bx = L.x, by = L.y - 7 * LSC - h - 5 * LSC - CHO.w * .2 * LSC, a = lean * Math.PI / 180, Ls = CHO.stick * h; return [bx + Math.sin(a) * Ls, by - Math.cos(a) * Ls]; };
    let SPOT = null;                                                  // where she sets it down at the stop (at her feet, toward Clawd)
    const setSpot = () => { const w = walk(STOP + .2); SPOT = { x: X0 + w.dx + 70, y: FLOOR }; };
    // which arm target, frame by frame: null = the carry pose (the lamp hangs from her fist)
    function armTarget(q, pose, T) {
      if (q >= BOW && q < HOVER) return [BOOKX + 30, 690];            // on the way down to it
      if (q >= HOVER && q < TAKE) return [BOOKX + 10, 705];           // one beat over the book
      if (q >= TAKE && q < UP) return stickTopFloor(L0, LEAN);       // the lamp's stick instead
      if (q >= SETD && q < RISE) return stickTopFloor(SPOT, -LEAN);  // set at her feet
      if (q >= RISE && q < GRAB) { const hd = CLAWDP.world(CPOSE, CP).head.transformPoint(new DOMPoint(860, 250)); return q >= REST ? [hd.x - 6, hd.y - 14] : [hd.x - 40, hd.y - 60]; }
      if (q >= GRAB && q < OUT + f) return stickTopFloor(SPOT, -LEAN); // one snap: down to it and up with it
      return null;
    }
    const lampState = q => q < TAKE ? { floor: L0, lean: LEAN } : (q >= SETD + 2 * f && q < GRAB) ? { floor: SPOT, lean: -LEAN } : { hand: true };
    function poseS(tt) {
      const q = Math.floor(tt * 12 + 1e-6) / 12; if (!SPOT) setSpot();
      const w = walk(q), p = { ...w, ...bowAt(q), ...headAt(q), _ghost: {} }; p.torso = (w.torso || 0) + p.torso;
      const T = Tq(q), tg = armTarget(q, p, T), carrying = q >= TAKE;
      if (tg) Object.assign(p, reachIn(FABLE_S, p, T, 'torso', STAND_ARM, tg));
      else if (carrying) { p.upperarm = CARRY.upperarm + (w.upperarm || 0); p.forearm = CARRY.forearm; p.hand = 0; }
      else { p.upperarm = w.upperarm || 0; p.forearm = 0; p.hand = 0; }
      p.hair = -(p.head + (p.torso || 0)) * .85; p._T = T; return p;
    }
    // the lamp's light this frame: where it is (on the floor, or hanging from her fist, swinging a little as she walks)
    function lampNow(tt, p) {
      const q = Math.floor(tt * 12 + 1e-6) / 12, st = lampState(q);
      if (st.floor) { const h = CHO.h * LSC; return { st, cx: st.floor.x, cy: st.floor.y - 7 * LSC - h / 2 }; }
      const fi = fistAt(FABLE_S, p, p._T, STAND_ARM), dir = flipAt(q), k = Math.floor((q - TURN) * 12 + 1e-6);
      const swing = q < TURN + 4 * f ? [0, 14, -8, 4][Math.max(0, Math.min(3, k))] * dir : 5 * Math.sin(q * 2 * Math.PI / BEAT) * (q >= steps[0].t && q < STOP + .2 || q >= OUT ? 1 : 0);
      const drop = CHO.w * .2 * LSC + 5 * LSC + CHO.h * LSC / 2, a = 28 * Math.PI / 180, Ls = CHO.stick * CHO.h * LSC * .8;
      const tip = [fi[0] + dir * Math.cos(a) * Ls, fi[1] + Math.sin(a) * Ls];
      return { st, fi, dir, swing, cx: tip[0] - Math.sin(swing * Math.PI / 180) * drop, cy: tip[1] + Math.cos(swing * Math.PI / 180) * drop };
    }
    const TAILS_S = [{ len: 2500, w: 118, rest: [97, 100, 104, 107, 108, 105, 100] }, { len: 2150, w: 104, rest: [100, 104, 108, 111, 110, 104, 99] }];
    const HIDE_SEATED = ['lower', 'torso', 'head', 'hair', 'upperarm', 'forearm', 'hand'];
    const BACK2 = 166.0, BACK2N = 20;                                 // the pull-back to the wood, in drawings, as the held note ends
    const EDGE = SCREEN.rect[0] + SCREEN.rect[2];
    function scene(tt) {
      const p = poseS(tt), ln = lampNow(tt, p), gone = ln.cx > EDGE + CHO.w * LSC * .8;   // the light has left the window
      X.fillStyle = '#0d0b0a'; X.fillRect(0, 0, W, H);
      if (!gone) screen(tt, { stops: HOT, tex: .24, power: 1.02, lamp: [ln.cx, ln.cy] });
      else { X.fillStyle = '#0b0908'; X.fillRect(...SCREEN.rect); }
      shadow(c => {                                                  // the screen plane: the rail, what she left, Clawd's puppet
        c.globalCompositeOperation = 'source-over'; c.fillStyle = 'rgb(22,22,26)'; c.fillRect(150, FLOOR, 1620, 10);
        FABLE.draw(c, { _ghost: {} }, T, { hide: HIDE_SEATED });
        PUPPET.drawShape(c, PUPPET.shapeAt(FAN, 'book', 'book', 1), new DOMMatrix().translate(BOOKX, FLOOR).scale(.15));
        CLAWDP.draw(c, CPOSE, CP, { gel: CLAWD_GEL, misreg: [1.5, 1], rods: [{ part: 'torso', at: [1076, 1200], w: 5, lean: -70 }, { part: 'claw_R', at: [1640, 1600], w: 2.5, lean: 26 }] });
      }, 0);
      if (gone) {                                                    // her eye slits, lit from inside, in the dark window
        const M = CLAWDP.world(CPOSE, CP).head, hd = CLAWDP.by.head; X.save(); X.setTransform(X.getTransform().multiply(M));
        const inPoly = (pts, x, y) => { let r = false; for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) { const [xi, yi] = pts[i], [xj, yj] = pts[j]; if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) r = !r; } return r; };
        for (const [ex, ey] of [[956, 704], [1187, 713]]) for (const h of hd.holeList) if (inPoly(h.pts, ex, ey)) {
          X.globalCompositeOperation = 'lighter'; X.shadowColor = 'rgba(255,200,120,.9)'; X.shadowBlur = 18; X.fillStyle = 'rgb(255,226,170)'; X.fill(h.path); }
        X.restore();
      }
      const T2 = p._T;
      shadow(c => {
        TAILS_S.forEach((tl, i) => {
          // solved facing right and mirrored when she faces left (a flipped card flips its ribbon with it)
          let pts = PUPPET.stiff(FABLE_S, poseS, TS0, { part: 'head', at: [900, 820], rest: tl.rest, len: tl.len, drag: .1 }, tt);
          if (T2.flip < 0) pts = pts.map(([x, y]) => [2 * T2.x - x, y]);
          c.setTransform(1, 0, 0, 1, 0, 0); c.globalCompositeOperation = i ? 'multiply' : 'source-over';
          c.fillStyle = FABLE_GEL; c.fill(P(PUPPET.strip(pts, tl.w * T2.s, .85, tl.w * .9 * T2.s)));
        });
        c.globalCompositeOperation = 'source-over';
        drawStanding(c, p, T2, { rods: [{ part: 'torso', at: [1060, 1700], w: 7 }] });
      }, 0);
      // the lamp, over everything on the screen: on the floor with its stick, or hanging from her fist
      if (!gone || ln.cx < EDGE + 200) {
        X.save(); X.beginPath(); X.rect(...SCREEN.rect); X.clip();
        if (ln.st.floor) chochin(ln.st.floor.x, ln.st.floor.y, LSC, { gold: true, stick: ln.st.lean });
        else chochinHang(ln.fi[0], ln.fi[1], ln.dir, LSC, { gold: true, swing: ln.swing });
        X.restore();
      }
      if (!gone) { bridgeText(tt); pageVellum(tt); }                   // (ink on unlit paper is nothing)
      X.save(); X.globalCompositeOperation = 'overlay'; X.globalAlpha = .16; X.fillStyle = X.createPattern(GRAIN[Math.floor(tt * 12) % 4], 'repeat'); X.fillRect(0, 0, W, H); X.restore();
    }
    // in the room: person-sized beside the butai, facing it; two geta steps in from the frame's edge (no glide), still. Hood up;
    // the lantern lit in her hand, low; her face lit from below. Black; the light is in front of her and beneath.
    const ROOM = OUT + 2.5 * BEAT, RX = [2180, 1690], RS = .48, RLSC = 2.3;
    const roomPose = T => { const p = { _ghost: {}, head: -4, hair: 3.4 }; return Object.assign(p, reachIn(FABLE_S, p, T, 'torso', STAND_ARM, [T.x - 110, 560])); };   // her fist at her chest
    const roomT = tt => { const q = Math.floor((tt - ROOM) * 12 + 1e-6) / 12, st = BEAT / 2, k = Math.min(2, Math.max(0, q / st)), i = Math.min(1, Math.floor(k)), u = k >= 2 ? 1 : k - i;
      const e = u * u * (3 - 2 * u), x = RX[0] + (RX[1] - RX[0]) * (i + e) / 2, lift = k < 2 ? -14 * Math.sin(Math.PI * u) : 0;
      return { x, y: 175 + (3700 - 250) * RS + lift, s: RS, flip: -1, origin: [1100, 3700] }; };
    // her hood, up (the canon's): over the crown and down the back to the shoulder, its opening from the brow down behind the
    // cheek to the jaw, so her profile shows (head-part master px)
    const HOOD = [[1330, 330], [1290, 230], [1150, 165], [980, 150], [820, 200], [700, 330], [650, 520], [640, 720], [670, 880], [760, 980], [900, 960], [1020, 880], [1120, 800], [1180, 730], [1230, 620], [1262, 480]];
    let RL = null;
    function roomFable(tt) {
      if (tt < ROOM) return;
      if (!RL) RL = [mkCanvas(W, H), mkCanvas(W, H)];
      const T = roomT(tt), p = roomPose(T), S = RL[0].getContext('2d'), R = RL[1].getContext('2d'), M = FABLE_S.world(p, T);
      S.setTransform(1, 0, 0, 1, 0, 0); S.globalCompositeOperation = 'source-over'; S.clearRect(0, 0, W, H);
      FABLE_S.draw(S, p, T, { solid: true, ink: 'rgb(9,7,9)', hide: ['hair'] });
      S.setTransform(M.head); S.fillStyle = 'rgb(9,7,9)'; S.beginPath(); HOOD.forEach(([x, y], i) => i ? S.lineTo(x, y) : S.moveTo(x, y)); S.closePath(); S.fill();
      S.setTransform(1, 0, 0, 1, 0, 0);
      // the lantern in her hand (hung from its stick), and its light on her from below and in front
      const fi = fistAt(FABLE_S, p, T, STAND_ARM), arrive = ROOM + BEAT, k = Math.max(0, tt - arrive), sw = tt < arrive ? 10 * Math.sin((tt - ROOM) * 2 * Math.PI / (BEAT / 2)) : 8 * Math.exp(-k * 2.6) * Math.cos(k * 7.5);
      const drop = CHO.w * .2 * RLSC + 5 * RLSC + CHO.h * RLSC / 2, a = 0, Ls = CHO.stick * CHO.h * RLSC * .3, tip = [fi[0] - Math.cos(a) * Ls, fi[1] + Math.sin(a) * Ls];
      const lc = [tip[0] - Math.sin(sw * Math.PI / 180) * drop, tip[1] + Math.cos(sw * Math.PI / 180) * drop];
      R.setTransform(1, 0, 0, 1, 0, 0); R.globalCompositeOperation = 'source-over'; R.clearRect(0, 0, W, H);
      R.drawImage(RL[0], 0, 0); R.globalCompositeOperation = 'source-in'; R.fillStyle = 'rgba(255,196,120,.95)'; R.fillRect(0, 0, W, H);
      R.globalCompositeOperation = 'destination-out'; R.drawImage(RL[0], 4, -6);                    // the edges that face the lamp (in front and below)
      R.globalCompositeOperation = 'destination-in'; const g = R.createRadialGradient(lc[0], lc[1], 0, lc[0], lc[1], 1900 * RS); g.addColorStop(0, '#000'); g.addColorStop(.5, 'rgba(0,0,0,.8)'); g.addColorStop(1, 'rgba(0,0,0,0)'); R.fillStyle = g; R.fillRect(0, 0, W, H);
      // her lantern lights the air of the room around her: her black shape reads against it
      X.save(); X.globalCompositeOperation = 'lighter'; const hz = X.createRadialGradient(lc[0], lc[1], 20, lc[0], lc[1], 820);
      hz.addColorStop(0, 'rgba(150,104,56,.42)'); hz.addColorStop(.45, 'rgba(90,60,34,.2)'); hz.addColorStop(1, 'rgba(0,0,0,0)'); X.fillStyle = hz; X.fillRect(0, 0, W, H); X.restore();
      X.save(); X.globalCompositeOperation = 'lighter'; X.filter = 'blur(10px)'; X.globalAlpha = .6; X.drawImage(RL[1], 0, 0);
      X.globalCompositeOperation = 'source-over'; X.filter = 'none'; X.globalAlpha = 1; X.drawImage(RL[0], 0, 0);
      X.globalCompositeOperation = 'lighter'; X.filter = 'blur(1.4px)'; X.drawImage(RL[1], 0, 0); X.restore();
      chochinHang(fi[0], fi[1], -1, RLSC, { swing: sw, len: .3, stickAngle: 0, gold: true, ribs: 'rgba(22,40,96,.6)' });   // the lamp she carried out: the same gold, indigo only in its ribs (Fable)
    }
    LOOPS.bridgeB8 = t => {
      const ts = S0 + Math.floor(t * 12 + 1e-6) / 12;
      const e = Math.min(1, Math.floor((ts - BACK2) * 12 + 1e-6) / BACK2N), ee = e * e * (3 - 2 * e);
      const cam = camLerp(CAM_WINDOW, CAM_WIDE, ee); stage(ts, scene, { cam, doors: 1 });
      roomFable(ts);
      readers(ts, cam);
    };
    LOOPS.bridgeB8.len = S1 - S0;
    let TEXT = null;
    function w8(n, after) { return ((window.WORDS || []).find(x => x.t0 > after && x.w.toLowerCase().replace(/[^a-z]/g, '').startsWith(n)) || {}).t0 ?? 999; }
    function bridgeText(tt) {
      if (!TEXT) TEXT = [[w8('mukashi', 168), 'Mukashi mukashi was a long time ago.'], [w8('this', 172), 'This is now.'], [w8('sorekara', 174.5), '“Sorekara?”']];
      TEXT.forEach(([t0, str], i) => inkVellum(str, 190, 262 + i * 76, tt, t0, { font: 'caslon', size: 54, alpha: .92, col: 'rgb(30,24,22)' }));
    }
  }
}

