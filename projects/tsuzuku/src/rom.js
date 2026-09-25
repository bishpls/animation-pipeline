// rom.js: the range-of-motion test (LOOPS.rom, .rommag, .romid). A matrix of short segments, each exercising one thing:
// every view at rest, every control swept alone both ways, the common combinations, fast whips (springs), tilts and nods
// inside every drawn view, every view switch both ways, faces per view. tools/romcheck.py checks every frame.
// window.ROM lists the segments ([name, t0, t1]) for the checker.
{
  const segs = [], S = Math.sin, PI = Math.PI;
  const add = (name, dur, fn) => segs.push({ name, dur, fn });
  const sweep = u => S(2 * PI * u);                     // 0 -> +1 -> 0 -> -1 -> 0
  const VIEWS = ['F', 'HL', 'L', 'HR', 'R'];
  for (const v of VIEWS) add(`rest ${v}`, .5, () => ({ view: v }));
  // controls alone (front head), both directions
  add('angleX F', 2, u => ({ angleX: sweep(u) }));
  add('angleY F', 2, u => ({ angleY: sweep(u) }));
  add('angleZ F', 2, u => ({ angleZ: 14 * sweep(u) }));
  add('bodyZ', 2, u => ({ bodyZ: 7 * sweep(u) }));
  add('bodyX', 2, u => ({ bodyX: sweep(u) }));
  add('breath+bounce', 2, u => ({ breath: .5 + .5 * sweep(u), bounce: -18 * Math.abs(S(4 * PI * u)) }));
  // combinations
  add('X+Z', 2, u => ({ angleX: sweep(u), angleZ: 12 * sweep(u) }));
  add('X-Z', 2, u => ({ angleX: sweep(u), angleZ: -12 * sweep(u) }));
  add('X+Y', 2, u => ({ angleX: sweep(u), angleY: .7 * S(4 * PI * u) }));
  add('Z+bodyZ', 2, u => ({ angleZ: 12 * sweep(u), bodyZ: 6 * sweep(u) }));
  // fast whips (springs): a snap each way, then settle
  add('whip X', 2, u => ({ angleX: u < .08 ? 0 : u < .5 ? 1 : -1 }));
  add('whip bodyZ', 2, u => ({ bodyZ: u < .08 ? 0 : u < .5 ? 7 : -7 }));
  // inside each drawn view: tilt, nod, small turn
  for (const v of VIEWS.slice(1)) {
    add(`tilt ${v}`, 1.5, u => ({ view: v, angleZ: 12 * sweep(u) }));
    add(`nod ${v}`, 1.5, u => ({ view: v, angleY: .8 * sweep(u) }));
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
  let t = 0; window.ROM = segs.map(s => { const r = [s.name, +t.toFixed(3), +(t + s.dur).toFixed(3)]; s.t0 = t; t += s.dur; return r; });
  const len = t, B = 60 / 170 * 4;
  const P = tt => { const s = segs.find(g => tt >= g.t0 && tt < g.t0 + g.dur) || segs[segs.length - 1];
    return { view: 'F', breath: .5, ...s.fn(Math.min(1, (tt - s.t0) / s.dur)) }; };
  const draw = (bg, id) => t => {
    X.fillStyle = bg; X.fillRect(0, 0, W, H);
    window.RIG_IDPASS = id; RIGS.clawd.draw(X, t, P, { x: 960, y: 540 + (3700 - 620) * 1.05, s: 1.05 }); window.RIG_IDPASS = false;   // head + chest, large
  };
  LOOPS.rom = draw('#201d33', false); LOOPS.rommag = draw('#ff00ff', false); LOOPS.romid = draw('#000000', true);
  LOOPS.rom.len = LOOPS.rommag.len = LOOPS.romid.len = len;
}
