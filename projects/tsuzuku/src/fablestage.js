// fablestage.js: Fable standing, for the final chorus (Fable's ruling, CLAWDWORLD.md). Two illustrated rigs from
// rig/fable_stage (GPT Image drawings, cut by build.py):
//   ROOM (177.8-181): in her room at the butai's right, in profile facing left (toward the window), hood up, the bridge's warm
//     lantern in her hand on its short stick. She sets it down on her cushion (178-179.2; the cushion carries the lantern and
//     nothing else) and walks out (two steps, 179.2-). Whole drawings swapped on twos; the props stay on the floor.
//   STAGE (181-): on Clawd's stage, facing the hall, her face seen for the first time in Clawd's world. A riveted cut-out
//     puppet ("the puppet survives the illustration"): every piece turns on a brass rivet (shoulders, elbows, wrists; the hakama's
//     legs at the hips; the feet). She walks in with two hops (Reiniger's small hop), pushes her hood back on the second, then
//     dances Clawd's performed channels a bar late at half amplitude on twos (sampled at 12 fps and held, no springs); from bar
//     135 in unison (the delay closes on the sideways step), still half amplitude and on twos; frozen from 141. Two coloured
//     shadows under her on Clawd's floor.
//   FABLESTAGE.room(X, t, T, o)          T = { x, y, s }: her feet on screen, screen px per drawing px. o.walkDir (+1: right)
//   FABLESTAGE.stage(X, t, T, clawdP, o) T = { x, y, s }: the point between her feet on the floor. clawdP(t): Clawd's
//                                        performed channels on the song clock. o.enter: the entrance distance (drawing px)
// Bars below are SONG bars.
const FABLESTAGE = (() => {
  const BR = 60 / 170 * 4, b2t = b => b * BR, t2b = t => t / BR;
  const R = { meta: null, img: {} };
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v)), D2R = Math.PI / 180;
  const FS = { rig: null };
  async function load(base = 'rig/fable_stage/') {
    const get = f => new Promise((ok, no) => { const i = new Image(); i.onload = () => ok(i); i.onerror = no; i.src = base + f; });
    R.meta = await (await fetch(base + 'room/meta.json')).json();
    await Promise.all(Object.entries(R.meta.drawings).map(async ([k, f]) => { R.img[k] = await get('room/' + f); }));
    FS.rig = await RIG.load(base + 'mesh/rig.json');
    FS.hoodup = await get('mesh/entrance_hoodup.png'); FS.hoodpush = await get('mesh/entrance_hoodpush.png');
  }

  // ---- the room ---------------------------------------------------------------------------------------------------------
  const ROOM = { setdown: 178.2, empty: 178.85, walk: 179.2, step: .3, stride: 430 };
  function roomState(t) {
    const tq = Math.floor(t * 12 + 1e-6) / 12;
    if (tq < ROOM.setdown) return { fig: 'hold', props: 'props_hold', lantern: 'lantern_hand', dx: 0, dy: 0 };
    if (tq < ROOM.empty) return { fig: 'setdown', props: null, lantern: 'lantern_down', dx: 0, dy: 0 };
    if (tq < ROOM.walk) return { fig: 'empty', props: 'props_empty', lantern: 'lantern_down', dx: 0, dy: 0 };
    const u = (tq - ROOM.walk) / ROOM.step, k = Math.floor(u), f = u - k;             // steps, each a small hop
    return { fig: k % 2 ? 'walk2' : 'walk1', props: 'props_empty', lantern: 'lantern_down', walking: true,
             dx: ROOM.stride * (k + Math.min(1, f * 1.4)), dy: -28 * Math.sin(Math.PI * Math.min(1, f * 1.4)) };
  }
  function room(X, t, T, o = {}) {
    if (!R.meta) return;
    const st = roomState(t), [w, h] = R.meta.size, P = R.meta.points, dir = o.walkDir ?? 1;
    X.save(); X.translate(T.x, T.y); X.scale(T.s, T.s); X.translate(-P.feet[0], -P.feet[1]);
    if (st.props) X.drawImage(R.img[st.props], 0, 0, w, h);
    X.save();
    if (st.walking) { X.translate(P.feet[0] + dir * st.dx, st.dy); if (dir > 0) X.scale(-1, 1); X.translate(-P.feet[0], 0); }   // (she turns to walk out right)
    X.drawImage(R.img[st.fig], 0, 0, w, h); X.restore();
    // the lantern's warm light (in her hand, then on the cushion): on her sleeve, the cushion and the floor
    const [lx, ly] = P[st.lantern], fl = 1 + .04 * Math.sin(t * 9.1) * Math.sin(t * 3.3);
    X.globalCompositeOperation = 'lighter';
    let g = X.createRadialGradient(lx, ly, 8, lx, ly, 300 * fl); g.addColorStop(0, 'rgba(244,190,110,.32)'); g.addColorStop(.4, 'rgba(244,160,80,.12)'); g.addColorStop(1, 'rgba(244,160,80,0)');
    X.fillStyle = g; X.fillRect(lx - 310, ly - 310, 620, 620);
    X.restore();
    return st;
  }

  // ---- on Clawd's stage: the illustrated rig (rig/fable_stage/mesh, engine/rig.js; RIGGING.md) --------------------------------
  // A Live2D-style mesh rig of the front-view drawing, built like Clawd's (tools/segment.py -> layers.py -> rigbuild.py, with real
  // drawing for what motion reveals: the jacket under her sleeves, the collar and hood under her hair). She dances Clawd's
  // performed channels a bar late at half amplitude on twos (sampled at 12 fps and held; no springs: Fable's rule), in unison from
  // 135, frozen from 141. Her head turns are her own (copying Clawd's turn to her on "why" would turn her away): the glance at
  // Clawd on "why". The entrance (two hops, hood up; the push) is two whole drawings registered on the rig's canvas.
  const ST = { enter: [128.25, 128.75], hood: [128.75, 129.0], dance: 129, unison: 135, freeze: 141 };
  const RIGH = 2871;                                   // her standing height in rig px (crown 69 .. soles 2940): h scales it
  const FEET = [1015, 2940], SIZE = [2048, 3072];      // the rig's origin (between her soles) and canvas
  const LEGK = (2940 - 1500) / (3700 - 1950);          // her hip height over Clawd's (translations are in Clawd's base px)
  const AMP = .5;                                      // half amplitude (Fable's ruling)
  // Clawd's performed channels -> Fable's rig parameters: angles halved (each rig's angles are from its own rest), translations
  // halved and scaled to her legs
  function mapP(q) {
    const tr = AMP * LEGK, h = n => AMP * (q[n] || 0), l = n => tr * (q[n] || 0);
    // (arm and elbow angles as seen, held through folds and windmills: clawdAt)
    const ha = n => AMP * (q['_' + n] ?? clamp(wrap(q[n] || 0), -150, 150));
    return { armL: ha('armL'), armR: ha('armR'), elbowL: ha('elbowL'), elbowR: ha('elbowR'), bodyX: h('bodyX'), bodyZ: h('bodyZ'),
      angleX: h('angleX'), angleY: h('angleY'), angleZ: h('angleZ'), hipX: h('hipX'), hipY: l('hipY'), bounce: l('bounce'),
      footLX: l('footLX'), footLY: l('footLY'), footRX: l('footRX'), footRY: l('footRY'), heelL: l('heelL'), heelR: l('heelR'),
      footLR: h('footLR'), footRR: h('footRR'), footLP: h('footLP'), footRP: h('footRP'),
      armFrontL: q.armFrontL, armFrontR: q.armFrontR, armBackL: q.armBackL, armBackR: q.armBackR };
  }
  const srcTime = tq => { const b = t2b(tq); return b >= ST.freeze ? b2t(ST.freeze) : b >= ST.unison ? tq : tq - BR; };   // a bar late, then unison, then frozen
  const wrap = v => ((v + 180) % 360 + 360) % 360 - 180;
  // Clawd's channels per drawing (cached per source), her arm and elbow angles as seen. Halving an angle is only meaningful while
  // it's clearly on one side: through a fold (near 180, the same both ways) or one of Clawd's windmills (her angles run on past
  // +-180), halving would flip Fable's forearm across. There Fable does what her grammar does anyway: she holds her last clear pose
  // and snaps to the next. Holding needs history, so the finale's drawings are filled in order from bar 124 on first use (a pure
  // function of t all the same)
  const CC = new WeakMap(), HOLD0 = Math.round(124 * BR * 12), JOINTS = ['armL', 'armR', 'elbowL', 'elbowR'];
  function clawdAt(clawdP, tq) {
    let C = CC.get(clawdP); if (!C) CC.set(clawdP, C = new Map());
    const key = Math.round(tq * 12); if (C.has(key)) return C.get(key);
    const fill = k => { const q = { ...(clawdP(k / 12) || {}) }, pv = C.get(k - 1);
      for (const n of JOINTS) { const v = wrap(q[n] || 0); q['_' + n] = Math.abs(v) <= 150 || !pv ? clamp(v, -150, 150) : pv['_' + n]; }
      C.set(k, q); return q; };
    if (key < HOLD0) return fill(key);
    let k0 = key; while (k0 > HOLD0 && !C.has(k0 - 1)) k0--;
    for (let k = k0; k < key; k++) if (!C.has(k)) fill(k);
    return fill(key);
  }
  // her parameters at song t (on twos), with her travel and hop; null before she arrives
  function pose(t, clawdP) {
    const tq = Math.floor(t * 12 + 1e-6) / 12, b = t2b(tq);
    if (b < ST.enter[0]) return null;
    if (b < ST.dance) {                                                               // two hops in, from the right
      const u = clamp((b - ST.enter[0]) / (ST.dance - ST.enter[0] - .08), 0, 1) * 2, k = Math.min(1, Math.floor(u)), f = Math.min(1, u - k);
      return { entrance: b < ST.hood[0] ? 'hoodup' : 'hoodpush', b, tq, x: 1 - (k + (k < 2 ? f : 0)) / 2, hop: Math.sin(Math.PI * f) * (u < 2 ? 1 : 0) };
    }
    const q = clawdP ? clawdAt(clawdP, srcTime(tq)) : {}, p = mapP(q);
    if (b >= 131.5 && b < 133.3) { p.angleX = -.32; p.angleZ = (p.angleZ || 0) - 2; p.eyes = 'glance'; }   // "why": she glances at Clawd (image-left)
    if ((b >= 133.3 && b < 135) || b >= ST.freeze) { p.eyes = 'smile'; p.mouth = 'smile'; }   // then the dry smile, one brow up; held at the freeze
    for (const k of [130.3, 136.4, 138.2, 139.9]) if (b >= k && b < k + .12) p.eyes = 'closed';   // blinks, two drawings
    return { p, b, tq, x: 0, hop: 0, rootX: AMP * (q.rootX || 0) };
  }
  let OFF = null, SH = null;
  // T = { x, y, h } in the coordinates X is drawing in (the card's world): the point between her feet, her standing height
  // (the finale's contract; T.s is read as the old puppet's scale if h is missing)
  function stage(X, t, T, clawdP, o = {}) {
    if (!FS.rig) return null;
    const st = pose(t, clawdP); if (!st) return null;
    const m = X.getTransform(), zs = Math.hypot(m.a, m.b), s = (T.h || T.s * 2085) / RIGH;
    const fx = T.x + (st.entrance ? (o.enter ?? 2000) * .75 * s * st.x : st.rootX * .27), fy = T.y - 60 * .75 * s * st.hop;
    const sp = m.transformPoint(new DOMPoint(fx, fy)), TT = { x: sp.x, y: sp.y, s: s * zs };
    const W0 = X.canvas.width, H0 = X.canvas.height;
    if (!OFF || OFF.width !== W0 || OFF.height !== H0) { OFF = Object.assign(document.createElement('canvas'), { width: W0, height: H0 }); SH = Object.assign(document.createElement('canvas'), { width: W0 / 2, height: H0 / 2 }); }
    const g = OFF.getContext('2d'); g.setTransform(1, 0, 0, 1, 0, 0); g.clearRect(0, 0, W0, H0);
    if (st.entrance) g.drawImage(FS[st.entrance], TT.x - FEET[0] * TT.s, TT.y - FEET[1] * TT.s, SIZE[0] * TT.s, SIZE[1] * TT.s);
    else FS.rig.draw(g, st.tq, () => st.p, TT);
    // two coloured shadows on Clawd's floor (her lights: pink from one side, cyan from the other), laid back from her feet
    const sg = SH.getContext('2d');
    X.save(); X.setTransform(1, 0, 0, 1, 0, 0);
    for (const [col, sk] of [['rgba(255,92,168,.22)', -1], ['rgba(57,223,255,.20)', 1]]) {
      sg.setTransform(1, 0, 0, 1, 0, 0); sg.globalCompositeOperation = 'copy'; sg.drawImage(OFF, 0, 0, SH.width, SH.height);
      sg.globalCompositeOperation = 'source-in'; sg.fillStyle = col; sg.fillRect(0, 0, SH.width, SH.height);
      X.save(); X.translate(sp.x, sp.y); X.transform(1, 0, sk * .32, .15, 0, 0); X.translate(-sp.x, -sp.y); X.filter = 'blur(6px)';
      X.drawImage(SH, 0, 0, W0, H0); X.restore();
    }
    X.drawImage(OFF, 0, 0);
    X.restore();
    return st;
  }

  // ---- previews and the range of motion (her alone, or beside a stand-in Clawd) -----------------------------------------------
  {
    const proxy = () => { const PA = window.CHOREO && (CHOREO.clawdF || CHOREO.clawdA); if (!PA) return null; const P0 = PA.P(); return CHOREO.clawdF ? P0 : (tt => P0(tt - 81 * BR)); };
    const bg = (top, bot) => { X.setTransform(1, 0, 0, 1, 0, 0); const g = X.createLinearGradient(0, 0, 0, H); g.addColorStop(0, top); g.addColorStop(1, bot); X.fillStyle = g; X.fillRect(0, 0, W, H); };
    const label = t => { X.setTransform(1, 0, 0, 1, 0, 0); X.fillStyle = 'rgba(255,255,255,.7)'; X.font = '24px sans-serif'; X.fillText(`song ${t.toFixed(2)}  bar ${t2b(t).toFixed(2)}`, 30, 40); };
    // the room (177.8-181), then her beside Clawd on a plain stage (181-)
    LOOPS.fablestage = t => {
      if (t < 181) {
        bg('#0f0b09', '#1d1611'); X.fillStyle = '#e8d8b8'; X.globalAlpha = .18; X.fillRect(200, 120, 1100, 620); X.globalAlpha = 1;
        X.fillStyle = '#0a0806'; X.fillRect(0, 1002, W, H - 1002); room(X, t, { x: 1654, y: 1002, s: .697 });
      } else {
        bg('#120c20', '#241840'); X.fillStyle = '#1b1430'; X.fillRect(0, 760, W, H - 760);
        const P = proxy(); stage(X, t, { x: 1250, y: 1000, h: 794 }, P);
        if (P && window.RIGS) RIGS.clawd.draw(X, t, P, { x: 700 + (P(t).rootX || 0) * .2, y: 1030, s: .2 });
      }
      label(t);
    };
    LOOPS.fablestage.len = 203;
    // her alone, large (for 100% crops), on the same clock
    LOOPS.fablestage_cu = t => { bg('#241840', '#241840'); stage(X, t, { x: 960, y: 1060, h: 1020 }, proxy(), { enter: 900 }); label(t); };
    LOOPS.fablestage_cu.len = 203;
    // the range of motion, straight into her rig (no mapping, no halving): each channel swept to and past its extremes, 1 s each
    const SWEEP = [['armL', -40, 110], ['armR', -40, 110], ['elbowL', -30, 150], ['elbowR', -30, 150], ['angleX', -1, 1], ['angleY', -1, 1],
      ['angleZ', -14, 14], ['bodyX', -1, 1], ['bodyZ', -8, 8], ['hipX', -1.2, 1.2], ['hipY', -30, 60], ['footLX', -120, 120], ['footRX', -120, 120],
      ['footLY', 0, 60], ['footRY', 0, 60]];
    LOOPS.fablestage_rom = t => {
      bg('#241840', '#241840');
      const k = Math.min(SWEEP.length - 1, Math.floor(t)), [ch, lo, hi] = SWEEP[k], u = .5 - .5 * Math.cos(2 * Math.PI * (t - k)), v = lo + (hi - lo) * u;
      if (FS.rig) FS.rig.draw(X, t, () => ({ [ch]: v }), { x: 960, y: 1060, s: 1020 / RIGH });
      X.setTransform(1, 0, 0, 1, 0, 0); X.fillStyle = 'rgba(255,255,255,.8)'; X.font = '28px sans-serif'; X.fillText(`${ch} ${v.toFixed(2)}`, 40, 60);
    };
    LOOPS.fablestage_rom.len = SWEEP.length;
    // the range-of-motion test (tools/romrun.py projects/tsuzuku --name fablerom): every control alone, the combinations the finale
    // makes, the extremes, and her performance of Clawd's finale through the mapping; 'rest' segments are the baselines. Frames:
    // full body, waist-up for the arms, the head large for the head's own controls
    const sw = u => Math.sin(2 * Math.PI * u), up = u => .5 - .5 * Math.cos(2 * Math.PI * u), segs = [];
    const add = (name, dur, frame, fn) => segs.push({ name, dur, frame, fn });
    add('rest full', 1, 'full', () => ({})); add('rest mid', 1, 'mid', () => ({})); add('rest head', 1, 'head', () => ({}));
    for (const sd of ['L', 'R']) {
      add(`arm${sd} out`, 2, 'mid', u => ({ ['arm' + sd]: 110 * up(u) }));
      add(`arm${sd} in`, 1.5, 'mid', u => ({ ['arm' + sd]: -40 * up(u) }));
      add(`elbow${sd}`, 2, 'mid', u => ({ ['elbow' + sd]: 150 * up(u) }));
      add(`elbow${sd} raised`, 2, 'mid', u => ({ ['arm' + sd]: 80, ['elbow' + sd]: 140 * up(u) }));
      add(`elbow${sd} back`, 1.5, 'mid', u => ({ ['elbow' + sd]: -40 * up(u) }));
    }
    add('arms both', 2, 'mid', u => ({ armL: 90 * up(u), armR: 90 * up(u), elbowL: 60 * up(u), elbowR: 60 * up(u) }));
    add('arms front', 2, 'mid', u => ({ armL: 40 * up(u), armR: 40 * up(u), elbowL: 130 * up(u), elbowR: 130 * up(u), armFrontL: 1, armFrontR: 1 }));
    add('turn', 2, 'head', u => ({ angleX: .6 * sw(u) })); add('tilt', 2, 'head', u => ({ angleZ: 12 * sw(u) }));
    add('nod', 2, 'head', u => ({ angleY: .8 * sw(u) })); add('turn tilt', 2, 'head', u => ({ angleX: .5 * sw(u), angleZ: 8 * Math.cos(2 * Math.PI * u) }));
    add('body x', 2, 'full', u => ({ bodyX: .8 * sw(u) })); add('body z', 2, 'full', u => ({ bodyZ: 8 * sw(u) }));
    add('hips', 2, 'full', u => ({ hipX: 1.2 * sw(u) })); add('dip', 2, 'full', u => ({ hipY: 50 * up(u) }));
    add('step L', 2, 'full', u => ({ footLX: -120 * up(u), footLY: 40 * Math.max(0, sw(u)) }));
    add('step R', 2, 'full', u => ({ footRX: 120 * up(u), footRY: 40 * Math.max(0, sw(u)) }));
    add('side step', 2, 'full', u => ({ footLX: -100 * up(u), footRX: -60 * up(u), hipX: -.8 * up(u) }));
    const perf = b => { const PF = window.CHOREO && CHOREO.clawdF && CHOREO.clawdF.P(), st = PF && pose(Math.floor(b2t(b) * 12 + 1e-6) / 12, PF); return st && st.p ? st.p : {}; };   // (as the finale plays her)
    add('perform 129-135', 6 * BR, 'full', u => perf(129 + 6 * u));
    add('perform 135-141', 6 * BR, 'full', u => perf(135 + 6 * u));
    let T0 = 0; for (const g of segs) { g.t0 = T0; T0 += g.dur; }
    window.ROMSETS = window.ROMSETS || {}; window.ROMSETS.fablerom = segs.map(g => [g.name, +g.t0.toFixed(3), +(g.t0 + g.dur).toFixed(3), g.frame]);
    const FR = { full: { x: 960, y: 1060, s: 1020 / RIGH }, mid: { x: 960, y: 540 + (2940 - 1150) * .52, s: .52 }, head: { x: 960, y: 560 + (2940 - 420) * .95, s: .95 } };
    const romDraw = (bgc, id) => t => {
      X.setTransform(1, 0, 0, 1, 0, 0); X.fillStyle = bgc; X.fillRect(0, 0, W, H);
      const g = segs.find(q => t >= q.t0 && t < q.t0 + q.dur) || segs[segs.length - 1], u = Math.min(1, Math.max(0, (t - g.t0) / g.dur));
      const q = { breath: .5, ...g.fn(u) };
      window.RIG_IDPASS = id; if (FS.rig) FS.rig.draw(X, t, () => q, FR[g.frame]); window.RIG_IDPASS = false;
    };
    LOOPS.fablerom = romDraw('#201d33', false); LOOPS.fableromid = romDraw('#000000', true);
    LOOPS.fablerom.len = LOOPS.fableromid.len = T0;
  }
  return { load, room, stage, pose, mapP, clawdAt, roomState, ROOM, ST, R, FS };
})();
