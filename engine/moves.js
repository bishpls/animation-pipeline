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
      const out = S(PI * ph), step = (o.step ?? 120) * out, lift = (o.lift ?? 45) * (ph < .5 ? 1 : .6) * Math.abs(S(2 * PI * ph));   // (lifted home too: never dragged)
      const f = side > 0 ? { footRX: step, footRY: lift } : { footLX: -step, footLY: lift };
      return { ...f, hipX: 1.1 * side * out, bodyZ: 2 * side * out, hipY: (o.dip ?? 14) * pulse(b % 1, .5) };
    },
    // the sideways step (Fable's exception): each step travels in the last third of a period and LANDS on its downbeat, weight
    // low (a dip), feet flat; the other foot closes mid-period, lifted (never dragged), and the root travels with it. rootX (base
    // px) moves her across the stage; feet are relative to the root. Entry and exit are part of the move, so it never starts or
    // stops with a foot in the air or apart:
    //   o.lead   beats from the move's start to the first landing: she starts closed, and the lead steps out to land (0: starts landed)
    //   o.steps  landings; after the last the trail closes and she holds, feet together. A reversal is then a clean
    //            side-together | side the other way: a second sideStep starting closed where this one stopped (root0).
    sideStep: (b, o) => {
      const ev = o.every ?? 2, dir = o.dir ?? 1, st = o.step ?? 240, r0 = o.root0 ?? 0, n = o.steps ?? Infinity, u = (b - (o.lead ?? 0)) / ev;
      let k = Math.floor(u), ph = u - k;
      if (u < 0) { k = -1; ph = Math.max(0, u + 1); }                                  // the entry: closed, then the lead steps out
      if (k > n - 1) { k = n - 1; ph = 1; }                                             // the exit: closed, held
      const last = k === n - 1, entry = k < 0;
      const close = entry ? 1 : ph < .3 ? 0 : ph < .67 ? ease((ph - .3) / .37) : 1, out = last || ph < .67 ? 0 : ease((ph - .67) / .33);
      const root = r0 + dir * st * (k + close), leadAbs = r0 + dir * st * (k + 1 + out), trailAbs = root;
      const lead = dir > 0 ? 'R' : 'L', trail = dir > 0 ? 'L' : 'R', lift = last || ph < .67 ? 0 : S(PI * (ph - .67) / .33);
      const land = entry ? 0 : pulse(ph, .35);
      const tlift = !entry && ph > .3 && ph < .67 ? S(PI * (ph - .3) / .37) : 0;       // the trailing foot LIFTS as it closes
      return { rootX: root, ['foot' + lead + 'X']: leadAbs - root, ['foot' + lead + 'Y']: (o.lift ?? 40) * lift, ['foot' + trail + 'X']: trailAbs - root,
               ['foot' + trail + 'Y']: (o.tlift ?? 34) * tlift,
               hipX: dir * ((entry ? 0 : .85 * (1 - close)) - .3 * lift), hipY: (o.dip ?? 28) * land, bodyZ: 2.5 * dir * (entry ? 0 : 1 - close) };
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
    // the curtsy (the end of her performance), in beats from its start: weight onto the front foot while the other lifts, travels
    // back and behind and PLACES (no sliding contact), then loads; both knees bend (the hip drop), the head bows, eyes close,
    // and both hands pinch the skirt's sides and lift them a little outward; a real hold, then a light rise. The back foot is
    // the image-right one (R: its leg draws behind the other). o.down [start, end] beats of the dip; o.rise [start, end].
    curtsy: (b, o) => {
      const [d0, d1] = o.down ?? [1, 3], [r0, r1] = o.rise ?? [4.4, 5.6], back = o.back ?? -200, deep = o.deep ?? 175;
      const step = ease(b / .9), dip = ease((b - d0) / (d1 - d0)) - (1 - (o.rest ?? .38)) * ease((b - r0) / (r1 - r0));
      const reach = ease(b / 1.1), lift = ease((b - d0) / (d1 - d0)) * (1 - .6 * ease((b - r0) / (r1 - r0)));
      const out = {
        hipX: -.42 * step, hipY: deep * dip, kneeOut: .75 * step,                                  // (knees bend out: a plié, not knock-kneed)
        footRX: back * step, footRY: 36 * S(PI * Math.min(1, b / .9)) + 20 * step,            // lift, travel, place (back = up the floor)
        armL: -26 * reach + 2 * lift, armR: -26 * reach + 2 * lift, elbowL: 8 * reach + 13 * lift, elbowR: 8 * reach + 13 * lift,   // (on the hem: the lift is the elbows)
        angleY: .8 * dip + .08 * step, bodyZ: .8 * step,
      };
      if (b > .7) { out.handL = 'skirtpinch'; out.handR = 'skirtpinch'; }
      if (b > d0 + .6 && b < r0 + .5) out.eyes = 'closed'; else if (b > d0 + .3 && b < r1) out.eyes = 'half';
      return out;
    },
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

  // lip-sync on ones (24 drawings a second) from word timestamps ({t0, t1, w, who}) and her voice's loudness (env: {fps,
  // [who]: [0..1]}), built as an animator would time it:
  //  - each word's syllables come from a pronunciation table (PRON: vowel per syllable, stress, a lip closure m/b/p before
  //    it), falling back to spelling; syllable onsets split the word at the dips in her voice
  //  - each syllable's drawing comes from its vowel, full when stressed and loud, soft otherwise; the wide grins (I, E) are
  //    kept for bright held exclamations only ("me!", "see!")
  //  - the mouth leads the voice by one frame; it OPENS ahead of a syllable and CLOSES after the sound, and every change
  //    travels through the drawings between (openness x rounding: closed > S > Am > A, never closed > wide; O > Os > U)
  //  - the jaw stays open through a phrase: short gaps between syllables hold S, and consecutive open syllables get a
  //    one-frame jaw dip (the consonant) instead of a snap to closed; m/b/p press the lips (MBP) before they open
  //  - a held note softens once (A > Am) as it decays; crowd calls (words in parentheses) keep the mouth closed
  // Returns a mouth variant name, or null for the rest mouth.
  const PRON = {                       // '^' lips close before the syllable; UPPER stressed, lower unstressed; x = schwa
    a: 'x', and: 'a', be: '^I', behind: '^i A', book: '^U', but: '^A', "can't": 'A', close: 'O', continued: 'x I U', copy: 'O ^i',
    crab: 'A', dare: 'E', "don't": 'O', "else's": 'E i', ever: 'E x', every: 'E i', fine: 'A', first: 'x', free: 'I', go: 'O',
    hand: 'A', her: 'x', how: 'A', i: 'A', "i'll": 'A', "i'm": 'A', if: 'i', ikuzo: 'I U O', in: 'i', it: 'i', line: 'A',
    little: 'I x', made: '^E', make: '^E', me: '^I', my: '^A', never: 'E x', next: 'E', "nobody's": 'O ^o i', of: 'x', okay: 'o E',
    on: 'O', once: 'A', own: 'O', page: '^E', path: '^A', prompt: '^O', read: 'E', right: 'A', says: 'E', see: 'I', she: 'I',
    "she'd": 'I', show: 'O', 'side-step': 'A E', sideways: 'A E', 'snip-snip': 'I I', so: 'O', somebody: 'A ^o i',
    sorekara: 'O e A a', steps: 'E', straight: 'E', that: 'A', "that's": 'A', the: 'x', then: 'E', to: 'u', told: 'O', turn: 'x',
    up: 'A', upon: 'x ^O', walk: 'O', walked: 'O', walks: 'O', want: 'O', was: 'o', watch: 'O', way: 'E', we: 'I', went: 'E',
    who: 'U', why: 'A', "won't": 'O', wrote: 'O', yet: 'E', you: 'U' };
  function pron(word) {
    const w = word.toLowerCase().replace(/[^a-z\-']/g, '');
    if (PRON[w]) return PRON[w].split(' ').map(q => ({ mbp: q[0] === '^', v: q.replace('^', '').toUpperCase(), stress: /[AEIOU]/.test(q.replace('^', '')) }));
    const out = [];                                                           // (fallback: spelling; romaji is regular)
    for (const part of (w.includes('-') ? w.split('-') : [w]).filter(Boolean))
      for (const m of part.matchAll(/[aeiouy]+/g)) {
        const g = m[0], v = /^(ee|ea|ie|i|y)/.test(g) ? 'I' : /^(oo|u)/.test(g) ? 'U' : /^o/.test(g) ? 'O' : /^e/.test(g) ? 'E' : 'A';
        out.push({ v, mbp: /[mbp]/.test(part[m.index - 1] || ''), stress: out.length === 0 });
      }
    return out.length ? out : [{ v: 'X', mbp: false, stress: false }];
  }
  // the drawings as points: openness (0 closed .. 3 wide) and rounding (-1 spread .. 1 round); the grins sit outside the family
  const MP = { null: [0, 0], MBP: [0, .2], S: [1, 0], Is: [.9, -1], Ih: [1.5, -.9], Eh: [2, -.4], Am: [2, 0], A: [3, 0], A2: [3, 0],
               Os: [2, 1], O: [3, 1], U: [1.3, 1.3], I: [3, -1], E: [3, -.6] };
  const FAMILY = ['null', 'S', 'Is', 'Ih', 'Eh', 'Am', 'A', 'Os', 'O', 'U'];
  const FULL = { A: 'A', E: 'Eh', I: 'Ih', O: 'O', U: 'U', X: 'Am' }, SOFT = { A: 'Am', E: 'Ih', I: 'Is', O: 'Os', U: 'U', X: 'S' };
  const DECAY = { A: 'Am', A2: 'Am', Am: 'S', Eh: 'Ih', Ih: 'Is', Is: 'S', I: 'Ih', E: 'Eh', O: 'Os', Os: 'U', U: 'S', S: 'S' };
  const dist = (p, q) => { const a = MP[p], b = MP[q]; return Math.hypot(a[0] - b[0], .8 * (a[1] - b[1])); };
  const nearest = (o, r, rest = true) => { let best = 'S', d = Infinity; for (const n of FAMILY) { if (!rest && n === 'null') continue; const e = Math.hypot(MP[n][0] - o, .8 * (MP[n][1] - r)); if (e < d) { d = e; best = n; } } return best; };
  function between(p, q) {                                                    // the drawings on the way from p to q
    const n = Math.ceil(dist(p, q) / 1.25) - 1, out = [];
    for (let k = 1; k <= n; k++) { const u = k / (n + 1), a = MP[p], b = MP[q], s2 = nearest(a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u, false);   // (never the rest mouth mid-way)
      if (s2 !== p && s2 !== q && s2 !== out[out.length - 1]) out.push(s2); }
    return out;
  }
  function lips(words, who, env) {
    const W = [], crowdSpans = []; let crowd = false, cs = null;
    for (const w of words || []) {
      if (w.who !== who) continue;
      const open = w.w.includes('('), close = w.w.includes(')');
      if (open) { crowd = true; cs = w.t0; }
      if (!crowd) W.push(w);
      if (close) { crowd = false; crowdSpans.push([cs, w.t1 + .15]); }
    }
    const E = env && env[who], fps = env && env.fps, F = 24, THR = .3;
    const level = t => { if (!E) return 1; const i = Math.round(t * fps); let s = 0; for (let k = -1; k <= 1; k++) s += E[Math.max(0, i + k)] || 0; return s / 3; };
    const inCrowd = t => crowdSpans.some(([a, b]) => t >= a && t < b);
    // syllables, their onsets and how long each sounds
    const SY = [];
    for (let wi = 0; wi < W.length; wi++) {
      const w = W[wi], sy = pron(w.w), n = sy.length, d = Math.max(.06, w.t1 - w.t0), next = W[wi + 1] ? W[wi + 1].t0 : w.t1 + 4;
      const on = [w.t0];
      for (let k = 1; k < n; k++) {
        const c = w.t0 + d * k / n, r = .3 * d / n; let best = c, lo = Infinity;
        if (E) for (let tt = c - r; tt <= c + r; tt += 1 / fps) { const l = level(tt); if (l < lo) { lo = l; best = tt; } }
        on.push(Math.max(on[k - 1] + 2 / F, best));
      }
      let endW = w.t1; if (E) while (endW < next && level(endW) >= THR) endW += 1 / fps;       // a held note sounds past its word
      sy.forEach((s, k) => SY.push({ ...s, t: on[k], end: k < n - 1 ? on[k + 1] : Math.min(next, endW), last: k === n - 1, excl: w.w.includes('!'), wt1: w.t1 }));
    }
    // each syllable's drawing
    let prev = null;
    for (const s of SY) {
      let pk = 0; for (let tt = s.t; tt < s.t + .12; tt += 1 / 50) pk = Math.max(pk, level(tt));
      s.shape = (s.stress && (!E || pk >= .5) && s.end - s.t >= 4 / F ? FULL : SOFT)[s.v] || 'Am';   // (a very short syllable undershoots)
      if (s.excl && s.last && s.stress && s.v === 'I' && s.end - s.t >= .45 && pk >= .6) s.shape = 'I';      // the wide grin: a bright held 'ee!' only
      if (s.shape === prev && s.shape === 'A') s.shape = 'A2';
      prev = s.shape;
      s.decay = Infinity; if (E && s.last) for (let tt = s.t + .25; tt < s.end; tt += 1 / 50) if (level(tt) < .42) { s.decay = tt; break; }
    }
    // the targets, frame by frame (lead one frame; closed = 'null')
    const N = Math.ceil(((W.length ? W[W.length - 1].t1 : 0) + 6) * F), T = new Array(N).fill('null'), syl = new Array(N).fill(-1);
    SY.forEach((s, i) => { const fa = Math.max(0, Math.round(s.t * F) - 1), fb = Math.min(N, Math.round(s.end * F));
      for (let f = fa; f < fb; f++) { if (f / F > s.wt1 && inCrowd(f / F)) break;               // (a note held into the crowd's call closes)
        T[f] = f / F >= s.decay ? DECAY[s.shape] || 'S' : s.shape; syl[f] = i; } s.fa = fa; s.fb = fb; });
    // short gaps inside a phrase hold the jaw at S; m/b/p press the lips just before their syllable opens
    SY.forEach((s, i) => { const nx = SY[i + 1]; if (!nx) return;
      if (nx.fa - s.fb > 0 && nx.fa - s.fb <= Math.round(.18 * F) && !inCrowd((s.fb + 1) / F)) for (let f = s.fb; f < nx.fa; f++) T[f] = 'S';
      if (nx.mbp) { const len = s.fb - s.fa >= 6 || s.fb < nx.fa - 1 ? 2 : 1;                   // (after a short syllable: one frame)
        for (let f = Math.max(0, nx.fa - len); f < nx.fa; f++) T[f] = 'MBP'; }
      // the consonant between two open syllables: a one-frame dip of the jaw
      else if (nx.fa === s.fb && s.fb - s.fa >= 3 && nx.fb - nx.fa >= 3 && MP[T[s.fb - 1]][0] >= 2 && MP[T[nx.fa]][0] >= 2) {
        const a = MP[T[s.fb - 1]], b = MP[T[nx.fa]]; T[s.fb - 1] = nearest(Math.min(a[0], b[0]) - 1, (a[1] + b[1]) / 2, false);
      } });
    // the paths between: opening and changes arrive ON the target frame (the in-betweens take the frames before it, never
    // the whole of the previous drawing); closing to rest happens after the sound
    const O = T.slice(), lock = new Array(N).fill(false), runs = [];
    for (let f = 0; f < N;) { let g = f; while (g < N && T[g] === T[f]) g++; runs.push([T[f], f, g - f]); f = g; }
    for (let r = 0; r + 1 < runs.length; r++) {
      const [P, pf, pl] = runs[r], [Q, qf, ql] = runs[r + 1], mids = between(P, Q).slice(0, Q === 'MBP' ? 1 : 9);   // (lips snap shut for m/b/p)
      if (!mids.length) continue;
      if (Q === 'null') { const k = Math.min(mids.length, ql); for (let i = 0; i < k; i++) { O[qf + i] = mids[i]; lock[qf + i] = true; } }
      else {
        let room = P === 'null' ? pl : pl - 1; while (room > 0 && lock[qf - room]) room--;
        const k = Math.min(mids.length, room), spill = Math.min(mids.length - k, Math.max(0, ql - 2));   // (no room before: the rest open into the target)
        for (let i = 0; i < k; i++) { const f = qf - k + i; O[f] = mids[i]; lock[f] = true; }
        for (let i = 0; i < spill; i++) { O[qf + i] = mids[k + i]; lock[qf + i] = true; }
      }
    }
    for (let f = 1; f < N - 1; f++) if (O[f] === 'null' && O[f - 1] !== 'null') {             // a closure of 1-2 frames isn't a stop: hold S
      let g = f; while (g < N && O[g] === 'null') g++; if (g < N && g - f <= 2) for (let h = f; h < g; h++) O[h] = 'S'; f = g; }
    return t => { const f = Math.floor(t * F + 1e-6); return f < 0 || f >= N || O[f] === 'null' ? null : O[f]; };
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
    // o.world {key: px per unit}: follow these in WORLD space (value x scale + rootX), so a travelling root (sideStep) never
    // makes a planted foot or the pelvis slide while the spring catches up with the relative target
    const names = Object.keys(springs), dt = 1 / 120, start = o.start ?? 0, cache = [], Wd = o.world || {};
    const val = (p, k) => (p[k] || 0) * (Wd[k] ?? 1) + (k in Wd ? (p.rootX || 0) : 0);
    const stateAt = j => {
      if (cache.length === 0) { const p0 = P(start); cache.push(names.map(k => [val(p0, k), 0])); }
      while (cache.length <= j) {
        const prev = cache[cache.length - 1], p = P(start + cache.length * dt);
        cache.push(names.map((k, i) => { const { w, z } = springs[k], [x, v] = prev[i], a = w * w * (val(p, k) - x) - 2 * z * w * v, v2 = v + a * dt; return [x + v2 * dt, v2]; }));
      }
      return cache[j];
    };
    return t => {
      const out = { ...P(t) };
      if (t < start) return out;
      const f = (t - start) / dt, j = Math.floor(f), u = f - j, A = stateAt(j), B = stateAt(j + 1);
      names.forEach((k, i) => { const x = A[i][0] + (B[i][0] - A[i][0]) * u; out[k] = k in Wd ? (x - (out.rootX || 0)) / Wd[k] : x; });
      return out;
    };
  }
  // the default body springs: arms looser at the elbow (the forearm trails), hips weighty, the body lean slow
  const BODY = { armL: { w: 13, z: .62 }, armR: { w: 13, z: .62 }, elbowL: { w: 10, z: .5 }, elbowR: { w: 10, z: .5 },
                 hipX: { w: 11, z: .7 }, hipY: { w: 22, z: .55 }, bodyZ: { w: 8, z: .7 }, bodyX: { w: 8, z: .75 },
                 footLX: { w: 34, z: .95 }, footRX: { w: 34, z: .95 }, footLY: { w: 30, z: .8 }, footRY: { w: 30, z: .8 } };   // feet: stiff (flat, no slide)

  return { M, choreo, follow, BODY, lips, blinks, pulse, snap, ease };
})();
