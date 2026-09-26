// finale.js: the final chorus in Clawd's world (song 177.8-202.59, bars ~126-143.5), Fable's ruling (CLAWDWORLD.md, "F"):
//   177.8  the room wide (B9's end): Fable standing at the butai's right, lantern in hand; the window blazes as Clawd's stage
//          powers up, and under the flood the paper silhouette is the illustrated rig. 178-179.2 she sets the lantern on her
//          cushion; 179.2-181 the camera pushes through the window as she walks out right.
//   181    Clawd's stage full frame: Fable hops in from the right and pushes her hood back (src/fablestage.js), then dances Clawd's
//          pose a bar late at half amplitude on twos; unison from the sideways step at 135; Clawd turns on "why" and finds a face.
//   F4/F6  her lines press into the card's margin in full ink; F6 lands on Clawd's LEDs at the same time.
//   141    the hit: freeze, the margin empty. ~142 the room wide: the frozen picture in the window, the light ringing out onto her
//          cushion and the lantern on it. The paper world's outro follows at 202.59.
// Clawd's choreography below is keyed (the move vocabulary, engine/moves.js), with the motion lab's groove on top.
//   node engine/render.mjs projects/tsuzuku --loop=finale --clip=177.8:202.59
{
  const BAR = 60 / 170 * 4, beat = BAR / 4, b2t = b => b * BAR;
  const choreo = () => MOVES.choreo({ bpm: 170, t0: 0 }, {
    legs: [
      [124, 'idle'], [127, 'groove', { amp: 6 }],
      [129, 'bounce'], [131, 'groove'], [133.9, 'bounce', { amp: 12 }],
      // "Sideways, sideways, that's the way we go!": the fable's step, landing each downbeat, weight low, feet flat (she steps too)
      // (each starts closed and its lead foot steps out to LAND on the downbeat, as in world A: a step already out slid into place)
      [134.835, 'sideStep', { dir: -1, every: 1, steps: 2, lead: .66 }], [137, 'groove', { root: -480 }],
      [138.835, 'sideStep', { dir: 1, every: 1, steps: 2, root0: -480, lead: .66 }], [141, 'idle'],
    ],
    arms: [
      [124, 'idle'], [127.5, 'rise'],                                   // the build: rising with the power-up
      [129, 'reach', { side: 1 }], [129.86, 'armPump', { fade: .3 }],  // To be continued! (Tsuzuku!)
      [130.15, 'reach', { side: 1, a: 50 }], [130.36, 'armsOut', { a: 40 }],            // To be continued! (Tsuzuku!)
      [131.14, 'pointOut', { side: 1 }],                               // Don't you dare close the book on me!
      [132.33, 'handOnChest', { side: 1, fade: .4 }],                  // I'm made of
      [132.99, 'armsOut', { a: 38 }],                                  // "why?"! (she turns to Fable)
      [133.95, 'callEar', { side: -1, fade: .4 }], [134.5, 'snipSnip', { fade: .3 }],   // (So-re-ka-ra?!)
      [135, 'claws', { snip: 0 }], [136.14, 'armPump'],                // Sideways, sideways, that's the way we go!
      [136.99, 'pageWipe', { side: -1, fade: .3 }],                    // Turn the page,
      [137.93, 'reach', { side: 1 }],                                  // I want to see!
      [138.87, 'armPump'], [139.96, 'swingArms'],                      // To be continued (tsuzuku!), and then, and then, and then-
      [140.85, 'rise', { fade: .15 }],                                 // the hit: she never lands (it rises)
    ],
    head: [
      [124, 'look', { view: 'F', y: .2 }], [127.5, 'look', { view: 'F', y: -.2 }],
      [129, 'headBob'], [131, 'look', { view: 'F' }],
      [132.9, 'look', { view: 'HR', z: -3 }],                          // "why": she turns and finds a face
      [133.9, 'headTilt', { amp: 7 }], [135, 'headBob'], [137, 'look', { view: 'F' }], [138.87, 'headBob'],
      [140.85, 'look', { view: 'F', y: -.3 }],
    ],
  }, { lips: MOVES.lips(window.WORDS, 'clawd', window.VOCAL_ENV), blinks: MOVES.blinks(23, 176, 205) });
  // the motion lab's layers, as in world A (src/chorus.js): the groove, then the phrases from motion capture listed in
  // refs/mocap/phrases.json (the finale's are the f* phrases, bars 129-141), keyed hands, faces and views on top
  let P = null, B0 = null;
  const base = () => (B0 = B0 || RIG.perform(RIGS.clawd, MOVES.follow(choreo(), MOVES.BODY, { start: 124 * BAR, world: { footLX: 1, footRX: 1, hipX: 140 } })));
  const get = () => (P = P || (typeof MOTIONLAB !== 'undefined' ? MOTIONLAB.layer(MOTIONLAB.groove(base())) : base()));
  window.CHOREO = window.CHOREO || {};
  window.CHOREO.clawdF = { t0: 126 * BAR, dur: 17.5 * BAR, P: get, base };            // (for the harness; base: before the lab's layers)

  // her backup crabs, as in world A: they land the downbeats; pincers on the crowd call and the sideways step; frozen at the hit
  const crabs = (t, i, r) => {
    const b = t / BAR, ph = (t % beat) / beat, bb = Math.floor(t / beat) % 4;
    const call = b >= 133.9 && b < 135, claws = b >= 135 && b < 137, live = b >= 128;
    const hop = (live ? 16 : 5) * Math.sin(Math.PI * ph), sq = (live ? .14 : 0) * Math.max(0, 1 - ph / .22);
    const sway = (b >= 131 && b < 133.9) || (b >= 137 && b < 139) ? .12 * Math.sin(Math.PI * t / BAR * 2) : 0;
    const snip = (call && bb >= 2) || claws ? Math.max(0, Math.sin(Math.PI * Math.min(1, ph / .3))) : 0;
    const walk = claws || (b >= 139 && b < 141) ? t / beat / 2 : null;
    return { hop, sq, lean: sway, pincer: call || claws, snip, walk, armL: call ? .5 : 0, armR: call ? .5 : 0, eyes: snip > .5 ? 'happy' : undefined };
  };
  const ROWS = [{ xs: [330, 580, 1590, 1820], y: 800, s: .8, seed: 5, lag: .06 }, { xs: [300, 540, 1660, 1880], y: 930, s: 1.05, lag: .04 }];   // (Fable stands upstage right)

  // where they stand (world coords, the card's floor): Clawd centre; Fable one step upstage at her stage-left (house right)
  // Fable is the taller one ("tall and narrow next to Clawd's fluffy A-line", FABLE.md §3; no number in the docs; the paper world
  // stages her at ~1.6x Clawd's puppet, a mother-and-child scale). On Clawd's stage: 10% taller on screen, a step upstage (Clawd
  // stands 975 world px, soles to the buns' top; Fable h 1072, her crown ~150 px above). FW.h is the interface: the rig scales
  // itself to it (the current puppet: s = h / its drawn height 2085)
  const FW = { x: 1520, y: 1000, h: 1072, s: 1072 / 2085 };
  const clawdT = (t, W2S, c) => { const q = P(t), [x, y] = W2S(960 + (q.rootX || 0) * .27, 1040); return { x, y, s: .27 * c.z }; };

  // the camera: the room (butai px), then the card's own camera (world). [bar, from, to, room?]
  const CAMW = { x: 1920, y: 1180, zoom: .5 }, CARDC = { x: 1919.5, y: 1303, zoom: 1.0475 };
  const WIDE = { cx: 960, cy: 540, z: 1 }, FULL = { cx: 960, cy: 560, z: 1.02 }, room = (a, b = a) => ({ room: [a, b] });
  const TWO = (cx, cy, z) => ({ cx, cy, z });
  // the card's camera frames the two of them: both full figures with headroom over Fable's crown (world y ~ -10), inside the washi
  // border (the picture is ~972 px tall on screen)
  const FULLF = TWO(1220, 500, .8), MED2 = (z = 1.24, cy = 310) => TWO(1240, cy, z), CU2 = TWO(1240, 170, 1.72), HALL = TWO(1120, 490, .76);
  const SHOTS = [
    [125.9, FULLF, FULLF, room(CAMW)],                                // the room: B9's end; the window blazes
    [126.93, FULLF, FULLF, room(CAMW, CARDC)],                        // the push-in through the window (she walks out right)
    [128.21, FULLF, FULLF],                                            // her stage, full frame: Fable hops in from the right
    [129, TWO(1220, 500, .78), FULLF],                                 // the drop (the key change)
    [130.15, MED2(1.16, 340), MED2(1.22, 330)],
    [131.1, MED2(), MED2(1.29, 305)],                                  // the two of them
    [132.9, CU2, TWO(1240, 165, 1.78)],                                // "why": she turns and finds a face
    [133.9, HALL, HALL],                                               // (So-re-ka-ra?!) the hall
    [135, TWO(1130, 500, .8), TWO(1130, 500, .8)],                  // sideways, together: locked, full bodies
    [137, TWO(1100, 495, .8), TWO(1100, 490, .83)],                  // F6: her line on the LEDs and in the margin
    [138.87, FULLF, MED2(1.02, 400)],
    [140.85, MED2(1.34, 280), MED2(1.34, 280)],                          // the hit, close: frozen
    [142, WIDE, WIDE, room(CAMW)],                                     // the room: the frozen window, the light ringing out
  ];
  const HITS = [[129, .05, 6], [141, .05, 4]]; for (let bb = 130; bb < 141; bb++) if (bb !== 134) HITS.push([bb, .017, 0]);
  const TF = 199.07;                                                   // the hit on the dash ("and then-"): everything freezes

  // her lines in the margin, full ink (F4, F6); the margin empties on the hit (F8). F6 also on Clawd's side screens
  // (Fable: in the finale her lines press as she sings them, a bar behind Clawd's; three lines, full ink, then empty at the hit)
  const NOTES = { list: [[b2t(130.2), '\u2026to be continued.'], [189.11, 'And I\u2019m made of \u201cand then.\u201d'], [193.39, '~~I\u2019ve read how it ends.~~ I\u2019d still like to see.']],
                  ink: 'rgb(22,22,26)', clear: TF };
  const side = t => (t >= b2t(137) && t < b2t(139) ? ['I’D', 'STILL', 'LIKE', 'TO SEE'] : null);

  // the room figure: standing Fable (the lantern, the set-down, the walk out), at her place beside the butai
  const FEET = [3308, 2104];                                           // butai px: where she knelt in world A ("I stand where I sat")
  const roomFable = (t, frozen) => (X, cam, lit) => {
    const T = { x: W / 2 + (FEET[0] - cam.x) * cam.zoom, y: H / 2 + (FEET[1] - cam.y) * cam.zoom, s: 1.394 * cam.zoom };
    FABLESTAGE.room(X, t, T);
  };
  // the blaze at 177.8 (the stage powering up: it covers the medium's change) and the light ringing out after the freeze
  const roomAfter = t => (X, cam) => {
    const [wx, wy] = [W / 2 + (1919.5 - cam.x) * cam.zoom, H / 2 + (1303 - cam.y) * cam.zoom], R = 1100 * cam.zoom;
    let a = 0, col = '255,240,250';
    if (t < 178.5) a = .95 * Math.max(0, 1 - (t - 177.8) / .7) ** 1.6;
    if (t >= b2t(142)) { a = .45 * Math.exp(-(t - b2t(142)) / 1.1) + .08; col = '255,214,236'; }
    if (a <= 0) return;
    X.save(); X.globalCompositeOperation = 'lighter';
    const g = X.createRadialGradient(wx, wy, R * .2, wx, wy, R * 2.2); g.addColorStop(0, `rgba(${col},${a})`); g.addColorStop(.45, `rgba(${col},${a * .35})`); g.addColorStop(1, `rgba(${col},0)`);
    X.fillStyle = g; X.fillRect(0, 0, W, H); X.restore();
  };

  LOOPS.finale = t => {
    get();
    const tt = Math.min(t, TF), c = IDOLSTAGE.camFrom(SHOTS, t, HITS, null);        // (from 181 the room is gone: the card fills the frame)
    IDOLSTAGE.OVR.side = side;
    IDOLSTAGE.frame(tt, (W2S, cam) => {
      mascotTroupe(tt, crabs, ROWS);
      FABLESTAGE.stage(X, tt, FW, P, { enter: 2000 });                 // (upstage: behind Clawd; she hops in from beyond the frame's edge)
      RIGS.clawd.draw(X, tt, P, clawdT(tt, W2S, cam));
    }, { cam: c, clawdX: 960 + (P(tt).rootX || 0) * .27, notes: NOTES, roomFable: roomFable(t), roomAfter: roomAfter(t),
         clawdAt: (t2, W2S, cam, g) => RIGS.clawd.draw(g || X, t2, P, clawdT(t2, W2S, cam)) });
  };
  LOOPS.finale.len = 203;
}
