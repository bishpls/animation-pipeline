// fableroom.js: Fable in her room, 177.8-181 (the final chorus's fold, CLAWDWORLD.md "F"): she sets the lantern on her cushion,
// turns, and walks out right while the camera pushes through the window. A drop-in for FABLESTAGE.room (same signature):
//   FABLEROOM.room(X, t, T, o)   T = { x, y, s }: her standing feet on screen, screen px per drawing px (the room drawings of
//                                rig/fable_stage/room: 1024x1280, feet 559,1218.5). Returns the state drawn.
// The drawings (rig/fable_room: GPT Image edits of the room drawings, keyed and registered on their canvas by build.py) are whole
// drawings swapped on twos (12 a second): puppet timing, clean poses and holds, no tweens. The props (the cushion; from the kneel
// on, the lantern and its stick where she set them) are drawn once, underneath, so they never move.
//   178.25  she bows and lowers the lantern (down), kneels and sets it on the cushion (setdown, held), rises with empty hands
//           (rise), and stands (empty)
//   179.0   the turn, toward us, the eyes and head leading: three-quarter (turn_l), front (a small hold), three-quarter right
//   179.33  the walk out right: contact (held: the geta clack), trail, passing, reach (held); 0.5 s a step. Every planted
//           geta is pinned to its footprint on the floor: the body advances, the planted foot stays put.
//   FABLEROOM.ending(X, t, T, o)  the room ending (Michael + Fable, 177.8-201.5), same T; o.P = Clawd's performed channels
//                                (finale.js): she stays in the room at her place, lantern in hand, watching the window. See below.
// Bars are song bars (170 bpm).
const FABLEROOM = (() => {
  const R = { meta: null, img: {} }, TW = 1 / 12;
  async function load(base = 'rig/fable_room/room/') {
    const get = f => new Promise((ok, no) => { const i = new Image(); i.onload = () => ok(i); i.onerror = no; i.src = base + f; });
    R.meta = await (await fetch(base + 'meta.json')).json();
    await Promise.all(Object.entries(R.meta.drawings).map(async ([k, d]) => { R.img[k] = await get(d.file); }));
    plan();
    const eb = 'rig/fable_room/ending/', eget = f => new Promise((ok, no) => { const i = new Image(); i.onload = () => ok(i); i.onerror = no; i.src = eb + f; });
    E.meta = await (await fetch(eb + 'meta.json')).json();
    await Promise.all(Object.entries(E.meta.drawings).map(async ([k, d]) => { E.img[k] = await eget(d.file); }));
    endPlace();
    try { Q.base = await get3('base_keyed.png'); } catch (e) { Q.base = null; }   // (the three-quarter rig's base: preview only)
  }
  // ---- the three-quarter rig (rig/fable_3q): WIP. LOOPS.room3q_film: the film with the static base drawing in her place
  const Q = { base: null, FEET: [1390, 3745], K: 1140.5 / 3650 }, get3 = f => new Promise((ok, no) => { const i = new Image(); i.onload = () => ok(i); i.onerror = no; i.src = 'rig/fable_3q/' + f; });
  function static3q(X, T) {
    const s = T.s * Q.K; X.save(); X.globalCompositeOperation = 'source-over'; X.globalAlpha = 1;
    X.drawImage(Q.base, T.x - Q.FEET[0] * s, T.y - Q.FEET[1] * s, Q.base.width * s, Q.base.height * s); X.restore();
  }
  LOOPS.room3q_film = t => { window.FABLE3Q_STATIC = true; try { LOOPS.film(t); } finally { window.FABLE3Q_STATIC = false; } };
  LOOPS.room3q_film.len = 209.65;

  // ---- the timeline (slots of 1/12 s from the song clock). [drawing, slots]; the props and lantern follow the drawing
  const T0 = 178.25;                                                       // (the set-down starts on the drawing after 178.2)
  const SETDOWN = [['bend', 1], ['down', 2], ['setdown', 3], ['rise', 1], ['rise2', 1], ['empty', 1]];
  const TURN = [['turn_l', 1], ['front', 2], ['turn_r', 1]];
  // the walk: two steps a cycle, 0.5 s a step: contact (held: the geta clack), trail, passing, reach (held: the geta placed).
  // kind 'c' (contact): x pinned by the back geta to the footprint it stood on, y by the front geta (it lands flat; both geta
  // are on the floor line in these two drawings); the front geta's footprint is the next one. kind 's' (stance): the planted geta
  // (index into the drawing's geta, sorted by x) pinned to the current footprint. (walk_c1/c2/d1 float the back geta 40 px:
  // unused.) The trail and reach drawings follow the step of the contact before them (s2/p2 the far leg planted, s1/p1 the near)
  const CYCLE = [['walk_u1', 2, 'c'], ['walk_s2', 1, 's', 0], ['walk_m1', 1, 's', 0], ['walk_p2', 2, 's', 0],
                 ['walk_u2', 2, 'c'], ['walk_s1', 1, 's', 1], ['walk_m1', 1, 's', 0], ['walk_p1', 2, 's', 0]];
  const STEPS = 3;                                                          // (cycles planned: she's out of frame long before)
  // placement fixes (drawing px), measured on the renders (rig/fable_room/slide.py): the standing foot stays where she stood.
  // 'down' is drawn 24.5 low; 'rise' steps her front foot 82 px forward of it; the turn is pinned on its pivot foot
  const FIX = { bend: [8, 9], down: [11.5, -24.5], rise: [55, 6.5], rise2: [19, -13.5], turn_l: [8.5, -1.5], front: [7, 3.5], turn_r: [59, 3] };
  const A0 = 25;                                                            // the first footprint: the pivot geta's front tooth once
                                                                            //  it turns to point right (a quarter geta ahead)
  let SEQ = null;
  function plan() {
    const M = R.meta.drawings, FL = R.meta.points.feet[1], g = n => M[n].geta;
    SEQ = []; let k = Math.round(T0 * 12);
    const push = (d, slots, ox = 0, oy = 0, extra = {}) => { SEQ.push({ k, d, ox, oy, ...extra }); k += slots; };
    for (const [d, n] of SETDOWN) push(d, n, ...(FIX[d] || [0, 0]), { props: d === 'down' || d === 'bend' ? 'props_hold' : 'props_down' });
    for (const [d, n] of TURN) push(d, n, ...FIX[d], { props: 'props_down' });
    // the footprints (world x of the planted geta's front tooth, drawing px); the first is the pivot foot of the turn
    let foot = g('turn_r')[0].toe[0] + FIX.turn_r[0] + A0, step = 0;
    for (let c = 0; c < STEPS; c++) for (const [d, n, kind, i] of CYCLE) {
      const G = g(d);
      if (kind === 'c') {
        const ox = foot - G[0].toe[0], oy = FL - G[1].toe[1];
        push(d, n, ox, oy, { props: 'props_down', walk: step, plant: [foot, FL], land: [G[1].toe[0] + ox, FL] });
        foot = G[1].toe[0] + ox; step++;                                    // (the front geta's footprint: the new stance)
      } else push(d, n, foot - G[i].toe[0], FL - G[i].toe[1], { props: 'props_down', walk: step, plant: [foot, FL] });
    }
    SEQ.push({ k, d: null, props: 'props_down' });                          // (gone)
    return SEQ;
  }
  function state(t) {
    if (!SEQ) return null;
    const k = Math.floor(t * 12 + 1e-6);
    if (k < SEQ[0].k) return { d: 'hold', ox: 0, oy: 0, props: 'props_hold', lantern: 'lantern_hand', k };
    let i = 0; while (i + 1 < SEQ.length && k >= SEQ[i + 1].k) i++;
    const s = SEQ[i];
    return { ...s, lantern: s.d === 'down' ? 'lantern_low' : s.d === 'bend' ? 'lantern_bend' : 'lantern_down' };
  }

  function room(X, t, T, o = {}) {
    if (!R.meta) return null;
    const st = state(t), [w, h] = R.meta.size, P = R.meta.points;
    X.save(); X.translate(T.x, T.y); X.scale(T.s, T.s); X.translate(-P.feet[0], -P.feet[1]);
    X.globalCompositeOperation = 'source-over'; X.globalAlpha = 1;
    if (!o.figureOnly) X.drawImage(R.img[st.props], 0, 0, w, h);
    if (st.d) X.drawImage(R.img[st.d], st.ox, st.oy, w, h);
    if (o.figureOnly) { X.restore(); return st; }
    // the lantern's warm light (in her hand, lowered, then on the cushion): on her sleeve, the cushion and the floor
    const carried = st.lantern !== 'lantern_down' && st.lantern !== 'lantern_hand';          // (in the drawing: moves with it)
    const lx = P[st.lantern][0] + (carried ? st.ox : 0), ly = P[st.lantern][1] + (carried ? st.oy : 0), fl = 1 + .04 * Math.sin(t * 9.1) * Math.sin(t * 3.3);
    X.globalCompositeOperation = 'lighter';
    const gr = X.createRadialGradient(lx, ly, 8, lx, ly, 300 * fl);
    gr.addColorStop(0, 'rgba(244,190,110,.32)'); gr.addColorStop(.4, 'rgba(244,160,80,.12)'); gr.addColorStop(1, 'rgba(244,160,80,0)');
    X.fillStyle = gr; X.fillRect(lx - 310, ly - 310, 620, 620);
    X.restore();
    return st;
  }

  // ---- preview: the room figure on a plain dark ground, on the song clock (177.8-181.5), at the room's wide camera (feet
  // 1654,1002, .697 screen px per drawing px: B9's end), camera still. ?loop=fableroom
  const WIDE = { x: 1654, y: 1002, s: .697 };
  LOOPS.fableroom = t => {
    X.setTransform(1, 0, 0, 1, 0, 0);
    const gr = X.createLinearGradient(0, 0, 0, H); gr.addColorStop(0, '#0f0b09'); gr.addColorStop(1, '#1d1611'); X.fillStyle = gr; X.fillRect(0, 0, W, H);
    X.fillStyle = '#e8d8b8'; X.globalAlpha = .12; X.fillRect(200, 120, 1100, 620); X.globalAlpha = 1;          // (the window)
    X.fillStyle = '#0a0806'; X.fillRect(0, 1002, W, H - 1002);
    const st = room(X, Math.max(177.8, t), WIDE);
    X.fillStyle = 'rgba(255,255,255,.7)'; X.font = '24px sans-serif';
    X.fillText(`song ${t.toFixed(3)}  bar ${(t / (60 / 170 * 4)).toFixed(2)}  ${st ? st.d || '(gone)' : ''}`, 30, 40);
  };
  LOOPS.fableroom.len = 181.5;
  // the same, with every planted footprint marked (the check for sliding) and the drawing's name
  LOOPS.fableroom_feet = t => {
    LOOPS.fableroom(t);
    const st = state(t); if (!st || !SEQ) return;
    const P = R.meta.points, sx = x => WIDE.x + (x - P.feet[0]) * WIDE.s, sy = y => WIDE.y + (y - P.feet[1]) * WIDE.s;
    X.save(); X.lineWidth = 2;
    for (const s of SEQ) if (s.plant) { X.strokeStyle = 'rgba(0,255,200,.5)'; X.beginPath(); X.moveTo(sx(s.plant[0]), sy(P.feet[1]) - 14); X.lineTo(sx(s.plant[0]), sy(P.feet[1]) + 14); X.stroke(); }
    if (st.plant) { X.strokeStyle = '#ff3060'; X.beginPath(); X.arc(sx(st.plant[0]), sy(st.plant[1]), 10, 0, 7); X.stroke(); }
    X.restore();
  };
  LOOPS.fableroom_feet.len = 181.5;
  // the same figure standing mid-frame, so the whole walk stays in view (the check for the walk; not the shot)
  LOOPS.fableroom_mid = t => {
    X.setTransform(1, 0, 0, 1, 0, 0); X.fillStyle = '#1a1512'; X.fillRect(0, 0, W, H); X.fillStyle = '#0a0806'; X.fillRect(0, 1002, W, H - 1002);
    const T = { x: 560, y: 1002, s: .697 }, st = room(X, Math.max(177.8, t), T), P = R.meta.points;
    const sx = x => T.x + (x - P.feet[0]) * T.s, sy = T.y;
    X.save(); X.lineWidth = 2;
    for (const s of SEQ || []) if (s.plant) { X.strokeStyle = 'rgba(0,255,200,.45)'; X.beginPath(); X.moveTo(sx(s.plant[0]), sy - 12); X.lineTo(sx(s.plant[0]), sy + 12); X.stroke(); }
    if (st && st.plant) { X.strokeStyle = '#ff3060'; X.beginPath(); X.arc(sx(st.plant[0]), sy, 9, 0, 7); X.stroke(); }
    X.restore();
    X.fillStyle = 'rgba(255,255,255,.7)'; X.font = '24px sans-serif'; X.fillText(`song ${t.toFixed(3)}  ${st ? st.d || '(gone)' : ''}`, 30, 40);
  };
  LOOPS.fableroom_mid.len = 181.5;
  // the figure alone on flat green at the mid-frame placement (rig/fable_room/slide.py keys these frames and tracks the geta)
  LOOPS.fableroom_key = t => {
    X.setTransform(1, 0, 0, 1, 0, 0); X.fillStyle = '#00ff00'; X.fillRect(0, 0, W, H);
    room(X, Math.max(177.8, t), { x: 560, y: 1002, s: .697 }, { figureOnly: true });
  };
  LOOPS.fableroom_key.len = 181.5;

  // =============================================================================================================== the ending
  // The room ending (Michael + Fable; the final chorus, 177.8-201.3). She stays at her place beside the butai, in profile facing the
  // window, and she's moved by it (Michael, after v6: "sullen... at odds with the finale"; Fable's arc). Every standing drawing is
  // hold with only the head, the face or the free arm pasted in (rig/fable_room/build.py ending); the lantern is a prop, its stick
  // fixed in her fist and the lantern swinging on its ring. Twos, snaps and holds; small code offsets (the bounce) only.
  //   177.8   hood up, the head following Clawd in the card a bar late (small), the face at rest.
  //   182.12  the drop: F-A, "the corner" (the mouth's corner up, the eye bright). Head bobs on her pulse (the half-note), small
  //           (a lift); from 185.7 the lantern swings with them, +-6 degrees.
  //   187.67  "why" (Clawd looks out at her at 187.62): the hood push, the free (near) hand: rising, to the rim, the hood sliding
  //           back, the hood down with her hand at the back of her head. F-B, "the eyebrow" (the dry, knowing half-smile), revealed.
  //   188.76  two claps with the hall before its "SO-RE-KA-RA?!" (189.11): the free hand to the lantern wrist (the lantern stays).
  //   189.08  the bobs grow (a dip on the pulse); F-B.
  //   190.588 the step toward the window (past the cushion's near side), landing on the downbeat of bar 135 with a bounce (a dip,
  //           then up: a squash about her soles, feet planted); the trailing foot closes at 190.941.
  //   191.25  F-C, "the smile" (lips closed, eyes open); the bobs are full (a dip on the pulse, a lift between).
  //   193.33  the page-wipe on "Turn the page" (mekutte, 193.39), with Clawd: the free hand up and across toward the window, held,
  //           back.
  //   197.24  claps, two before each "and then" (197.59, 198.21, 198.89), on the eighths before the call.
  //   199.0   the hit: the lantern raised overhead (r_half, r_up: snapped on the dash, 199.07), F-D, "the hit": an open smile, eyes
  //           open, at the window ("I'd still like to see"). Held, frozen with the card, through the ring-out.
  //   200.58  she lowers it (r_half, then standing) and stays (Fable, after v7: no walk-off): F-C, watching the doors close on the
  //           frozen card (201.5-202.4), the lantern settling on its ring, still, lit, to the outro's clack at 202.59. (The turn,
  //           glance and walk drawings stay in rig/fable_room/ending for the record; OFF is unused.)
  const E = { meta: null, img: {}, head: null, P: null }, BR = 60 / 170 * 4, BEAT = BR / 4, EIGHTH = BR / 8;
  const sl = t => Math.floor(t * 12 + 1e-6);
  const EK = { start: 177.8, drop: 182.1176, swing: 185.7, push: 187.6667, stepK: 190.5834, close: 190.9167, smile: 191.25,
               wipe: 193.3334, hit: 199.0, lower: 200.5834, freeze: 199.07 };
  const PULSE = BR / 2;                                                // her pulse: the half-note
  const CALLS1 = [189.111], CALLS2 = [197.591, 198.211, 198.891];      // (the hall's calls: two claps on the eighths before each)
  const CLAPS = [...CALLS1, ...CALLS2].flatMap(c => [c - 2 * EIGHTH, c - EIGHTH]);
  const PUSH = [['push0.A', 2], ['push1.A', 2], ['push1b.A', 1], ['push2.B', 1], ['push2b.B', 1], ['push3.B', 2], ['wipe1.B', 2]];   // (the hood's cloth on twos, v7; hood down from push2)
  const WIPE = [['wipe1.C', 2], ['wipe2.C', 5], ['wipe1.C', 2]];
  const OFF = [['r_half', 1], ['d.C', 1], ['turn1.C', 1], ['turn2.C', 1], ['wc1g', 2], ['wp1.C', 1], ['wc2.C', 2], ['wp1b', 2]];
  const FL = 1218.5, D_NEAR = 499, D_FAR_Y = 1194.5;                 // (hold's near geta tip, its far geta's sole: measured)
  const PLACE = {};                                                    // drawing px offsets of the placed drawings
  function endPlace() {
    const M = E.meta.drawings, G = n => M[n].geta, bot = n => Math.max(...G(n).map(g => g.box[3])), cx = g => (g.box[0] + g.box[2]) / 2;
    // the step: the far foot stays where it stood (its tip, its sole); the near foot lands one step toward the window, on the
    // floor in front of the cushion's corner (the cushion reaches nearer the viewer than her feet: a step along the line would
    // land on it), so she closes one step left and a little nearer. L: that move, for the closed pose and the walk-off after it
    const sN = G('step.B')[0], sF = G('step.B')[1], dFar = G('d.C')[0].box[0];
    PLACE.step = [dFar - sF.box[0], D_FAR_Y - sF.box[3]];
    PLACE.L = [sN.box[0] + PLACE.step[0] - D_NEAR, sN.box[3] + PLACE.step[1] - FL];
    const F2 = FL + PLACE.L[1], c0 = (dFar + 641.5) / 2 + PLACE.L[0];  // her feet, closed: the floor line she walks off on
    const u1 = G('turn1.C'), c1 = (Math.min(...u1.map(g => g.box[0])) + Math.max(...u1.map(g => g.box[2]))) / 2;
    PLACE['turn1.C'] = [c0 - c1, F2 - bot('turn1.C')];                 // she pivots on the spot
    PLACE['turn2.C'] = [c0 - cx(G('turn2.C')[0]), F2 - bot('turn2.C')]; // the back foot is the pivot foot; the front one steps out
    const toe = (n, i) => G(n)[i].toe[0] + PLACE[n][0];
    PLACE.wc1g = [toe('turn2.C', 1) - G('wc1g')[0].toe[0], F2 - bot('wc1g')];   // each planted geta pinned to where it landed
    PLACE['wp1.C'] = [toe('wc1g', 1) - G('wp1.C')[0].toe[0], F2 - bot('wp1.C')];
    PLACE['wc2.C'] = [toe('wp1.C', 0) - G('wc2.C')[0].toe[0], F2 - bot('wc2.C')];
    PLACE.wp1b = [toe('wc2.C', 1) - G('wp1.C')[0].toe[0], F2 - bot('wp1.C')];
  }
  // before the drop the head follows Clawd a bar late (her angleY at t - 1 bar: chin up / level), held three drawings at least
  function headTrack(P) {
    const k0 = sl(EK.start), k1 = sl(EK.drop), raw = [];
    for (let k = k0; k < k1; k++) { const v = (P(k / 12 - BR) || {}).angleY || 0; raw.push(v > .2 ? 'up' : ''); }
    const out = raw.slice();
    for (let i = 0, prev = ''; i < out.length;) { let j = i; while (j < out.length && raw[j] === raw[i]) j++; const v = j - i >= 3 ? raw[i] : prev; for (let m = i; m < j; m++) out[m] = v; prev = v; i = j; }
    return { k0, h: out };
  }
  const phase = t => (((t - EK.drop) / PULSE) % 1 + 1) % 1;
  function swingAt(k) {                                                // the lantern on its ring, with her pulse, on twos (degrees)
    if (k < sl(EK.swing)) return 0;
    const v = Math.sin(2 * Math.PI * phase(k / 12)); return Math.round(v * 2) * 3;   // (-6, -3, 0, 3, 6)
  }
  function claps(k) {                                                  // the clap drawing at slot k (null: not clapping)
    const shut = CLAPS.map(sl), near = shut.filter(s => s >= k - 6 && s <= k + 6);
    if (!near.length) return null;
    if (shut.includes(k)) return 'c_shut';
    const first = Math.min(...near), last = Math.max(...near);
    if (k >= first - 2 && k <= last + 1) return 'c_open';
    return null;
  }
  function endState(t) {
    let k = sl(t); const s = { d: 'u.N', ox: 0, oy: 0, sy: 1, swing: 0, k };
    if (k > sl(EK.hit) + 1 && k < sl(EK.lower)) k = sl(EK.hit) + 1;              // the hit: r_up held, frozen with the card
    const run = (list, k0) => { let at = k0; for (const [d, n] of list) { if (k < at + n) return d; at += n; } return null; };
    if (k >= sl(EK.lower)) {                                                     // she lowers it and stays (Fable, v7: no walk-off)
      // "I stay and watch the doors close on her frozen card by both lights": standing, F-C, watching the window, the lantern
      // in her hand settling on its ring after the lowering (a swing that dies out, held on twos), still to the outro's clack
      const i = k - sl(EK.lower);
      if (i < 1) return { ...s, d: 'r_half', ox: PLACE.L[0], oy: PLACE.L[1] };
      const SETTLE = [6, 6, 6, -5, -5, -5, 4, 4, 4, -3, -3, -3, 2, 2, 2, -1, -1, -1];
      return { ...s, d: 'd.C', ox: PLACE.L[0], oy: PLACE.L[1], swing: SETTLE[i - 1] || 0 };
    }
    if (k >= sl(EK.hit)) return { ...s, d: k === sl(EK.hit) ? 'r_half' : 'r_up', ox: PLACE.L[0], oy: PLACE.L[1] };
    const closed = k >= sl(EK.close), face = k >= sl(EK.smile) ? 'C' : 'B', ph = phase(k / 12);
    if (closed) [s.ox, s.oy] = PLACE.L;
    s.swing = swingAt(k);
    if (k >= sl(EK.push) && k < sl(EK.push) + 11) return { ...s, d: run(PUSH, sl(EK.push)) };
    const c = claps(k); if (c) return { ...s, d: c + '.' + face };
    if (k >= sl(EK.wipe) && k < sl(EK.wipe) + 9) return { ...s, d: run(WIPE, sl(EK.wipe)) };
    if (k >= sl(EK.stepK) && k < sl(EK.close)) {                                // the step: a bounce on the landing
      [s.ox, s.oy] = PLACE.step; s.sy = k === sl(EK.stepK) ? .985 : k === sl(EK.stepK) + 1 ? 1.012 : 1;
      return { ...s, d: 'step.B' };
    }
    if (k >= sl(EK.push)) {                                                      // hood down: bobs on the pulse, growing
      if (face === 'B') return { ...s, d: ph < .2 ? 'd_dn.B' : 'd.B' };
      return { ...s, d: ph < .2 ? 'd_dn.C' : ph >= .5 && ph < .7 ? 'd_up.C' : 'd.C' };
    }
    if (k >= sl(EK.drop)) return { ...s, d: ph < .25 ? 'u_up.A' : 'u.A' };       // hood up, the corner: a small lift on the pulse
    const hv = E.head ? E.head.h[k - E.head.k0] || '' : '';
    return { ...s, d: hv === 'up' ? 'u_up.N' : 'u.N' };
  }
  function ending(X, t, T, o = {}) {
    if (window.FABLE3Q_STATIC && Q.base) { static3q(X, T); return { d: '3q' }; }
    if (!E.meta) return null;
    if (o.P && E.P !== o.P) { E.P = o.P; E.head = headTrack(o.P); }
    const st = endState(Math.max(t, EK.start)), [w, h] = E.meta.size, P = E.meta.points, M = E.meta.drawings;
    X.save(); X.translate(T.x, T.y); X.scale(T.s, T.s); X.translate(-559, -FL);
    X.globalCompositeOperation = 'source-over'; X.globalAlpha = 1;
    // (no cushion in the room: Fable has one zabuton, and she left it on the rail inside the window at B8, beside the book)
    if (st.d) {
      const m = M[st.d], pr = m.prop;
      X.save(); X.translate(st.ox, st.oy);
      if (st.sy !== 1) { const fx = 559; X.translate(fx, FL); X.scale(1, st.sy); X.translate(-fx, -FL); }   // (the bounce: about her soles)
      let lc = null;
      if (pr) {                                                        // the lantern prop: the stick in her fist, the lantern on its ring
        X.save(); X.translate(pr[0], pr[1]);
        X.drawImage(E.img.prop_stick, 0, 0, w, h);
        const [hx, hy] = P.hook, a = st.swing * Math.PI / 180;
        X.translate(hx, hy); X.rotate(a); X.translate(-hx, -hy); X.drawImage(E.img.prop_lantern, 0, 0, w, h);
        X.restore();
        const [cx, cy] = P.lantern_c; lc = [pr[0] + P.hook[0] + (cx - P.hook[0]) * Math.cos(a) - (cy - P.hook[1]) * Math.sin(a),
                                            pr[1] + P.hook[1] + (cx - P.hook[0]) * Math.sin(a) + (cy - P.hook[1]) * Math.cos(a)];
      } else lc = m.lantern;
      X.drawImage(E.img[st.d], 0, 0, w, h);
      // the lantern's warm light: on her sleeve, her face from below, the floor; it goes where the lantern goes
      if (lc && !o.figureOnly) {
        const fl = 1 + .04 * Math.sin(t * 9.1) * Math.sin(t * 3.3);
        X.globalCompositeOperation = 'lighter';
        const gr = X.createRadialGradient(lc[0], lc[1], 8, lc[0], lc[1], 300 * fl);
        gr.addColorStop(0, 'rgba(244,190,110,.32)'); gr.addColorStop(.4, 'rgba(244,160,80,.12)'); gr.addColorStop(1, 'rgba(244,160,80,0)');
        X.fillStyle = gr; X.fillRect(lc[0] - 310, lc[1] - 310, 620, 620);
      }
      X.restore();
    }
    X.restore();
    return st;
  }
  // the sounds (sound/mix.py; names from sound/sfx_lib.py), from the same constants: the cloth of the hood sliding back, her claps
  // (her palm on her own wrist: quiet, under the hall's), the step's two geta, and her geta on the walk-off's two contacts
  PAPER_SFX.push(() => [[(sl(EK.push) + 4) / 12, 'cloth', -31], ...CLAPS.map(c => [c, 'clap', -34]),
                        [190.588, 'geta', -24], [190.941, 'geta', -26]]);   // (the walk-off's geta went with the walk-off: v7)
  // preview: the ending on a plain dark ground at the finale's room camera (FIN: her feet at (1650, 1010), s .767), on the song
  // clock, Clawd's performance from finale.js (CHOREO.clawdF). ?loop=fableroom_end; _key: the figure alone on green, camera still
  const FIN = { x: 1650, y: 1010, s: 1.394 * .55 };
  const clawdP = () => (window.CHOREO && CHOREO.clawdF && CHOREO.clawdF.P ? CHOREO.clawdF.P() : null);
  LOOPS.fableroom_end = t => {
    X.setTransform(1, 0, 0, 1, 0, 0);
    const gr = X.createLinearGradient(0, 0, 0, H); gr.addColorStop(0, '#0f0b09'); gr.addColorStop(1, '#1d1611'); X.fillStyle = gr; X.fillRect(0, 0, W, H);
    X.fillStyle = '#e8d8b8'; X.globalAlpha = .12; X.fillRect(120, 140, 1180, 700); X.globalAlpha = 1; X.fillStyle = '#0a0806'; X.fillRect(0, 1010, W, H - 1010);
    const st = ending(X, t, FIN, { P: clawdP() });
    X.fillStyle = 'rgba(255,255,255,.7)'; X.font = '24px sans-serif';
    X.fillText(`song ${t.toFixed(3)}  bar ${(t / BR).toFixed(2)}  ${st ? st.d || '(gone)' : ''}`, 30, 40);
  };
  LOOPS.fableroom_end.len = 202;
  LOOPS.fableroom_end_key = t => {
    X.setTransform(1, 0, 0, 1, 0, 0); X.fillStyle = '#00ff00'; X.fillRect(0, 0, W, H);
    ending(X, t, { x: 1250, y: 1010, s: .697 }, { P: clawdP(), figureOnly: true });
  };
  LOOPS.fableroom_end_key.len = 202;
  return { load, room, state, plan, SEQ: () => SEQ, R, T0, ending, endState, E, EK, PLACE };
})();
