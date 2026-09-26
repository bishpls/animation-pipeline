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
// Bars are song bars (170 bpm).
const FABLEROOM = (() => {
  const R = { meta: null, img: {} }, TW = 1 / 12;
  async function load(base = 'rig/fable_room/room/') {
    const get = f => new Promise((ok, no) => { const i = new Image(); i.onload = () => ok(i); i.onerror = no; i.src = base + f; });
    R.meta = await (await fetch(base + 'meta.json')).json();
    await Promise.all(Object.entries(R.meta.drawings).map(async ([k, d]) => { R.img[k] = await get(d.file); }));
    plan();
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
  return { load, room, state, plan, SEQ: () => SEQ, R, T0 };
})();
