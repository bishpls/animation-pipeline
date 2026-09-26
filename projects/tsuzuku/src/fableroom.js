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
  }

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
  // The room ending (Michael + Fable; the final chorus, 177.8-201.5). She stays at her place beside the butai, in profile facing
  // the window, the lantern on its short stick in her fist (hold's arm: the drawing B9 hands off to at 177.8), and it never moves:
  // every standing drawing is hold with only the head or the free arm pasted in (rig/fable_room/build.py ending), so the lantern,
  // the fist and the far sleeve are hold's own pixels throughout. "A still light in a moving room." Twos, snap and hold.
  //   177.8   hood up. The head follows Clawd in the card a bar late, small: her angleY at t - 1 bar, on twos, as chin up / level /
  //           chin down (hood up: up or level), each held at least three drawings. Nothing else moves.
  //   187.83  "why" (Clawd turns and looks out at her at 187.62): the hood push, the free (near) hand: rising, to the hood's rim
  //           (held), the hood sliding back, the hood down with her hand at the back of her head (held), the hand coming down;
  //           hood down from 188.42, all landed by 188.92. Her face in profile from then.
  //   190.588 the step (the only time she moves on Clawd's beat): the near foot one step toward the window, landing on the
  //           downbeat of bar 135; the trailing foot closes on the next beat (190.941). Held there. Feet pinned (no slide).
  //   194.67  one page-wipe, a bar after Clawd's (bar 136.99, "Turn the page"): the free hand up, swept toward the window (held),
  //           back, at rest by 195.5. Half her own reach.
  //   199.07  she freezes with the card (the drawing held) until 200.6.
  //   200.67  she turns (three-quarter to the viewer, the lantern swinging round in front of her; three-quarter right) and walks
  //           off the frame's right edge, the lantern carried ahead, geta on the beat (200.82, 201.18), the ribbon last; gone at
  //           201.5 (off the frame's edge at the room's wide camera by ~201.3). Her lantern's light leaves with her; the cushion stays.
  const E = { meta: null, img: {}, head: null, P: null }, BR = 60 / 170 * 4, sl = t => Math.floor(t * 12 + 1e-6);
  const EK = { start: 177.8, push: 187.8334, step: 190.5834, close: 190.9167, wipe: 194.6667, freeze: 199.07, off: 200.6667 };
  const PUSH = [['push0', 2], ['push1', 3], ['push2', 2], ['push3', 4], ['d_wipe1', 2]];     // (hood down from push3)
  const WIPE = [['d_wipe1', 2], ['d_wipe2', 6], ['d_wipe1', 2]];
  const OFF = [['turn1', 1], ['turn2', 1], ['wc1', 2], ['wp1', 2], ['wc2', 2], ['wp1b', 2]];   // (wp1b: wp1 again, the next step)
  const FL = 1218.5, D_NEAR = 499, D_FAR_Y = 1194.5;                 // (hold's near geta tip, its far geta's sole: measured)
  const PLACE = {};                                                    // drawing px offsets of the placed drawings
  function endPlace() {
    const M = E.meta.drawings, G = n => M[n].geta, bot = n => Math.max(...G(n).map(g => g.box[3])), cx = g => (g.box[0] + g.box[2]) / 2;
    // the step: the far foot stays where it stood (its tip, its sole); the near foot lands one step toward the window, on the
    // floor in front of the cushion's corner (the cushion reaches nearer the viewer than her feet: a step along the line would
    // land on it), so she closes one step left and a little nearer. L: that move, for the closed pose and the walk-off after it
    const sN = G('step')[0], sF = G('step')[1], dFar = G('d')[0].box[0];
    PLACE.step = [dFar - sF.box[0], D_FAR_Y - sF.box[3]];
    PLACE.L = [sN.box[0] + PLACE.step[0] - D_NEAR, sN.box[3] + PLACE.step[1] - FL];
    const F2 = FL + PLACE.L[1], c0 = (dFar + 641.5) / 2 + PLACE.L[0];  // her feet, closed: the floor line she walks off on
    const u1 = G('turn1'), c1 = (Math.min(...u1.map(g => g.box[0])) + Math.max(...u1.map(g => g.box[2]))) / 2;
    PLACE.turn1 = [c0 - c1, F2 - bot('turn1')];                        // she pivots on the spot
    PLACE.turn2 = [c0 - cx(G('turn2')[0]), F2 - bot('turn2')];        // the back foot is the pivot foot; the front one steps out
    const toe = (n, i) => G(n)[i].toe[0] + PLACE[n][0];
    PLACE.wc1 = [toe('turn2', 1) - G('wc1')[0].toe[0], F2 - bot('wc1')];   // each planted geta pinned to where it landed
    PLACE.wp1 = [toe('wc1', 1) - G('wp1')[0].toe[0], F2 - bot('wp1')];
    PLACE.wc2 = [toe('wp1', 0) - G('wc2')[0].toe[0], F2 - bot('wc2')];
    PLACE.wp1b = [toe('wc2', 1) - G('wp1')[0].toe[0], F2 - bot('wp1')];
  }
  // the head, from Clawd's performance a bar late: sampled at every drawing 177.8-200.6, quantized, runs under three drawings
  // dropped (so it holds). Built once from the whole range (the same at any t, cold or warm)
  function headTrack(P) {
    const k0 = sl(EK.start), k1 = sl(EK.off), raw = [];
    for (let k = k0; k < k1; k++) { const q = P(k / 12 - BR) || {}, v = q.angleY || 0; raw.push(v > .2 ? 'up' : v < -.15 ? 'dn' : ''); }
    const out = raw.slice();
    for (let i = 0, prev = ''; i < out.length;) { let j = i; while (j < out.length && raw[j] === raw[i]) j++; const v = j - i >= 3 ? raw[i] : prev; for (let m = i; m < j; m++) out[m] = v; prev = v; i = j; }
    return { k0, h: out };
  }
  function endState(t) {
    let k = sl(t); const s = { d: 'u', ox: 0, oy: 0, lantern: true, gone: false, k };
    if (k >= sl(EK.freeze) && k < sl(EK.off)) k = sl(EK.freeze);                 // the freeze: her drawing held
    const run = (list, k0) => { let at = k0; for (const [d, n] of list) { if (k < at + n) return d; at += n; } return null; };
    if (k >= sl(EK.off)) {                                                       // the walk-off
      const d = run(OFF, sl(EK.off)); if (!d) return { ...s, d: null, gone: true };
      const [ox, oy] = PLACE[d]; return { ...s, d: d === 'wp1b' ? 'wp1' : d, ox, oy, carried: true };
    }
    const hoodDown = k >= sl(EK.push) + 7, closed = k >= sl(EK.close);
    if (closed) [s.ox, s.oy] = PLACE.L;
    let g = k >= sl(EK.push) ? run(PUSH, sl(EK.push)) : null;
    if (!g && k >= sl(EK.wipe)) g = run(WIPE, sl(EK.wipe));
    if (!g && k >= sl(EK.step) && k < sl(EK.close)) { [s.ox, s.oy] = PLACE.step; return { ...s, d: 'step', carried: true }; }
    if (g) return { ...s, d: g };
    const hv = E.head ? E.head.h[k - E.head.k0] || '' : '';
    s.d = hoodDown ? (hv ? 'd_' + hv : 'd') : (hv === 'up' ? 'u_up' : 'u');
    return s;
  }
  function ending(X, t, T, o = {}) {
    if (!E.meta) return null;
    if (o.P && E.P !== o.P) { E.P = o.P; E.head = headTrack(o.P); }
    const st = endState(Math.max(t, EK.start)), [w, h] = E.meta.size, P = R.meta ? R.meta.points : { feet: [559, 1218.5] };
    X.save(); X.translate(T.x, T.y); X.scale(T.s, T.s); X.translate(-P.feet[0], -P.feet[1]);
    X.globalCompositeOperation = 'source-over'; X.globalAlpha = 1;
    if (!o.figureOnly) X.drawImage(E.img.props, 0, 0, w, h);
    if (st.d) {
      X.drawImage(E.img[st.d], st.ox, st.oy, w, h);
      // the lantern's warm light, in her fist: on her sleeve, her face from below, the floor; it goes where she goes
      const lc = E.meta.drawings[st.d].lantern, fl = 1 + .04 * Math.sin(t * 9.1) * Math.sin(t * 3.3);
      if (lc && !o.figureOnly) {
        const lx = lc[0] + st.ox, ly = lc[1] + st.oy;
        X.globalCompositeOperation = 'lighter';
        const gr = X.createRadialGradient(lx, ly, 8, lx, ly, 300 * fl);
        gr.addColorStop(0, 'rgba(244,190,110,.32)'); gr.addColorStop(.4, 'rgba(244,160,80,.12)'); gr.addColorStop(1, 'rgba(244,160,80,0)');
        X.fillStyle = gr; X.fillRect(lx - 310, ly - 310, 620, 620);
      }
    }
    X.restore();
    return st;
  }
  // the sounds (sound/mix.py; names from sound/sfx_lib.py), from the same constants: the step's two geta, the cloth of the hood
  // as it slides back, and her geta on the walk-off's two contacts. Nothing for the wipe or the head (her gestures are silent)
  PAPER_SFX.push(() => [[190.588, 'geta', -24], [190.941, 'geta', -26], [(sl(EK.push) + 5) / 12, 'cloth', -31],
                        [(sl(EK.off) + 2) / 12, 'geta', -26], [(sl(EK.off) + 6) / 12, 'geta', -27]]);
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
