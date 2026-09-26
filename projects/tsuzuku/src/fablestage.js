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
  const S = { meta: null, img: {} }, R = { meta: null, img: {} }, BUF = {};
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v)), D2R = Math.PI / 180;
  async function load(base = 'rig/fable_stage/') {
    const get = f => new Promise((ok, no) => { const i = new Image(); i.onload = () => ok(i); i.onerror = no; i.src = base + f; });
    S.meta = await (await fetch(base + 'stage/meta.json')).json(); R.meta = await (await fetch(base + 'room/meta.json')).json();
    await Promise.all([...Object.entries(S.meta.parts).map(async ([k, f]) => { S.img[k] = await get('stage/' + f); }),
                       ...Object.entries(R.meta.drawings).map(async ([k, f]) => { R.img[k] = await get('room/' + f); })]);
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

  // ---- on Clawd's stage ---------------------------------------------------------------------------------------------------
  const ST = { enter: [128.25, 128.75], hood: [128.75, 129.0], dance: 129, unison: 135, freeze: 141 };
  const K = .37;                               // Clawd's rig px -> hers (her drawing is ~.74 of Clawd's scale) x half amplitude
  const REST = 10;                             // Clawd's arms rest ~10 deg out; hers are drawn so
  function face(b) {
    if (b >= 131.5 && b < 133.3) return 'head_why';                                   // Clawd turns to her on "why": she's there
    if (b >= 133.3 && b < 135) return 'head_smile';                                   // one raised eyebrow
    if (b >= ST.freeze) return 'head_smile';
    for (const k of [130.3, 136.4, 138.2, 139.9]) if (b >= k && b < k + .12) return 'head_closed';   // blinks, two drawings
    return 'head';
  }
  function pose(t, clawdP) {
    const tq = Math.floor(t * 12 + 1e-6) / 12, b = t2b(tq);
    const p = { b, x: 0, hop: 0, hood: 'back', face: face(b), q: {} };
    if (b < ST.enter[0]) return null;                                                 // not arrived yet
    if (b < ST.dance) {                                                               // two hops in, from the right
      const u = clamp((b - ST.enter[0]) / (ST.dance - ST.enter[0] - .08), 0, 1) * 2, k = Math.min(1, Math.floor(u)), f = Math.min(1, u - k);
      p.x = 1 - (k + (k < 2 ? f : 0)) / 2; p.hop = Math.sin(Math.PI * f) * (u < 2 ? 1 : 0);
      p.lift = k === 0 ? 'R' : 'L';
      p.hood = b < ST.hood[0] ? 'up' : 'push';
      return p;
    }
    const src = b >= ST.freeze ? b2t(ST.freeze) : b >= ST.unison ? tq : tq - BR;   // a bar late, then unison, then frozen
    p.q = clawdP ? clawdP(src) || {} : {};
    return p;
  }
  // the pieces, in drawing px: the pelvis (hips shift and bounce), the hakama's legs swinging to where the feet stand, the torso
  // leaning over the waist, the head tilting on the neck, each arm turning at its three rivets
  function assemble(g, p) {
    const [w, h] = S.meta.size, J = S.meta.joints, q = p.q, I = S.img;
    const hx = K * 140 * clamp(q.hipX || 0, -1.3, 1.3), dy = K * ((q.hipY || 0) + (q.bounce || 0));
    const fL = [K * (q.footLX || 0), -K * (q.footLY || 0)], fR = [K * (q.footRX || 0), -K * (q.footRY || 0)];
    if (p.lift === 'L') fL[1] -= 40 * p.hop; if (p.lift === 'R') fR[1] -= 40 * p.hop;
    const img = (k, rot, piv, pre) => { g.save(); if (pre) pre(); if (rot) { g.translate(piv[0], piv[1]); g.rotate(rot * D2R); g.translate(-piv[0], -piv[1]); } g.drawImage(I[k], 0, 0, w, h); g.restore(); };
    const legLen = J.feet[1] - J.hip_L[1];
    // under-skirt, feet, legs, the obi piece
    g.save(); g.translate(hx, dy); g.drawImage(I.skirt_under, 0, 0, w, h); g.restore();
    img('foot_L', 0, null, () => g.translate(fL[0], fL[1])); img('foot_R', 0, null, () => g.translate(fR[0], fR[1]));
    for (const [s, f] of [['L', fL], ['R', fR]]) {
      const piv = J['hip_' + s], th = -Math.atan2(f[0] - hx, legLen) / D2R;
      img('leg_' + s, th, [piv[0] + hx, piv[1] + dy], () => g.translate(hx, dy));
    }
    img('skirt_top', -2.5 * (q.hipX || 0), [J.waist[0] + hx, J.waist[1] + dy], () => g.translate(hx, dy));
    // the torso group
    g.save(); g.translate(hx * .8 + K * 50 * (q.bodyX || 0), dy);
    g.translate(J.waist[0], J.waist[1]); g.rotate(.5 * clamp(q.bodyZ || 0, -12, 12) * D2R); g.translate(-J.waist[0], -J.waist[1]);
    g.drawImage(I.body, 0, 0, w, h);
    const hood = p.hood === 'up' ? 'hoodup' : p.hood === 'push' ? 'hoodpush' : null;
    g.save(); g.translate(K * 14 * (q.angleX || 0), K * 12 * (q.angleY || 0));
    g.translate(J.neck[0], J.neck[1]); g.rotate(.5 * clamp(q.angleZ || 0, -20, 20) * D2R); g.translate(-J.neck[0], -J.neck[1]);
    g.drawImage(I[hood || p.face], 0, 0, w, h); g.restore();
    for (const s of ['L', 'R']) {
      if (hood === 'hoodpush' && s === 'L') continue;                                 // (that drawing raises this arm)
      const sg = s === 'L' ? 1 : -1, a = sg * .5 * clamp((q['arm' + s] ?? REST) - REST, -70, 160), e = sg * .5 * clamp(q['elbow' + s] || 0, -30, 220);
      const Sh = J['shoulder_' + s], E = J['elbow_' + s], Wr = J['wrist_' + s];
      g.save(); g.translate(Sh[0], Sh[1]); g.rotate(a * D2R); g.translate(-Sh[0], -Sh[1]);
      g.drawImage(I['upper_' + s], 0, 0, w, h);
      g.translate(E[0], E[1]); g.rotate(e * D2R); g.translate(-E[0], -E[1]);
      g.drawImage(I['fore_' + s], 0, 0, w, h);
      g.translate(Wr[0], Wr[1]); g.rotate(clamp(.25 * e, -14, 14) * D2R); g.translate(-Wr[0], -Wr[1]);
      g.drawImage(I['hand_' + s], 0, 0, w, h);
      g.restore();
    }
    if (hood === 'hoodpush') g.drawImage(I.hoodpush, 0, 0, w, h);
    g.restore();
  }
  const PAD = 420;                                                                     // room round the drawing for arms and travel
  function figure(p) {
    const key = JSON.stringify([p.hood, p.face, p.lift, +p.hop.toFixed(3), ...['hipX', 'hipY', 'bounce', 'footLX', 'footLY', 'footRX', 'footRY', 'bodyX', 'bodyZ',
      'angleX', 'angleY', 'angleZ', 'armL', 'armR', 'elbowL', 'elbowR'].map(k => +(p.q[k] || 0).toFixed(2))]);
    if (BUF.key === key) return BUF;
    const [w, h] = S.meta.size;
    if (!BUF.c) { BUF.c = Object.assign(document.createElement('canvas'), { width: w + 2 * PAD, height: h + PAD }); BUF.sh = Object.assign(document.createElement('canvas'), { width: (w + 2 * PAD) / 2, height: (h + PAD) / 2 }); }
    const g = BUF.c.getContext('2d'); g.setTransform(1, 0, 0, 1, 0, 0); g.clearRect(0, 0, BUF.c.width, BUF.c.height);
    g.translate(PAD, PAD); assemble(g, p);
    const s = BUF.sh.getContext('2d'); s.setTransform(1, 0, 0, 1, 0, 0); s.globalCompositeOperation = 'copy'; s.drawImage(BUF.c, 0, 0, BUF.sh.width, BUF.sh.height);
    s.globalCompositeOperation = 'source-in'; s.fillStyle = '#fff'; s.fillRect(0, 0, BUF.sh.width, BUF.sh.height);   // (her silhouette, for the shadows)
    BUF.key = key; return BUF;
  }
  function stage(X, t, T, clawdP, o = {}) {
    if (!S.meta) return null;
    const p = pose(t, clawdP); if (!p) return null;
    const J = S.meta.joints, B = figure(p), travel = (o.enter ?? 1400) * p.x + K * (p.q.rootX || 0), lift = -60 * p.hop;
    X.save(); X.translate(T.x, T.y); X.scale(T.s, T.s); X.translate(travel, 0);
    // two coloured shadows on Clawd's floor (her lights: pink from one side, cyan from the other), laid back from her feet
    for (const [col, sk] of [['rgba(255,92,168,.22)', -1], ['rgba(57,223,255,.20)', 1]]) {
      X.save(); X.transform(1, 0, sk * .32, .15, 0, 0); X.globalCompositeOperation = 'source-over';   // (laid back up the floor, squashed, sheared)
      X.filter = 'blur(6px)';
      const c = BUF.tint || (BUF.tint = Object.assign(document.createElement('canvas'), { width: B.sh.width, height: B.sh.height })), tg = c.getContext('2d');
      tg.globalCompositeOperation = 'copy'; tg.drawImage(B.sh, 0, 0); tg.globalCompositeOperation = 'source-in'; tg.fillStyle = col; tg.fillRect(0, 0, c.width, c.height);
      X.drawImage(c, -J.feet[0] - PAD, -J.feet[1] - PAD, B.c.width, B.c.height); X.restore();
    }
    X.translate(-J.feet[0] - PAD, -J.feet[1] - PAD + lift);
    X.drawImage(B.c, 0, 0);
    X.restore();
    return p;
  }

  // ---- test: the room (177.8-181), then her on a plain stage beside Clawd (181-202.6). Clawd's final-chorus choreography
  // isn't built yet: a stand-in plays world A's chorus 1 shifted so its sideways step lands on bar 135 (world A's 54)
  {
    const proxy = () => { const PA = window.CHOREO && CHOREO.clawdA && CHOREO.clawdA.P(); return PA ? (tt => PA(tt - 81 * BR)) : null; };
    LOOPS.fablestage = t => {
      X.setTransform(1, 0, 0, 1, 0, 0);
      if (t < 181) {
        const g = X.createLinearGradient(0, 0, 0, H); g.addColorStop(0, '#0f0b09'); g.addColorStop(1, '#1d1611'); X.fillStyle = g; X.fillRect(0, 0, W, H);
        X.fillStyle = '#e8d8b8'; X.globalAlpha = .18; X.fillRect(200, 120, 1100, 620); X.globalAlpha = 1;          // (the window)
        X.fillStyle = '#0a0806'; X.fillRect(0, 1002, W, H - 1002);
        room(X, t, { x: 1654, y: 1002, s: .697 });                                   // (B9's end at CAM_WIDE: feet 1654,1002, 812 px tall)
      } else {
        const g = X.createLinearGradient(0, 0, 0, H); g.addColorStop(0, '#120c20'); g.addColorStop(1, '#241840'); X.fillStyle = g; X.fillRect(0, 0, W, H);
        X.fillStyle = '#1b1430'; X.fillRect(0, 760, W, H - 760);
        const P = proxy();
        if (P && window.RIGS) RIGS.clawd.draw(X, t, P, { x: 720 + (P(t).rootX || 0) * .27, y: 1040, s: .27 });
        stage(X, t, { x: 1230, y: 985, s: .25 }, P);
      }
      X.fillStyle = 'rgba(255,255,255,.7)'; X.font = '24px sans-serif'; X.fillText(`song ${t.toFixed(2)}  bar ${t2b(t).toFixed(2)}`, 30, 40);
    };
    LOOPS.fablestage.len = 203;
    // her alone, large (for 100% crops), on the same clock
    LOOPS.fablestage_cu = t => {
      X.setTransform(1, 0, 0, 1, 0, 0); X.fillStyle = '#241840'; X.fillRect(0, 0, W, H);
      stage(X, t, { x: 960, y: 1060, s: .45 }, proxy(), { enter: 900 });
    };
    LOOPS.fablestage_cu.len = 203;
    // the range of motion: each channel swept to (and past) its extremes, one per second, her alone
    const SWEEP = [['armL', -60, 200], ['armR', -60, 200], ['elbowL', 0, 240], ['elbowR', 0, 240], ['hipX', -1.3, 1.3], ['bodyZ', -12, 12],
                   ['angleZ', -20, 20], ['footLX', -300, 300], ['footRY', 0, 120], ['hipY', -60, 80]];
    LOOPS.fablestage_rom = t => {
      X.setTransform(1, 0, 0, 1, 0, 0); X.fillStyle = '#241840'; X.fillRect(0, 0, W, H);
      const k = Math.min(SWEEP.length - 1, Math.floor(t)), [ch, lo, hi] = SWEEP[k], u = .5 - .5 * Math.cos(2 * Math.PI * (t - k));
      const P = () => ({ armL: 10, armR: 10, [ch]: lo + (hi - lo) * u });
      stage(X, b2t(136), { x: 960, y: 1060, s: .45 }, P);                            // (bar 136: in unison, so P(t) is read as is)
      X.fillStyle = 'rgba(255,255,255,.8)'; X.font = '28px sans-serif'; X.fillText(`${ch} ${(lo + (hi - lo) * u).toFixed(1)}`, 40, 60);
    };
    LOOPS.fablestage_rom.len = SWEEP.length;
    // the same at 100% of the drawing, framed on the joint each channel moves (for the crops)
    const FOCUS = { armL: 'shoulder_L', armR: 'shoulder_R', elbowL: 'elbow_L', elbowR: 'elbow_R', hipX: 'hip_L', bodyZ: 'waist', angleZ: 'neck', footLX: 'feet', footRY: 'feet', hipY: 'waist' };
    LOOPS.fablestage_rom100 = t => {
      X.setTransform(1, 0, 0, 1, 0, 0); X.fillStyle = '#241840'; X.fillRect(0, 0, W, H);
      const k = Math.min(SWEEP.length - 1, Math.floor(t)), [ch, lo, hi] = SWEEP[k], u = .5 - .5 * Math.cos(2 * Math.PI * (t - k));
      const P = () => ({ armL: 10, armR: 10, [ch]: lo + (hi - lo) * u }), J = S.meta.joints, f = J[FOCUS[ch]];
      stage(X, b2t(136), { x: 960 - (f[0] - J.feet[0]), y: 540 - (f[1] - J.feet[1]) + (ch.startsWith('foot') ? -300 : 0), s: 1 }, P);
      X.fillStyle = 'rgba(255,255,255,.8)'; X.font = '28px sans-serif'; X.fillText(`${ch} ${(lo + (hi - lo) * u).toFixed(1)}`, 40, 60);
    };
    LOOPS.fablestage_rom100.len = SWEEP.length;
  }
  return { load, room, stage, pose, roomState, ROOM, ST, S, R };
})();
