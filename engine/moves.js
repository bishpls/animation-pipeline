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

  const M = {
    idle: () => ({}),
    // legs
    bounce: (b, o) => ({ hipY: (o.amp ?? 10) * pulse(b % 1) }),
    sway: (b, o) => {                                                          // the hips cross on each period and hold
      const ev = o.every ?? 2, ph = (b % ev) / ev, side = alt(b, ev) * (o.side ?? 1), amp = o.amp ?? .9;
      return { hipX: amp * (-side + 2 * side * snap(ph, .3)), hipY: (o.dip ?? 8) * pulse(b % 1) };
    },
    stepTouch: (b, o) => {                                                     // step out and touch in, alternating feet
      const ev = o.every ?? 2, k = Math.floor(b / ev), ph = (b % ev) / ev, side = (k % 2 ? -1 : 1) * (o.side ?? 1);
      const out = S(PI * ph), step = (o.step ?? 70) * out, lift = (o.lift ?? 30) * Math.max(0, S(2 * PI * ph));
      const f = side > 0 ? { footRX: step, footRY: lift } : { footLX: -step, footLY: lift };
      return { ...f, hipX: .8 * side * out, hipY: (o.dip ?? 10) * pulse(b % 1) };
    },
    // arms (side: +1 the character's left)
    armPump: (b, o) => { const u = pulse(b % 1, .45), s2 = alt(b) * (o.side ?? 1);
      return { ...arm(s2, 12 + 14 * u, 45 + 55 * u), ...arm(-s2, 10, 40) }; },
    handToEar: (b, o) => { const s2 = o.side ?? 1, u = snap(b, .4);
      return { ...arm(s2, 28 * u, 118 * u), angleZ: 6 * s2 * u, angleX: .15 * s2 * u, bodyZ: 1.5 * s2 * u }; },
    wave: (b, o) => { const s2 = o.side ?? 1, u = snap(b, .4); return arm(s2, 30 * u, (85 + 20 * S(2 * PI * b * (o.rate ?? 2))) * u); },
    reach: (b, o) => { const s2 = o.side ?? 1, u = snap(b, .3); return arm(s2, (o.a ?? 42) * u, (o.e ?? 12) * u); },
    claws: (b, o) => { const u = snap(b, .3), sn = (o.snip ?? 1) * pulse(b % 1, .3);   // both arms up, bent: the crab
      return { ...arm(1, 22 * u, (100 - 25 * sn) * u), ...arm(-1, 22 * u, (100 - 25 * sn) * u) }; },
    armsOut: (b, o) => { const u = snap(b, .3); return { ...arm(1, (o.a ?? 38) * u, (o.e ?? 20) * u), ...arm(-1, (o.a ?? 38) * u, (o.e ?? 20) * u) }; },
    // head
    headBob: (b, o) => ({ angleY: -(o.amp ?? .35) * pulse(b % 1, .4) }),
    headTilt: (b, o) => { const ev = o.every ?? 2, side = alt(b, ev) * (o.side ?? 1); return { angleZ: (o.amp ?? 7) * side * snap((b % ev) / ev, .25) }; },
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

  return { M, choreo, lips, blinks, pulse, snap, ease };
})();
