// motionlab.js: the motion lab for Clawd's choreography (MOTION.md). Two things:
//   MOTIONLAB.dump(b0, b1, fps)   the performed parameters of world A per frame (CHOREO.clawdA), the located body points
//                                 (hands, face, chest, pelvis, feet, a bun) in stage px, and the rig's secondary springs,
//                                 for tools/motion_audit.py:
//     node engine/render.mjs projects/tsuzuku --eval='MOTIONLAB.dump(45, 93, 24)' > board/motion/dump.json
//   LOOPS.motionlab              before | after, side by side on one phrase, full body on a fixed camera, with the song
//     node engine/render.mjs projects/tsuzuku --loop=motionlab --clip=0:11.3 --out=projects/tsuzuku/out/motionlab_v1.mp4
const MOTIONLAB = (() => {
  const BAR = 60 / 170 * 4;
  const CH = ['hipX', 'hipY', 'bodyX', 'bodyZ', 'angleX', 'angleY', 'angleZ', 'armL', 'armR', 'elbowL', 'elbowR',
              'footLX', 'footLY', 'footRX', 'footRY', 'rootX', 'breath'];
  const PTS = ['hand_L', 'hand_R', 'face', 'chest', 'waistband', 'boot_L', 'boot_R', 'bun_L', 'skirt'];
  // the rig's springs (engine/rig.js springs(), reproduced read-only so the audit sees the secondary motion)
  function springs(R, P, t) {
    const S = R.springs || {}, names = Object.keys(S);
    const vang = p => ((R.views && p.view && R.views[p.view] && R.views[p.view].angle) || 0) * (R.viewDrive ?? .3);
    const drive = (p, name) => { const d = S[name].drive; return d === 'headX' ? vang(p) + (p.angleX || 0) * 30 : d === 'headZ' ? (p.angleZ || 0) : d === 'headY' ? (p.angleY || 0) * 18
      : d === 'pelvis' ? (p.bodyZ ?? 0) + (p.hipX || 0) * 8 : d === 'hipY' ? (p.hipY || 0) + (p.bounce || 0)
      : d === 'bodyZ' ? (p.bodyZ ?? 0) : d === 'bounce' ? (p.bounce || 0) : d === 'bodyX' ? (p.bodyX ?? 0) * 20 : (p[d] || 0); };
    const dt = 1 / 120, pre = R.preroll || 2, t0 = t - pre, n = Math.round(pre / dt);
    const st = {}; for (const k of names) st[k] = { x: drive(P(t0), k), v: 0 };
    for (let i = 1; i <= n; i++) { const p = P(t0 + i * dt); for (const k of names) { const s = S[k], d = drive(p, k), q = st[k]; const a = -s.k * (q.x - d) - s.c * q.v; q.v += a * dt; q.x += q.v * dt; } }
    const P1 = P(t), out = {}; for (const k of names) out[k] = (st[k].x - drive(P1, k)) * (S[k].gain || 1); return out;
  }
  // ---- fix #1 (MOTION.md): the core dances. An additive layer on the performed choreography, driven from the pelvis:
  //   bounce   she rises ON the beat (Fable: Clawd never lands) and gives on the "and": a quick push from the dip into the rise,
  //            a softer fall; big enough to read (70 base px of knee give, ~19 screen px at the wide), phased to the kicks
  //   weight   the weight arrives on each beat, alternating sides (hipX), so the rig's heel lift unloads the free foot
  //   overlap  the chest follows the pelvis two frames late, the head four (tilt) and three (nod): successive breaking
  //   arms     drop a little after the body's drop and the forearms trail: the arms breathe with the groove
  //   holds    it never stops, so a held pose is a moving hold
  //   energy   by section, and halved while she travels (feet busy)
  // Timing: world A's kicks land 68 ms after the 170 BPM grid (tools/motion_audit.py); the rise peaks one frame ahead of the
  // kick (a visual hit reads on time a frame early), so the phase reference is grid + 26 ms.
  // o.curves: retargeted channel curves (MOTION.md, "Retargeting"): {channel: {b: [song bars], v: [values], gain, mode}}; 'add'
  // (default) adds the sampled curve, 'set' replaces the channel. Sampled linearly on the song bar.
  const BT = BAR / 4, FR = 1 / 24;
  const ENERGY = [[45, .45], [46, 1], [62, .8], [66, .55], [82, 1.1], [90, .6], [91.2, .25], [91.6, 0]];
  const energyAt = b => {                                                           // eased over half a bar into each section's level
    let i = 0; while (i + 1 < ENERGY.length && b >= ENERGY[i + 1][0]) i++;
    const [b0, v] = ENERGY[i]; if (i === 0 || b < b0) return v;
    const pv = ENERGY[i - 1][1], u = Math.min(1, (b - b0) / .5); return pv + (v - pv) * u * u * (3 - 2 * u);
  };
  const sampleCurve = (c, b) => { const B = c.b, V = c.v; if (b <= B[0]) return V[0]; if (b >= B[B.length - 1]) return V[V.length - 1];
    let i = 1; while (B[i] < b) i++; const u = (b - B[i - 1]) / (B[i] - B[i - 1]); return V[i - 1] + (V[i] - V[i - 1]) * u; };
  function groove(P, o = {}) {
    const off = o.offset ?? .026, Ay = o.bounce ?? 70, Ax = o.sway ?? .5;
    const ph = t => (t - off) / BT;                                                  // beats
    const dip = t => { const u = ph(t), f = u - Math.floor(u); const w = f + .09 * Math.sin(2 * Math.PI * f); return .5 - .5 * Math.cos(2 * Math.PI * w); };   // 0 on the beat, 1 on the "and": quick through the beat, a sit in the knees
    const rise = t => { const u = ph(t), f = u - Math.floor(u); return Math.max(0, Math.cos(Math.PI * Math.min(1, f / .22))) * (f < .22 ? 1 : 0); };   // the pop on the beat
    const sway = t => Math.sin(Math.PI * (ph(t) - .5));                            // weight on each beat, alternating
    return t => {
      const q = { ...P(t) }, b = t / BAR;
      const trav = Math.abs(((P(t + FR).rootX || 0) - (P(t - FR).rootX || 0)) / (2 * FR)) > 40 ? .5 : 1;   // travelling: the feet are busy
      const E = energyAt(b) * trav, add = (k, v) => { q[k] = (q[k] || 0) + v; };
      add('hipY', E * (Ay * dip(t) - .35 * Ay * rise(t)));
      q.kneeOut = Math.min(1, Math.max(q.kneeOut || 0, .62 * Math.min(1, E * 1.5)));  // the knees track over the toes (not knock-kneed)
      add('hipX', E * Ax * sway(t));
      if (Ay === 0 && Ax === 0) { if (o.curves && (!o.only || (b >= o.only[0] && b < o.only[1]))) for (const [k, c] of Object.entries(o.curves)) { const v = sampleCurve(c, b) * (c.gain ?? 1); q[k] = c.mode === 'set' ? v : (q[k] || 0) + v; } return q; }
      add('bodyZ', -E * 3.2 * sway(t - 2 * FR));                                      // the chest counter-tilts, two frames late
      add('angleZ', E * 2.4 * sway(t - 4 * FR));                                      // the head goes with the weight, four frames late
      add('angleY', E * .3 * dip(t - 3 * FR) - E * .12 * rise(t - 3 * FR));           // the head nods after the body's drop
      add('armL', -E * 4 * dip(t - 2 * FR)); add('armR', -E * 4 * dip(t - 2 * FR));  // the arms settle after the drop...
      add('elbowL', E * 7 * dip(t - 3 * FR)); add('elbowR', E * 7 * dip(t - 3 * FR)); // ...the forearms trail
      if (o.curves && (!o.only || (b >= o.only[0] && b < o.only[1])))                // (o.only [bar0, bar1]: the curves' span)
        for (const [k, c] of Object.entries(o.curves)) { const v = sampleCurve(c, b) * (c.gain ?? 1); q[k] = c.mode === 'set' ? v : (q[k] || 0) + v; }
      return q;
    };
  }
  let P1 = null;
  const after = () => (P1 = P1 || groove(CHOREO.clawdA.P()));
  // before | after, side by side, full body on a fixed camera, song time (chorus 1's groove: bars 46-54)
  LOOPS.motionlab = t => {
    const P0 = CHOREO.clawdA.P(), Pa = after();
    X.setTransform(1, 0, 0, 1, 0, 0); X.fillStyle = '#3a3448'; X.fillRect(0, 0, W, H); X.fillStyle = '#2c2838'; X.fillRect(0, 1000, W, 80);
    X.fillStyle = '#4a4458'; X.fillRect(958, 0, 4, H);
    RIGS.clawd.draw(X, t, P0, { x: 480 + (P0(t).rootX || 0) * .25, y: 1040, s: .25 });
    RIGS.clawd.draw(X, t, Pa, { x: 1440 + (Pa(t).rootX || 0) * .25, y: 1040, s: .25 });
    X.fillStyle = 'rgba(255,255,255,.7)'; X.font = '600 30px sans-serif'; X.fillText('now', 40, 60); X.fillText('fix #1: the core dances', 1000, 60);
    X.font = '22px sans-serif'; X.fillText('bar ' + (t / BAR).toFixed(2), 40, 100);
  };
  LOOPS.motionlab.len = 220;

  // ---- the hook from motion capture (MOTION.md, "Retargeting"): the Seedance reference (refs/mocap/hook_v1.mp4), tracked
  // (tools/posetrack.py), retargeted onto her channels and warped onto the song by tools/retarget_mocap.py. Three panels, song
  // time over the hook (bars 62-66): the hand-keyed hook | the retargeted hook (her body and arms from the data; the pinch hands,
  // mouth, eyes and views still from the choreography) | the source with its skeleton, at the warped source time.
  //   node engine/render.mjs projects/tsuzuku --loop=motionlab_hook --clip=87.53:93.18 --out=projects/tsuzuku/out/motionlab_hook_mocap_v1.mp4
  const MOCAP = { url: 'refs/mocap/hook_v1_rig.json', sheet: null, J: null };
  const sheetImg = (() => { const i = new Image(); i.src = 'refs/mocap/hook_v1_overlay_sheet.jpg'; return i; })();
  function mocap() {
    if (!MOCAP.J) { const x = new XMLHttpRequest(); x.open('GET', MOCAP.url, false); x.send(); MOCAP.J = JSON.parse(x.responseText); }   // (sync: loops are synchronous)
    return MOCAP.J;
  }
  let PH = null;
  const hookMocap = () => (PH = PH || groove(CHOREO.clawdA.P(), { bounce: 0, sway: 0, curves: mocap().curves, only: [62, 66] }));
  LOOPS.motionlab_hook = t => {
    const P0 = CHOREO.clawdA.P(), Pm = hookMocap(), J = mocap(), b = t / BAR;
    X.setTransform(1, 0, 0, 1, 0, 0); X.fillStyle = '#3a3448'; X.fillRect(0, 0, W, H); X.fillStyle = '#2c2838'; X.fillRect(0, 1000, W, 80);
    X.fillStyle = '#4a4458'; X.fillRect(638, 0, 4, H); X.fillRect(1278, 0, 4, H);
    RIGS.clawd.draw(X, t, P0, { x: 320 + (P0(t).rootX || 0) * .22, y: 1030, s: .22 });
    RIGS.clawd.draw(X, t, Pm, { x: 960 + (Pm(t).rootX || 0) * .22, y: 1030, s: .22 });
    // the source frame at the warped time
    const k = Math.max(0, Math.min(J.src_time.length - 1, Math.round((t - J.grid_t[0]) * 24))), st = J.src_time[k], f = Math.max(0, Math.min(120, Math.round(st * 24)));
    if (sheetImg.complete && sheetImg.naturalWidth) X.drawImage(sheetImg, (f % 11) * 270, Math.floor(f / 11) * 480, 270, 480, 1310, 60, 540, 960);
    X.fillStyle = 'rgba(255,255,255,.75)'; X.font = '600 26px sans-serif';
    X.fillText('hand-keyed', 40, 50); X.fillText('retargeted mocap', 680, 50); X.fillText('reference (Seedance + MediaPipe)', 1300, 50);
    X.font = '20px sans-serif'; X.fillText(`bar ${b.toFixed(2)}   src ${st.toFixed(2)} s`, 40, 84);
  };
  LOOPS.motionlab_hook.len = 220;

  // the new rig range (MOTION.md, "Rig limits"): a board of static poses. t picks the page: 0 arms, 1 feet
  const RANGE = [
    [{ armR: 40, elbowR: 150 }, 'elbow 150'], [{ armR: 40, elbowR: 210, armFrontR: 1 }, 'elbow 210 (front)'], [{ armR: 40, elbowR: 280, armFrontR: 1 }, 'elbow 280 (front)'],
    [{ armR: -90, elbowR: 60, armFrontR: 1 }, 'arm -90 across'], [{ armR: 150, elbowR: 20 }, 'arm 150 overhead'], [{ armR: 170, elbowR: 60, armFrontR: 1 }, 'arm 170 + elbow'],
    [{ armL: 30, elbowL: 135, armFrontL: 1, armR: 30, elbowR: 135, armFrontR: 1 }, 'claws in front'], [{ armR: -30, elbowR: 40, armBackR: 1 }, 'arm behind'],
  ];
  const FEET = [
    [{}, 'rest'], [{ heelR: 60 }, 'heel pivot 60'], [{ footRR: 30 }, 'toe out 30'], [{ footRR: -25 }, 'toe in 25'],
    [{ footRY: 60, footRP: 1 }, 'lifted, pointed'], [{ footRY: 60, footRP: -.8 }, 'lifted, flexed'], [{ hipX: -1, hipY: 30 }, 'weight left (auto pivot)'], [{ heelL: 50, heelR: 50, hipY: -20 }, 'both heels (releve)'],
  ];
  LOOPS.motionlab_range = t => {
    const page = Math.floor(t) % 2 ? FEET : RANGE;
    X.setTransform(1, 0, 0, 1, 0, 0); X.fillStyle = '#3a3448'; X.fillRect(0, 0, W, H);
    page.forEach(([q, lab], i) => {
      const P = () => ({ view: 'F', ...q }), cx = 120 + (i % 4) * 560, cy = i < 4 ? 520 : 1060, feetOnly = page === FEET;
      if (feetOnly) { X.save(); X.beginPath(); X.rect(i * 240, 0, 238, H); X.clip(); RIGS.clawd.draw(X, 0, P, { x: 120 + i * 240 - 205 * .5, y: 1060, s: .5 }); X.restore();   // (the image-right boot)
        X.fillStyle = 'rgba(255,255,255,.9)'; X.font = '600 18px sans-serif'; X.fillText(lab, 8 + i * 240, 460); return; }
      else RIGS.clawd.draw(X, 0, P, { x: 240 + (i % 4) * 480, y: i < 4 ? 530 : 1070, s: .14 });
      X.fillStyle = 'rgba(255,255,255,.85)'; X.font = '600 22px sans-serif'; X.fillText(lab, 60 + (i % 4) * 480, i < 4 ? 40 : 580);
    });
  };
  LOOPS.motionlab_range.len = 2;

  function dump(b0 = 45, b1 = 93, fps = 24, pts = true, which = 'now') {
    const P = which === 'after' ? after() : which === 'mocap' ? hookMocap() : CHOREO.clawdA.P(), rig = RIGS.clawd, out = { fps, b0, b1, bar: BAR, t: [], P: {}, view: [], pts: {}, sp: {} };
    for (const k of CH) out.P[k] = [];
    if (pts) for (const k of PTS) out.pts[k] = [];
    for (const k of Object.keys(rig.R.springs || {})) out.sp[k] = [];
    for (let t = b0 * BAR; t < b1 * BAR; t += 1 / fps) {
      const q = P(t); out.t.push(+t.toFixed(4)); out.view.push(q.view || 'F');
      for (const k of CH) out.P[k].push(+(q[k] || 0).toFixed(4));
      const T = { x: 960 + (q.rootX || 0) * .27, y: 1040, s: .27 };
      if (pts) for (const k of PTS) { const p = rig.locate(t, P, T, k); out.pts[k].push(p ? [+p[0].toFixed(2), +p[1].toFixed(2)] : null); }
      const s = springs(rig.R, P, t); for (const k of Object.keys(s)) out.sp[k].push(+s[k].toFixed(3));
    }
    return out;
  }
  return { dump, springs, groove, mocap, CH, PTS };
})();
