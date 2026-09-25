// engine/moves.js: a dance move vocabulary and a choreography compiler for rigs (engine/rig.js parameter names).
//
//   const P = MOVES.choreo({ bpm: 170, beatsPerBar: 4, t0: 64.94 }, {
//     legs: [[0, 'bounce'], [4, 'sway', { every: 2 }], [8, 'stepTouch']],        // [bar, move, options]
//     arms: [[0, 'reach', { side: 1 }], [2, 'handToEar', { side: -1 }]],
//     head: [[0, 'headBob'], [6, 'look', { view: 'HR' }]],
//   }, { lips: MOVES.lips(WORDS, 'clawd'), blinks: MOVES.blinks(7) });
//   rig.draw(X, t, RIG.perform(rig, P), T)
//
// A move is (b, o) -> params, b = beats since the move began. Within a channel, a new move crossfades from the previous one
// over o.fade beats (default .5); channels add. Strings (view, eyes, mouth) take the latest writer. Everything is a pure
// function of t. Sides: +1 = the character's left (image right), matching rig.js's armL/armR signs.
const MOVES = (() => {
  const S = Math.sin, PI = Math.PI, clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const ease = u => (u = clamp(u, 0, 1), u * u * (3 - 2 * u));
  const pulse = (ph, w = .35) => Math.max(0, S(PI * Math.min(1, ph / w)));      // a quick hit on the beat, then rest
  const snap = (ph, w = .25) => ease(ph / w);                                     // a quick move, then hold
  const alt = (b, every = 1) => (Math.floor(b / every) % 2 ? -1 : 1);            // +1, -1, +1 ... per period
  const arm = (side, a, e) => side > 0 ? { armR: a, elbowR: e } : { armL: a, elbowL: e };

  // Moves set TARGETS (MOVES.follow turns them into physical motion). Legs keep the beat; arms phrase on the half bar.
  const M = {
    idle: () => ({}),
    // legs and body
    bounce: (b, o) => ({ hipY: (o.amp ?? 16) * pulse(b % 1, .5) }),                                  // knees dip on the beat
    groove: (b, o) => { const side = alt(b, 2) * (o.side ?? 1);                                   // lean over each 2 beats, dip each beat
      return { hipY: (o.amp ?? 14) * pulse(b % 1, .5), bodyZ: 2.5 * side, hipX: .35 * side, angleZ: -1.5 * side }; },
    sway: (b, o) => {                                                          // the hips cross on each period and hold
      const ev = o.every ?? 2, ph = (b % ev) / ev, side = alt(b, ev) * (o.side ?? 1), amp = o.amp ?? 1.1;
      return { hipX: amp * (-side + 2 * side * snap(ph, .35)), hipY: (o.dip ?? 12) * pulse(b % 1, .5) };
    },
    stepTouch: (b, o) => {                                                     // step out and touch in, alternating feet
      const ev = o.every ?? 2, k = Math.floor(b / ev), ph = (b % ev) / ev, side = (k % 2 ? -1 : 1) * (o.side ?? 1);
      const out = S(PI * ph), step = (o.step ?? 120) * out, lift = (o.lift ?? 45) * Math.max(0, S(2 * PI * ph));
      const f = side > 0 ? { footRX: step, footRY: lift } : { footLX: -step, footLY: lift };
      return { ...f, hipX: 1.1 * side * out, bodyZ: 2 * side * out, hipY: (o.dip ?? 14) * pulse(b % 1, .5) };
    },
    // arms (side: +1 the character's left = image right); half-bar phrasing
    armPump: (b, o) => { const ev = o.every ?? 2, u = pulse((b % ev) / ev, .5), s2 = alt(b, ev) * (o.side ?? 1);
      return { ...arm(s2, 15 + 25 * u, 45 + 65 * u), ...arm(-s2, 12, 45), bodyZ: 1.5 * s2 * u, bodyX: .25 * s2 * u }; },
    handToEar: (b, o) => { const s2 = o.side ?? 1;
      return { ...arm(s2, 30, 120), ...arm(-s2, 8, 20), angleZ: 7 * s2, angleX: .2 * s2, bodyZ: 2.5 * s2, bodyX: .3 * s2 }; },
    wave: (b, o) => { const s2 = o.side ?? 1; return { ...arm(s2, 34, 95 + 18 * S(PI * b)), bodyZ: 1.5 * s2 }; },     // one wave per 2 beats
    reach: (b, o) => { const s2 = o.side ?? 1; return { ...arm(s2, o.a ?? 58, o.e ?? 8), ...arm(-s2, 14, 30), bodyZ: -2.5 * s2, bodyX: .35 * s2, angleZ: -3 * s2 }; },
    claws: (b, o) => { const ev = o.every ?? 2, sn = (o.snip ?? 1) * pulse((b % ev) / ev, .35);      // both arms up, bent: the crab
      return { ...arm(1, 26, 105 - 30 * sn), ...arm(-1, 26, 105 - 30 * sn), hipY: 6 * sn }; },
    armsOut: (b, o) => ({ ...arm(1, o.a ?? 48, o.e ?? 15), ...arm(-1, o.a ?? 48, o.e ?? 15), angleY: o.y ?? -.25 }),
    present: (b, o) => ({ ...arm(1, 40, 35), ...arm(-1, 40, 35), angleY: -.35, hipY: 8 }),                  // arms open to the crowd
    // head
    headBob: (b, o) => ({ angleY: -(o.amp ?? .4) * pulse(b % 1, .45) }),
    headTilt: (b, o) => { const ev = o.every ?? 2, side = alt(b, ev) * (o.side ?? 1); return { angleZ: (o.amp ?? 8) * side * snap((b % ev) / ev, .3) }; },
    look: (b, o) => ({ view: o.view ?? 'F', angleX: o.x ?? 0, angleY: o.y ?? 0, angleZ: o.z ?? 0 }),
  };

  function choreo(clock, tracks, extra = {}) {
    const beat = 60 / clock.bpm, bar = beat * (clock.beatsPerBar ?? 4), t0 = clock.t0 ?? 0;
    const chans = Object.values(tracks).map(list => list.map(([br, name, o = {}]) => ({ t: t0 + br * bar, f: M[name] || name, o })));
    return t => {
      const out = {};
      const add = p => { for (const [k, v] of Object.entries(p)) { if (typeof v === 'number') out[k] = (out[k] || 0) + v; else if (v != null) out[k] = v; } };
      for (const ch of chans) {
        let i = -1; for (let j = 0; j < ch.length; j++) if (t >= ch[j].t) i = j;
        if (i < 0) continue;
        const cur = ch[i], pc = cur.f((t - cur.t) / beat, cur.o), fade = (cur.o.fade ?? .5) * beat;
        if (i > 0 && t - cur.t < fade) {                                         // crossfade from the previous move
          const pv = ch[i - 1], pp = pv.f((t - pv.t) / beat, pv.o), w = ease((t - cur.t) / fade), mix = {};
          for (const k of new Set([...Object.keys(pp), ...Object.keys(pc)])) {
            const a = pp[k], c = pc[k];
            mix[k] = typeof (c ?? a) === 'number' ? (a || 0) * (1 - w) + (c || 0) * w : (w < .5 ? a ?? c : c ?? a);
          }
          add(mix);
        } else add(pc);
      }
      if (extra.lips) { const m = extra.lips(t); if (m) out.mouth = m; }
      if (extra.blinks) { const e = extra.blinks(t); if (e && !out.eyes) out.eyes = e; }
      out.breath = .5 + .5 * S(2 * PI * t / 3.23);
      return out;
    };
  }

  // lip-sync from word timestamps ({t0, t1, w, who}): one drawn vowel per word, closed between words, crowd calls (in
  // parentheses) silent. Shapes change on twos.
  function lips(words, who) {
    const W = []; let crowd = false;
    for (const w of words || []) {
      if (w.who !== who) continue;
      const open = w.w.includes('('), close = w.w.includes(')');
      if (open) crowd = true;
      if (!crowd) W.push(w);
      if (close) crowd = false;
    }
    const VOW = s => ({ a: 'A', e: 'E', i: 'I', o: 'O', u: 'U', y: 'I' })[(s.toLowerCase().match(/[aeiouy]/) || ['e'])[0]];
    return t => { const q = Math.floor(t * 12) / 12;
      for (const w of W) if (q >= w.t0 - .04 && q < w.t1 - .03) return VOW(w.w);
      return null; };
  }
  // seeded blinks: close 0.1 / hold 0.05 / open 0.15 s, every 2-4 s (three drawings on twos)
  function blinks(seed = 7, from = 0, to = 400) {
    const ts = []; let s = seed, t = from + 1; const rnd = () => (s = (s * 16807) % 2147483647) / 2147483647;
    while (t < to) { ts.push(t); t += 2 + 2 * rnd(); }
    return t => { const q = Math.floor(t * 12) / 12;
      for (const t0 of ts) { const d = q - t0; if (d >= 0 && d < 3 / 12) return d < 1 / 12 ? 'half' : d < 2 / 12 ? 'closed' : 'half'; if (t0 > q) break; }
      return null; };
  }

  // follow(P, springs): the choreography sets TARGETS; each listed parameter follows its target through a damped spring
  // (natural frequency w rad/s, damping ratio z), simulated at 1/120 s from a pre-roll, so poses are reached with real
  // acceleration, a little overshoot and a settle, instead of snapping. Looser springs on the elbows than the shoulders give
  // overlapping action (the forearm trails the upper arm). Pure function of t.
  function follow(P, springs, o = {}) {
    // simulated once from a FIXED start on a fixed grid and cached, so any t gives the same answer in any render order (and
    // the rig's own springs, which query P many times per frame, cost nothing extra)
    const names = Object.keys(springs), dt = 1 / 120, start = o.start ?? 0, cache = [];
    const stateAt = j => {
      if (cache.length === 0) { const p0 = P(start); cache.push(names.map(k => [p0[k] || 0, 0])); }
      while (cache.length <= j) {
        const prev = cache[cache.length - 1], p = P(start + cache.length * dt);
        cache.push(names.map((k, i) => { const { w, z } = springs[k], [x, v] = prev[i], a = w * w * ((p[k] || 0) - x) - 2 * z * w * v, v2 = v + a * dt; return [x + v2 * dt, v2]; }));
      }
      return cache[j];
    };
    return t => {
      const out = { ...P(t) };
      if (t < start) return out;
      const f = (t - start) / dt, j = Math.floor(f), u = f - j, A = stateAt(j), B = stateAt(j + 1);
      names.forEach((k, i) => { out[k] = A[i][0] + (B[i][0] - A[i][0]) * u; });
      return out;
    };
  }
  // the default body springs: arms looser at the elbow (the forearm trails), hips weighty, the body lean slow
  const BODY = { armL: { w: 13, z: .62 }, armR: { w: 13, z: .62 }, elbowL: { w: 10, z: .5 }, elbowR: { w: 10, z: .5 },
                 hipX: { w: 11, z: .7 }, hipY: { w: 22, z: .55 }, bodyZ: { w: 8, z: .7 }, bodyX: { w: 8, z: .75 },
                 footLX: { w: 18, z: .8 }, footRX: { w: 18, z: .8 }, footLY: { w: 22, z: .7 }, footRY: { w: 22, z: .7 } };

  return { M, choreo, follow, BODY, lips, blinks, pulse, snap, ease };
})();
