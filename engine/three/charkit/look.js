// engine/three/charkit/look.js: charkit's anime look in three.js WebGPU (TSL node materials), read from our own export
// (charkit/gltf.py: glTF 2.0 / VRM 1.0 with the OPENADS_charkit_look extension). Plain script: defines the global CK.
// Needs engine/vendor/three-vrm.js (window.THREE) and, for motion, engine/three/vrm.js (V3).
//
//   const ctx = await V3.renderer({ w, h, backend: 'webgpu' })
//   const ck = await CK.load(ctx, url)          // the VRM (three-vrm: humanoid, expressions, lookAt) with our materials,
//                                               // outline hulls, feature layers and skin holdouts built from the extension
//   scene.add(ck.scene); ck.buildPose()         // the build's A-pose (ck.restPose(): the file's T-pose rest)
//   ck.keys({ eye_blink: 1 }); ck.expressions({ happy: 1 }); ck.update()   // shape keys / VRM expressions, head light
//   const P = CK.pipeline(ctx, { ss: 2 })       // main pass, eyes and brows through the fringe, composite (and bloom)
//   P.render(scene, camera, ck, [x, y, w, h])   // into that canvas region (y from the top)
//
// The look (charkit/shade.py, faceshade.py, hair.py; every number comes from the file):
//   toon3   three tones on half-lambert h = 0.5 + 0.5 N.L against CK.U.light (world), linear steps of +-softness at the
//           two thresholds (Blender's colour ramps), a lit-side rim from Blender's Layer Weight 'Facing' (1 - |N.V|^e),
//           screen-blended; an optional texture multiplied over the result (garments)
//   face    toon3 blended (by _FACE_MASK) with the SDF face: t = atan2(|l.x|, l.z) / pi of the head-space light, the
//           threshold map sampled in the 'face' UV (mirrored for light from her right), a +-softness step, the fringe's
//           shadow, the blush (multiply by its alpha); two tones (lit, shade); the drawn jaw line (ink, off the neck by
//           _INK_W) over the result
//   hair    toon3 plus (analytic hair, 'lock' UV) the angel ring (a band at an elevation above the hair centre, on each
//           lock's middle, facing the camera, on the lit side), the root-to-tip gradient and drawn strand lines
//   streaks toon3's `highlight` (the cut hair, charkit.shade.hair_toon): a band at an elevation above the head centre,
//           each lock (_LOCK) keeping a streak by a hash of its index and shifting it by another, facing the camera, lit
//   light   the root's light.direction (world), or with light.mode 'camera' a key [deg left of the camera, deg up] that
//           turns with the camera (ck.update(dt, camera)), as charkit.shade.set_view lights the boards
//   lines   the root's lines.mode 'screen': every outline frac x the picture's height at the head's distance (times its
//           region's factor), as charkit.shade.set_view widens them per view; else each mesh's build width
//   plate   the eye textures (cubic B-spline filtering and CLIP, like Blender's image nodes); flat: one colour
//   outline an inverted hull per outlined mesh: back faces pushed out along _HULL_NORMAL (or NORMAL) by width x
//           _OUTLINE_WIDTH (POSITION is already Blender's surface, drawn inward by the same amount)
//   through features (eyes, lashes, brows) rendered again with the skin as a depth-only holdout and everything else hidden,
//           laid over the frame at 0.55 x their alpha in sRGB, as charkit.qa.features_through does
// Debug views (CK.U.debug): see CK.DEBUG.

(() => {
  const T = window.THREE, S = T.TSL;
  const EXT = 'OPENADS_charkit_look';
  const CK = {};
  CK.EXT = EXT;
  CK.DEBUG = ['look', 'normals', 'n.l', 'sdf', 'uv0', 'uv1', 'weights', 'face mask', 'outline width', 'albedo', 'rim', 'depth'];
  CK.LAYER = { main: 0, feature: 1, holdout: 2 };

  // ------------------------------------------------------------------------------------------------ shared uniforms
  const U = CK.U = {
    light: S.uniform(new T.Vector3(-0.45, 0.70, 0.55).normalize()),   // toward the key light, world (glTF frame)
    headLight: S.uniform(new T.Vector3(-0.45, 0.70, 0.55).normalize()),// the same in the head bone's rest frame
    debug: S.uniform(0),
    bone: S.uniform(0),                                               // joint index for the weights view
    ortho: S.uniform(0),
    camBack: S.uniform(new T.Vector3(0, 0, 1)),                        // toward the camera (orthographic)
    outline: S.uniform(1),                                            // outline width scale (0 hides them)
    lineScreen: S.uniform(0),                                         // screen lines: frac x the visible height (m), 0 off
    rim: S.uniform(1), sdf: S.uniform(1), ring: S.uniform(1),         // system toggles (1 on)
    time: S.uniform(0),
  };

  // ------------------------------------------------------------------------------------------------ small TSL helpers
  const v3 = c => S.vec3(c[0], c[1], c[2]);
  const sat = x => S.clamp(x, 0.0, 1.0);
  const mapRange = (x, a, b, c = 0, d = 1) => S.mix(S.float(c), S.float(d), sat(S.float(x).sub(a).div(b - a)));
  const screen = (a, b, f) => S.vec3(1.0).sub(S.vec3(1.0).sub(f).add(f.mul(S.vec3(1.0).sub(b))).mul(S.vec3(1.0).sub(a)));
  const inside01 = uv => S.step(0.0, uv.x).mul(S.step(uv.x, 1.0)).mul(S.step(0.0, uv.y)).mul(S.step(uv.y, 1.0));
  // (no select()/If for choices: TSL emits them as if/else, and a node shared with the other branch is then declared
  // inside the first branch that builds it, so the other path reads an unset variable. Choices are arithmetic masks.)
  const is = (u, i) => S.float(1.0).sub(S.min(S.abs(u.sub(i)), 1.0));        // 1 where the (integer) uniform u == i

  // cubic B-spline filtering from four bilinear taps (GPU Gems 2, ch. 20), as Blender's 'Cubic' image interpolation
  const bicubic = (tex, uv, size) => {
    const st = uv.mul(size).sub(0.5), i = S.floor(st), f = st.sub(i);
    const f2 = f.mul(f), f3 = f2.mul(f);
    const w0 = S.vec2(1.0).sub(f).pow(3.0).div(6.0);
    const w1 = f3.mul(3.0).sub(f2.mul(6.0)).add(4.0).div(6.0);
    const w2 = f3.mul(-3.0).add(f2.mul(3.0)).add(f.mul(3.0)).add(1.0).div(6.0);
    const w3 = f3.div(6.0);
    const g0 = w0.add(w1), g1 = w2.add(w3);
    const h0 = i.sub(0.5).add(w1.div(g0)).div(size);      // (i - 1 + w1/g0 + 0.5) / size
    const h1 = i.add(1.5).add(w3.div(g1)).div(size);      // (i + 1 + w3/g1 + 0.5) / size
    const t = (x, y) => S.texture(tex, S.vec2(x, y));
    return t(h0.x, h0.y).mul(g0.x.mul(g0.y)).add(t(h1.x, h0.y).mul(g1.x.mul(g0.y)))
      .add(t(h0.x, h1.y).mul(g0.x.mul(g1.y))).add(t(h1.x, h1.y).mul(g1.x.mul(g1.y)));
  };
  const sample = (tex, info, uvNode, cubic) => {
    const size = S.vec2(tex.image.width, tex.image.height);
    let c = cubic ? bicubic(tex, uvNode, size) : S.texture(tex, uvNode);
    if (info && info.wrap === 'clip') c = c.mul(inside01(uvNode));
    return c;
  };
  const uvOf = info => S.uv((info && info.texCoord) || 0);

  // the shading normal, facing the viewer (Blender's Geometry Normal on a two-sided material), in world and view space
  // (world space only: in r186 a material that reads normalView as well as normalWorld gets a zero normalWorld)
  const nWorld = () => S.normalWorld.normalize();
  const viewDir = () => S.mix(S.cameraPosition.sub(S.positionWorld).normalize(), U.camBack, U.ortho);
  // Blender's Layer Weight 'Facing' output: 1 - |N.V|^e, e = 2 blend (blend < 0.5) or 0.5 / (1 - blend)
  const facing = blend => {
    const e = blend === 0.5 ? 1.0 : blend < 0.5 ? 2 * blend : 0.5 / (1 - Math.min(blend, 0.99999));
    return S.float(1.0).sub(S.abs(S.dot(nWorld(), viewDir())).pow(e));
  };

  // ------------------------------------------------------------------------------------------------ materials
  function toon3Nodes(L) {
    const h = S.dot(nWorld(), U.light).mul(0.5).add(0.5);
    const s = L.softness;
    const sLit = sat(h.sub(L.threshold - s).div(2 * s));
    const sDeep = sat(h.sub(L.deepThreshold - s).div(2 * s));
    const base = S.mix(S.mix(v3(L.deep), v3(L.shade), sDeep), v3(L.lit), sLit);
    let col = base, rimF = S.float(0);
    if (L.rim && L.rim.amount > 0) {
      rimF = mapRange(facing(L.rim.facing), L.rim.range[0], L.rim.range[1]).mul(L.rim.amount).mul(sLit).mul(U.rim);
      col = screen(base, v3(L.rim.color), rimF);
    }
    if (L.highlight && L.highlight.kind === 'streaks') col = streakNodes(L.highlight, col, sLit);
    return { h, sLit, sDeep, col, rimF };
  }

  // charkit.shade.hair_toon's streaks: fract(sin(i k) 43758.5453) hashes of the lock index pick and shift each streak
  function streakNodes(Hl, col, sLit) {
    const rad = Math.PI / 180;
    const lock = S.attribute('_lock', 'float');
    const hash = k => S.fract(S.sin(lock.mul(k)).mul(43758.5453));
    const keep = S.float(1.0).sub(S.step(Hl.keep, hash(12.9898)));            // hash < keep
    const el0 = S.mix(S.float((Hl.elevation - Hl.jitter) * rad), S.float((Hl.elevation + Hl.jitter) * rad), hash(78.233));
    const p = S.positionGeometry.sub(v3(Hl.centre));
    const el = S.atan(p.y, S.length(p.xz));
    const half = Hl.width / 2 * rad;
    const band = mapRange(S.abs(el.sub(el0)), half, half * 0.6);
    const face = mapRange(facing(Hl.facingBlend), Hl.facing[0], Hl.facing[1]);
    return S.mix(col, v3(Hl.color), band.mul(keep).mul(face).mul(sLit).mul(Hl.amount).mul(U.ring));
  }

  function faceNodes(L, tex, toon) {
    const F = L.face;
    const uv1 = uvOf(F.sdf);
    const lx = U.headLight.x, lz = U.headLight.z;
    const t = S.atan(S.abs(lx), lz).div(Math.PI);                 // 0 light from the front .. 1 from behind
    const right = S.float(1.0).sub(S.step(0.0, lx));             // light from her right: mirror the map
    const u = S.mix(uv1.x, S.float(1.0).sub(uv1.x), right);
    const suv = S.vec2(u, uv1.y);
    const st = tex[F.sdf.index];
    const raw = F.sdf.filter === 'cubic' ? bicubic(st, suv, S.vec2(st.image.width, st.image.height)) : S.texture(st, suv);
    const sdf = F.sdf.encoding === 'rg16' ? raw.x.mul(65280 / 65535).add(raw.y.mul(255 / 65535)) : raw.x;
    const edge = sat(t.sub(sdf).add(F.softness).div(2 * F.softness));
    let sh = edge;
    if (F.fringe) {
      const fr = sample(tex[F.fringe.index], F.fringe, uvOf(F.fringe), F.fringe.filter === 'cubic').x;
      sh = S.max(sh, mapRange(fr, F.fringeRange[0], F.fringeRange[1]));
    }
    sh = sat(sh).mul(U.sdf);
    let col = S.mix(v3(F.lit), v3(F.shade), sh);
    if (F.blush) {
      const b = sample(tex[F.blush.index], F.blush, uvOf(F.blush), F.blush.filter === 'cubic');
      col = S.mix(col, col.mul(b.xyz), b.w);
    }
    const mask = S.attribute('_face_mask', 'float');
    let out = S.mix(toon.col, col, mask);
    if (F.ink) {                                                  // faceshade.ink: drawn lines, off the neck (_INK_W)
      const k = sample(tex[F.ink.index], F.ink, uvOf(F.ink), F.ink.filter === 'cubic');
      out = S.mix(out, k.xyz, k.w.mul(S.attribute('_ink_w', 'float')));
    }
    return { col: out, sdf, t, mask, sh };
  }

  function hairNodes(L, toon, col, hasLock) {
    // a mesh without the 'lock' UV (a bun sharing the hair material) reads (0, 0) there, as Blender's UV Map node does
    const Hh = L.hair, R = Hh.ring, uvl = hasLock ? S.uv(Hh.lock || 1) : S.vec2(0.0, 1.0);
    const across = S.abs(uvl.x), along = S.float(1.0).sub(uvl.y);   // glTF v = 1 - Blender v
    const p = S.positionGeometry.sub(v3(R.centre));
    const el = S.atan(p.y, S.length(p.xz));
    const rad = Math.PI / 180;
    const mid = mapRange(across, R.mid[0], R.mid[1]);
    const lens = S.float(R.width * rad).sub(across.mul(across).mul(R.width * rad)).sub(S.abs(el.sub(R.elevation * rad)));
    const band = sat(lens.div(R.soft * rad));
    const face = mapRange(facing(R.facingBlend), R.facing[0], R.facing[1]);
    const ring = mid.mul(band).mul(face).mul(toon.sLit).mul(R.amount).mul(U.ring);
    let c = S.mix(col, v3(R.color), ring);
    const G = Hh.gradient;
    c = c.mul(mapRange(along, G.range[0], G.range[1], G.root, 1.0));
    const St = Hh.strands;
    const ln = mapRange(S.abs(across.sub(St.offset)), St.width[0], St.width[1], 1.0, 0.0);
    const lf = mapRange(along, St.fade[0], St.fade[1], St.amount, 0.0);
    return S.mix(c, c.mul(v3(St.color)), ln.mul(lf));
  }

  // the weight of the chosen joint, computed per vertex
  const boneWeight = () => {
    const idx = S.vec4(S.attribute('skinIndex', 'uvec4')), w = S.attribute('skinWeight', 'vec4');
    const m = k => w[k].mul(is(idx[k], U.bone));
    return S.varying(m('x').add(m('y')).add(m('z')).add(m('w')));
  };
  const heat = x => S.mix(S.mix(S.vec3(0.05, 0.05, 0.35), S.vec3(0.1, 0.8, 0.3), sat(x.mul(2))), S.vec3(1.0, 0.2, 0.1), sat(x.mul(2).sub(1)));

  // a surface material from one material's look (L) and its mesh (M); attrs: which custom attributes the geometry has
  CK.material = (L, M, tex, attrs) => {
    const m = new T.MeshBasicNodeMaterial();
    m.side = L.doubleSided ? T.DoubleSide : T.FrontSide;
    m.name = 'ck:' + (L.role || L.kind);
    let color, toon = null, face = null, alpha = null;
    if (L.kind === 'flat') color = v3(L.color);
    else if (L.kind === 'plate') {
      const c = sample(tex[L.texture.index], L.texture, uvOf(L.texture), L.texture.filter === 'cubic');
      color = c.xyz;
      if (L.alpha === 'blend') alpha = c.w;
    } else {
      toon = toon3Nodes(L);
      color = toon.col;
      if (L.kind === 'face' && L.face) { face = faceNodes(L, tex, toon); color = face.col; }
      if (L.kind === 'hair' && L.hair) color = hairNodes(L, toon, color, attrs.uv1);
      if (L.texture) color = color.mul(sample(tex[L.texture.index], L.texture, uvOf(L.texture), L.texture.filter === 'cubic').xyz);
    }
    // debug views
    const dbg = [
      color,
      nWorld().mul(0.5).add(0.5),
      toon ? S.vec3(toon.h).mul(0.8).add(S.vec3(0.2, 0, 0).mul(S.step(0.5 - 0.004, toon.h).mul(S.step(toon.h, 0.5 + 0.004)))) : S.vec3(0.5),
      face ? S.mix(S.vec3(face.sdf), S.vec3(1.0, 0.25, 0.2), S.float(1).sub(face.sh).mul(face.mask).mul(0.35)) : S.vec3(0.3),
      attrs.uv0 ? S.vec3(S.fract(S.uv(0).mul(8)), 0.25) : S.vec3(0.15),
      attrs.uv1 ? S.vec3(S.fract(S.uv(1).mul(8)), 0.25) : S.vec3(0.15),
      heat(boneWeight()),
      attrs.faceMask ? S.vec3(S.attribute('_face_mask', 'float')) : S.vec3(0),
      attrs.outlineW ? heat(S.attribute('_outline_width', 'float')) : S.vec3(M && M.outline ? 1 : 0.1),
      L.kind === 'flat' ? v3(L.color) : L.lit ? v3(L.lit) : color,
      toon ? S.vec3(toon.rimF.mul(4)) : S.vec3(0),
      S.vec3(S.fract(S.cameraPosition.sub(S.positionWorld).length().mul(4))),
    ];
    let out = dbg[0].mul(is(U.debug, 0));
    for (let i = 1; i < dbg.length; i++) out = out.add(dbg[i].mul(is(U.debug, i)));
    m.colorNode = out;
    if (alpha) { m.transparent = true; m.depthWrite = false; m.opacityNode = S.mix(alpha, S.float(1), S.min(U.debug, 1.0)); }
    m.userData.look = L;
    return m;
  };

  CK.hullMaterial = (M, attrs) => {
    const m = new T.MeshBasicNodeMaterial();
    m.side = T.BackSide;
    m.name = 'ck:outline';
    m.colorNode = v3(M.outline.color);
    const w = attrs.outlineW ? S.attribute('_outline_width', 'float') : S.float(1);
    // screen lines (the root's lines.mode 'screen'): U.lineScreen x the region's factor, else the build width
    const width = S.mix(S.float(M.outline.width), U.lineScreen.mul(M.outline.regionFactor || 1), S.step(1e-9, U.lineScreen));
    m.positionNode = S.positionLocal.add(S.normalLocal.mul(w.mul(width).mul(U.outline)));
    return m;
  };

  // the skin as a depth-only holdout for the feature pass; at the original surface (charkit.qa.features_through turns
  // the outline SOLIDIFY off on its holdouts), i.e. where the hull is
  CK.holdoutMaterial = (M, attrs) => {
    const m = new T.MeshBasicNodeMaterial({ colorWrite: false });
    m.side = T.DoubleSide; m.name = 'ck:holdout';
    if (M && M.outline) {
      const w = attrs.outlineW ? S.attribute('_outline_width', 'float') : S.float(1);
      m.positionNode = S.positionLocal.add(S.normalLocal.mul(w.mul(M.outline.width)));
    }
    return m;
  };

  // ------------------------------------------------------------------------------------------------ loading
  // a stand-in for three-vrm's MToon plugin: the MToon fallbacks are for other viewers; we build our own materials
  const noMToon = parser => ({ name: 'VRMC_materials_mtoon', beforeRoot: async () => {}, afterRoot: async () => {},
    getMaterialType: () => null, extendMaterialParams: async () => {}, loadMesh: i => parser.loadMesh(i) });

  class LookPlugin {
    constructor(parser) { this.parser = parser; this.name = EXT; }
    async afterRoot(gltf) {
      const js = this.parser.json, want = new Set();
      const walk = o => { if (o && typeof o === 'object') { if ('index' in o && 'texCoord' in o) want.add(o.index); Object.values(o).forEach(walk); } };
      (js.materials || []).forEach(m => walk(m.extensions && m.extensions[EXT]));
      const tex = {};
      for (const i of want) tex[i] = await this.parser.getDependency('texture', i);
      gltf.userData.charkit = { root: (js.extensions || {})[EXT] || {}, tex,
        materials: (js.materials || []).map(m => (m.extensions || {})[EXT] || null),
        meshes: (js.meshes || []).map(m => (m.extensions || {})[EXT] || {}) };
    }
  }

  CK.load = async (ctx, url, { onProgress } = {}) => {
    const loader = new T.GLTFLoader();
    loader.register(parser => new T.VRM.VRMLoaderPlugin(parser, { mtoonMaterialPlugin: noMToon(parser) }));
    loader.register(parser => new LookPlugin(parser));
    const gltf = await loader.loadAsync(url, onProgress);
    const vrm = gltf.userData.vrm, info = gltf.userData.charkit;
    if (!vrm || !info) throw new Error(url + ': not a charkit VRM (no VRMC_vrm or ' + EXT + ')');
    const js = gltf.parser.json, assoc = gltf.parser.associations;
    // texture colour spaces: colour maps sRGB, data maps linear
    const data = new Set();
    for (const L of info.materials) if (L && L.face) for (const k of ['sdf', 'fringe']) if (L.face[k]) data.add(L.face[k].index);
    for (const [i, t] of Object.entries(info.tex)) {
      t.colorSpace = data.has(+i) ? T.NoColorSpace : T.SRGBColorSpace;
      t.generateMipmaps = true; t.minFilter = T.LinearMipmapLinearFilter; t.magFilter = T.LinearFilter;
      t.anisotropy = 8; t.needsUpdate = true;
    }
    const ck = { vrm, gltf, url, root: info.root, scene: vrm.scene, parts: {}, meshes: [], hulls: [], holdouts: [], features: [],
      materials: [], keyIndex: {}, bindPose: info.root.bindPose || {} };
    const meshes = [];
    vrm.scene.traverse(o => { if (o.isMesh) meshes.push(o); });
    for (const mesh of meshes) {
      const a = assoc.get(mesh);
      if (!a || a.meshes === undefined) continue;
      const gm = a.meshes, pi = a.primitives || 0;
      const prim = js.meshes[gm].primitives[pi];
      const L = info.materials[prim.material] || { kind: 'flat', color: [0.8, 0.8, 0.8], doubleSided: true };
      const M = info.meshes[gm] || {};
      const name = M.object || js.meshes[gm].name;
      const g = mesh.geometry;
      const attrs = { uv0: !!g.attributes.uv, uv1: !!g.attributes.uv1, faceMask: !!g.attributes._face_mask,
        outlineW: !!g.attributes._outline_width, hullN: !!g.attributes._hull_normal };
      mesh.material = CK.material(L, M, info.tex, attrs);
      mesh.frustumCulled = false;
      mesh.userData.ck = { name, look: L, mesh: M, prim: pi, attrs };
      ck.materials.push(mesh.material);
      (ck.parts[name] = ck.parts[name] || { name, meshes: [], hulls: [], holdouts: [], look: M, visible: true }).meshes.push(mesh);
      ck.meshes.push(mesh);
      if (M.feature) { mesh.layers.enable(CK.LAYER.feature); ck.features.push(mesh); }
      const clone = (geom, mat, layer) => {
        const c = mesh.isSkinnedMesh ? new T.SkinnedMesh(geom, mat) : new T.Mesh(geom, mat);
        if (mesh.isSkinnedMesh) { c.bind(mesh.skeleton, mesh.bindMatrix); c.bindMode = mesh.bindMode; }
        c.position.copy(mesh.position); c.quaternion.copy(mesh.quaternion); c.scale.copy(mesh.scale);
        if (mesh.morphTargetInfluences) { c.morphTargetInfluences = mesh.morphTargetInfluences; c.morphTargetDictionary = mesh.morphTargetDictionary; }
        c.frustumCulled = false; c.layers.set(layer);
        mesh.parent.add(c);
        return c;
      };
      let hg = g;
      if (M.outline && attrs.hullN) {                        // the hull extrudes along its own normals
        hg = new T.BufferGeometry();
        for (const [k, v] of Object.entries(g.attributes)) hg.setAttribute(k, v);
        hg.setAttribute('normal', g.attributes._hull_normal);
        hg.setIndex(g.index); hg.morphAttributes = g.morphAttributes; hg.morphTargetsRelative = g.morphTargetsRelative;
      }
      if (M.outline) {
        const R = info.root.lines;
        if (R && R.regions) M.outline.regionFactor = R.regions[M.outline.region] || 1;
        const h = clone(hg, CK.hullMaterial(M, attrs), CK.LAYER.main);
        h.userData.ck = { name, hull: true }; h.renderOrder = -1;
        ck.hulls.push(h); ck.parts[name].hulls.push(h);
      }
      if (M.holdout) {
        const h = clone(hg, CK.holdoutMaterial(M, attrs), CK.LAYER.holdout);
        h.userData.ck = { name, holdout: true }; h.renderOrder = -10;   // depth first: it must hide what's behind it
        ck.holdouts.push(h); ck.parts[name].holdouts.push(h);
      }
      if (mesh.morphTargetDictionary) for (const [k, i] of Object.entries(mesh.morphTargetDictionary)) (ck.keyIndex[k] = ck.keyIndex[k] || []).push([mesh, i]);
    }
    // the head's rest frame (the head-space light) and the joints (the weights view)
    const H = vrm.humanoid;
    H.resetNormalizedPose(); vrm.scene.updateMatrixWorld(true);
    ck.headNode = H.getRawBoneNode((info.root.head && info.root.head.bone) || 'head');
    ck.headRest = ck.headNode.getWorldQuaternion(new T.Quaternion());
    const skinned = meshes.find(m => m.isSkinnedMesh);
    ck.joints = skinned ? skinned.skeleton.bones.map(b => b.name) : [];
    ck.keyNames = Object.keys(ck.keyIndex).sort();
    ck.expressionNames = vrm.expressionManager ? vrm.expressionManager.expressions.map(e => e.expressionName) : [];
    ck.light = new T.Vector3(...((info.root.light && info.root.light.direction) || [-0.45, 0.70, 0.55])).normalize();
    ck.rawKeys = {}; ck.exprs = {}; ck.gaze = null;

    // ---- controls
    ck.restPose = () => { H.resetNormalizedPose(); H.update(); vrm.scene.updateMatrixWorld(true); };
    ck.buildPose = () => {                                   // the pose the build (and Blender) shows: the A-pose bind
      H.resetNormalizedPose();
      for (const [b, q] of Object.entries(ck.bindPose)) { const n = H.getNormalizedBoneNode(b); if (n) n.quaternion.fromArray(q); }
      H.update(); vrm.scene.updateMatrixWorld(true);
    };
    ck.keys = (w = {}) => { ck.rawKeys = { ...w }; };
    ck.expressions = (w = {}) => { ck.exprs = { ...w }; };
    ck.look = (yaw = 0, pitch = 0) => { ck.gaze = [yaw, pitch]; };
    ck.setVisible = (name, on) => { const p = ck.parts[name]; if (!p) return; p.visible = on; for (const m of [...p.meshes, ...p.hulls, ...p.holdouts]) m.visible = on; };
    // apply the face (expressions, then raw keys on top), and the head-space light
    ck.update = (dt = 0, camera = null) => {
      if (camera) ck.camera = camera;
      const E = vrm.expressionManager;
      for (const m of ck.meshes) if (m.morphTargetInfluences) m.morphTargetInfluences.fill(0);
      if (E) {
        for (const e of E.expressions) E.setValue(e.expressionName, 0);
        for (const [k, v] of Object.entries(ck.exprs)) E.setValue(k, v);
        if (ck.gaze && (ck.gaze[0] || ck.gaze[1]) && vrm.lookAt) { vrm.lookAt.autoUpdate = false; vrm.lookAt.applier.applyYawPitch(ck.gaze[0], ck.gaze[1]); }
        E.update();
      }
      for (const [k, v] of Object.entries(ck.rawKeys)) for (const [m, i] of ck.keyIndex[k] || []) m.morphTargetInfluences[i] += v;
      vrm.scene.updateMatrixWorld(true);
      ck.updateLight();
    };
    ck.camera = null;
    const LT = info.root.light || {}, LN = info.root.lines || {};
    const cameraLight = cam => {                             // charkit.shade.view_light's camera key, in the glTF frame
      const t = ck.head().centre, up = new T.Vector3(0, 1, 0);
      const b = cam.getWorldPosition(new T.Vector3()).sub(t); b.y = 0;
      if (b.lengthSq() < 1e-12) b.set(0, 0, 1);
      b.normalize();
      const r = new T.Vector3().crossVectors(up, b);
      const a0 = LT.key[0] * Math.PI / 180, el = LT.key[1] * Math.PI / 180;
      return b.multiplyScalar(Math.cos(a0) * Math.cos(el)).addScaledVector(r, -Math.sin(a0) * Math.cos(el)).addScaledVector(up, Math.sin(el));
    };
    const visibleHeight = cam => {                            // at the head's distance (charkit.qa.render_view's target)
      if (cam.isOrthographicCamera) return (cam.top - cam.bottom) / cam.zoom;
      const d = cam.getWorldPosition(new T.Vector3()).distanceTo(ck.head().centre);
      return 2 * d * Math.tan(cam.fov * Math.PI / 360) / (cam.zoom || 1);
    };
    ck.updateLight = () => {
      if (LT.mode === 'camera' && LT.key && ck.camera) ck.light.copy(cameraLight(ck.camera)).normalize();
      U.lineScreen.value = LN.mode === 'screen' && ck.camera ? LN.frac * visibleHeight(ck.camera) : 0;
      U.light.value.copy(ck.light);
      const q = ck.headNode.getWorldQuaternion(new T.Quaternion()).multiply(ck.headRest.clone().invert());
      U.headLight.value.copy(ck.light).applyQuaternion(q.invert());
    };
    ck.setLight = v => { ck.light.copy(v).normalize(); ck.updateLight(); };
    ck.head = () => {                                        // the head centre and head length (camera framing)
      const h = info.root.head || { centre: [0, 1.4, 0], L: 0.25 };
      return { centre: new T.Vector3(...h.centre), L: h.L };
    };
    ck.updateLight();
    return ck;
  };

  // ------------------------------------------------------------------------------------------------ the frame pipeline
  // main pass -> RT (MSAA, ss x supersampled); feature pass (layers feature + holdout) -> RT; composite (features over the
  // frame at `through` x alpha in sRGB, as charkit.qa.features_through; then the ss x ss box down to the output) -> canvas
  CK.pipeline = (ctx, { ss = 1, bg = [0.86, 0.86, 0.90], samples = 4, through = null, bloom = 0 } = {}) => {
    const r = ctx.renderer;
    const P = { ss, bg: new T.Color(...bg), through, bloom, bloomThreshold: 0.92, size: [0, 0] };
    const mk = () => new T.RenderTarget(1, 1, { samples, type: T.HalfFloatType, depthBuffer: true });
    const rtMain = mk(), rtFeat = mk();
    const rtB = [0, 1].map(() => new T.RenderTarget(1, 1, { type: T.HalfFloatType, depthBuffer: false }));
    const uThrough = S.uniform(0.55), uSS = S.uniform(1), uTexel = S.uniform(new T.Vector2(1, 1));
    const uBloom = S.uniform(0), uBloomT = S.uniform(0.92), uBTexel = S.uniform(new T.Vector2(1, 1));
    const quv = S.uv();                                      // QuadMesh uv: (0,0) bottom-left
    const tMain = S.texture(rtMain.texture), tFeat = S.texture(rtFeat.texture);
    // bloom: bright parts of the frame (above a threshold), blurred separably at 1/4 size
    const bright = new T.MeshBasicNodeMaterial();
    bright.colorNode = S.max(S.texture(rtMain.texture, quv).xyz.sub(uBloomT), S.vec3(0)).div(S.float(1).sub(uBloomT).max(0.01));
    const makeBlur = (src, dir) => {
      const m = new T.MeshBasicNodeMaterial(), tx = S.texture(src.texture), w = [0.227027, 0.1945946, 0.1216216, 0.054054, 0.016216];
      let c = tx.sample(quv).xyz.mul(w[0]);
      for (let i = 1; i < 5; i++) {
        const o = S.vec2(dir[0], dir[1]).mul(uBTexel).mul(i * 1.5);
        c = c.add(tx.sample(quv.add(o)).xyz.mul(w[i])).add(tx.sample(quv.sub(o)).xyz.mul(w[i]));
      }
      m.colorNode = c;
      return new T.QuadMesh(m);
    };
    const qBlurH = makeBlur(rtB[0], [1, 0]), qBlurV = makeBlur(rtB[1], [0, 1]);
    const qBright = new T.QuadMesh(bright);
    const comp = new T.MeshBasicNodeMaterial();
    comp.colorNode = S.Fn(() => {
      const A = S.vec3(0).toVar(), B = S.vec4(0).toVar();
      // ss x ss box: taps at the hi-res texel centres inside this output pixel
      for (let j = 0; j < 3; j++) for (let i = 0; i < 3; i++) {
        const use = S.float(i).lessThan(uSS).and(S.float(j).lessThan(uSS));
        const off = S.vec2(i + 0.5, j + 0.5).sub(uSS.mul(0.5)).mul(uTexel);
        S.If(use, () => { A.addAssign(tMain.sample(quv.add(off)).xyz); B.addAssign(tFeat.sample(quv.add(off))); });
      }
      const n = uSS.mul(uSS);
      A.divAssign(n); B.divAssign(n);
      const As = S.sRGBTransferOETF(S.max(A, S.vec3(0)));
      const Bs = S.sRGBTransferOETF(S.max(B.xyz.div(B.w.max(1e-4)), S.vec3(0)));
      const k = sat(B.w).mul(uThrough);
      let out = S.sRGBTransferEOTF(S.mix(As, Bs, k));
      out = out.add(S.texture(rtB[0].texture, quv).xyz.mul(uBloom));
      return out;
    })();
    const qComp = new T.QuadMesh(comp);
    const featCam = { persp: new T.PerspectiveCamera(), ortho: new T.OrthographicCamera() };

    P.render = (scene, cam, ck, [x, y, w, h] = [0, 0, ctx.w, ctx.h]) => {
      const W_ = Math.round(w * P.ss), H_ = Math.round(h * P.ss);
      if (P.size[0] !== W_ || P.size[1] !== H_) {
        rtMain.setSize(W_, H_); rtFeat.setSize(W_, H_);
        for (const b of rtB) b.setSize(Math.max(1, W_ >> 2), Math.max(1, H_ >> 2));
        P.size = [W_, H_];
      }
      U.ortho.value = cam.isOrthographicCamera ? 1 : 0;
      cam.getWorldDirection(U.camBack.value).negate();
      if (ck && ck.updateLight) { ck.camera = cam; ck.updateLight(); }   // the view's light and line widths (the look)
      if (ck) ck.updateLight();
      const bg0 = scene.background; scene.background = null;
      r.setScissorTest(false);
      r.setRenderTarget(rtMain); r.setClearColor(P.bg, 1); r.clear(); r.render(scene, cam);
      const th = P.through != null ? P.through : ck && ck.root.features ? ck.root.features.through : 0.55;
      r.setRenderTarget(rtFeat); r.setClearColor(0x000000, 0); r.clear();
      if (th > 0 && ck && ck.features.length && U.debug.value === 0) {
        const fc = cam.isOrthographicCamera ? featCam.ortho : featCam.persp;
        fc.copy(cam); fc.layers.set(CK.LAYER.feature); fc.layers.enable(CK.LAYER.holdout);
        r.render(scene, fc);
      }
      uBloom.value = P.bloom;
      if (P.bloom > 0) {
        uBloomT.value = P.bloomThreshold;
        r.setRenderTarget(rtB[0]); qBright.render(r);
        const tw = 1 / rtB[0].width, th_ = 1 / rtB[0].height;
        uBTexel.value.set(tw, th_);
        for (let pass = 0; pass < 3; pass++) {            // H: 0 -> 1, V: 1 -> 0 (the result ends in rtB[0])
          r.setRenderTarget(rtB[1]); qBlurH.render(r);
          r.setRenderTarget(rtB[0]); qBlurV.render(r);
        }
      } else {
        r.setRenderTarget(rtB[0]); r.setClearColor(0x000000, 1); r.clear();
      }
      scene.background = bg0;
      uThrough.value = th; uSS.value = P.ss; uTexel.value.set(1 / W_, 1 / H_);
      r.setRenderTarget(null);
      const yy = r.isWebGPURenderer ? y : ctx.h - y - h;
      r.setViewport(x, yy, w, h); r.setScissor(x, yy, w, h); r.setScissorTest(true);
      qComp.render(r);
      r.setScissorTest(false);
      r.setViewport(0, 0, ctx.w, ctx.h);
    };
    P.dispose = () => { rtMain.dispose(); rtFeat.dispose(); rtB.forEach(b => b.dispose()); };
    return P;
  };

  // cameras in Blender's board terms (charkit.qa.render_view): az degrees round her (+ toward her left), dist and height
  // from the target, lens mm on a 36 mm sensor fitted to the longer side, or orthographic with ortho scale on the longer side
  CK.camera = ({ target, az = 0, dist = 1, height = 0, lens = 50, aspect = 1, ortho = null, near = 0.01, far = 100 }) => {
    const a = az * Math.PI / 180;
    const pos = new T.Vector3(target[0] + Math.sin(a) * dist, target[1] + height, target[2] + Math.cos(a) * dist);
    let cam;
    if (ortho) {
      const hh = aspect >= 1 ? ortho / aspect / 2 : ortho / 2, hw = hh * aspect;
      cam = new T.OrthographicCamera(-hw, hw, hh, -hh, near, far);
    } else {
      const half = Math.atan(18 / lens);
      const vfov = aspect >= 1 ? 2 * Math.atan(Math.tan(half) / aspect) : 2 * half;
      cam = new T.PerspectiveCamera(vfov * 180 / Math.PI, aspect, near, far);
    }
    cam.position.copy(pos); cam.lookAt(new T.Vector3(...target)); cam.updateMatrixWorld(true);
    return cam;
  };

  window.CK = CK;
})();
