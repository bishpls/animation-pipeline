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
  const arm = (side, a, e, h) => side > 0 ? { armR: a, elbowR: e, ...(h ? { handR: h } : {}) } : { armL: a, elbowL: e, ...(h ? { handL: h } : {}) };

  // Moves set TARGETS (MOVES.follow turns them into physical motion). Legs keep the beat; arms phrase on the half bar.
  const M = {
    idle: () => ({}),
    // legs and body
    // Clawd never lands (Fable, CLAWDWORLD.md): she rises ON the beat (up on her toes) and gives on the "and"; the crabs land it
    bounce: (b, o) => ({ hipY: (o.amp ?? 16) * (pulse((b + .5) % 1, .5) - .45 * pulse(b % 1, .4)) }),
    groove: (b, o) => { const side = alt(b, 2) * (o.side ?? 1);                                   // lean over each 2 beats, dip each beat
      return { hipY: (o.amp ?? 14) * (pulse((b + .5) % 1, .5) - .45 * pulse(b % 1, .4)), bodyZ: 2.5 * side, hipX: .35 * side, angleZ: -1.5 * side }; },
    sway: (b, o) => {                                                          // the hips cross on each period and hold
      const ev = o.every ?? 2, ph = (b % ev) / ev, side = alt(b, ev) * (o.side ?? 1), amp = o.amp ?? 1.1;
      return { hipX: amp * (-side + 2 * side * snap(ph, .35)), hipY: (o.dip ?? 12) * (pulse((b + .5) % 1, .5) - .45 * pulse(b % 1, .4)) };
    },
    stepTouch: (b, o) => {                                                     // step out and touch in, alternating feet
      const ev = o.every ?? 2, k = Math.floor(b / ev), ph = (b % ev) / ev, side = (k % 2 ? -1 : 1) * (o.side ?? 1);
      const out = S(PI * ph), step = (o.step ?? 120) * out, lift = (o.lift ?? 45) * Math.max(0, S(2 * PI * ph));
      const f = side > 0 ? { footRX: step, footRY: lift } : { footLX: -step, footLY: lift };
      return { ...f, hipX: 1.1 * side * out, bodyZ: 2 * side * out, hipY: (o.dip ?? 14) * pulse(b % 1, .5) };
    },
    // the sideways step (Fable's exception): each step travels in the last third of the period before and LANDS on the
    // downbeat, weight low (a deep dip), feet flat; the other foot closes mid-period. Steps travel in one direction (o.dir).
    sideStep: (b, o) => {
      // travelling: per period k the lead foot has LANDED at the downbeat (weight low, hips over it); the trail foot closes
      // (ph .3-.67, the root travels with it); then the lead lifts and travels to land on the next downbeat. rootX (base px)
      // moves her across the stage (the stage adds it to the draw position); feet are relative to the root, so they're flat.
      const ev = o.every ?? 2, k = Math.floor(b / ev), ph = (b % ev) / ev, dir = o.dir ?? 1, st = o.step ?? 360, r0 = o.root0 ?? 0;
      const close = ph < .3 ? 0 : ph < .67 ? ease((ph - .3) / .37) : 1, out = ph < .67 ? 0 : ease((ph - .67) / .33);
      const root = r0 + dir * st * (k + close), leadAbs = r0 + dir * st * (k + 1 + out), trailAbs = r0 + dir * st * (k + close);
      const lead = dir > 0 ? 'R' : 'L', trail = dir > 0 ? 'L' : 'R', lift = ph < .67 ? 0 : S(PI * (ph - .67) / .33);
      const land = pulse(ph, .35);
      return { rootX: root, ['foot' + lead + 'X']: leadAbs - root, ['foot' + lead + 'Y']: (o.lift ?? 40) * lift, ['foot' + trail + 'X']: trailAbs - root,
               hipX: dir * (.85 * (1 - close) - .3 * lift), hipY: (o.dip ?? 28) * land, bodyZ: 2.5 * dir * (1 - close) };
    },
    swingArms: (b, o) => { const u = S(PI * b / 2); return { ...arm(1, 16 + 10 * u, 35 + 15 * u), ...arm(-1, 16 - 10 * u, 35 - 15 * u) }; },   // walking
    rise: (b, o) => ({ ...arm(1, 52, 18), ...arm(-1, 52, 18), angleY: .3, hipY: -8 }),                    // phrase end, rising
    // arms (side: +1 the character's left = image right); half-bar phrasing
    armPump: (b, o) => { const ev = o.every ?? 2, u = pulse((b % ev) / ev, .5), s2 = alt(b, ev) * (o.side ?? 1);
      return { ...arm(s2, 15 + 25 * u, 45 + 65 * u, 'fist'), ...arm(-s2, 12, 45, 'fist'), bodyZ: 1.5 * s2 * u, bodyX: .25 * s2 * u }; },
    handToEar: (b, o) => { const s2 = o.side ?? 1;
      return { ...arm(s2, 30, 120), ...arm(-s2, 8, 20), angleZ: 7 * s2, angleX: .2 * s2, bodyZ: 2.5 * s2, bodyX: .3 * s2 }; },
    wave: (b, o) => { const s2 = o.side ?? 1; return { ...arm(s2, 34, 95 + 18 * S(PI * b)), bodyZ: 1.5 * s2 }; },     // one wave per 2 beats
    reach: (b, o) => { const s2 = o.side ?? 1; return { ...arm(s2, o.a ?? 58, o.e ?? 8, o.hand ?? 'point'), ...arm(-s2, 14, 30), bodyZ: -2.5 * s2, bodyX: .35 * s2, angleZ: -3 * s2 }; },
    claws: (b, o) => { const ev = o.every ?? 2, sn = (o.snip ?? 1) * pulse((b % ev) / ev, .35);      // both arms up, bent: the crab
      const h = sn > .25 ? 'pinch' : null;                                                                   // the snip: pinch on the hit
      return { ...arm(1, 26, 105 - 30 * sn, h), ...arm(-1, 26, 105 - 30 * sn, h), hipY: 6 * sn }; },
    armsOut: (b, o) => ({ ...arm(1, o.a ?? 48, o.e ?? 15), ...arm(-1, o.a ?? 48, o.e ?? 15), angleY: o.y ?? -.25 }),
    present: (b, o) => ({ ...arm(1, 40, 35), ...arm(-1, 40, 35), angleY: -.35, hipY: 8 }),                  // arms open to the crowd
    peace: (b, o) => { const s2 = o.side ?? 1; return { ...arm(s2, 32, 118, 'peace'), ...arm(-s2, 14, 40), angleZ: 8 * s2, bodyZ: 2 * s2, eyes: o.wink ? null : undefined, [s2 > 0 ? 'eyeR' : 'eyeL']: o.wink ? 'closed' : undefined }; },
    // the hook (one call per bar: the call on beats 1-2, the crowd's two claps on 3-4, which Clawd answers with two snips)
    snipSnip: (b, o) => { const hit = b < 2 ? pulse(b % 1, .3) : 0, h = hit > .25 ? 'pinch' : null;        // two snips from its start
      return { ...arm(1, 24, 100 - 28 * hit, h), ...arm(-1, 24, 100 - 28 * hit, h), hipY: 5 * hit }; },
    callEar: (b, o) => { const s2 = o.side ?? 1;                                 // the call, asked: hand to ear, the head tilts in
      return { ...arm(s2, 30, 120), ...arm(-s2, 12, 35), angleZ: 8 * s2, angleX: .2 * s2, bodyZ: 2.5 * s2, bodyX: .3 * s2 }; },
    pageWipe: (b, o) => { const s2 = o.side ?? 1, u = snap(b / 2, .6);      // turn the page: a flat hand sweeps across the body
      return { ...arm(s2, 38 - 46 * u, 10 - 135 * u), ...arm(-s2, 14, 30), bodyZ: -2.5 * s2 * u, bodyX: -.4 * s2 * u, angleZ: -3 * s2 * u }; },
    handOnChest: (b, o) => { const s2 = o.side ?? 1; return { ...arm(s2, -8, -125), ...arm(-s2, 10, 25), angleY: -.15 }; },
    telling: (b, o) => { const s2 = o.side ?? 1; return { ...arm(s2, 30, 45), ...arm(-s2, 12, 30), angleZ: 4 * s2, bodyZ: 1.5 * s2 }; },   // an open palm, telling
    writing: (b, o) => { const s2 = o.side ?? 1; return { ...arm(s2, 24 + 4 * S(PI * b * 2), 70 + 12 * S(PI * b * 4), 'point'), ...arm(-s2, 16, 60), angleY: .25 }; },
    shrug: (b, o) => ({ ...arm(1, 26, 70), ...arm(-1, 26, 70), angleZ: 6 * (o.side ?? 1), hipY: 6 }),
    pointOut: (b, o) => { const s2 = o.side ?? 1; return { ...arm(s2, 50, 5, 'point'), ...arm(-s2, 12, 30), bodyX: .3 * s2, angleX: .15 * s2 }; },
    shake: (b, o) => ({ angleX: .22 * S(2 * PI * b) }),                                                          // 'no, no'
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
        const run = (m, tt) => { const r = m.f((tt - m.t) / beat, m.o); return m.o.root != null && r.rootX == null ? { rootX: m.o.root, ...r } : r; };   // o.root: hold her place
        const cur = ch[i], pc = run(cur, t), fade = (cur.o.fade ?? .5) * beat;
        if (i > 0 && t - cur.t < fade) {                                         // crossfade from the previous move
          const pv = ch[i - 1], pp = run(pv, t), w = ease((t - cur.t) / fade), mix = {};
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
                 footLX: { w: 34, z: .95 }, footRX: { w: 34, z: .95 }, footLY: { w: 30, z: .8 }, footRY: { w: 30, z: .8 } };   // feet: stiff (flat, no slide)

  return { M, choreo, follow, BODY, lips, blinks, pulse, snap, ease };
})();
