// engine/rig.js: a Live2D-style runtime for layered illustrations (rig art from tools/layers.py + tools/rigbuild.py).
//
//   const r = await RIG.load('rig/clawd/rig.json');           // textures + meshes
//   r.draw(X, t, P => ({ angleX: .3, armL: 12, ... }), { x, y, s })
//       P(t) returns the parameters at any time t; physics is stepped from a pre-roll, so a frame is a pure function of t.
//       The rig is drawn into X (a Canvas2D) with its base-image pixel (bx, by) mapped to (x + (bx - ox) * s, y + (by - oy) * s),
//       where (ox, oy) = rig.json "origin".
//
// rig.json (base-image pixel coordinates):
//   manifest: layers (back to front) with crops;  origin: [x, y] (feet, usually)
//   head: { layers, center: [x, y], radius: [rx, ry], neck: [x, y], depth: { layer: d | [d_centre, d_edge] } }
//   body: { waist: [x, y], hip: [x, y], upper: [layers], lower: [layers] }
//   arms: { L: { layers, shoulder: [x, y], sleeve: 'layer', sleeveFollow: .4 }, R: {...} }
//   sway: { layer: { root: y, len: px, spring: 'name', amp: px, axis: 'x' | 'y' | 'rot', pivot: [x, y] } }
//   springs: { name: { drive: 'headX' | 'headZ' | 'bodyZ' | 'bounce' | 'armL' ..., k, c, gain } }
//   mouth: { layer, center: [x, y], w, h }     procedural mouth drawn over the mouth patch when open
// Parameters (all default 0): angleX, angleY (-1..1 = +-30/+-18 deg), angleZ (deg), bodyZ (deg), bodyX (-1..1), bounce (px),
//   breath (0..1, auto if undefined), armL, armR (deg, + = outward), mouthOpen (0..1), mouthWide (-1..1), smile (0..1).

const RIG = (() => {
  const VS = `#version 300 es
    in vec2 p; in vec2 uv; uniform vec2 res; out vec2 v;
    void main() { v = uv; gl_Position = vec4(p.x / res.x * 2. - 1., 1. - p.y / res.y * 2., 0, 1); }`;
  const FS = `#version 300 es
    precision highp float; in vec2 v; uniform sampler2D tex; uniform sampler2D inv; uniform float alpha; uniform vec4 idc; out vec4 o;
    // the ID pass (idc.a > 0): each layer as its flat ID colour; its INVENTED pixels (fills) at half brightness
    void main() { vec4 c = texture(tex, v) * alpha; o = idc.a > 0. ? (c.a > .5 ? vec4(idc.rgb * (texture(inv, v).r > .5 ? .5 : 1.), 1) : vec4(0)) : c; }`;
  let gl = null, cv = null, prog = null, buf = null;

  function glInit(w, h) {
    if (!cv) {
      cv = document.createElement('canvas');
      gl = cv.getContext('webgl2', { premultipliedAlpha: true, antialias: true, preserveDrawingBuffer: true });
      const sh = (type, src) => { const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s); if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw gl.getShaderInfoLog(s); return s; };
      prog = gl.createProgram(); gl.attachShader(prog, sh(gl.VERTEX_SHADER, VS)); gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, FS)); gl.linkProgram(prog);
      buf = { p: gl.createBuffer(), uv: gl.createBuffer(), idx: gl.createBuffer() };
    }
    if (cv.width !== w || cv.height !== h) { cv.width = w; cv.height = h; }
    gl.viewport(0, 0, w, h); gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT);
    gl.useProgram(prog); gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
    gl.uniform2f(gl.getUniformLocation(prog, 'res'), w, h);
  }

  function texFrom(img) {
    const t = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, t);
    gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, true);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, img);
    gl.generateMipmap(gl.TEXTURE_2D);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    return t;
  }
  const loadImg = src => new Promise((ok, no) => { const i = new Image(); i.onload = () => ok(i); i.onerror = () => no(new Error('rig: ' + src)); i.src = src; });

  // a grid mesh over a layer's crop
  function mesh(l, cell = 48) {
    const cols = Math.max(2, Math.min(64, Math.round(l.w / cell))), rows = Math.max(2, Math.min(64, Math.round(l.h / cell)));
    const rest = [], uv = [], idx = [];
    for (let j = 0; j <= rows; j++) for (let i = 0; i <= cols; i++) { rest.push(l.x + l.w * i / cols, l.y + l.h * j / rows); uv.push(i / cols, j / rows); }
    for (let j = 0; j < rows; j++) for (let i = 0; i < cols; i++) { const a = j * (cols + 1) + i, b = a + 1, c = a + cols + 1, d = c + 1; idx.push(a, b, c, b, d, c); }
    return { rest: new Float32Array(rest), uv: new Float32Array(uv), idx: new Uint16Array(idx), n: idx.length };
  }

  const interp = (tbl, v) => { if (v <= tbl[0][0]) return tbl[0][1]; for (let i = 1; i < tbl.length; i++) if (v <= tbl[i][0]) { const [a0, b0] = tbl[i - 1], [a1, b1] = tbl[i]; return b0 + (b1 - b0) * (v - a0) / (a1 - a0); } return tbl[tbl.length - 1][1]; };
  const rot = (x, y, cx, cy, deg) => { const a = deg * Math.PI / 180, c = Math.cos(a), s = Math.sin(a), dx = x - cx, dy = y - cy; return [cx + dx * c - dy * s, cy + dx * s + dy * c]; };
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

  // damped springs, stepped at 1/120 s from a pre-roll: out = spring position minus its driver (the lag), times gain
  function springs(R, P, t) {
    const S = R.springs || {}, names = Object.keys(S); if (!names.length) return {};
    // a drawn view is a real head angle, but its drawing already carries the hair to the new place: springs feel only part
    // of a view change (R.viewDrive), as a modest overshoot, not a whip
    const vang = p => ((R.views && p.view && R.views[p.view] && R.views[p.view].angle) || 0) * (R.viewDrive ?? .3);
    const drive = (p, name) => { const d = S[name].drive; return d === 'headX' ? vang(p) + (p.angleX || 0) * 30 : d === 'headZ' ? (p.angleZ || 0) : d === 'headY' ? (p.angleY || 0) * 18
      : d === 'pelvis' ? (p._bz ?? p.bodyZ ?? 0) + (p.hipX || 0) * 8 : d === 'hipY' ? (p.hipY || 0) + (p.bounce || 0)
      : d === 'bodyZ' ? (p._bz ?? p.bodyZ ?? 0) : d === 'bounce' ? (p.bounce || 0) : d === 'bodyX' ? (p._bx ?? p.bodyX ?? 0) * 20 : (p[d] || 0); };
    const dt = 1 / 120, pre = R.preroll || 2, t0 = t - pre, n = Math.round(pre / dt);
    const st = {}; for (const k of names) { const v = drive(P(t0), k); st[k] = { x: v, v: 0 }; }
    for (let i = 1; i <= n; i++) {
      const p = P(t0 + i * dt);
      for (const k of names) { const s = S[k], d = drive(p, k), q = st[k]; const a = -s.k * (q.x - d) - s.c * q.v; q.v += a * dt; q.x += q.v * dt; }
    }
    const P1 = P(t), out = {}; for (const k of names) out[k] = (st[k].x - drive(P1, k)) * (S[k].gain || 1); return out;
  }

  async function load(url) {
    const base = url.slice(0, url.lastIndexOf('/') + 1);
    const R = await (await fetch(url)).json();
    const man = await (await fetch(base + R.manifest)).json(); const mdir = base + R.manifest.slice(0, R.manifest.lastIndexOf('/') + 1);
    glInit(16, 16);
    const invOf = async src => { try { return texFrom(await loadImg(src)); } catch (e) { return null; } };
    const cellOf = n => (R.mesh && R.mesh[n]) || 48;           // finer meshes where layers bend (arms at the elbow)
    const layers = await Promise.all(man.layers.map(async l => ({ ...l, tex: texFrom(await loadImg(mdir + l.name + '.png')), inv: await invOf(mdir + l.name + '.inv.png'), m: mesh(l, cellOf(l.name)) })));
    // head views (drawn three-quarter heads): layer sets that replace the front head, each with its own head geometry
    const views = {};
    for (const [vn, V] of Object.entries(R.views || {})) {
      const vm = await (await fetch(base + V.manifest)).json(), vdir = base + V.manifest.slice(0, V.manifest.lastIndexOf('/') + 1);
      views[vn] = { V, layers: await Promise.all(vm.layers.map(async l => ({ ...l, tex: texFrom(await loadImg(vdir + l.name + '.png')), inv: await invOf(vdir + l.name + '.inv.png'), m: mesh(l, cellOf(l.name)), view: vn }))) };
    }
    // drawn variants of face patches (tools/variants.py): {patch: {variant: layer}}, per view
    const variants = {};
    const loadVars = async (file, key) => {
      const vt = await (await fetch(base + file)).json(), vdir = base + file.slice(0, file.lastIndexOf('/') + 1); variants[key] = {};
      for (const [pn, vs] of Object.entries(vt)) { variants[key][pn] = {};
        for (const [vn, e] of Object.entries(vs)) variants[key][pn][vn] = { name: pn, x: e.x, y: e.y, w: e.w, h: e.h, tex: texFrom(await loadImg(vdir + e.file)), m: mesh(e) }; }
    };
    if (R.variants) await loadVars(R.variants, 'F');
    for (const [vn, V] of Object.entries(R.views || {})) if (V.variants) await loadVars(V.variants, vn);
    const set = a => new Set(a || []);
    const head = set(R.head && R.head.layers), upper = set(R.body && R.body.upper), armOf = {};
    for (const s of ['L', 'R']) if (R.arms && R.arms[s]) for (const n of R.arms[s].layers) armOf[n] = s;
    const puffSides = {};                                      // layer -> the arms whose puff it carries
    for (const s of ['L', 'R']) if (R.arms && R.arms[s] && R.arms[s].puff) for (const n of R.arms[s].puff.layers) (puffSides[n] = puffSides[n] || []).push(s);
    const rig = { R, layers, head, upper, armOf, puffSides, size: man.size, views, variants };
    // the draw list for each view: the front head's layers swapped by name; view-only layers go in front of the next swapped one
    rig.lists = { F: layers };
    for (const [vn, v] of Object.entries(views)) {
      const byName = Object.fromEntries(v.layers.map(l => [l.name, l])), swapped = new Set(R.head.layers || []);   // the base neck stays (chest)
      const list = []; let pending = [], used = new Set();
      const vorder = v.layers.map(l => l.name);
      const hide = new Set(v.V.hide || []);                  // base layers this view replaces outright (e.g. the neck: the yoke draws it)
      for (const l of layers) {
        if (hide.has(l.name)) continue;
        if (!swapped.has(l.name)) { list.push(l); continue; }
        if (byName[l.name]) {
          const i = vorder.indexOf(l.name); pending = vorder.slice(0, i).filter(n => !used.has(n) && !layers.some(b => b.name === n));
          for (const n of pending) { list.push(byName[n]); used.add(n); }
          list.push(byName[l.name]); used.add(l.name);
        }
      }
      // explicit placements [[layer, 'after:ref'], ...]: ref is found among view layers first, then base layers
      for (const [n, where] of (Array.isArray(v.V.insert) ? v.V.insert : Object.entries(v.V.insert || {}))) {
        if (!byName[n]) continue; const ref = where.split(':')[1];
        let i = list.findIndex(l => l.name === ref && l.view); if (i < 0) i = list.findIndex(l => l.name === ref);
        list.splice(i + 1, 0, byName[n]); used.add(n);
      }
      for (const n of vorder) if (!used.has(n)) list.splice(list.indexOf(byName['hair_front']) >= 0 ? list.indexOf(byName['hair_front']) : list.length, 0, byName[n]);
      rig.lists[vn] = list;
    }
    // mouth: a small canvas texture, redrawn when the mouth is open
    if (R.mouth) { rig.mc = document.createElement('canvas'); rig.mc.width = 256; rig.mc.height = 160; rig.mtex = gl.createTexture(); }
    // ID colours for the ID pass (tools/romcheck.py): one per (layer, view), stable, listed in window.RIG_IDS
    const allL = [...layers, ...Object.values(views).flatMap(v => v.layers)]; window.RIG_IDS = {};
    allL.forEach((l, i) => { const k = i + 1, c = [((k * 37) % 251 + 4) / 255, ((k * 91) % 247 + 4) / 255, ((k * 53) % 239 + 8) / 255];
      l.idc = c; window.RIG_IDS[(l.view ? l.view + ':' : '') + l.name] = c.map(v => Math.round(v * 255)); });
    rig.draw = (X, t, P, T) => draw(rig, X, t, P, T);
    rig.locate = (t, P, T, name) => locate(rig, t, P, T, name);
    return rig;
  }

  // puff weight: along the arm axis from the shoulder (0 at along[0], 1 at along[1], smoothstepped), times a soft gate that is 0
  // inside the torso's side contour (a polyline [x, y] top to bottom) and up to `inset` px outside it, 1 from inset + gate px
  const smooth = v => v * v * (3 - 2 * v);
  function puffW(A, x, y, sd) {
    const P = A.puff, sh = A.shoulder, ax = A.axis, sAl = (x - sh[0]) * ax[0] + (y - sh[1]) * ax[1];
    const wa = smooth(clamp((sAl - P.along[0]) / (P.along[1] - P.along[0]), 0, 1));
    if (!wa) return 0;
    const T = P.torso; let xc = T[0][0];
    if (y >= T[T.length - 1][1]) xc = T[T.length - 1][0];
    else for (let i = 1; i < T.length; i++) if (y <= T[i][1]) { const u = clamp((y - T[i - 1][1]) / (T[i][1] - T[i - 1][1] || 1), 0, 1); xc = T[i - 1][0] + (T[i][0] - T[i - 1][0]) * u; break; }
    const out = sd === 'L' ? xc - x : x - xc;                 // (the inner seam, on the contour and just outside it, never moves)
    return wa * smooth(clamp((out - (P.inset ?? 16)) / (P.gate || 48), 0, 1));
  }
  const puffSides = (rig, name) => rig.puffSides[name] || [];

  function deform(rig, l, p, sp, out) {
    const R = rig.R, H = l.view ? { ...R.head, ...R.views[l.view].head } : R.head, B = R.body || {}, rest = l.m.rest, name = l.name;
    const nx = clamp(p.angleX || 0, -1, 1), ny = clamp(p.angleY || 0, -1, 1);
    const breath = p.breath !== undefined ? p.breath : .5 + .5 * Math.sin(p._t * 2 * Math.PI / 3.6);
    const viewNeck = l.view && (H.neckLayers || []).includes(name), viewBody = l.view && (R.views[l.view].bodyLayers || []).includes(name);
    const inHead = l.view ? !viewNeck && !viewBody : rig.head.has(name), inUpper = inHead || viewNeck || viewBody || rig.upper.has(name) || rig.armOf[name];
    const fo = R.follow && R.follow[name];               // e.g. the back-hair plate moves exactly like the side hair in front of it
    const arm = rig.armOf[name] ? R.arms[rig.armOf[name]] : null;
    let dep = H && H.depth && H.depth[name] !== undefined ? H.depth[name] : 0;
    const rigid = H && H.rigid && H.rigid[name], neckL = (H.neckLayers || []).includes(name) && !inHead, pSides = puffSides(rig, name);
    for (let k = 0; k < rest.length; k += 2) {
      let x = rest[k], y = rest[k + 1];
      const as = fo ? (x < (H.center ? H.center[0] : fo.split) ? fo.left : fo.right) : name, sw = R.sway && R.sway[as];
      // hair resting on the shoulders is skinned to the body: 1 above the jaw line, falling to wmin at the tips
      const hg = inHead && H.hang && H.hang[as], hfv = hg ? 1 - (1 - hg[2]) * clamp((y - hg[0]) / (hg[1] - hg[0]), 0, 1) : 1;
      // 1. secondary motion (a bend that grows from the root)
      if (sw) {
        const f = clamp((y - sw.root) / sw.len, 0, 1.2) * (hg ? hfv : 1), amt = (sp[sw.spring] || 0) * (sw.amp || 1);
        if (sw.axis === 'rot') [x, y] = rot(x, y, sw.pivot[0], sw.pivot[1], amt * f);
        else if (sw.axis === 'y') y += amt * f * f; else x += amt * f * f;
      }
      // Measured model (docs/research/README.md §4, Live2D's sample rigs), applied innermost first:
      //   head X/Y warp -> head Z (rigid, about a point just above the chin) -> neck (its hidden top follows part of the head)
      //   -> arms -> body X (a shear peaking at the chest centre) -> breath -> body Z (a progressive bend) -> bounce.
      // Head parameters never move the collar, shoulders or chest; the body's own parameters do.
      const az = p.angleZ || 0, NK = H.neck || {};
      const headMove = (qx, qy, nm, rg, hf) => {
        const px = rg ? rg[0] : qx, u = clamp(Math.abs(px - H.center[0]) / H.radius[0], 0, 1);
        const kk = (K, fb) => { const k = K && K[nm] !== undefined ? K[nm] : fb; return Array.isArray(k) ? k[0] + (k[1] - k[0]) * u : k; };
        const kx = kk(H.kx, .5), ky = kk(H.ky, kx);
        return rot(qx + H.D[0] * nx * kx * hf, qy - H.D[1] * ny * ky * hf, H.pivot[0], H.pivot[1], az * hf * (H.hairZ && H.hairZ[nm] || 1));
      };
      if (inHead) [x, y] = headMove(x, y, as, rigid, hfv);
      else if (neckL) {
        // v: 0 at the chin (its top is hidden behind the jaw), 1 at the collar
        const v = clamp((y - NK.top) / (NK.base - NK.top), 0, 1), wz = interp(NK.wz || [[0, .5], [.5, .16], [1, 0]], v), top = 1 - v;
        x += H.D[0] * nx * .5 * (NK.wx ?? .03) * top; y -= H.D[1] * ny * .5 * (NK.wy ?? .24) * top;
        [x, y] = rot(x, y, H.pivot[0], H.pivot[1], az * wz);
      }
      // the puff sleeves (arms.<s>.puff): skinned to the shoulder rotation by region, so the puff's opening moves exactly with the
      // trim and the upper arm while its top and its inner seam stay on the body (it stretches between; nothing slides apart).
      // Applies to the sleeve layer, and to a view's flattened 'upper' layer, which carries both puffs.
      for (const sd of puffSides(rig, name)) {
        const A = R.arms[sd], w = puffW(A, x, y, sd);
        if (w > 0) [x, y] = rot(x, y, A.shoulder[0], A.shoulder[1], (sd === 'L' ? 1 : -1) * (p['arm' + sd] || 0) * w);
      }
      // arms at the shoulder
      if (arm && !(arm.puff && arm.puff.layers.includes(name))) {
        const sd = rig.armOf[name], sg = sd === 'L' ? 1 : -1;
        // the elbow (FK, before the shoulder): the forearm, cuff and hand rotate about it; the arm's own mesh is skinned across
        // the joint (weight by distance along the arm axis), so it bends instead of breaking
        const eb = p['elbow' + sd] || 0;
        if (eb && arm.elbow) {
          const E = arm.elbow, ax = arm.axis, sAlong = (x - E[0]) * ax[0] + (y - E[1]) * ax[1];
          const bl = arm.blend * clamp(1 - (Math.abs(eb) - 120) / 60, .08, 1);   // past 120 deg the joint sharpens to a hinge (circles, the windmill)
          const w = arm.forearm && arm.forearm.includes(name) ? 1 : name === arm.upper ? (v => v * v * (3 - 2 * v))(clamp((sAlong + bl) / (2 * bl), 0, 1)) : 0;
          if (w) [x, y] = rot(x, y, E[0], E[1], sg * eb * w);
        }
        const a = sg * (p['arm' + sd] || 0) * (name === arm.sleeve ? (arm.sleeveFollow || .4) : 1); [x, y] = rot(x, y, arm.shoulder[0], arm.shoulder[1], a);
      }
      // the body, from REST positions (so every layer meeting at a point moves identically there: no seams). The head block
      // (head, neck, collar top) moves rigidly with the collar line; hair resting on the shoulders blends to the body there.
      if (B.bodyX) {
        const X0 = rest[k], Y0 = rest[k + 1], BX = B.bodyX, hb = inHead || neckL;
        const torso = (qx, qy) => { const fh = 1 - Math.pow(clamp(Math.abs(qx - BX.cx) / BX.rx, 0, 1), 1.5), pv = interp(BX.prof, qy);
                                    const tb = BX.head + (pv - BX.head) * fh;
                                    if (pSides.length) { let w = 0; for (const sd of pSides) w = Math.max(w, puffW(R.arms[sd], qx, qy, sd));   // a puff: the body
                                      return tb * (1 - w) + interp(BX.arm, qy) * w; }                                               // at its seam, the arm at its trim
                                    return rig.armOf[name] ? interp(BX.arm, qy) : tb; };
        const kf = hb ? BX.head * hfv + torso(X0, Y0) * (1 - hfv) : torso(X0, Y0) + ((B.lead || {})[name] || 0);
        x += BX.D * clamp(p._bx || 0, -1.2, 1.2) * kf;
        const BR = B.breath, br = clamp(breath, 0, 1), yb = hb ? BR.prof[0][0] : Y0;
        y -= BR.rise * br * interp(BR.prof, yb); if (!hb) x = BX.cx + (x - BX.cx) * (1 + BR.widen * br * Math.max(0, 1 - Math.abs(Y0 - BR.chestY) / 250));
        const BZ = B.bend, yz = hb ? BZ.prof[0][0] : Y0;
        [x, y] = rot(x, y, BX.cx, interp(BZ.pivot, yz), (p._bz || 0) * interp(BZ.prof, yz));
        y += (p.bounce || 0) * interp(B.bounce || [[0, 1], [1370, 1], [1900, .7], [2400, .2]], yz);
      }
      // the pelvis (outermost): hipX shifts it sideways and tilts it (the hip on the weight side rises), hipY dips it. The torso
      // rides the waist point (translation only: its own tilt is bodyZ, the contrapposto); pelvis layers take the full pelvis
      // transform, skinned into the torso across the waist band; the legs are skinned from the pelvis (top) to the ankle
      // (pinned), and the leg whose top drops shortens by bending its knee inward. The boots stay planted.
      const PV = B.pelvis;
      const fL = [p.footLX || 0, p.footLY || 0], fR = [p.footRX || 0, p.footRY || 0];     // feet: x step, y lift (px, base)
      const hp = { L: p.heelL || 0, R: p.heelR || 0 };                                // heel pivot (px): the ankle and shin rise, the sole stays
      // weight shift: when the hips move over one foot, the other unloads: its heel lifts and it draws a little toward the
      // centre (so feet are never glued through a sway); the lift bends that knee through the leg skinning below
      if (PV && PV.heel) { const hw = clamp(p.hipX || 0, -1.3, 1.3);
        if (PV.heelPivot) { hp.L += PV.heel * Math.max(0, hw); hp.R += PV.heel * Math.max(0, -hw); }   // the free foot rolls onto its toe
        else { fL[1] += PV.heel * Math.max(0, hw); fR[1] += PV.heel * Math.max(0, -hw); }
        fL[0] += PV.drawIn * Math.max(0, hw); fR[0] -= PV.drawIn * Math.max(0, -hw); }
      const artic = hp.L || hp.R || p.footLR || p.footRR || p.footLP || p.footRP;
      if (PV && (p.hipX || p.hipY || fL[0] || fL[1] || fR[0] || fR[1] || artic)) {
        const hx = clamp(p.hipX || 0, -1.3, 1.3), th = -PV.tilt * hx, dxp = PV.D * hx, dyp = (p.hipY || 0) + PV.lift * Math.abs(hx);
        const Tp = (qx, qy) => { const [a, b] = rot(qx, qy, PV.c[0], PV.c[1], th); return [a + dxp, b + dyp]; };
        const [wx, wy] = Tp(PV.waist[0], PV.waist[1]), tdx = wx - PV.waist[0], tdy = wy - PV.waist[1];
        const kind = PV.legs[name] ? 'leg' : PV.feet.includes(name) ? 'foot' : rig.armOf[name] || inHead || neckL ? 'torso' : 'body';
        if (kind === 'torso') { x += tdx; y += tdy; }
        else if (kind === 'body') {
          const Y0 = rest[k + 1], v = clamp((Y0 - PV.band[0]) / (PV.band[1] - PV.band[0]), 0, 1), w = v * v * (3 - 2 * v);
          const [px, py] = Tp(x, y); x = x + tdx + (px - x - tdx) * w; y = y + tdy + (py - y - tdy) * w;
        } else if (kind === 'foot') {
          // the boot is the shin and the foot; below the ankle (PV.ankleJ) the foot articulates in the front view: a heel pivot
          // stretches it between the risen ankle and the planted sole, toe in/out swings the toe box sideways (footSR, deg, + out),
          // and a point lengthens it downward (footSP, -1 flex .. 1 point)
          const sd = name === PV.feet[0] ? 'L' : 'R', f = sd === 'L' ? fL : fR, A = PV.ankleJ || 3300, So = PV.sole || 3700;
          const v = clamp((rest[k + 1] - A) / (So - A), 0, 1), out = sd === 'L' ? -1 : 1;
          x += f[0] + out * Math.sin((p['foot' + sd + 'R'] || 0) * Math.PI / 180) * (PV.footLen || 240) * v;
          y -= f[1] + hp[sd] * (1 - v) - (p['foot' + sd + 'P'] || 0) * (PV.point || 80) * v;
        } else if (kind === 'leg') {
          const L0 = PV.legs[name], Y0 = rest[k + 1], v = clamp((Y0 - L0.top[1]) / (PV.ankle - L0.top[1]), 0, 1);   // 0 at the top, 1 at the ankle
          const [tx, ty] = Tp(L0.top[0], L0.top[1]), ddx = tx - L0.top[0], ddy = ty - L0.top[1], fall = 1 - v;
          const lsd = name === Object.keys(PV.legs)[0] ? 'L' : 'R', f = lsd === 'L' ? fL : fR, fy = f[1] + hp[lsd];   // the ankle follows its foot (and its heel)
          x += ddx * fall + f[0] * v; y += ddy * fall - fy * v;
          const drop = ddy + fy;                                                     // a lifted foot (or heel) also bends the knee
          if (drop > 0) x += Math.sign(PV.c[0] - L0.top[0]) * (1 - 2 * clamp(p.kneeOut || 0, 0, 1)) * PV.knee * drop * Math.sin(Math.PI * v);   // the bent knee (kneeOut 1: out, a curtsy's plié)
        }
      }
      out[k] = x; out[k + 1] = y;
    }
  }

  function drawMouth(rig, p) {
    const c = rig.mc, x = c.getContext('2d'), o = clamp(p.mouthOpen || 0, 0, 1), w = clamp(p.mouthWide || 0, -1, 1), sm = p.smile === undefined ? 1 : p.smile;
    x.clearRect(0, 0, c.width, c.height);
    const cx = 128, cy = 64, hw = 44 + 22 * w, top = 2 - 6 * sm, bot = 6 + o * 52;
    x.lineJoin = 'round'; x.lineCap = 'round';
    x.beginPath(); x.moveTo(cx - hw, cy + top); x.quadraticCurveTo(cx, cy + top + 10 * sm - 4, cx + hw, cy + top);
    x.bezierCurveTo(cx + hw * .8, cy + bot, cx - hw * .8, cy + bot, cx - hw, cy + top); x.closePath();
    x.fillStyle = '#5a1f22'; x.fill();
    x.save(); x.clip(); x.fillStyle = '#e0736e'; x.beginPath(); x.ellipse(cx, cy + bot - 4, hw * .55, 8 + o * 12, 0, 0, Math.PI * 2); x.fill();     // tongue
    x.fillStyle = '#fbf7f2'; x.fillRect(cx - hw, cy + top - 2, hw * 2, 6 + 4 * o); x.restore();                                         // upper teeth
    x.strokeStyle = '#2b1614'; x.lineWidth = 5; x.stroke();
    gl.bindTexture(gl.TEXTURE_2D, rig.mtex); gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, true);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, c); gl.generateMipmap(gl.TEXTURE_2D);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR);
  }

  let black = null;
  const blackTex = () => { if (!black) { black = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, black); gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 1, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array([0, 0, 0, 255])); } return black; };
  function drawMesh(l, pos, T, tex, alpha = 1) {
    const n = pos.length, sc = new Float32Array(n);
    for (let k = 0; k < n; k += 2) { sc[k] = T.x + (pos[k] - T.ox) * T.s; sc[k + 1] = T.y + (pos[k + 1] - T.oy) * T.s; }
    const loc = n2 => gl.getAttribLocation(prog, n2);
    gl.bindBuffer(gl.ARRAY_BUFFER, buf.p); gl.bufferData(gl.ARRAY_BUFFER, sc, gl.DYNAMIC_DRAW); gl.enableVertexAttribArray(loc('p')); gl.vertexAttribPointer(loc('p'), 2, gl.FLOAT, false, 0, 0);
    gl.bindBuffer(gl.ARRAY_BUFFER, buf.uv); gl.bufferData(gl.ARRAY_BUFFER, l.m.uv, gl.DYNAMIC_DRAW); gl.enableVertexAttribArray(loc('uv')); gl.vertexAttribPointer(loc('uv'), 2, gl.FLOAT, false, 0, 0);
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, buf.idx); gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, l.m.idx, gl.DYNAMIC_DRAW);
    gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D, (window.RIG_IDPASS && l.inv) || blackTex()); gl.uniform1i(gl.getUniformLocation(prog, 'inv'), 1);
    gl.activeTexture(gl.TEXTURE0); gl.uniform1i(gl.getUniformLocation(prog, 'tex'), 0);
    gl.bindTexture(gl.TEXTURE_2D, tex); gl.uniform1f(gl.getUniformLocation(prog, 'alpha'), alpha);
    const id = window.RIG_IDPASS && l.idc; gl.uniform4f(gl.getUniformLocation(prog, 'idc'), id ? id[0] : 0, id ? id[1] : 0, id ? id[2] : 0, id ? 1 : 0);
    gl.drawElements(gl.TRIANGLES, l.m.n, gl.UNSIGNED_SHORT, 0);
  }

  // where a layer is (the centroid of its deformed mesh) in screen px, without drawing: e.g. her hand, so a page-wipe can follow it
  function locate(rig, t, P, T, name) {
    const C = rig.R.couple || {}, vang = q => (rig.R.views && q.view && rig.R.views[q.view] && rig.R.views[q.view].angle) || 0;
    const Pt = tt => { const q = { ...P(tt), _t: tt }; const turn = (vang(q) + (q.angleX || 0) * 30) / 35, cp = q.nocouple || !C.on ? 0 : 1;
      q._bx = (q.bodyX || 0) + cp * (C.turn ?? .25) * turn; q._bz = (q.bodyZ || 0) + cp * (C.tilt ?? .25) * (q.angleZ || 0); return q; };
    const p = Pt(t), sp = springs(rig.R, Pt, t), l = (rig.lists[p.view || 'F'] || rig.layers).find(q => q.name === name);
    if (!l) return null;
    const pos = new Float32Array(l.m.rest.length); deform(rig, l, p, sp, pos);
    let sx = 0, sy = 0; for (let k = 0; k < pos.length; k += 2) { sx += pos[k]; sy += pos[k + 1]; }
    const n = pos.length / 2, ox = rig.R.origin[0], oy = rig.R.origin[1];
    return [T.x + (sx / n - ox) * T.s, T.y + (sy / n - oy) * T.s];
  }

  function draw(rig, X, t, P, T) {
    const W = X.canvas.width, Hh = X.canvas.height; glInit(W, Hh);
    // coupling (every shot gets it): a head turn brings the torso a quarter of the way, a tilt brings a little shoulder tilt
    const C = rig.R.couple || {}, vang = q => (rig.R.views && q.view && rig.R.views[q.view] && rig.R.views[q.view].angle) || 0;
    const Pt = tt => { const q = { ...P(tt), _t: tt }; const turn = (vang(q) + (q.angleX || 0) * 30) / 35;
      const cp = q.nocouple || !C.on ? 0 : 1;                  // off unless rig.json asks: coupling belongs in the motion (RIG.perform)
      q._bx = (q.bodyX || 0) + cp * (C.turn ?? .25) * turn; q._bz = (q.bodyZ || 0) + cp * (C.tilt ?? .25) * (q.angleZ || 0); return q; };
    const p = Pt(t), sp = springs(rig.R, Pt, t); rig.last = { p, sp };   // (debug: last pose)
    const TT = { x: T.x, y: T.y, s: T.s, ox: rig.R.origin[0], oy: rig.R.origin[1] };
    const VV = rig.variants[p.view || 'F'] || {};
    const want = n => n === 'eye_L' ? (p.eyeL || p.eyes) : n === 'eye_R' ? (p.eyeR || p.eyes) : n === 'mouth' ? p.mouth
      : n === 'hand_L' ? p.handL : n === 'hand_R' ? p.handR : null;                // drawn hand shapes: pinch, peace, point, fist
    let order = rig.lists[p.view || 'F'] || rig.layers;
    if (p.armFrontL > .5 || p.armFrontR > .5 || p.armBackL > .5 || p.armBackR > .5) {    // the arm's depth, by layer order (a circle passes
      order = order.slice();                                                               // in front of the face or behind the body)
      for (const sd of ['L', 'R']) {
        const grp = ['arm_' + sd, 'cuff_' + sd, 'hand_' + sd], mv = order.filter(l => grp.includes(l.name)); if (!mv.length) continue;
        if (p['armFront' + sd] > .5) order = order.filter(l => !grp.includes(l.name)).concat(mv);
        else if (p['armBack' + sd] > .5) { const rest2 = order.filter(l => !grp.includes(l.name)), at = rest2.findIndex(l => l.name === 'shorts'); order = [...rest2.slice(0, Math.max(0, at)), ...mv, ...rest2.slice(Math.max(0, at))]; }
      }
    }
    for (const l0 of order) {
      if (window.RIG_HIDE && window.RIG_HIDE.includes(l0.name)) continue;          // (debug)
      const w = want(l0.name), l = w && VV[l0.name] && VV[l0.name][w] ? { ...VV[l0.name][w], view: l0.view, idc: l0.idc } : l0;
      const pos = new Float32Array(l.m.rest.length); deform(rig, l, p, sp, pos);
      drawMesh(l, pos, TT, l.tex);
      if (rig.R.mouth && !p.mouth && l.name === rig.R.mouth.layer && (p.mouthOpen || 0) > .02) {
        // the open mouth: a quad over the mouth patch, deformed with the head (carried by the patch's own mesh centre)
        const M = l.view ? { ...rig.R.mouth, ...rig.R.views[l.view].mouth } : rig.R.mouth, q = { m: { uv: new Float32Array([0, 0, 1, 0, 0, 1, 1, 1]), idx: new Uint16Array([0, 1, 2, 1, 3, 2]), n: 6,
          rest: new Float32Array([M.center[0] - M.w / 2, M.center[1] - M.h / 2, M.center[0] + M.w / 2, M.center[1] - M.h / 2, M.center[0] - M.w / 2, M.center[1] + M.h / 2, M.center[0] + M.w / 2, M.center[1] + M.h / 2]) }, name: l.name };
        q.view = l.view; const qp = new Float32Array(8); deform(rig, q, p, sp, qp); drawMouth(rig, p); drawMesh(q, qp, TT, rig.mtex);
      }
    }
    X.save(); X.setTransform(1, 0, 0, 1, 0, 0); X.drawImage(cv, 0, 0); X.restore();
  }

  // keys: [[t, {param: value}], ...] -> P(t). Each move eases in-out with a small anticipation (the opposite way first)
  // and overshoot, then holds. `twos`: pose parameters step at 12 fps (anime timing); physics and the camera stay on ones.
  function keys(list, o = {}) {
    const ant = o.anticipate ?? .1, over = o.overshoot ?? .08, dur = o.move ?? .22, fps = o.twos ? 12 : 0;
    // keys land on drawings (twos grid), so a pose change is never a drawing late; a key that switches the drawn view is a cut:
    // its values arrive at once (a new drawing comes in its own pose) instead of easing from the old one
    const snapT = t => fps ? Math.ceil(t * fps - 1e-6) / fps : t;
    const names = [...new Set(list.flatMap(([, k]) => Object.keys(k)))];
    const tracks = {}; for (const n of names) tracks[n] = list.filter(([, k]) => n in k).map(([t, k]) => [snapT(t), k[n], 'view' in k]);
    const shape = u => {                                        // 0..1 -> 0..1 with anticipation and overshoot
      if (u <= 0) return 0; if (u >= 1) return 1;
      if (u < .25) return -ant * Math.sin(u / .25 * Math.PI);  // wind up
      const v = (u - .25) / .75, e = v < .5 ? 4 * v * v * v : 1 - Math.pow(-2 * v + 2, 3) / 2;
      return e + over * Math.sin(v * Math.PI) * (v > .6 ? 1 : 0) * Math.sin((v - .6) / .4 * Math.PI);
    };
    return t => {
      const tq = fps ? Math.floor(t * fps) / fps : t, out = {};
      for (const n of names) {
        const tr = tracks[n]; let v = tr[0][1];
        for (let i = 1; i < tr.length; i++) { const [t1, v1, cut] = tr[i], [, v0] = tr[i - 1]; if (tq < t1) break; v = typeof v1 === 'number' && !cut ? v0 + (v1 - v0) * shape((tq - t1) / dur) : v1; }
        out[n] = v;
      }
      return out;
    };
  }

  // perform(rig, P, o): the body's motion derived from the head's, per the official motions (docs/research §4): the same
  // direction, a smaller swing, leading by ~60 ms. Turn: bodyX += x * head turn (drawn views count as real angles), clamped;
  // tilt: bodyZ (deg) += z * angleZ (deg). Any bodyX/bodyZ the choreography sets itself is kept and added to.
  function perform(rig, P, o = {}) {
    const C = { x: 1.76, z: .41, lead: .06, ...(rig.R.perform || {}), ...o };
    const vang = q => (rig.R.views && q.view && rig.R.views[q.view] && rig.R.views[q.view].angle) || 0;
    return t => { const q = P(t), h = P(t + C.lead), turn = (vang(h) + (h.angleX || 0) * 30) / 30;
      // contrapposto: the shoulders counter-tilt over the weight leg (bodyZ follows hipX), and the head stays near level
      const cz = (C.contra ?? 3) * (q.hipX || 0), bz = (q.bodyZ || 0) + C.z * (h.angleZ || 0) + cz;
      return { ...q, bodyX: (q.bodyX || 0) + clamp(C.x * turn, -1, 1), bodyZ: bz, angleZ: (q.angleZ || 0) - (C.level ?? .8) * cz }; };
  }

  return { load, keys, perform };
})();
