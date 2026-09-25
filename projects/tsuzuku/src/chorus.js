// chorus.js: the first dance test on the song clock (LOOPS.chorus, song time). Chorus 1, bars 46-62, composed from the move
// vocabulary (engine/moves.js); lip-sync from assets/words.json (crowd calls silent), seeded blinks, body coupling from
// RIG.perform. Render with the song: node engine/render.mjs projects/tsuzuku --loop=chorus --clip=63.5:88.5
{
  const BAR = 60 / 170 * 4, C0 = 46 * BAR;
  let P = null;
  const build = () => MOVES.choreo({ bpm: 170, t0: C0 }, {
    legs: [[-1, 'bounce', { amp: 6 }], [0, 'bounce'], [2, 'sway'], [4, 'bounce'], [6, 'sway'], [8, 'stepTouch'], [12, 'sway', { every: 1, amp: 1 }], [15.5, 'bounce', { amp: 4 }]],
    arms: [[-1, 'idle'], [0, 'reach', { side: 1 }], [1, 'armPump'], [2, 'handToEar', { side: -1 }], [4, 'reach', { side: -1 }], [5, 'armPump', { side: -1 }],
           [6, 'handToEar', { side: 1 }], [8, 'claws', { snip: 0 }], [10, 'armPump'], [11.75, 'claws'], [12.75, 'armPump'], [15, 'armsOut']],
    head: [[-1, 'look', { view: 'F' }], [0, 'headBob'], [2, 'look', { view: 'HR', z: -4 }], [3, 'headBob', { amp: .25 }], [4, 'headTilt'],
           [6, 'look', { view: 'HL', z: 4 }], [7, 'headBob'], [8, 'headTilt', { every: 1, amp: 8 }], [12, 'headBob', { amp: .45 }], [15, 'look', { view: 'F', y: -.2 }]],
  }, { lips: MOVES.lips(window.WORDS, 'clawd'), blinks: MOVES.blinks(11, 50, 100) });
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
