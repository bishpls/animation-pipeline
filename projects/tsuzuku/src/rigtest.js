// rigtest.js: the Clawd idol rig motion test (LOOPS.rig), built on the conventions measured from Live2D's sample rigs:
// ease-in-out keys with holds; the body leads the head by ~0.15 s; a small idle sway from incommensurate sines (the loop
// never visibly repeats); blinks of close 0.1 / hold 0.05 / open 0.15 s every 2-4 s (three drawings on twos). Big turns go
// through the drawn in-between (half turn) to the three-quarter view, one drawing each.
{
  const B = 60 / 170 * 4, b = n => n * B, f = 1 / 12, lead = .16;
  // a turn: front -> half view -> three-quarter view, each landing a touch short and settling
  // three drawings: the front head warped to its limit (a true half step), the drawn half view, the three-quarter view
  const turn = (t, half, full, sgn) => [[t, { view: 'F', angleX: .9 * sgn }], [t + 2 * f, { view: half, angleX: 0 }], [t + 4 * f, { view: full, angleX: -.1 * sgn }], [t + 6 * f, { angleX: 0 }]];
  const back = (t, half, sgn) => [[t, { view: half, angleX: 0 }], [t + 2 * f, { view: 'F', angleX: .9 * sgn }], [t + 4 * f, { angleX: -.1 * sgn }], [t + 6 * f, { angleX: 0 }]];
  const head = RIG.keys([
    [0, { view: 'F', angleX: 0, angleY: 0, angleZ: 0 }],
    ...turn(b(.75), 'HL', 'L', -1), [b(.75), { angleZ: -4 }],                   // she looks to our left
    ...back(b(1.75), 'HL', -1), [b(1.75), { angleZ: 0 }],                         // back to camera
    [b(2.5), { angleX: .35, angleY: .5, angleZ: 4 }],                             // a look up and across, front head
    [b(3.25), { angleX: 0, angleY: 0, angleZ: 8 }],                               // the cute tilt, held
    ...turn(b(4.25), 'HR', 'R', 1), [b(4.25), { angleZ: 3 }],                    // she looks to our right
    [b(5), { angleY: -.6 }], [b(5.25), { angleY: 0 }],                            // a nod in the three-quarter view
    ...back(b(6), 'HR', 1), [b(6), { angleZ: 0 }],
    [b(6.75), { angleX: -.4, angleY: -.3 }], [b(7.5), { angleX: 0, angleY: 0 }],  // a small glance down-left, front head
  ], { twos: true, move: .2 });
  const body = RIG.keys([                                                          // the body leads the head
    [0, { bodyZ: 0, bodyX: 0, armL: 3, armR: 3 }],
    [b(.75) - lead, { bodyZ: -1.5, bodyX: -.3 }], [b(1.75) - lead, { bodyZ: 0, bodyX: 0 }],
    [b(2.5) - lead, { armR: 8 }], [b(3.25) - lead, { armR: 3 }],
    [b(4.25) - lead, { bodyZ: 1.5, bodyX: .3 }], [b(6) - lead, { bodyZ: 0, bodyX: 0, armL: 8 }], [b(7) - lead, { armL: 3 }],
  ], { twos: true, move: .3, anticipate: .05 });
  // seeded blinks
  const blinks = []; { let s = 7, t = 1.1; const rnd = () => (s = (s * 16807) % 2147483647) / 2147483647; while (t < 12) { blinks.push(t); t += 2 + 2 * rnd(); } }
  const blinkAt = q => { for (const t0 of blinks) { const d = q - t0; if (d >= 0 && d < 3 * f) return d < f ? 'half' : d < 2 * f ? 'closed' : 'half'; } return null; };
  // lip-sync: chorus-1 words from assets/words.json, replayed from bar 2 of the loop; vowels -> drawn mouths
  const VOW = w => { const v = (w.toLowerCase().match(/[aeiouy]/) || ['e'])[0]; return { a: 'A', e: 'E', i: 'I', o: 'O', u: 'U', y: 'I' }[v]; };
  const lip = tt => {
    const W = (window.WORDS || []).filter(w => w.who === 'clawd'), off = 65.12 - b(2);
    for (const w of W) { const a = w.t0 - off, z = w.t1 - off; if (tt >= a - .04 && tt < z - .02) return VOW(w.w); }
    return null;
  };
  const S = Math.sin, TAU = Math.PI * 2;
  LOOPS.rig = t => {
    const g = X.createLinearGradient(0, 0, 0, H); g.addColorStop(0, '#2a2440'); g.addColorStop(1, '#141220'); X.fillStyle = window.DEBUG_BG || g; X.fillRect(0, 0, W, H);
    const P = tt => {
      const p = { ...head(tt), ...body(tt) }, q = Math.floor(tt * 12) / 12;
      p.angleX += .07 * S(TAU * tt / 6.53); p.angleY += .06 * S(TAU * tt / 3.53); p.angleZ += 1.5 * S(TAU * tt / 5.53);   // idle sway
      p.bodyX += .12 * S(TAU * tt / 15.5); p.breath = .5 + .5 * S(TAU * tt / 3.23);
      p.eyes = q >= 3.9 && q < 5.0 ? 'happy' : blinkAt(q);
      if (q >= 5.35 && q < 5.65) p.eyeR = 'closed';                               // a wink
      p.mouth = q >= 3.9 && q < 5.0 ? 'grin' : lip(q);
      const bp = (tt % B) / B; p.bounce = -5 * Math.max(0, Math.sin(Math.PI * Math.min(1, bp / .18)));
      return p;
    };
    const PP = RIG.perform(RIGS.clawd, P);                                     // the body follows the head (measured ratios, leads 60 ms)
    RIGS.clawd.draw(X, t, PP, { x: 560, y: 1060, s: .27 });
    RIGS.clawd.draw(X, t, PP, { x: 1400, y: 1060 + (3700 - 560) * 1.15 - 700, s: 1.15 });
  };
  LOOPS.rig.len = b(8);
}
// the same test on magenta: tools/holes.py finds enclosed background (holes) frame by frame
LOOPS.rigmag = t => { window.DEBUG_BG = '#ff00ff'; LOOPS.rig(t); window.DEBUG_BG = null; };
LOOPS.rigmag.len = LOOPS.rig.len;
// (debug) the same frame four times, each with one layer set hidden: LOOPS.hidetest
LOOPS.hidetest = t => {
  const sets = [[], ['hair_back'], ['hair_side_L'], ['hair_side_R']], k = Math.min(3, Math.floor(t));
  window.RIG_HIDE = sets[k]; window.DEBUG_BG = '#ff00ff'; LOOPS.rig(201 / 24); window.RIG_HIDE = null; window.DEBUG_BG = null;
};
LOOPS.hidetest.len = 4;
// (debug) Clawd at any song time of world A (the chorus choreography): left on magenta, right as the ID pass (each layer a flat
// colour, its invented pixels at half brightness). LOOPS.clawdat (head), clawdatmid (waist up), clawdatfull; t = song seconds
{
  const at = T => t => {
    const P = window.CHOREO.clawdA.P();
    X.fillStyle = '#ff00ff'; X.fillRect(0, 0, W / 2, H); X.fillStyle = '#000'; X.fillRect(W / 2, 0, W / 2, H);
    X.save(); X.beginPath(); X.rect(0, 0, W / 2, H); X.clip(); RIGS.clawd.draw(X, t, P, T(480)); X.restore();
    X.save(); X.beginPath(); X.rect(W / 2, 0, W / 2, H); X.clip(); window.RIG_IDPASS = true; RIGS.clawd.draw(X, t, P, T(1440)); window.RIG_IDPASS = false; X.restore();
  };
  LOOPS.clawdat = at(x => ({ x, y: 540 + (3700 - 620) * 1.05, s: 1.05 }));
  LOOPS.clawdatmid = at(x => ({ x, y: 540 + (3700 - 1250) * .5, s: .5 }));
  LOOPS.clawdatfull = at(x => ({ x, y: 1060, s: .27 }));
  LOOPS.clawdat.len = LOOPS.clawdatmid.len = LOOPS.clawdatfull.len = 220;
}
