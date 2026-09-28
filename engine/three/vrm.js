// engine/three/vrm.js: a VRM character in three.js, posed and animated as a pure function of time (docs/PIPELINE_3D.md §1:
// one character, two runtimes). Needs engine/vendor/three-vrm.js (window.THREE, with THREE.VRM and THREE.GLTFLoader) loaded
// first. Plain script: defines the global V3 (like the rest of engine/).
//
//   const ctx = await V3.renderer({ w: W, h: H, backend: 'auto' })  // 'auto' | 'webgpu' | 'webgpu-gl' | 'webgl'; ctx.backend
//                                                                     // says which ran ('auto': WebGPU if an adapter exists)
//   const vrm = await V3.load(ctx, url)                              // VRM 1.0 (or 0.x), MToon (node material under WebGPU)
//   const clip = await (await fetch(motionJson)).json()               // charkit/export.py --clip (canonical clip, world rotations)
//   const { scene } = V3.stage({ bg: 0xffffff }); scene.add(vrm.scene)  // key light from kit.LDIR at intensity π, no fill
//   const P = V3.performer(vrm, clip, { face })                       // retarget (rest-pose calibration), springs, face track
//   P.at(t)                                                           // pose + springs (stepped from t=0 on a fixed grid) + face
//   const cam = V3.camera({ az: 35, dist: 4.2, height: 0.25, target: [0, 0.8, 0], lens: 40, aspect })  // Blender-style framing
//   await V3.warm(ctx, scene, cam)                                    // once, before the first frame (bit-exact frames after)
//   V3.draw(ctx, scene, [[cam, x, y, w, h, before?], ...]); X.drawImage(ctx.canvas, 0, 0)  // one or more viewports
//
// Frames: VRM 1.0 and the canonical clip are both Y up, facing +Z, metres; her left is +X. Blender is Z up, facing -Y:
// V3.fromBlender([x, y, z]) = [x, z, -y].
// Retarget (projects/clawd3d/build/motion.py's recipe, against the VRM's normalized humanoid, whose rest rotations are all
// identity in the T-pose): calibrate by aiming each mapped bone along its source bone's rest direction (the hands also
// turned so the knuckle line matches), then per frame  W_bone(t) = G_source(t) · Wcal_bone,  local = W_parent⁻¹ · W_bone.
// Springs: VRM spring bones, reset at t = 0 and stepped on a fixed 1/(fps·substeps) grid, so any t gives the same pose
// whatever order frames are asked for (a cache continues forward; going back replays from 0). No clock, no Math.random.

(() => {
  const T = window.THREE;
  const V3 = {};
  V3.fromBlender = ([x, y, z]) => [x, z, -y];
  V3.LDIR = V3.fromBlender([0.35, -0.55, 0.75]);           // kit.LDIR: toward the key light

  // ---------------------------------------------------------------- renderer
  V3.webgpuAvailable = async () => {
    if (!navigator.gpu) return { ok: false, why: 'navigator.gpu missing' };
    try {
      const a = await navigator.gpu.requestAdapter();
      if (!a) return { ok: false, why: 'requestAdapter() returned null' };
      const info = a.info || {};
      return { ok: true, adapter: [info.vendor, info.architecture, info.device, info.description].filter(Boolean).join(' ') };
    } catch (e) { return { ok: false, why: String(e) }; }
  };
  V3.renderer = async ({ w = 1920, h = 1080, backend = 'auto', canvas = null, antialias = true } = {}) => {
    canvas = canvas || document.createElement('canvas');
    canvas.width = w; canvas.height = h;
    const gpu = await V3.webgpuAvailable();
    const want = backend === 'auto' ? (gpu.ok ? 'webgpu' : 'webgl') : backend;
    let r, name;
    if (want === 'webgpu' || want === 'webgpu-gl') {        // 'webgpu-gl': WebGPURenderer on its WebGL2 backend
      r = new T.WebGPURenderer({ canvas, antialias, alpha: false, forceWebGL: want === 'webgpu-gl' });
      await r.init();
      name = r.backend && r.backend.isWebGPUBackend ? 'WebGPU' : 'WebGL2 (WebGPURenderer fallback)';
    } else {
      r = new T.WebGLRenderer({ canvas, antialias, alpha: false, preserveDrawingBuffer: true });
      name = r.capabilities.isWebGL2 ? 'WebGL2' : 'WebGL1';
    }
    r.setPixelRatio(1); r.setSize(w, h, false);
    r.outputColorSpace = T.SRGBColorSpace;
    r.toneMapping = T.NoToneMapping;
    r.autoClear = false;
    return { renderer: r, canvas, w, h, backend: name, node: want !== 'webgl', gpu };
  };

  // ---------------------------------------------------------------- loading
  V3.load = async (ctx, url) => {
    const loader = new T.GLTFLoader();
    loader.register(parser => {
      const opt = {};
      if (ctx.node) opt.mtoonMaterialPlugin = new T.VRM.MToonMaterialLoaderPlugin(parser, { materialType: T.MToonNodeMaterial });
      return new T.VRM.VRMLoaderPlugin(parser, opt);
    });
    const gltf = await loader.loadAsync(url);
    const vrm = gltf.userData.vrm;
    if (!vrm) throw new Error(url + ': no VRM in the file');
    if (vrm.meta && vrm.meta.metaVersion === '0') T.VRM.VRMUtils.rotateVRM0(vrm);
    vrm.scene.traverse(o => { o.frustumCulled = false; });  // skinned bounds are the rest pose's
    vrm.scene.updateMatrixWorld(true);
    return vrm;
  };

  // ---------------------------------------------------------------- stage: a key light from kit.LDIR, no fill (MToon's
  // shade colour is the fill), so lit = base colour and shadow = shade colour, as in the Blender emission shaders. MToon
  // lights with lightColor · BRDF_Lambert (1/π): intensity π gives the colours back exactly.
  V3.stage = ({ bg = 0xffffff, ldir = V3.LDIR, intensity = Math.PI, ambient = 0 } = {}) => {
    const scene = new T.Scene();
    scene.background = new T.Color(bg);
    const key = new T.DirectionalLight(0xffffff, intensity);
    key.position.set(...ldir); scene.add(key); scene.add(key.target);
    if (ambient) scene.add(new T.AmbientLight(0xffffff, ambient));
    return { scene, key };
  };

  // Blender-style camera: az degrees round her from the front (+ = toward her left), dist and height relative to the
  // target (Blender's kit.aim(cam, tgt + (sin a·d, -cos a·d, h), tgt)); lens mm on a 36 mm sensor fitted to the longer side
  V3.camera = ({ az = 0, dist = 4.2, height = 0.25, target = [0, 0.8, 0], lens = 40, aspect = 16 / 9, near = 0.05, far = 100 } = {}) => {
    const half = Math.atan(18 / lens);
    const vfov = aspect >= 1 ? 2 * Math.atan(Math.tan(half) / aspect) : 2 * half;
    const cam = new T.PerspectiveCamera(vfov * 180 / Math.PI, aspect, near, far);
    const a = az * Math.PI / 180;
    cam.position.set(target[0] + Math.sin(a) * dist, target[1] + height, target[2] + Math.cos(a) * dist);
    cam.lookAt(new T.Vector3(...target));
    cam.updateMatrixWorld(true);
    return cam;
  };

  // render viewports [[camera, x, y, w, h, before?], ...] (canvas pixels, y from the top) into ctx.canvas; before() runs
  // ahead of its viewport (set a pose or an expression per cell)
  V3.draw = (ctx, scene, views) => {
    const r = ctx.renderer;
    r.setScissorTest(false);
    r.setClearColor(scene.background || new T.Color(0xffffff), 1);
    r.clear();
    r.setScissorTest(true);
    for (const [cam, x, y, w, h, before] of views) {
      if (before) before();
      const yy = r.isWebGPURenderer ? y : ctx.h - y - h;    // WebGLRenderer's viewports count from the bottom
      r.setViewport(x, yy, w, h); r.setScissor(x, yy, w, h);
      r.render(scene, cam);
    }
    r.setScissorTest(false);
  };

  // compile every pipeline and draw once before the first real frame: under WebGPU the first frame on a page otherwise
  // differs by a few levels in a few dozen pixels (texture/mip upload), which breaks bit-exact A/B checks
  V3.warm = async (ctx, scene, cam) => {
    const r = ctx.renderer;
    if (r.compileAsync) await r.compileAsync(scene, cam);
    V3.draw(ctx, scene, [[cam, 0, 0, ctx.w, ctx.h]]);
    if (r.backend && r.backend.device) await r.backend.device.queue.onSubmittedWorkDone();
    V3.draw(ctx, scene, [[cam, 0, 0, ctx.w, ctx.h]]);
  };

  // ---------------------------------------------------------------- retarget (canonical clip -> normalized humanoid)
  const PREF_CHILD = {
    hips: 'spine', spine: 'chest', chest: 'upperChest', upperChest: 'neck', neck: 'head',
  };
  for (const s of ['left', 'right']) Object.assign(PREF_CHILD, {
    [s + 'Shoulder']: s + 'UpperArm', [s + 'UpperArm']: s + 'LowerArm', [s + 'LowerArm']: s + 'Hand', [s + 'Hand']: s + 'MiddleProximal',
    [s + 'UpperLeg']: s + 'LowerLeg', [s + 'LowerLeg']: s + 'Foot', [s + 'Foot']: s + 'Toes',
    [s + 'ThumbMetacarpal']: s + 'ThumbProximal', [s + 'ThumbProximal']: s + 'ThumbDistal',
    ...Object.fromEntries(['Index', 'Middle', 'Ring', 'Little'].flatMap(f => [[s + f + 'Proximal', s + f + 'Intermediate'], [s + f + 'Intermediate', s + f + 'Distal']])),
  });

  V3.retarget = (vrm, clip) => {
    const H = vrm.humanoid, node = b => H.getNormalizedBoneNode(b);
    const bones = T.VRM.VRMHumanBoneList.filter(b => node(b));
    const parentOf = b => { let p = T.VRM.VRMHumanBoneParentMap[b]; while (p && !node(p)) p = T.VRM.VRMHumanBoneParentMap[p]; return p || null; };
    // parents-first order
    const order = [], seen = new Set();
    const visit = b => { if (seen.has(b)) return; const p = parentOf(b); if (p) visit(p); seen.add(b); order.push(b); };
    bones.forEach(visit);
    // rest positions (normalized rest = the VRM's T-pose; rotations identity)
    H.resetNormalizedPose(); vrm.scene.updateMatrixWorld(true);
    const P0 = {}; for (const b of bones) P0[b] = node(b).getWorldPosition(new T.Vector3());
    const restDir = b => {                                   // the bone's length axis in the T-pose
      let c = PREF_CHILD[b];
      if (b === 'chest' && !node('upperChest')) c = 'neck';
      if (c && node(c)) return P0[c].clone().sub(P0[b]).normalize();
      if (b === 'head') return new T.Vector3(0, 1, 0);
      if (/Toes$/.test(b)) return new T.Vector3(0, 0, 1);
      const p = parentOf(b); return p ? restDir(p) : new T.Vector3(0, 1, 0);  // distal digits continue their parent
    };
    const src = clip.joints, J = Object.fromEntries(src.map((j, i) => [j, i]));
    const rest = j => new T.Vector3(...clip.rest[j]);
    const swing = (a, b) => new T.Quaternion().setFromUnitVectors(a.clone().normalize(), b.clone().normalize());
    // calibration: the normalized pose that matches the source's rest pose
    const Wcal = {};
    for (const b of order) {
      const p = parentOf(b);
      let q = p ? Wcal[p].clone() : new T.Quaternion();
      const m = clip.map[b];
      if (m && clip.rest[m[0]] && clip.rest[m[1]]) {
        const want = rest(m[1]).sub(rest(m[0]));
        if (want.lengthSq() > 1e-12) q = swing(restDir(b).applyQuaternion(q), want).multiply(q);
      }
      const tw = clip.twist && clip.twist[b];
      const idx = b.replace('Hand', 'IndexProximal'), lit = b.replace('Hand', 'LittleProximal');
      if (tw && node(idx) && node(lit)) {                    // turn about the length so the knuckle line matches
        const axis = restDir(b).applyQuaternion(q).normalize();
        const flat = v => v.sub(axis.clone().multiplyScalar(v.dot(axis))).normalize();
        const want = flat(rest(tw[1]).sub(rest(tw[0])));
        const have = flat(P0[lit].clone().sub(P0[idx]).applyQuaternion(q));
        let ang = Math.acos(Math.max(-1, Math.min(1, have.dot(want))));
        if (have.clone().cross(want).dot(axis) < 0) ang = -ang;
        q = new T.Quaternion().setFromAxisAngle(axis, ang).multiply(q);
      }
      Wcal[b] = q;
    }
    const mapped = order.filter(b => clip.map[b] && J[clip.map[b][0]] !== undefined);
    const hips0 = P0.hips.clone(), scale = hips0.y / clip.hipsHeight, root0 = clip.root[0];
    const q0 = new T.Quaternion(), q1 = new T.Quaternion(), W = {}, inv = new T.Quaternion();
    const sample = (t) => {                                  // source world rotations and root at time t (slerp)
      const s = Math.min(Math.max(t * clip.fps, 0), clip.frames - 1), k0 = Math.floor(s), k1 = Math.min(k0 + 1, clip.frames - 1), a = s - k0;
      const G = {};
      for (const b of mapped) {
        const j = J[clip.map[b][0]];
        q0.fromArray(clip.rot[k0][j]); q1.fromArray(clip.rot[k1][j]);
        G[b] = q0.clone().slerp(q1, a);
      }
      const r0 = clip.root[k0], r1 = clip.root[k1];
      return { G, root: [0, 1, 2].map(i => r0[i] + (r1[i] - r0[i]) * a) };
    };
    // set the normalized pose for time t (pure: every mapped bone and the hips are written)
    const pose = (t) => {
      const { G, root } = sample(t);
      for (const b of order) {
        const p = parentOf(b);
        W[b] = G[b] ? G[b].clone().multiply(Wcal[b]) : (p ? W[p].clone() : new T.Quaternion());
        const local = p ? inv.copy(W[p]).invert().multiply(W[b]) : W[b];
        node(b).quaternion.copy(local);
      }
      node('hips').position.set(hips0.x + (root[0] - root0[0]) * scale, root[1] * scale, hips0.z + (root[2] - root0[2]) * scale);
    };
    return { pose, Wcal, scale, order, mapped, len: (clip.frames - 1) / clip.fps };
  };

  // ---------------------------------------------------------------- performer: motion + springs + face, a function of t
  V3.performer = (vrm, clip, { fps = 24, substeps = 2, face = null, springs = true } = {}) => {
    const R = V3.retarget(vrm, clip);
    const E = vrm.expressionManager;
    const dt = 1 / (fps * substeps);
    let sim = null;                                          // { n }: spring state stepped to grid step n
    const setFace = (t) => {
      if (!E) return;
      for (const ex of E.expressions) E.setValue(ex.expressionName, 0);
      if (face) for (const [name, w] of Object.entries(face(t) || {})) E.setValue(name, w);
    };
    const settle = () => { vrm.humanoid.update(); vrm.scene.updateMatrixWorld(true); };
    const at = (t) => {
      const n = Math.max(0, Math.floor(t / dt + 1e-6));
      if (springs && vrm.springBoneManager) {
        if (!sim || sim.n > n) {                             // start (or restart) from the pose at t = 0, springs at rest
          R.pose(0); settle(); vrm.springBoneManager.reset(); sim = { n: 0 };
        }
        while (sim.n < n) {
          sim.n++;
          R.pose(sim.n * dt); settle(); vrm.springBoneManager.update(dt);
        }
      }
      R.pose(t); settle();                                   // spring bones aren't humanoid: they keep step n's state
      setFace(t); if (E) E.update();
      vrm.scene.updateMatrixWorld(true);
    };
    const setFaceNow = (w) => {                              // an expression set now, outside the track (boards)
      if (!E) return;
      for (const ex of E.expressions) E.setValue(ex.expressionName, 0);
      for (const [k, v] of Object.entries(w || {})) E.setValue(k, v);
      E.update(); vrm.scene.updateMatrixWorld(true);
    };
    // invalidate(): someone else posed the rig or reset the springs; the next at(t) replays from t = 0
    return { at, setFace: setFaceNow, invalidate: () => { sim = null; }, retarget: R, vrm, len: R.len };
  };

  // a deterministic blink track: blinks every 2.1-3.2 s from a seed (hash, not Math.random), 1 frame half, 2 closed, 1 half
  V3.blinks = (len, seed = 7, first = 0.9, fps = 24) => {
    const out = []; let t = first, k = 0;
    const h = n => { const x = Math.sin(n * 127.1 + seed * 311.7) * 43758.5453; return x - Math.floor(x); };
    while (t < len) { out.push(t); t += 2.1 + 1.1 * h(k++); }
    return t2 => {
      for (const b of out) {
        const d = (t2 - b) * fps;
        if (d >= 0 && d < 2) return { blink: 1 };
        if ((d >= -1 && d < 0) || (d >= 2 && d < 3)) return { eyesHalf: 1 };
      }
      return {};
    };
  };

  window.V3 = V3;
})();
