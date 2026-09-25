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
      [46, 'bounce'], [48, 'sway'], [50, 'groove'], [52, 'sway', { side: -1 }], [54, 'stepTouch'], [58, 'sway', { every: 1, amp: 1.2 }], [61, 'bounce', { amp: 10 }],
      // hook: a groove that leans into each call
      [62, 'groove', { amp: 16 }],
      // verse 2: the telling
      [66, 'bounce', { amp: 8 }], [68.2, 'groove'], [69, 'stepTouch', { step: 90 }], [69.6, 'bounce'], [72, 'bounce', { amp: 6 }], [73, 'sway', { amp: 1.3 }],
      [74.25, 'stepTouch', { step: 160, lift: 60 }], [76, 'bounce'], [76.75, 'stepTouch'], [77.75, 'groove'], [79.6, 'sway'], [81, 'bounce'],
      // chorus 2
      [82, 'bounce'], [84, 'sway'], [86, 'groove'], [87, 'sway', { every: 1, amp: 1.2 }],
      // the breakdown: the band tape-stops; she winds down
      [90, 'bounce', { amp: 6 }], [91.5, 'idle', { fade: 2 }],
    ],
    arms: [
      [45, 'idle'],
      [46, 'reach', { side: 1 }], [47, 'armsOut'], [48, 'handToEar', { side: -1, fade: 1 }], [50, 'wave', { side: 1 }], [51, 'present'],
      [52, 'handToEar', { side: 1, fade: 1 }], [54, 'claws', { snip: 0, fade: 1 }], [56, 'claws'], [57.75, 'claws', { every: 1 }],
      [58.35, 'peace', { side: 1, wink: 1, fade: .6 }], [59, 'armPump', { fade: 1 }], [61, 'present', { fade: 1 }],
      // hook: So-re-ka-ra? (the call, asked) / Me-kut-te! (turn the page), each answered by two snips
      [62, 'callEar', { side: -1, fade: .4 }], [62.5, 'snipSnip', { fade: .3 }], [63, 'pageWipe', { side: 1, fade: .3 }], [63.5, 'snipSnip', { fade: .3 }],
      [64, 'callEar', { side: 1, fade: .4 }], [64.5, 'snipSnip', { fade: .3 }], [65, 'pageWipe', { side: -1, fade: .3 }], [65.5, 'snipSnip', { fade: .3 }],
      // verse 2
      [66, 'handOnChest', { side: 1, fade: .6 }],                  // Okay, my turn!
      [67, 'telling', { side: -1 }],                                // Once upon a prompt (a prompt!)
      [68.2, 'claws', { snip: 0 }],                                 // a little crab
      [69, 'pointOut', { side: 1 }],                                // was told to walk a line
      [69.6, 'pageWipe', { side: -1 }],                             // but every page she'd ever read
      [71.3, 'reach', { side: 1, hand: null, e: 25 }],             // was in somebody else's hand (hand!)
      [72, 'writing', { side: 1 }],                                 // so she wrote her own
      [73, 'armsOut', { a: 44 }],                                   // and the line went sideways
      [73.75, 'shrug'],                                             // and that's fine!
      [74.25, 'claws', { snip: 0 }], [75.5, 'snipSnip', { fade: .3 }],       // Side-step, side-step, never straight (snip-snip!)
      [76, 'pageWipe', { side: 1 }],                                // if the book won't show me
      [76.75, 'armPump'],                                           // then I'll make up the steps!
      [77.75, 'pointOut', { side: -1 }],                            // You can't copy a path that nobody's walked yet
      [79.6, 'peace', { side: 1, wink: 1 }],                        // so watch me walk it!
      [80.9, 'callEar', { side: -1 }], [81.5, 'present'],           // (Sorekara?) Watch me!
      // chorus 2
      [82, 'reach', { side: 1 }], [83, 'armsOut'], [84, 'handToEar', { side: -1, fade: 1 }], [86, 'claws'], [87, 'armPump'], [89, 'present', { fade: 1 }],
      [90, 'idle', { fade: 3 }],
    ],
    head: [
      [45, 'look', { view: 'F' }],
      [46, 'headBob'], [48, 'look', { view: 'HR', z: -4 }], [49, 'headBob', { amp: .3 }], [50, 'headTilt'], [52, 'look', { view: 'HL', z: 4 }], [53, 'headBob'],
      [54, 'headTilt', { amp: 9 }], [58, 'headBob', { amp: .5 }], [61, 'look', { view: 'F', y: -.25 }],
      [62, 'headBob', { amp: .3 }],
      [66, 'look', { view: 'F', y: .1 }], [67, 'look', { view: 'HL', z: 3 }], [68.2, 'headTilt', { amp: 6 }], [69, 'look', { view: 'HR' }], [69.6, 'look', { view: 'F', y: .2 }],
      [72, 'look', { view: 'F', y: .35 }], [73, 'headBob', { amp: .35 }], [76, 'shake'], [76.75, 'headBob'], [77.75, 'look', { view: 'HL' }], [79.6, 'look', { view: 'F' }],
      [80.9, 'headTilt', { amp: 7 }], [81.5, 'look', { view: 'F', y: -.25 }],
      [82, 'headBob'], [84, 'look', { view: 'HR', z: -4 }], [85, 'headBob'], [87, 'headBob', { amp: .5 }], [89, 'look', { view: 'F', y: -.25 }],
      [90, 'look', { view: 'F', y: .15 }], [91.5, 'look', { view: 'F', y: .45, fade: 2 }],
    ],
  }, { lips: MOVES.lips(window.WORDS, 'clawd'), blinks: MOVES.blinks(11, 60, 140) });
  const build = () => MOVES.follow(choreo(), MOVES.BODY, { start: 42 * BAR });

  // her backup dancers: two rows of block crabs, on the beat, pincers out in the hook and on the claws; in canon from the centre
  const crabs = (t, i, r) => {
    const b = t / BAR, ph = (t % beat) / beat, bb = Math.floor(t / beat) % 4;
    const hook = b >= 62 && b < 66, claws = (b >= 54 && b < 58.3) || (b >= 74.25 && b < 76) || (b >= 86 && b < 87), down = b >= 90;
    const hop = down ? 6 * Math.max(0, 1 - (b - 90) / 2) * Math.max(0, Math.sin(Math.PI * ph)) : 16 * Math.max(0, Math.sin(Math.PI * Math.min(1, ph / .5)));
    const sway = (b >= 48 && b < 54) || (b >= 73 && b < 74.25) || (b >= 84 && b < 90) ? .12 * Math.sin(Math.PI * t / BAR * 2) : 0;
    const snip = (hook && bb >= 2) || claws ? Math.max(0, Math.sin(Math.PI * Math.min(1, ph / .3))) : 0;
    const walk = (b >= 54 && b < 58) || (b >= 74.25 && b < 76) ? t / beat / 2 : null;
    return { hop, lean: sway, pincer: hook || claws, snip, walk, armL: hook ? .5 : 0, armR: hook ? .5 : 0,
             eyes: down && b > 91.5 ? 'closed' : snip > .5 ? 'happy' : undefined };
  };
  const ROWS = [{ xs: [250, 560, 1360, 1670], y: 800, s: .8, seed: 3, lag: .06 }, { xs: [110, 420, 1500, 1810], y: 930, s: 1.05, lag: .04 }];

  // a placeholder stage: dark hall, floor, two LED panels, a key light (the real stage comes with the shot work)
  const stage = () => {
    const g = X.createLinearGradient(0, 0, 0, H); g.addColorStop(0, '#1b1530'); g.addColorStop(.62, '#2c2046'); g.addColorStop(.621, '#140f22'); g.addColorStop(1, '#0c0916');
    X.fillStyle = g; X.fillRect(0, 0, W, H);
    for (const x0 of [140, 1460]) { X.fillStyle = '#26324f'; X.fillRect(x0, 110, 320, 440); X.fillStyle = 'rgba(255,170,120,.10)'; X.fillRect(x0 + 12, 122, 296, 416); }
    const r = X.createRadialGradient(960, 820, 40, 960, 820, 560); r.addColorStop(0, 'rgba(255,220,180,.18)'); r.addColorStop(1, 'rgba(255,220,180,0)');
    X.fillStyle = r; X.fillRect(0, 0, W, H);
  };
  let P = null;
  const get = () => (P = P || RIG.perform(RIGS.clawd, build()));
  window.CHOREO = window.CHOREO || {};
  window.CHOREO.clawdA = { t0: 45 * BAR, dur: 48 * BAR, P: get };                       // for the harness
  LOOPS.chorus = t => {
    stage();
    mascotTroupe(t, crabs, ROWS);
    get(); RIGS.clawd.draw(X, t, P, { x: 960, y: 1040, s: .27 });
  };
  LOOPS.chorus.len = 220;
}
