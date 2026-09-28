// charkit-look inspector: look at any charkit character from any angle and see what each system is doing.
//   node engine/render.mjs projects/charkit-look --serve      then open the printed URL (Chrome, WebGPU)
//   ?vrm=charkit/out/NAME/NAME.vrm (default clawd) &qa=charkit/out/NAME/qa/qa.json (default: next to the VRM's build)
//   &trace=charkit/out/NAME/trace.jsonl (the build's state log, charkit/trace.py; default: next to the VRM)
//   review notes: served by `python -m charkit review serve BUILD` the "review notes" panel saves notes (with the camera)
// Mouse: drag orbits, shift-drag or right-drag pans, wheel zooms, click picks a part (its material and mesh data show
// under "picked"), double-click also re-centres the orbit there. Keys: 0-9 / - = debug views, f face, b body,
// o outlines, w wireframe, t T-pose / build pose, p save a PNG.
let IN = null;

async function startInspector(q) {
  const root = '../../';
  const vrmPath = q.get('vrm') || 'charkit/out/clawd/clawd.vrm';
  const name = vrmPath.split('/').pop().replace(/\.(vrm|glb)$/, '');
  const qaPath = q.get('qa') || vrmPath.replace(/[^/]+$/, 'qa/qa.json');
  const tracePath = q.get('trace') || vrmPath.replace(/[^/]+$/, 'trace.jsonl');
  document.title = `${name} · charkit inspector`;
  document.body.classList.add('inspector');
  const view = el('div', { id: 'view' }); const side = el('div', { id: 'side' });
  document.body.append(view, side);
  const hud = el('div', { id: 'hud' }); view.append(hud);
  const size = () => [Math.max(64, view.clientWidth), Math.max(64, view.clientHeight)];
  let [w, h] = size();
  const ctx = await V3.renderer({ w, h, backend: q.get('gl') || 'auto' });
  ctx.canvas.id = 'gl'; view.prepend(ctx.canvas);
  hud.textContent = `loading ${vrmPath} ...`;
  const scene = new THREE.Scene();
  const t0 = performance.now();
  const ck = await CK.load(ctx, root + vrmPath);
  scene.add(ck.scene);
  ck.buildPose(); ck.update();
  const P = CK.pipeline(ctx, { ss: 1 });
  const head = ck.head(), Hm = ck.root.height || 1.6;
  let tris = 0; ck.meshes.forEach(m => { tris += m.geometry.index.count / 3; });
  const S = IN = {
    ck, P, ctx, scene, name, dirty: true, pose: 'build', wire: false, ortho: false, lens: 85,
    orbit: { target: new THREE.Vector3(0, head.centre.y, 0), az: 25, el: 3, dist: 1.1 },
    bones: {}, exprs: {}, keys: {}, gaze: [0, 0], lightAzEl: null, motion: null, t: 0,
  };
  const mark = () => { S.dirty = true; };

  // ---------------------------------------------------------------- camera
  const camera = () => {
    const [W_, H_] = [ctx.w, ctx.h], a = S.orbit.az * Math.PI / 180, e = S.orbit.el * Math.PI / 180;
    const off = new THREE.Vector3(Math.sin(a) * Math.cos(e), Math.sin(e), Math.cos(a) * Math.cos(e)).multiplyScalar(S.orbit.dist);
    const half = Math.atan(18 / S.lens), asp = W_ / H_;
    const vfov = asp >= 1 ? 2 * Math.atan(Math.tan(half) / asp) : 2 * half;
    let cam;
    if (S.ortho) {                                           // the same framing at the orbit distance
      const hv = S.orbit.dist * Math.tan(vfov / 2);
      cam = new THREE.OrthographicCamera(-hv * asp, hv * asp, hv, -hv, 0.01, 100);
    } else cam = new THREE.PerspectiveCamera(vfov * 180 / Math.PI, asp, 0.01, 100);
    cam.position.copy(S.orbit.target).add(off); cam.lookAt(S.orbit.target); cam.updateMatrixWorld(true);
    return cam;
  };
  const frame = (which) => {
    const F = { face: [head.centre.y + 0.06 * head.L, 1.0, 85], face3: [head.centre.y, 1.0, 85], body: [Hm * 0.52, 4.6, 50] }[which];
    S.orbit.target.set(0, F[0], 0); S.orbit.dist = F[1]; S.lens = F[2]; S.orbit.el = which === 'body' ? 5 : 2; mark(); sync();
  };

  // ---------------------------------------------------------------- pose, face, light
  const applyPose = () => {
    if (S.motion) { S.motion.at(S.t); }
    else if (S.pose === 'build') ck.buildPose(); else ck.restPose();
    if (!S.motion) {
      const H = ck.vrm.humanoid;
      for (const [b, e] of Object.entries(S.bones)) {
        const n = H.getNormalizedBoneNode(b); if (!n) continue;
        const q_ = new THREE.Quaternion().setFromEuler(new THREE.Euler(...e.map(d => d * Math.PI / 180), 'YXZ'));
        n.quaternion.multiply(q_);
      }
      H.update();
    }
    ck.keys(S.keys);
    ck.expressions(S.motion ? { ...S.motionFace, ...S.exprs } : S.exprs);
    ck.look(S.gaze[0], S.gaze[1]);
    ck.update();
  };
  const setLight = (az, el) => {
    const a = az * Math.PI / 180, e = el * Math.PI / 180;
    ck.setLight(new THREE.Vector3(Math.sin(a) * Math.cos(e), Math.sin(e), Math.cos(a) * Math.cos(e)));
    S.lightAzEl = [az, el];
  };
  const l0 = ck.light.clone();
  const lightDefault = [Math.atan2(l0.x, l0.z) * 180 / Math.PI, Math.asin(l0.y) * 180 / Math.PI];
  setLight(...lightDefault);

  // ---------------------------------------------------------------- render loop (on demand)
  let last = performance.now(), fps = 0;
  const draw = () => {
    const [W_, H_] = size();
    if (W_ !== ctx.w || H_ !== ctx.h) { ctx.w = W_; ctx.h = H_; ctx.renderer.setSize(W_, H_, false); S.dirty = true; }
    if (S.motion && S.playing) { S.t = (S.t + (performance.now() - last) / 1000) % S.motion.len; S.dirty = true; syncTime(); }
    const now = performance.now();
    if (S.dirty) {
      S.dirty = false;
      applyPose();
      for (const m of ck.materials) if (m.wireframe !== S.wire) { m.wireframe = S.wire; m.needsUpdate = true; }
      const t1 = performance.now();
      P.render(scene, camera(), ck, [0, 0, ctx.w, ctx.h]);
      fps = 1000 / Math.max(1, performance.now() - t1);
      const lh = CK.U.headLight.value, tS = Math.atan2(Math.abs(lh.x), lh.z) / Math.PI;
      hud.innerHTML = `${name} · ${ctx.backend} · ${Math.round(tris / 1000)}k tris + hulls · ${ctx.w}x${ctx.h}${P.ss > 1 ? ' x' + P.ss : ''} · ` +
        `${fps.toFixed(0)} fps (cpu) · view: <b>${CK.DEBUG[CK.U.debug.value]}</b> · face light t ${tS.toFixed(3)}` +
        (S.motion ? ` · t ${S.t.toFixed(2)} s` : '');
    }
    last = now;
    requestAnimationFrame(draw);
  };

  // ---------------------------------------------------------------- mouse
  let drag = null;
  ctx.canvas.addEventListener('contextmenu', e => e.preventDefault());
  ctx.canvas.addEventListener('pointerdown', e => { drag = { x: e.clientX, y: e.clientY, b: e.button, shift: e.shiftKey, moved: 0 }; ctx.canvas.setPointerCapture(e.pointerId); });
  ctx.canvas.addEventListener('pointermove', e => {
    if (!drag) return;
    const dx = e.clientX - drag.x, dy = e.clientY - drag.y; drag.x = e.clientX; drag.y = e.clientY; drag.moved += Math.abs(dx) + Math.abs(dy);
    if (drag.b === 2 || drag.shift) {
      const cam = camera(), k = S.orbit.dist * 36 / S.lens / ctx.h;
      const right = new THREE.Vector3().setFromMatrixColumn(cam.matrixWorld, 0), up = new THREE.Vector3().setFromMatrixColumn(cam.matrixWorld, 1);
      S.orbit.target.addScaledVector(right, -dx * k).addScaledVector(up, dy * k);
    } else { S.orbit.az -= dx * 0.4; S.orbit.el = Math.max(-89, Math.min(89, S.orbit.el + dy * 0.3)); }
    mark(); sync();
  });
  ctx.canvas.addEventListener('pointerup', e => { if (drag && drag.moved < 4 && drag.b === 0) pick(e, false); drag = null; });
  ctx.canvas.addEventListener('dblclick', e => pick(e, true));
  ctx.canvas.addEventListener('wheel', e => { e.preventDefault(); S.orbit.dist = Math.max(0.05, Math.min(30, S.orbit.dist * Math.exp(e.deltaY * 0.0012))); mark(); sync(); }, { passive: false });
  const rc = new THREE.Raycaster();
  const pick = (e, recentre) => {
    const r = ctx.canvas.getBoundingClientRect();
    rc.setFromCamera(new THREE.Vector2((e.clientX - r.left) / r.width * 2 - 1, 1 - (e.clientY - r.top) / r.height * 2), camera());
    const hits = rc.intersectObjects(ck.meshes.filter(m => m.visible), false);
    if (!hits.length) return;
    const hit = hits[0], u = hit.object.userData.ck;
    if (recentre) { S.orbit.target.copy(hit.point); mark(); }
    showPick(hit, u);
  };

  // ---------------------------------------------------------------- keys
  window.addEventListener('keydown', e => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT' || e.target.tagName === 'TEXTAREA') return;
    const k = e.key;
    if (/^[0-9]$/.test(k)) setDebug(+k); else if (k === '-') setDebug(10); else if (k === '=') setDebug(11);
    else if (k === 'f') frame('face'); else if (k === 'b') frame('body');
    else if (k === 'o') { CK.U.outline.value = CK.U.outline.value ? 0 : 1; mark(); sync(); }
    else if (k === 'w') { S.wire = !S.wire; mark(); sync(); }
    else if (k === 't') { S.pose = S.pose === 'build' ? 'rest' : 'build'; mark(); sync(); }
    else if (k === 'p') savePNG();
  });
  const setDebug = i => { CK.U.debug.value = Math.max(0, Math.min(CK.DEBUG.length - 1, i)); mark(); sync(); };
  const savePNG = () => { requestAnimationFrame(() => { const a = document.createElement('a'); a.download = `${name}_${CK.DEBUG[CK.U.debug.value]}.png`; a.href = ctx.canvas.toDataURL('image/png'); a.click(); }); S.dirty = true; };

  // ---------------------------------------------------------------- the side panel
  const syncers = [];
  const sync = () => syncers.forEach(f => f());
  let syncTime = () => {};
  const sec = (title, open = true) => { const d = el('details', { open }); d.append(el('summary', {}, title)); side.append(d); return d; };
  const row = (parent, label, input, out) => { const r = el('div', { class: 'row' }); r.append(el('label', {}, label), input); if (out) r.append(out); parent.append(r); return r; };
  const slider = (parent, label, min, max, step, get, set, fmt = v => (+v).toFixed(2)) => {
    const i = el('input', { type: 'range', min, max, step }); const o = el('span', { class: 'val' });
    i.value = get(); o.textContent = fmt(get());
    i.oninput = () => { set(+i.value); o.textContent = fmt(+i.value); mark(); };
    i.ondblclick = () => { set(0); i.value = 0; o.textContent = fmt(0); mark(); };
    syncers.push(() => { i.value = get(); o.textContent = fmt(get()); });
    return row(parent, label, i, o);
  };
  const check = (parent, label, get, set) => {
    const i = el('input', { type: 'checkbox' }); i.checked = get();
    i.onchange = () => { set(i.checked); mark(); };
    syncers.push(() => { i.checked = get(); });
    return row(parent, label, i);
  };
  const select = (parent, label, opts, get, set) => {
    const s = el('select'); opts.forEach(([v, t]) => s.append(el('option', { value: v }, t)));
    s.value = get(); s.onchange = () => { set(s.value); mark(); };
    syncers.push(() => { s.value = String(get()); });
    return row(parent, label, s);
  };
  const buttons = (parent, list) => { const r = el('div', { class: 'btns' }); list.forEach(([t, f]) => { const b = el('button', {}, t); b.onclick = f; r.append(b); }); parent.append(r); };

  side.append(el('div', { class: 'title' }, `${name}`), el('div', { class: 'sub' }, `${vrmPath} · ${ck.meshes.length} primitives · ${Object.keys(ck.parts).length} parts · ${Math.round(tris / 1000)}k tris · ${ctx.backend} · loaded in ${Math.round(performance.now() - t0)} ms`));

  const V = sec('view');
  buttons(V, [['face', () => frame('face')], ['body', () => frame('body')], ['front', () => { S.orbit.az = 0; S.orbit.el = 0; mark(); sync(); }],
    ['3/4', () => { S.orbit.az = 35; mark(); sync(); }], ['side', () => { S.orbit.az = 90; mark(); sync(); }], ['back', () => { S.orbit.az = 180; mark(); sync(); }], ['PNG', savePNG]]);
  select(V, 'debug view', CK.DEBUG.map((d, i) => [i, `${i < 10 ? i : i === 10 ? '-' : '='} · ${d}`]), () => CK.U.debug.value, v => { CK.U.debug.value = +v; });
  select(V, 'weights bone', ck.joints.map(j => [ck.joints.indexOf(j), j]), () => CK.U.bone.value, v => { CK.U.bone.value = +v; });
  select(V, 'pose', [['build', 'build pose (Blender, A)'], ['rest', 'file rest (VRM T-pose)']], () => S.pose, v => { S.pose = v; });
  slider(V, 'lens mm', 20, 200, 1, () => S.lens, v => { S.lens = v; }, v => (+v).toFixed(0));
  check(V, 'orthographic', () => S.ortho, v => { S.ortho = v; });
  check(V, 'wireframe', () => S.wire, v => { S.wire = v; });
  select(V, 'supersample', [[1, '1x (interactive)'], [2, '2x (as the boards)']], () => P.ss, v => { P.ss = +v; });
  const L = sec('look systems');
  slider(L, 'outline width x', 0, 4, 0.05, () => CK.U.outline.value, v => { CK.U.outline.value = v; });
  check(L, 'rim', () => CK.U.rim.value > 0, v => { CK.U.rim.value = v ? 1 : 0; });
  check(L, 'SDF face shadow', () => CK.U.sdf.value > 0, v => { CK.U.sdf.value = v ? 1 : 0; });
  check(L, 'hair ring', () => CK.U.ring.value > 0, v => { CK.U.ring.value = v ? 1 : 0; });
  slider(L, 'eyes through hair', 0, 1, 0.01, () => P.through == null ? ((ck.root.features || {}).through || 0.55) : P.through, v => { P.through = v; });
  slider(L, 'bloom', 0, 1.5, 0.01, () => P.bloom, v => { P.bloom = v; });
  slider(L, 'bloom threshold', 0.5, 1, 0.01, () => P.bloomThreshold, v => { P.bloomThreshold = v; });
  const Lt = sec('light');
  slider(Lt, 'azimuth', -180, 180, 1, () => S.lightAzEl[0], v => setLight(v, S.lightAzEl[1]), v => (+v).toFixed(0) + '°');
  slider(Lt, 'elevation', -89, 89, 1, () => S.lightAzEl[1], v => setLight(S.lightAzEl[0], v), v => (+v).toFixed(0) + '°');
  buttons(Lt, [['default (the file\'s)', () => { setLight(...lightDefault); mark(); sync(); }], ['orbit light (60 s)', () => {
    const a0 = S.lightAzEl[0], t0_ = performance.now();
    const spin = () => { const t = (performance.now() - t0_) / 1000; if (t > 60) return; setLight(a0 + t * 12, S.lightAzEl[1]); mark(); sync(); requestAnimationFrame(spin); }; spin(); }]]);
  Lt.append(el('div', { class: 'note' }, 'toon3 steps on half-lambert N·L of this light; the face reads it in head space (t in the status bar: 0 front, 0.5 side, 1 behind).'));

  const Pt = sec('parts');
  const partNames = Object.keys(ck.parts).sort();
  buttons(Pt, [['all', () => { partNames.forEach(n => ck.setVisible(n, true)); mark(); sync(); }], ['none', () => { partNames.forEach(n => ck.setVisible(n, false)); mark(); sync(); }],
    ['hide hair', () => { partNames.filter(n => /hair|bun|star|crab/.test(n)).forEach(n => ck.setVisible(n, false)); mark(); sync(); }],
    ['hide outfit', () => { partNames.filter(n => !/skin|hair|sclera|iris|lash|brow|teeth|tongue|mouth|star|crab/.test(n)).forEach(n => ck.setVisible(n, false)); mark(); sync(); }]]);
  for (const n of partNames) {
    const p = ck.parts[n], M = p.look || {};
    const tags = [M.outline ? 'outline' : '', M.feature ? 'feature' : '', M.holdout ? 'holdout' : ''].filter(Boolean).join(' ');
    const r = check(Pt, n, () => p.visible, v => ck.setVisible(n, v));
    r.title = 'alt-click: solo';
    r.querySelector('label').onclick = e => { if (e.altKey) { partNames.forEach(m => ck.setVisible(m, m === n)); mark(); sync(); } };
    r.append(el('span', { class: 'tag' }, tags));
  }

  const Ex = sec('expressions (VRM)');
  const presets = ['aa', 'ih', 'ou', 'ee', 'oh', 'blink', 'blinkLeft', 'blinkRight', 'happy', 'angry', 'sad', 'relaxed', 'surprised', 'lookUp', 'lookDown', 'lookLeft', 'lookRight'];
  buttons(Ex, [['reset', () => { S.exprs = {}; S.keys = {}; S.gaze = [0, 0]; mark(); sync(); }]]);
  for (const x of presets.filter(p => ck.expressionNames.includes(p))) slider(Ex, x, 0, 1, 0.01, () => S.exprs[x] || 0, v => { S.exprs[x] = v; });
  const Cu = sec('expressions (custom)', false);
  for (const x of ck.expressionNames.filter(p => !presets.includes(p) && p !== 'neutral')) slider(Cu, x, 0, 1, 0.01, () => S.exprs[x] || 0, v => { S.exprs[x] = v; });
  const K = sec('shape keys (raw)', false);
  K.append(el('div', { class: 'note' }, 'added on top of the expressions: every mesh carrying the key gets it (as charkit.boards set_expr / set_mouth do).'));
  for (const k of ck.keyNames) slider(K, k, 0, 1, 0.01, () => S.keys[k] || 0, v => { S.keys[k] = v; });
  const G = sec('gaze (lookAt)');
  slider(G, 'yaw', -30, 30, 0.5, () => S.gaze[0], v => { S.gaze[0] = v; }, v => (+v).toFixed(1) + '°');
  slider(G, 'pitch', -25, 25, 0.5, () => S.gaze[1], v => { S.gaze[1] = v; }, v => (+v).toFixed(1) + '°');
  const B = sec('bones', false);
  B.append(el('div', { class: 'note' }, 'degrees on the normalized humanoid (x pitch, y yaw, z roll), on top of the pose. Double-click a slider: 0.'));
  const boneAxes = { head: 'xyz', neck: 'xyz', upperChest: 'xyz', chest: 'xyz', spine: 'xyz', hips: 'y', leftUpperArm: 'xz', rightUpperArm: 'xz',
    leftLowerArm: 'y', rightLowerArm: 'y', leftHand: 'xz', rightHand: 'xz', leftUpperLeg: 'xz', rightUpperLeg: 'xz', leftLowerLeg: 'x', rightLowerLeg: 'x' };
  for (const [b, axes] of Object.entries(boneAxes)) {
    if (!ck.vrm.humanoid.getNormalizedBoneNode(b)) continue;
    for (const ax of axes) {
      const i = 'xyz'.indexOf(ax);
      slider(B, `${b}.${ax}`, -90, 90, 1, () => (S.bones[b] || [0, 0, 0])[i], v => { (S.bones[b] = S.bones[b] || [0, 0, 0])[i] = v; }, v => (+v).toFixed(0) + '°');
    }
  }
  buttons(B, [['reset bones', () => { S.bones = {}; mark(); sync(); }]]);

  const Mo = sec('motion', false);
  const tIn = el('input', { type: 'range', min: 0, max: 5, step: 1 / 24, value: 0 }), tOut = el('span', { class: 'val' }, '0.00');
  tIn.oninput = () => { S.t = +tIn.value; tOut.textContent = S.t.toFixed(2); mark(); };
  syncTime = () => { tIn.value = S.t; tOut.textContent = S.t.toFixed(2); };
  buttons(Mo, [['load the hook clip', async () => {
    const clip = await (await fetch('../vrm-test/assets/hook_v1.motion.json')).json();
    const blink = V3.blinks(60);
    S.motion = V3.performer(ck.vrm, clip, { fps: 24 });
    const at = S.motion.at; S.motion.at = t => { at(t); const f = blink(t); S.motionFace = f.eyesHalf ? { eye_half: 1 } : f; };
    tIn.max = S.motion.len; frame('body'); mark();
  }], ['play / pause', () => { S.playing = !S.playing; last = performance.now(); }], ['stop (back to the pose)', () => { S.motion = null; S.playing = false; mark(); }]]);
  row(Mo, 't (s)', tIn, tOut);
  Mo.append(el('div', { class: 'note' }, 'projects/vrm-test\'s canonical clip retargeted by engine/three/vrm.js (springs stepped from t = 0 on a fixed grid, so any t gives the same frame).'));

  const Pk = sec('picked');
  const pickBox = el('pre', { class: 'json' }, 'click the character');
  Pk.append(pickBox);
  const showPick = (hit, u) => {
    const g = hit.object.geometry;
    const info = { part: u.name, primitive: u.prim, vertices: g.attributes.position.count, triangles: g.index.count / 3,
      attributes: Object.keys(g.attributes), morphTargets: Object.keys(hit.object.morphTargetDictionary || {}).length,
      point: hit.point.toArray().map(v => +v.toFixed(4)), mesh: u.mesh, material: u.look };
    pickBox.textContent = JSON.stringify(info, (k, v) => (Array.isArray(v) && v.length > 6 && typeof v[0] === 'number' ? v.map(x => +(+x).toFixed(4)) : v), 1);
    Pk.open = true;
  };

  const Q = sec('QA report');
  const qBox = el('div'); Q.append(el('div', { class: 'note' }, qaPath), qBox);
  try {
    const r = await fetch(root + qaPath);
    if (!r.ok) throw new Error(r.status);
    const rep = await r.json();
    qBox.append(el('div', { class: 'badge ' + rep.summary }, `summary: ${rep.summary}`));
    const tb = el('table');
    for (const [k, c] of Object.entries(rep.checks || {})) {
      const tr = el('tr', { class: c.status });
      tr.append(el('td', {}, k), el('td', {}, c.value == null ? '' : String(c.value)), el('td', { class: 'st' }, c.status));
      tb.append(tr);
      const extra = c.per_view || c.per_garment || c.objects;
      if (extra) {
        const tr2 = el('tr'), td = el('td', { colspan: 3, class: 'sub' });
        for (const [kk, vv] of Object.entries(extra)) {
          const s = el('span', { class: 'chip' }, `${kk}: ${typeof vv === 'object' ? Object.entries(vv).map(([a, b]) => a + ' ' + b).join(', ') : vv}`);
          if (ck.parts[kk]) { s.classList.add('link'); s.title = 'solo this part'; s.onclick = () => { partNames.forEach(m => ck.setVisible(m, m === kk)); mark(); sync(); }; }
          td.append(s);
        }
        tr2.append(td); tb.append(tr2);
      }
    }
    qBox.append(tb);
    if (rep.views) {
      const tv = el('table', { class: 'views' });
      const cols = Object.keys(Object.values(rep.views)[0] || {});
      const hd = el('tr'); hd.append(el('th', {}, 'az')); cols.forEach(c => hd.append(el('th', {}, c))); tv.append(hd);
      for (const [az, v] of Object.entries(rep.views)) {
        const tr = el('tr'); const a = el('td', { class: 'link' }, az); a.onclick = () => { S.orbit.az = +az; frame('body'); S.orbit.az = +az; mark(); sync(); };
        tr.append(a); cols.forEach(c => tr.append(el('td', {}, String(v[c])))); tv.append(tr);
      }
      qBox.append(tv);
    }
    if (rep.face) {
      // the face's expressions (eye opening against neutral, iris visible) and mouth shapes (opening, in head lengths)
      const te = el('table', { class: 'views' });
      const hd = el('tr'); ['expression', 'open L', 'open R', 'iris L', 'iris R'].forEach(c => hd.append(el('th', {}, c))); te.append(hd);
      for (const [k, v] of Object.entries(rep.face.eyes || {})) {
        if (!v || !v.L) continue;
        const tr = el('tr'); tr.append(el('td', {}, k), el('td', {}, String(v.L.open)), el('td', {}, String(v.R.open)),
          el('td', {}, String(v.L.iris)), el('td', {}, String(v.R.iris))); te.append(tr);
      }
      const tm = el('table', { class: 'views' });
      const hm = el('tr'); ['mouth', 'area', 'width', 'height', 'asym'].forEach(c => hm.append(el('th', {}, c))); tm.append(hm);
      for (const [k, v] of Object.entries(rep.face.mouth || {})) {
        const tr = el('tr'); tr.append(el('td', {}, k), el('td', {}, String(v.area_L2)), el('td', {}, String(v.width_L)),
          el('td', {}, String(v.height_L)), el('td', {}, String(v.asym))); tm.append(tr);
      }
      qBox.append(el('div', { class: 'note' }, 'face, from the shape keys (eyes: opening against neutral, share of iris visible; mouth: in head lengths)'), te, tm);
    }
    const dir = qaPath.replace(/[^/]+$/, '');
    // the model sheet (figures found, face, whole body per view, expression heads, palette), then the rest
    for (const f of ['qa_sheet_figures.png', 'qa_sheet.png', 'qa_sheet_body.png', 'qa_sheet_expr.png', 'qa_sheet_palette.png',
      'qa_eyes.png', 'qa_face_contours.png', 'qa_face_shape.png', 'qa_shape_overlay.png', 'qa_ref_overlay.png', 'qa_scalp_front.png']) {
      const im = new Image(); im.className = 'qaimg'; im.title = f;
      im.onload = () => qBox.append(im); im.src = root + dir + f;
      im.onclick = () => window.open(im.src);
    }
  } catch (e) { qBox.append(el('div', { class: 'note' }, 'no QA report (' + e.message + '): charkit/qa3d.py writes out/NAME/qa/qa.json')); }

  // ---------------------------------------------------------------- review notes (charkit/review.py)
  // what the checks miss, written where it is seen: saved with this camera to BUILD/review/notes.json when the page is
  // served by `python -m charkit review serve BUILD` (the plain --serve server is read only)
  const Rv = sec('review notes', false);
  const buildDir = qaPath.replace(/qa\/qa\.json$/, '').replace(/\/$/, '');
  const notesPath = buildDir + '/review/notes.json';
  const nBox = el('div'), nMsg = el('div', { class: 'note' }, `${notesPath} · save needs: python -m charkit review serve ${buildDir}`);
  const nText = el('textarea', { rows: 3, style: 'width:100%', placeholder: "what the numbers miss: 'the face reads long'" });
  const nView = el('select'); ['', 'front', 'three_quarter', 'profile', 'back', 'body', 'expressions'].forEach(v => nView.append(el('option', { value: v }, v || 'view')));
  const nRegion = el('select'); ['', 'face', 'eyes', 'hair', 'silhouette', 'outfit', 'expressions', 'palette'].forEach(v => nRegion.append(el('option', { value: v }, v || 'region')));
  const nSev = el('select'); [[1, '1 minor'], [2, '2 visible'], [3, '3 reads wrong']].forEach(([v, t]) => nSev.append(el('option', { value: v }, t))); nSev.value = 2;
  Rv.append(nText); row(Rv, 'view · region', nView, nRegion); row(Rv, 'severity', nSev);
  const loadNotes = async () => {
    try {
      const r = await fetch(root + notesPath, { cache: 'no-store' }); if (!r.ok) throw new Error(r.status);
      const N = await r.json(); nBox.textContent = '';
      for (const n of N.notes.slice().reverse()) nBox.append(el('div', { class: 'obj' }, `${n.id} [${n.view || '-'}/${n.region || '-'} s${n.severity}] ${n.text}${n.ticket ? ' -> ' + n.ticket : ''}`));
    } catch (e) { nBox.textContent = 'no notes yet'; }
  };
  buttons(Rv, [['save note (with this camera)', async () => {
    if (!nText.value.trim()) return;
    const camera = { az: +S.orbit.az.toFixed(1), el: +S.orbit.el.toFixed(1), dist: +S.orbit.dist.toFixed(3), lens: S.lens, ortho: S.ortho,
      target: S.orbit.target.toArray().map(v => +v.toFixed(4)), debug: CK.DEBUG[CK.U.debug.value], pose: S.pose };
    try {
      const r = await fetch('/api/note', { method: 'POST', body: JSON.stringify({ build: buildDir, text: nText.value, view: nView.value || null,
        region: nRegion.value || null, severity: +nSev.value, camera }) });
      if (!r.ok) throw new Error(r.status);
      nMsg.textContent = 'saved ' + (await r.json()).note.id; nText.value = ''; loadNotes();
    } catch (e) { nMsg.textContent = `not saved (${e.message}): serve with python -m charkit review serve ${buildDir}`; }
  }]]);
  Rv.append(nMsg, nBox); loadNotes();

  // ---------------------------------------------------------------- the build's state log (charkit/trace.py)
  const Tr = sec('build trace', false);
  const tBox = el('div'); Tr.append(el('div', { class: 'note' }, tracePath), tBox);
  try {
    const r = await fetch(root + tracePath);
    if (!r.ok) throw new Error(r.status);
    const recs = (await r.text()).split('\n').filter(l => l.trim()).map(l => JSON.parse(l));
    const b = recs.find(x => x.event === 'begin') || {}, end = recs.find(x => x.event === 'end') || {};
    tBox.append(el('div', { class: 'sub' }, `git ${b.git} · blender ${b.blender} · spec ${b.spec_hash} · total ${end.total}s`));
    const timed = recs.filter(x => x.event === 'stage' || x.event === 'span');
    const tmax = Math.max(...timed.map(x => x.dt), 1e-3);
    const tb = el('table', { class: 'trace' });
    const HEALTH = ['open_edges', 'nonmanifold_edges', 'inverted_shells', 'degenerate_faces', 'loose_verts'];
    const solo = (s, nm) => { if (ck.parts[nm]) { s.classList.add('link'); s.title = 'solo this part'; s.onclick = () => { partNames.forEach(m => ck.setVisible(m, m === nm)); mark(); sync(); }; } };
    for (const x of recs) {
      if (x.event === 'stage' || x.event === 'span') {
        const tr = el('tr', { class: x.event });
        const label = x.event === 'stage' ? x.name : `  ${x.name}${x.path ? ' ' + x.path : ''}`;
        const bar = el('td', { style: 'width:34%' }); bar.append(el('span', { class: 'bar', style: `width:${Math.max(1, 100 * x.dt / tmax)}%` }));
        const what = x.event === 'stage' ? `${x.objects} obj (+${Object.keys(x.added).length} ~${Object.keys(x.changed).length} -${x.removed.length})` : '';
        tr.append(el('td', {}, label), el('td', {}, x.dt.toFixed(2) + 's'), bar, el('td', { class: 'sub' }, what));
        tb.append(tr);
        if (x.event === 'stage') {
          const objs = { ...x.added, ...x.changed };
          const names = Object.keys(objs).sort();
          if (names.length) {
            const tr2 = el('tr'), td = el('td', { colspan: 4, class: 'sub' });
            for (const nm of names) {
              const o = objs[nm], hl = o.health;
              const flags = hl ? HEALTH.filter(k => hl[k] && !(k === 'open_edges' && o.sheet)).map(k => `${k.replace('_edges', '').replace('_', ' ')} ${hl[k]}`) : [];
              const s = el('div', { class: 'obj' + (flags.length ? ' bad' : '') },
                hl ? `${x.changed[nm] ? '~' : '+'} ${nm}: v${hl.verts} f${hl.faces} shells ${hl.shells}${o.sheet ? ' (sheet)' : ''}${flags.length ? ' · ' + flags.join(', ') : ''}` : `+ ${nm} (${o.type.toLowerCase()})`);
              solo(s, nm); td.append(s);
            }
            tr2.append(td); tb.append(tr2);
          }
        }
      } else if (x.event === 'note') {
        const { t, event, name, ...vals } = x;
        const tr = el('tr', { class: 'note' }); tr.append(el('td', { colspan: 4, class: 'sub' }, `note ${name}: ${JSON.stringify(vals)}`)); tb.append(tr);
      }
    }
    tBox.append(tb, el('div', { class: 'note' }, 'python -m charkit trace A/trace.jsonl B/trace.jsonl prints what changed between two builds'));
  } catch (e) { tBox.append(el('div', { class: 'note' }, 'no trace (' + e.message + '): python -m charkit build writes out/NAME/trace.jsonl')); }

  const Ab = sec('file (' + CK.EXT + ')', false);
  Ab.append(el('pre', { class: 'json' }, JSON.stringify({ ...ck.root, bindPose: Object.keys(ck.root.bindPose || {}).length + ' bones' }, null, 1)));

  frame('face3'); S.orbit.az = 25;
  window.IN = S;
  requestAnimationFrame(draw);
}

function el(tag, attrs = {}, text) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'open') { if (v) e.setAttribute('open', ''); }
    else e.setAttribute(k, v);
  }
  if (text != null) e.textContent = text;
  return e;
}
