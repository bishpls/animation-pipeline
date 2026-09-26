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
    // the room ending: the three-quarter mesh rig (rig/fable_3q) and its key drawings' reference points
    E.rig = await RIG.load('rig/fable_3q/mesh/rig.json');
    const ap = await (await fetch('rig/fable_3q/mesh/build/armposes.json')).json();
    E.poses = Object.fromEntries([...(ap.R || []), ...(ap.L || [])].map(q => [q.name, q]));
    E.meta = { rig: 'fable_3q' };                                     // (FABLESTAGE.room's gate)
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
  // The room ending (Michael + Fable; the final chorus, 177.8-202.59). She stays in her room outside the butai, watching Clawd's
  // show through its window with her lantern lit: joyful, moved, the peak of her arc. A mesh-rigged illustration (rig/fable_3q,
  // RIGGING.md; engine/rig.js), seen THREE-QUARTERS FROM BEHIND, turned toward the window at the picture's left: her back and left
  // side toward us, the lantern in her far (right) hand held forward past her edge, lighting her cheek. In the room she's a person,
  // not a puppet (Fable): a 12 fps grid, every change with in-betweens; the hair (a rigid sheet hung at the tie), the ribbon (its own
  // plate at the knot, always in front of the hair), the sleeves, the hem and the lantern swing on springs from a fixed pre-roll.
  //   FABLEROOM.ending(X, t, T, o)   T = { x, y, s }: her feet on screen (the point between them); s: screen px per unit of the old
  //                                room drawings (she stands 1140.5 of them tall, hood down: s 1 = 1140 px). o.P (Clawd) unused.
  // Her timeline (Fable's rulings; "her pulse" = the half-note, 0.706 s; song seconds):
  //   always   her weight shifts foot to foot ON HER PULSE (hips leading, the hakama swinging with them, the unloaded heel lifting),
  //            the shoulders following (the near one dips with the near foot), the head tilting side to side after them (5-8
  //            degrees, never a nod); small through the build, full from the drop (182.12); held from the raise to the end.
  //   177.8    hood up, the near hand resting in its sleeve, the face at rest
  //   182.12   the drop: the corner of the mouth up, the eye bright
  //   187.67   the hood push (the near hand out of the sleeve, to the hood's crown, the hood pulled back over three drawings; down by
  //            188.42), the head turning ~15 degrees toward us as it comes off (the profile, the dry half-smile), then back
  //   188.76   two claps at the lantern wrist before "SO-RE-KA-RA" (189.11)
  //   190.588  the step toward the window (her near foot, landing on the pulse, a small bounce); the trailing foot closes at 190.941
  //   191.25   a real closed-lips smile
  //   193.39   "Turn the page": one sweep of the free hand across the window's light, six drawings, eased, ending at her side
  //   197.24   claps before each "and then" (197.24/.415, 197.858/198.035, 198.538/.715: the last pair rides the lantern's rise)
  //   198.36   the raise: the lantern rises through eight drawings (key drawings: at rest, lifted to her chin, overhead) and is
  //            overhead ON the dash (199.07); an open smile, eyes open. Held through the freeze
  //   200.6    she lowers it (eight drawings) and HOLDS, smiling, watching the window as the doors close (201.5-202.4), lit by it
  //   blinks   ~180.5, 185.0, 192.5, 201.9: half, closed, half (never on the hit, mid-clap or in the push)
  const E = { meta: null, rig: null, poses: null }, BR = 60 / 170 * 4, BEAT = BR / 4, EIGHTH = BR / 8, PULSE = BR / 2;
  const KQ = 1140.5 / 3650, ORIGIN = [1390, 4345];                 // (rig px per old drawing px; her feet in the rig)
  const EK = { start: 177.8, drop: 129 * BR, push: 187.667, hoodDown: 188.42, stepLift: 190.30, stepLand: 190.588, stepClose: 190.941,
               smile: 191.25, sweep: 193.39, raise: 199.07 - 2 * BEAT, hit: 199.07, lower: 200.6, end: 202.59 };
  const CLAPS = [[188.76, 188.93], [197.24, 197.415], [197.858, 198.035], [198.538, 198.715]];
  const BLINKS = [180.5, 185.0, 192.5, 201.9];
  const sl = t => Math.floor(t * 12 + 1e-6);
  const cl01 = u => Math.max(0, Math.min(1, u)), ss = u => { u = cl01(u); return u * u * (3 - 2 * u); };
  const ease = u => { u = cl01(u); return u < .5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2; };
  const lerp = (a, b, u) => a + (b - a) * u;
  const bump = (t, a, b, r) => ss((t - (a - r)) / r) * (1 - ss((t - b) / r));    // 1 on [a, b], eased over r at both ends
  // her weight: -1 on the near (image-left) foot, +1 on the far one. It arrives ON each pulse (the near foot on the bar's first and
  // third beats), holds a little with a small overshoot, then carries over, eased
  function weight(t) {
    if (t >= 189.9 && t < 191.3) {                                    // (the step: the weight never moves onto a lifted foot)
      if (t < 190.40) return 1;
      if (t < EK.stepLand) return 1 - 2 * ss((t - 190.40) / (EK.stepLand - 190.40));
      if (t < 191.0) return -1;
      return -1 + 2 * ss((t - 191.0) / (191.294 - 191.0));
    }
    const u = t / PULSE, k = Math.floor(u), f = u - k, from = k % 2 ? 1 : -1;
    const g = f < .28 ? 0 : ss((f - .28) / .72), over = f < .28 ? .1 * Math.sin(Math.PI * f / .28) : 0;
    return from * (1 + over) - 2 * from * g;
  }
  const dip = t => { const f = (t / PULSE) % 1; return f < .28 ? 0 : Math.sin(Math.PI * (f - .28) / .72); };   // the knees soften mid-transfer
  // energy: small through the build, full from the drop, easing out through the raise; held (breath only) after
  const env = t => t < EK.drop ? .35 + .65 * ss((t - (EK.drop - BR / 2)) / (BR / 2)) : t < EK.raise ? 1 : 1 - ss((t - EK.raise) / (EK.hit - EK.raise));
  // the step toward the window: the near foot lifts, swings and lands on the pulse; the body travels over it; the trailing foot
  // closes; planted feet never slide (each foot's world x is fixed while it's down: foot = world - root)
  const STEP = 170;                                                  // (rig px, image-left)
  function step(t) {
    const nu = cl01((t - EK.stepLift) / (EK.stepLand - EK.stepLift)), fu = cl01((t - 190.66) / (EK.stepClose - 190.66));
    const root = -STEP * (.55 * ss((t - EK.stepLift) / (EK.stepLand - EK.stepLift)) + .45 * ss((t - EK.stepLand) / (EK.stepClose - EK.stepLand)));
    const u = t - EK.stepLand, bounce = u > 0 ? 22 * Math.exp(-7 * u) * Math.sin(2 * Math.PI * Math.min(u, .7) / .36) : 0;
    return { rootX: root, footLX: -STEP * ease(nu) - root, footLY: 42 * Math.sin(Math.PI * nu), footRX: -STEP * ease(fu) - root, footRY: 34 * Math.sin(Math.PI * fu), bounce };
  }
  // ---- the lantern arm: key drawings (rig/fable_3q/poses.py: rest, lift, up), placed by the fist and the stick's angle
  const ang = (a, b) => Math.atan2(b[1] - a[1], b[0] - a[0]) * 180 / Math.PI;
  const rotP = (p, c, deg) => { const a = deg * Math.PI / 180, dx = p[0] - c[0], dy = p[1] - c[1]; return [c[0] + dx * Math.cos(a) - dy * Math.sin(a), c[1] + dx * Math.sin(a) + dy * Math.cos(a)]; };
  // raise progress s (0 at rest, 1 lifted to the chin, 2 overhead) per drawing, from the first drawing after 198.364: a slow start
  // (the last claps ride it), then up fast onto the dash (the drawing that holds 199.07); lowering from 200.6 the same way back
  // (the first four drawings are the anticipation: the lantern dips a little and gathers while the last two claps land on the wrist;
  //  then it rises fast, overshoots, settles: Fable's 'two beats before the dash' and her claps before each 'and then', both)
  const RAISE = [-.02, -.05, -.06, -.03, .3, .8, 1.35, 1.8, 2.06, 2.0];
  const LOWER = [1.85, 1.6, 1.25, .9, .6, .35, .15, .05, 0];
  function raise(t) {
    const k = sl(t), k0 = sl(EK.raise) + 1, k1 = sl(EK.lower);
    if (k >= k1) return LOWER[Math.min(k - k1, LOWER.length - 1)];
    if (k >= k0) return RAISE[Math.min(k - k0, RAISE.length - 1)];
    return 0;
  }
  function lanternArm(s) {                                           // -> { hand, pose, ring, wrist }
    const Pz = E.poses; if (!Pz || s === 0) return { ring: [302, 2022], wrist: Pz ? Pz.rest.wrist : [694, 1976] };
    if (s < 0) {                                                     // (the anticipation: the rest drawing dips, tilting a little)
      const D = Pz.rest, pose = { a: s * 40, cx: D.fist[0], cy: D.fist[1], dx: 0, dy: -s * 700 };
      const place = q => { const r = rotP(q, D.fist, pose.a); return [r[0], r[1] + pose.dy]; };
      return { hand: 'rest', pose, ring: place(D.ring), wrist: place(D.wrist) };
    }
    const keys = [Pz.rest, Pz.lift, Pz.up], i = Math.min(1, Math.floor(s)), u = Math.min(1, s - i), a = keys[i], b = keys[i + 1];
    const F = [lerp(a.fist[0], b.fist[0], u), lerp(a.fist[1], b.fist[1], u)] , th = lerp(ang(a.tip, a.fist), ang(b.tip, b.fist), u);
    const D = keys[Math.min(2, Math.round(s))], da = th - ang(D.tip, D.fist);     // (the nearer key drawing, moved to the in-between's place)
    const place = q => { const r = rotP(q, D.fist, da); return [r[0] + F[0] - D.fist[0], r[1] + F[1] - D.fist[1]]; };
    return { hand: D.name, pose: { a: da, cx: D.fist[0], cy: D.fist[1], dx: F[0] - D.fist[0], dy: F[1] - D.fist[1] }, ring: place(D.ring), wrist: place(D.wrist) };
  }
  // ---- the free hand, and the drawn states around the hood push. The arm is key drawings (rig/fable_3q/poses.py, build.py
  // pusharms: pushA gripping the hood's crown, pushB pulling it back, 'down' at her shoulder, the clap at the lantern wrist, the
  // sweep up in the light) turned about her shoulder for the in-betweens (p.poseL); the mesh arm only near rest (small angles)
  const HAND_IN = 290, SH = [1062, 1480];                           // (rig px: the hand drawn up into its sleeve; her shoulder)
  const KP = sl(EK.push);                                            // the push's first drawing (187.667)
  function view(k) {
    if (k < KP + 2) return 'hoodup';                                 // 177.8-187.75: hood up
    if (k < KP + 4) return 'push1';                                  // her hand grips the hood's crown
    if (k < KP + 6) return 'push2';                                  // the hood pulled back, the hair out, the head turning
    if (k < KP + 8) return 'turn';                                   // hood down (188.17), the profile found, the dry half-smile
    if (k < KP + 10) return 'turn_half';                             // back toward the window
    return null;
  }
  const clapK = CLAPS.flat().map(sl);                                // (a pat lands on the drawing that holds its time)
  const opened = k => Math.min(...clapK.map(c => [0, .55, 1][Math.min(2, Math.abs(k - c))]));
  function freeArm(t, s) {
    const k = sl(t), o = { armL: 0, elbowL: 0, handIn: 0 };
    const key = (hand, a = 0, dx = 0, dy = 0) => { o.handL = hand; o.poseL = { a, cx: SH[0], cy: SH[1], dx, dy }; };
    const mesh = (a, e, hi = 0) => { o.armL = a; o.elbowL = e; o.handIn = hi; };
    // resting in its sleeve until the push
    if (k < KP - 1) { o.handIn = HAND_IN; return o; }
    // the push: out of the sleeve and up, the grip, the pull, down to her shoulder, forward to the lantern wrist (the first claps)
    const PUSH = [[KP - 1, () => mesh(6, 8, HAND_IN * .5)], [KP, () => mesh(-4, 34)], [KP + 1, () => key('pushA', -38)], [KP + 2, () => key('pushA')],
                  [KP + 3, () => key('pushA', 3)], [KP + 4, () => key('pushB')], [KP + 5, () => key('pushB', 4)], [KP + 6, () => key('down', 18)],
                  [KP + 7, () => key('down')], [KP + 8, () => key('down', -12)], [KP + 9, () => key('clap', 30)], [KP + 10, () => key('clap', 16)],
                  [KP + 11, () => key('clap', 7)]];
    for (const [kk, f] of PUSH) if (k === kk) { f(); return o; }
    // the claps: the palm at the lantern wrist (it follows the wrist's small dip in the raise's anticipation), lifting off between pats
    const W = lanternArm(s).wrist, W0 = E.poses ? E.poses.rest.wrist : W;
    const clapAt = () => { const op = opened(k); key('clap', 0, 10 * op + W[0] - W0[0], -24 * op + W[1] - W0[1]); };
    const c1 = clapK[0], c2 = clapK[1], c3 = clapK[2], c8 = clapK[clapK.length - 1];
    if (k >= KP + 12 && k <= c2) { clapAt(); return o; }
    // (to and from her side the hand stays by her body, never across the lantern: the clap drawing turned in, then the mesh arm at
    //  angles solved to keep the hand at her hip: (-28, 52) -> (913, 2468), (-14, 30) -> (896, 2601))
    const back = [() => key('clap', -16), () => mesh(-28, 52), () => mesh(-14, 30)];     // (and down to her side)
    if (k > c2 && k <= c2 + 3) { back[k - c2 - 1](); return o; }
    const toward = [() => mesh(-14, 30), () => mesh(-28, 52), () => key('clap', -16)];    // (up from her side to the wrist)
    if (k >= c3 - 3 && k < c3) { toward[k - c3 + 3](); return o; }
    if (k >= c3 && k <= c8) { clapAt(); return o; }
    if (k > c8 && k <= c8 + 3) { back[k - c8 - 1](); return o; }
    // "Turn the page": up by her body, out along the arc into the light (the sweep drawing, on 'mekutte'), and down the arc and
    //  back by her body to her side: one sweep, eased (close drawings at its ends, wide in its middle), no hold
    const ks = sl(EK.sweep);
    const SWEEP = [[ks - 3, () => mesh(-14, 30)], [ks - 2, () => mesh(-28, 52)], [ks - 1, () => key('clap', -16)], [ks, () => key('sweep', -26)],
                   [ks + 1, () => key('sweep')], [ks + 2, () => key('sweep', -10)], [ks + 3, () => key('sweep', -26)], [ks + 4, () => key('clap', 2)],
                   [ks + 5, () => key('clap', -16)], [ks + 6, () => mesh(-28, 52)], [ks + 7, () => mesh(-14, 30)]];
    for (const [kk, f] of SWEEP) if (k === kk) { f(); return o; }
    return o;
  }
  // ---- the face: rest -> the corner (182.12) -> the smile (191.25) -> the open smile on the hit, eyes open -> the smile; blinks
  function face(t) {
    const k = sl(t), at = x => sl(x);
    let st = t < EK.drop ? null : t < EK.smile ? 'corner' : 'smile', eye = st;
    if (k >= at(EK.hit) - 1 && k < at(EK.lower)) { st = k < at(EK.hit) ? 'open_half' : 'open'; eye = 'corner'; }
    else if (k >= at(EK.lower) && k < at(EK.lower) + 2) { st = 'open_half'; eye = 'corner'; }
    for (const b of BLINKS) { const i = k - at(b); if (i >= 0 && i < 3) eye = i === 1 ? 'blink' : 'blink_half'; }
    const sw = {}; if (st) { sw.face = st; sw.ear = st; } if (eye) sw.eye = eye;
    return sw;
  }
  // ---- all her parameters at song time t (continuous; the rig draws on the 12 fps grid and steps its springs from a pre-roll)
  function pose(t) {
    const e = env(t), tilt = e * (1 - bump(t, EK.push - .1, EK.hoodDown + .25, .3)), st = step(t), s = raise(t);
    // (the hips shift, the shoulders dip with the near foot, the head tilts after them; small enough that the head stays over her
    //  feet: a weight shift, not a ballad crowd's sway. Head tilt in total ~6.4 degrees: its own 5 plus the shoulders')
    const p = { hipX: .35 * e * weight(t), bodyZ: 1.4 * e * weight(t - .09), angleZ: 5.0 * tilt * weight(t - .16),
                hipY: 10 * e * dip(t) + st.bounce, breath: .5 + .5 * Math.sin(2 * Math.PI * t / 3.4),
                footLX: st.footLX, footLY: st.footLY, footRX: st.footRX, footRY: st.footRY, rootX: st.rootX };
    p.swing = (p.bodyZ || 0) + p.hipX * 8 + st.rootX / 25;           // (the springs' drive: the hips' shift and her travel)
    Object.assign(p, freeArm(t, s));
    const LA = lanternArm(s);
    if (LA.hand) { p.handR = LA.hand; p.poseR = LA.pose; }
    p.lanternDX = LA.ring[0] - 302; p.lanternDY = LA.ring[1] - 2022; p._ringY = LA.ring[1];
    p.swap = face(t); const v = view(sl(t)); if (v) p.view = v;
    return p;
  }
  // the lantern on its ring: a damped pendulum (length 370 rig px: ~0.8 s, near her pulse) driven by the hook's motion (the hand, the
  // body's sway, her travel), stepped at 120 Hz from a fixed pre-roll, so a frame is a pure function of t
  const G = 21700, LEN = 370, W0 = Math.sqrt(G / LEN), ZETA = .12;
  function hook(t) {
    const p = pose(t), lx = LANTERN_X(p);
    return [lx, p._ringY + (p.hipY || 0)];
  }
  const LANTERN_X = p => 302 + p.lanternDX + (p.rootX || 0) + 150 * (p.hipX || 0) + (2600 - (p._ringY || 2022)) * Math.sin((p.bodyZ || 0) * .45 * Math.PI / 180);
  function pendulum(t) {
    const dt = 1 / 120, n = 360; let th = 0, om = 0, h0 = hook(t - n * dt - 2 * dt), h1 = hook(t - n * dt - dt);
    for (let i = 0; i <= n; i++) {
      const h2 = hook(t - (n - i) * dt), ax = (h2[0] - 2 * h1[0] + h0[0]) / (dt * dt), ay = (h2[1] - 2 * h1[1] + h0[1]) / (dt * dt);
      const acc = -(G + ay) / LEN * Math.sin(th) - ax / LEN * Math.cos(th) - 2 * ZETA * W0 * om;
      om += acc * dt; th += om * dt; h0 = h1; h1 = h2;
    }
    return Math.max(-14, Math.min(14, th * 180 / Math.PI));
  }
  function ending(X, t, T, o = {}) {
    if (!E.rig) return null;
    try { return endingDraw(X, t, T, o); }
    catch (e) { if (!E.warned) { E.warned = true; console.error('FABLEROOM.ending: ' + (e && e.stack || e)); } X.restore && X.setTransform(1, 0, 0, 1, 0, 0); return null; }
  }
  function endingDraw(X, t, T, o) {
    const tq = Math.floor(Math.max(t, EK.start) * 12 + 1e-6) / 12, th = pendulum(tq), s = T.s * KQ;
    const P3 = tt => { const p = pose(tt); p.lanternRot = th - .42 * (p.bodyZ || 0); return p; };
    const p = P3(tq), TT = { x: T.x + (p.rootX || 0) * s, y: T.y, s };
    X.save(); X.globalCompositeOperation = 'source-over'; X.globalAlpha = 1;
    E.rig.draw(X, tq, P3, TT);
    if (!o.figureOnly) {                                               // her lantern's warm light: her sleeve, her cheek, the floor
      const a = th * Math.PI / 180, cx = 302 + p.lanternDX + (p.hipX || 0) * 150 + Math.sin(a) * 360, cy = p._ringY + Math.cos(a) * 360;
      const lx = TT.x + (cx - ORIGIN[0]) * s, ly = TT.y + (cy - ORIGIN[1]) * s, fl = 1 + .04 * Math.sin(t * 9.1) * Math.sin(t * 3.3), R = 1500 * s * fl;
      X.setTransform(1, 0, 0, 1, 0, 0); X.globalCompositeOperation = 'lighter';
      const gr = X.createRadialGradient(lx, ly, 8, lx, ly, R);
      gr.addColorStop(0, 'rgba(244,190,110,.30)'); gr.addColorStop(.35, 'rgba(244,160,80,.11)'); gr.addColorStop(1, 'rgba(244,160,80,0)');
      X.fillStyle = gr; X.fillRect(lx - R, ly - R, 2 * R, 2 * R);
    }
    X.restore();
    return { t: tq, p, th };
  }
  // the sounds (sound/mix.py; names from sound/sfx_lib.py), from the same constants: the cloth of the hood sliding back, her claps
  // (her palm on her own wrist: quiet, under the hall's), the step's two geta
  PAPER_SFX.push(() => [[EK.push + .33, 'cloth', -31], ...CLAPS.flat().map(c => [c, 'clap', -34]),
                        [EK.stepLand, 'geta', -24], [EK.stepClose, 'geta', -26]]);
  // previews: the ending on a plain dark ground at the finale's default room shot (FIN, T from the finale's framing), on the song
  // clock; _big: her head and shoulders large (for 100% crops); _key: the figure alone on green
  const FIN = { x: 1593, y: 1377, s: .998 };
  const endBg = () => {
    X.setTransform(1, 0, 0, 1, 0, 0);
    const gr = X.createLinearGradient(0, 0, 0, H); gr.addColorStop(0, '#1a1426'); gr.addColorStop(1, '#241a30'); X.fillStyle = gr; X.fillRect(0, 0, W, H);
    X.fillStyle = '#e8d8f0'; X.globalAlpha = .16; X.fillRect(135, 60, 1650, 900); X.globalAlpha = 1;
  };
  const label = (t, st) => { X.setTransform(1, 0, 0, 1, 0, 0); X.fillStyle = 'rgba(255,255,255,.75)'; X.font = '24px sans-serif';
    X.fillText(`song ${t.toFixed(3)}  bar ${(t / BR).toFixed(2)}  drawing ${sl(t)}${st && st.p.handR ? '  ' + st.p.handR : ''}${st && st.p.handL ? '  ' + st.p.handL : ''}`, 30, 40); };
  LOOPS.fableroom_end = t => { endBg(); label(t, ending(X, Math.max(177.8, t), FIN)); };
  LOOPS.fableroom_end.len = 203;
  LOOPS.fableroom_end_wide = t => { endBg(); label(t, ending(X, Math.max(177.8, t), { x: 1100, y: 1030, s: .8 })); };
  LOOPS.fableroom_end_wide.len = 203;
  LOOPS.fableroom_end_why = t => { endBg(); label(t, ending(X, Math.max(177.8, t), { x: 1768, y: 1649, s: 1.275 })); };   // (the 'why' two-shot's T)
  LOOPS.fableroom_end_why.len = 203;
  LOOPS.fableroom_end_key = t => { X.setTransform(1, 0, 0, 1, 0, 0); X.fillStyle = '#00ff00'; X.fillRect(0, 0, W, H); ending(X, Math.max(177.8, t), { x: 1100, y: 1030, s: .8 }, { figureOnly: true }); };
  LOOPS.fableroom_end_key.len = 203;
  // ---- the range-of-motion test (tools/romrun.py projects/tsuzuku --name fable3qrom): every control alone and combined, every
  // drawn view's rest, tilt and sway, the step, spring whips, the free arm's mesh angles and every key drawing turned through the
  // range the motion uses (inside the views it plays in), the lantern's raise path and swing, the face's states, and the ending
  // performed. 'rest' segments are the per-view baselines. LOOPS.fable3qrom / fable3qromid (the ID pass)
  {
    const segs = [], add = (name, dur, frame, fn) => segs.push({ name, dur, frame, fn });
    const sw = u => Math.sin(2 * Math.PI * u), up = u => .5 - .5 * Math.cos(2 * Math.PI * u);
    const VIEWS = [null, 'hoodup', 'push1', 'push2', 'turn', 'turn_half'];
    for (const v of VIEWS) for (const fr of ['full', 'head']) add(`rest ${fr} ${v || 'F'}`, .5, fr, () => ({ view: v || undefined }));
    for (const v of [null, 'hoodup']) {
      add(`tilt ${v || 'F'}`, 2, 'head', u => ({ view: v || undefined, angleZ: 6.3 * sw(u), bodyZ: 1.8 * sw(u) }));   // (the performed range +25%)
      add(`weight ${v || 'F'}`, 2, 'full', u => ({ view: v || undefined, hipX: .6 * sw(u), bodyZ: 2.5 * sw(u), angleZ: 6 * sw(u), hipY: 14 * up(u) }));
      add(`whip ${v || 'F'}`, 2, 'full', u => ({ view: v || undefined, hipX: .6 * Math.sign(sw(3 * u)), swing: 8 * Math.sign(sw(3 * u)), angleZ: 8 * Math.sign(sw(3 * u)) }));
    }
    add('step', 1.4, 'full', u => { const st = step(190.1 + 1.2 * u); return { ...st, rootX: 0, footLX: st.footLX + st.rootX, footRX: st.footRX + st.rootX, hipY: st.bounce }; });
    add('feet', 2, 'full', u => ({ footLY: 50 * Math.max(0, sw(u)), footRY: 50 * Math.max(0, -sw(u)), hipX: .5 * sw(u) }));
    add('hand in', 1, 'full', u => ({ handIn: HAND_IN * up(u) }));
    add('arm mesh', 3, 'full', u => ({ armL: -30 + 40 * up(u), elbowL: 60 * up(1.5 * u) }));
    const KEYS = [['clap', -24, 32, [null, 'turn_half']], ['sweep', -42, 4, [null]], ['down', -14, 20, [null, 'turn', 'turn_half']],
                  ['pushA', -40, 5, ['hoodup', 'push1']], ['pushB', -2, 6, ['push2']]];
    for (const [h, a0, a1, views] of KEYS) for (const v of views)
      add(`key ${h} ${v || 'F'}`, 2, 'full', u => ({ view: v || undefined, handL: h, poseL: { a: a0 + (a1 - a0) * up(u), cx: SH[0], cy: SH[1], dx: 0, dy: 0 } }));
    add('clap pats', 1.5, 'full', u => { const op = Math.abs(sw(2 * u)); return { handL: 'clap', poseL: { a: 0, cx: SH[0], cy: SH[1], dx: 10 * op, dy: -24 * op } }; });
    add('raise', 3, 'full', u => { const s = -.06 + 2.12 * up(u), LA = lanternArm(s); return { handR: LA.hand, poseR: LA.pose, lanternDX: LA.ring[0] - 302, lanternDY: LA.ring[1] - 2022, lanternRot: 14 * sw(2 * u) }; });
    add('swing', 1.5, 'full', u => ({ lanternRot: 16 * sw(u), hipX: .4 * sw(u) }));
    for (const f of ['corner', 'smile', 'open_half', 'open']) add(`face ${f}`, .5, 'head', () => ({ swap: { face: f, ear: f, eye: f === 'open' ? 'corner' : f } }));
    add('blink', .5, 'head', u => ({ swap: { eye: u < .33 ? 'blink_half' : u < .66 ? 'blink' : 'blink_half' } }));
    add('perform', EK.end - EK.start, 'full', null);
    let T0 = 0; for (const g of segs) { g.t0 = T0; T0 += g.dur; }
    window.ROMSETS = window.ROMSETS || {}; window.ROMSETS.fable3qrom = segs.map(g => [g.name, +g.t0.toFixed(3), +(g.t0 + g.dur).toFixed(3), g.frame]);
    const FR = { full: { x: 960, y: 1070, s: .9 }, head: { x: 960 + (1390 - 1250) * 2.4 * KQ, y: 540 + (4345 - 1050) * 2.4 * KQ, s: 2.4 } };
    const romDraw = (bgc, id) => t => {
      X.setTransform(1, 0, 0, 1, 0, 0); X.fillStyle = bgc; X.fillRect(0, 0, W, H);
      const g = segs.find(q => t >= q.t0 && t < q.t0 + q.dur) || segs[segs.length - 1];
      window.RIG_IDPASS = id;
      try {
        if (!g.fn) endingDraw(X, EK.start + (t - g.t0), FR.full, { figureOnly: true });
        else if (E.rig) { const P = tt => ({ breath: .5, ...g.fn(Math.min(1, Math.max(0, (tt - g.t0) / g.dur))) }), T = FR[g.frame];
          E.rig.draw(X, t, P, { x: T.x, y: T.y, s: T.s * KQ }); }
      } finally { window.RIG_IDPASS = false; }
    };
    LOOPS.fable3qrom = romDraw('#201d33', false); LOOPS.fable3qromid = romDraw('#000000', true); LOOPS.fable3qrommag = romDraw('#ff00ff', false);
    LOOPS.fable3qrommag.len = T0;
    LOOPS.fable3qrom.len = LOOPS.fable3qromid.len = T0;
  }
  return { load, room, state, plan, SEQ: () => SEQ, R, T0, ending, pose, raise, lanternArm, pendulum, E, EK };
})();
