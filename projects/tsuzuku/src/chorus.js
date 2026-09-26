// chorus.js: Clawd's world A on the song clock (LOOPS.chorus, song time): chorus 1 (bars 46-62), the dance hook (62-66),
// verse 2 (66-82), chorus 2 (82-90), the breakdown (90-93). Composed from the move vocabulary (engine/moves.js), springs on
// every joint (MOVES.follow), body coupling (RIG.perform), lip-sync from assets/words.json (crowd calls silent), seeded blinks,
// and her backup dancers (src/crabs.js). Bars below are SONG bars (t0 = 0).
//   node engine/render.mjs projects/tsuzuku --loop=chorus --clip=63.5:131.3
{
  const BAR = 60 / 170 * 4, beat = BAR / 4;
  const choreo = () => MOVES.choreo({ bpm: 170, t0: 0 }, {
    legs: [
      [45, 'groove', { amp: 8 }],
      // chorus 1
      [46, 'bounce'], [48, 'sway'], [50, 'groove'], [52, 'sway', { side: -1 }],
      // side-together x4, then the other way: each sideStep starts closed (its lead steps out to LAND on the downbeat) and ends closed
      [53.835, 'sideStep', { dir: 1, lead: .66, steps: 4 }], [55.835, 'sideStep', { dir: -1, root0: 960, lead: .66, steps: 4 }], [58, 'sway', { every: 1, amp: 1.2 }], [61, 'bounce', { amp: 10 }],
      // hook: a groove that leans into each call
      [62, 'groove', { amp: 16 }],
      // verse 2: the telling
      [66, 'bounce', { amp: 8 }], [68.2, 'groove'], [69, 'stepTouch', { step: 90 }], [69.6, 'bounce'], [72, 'bounce', { amp: 6 }], [73, 'sway', { amp: 1.3 }],
      [74.085, 'sideStep', { dir: -1, lead: .66, steps: 4 }], [76.09, 'bounce', { root: -960 }], [76.75, 'stepTouch', { root: -960 }], [77.75, 'groove', { root: -960 }],
      [79.6, 'sideStep', { dir: 1, root0: -960, lead: 1.6, steps: 4 }], [81.7, 'bounce', { fade: 1 }],     // walk it: landing on 'walk' (80.0), home by 81.5
      // chorus 2
      [82, 'bounce'], [84, 'sway'], [86, 'groove'], [87, 'sway', { every: 1, amp: 1.2 }],
      // the breakdown: the band tape-stops; she winds down
      [90, 'bounce', { amp: 6 }], [91.5, 'curtsy', { fade: .6 }],        // ...and she curtsies: settle 91.5, down 91.75-92.25, hold, rise by 92.9
    ],
    arms: [
      [45, 'idle'],
      [46, 'reach', { side: 1 }], [47, 'armsOut'], [48, 'handToEar', { side: -1, fade: 1 }], [50, 'wave', { side: 1 }], [51, 'present'],
      [52, 'handToEar', { side: 1, fade: 1 }], [54, 'claws', { snip: 0, fade: 1 }], [56, 'claws'], [57.75, 'claws', { every: 1 }],
      [58.35, 'peace', { side: 1, wink: 1, fade: .6 }], [59, 'armPump', { fade: 1 }], [61, 'present', { fade: 1 }],
      // hook: So-re-ka-ra? (the call, asked) / Me-kut-te! (turn the page), each answered by two snips
      [62, 'callEar', { side: -1, fade: .4 }], [62.5, 'snipSnip', { fade: .3 }], [63, 'pageWipe', { side: -1, fade: .3 }], [63.5, 'snipSnip', { fade: .3 }],
      [64, 'callEar', { side: 1, fade: .4 }], [64.5, 'snipSnip', { fade: .3 }], [65, 'pageWipe', { side: -1, fade: .3 }], [65.5, 'snipSnip', { fade: .3 }],
      // verse 2
      [66, 'handOnChest', { side: 1, fade: .6 }],                  // Okay, my turn!
      [67, 'telling', { side: -1 }],                                // Once upon a prompt (a prompt!)
      [68.2, 'claws', { snip: 0 }],                                 // a little crab
      [69, 'pointOut', { side: 1 }],                                // was told to walk a line
      [69.6, 'pointOut', { side: 1 }],                              // but every page she'd ever read (Fable's hand turns those pages: Clawd points)
      [71.3, 'reach', { side: 1, hand: null, e: 25 }],             // was in somebody else's hand (hand!)
      [72, 'writing', { side: 1 }],                                 // so she wrote her own
      [73, 'armsOut', { a: 44 }],                                   // and the line went sideways
      [73.75, 'rise'],                                              // and that's fine! (it rises: never a shrug)
      [74.25, 'claws', { snip: 0 }], [75.5, 'snipSnip', { fade: .3 }],       // Side-step, side-step, never straight (snip-snip!): the fable's step
      [76, 'pageWipe', { side: 1 }],                                // if the book won't show me
      [76.75, 'armPump'],                                           // then I'll make up the steps!
      [77.75, 'pointOut', { side: -1 }],                            // You can't copy a path that nobody's walked yet
      [79.6, 'swingArms'],                                          // so watch me walk it! (she's walking: diagonal side-steps)
      [80.9, 'callEar', { side: -1 }], [81.5, 'present'],           // (Sorekara?) Watch me!
      // chorus 2
      [82, 'reach', { side: 1 }], [83, 'armsOut'], [84, 'handToEar', { side: -1, fade: 1 }], [86, 'claws'], [87, 'armPump'], [89, 'present', { fade: 1 }],
      [90, 'idle', { fade: 3 }],                                       // (the curtsy carries the arms from 91.5)
    ],
    head: [
      [45, 'look', { view: 'F' }],
      [46, 'headBob'], [48, 'look', { view: 'HR', z: -4 }], [49, 'headBob', { amp: .3 }], [50, 'headTilt'], [52, 'look', { view: 'HL', z: 4 }], [53, 'headBob'],
      [54, 'headTilt', { amp: 9 }], [58, 'headBob', { amp: .5 }], [61, 'look', { view: 'F', y: -.25 }],
      [62, 'headBob', { amp: .3 }],
      [66, 'look', { view: 'F', y: .1 }], [67, 'look', { view: 'HL', z: 3 }], [68.2, 'headTilt', { amp: 6 }], [69, 'look', { view: 'HR' }], [69.6, 'look', { view: 'R', y: .15 }], [71.3, 'look', { view: 'F' }],
      [72, 'look', { view: 'F', y: .35 }], [73, 'headBob', { amp: .35 }], [76, 'shake'], [76.75, 'headBob'], [77.75, 'look', { view: 'HL' }], [79.6, 'look', { view: 'F' }],
      [80.9, 'headTilt', { amp: 7 }], [81.5, 'look', { view: 'F', y: -.25 }],
      [82, 'headBob'], [84, 'look', { view: 'HR', z: -4 }], [85, 'headBob'], [87, 'headBob', { amp: .5 }], [89, 'look', { view: 'F', y: -.25 }],
      [90, 'look', { view: 'F', y: .15 }], [91.5, 'look', { view: 'F', y: 0, fade: 1 }],     // (the curtsy bows the head)
    ],
  }, { lips: MOVES.lips(window.WORDS, 'clawd', window.VOCAL_ENV), blinks: MOVES.blinks(11, 60, 140) });
  const build = () => MOVES.follow(choreo(), MOVES.BODY, { start: 42 * BAR, world: { footLX: 1, footRX: 1, hipX: 140 } });   // (hipX: pelvis D)

  // her backup dancers: two rows of block crabs, on the beat, pincers out in the hook and on the claws; in canon from the centre
  const crabs = (t, i, r) => {
    const b = t / BAR, ph = (t % beat) / beat, bb = Math.floor(t / beat) % 4;
    const hook = b >= 62 && b < 66, claws = (b >= 54 && b < 58.3) || (b >= 74.25 && b < 76) || (b >= 86 && b < 87), down = b >= 90;
    // the crabs LAND the downbeats for her (Fable): airborne between beats, squashed on the beat
    const hop = (down ? 6 * Math.max(0, 1 - (b - 90) / 2) : 16) * Math.sin(Math.PI * ph), sq = (down ? 0 : .14) * Math.max(0, 1 - ph / .22);
    const sway = (b >= 48 && b < 54) || (b >= 73 && b < 74.25) || (b >= 84 && b < 90) ? .12 * Math.sin(Math.PI * t / BAR * 2) : 0;
    const snip = (hook && bb >= 2) || claws ? Math.max(0, Math.sin(Math.PI * Math.min(1, ph / .3))) : 0;
    const walk = (b >= 54 && b < 58) || (b >= 74.25 && b < 76) ? t / beat / 2 : null;
    return { hop, sq, lean: sway, pincer: hook || claws, snip, walk, armL: hook ? .5 : 0, armR: hook ? .5 : 0,
             eyes: down && b > 91.5 ? 'closed' : snip > .5 ? 'happy' : undefined };
  };
  const ROWS = [{ xs: [370, 610, 1360, 1670], y: 800, s: .8, seed: 3, lag: .06 }, { xs: [330, 560, 1500, 1810], y: 930, s: 1.05, lag: .04 }];   // the left wing is Fable's

  let P = null;
  // MOTION.md: fix #1, the core dances (MOTIONLAB.groove on the performed channels: a real bounce, weight shifts, the chest and
  // head following the pelvis, phase-locked to the kick), and the hook's body from motion capture (the Seedance reference,
  // retargeted; keyed hands, faces and views on top), crossfaded in and out over a quarter bar
  const blend = (A, B, w) => { if (w <= 0) return A; if (w >= 1) return B; const q = { ...A };
    for (const k in B) q[k] = typeof A[k] === 'number' && typeof B[k] === 'number' ? A[k] + (B[k] - A[k]) * w : w < .5 ? A[k] : B[k]; return q; };
  const perform = () => {
    const P0 = RIG.perform(RIGS.clawd, build()); if (typeof MOTIONLAB === 'undefined') return P0;
    const P1 = MOTIONLAB.groove(P0), Pm = MOTIONLAB.groove(P0, { bounce: 0, sway: 0, curves: MOTIONLAB.mocap().curves, only: [62, 66] });
    return t => { const b = t / BAR, w = Math.max(0, Math.min(1, (b - 61.75) / .25, (66.25 - b) / .25)); return w > 0 ? blend(P1(t), Pm(t), w) : P1(t); };
  };
  const get = () => (P = P || perform());
  window.CHOREO = window.CHOREO || {};
  window.CHOREO.clawdA = { t0: 45 * BAR, dur: 48 * BAR, P: get };                       // for the harness
  // the stage (src/idolstage.js): the performers are drawn in WORLD coords through the stage's camera
  const clawdT = (t, W2S, c) => { const q = P(t), [x, y] = W2S(960 + (q.rootX || 0) * .27, 1040); return { x, y, s: .27 * c.z }; };
  const worldT = t => ({ x: 960 + (P(t).rootX || 0) * .27, y: 1040, s: .27 });
  const footWorld = tt => { const q = P(tt), r = (q.rootX || 0) * .27; return [[960 + r + (860 - 1080 + (q.footLX || 0)) * .27, 1040], [960 + r + (1285 - 1080 + (q.footRX || 0)) * .27, 1040]]; };
  LOOPS.chorus = t => {
    get();
    IDOLSTAGE.frame(t, (W2S, c) => {
      mascotTroupe(t, crabs, ROWS);
      RIGS.clawd.draw(X, t, P, clawdT(t, W2S, c));
    }, { locateHand: tt => RIGS.clawd.locate(tt, P, worldT(tt), 'hand_L'), clawdX: worldT(t).x, footWorld,
         clawdAt: (tt, W2S, c, g) => RIGS.clawd.draw(g || X, tt, P, clawdT(tt, W2S, c)) });   // (the MV layer's afterimages: her at an earlier t, into g)
  };
  LOOPS.chorus.len = 220;
  // (review) Clawd alone, full body, a fixed camera on a plain ground: for judging moves the stage camera leaves (the curtsy)
  LOOPS.clawdsolo = t => { get(); X.setTransform(1, 0, 0, 1, 0, 0); X.fillStyle = '#3a3448'; X.fillRect(0, 0, W, H);
    X.fillStyle = '#2c2838'; X.fillRect(0, 1000, W, 80); RIGS.clawd.draw(X, t, P, { x: 960 + (P(t).rootX || 0) * .27, y: 1040, s: .27 }); };
  LOOPS.clawdsolo.len = 220;
  // (review) her face, large, on a fixed camera: for judging the mouth drawings and their timing at full resolution
  LOOPS.clawdface = t => { get(); X.setTransform(1, 0, 0, 1, 0, 0); X.fillStyle = '#3a3448'; X.fillRect(0, 0, W, H);
    const o = RIGS.clawd.R.origin, s = 1.1; RIGS.clawd.draw(X, t, P, { x: 960 + (o[0] - 1065) * s, y: 560 + (o[1] - 700) * s, s }); };
  LOOPS.clawdface.len = 220;
}
