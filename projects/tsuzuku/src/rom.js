// rom.js: the range-of-motion test (LOOPS.rom, .rommag, .romid). A matrix of short segments, each exercising one thing:
// every view at rest, every control swept alone both ways, the common combinations, fast whips (springs), tilts and nods
// inside every drawn view, every view switch both ways, faces per view. tools/romcheck.py checks every frame.
// window.ROM lists the segments ([name, t0, t1]) for the checker.
{
  const segs = [], S = Math.sin, PI = Math.PI;
  // PERFORMANCE range (what choreography uses; docs/research §4): head tilt +-10 deg, body tilt +-5 deg, front-head turn +-0.5
  // (+-15 deg: beyond that the drawn half and three-quarter views take over), nod +-0.8. ?stress (window.ROM_STRESS) runs the
  // old extremes instead.
  const K = window.ROM_STRESS || /stress/.test(location.search) ? { x: 1, z: 14, bz: 7, y: 1 } : { x: .5, z: 10, bz: 5, y: .8 };
  const add = (name, dur, fn) => segs.push({ name, dur, fn });
  const sweep = u => S(2 * PI * u);                     // 0 -> +1 -> 0 -> -1 -> 0
  const VIEWS = ['F', 'HL', 'L', 'HR', 'R'];
  for (const v of VIEWS) add(`rest ${v}`, 1.5, () => ({ view: v }));          // long enough for the springs to settle after a switch (baselines at the end)
  // controls alone (front head), both directions
  add('angleX F', 2, u => ({ angleX: K.x * sweep(u) }));
  add('angleY F', 2, u => ({ angleY: K.y * sweep(u) }));
  add('angleZ F', 2, u => ({ angleZ: K.z * sweep(u) }));
  add('bodyZ', 2, u => ({ bodyZ: K.bz * sweep(u) }));
  add('bodyX', 2, u => ({ bodyX: sweep(u) }));
  add('breath+bounce', 2, u => ({ breath: .5 + .5 * sweep(u), bounce: -18 * Math.abs(S(4 * PI * u)) }));
  // combinations
  add('X+Z', 2, u => ({ angleX: K.x * sweep(u), angleZ: K.z * sweep(u) }));
  add('X-Z', 2, u => ({ angleX: K.x * sweep(u), angleZ: -K.z * sweep(u) }));
  add('X+Y', 2, u => ({ angleX: K.x * sweep(u), angleY: K.y * .8 * S(4 * PI * u) }));
  add('Z+bodyZ', 2, u => ({ angleZ: K.z * sweep(u), bodyZ: K.bz * sweep(u) }));
  // the hips (full-body framing): sway alone, sway with the beat dip, a whip, and sway under a head turn; contrapposto from perform
  add('rest full', 1.5, () => ({ full: 1 }));
  add('hipX', 2, u => ({ hipX: sweep(u), full: 1 }));
  add('hip sway', 3, u => ({ hipX: Math.sign(S(3 * PI * u)) * Math.min(1, Math.abs(S(3 * PI * u)) * 3), hipY: 10 * Math.abs(S(12 * PI * u)), full: 1 }));
  add('hip whip', 2, u => ({ hipX: u < .08 ? 0 : u < .5 ? 1 : -1, full: 1 }));
  add('hip+turn', 2, u => ({ hipX: sweep(u), angleX: .4 * sweep(u + .25), full: 1 }));
  // fast whips (springs): a snap each way, then settle
  add('whip X', 2, u => ({ angleX: u < .08 ? 0 : u < .5 ? K.x : -K.x }));
  add('whip bodyZ', 2, u => ({ bodyZ: u < .08 ? 0 : u < .5 ? K.bz : -K.bz }));
  // inside each drawn view: tilt, nod, small turn
  for (const v of VIEWS.slice(1)) {
    add(`tilt ${v}`, 1.5, u => ({ view: v, angleZ: K.z * sweep(u) }));
    add(`nod ${v}`, 1.5, u => ({ view: v, angleY: K.y * sweep(u) }));
    add(`turn ${v}`, 1.5, u => ({ view: v, angleX: .3 * sweep(u) }));
  }
  // every view switch both ways, at anime speed (two drawings each), held between
  const chain = (name, list) => add(name, list.length * .5, u => ({ view: list[Math.min(list.length - 1, Math.floor(u * list.length))] }));
  chain('switch left', ['F', 'HL', 'L', 'HL', 'F', 'L', 'F']);
  chain('switch right', ['F', 'HR', 'R', 'HR', 'F', 'R', 'F']);
  chain('switch across', ['L', 'R', 'HL', 'HR', 'L', 'F']);
  // faces per view
  for (const v of VIEWS) add(`face ${v}`, 2, u => { const k = Math.floor(u * 8);
    return { view: v, eyes: [null, 'half', 'closed', 'happy', null, null, null, null][k], mouth: [null, null, null, null, 'A', 'I', 'O', 'grin'][k] }; });
  let t = 0; window.ROM = segs.map(s => { const r = [s.name, +t.toFixed(3), +(t + s.dur).toFixed(3), s.fn(.5).full ? 'full' : 'head']; s.t0 = t; t += s.dur; return r; });
  const len = t, B = 60 / 170 * 4;
  const P = tt => { const s = tt < 0 ? segs[0] : segs.find(g => tt >= g.t0 && tt < g.t0 + g.dur) || segs[segs.length - 1];   // warm-up: the first pose
    return { view: 'F', breath: .5, ...s.fn(Math.min(1, (tt - s.t0) / s.dur)) }; };
  let PP = null;                                                     // contrapposto and a level head for the hip segments (built on
                                                                     // first draw: the rig loads after this script)
  const draw = (bg, id) => t => {
    X.fillStyle = bg; X.fillRect(0, 0, W, H);
    const full = P(t).full; PP = PP || RIG.perform(RIGS.clawd, P, { lead: 0 });
    window.RIG_IDPASS = id;
    if (full) RIGS.clawd.draw(X, t, PP, { x: 960, y: 1060, s: .27 });                           // full body
    else RIGS.clawd.draw(X, t, P, { x: 960, y: 540 + (3700 - 620) * 1.05, s: 1.05 });           // head + chest, large
    window.RIG_IDPASS = false;
  };
  LOOPS.rom = draw('#201d33', false); LOOPS.rommag = draw('#ff00ff', false); LOOPS.romid = draw('#000000', true);
  LOOPS.rom.len = LOOPS.rommag.len = LOOPS.romid.len = len;
}
