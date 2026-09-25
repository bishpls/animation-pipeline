// verse.js: the telling, song 12.7-24.0 (BEATS C3, V1, V2), on the song's clock, handing off to LOOPS.origami at 24.0.
// C3: the butai's doors open on the lit screen; the camera walks in to the window. V1: "Once upon a time there was a crab":
// the fan opens and becomes the crab, which hops down from her hand to the floor; "and her mother": the mother crab (the fan's
// crab, larger, stiff) hops in from the wing; "and a line": a new fan from her sleeve becomes the ruled line, laid on the ground,
// running out across it. V2: "Walk straight," said the mother (a stiff bob); "why d'you scuttle side to side?": the little one's
// paper lights clay-orange (colour is Clawd's; this is where it enters) and she scuttles to where the story will unfold her.
{
  const FLOOR = 962, f = 1 / 12, S0 = 12.7, S1 = 24.0, T = { x: 560, y: 960, s: .2, origin: [1150, 2760] };
  const PAPER_GEL = 'rgba(236, 118, 58, .92)', CREASE = 'rgba(128, 42, 12, .8)';
  const LAP = { forearm: 40, hand: 25, upperarm: 6 }, EYE = { forearm: -12, hand: 8, upperarm: 0 }, REST = { forearm: 0, hand: 0, upperarm: 0 };
  const LITTLE = { land: 1000, end: 1250, sc: .236 }, MOTHER = { x: 1520, from: 1960, sc: .364 }, LINE = { x0: 720, len: 980 };
  const land = t => t - 4 * f;                                        // a morph lands on its word
  let K = null;
  function keys() {
    const w = n => ((window.WORDS || []).find(x => x.t0 > 12 && x.t0 < 25 && x.w.toLowerCase().replace(/[^a-z]/g, '') === n) || {}).t0;
    const k = { time: w('time'), crab: w('crab'), mother: w('mother'), line: w('line'), walk: w('walk'), straight: w('straight'), why: w('why'), scuttle: w('scuttle') };
    k.release = k.crab + 2 * f; k.landed = k.release + 3 * f;         // the crab leaves the hand: one hop, three drawings
    k.sleeve = k.mother + 6 * f; k.fan2 = k.sleeve + 3 * f;           // a new fan from her sleeve
    k.set = k.line + 3 * f; k.laid = k.set + 2 * f;                   // the line lowered level to the floor, then run out
    k.fan3 = S1 - 8 * f;                                              // and one more fan, closed, before the story goes on
    K = k;
    K.fanA = PUPPET.morphs([[0, 'fan_closed'], [land(k.time), 'fan_open'], [land(k.crab), 'crab']]);
    K.fanB = PUPPET.morphs([[0, 'fan_closed'], [land(k.line), 'line']]);
    K.arm = PUPPET.snap([[0, REST], [k.time - 8 * f, EYE], [k.release + f, LAP], [k.sleeve, { forearm: 22, hand: 10, upperarm: 10 }], [k.fan2, EYE],
      [k.set - 2 * f, { forearm: 30, hand: -30, upperarm: -20 }], [k.laid + 3 * f, LAP], [k.fan3, REST]]);
    K.head = PUPPET.snap([[0, { head: 0 }], [k.release, { head: 8 }], [k.mother + 3 * f, { head: 5 }], [k.fan2, { head: 1 }], [k.set, { head: 9 }],
      [k.walk, { head: 5 }], [k.why, { head: 9 }], [k.fan3, { head: 0 }]]);
  }
  const poseAt = tt => { const q = Math.floor(tt * 12 + 1e-6) / 12, p = { ...K.arm(q), ...K.head(q), _ghost: {} }; p.hair = -(p.head || 0) * .85; return p; };
  const hopX = (a, b, t0, t1, ts, lift, n) => {                       // stop-motion hops from a to b: position per drawing, a lift in each hop
    const u = Math.min(1, Math.max(0, (ts - t0) / (t1 - t0))), hu = u * n, k = Math.min(n - 1, Math.floor(hu)), fr = hu - k;
    return [a + (b - a) * u, u >= 1 ? 0 : -lift * Math.sin(Math.PI * fr), fr];
  };
  // the mother and the line, as they stand from V1 on (shared with the unfold, which runs on from 24.0)
  window.VERSE_SET = (c, ts) => {
    if (!K) { if (!window.WORDS) return; keys(); }
    if (ts >= K.mother) {                                              // the mother hops in from the wing, stiff (no rock), and stands
      let [x, y] = hopX(MOTHER.from, MOTHER.x, K.mother, K.mother + 9 * f, ts, 16, 4);
      if ((ts >= K.walk && ts < K.walk + 2 * f) || (ts >= K.straight && ts < K.straight + 2 * f)) y -= 10;   // "Walk straight," a stiff bob
      PUPPET.drawShape(c, PUPPET.shapeAt(FAN, 'crab', 'crab', 1), new DOMMatrix().translate(x, FLOOR + y).scale(MOTHER.sc));
    }
    if (ts >= K.laid) {                                                // the line on the ground, run out in three drawings
      const d = Math.min(3, Math.floor((ts - K.laid) * 12 + 1e-6)), L = 140 + (LINE.len - 140) * [0, .45, .8, 1][d];
      PUPPET.drawShape(c, PUPPET.shapeAt(FAN, 'line', 'line', 1), new DOMMatrix().translate(LINE.x0, FLOOR - 7).rotate(90).scale(.45, L / 700));   // a ruler lying on the ground, its ticks open to the light
    }
  };
  function little(c, ts) {                                             // the little one: black paper until "why", then clay-orange
    if (ts < K.landed) return;
    let x = LITTLE.land, y = 0, rock = 0;
    if (ts >= K.scuttle) { const [hx, hy, fr] = hopX(LITTLE.land, LITTLE.end, K.scuttle, S1 - f, ts, 16, 4); x = hx; y = hy; rock = 5 * Math.sin(2 * Math.PI * fr); }
    const M = new DOMMatrix().translate(x, FLOOR + y).rotate(rock);
    const d = Math.floor((ts - K.why) * 12 + 1e-6), glow = ts < K.why ? 0 : [.35, .7, 1][Math.min(2, d)];
    if (glow > 0) PUPPET.drawShape(c, PUPPET.shapeAt(ORI, 'ocrab', 'ocrab', 1), M.scale(.16), null, { gel: PAPER_GEL, crease: CREASE });
    if (glow < 1) { c.save(); c.globalAlpha = 1 - glow; PUPPET.drawShape(c, PUPPET.shapeAt(FAN, 'crab', 'crab', 1), M.scale(LITTLE.sc)); c.restore(); }
  }
  function scene(ts) {
    X.fillStyle = '#0d0b0a'; X.fillRect(0, 0, W, H);
    screen(ts, { stops: FABLE_LAMP, tex: .32 });
    shore(ts, { floor: FLOOR });
    const p = poseAt(ts), props = [];
    if (ts < K.release) props.push(fanProp(K.fanA, ts));
    else if (ts >= K.fan2 && ts < K.set) props.push(fanProp(K.fanB, ts));
    else if (ts >= K.fan3) props.push(fanProp(() => ['fan_closed', 'fan_closed', 1], ts));
    shadow(c => {
      seatedRibbon(c, poseAt, T, ts);
      VERSE_SET(c, ts); little(c, ts);
      if (ts >= K.release && ts < K.landed) {                          // the crab in the air: one hop from her hand to the floor
        const Mh = FABLE.world(poseAt(K.release), T).hand.translate(FAN_GRIP[0], FAN_GRIP[1]), h0 = Mh.transformPoint(new DOMPoint(0, 0));
        const u = (Math.floor((ts - K.release) * 12 + 1e-6) + 1) / 3, x = h0.x + (LITTLE.land - h0.x) * u, y = h0.y + (FLOOR - h0.y) * u - 120 * Math.sin(Math.PI * u);
        PUPPET.drawShape(c, PUPPET.shapeAt(FAN, 'crab', 'crab', 1), new DOMMatrix().translate(x, y).scale(.2 + (LITTLE.sc - .2) * u));
      }
      if (ts >= K.set && ts < K.laid) {                                // the line lowered level to the floor, two drawings
        const u = (Math.floor((ts - K.set) * 12 + 1e-6) + 1) / 2, Mh = FABLE.world(poseAt(K.set), T).hand.translate(FAN_GRIP[0], FAN_GRIP[1]), h0 = Mh.transformPoint(new DOMPoint(0, 0));
        PUPPET.drawShape(c, PUPPET.shapeAt(FAN, 'line', 'line', 1), new DOMMatrix().translate(h0.x + (LINE.x0 - h0.x) * u, h0.y + (FLOOR - 7 - h0.y) * u).rotate(90).scale(.2 + .25 * u, .2));
      }
      FABLE.draw(c, p, T, { props, rods: FABLE_RODS });
    }, 0);
    pageVellum(ts); pageStrip(ts);
    X.save(); X.globalCompositeOperation = 'overlay'; X.globalAlpha = .16; X.fillStyle = X.createPattern(GRAIN[Math.floor(ts * 12) % 4], 'repeat'); X.fillRect(0, 0, W, H); X.restore();
  }
  // C3: the doors open (10 drawings) on the lit screen; the camera walks in to the window (16 drawings)
  const DOOR0 = 12.8, PUSH0 = 13.4;
  LOOPS.telling = t => {
    if (!K) keys();
    const ts = S0 + Math.floor(t * 12 + 1e-6) / 12;
    const dd = Math.min(1, Math.max(0, Math.floor((ts - DOOR0) * 12 + 1e-6) / 10)), e = Math.min(1, Math.max(0, Math.floor((ts - PUSH0) * 12 + 1e-6) / 16)), ee = e * e * (3 - 2 * e);
    window.SHORE = true;
    try { stage(ts, scene, { cam: camLerp(CAM_WIDE, CAM_WINDOW, ee), doors: dd * dd * (3 - 2 * dd) }); } finally { window.SHORE = false; }
    audience(ts, { y: H + 120 + 210 * ee, lift: 120, scale: .52 * (.65 + .35 * ee), calls: [[11.44, 14.04]] });
  };
  LOOPS.telling.len = S1 - S0;
}
