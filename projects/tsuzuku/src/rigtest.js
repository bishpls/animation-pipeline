// rigtest.js: the Clawd idol rig motion test (LOOPS.rig). An 8-bar phrase of held poses on the beat, the way anime acts:
// hold, wind up, move, overshoot, settle, hold. Poses on twos; physics on ones. Big turns snap to the drawn three-quarter
// heads (views L and R) in two drawings: the front head winds toward the turn, then the drawn view lands slightly short
// of its angle and settles.
{
  const B = 60 / 170 * 4, b = n => n * B, f = 1 / 12;
  const turn = (t, v, sgn) => [[t, { angleX: .22 * sgn }], [t + 2 * f, { view: v, angleX: -.14 * sgn }], [t + 4 * f, { angleX: 0 }]];
  const back = (t, sgn) => [[t, { angleX: -.1 * sgn }], [t + 2 * f, { view: 'F', angleX: .18 * sgn }], [t + 4 * f, { angleX: 0 }]];
  const pose = RIG.keys([
    [0, { view: 'F', angleX: 0, angleY: 0, angleZ: 0, bodyZ: 0, armL: 3, armR: 3 }],
    ...turn(b(.75), 'L', -1), [b(.75), { angleZ: -4, bodyZ: -1.5 }],          // she looks to our left
    ...back(b(1.75), -1), [b(1.75), { angleZ: 0, bodyZ: 0 }],                  // back to camera
    [b(2.5), { angleY: -.22, angleZ: 5, armR: 8 }],                            // a small look up, front head
    [b(3.25), { angleY: 0, angleZ: 9, armR: 3 }],                              // the cute tilt, held
    ...turn(b(4.25), 'R', 1), [b(4.25), { angleZ: 3, bodyZ: 1.5 }],           // she looks to our right
    [b(5), { angleY: .25 }], [b(5.25), { angleY: 0 }],                         // a nod in the three-quarter view
    ...back(b(6), 1), [b(6), { angleZ: 0, bodyZ: 0, armL: 8 }],
    [b(7), { armL: 3 }],
  ], { twos: true, move: .17 });
  // lip-sync: the chorus-1 words from assets/words.json, replayed from bar 2 of the loop; vowels -> drawn mouths
  const VOW = w => { const v = (w.toLowerCase().match(/[aeiouy]/) || ['e'])[0]; return { a: 'A', e: 'E', i: 'I', o: 'O', u: 'U', y: 'I' }[v]; };
  const lip = tt => {
    const W = (window.WORDS || []).filter(w => w.who === 'clawd'), off = 65.12 - b(2);   // "To be continued!" at loop bar 2
    for (const w of W) { const a = w.t0 - off, z = w.t1 - off; if (tt >= a - .04 && tt < z - .02) return VOW(w.w); }
    return null;
  };
  LOOPS.rig = t => {
    const g = X.createLinearGradient(0, 0, 0, H); g.addColorStop(0, '#2a2440'); g.addColorStop(1, '#141220'); X.fillStyle = g; X.fillRect(0, 0, W, H);
    const P = tt => {
      const p = pose(tt), bp = (tt % B) / B;
      const q = Math.floor(tt * 12) / 12;                                          // the face on twos too
      for (const [t0, e] of [[.45, 'half'], [.52, 'closed'], [.6, 'half'], [2.9, 'closed'], [2.97, 'half'], [3.9, 'happy'], [8.4, 'half'], [8.47, 'closed'], [8.55, 'half']])
        if (q >= t0 && q < t0 + (e === 'happy' ? 1.1 : .08)) p.eyes = e;
      if (q >= 5.3 && q < 5.6) p.eyeR = 'closed';                                  // a wink
      p.mouth = q >= 3.9 && q < 5.0 ? 'grin' : lip(q);
      p.bounce = -6 * Math.max(0, Math.sin(Math.PI * Math.min(1, bp / .18)));    // a small lift on each bar's downbeat
      return p;
    };
    RIGS.clawd.draw(X, t, P, { x: 560, y: 1060, s: .27 });
    RIGS.clawd.draw(X, t, P, { x: 1400, y: 1060 + (3700 - 560) * 1.15 - 700, s: 1.15 });
  };
  LOOPS.rig.len = b(8);
}
