// chorus.js: the first dance test on the song clock (LOOPS.chorus, song time). Chorus 1, bars 46-62, composed from the move
// vocabulary (engine/moves.js); lip-sync from assets/words.json (crowd calls silent), seeded blinks, body coupling from
// RIG.perform. Render with the song: node engine/render.mjs projects/tsuzuku --loop=chorus --clip=63.5:88.5
{
  const BAR = 60 / 170 * 4, C0 = 46 * BAR;
  let P = null;
  // v2: bigger moves, arms phrased on the half bar, every arm/hip/lean target followed through springs (MOVES.follow)
  const choreo = () => MOVES.choreo({ bpm: 170, t0: C0 }, {
    legs: [[-1, 'groove', { amp: 8 }], [0, 'bounce'], [2, 'sway'], [4, 'groove'], [6, 'sway', { side: -1 }], [8, 'stepTouch'],
           [12, 'sway', { every: 1, amp: 1.2 }], [15, 'bounce', { amp: 10 }]],
    arms: [[-1, 'idle'], [0, 'reach', { side: 1 }], [1, 'armsOut'], [2, 'handToEar', { side: -1, fade: 1 }], [4, 'wave', { side: 1 }], [5, 'present'],
           [6, 'handToEar', { side: 1, fade: 1 }], [8, 'claws', { snip: 0, fade: 1 }], [10, 'claws'], [11.75, 'claws', { every: 1 }],
           [12.5, 'armPump', { fade: 1 }], [15, 'present', { fade: 1 }]],
    head: [[-1, 'look', { view: 'F' }], [0, 'headBob'], [2, 'look', { view: 'HR', z: -4 }], [3, 'headBob', { amp: .3 }], [4, 'headTilt'],
           [6, 'look', { view: 'HL', z: 4 }], [7, 'headBob'], [8, 'headTilt', { amp: 9 }], [12, 'headBob', { amp: .5 }], [15, 'look', { view: 'F', y: -.25 }]],
  }, { lips: MOVES.lips(window.WORDS, 'clawd'), blinks: MOVES.blinks(11, 50, 100) });
  const build = () => MOVES.follow(choreo(), MOVES.BODY, { start: C0 - 3 * BAR });
  // a placeholder stage: dark hall, floor, two LED panels, a key light
  const stage = () => {
    const g = X.createLinearGradient(0, 0, 0, H); g.addColorStop(0, '#1b1530'); g.addColorStop(.72, '#2c2046'); g.addColorStop(.721, '#140f22'); g.addColorStop(1, '#0c0916');
    X.fillStyle = g; X.fillRect(0, 0, W, H);
    for (const x0 of [140, 1460]) { X.fillStyle = '#26324f'; X.fillRect(x0, 150, 320, 520); X.fillStyle = 'rgba(255,170,120,.10)'; X.fillRect(x0 + 12, 162, 296, 496); }
    const r = X.createRadialGradient(960, 820, 40, 960, 820, 520); r.addColorStop(0, 'rgba(255,220,180,.18)'); r.addColorStop(1, 'rgba(255,220,180,0)');
    X.fillStyle = r; X.fillRect(0, 0, W, H);
  };
  window.CHOREO = window.CHOREO || {}; window.CHOREO.chorus1 = { t0: C0 - BAR, dur: 18 * BAR, P: () => (window._ch1 = window._ch1 || build()) };   // for the harness
  LOOPS.chorus = t => {
    stage();
    P = P || RIG.perform(RIGS.clawd, build());
    RIGS.clawd.draw(X, t, P, { x: 960, y: 1040, s: .27 });
  };
  LOOPS.chorus.len = 220;
}
