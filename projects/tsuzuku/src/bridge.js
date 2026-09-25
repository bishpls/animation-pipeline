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
      [WT.flew - L - 4 * f, { upperarm: -60, forearm: 30, hand: -5 }],   // the wings high; the falling figure hangs from that hand by the ankles
      [WT.moral - 6 * f, { forearm: 14, hand: -6, upperarm: 6 }],       // brought in to chest height to be put away (the open fan clear of her face)
      [WT.job + 6 * f, LAP]]);                                          // folded, back in her lap
    head = PUPPET.snap([[0, { head: 7 }], [WT.all - 7 * f, { head: 0 }], [WT.fox - L - 3 * f, { head: 8 }], [WT.crow - L - 3 * f, { head: -4 }],
      [WT.boy - L - 3 * f, { head: 2 }], [WT.flew - L - 3 * f, { head: -7 }], [WT.sun - 2 * f, { head: 3 }], [WT.moral - 5 * f, { head: 2 }],
      [WT.job + 7 * f, { head: 7 }], [WT.stand, { head: 4 }]]);
  };
  const BLINKS = [133.4, 142.6, 146.3, 151.7, 155.2];
  const T = { x: 560, y: 960, s: .2, origin: [1150, 2760] };
  // Clawd's puppet, set down at the edge: leaning, head down, rod leaning, the eye slits still lit
  const CP = { x: 1690, y: FLOOR, s: .16, origin: [1076, 2800] }, CPOSE = { skirt: 11, head: 15, upperarm_L: 6, upperarm_R: -4, claw_L: 10, claw_R: -8, _ghost: {} };
  function scene(ts) {
    const strike = {}; let bright = 0;
    for (const [k, t0, dir] of STRIKES) { const u = pulled(ts, t0); strike[k] = [u, dir]; bright += u * (k.startsWith('rocks') ? .5 : 1); }
    const b = bright / 4, stops = HOT.map(([k, c], i) => [k, mixHex(FABLE_LAMP[i][1], c, b)]);
    X.fillStyle = '#0d0b0a'; X.fillRect(0, 0, W, H);
    screen(ts, { stops, tex: .32 - .08 * b, power: 1 + .12 * b });
    shore(ts, { floor: FLOOR, still: CLACK, strike });
    const p = { ...arm(ts), ...head(ts), _ghost: {} }; p.hair = -(p.head || 0) * .85;
    const blink = BLINKS.some(b0 => ts >= b0 && ts < b0 + 2 * f);
    shadow(c => {
      c.globalCompositeOperation = 'source-over';
      if (strike.ground[0] > 0) { c.fillStyle = 'rgb(22,22,26)'; c.fillRect(150, FLOOR, 1620, 10); }   // the plain rail the beach lay on
      CLAWDP.draw(c, CPOSE, CP, { gel: CLAWD_GEL, misreg: [1.5, 1], rods: [{ part: 'torso', at: [1076, 1200], w: 5, lean: -70 }, { part: 'claw_R', at: [1640, 1600], w: 2.5, lean: 26 }] });
      FABLE.draw(c, p, T, { props: [fanProp(seq, ts)], cover: blink ? { head: [[1496, 491]] } : {} });
    }, 0);
    X.save(); X.globalCompositeOperation = 'overlay'; X.globalAlpha = .16; X.fillStyle = X.createPattern(GRAIN[Math.floor(ts * 12) % 4], 'repeat'); X.fillRect(0, 0, W, H); X.restore();
  }
  // B4: "You stand in the dark," the camera pulls back past the wood, in drawings, and holds
  const BACK = 152.46, BACKN = 12;
  LOOPS.bridge = t => {
    if (!WT) { WT = build(); poses(); }
    const ts = S0 + Math.floor(t * 12 + 1e-6) / 12;
    const e = ts < BACK ? 0 : Math.min(1, Math.floor((ts - BACK) * 12 + 1e-6) / BACKN), ee = e * e * (3 - 2 * e);
    stage(ts, scene, { cam: camLerp(CAM_WINDOW, CAM_WIDE, ee), doors: 1 });
    audience(ts, { y: H + 270 - 150 * ee, lift: 120, scale: .52 * (1 - .35 * ee) });
  };
  LOOPS.bridge.len = 156.2 - S0;
}
