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
    precision highp float; in vec2 v; uniform sampler2D tex; uniform float alpha; out vec4 o;
    void main() { o = texture(tex, v) * alpha; }`;
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
  function mesh(l) {
    const cols = Math.max(2, Math.min(28, Math.round(l.w / 48))), rows = Math.max(2, Math.min(28, Math.round(l.h / 48)));
    const rest = [], uv = [], idx = [];
    for (let j = 0; j <= rows; j++) for (let i = 0; i <= cols; i++) { rest.push(l.x + l.w * i / cols, l.y + l.h * j / rows); uv.push(i / cols, j / rows); }
    for (let j = 0; j < rows; j++) for (let i = 0; i < cols; i++) { const a = j * (cols + 1) + i, b = a + 1, c = a + cols + 1, d = c + 1; idx.push(a, b, c, b, d, c); }
    return { rest: new Float32Array(rest), uv: new Float32Array(uv), idx: new Uint16Array(idx), n: idx.length };
  }

  const rot = (x, y, cx, cy, deg) => { const a = deg * Math.PI / 180, c = Math.cos(a), s = Math.sin(a), dx = x - cx, dy = y - cy; return [cx + dx * c - dy * s, cy + dx * s + dy * c]; };
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

  // damped springs, stepped at 1/120 s from a pre-roll: out = spring position minus its driver (the lag), times gain
  function springs(R, P, t) {
    const S = R.springs || {}, names = Object.keys(S); if (!names.length) return {};
    const drive = (p, name) => { const d = S[name].drive; return d === 'headX' ? (p.angleX || 0) * 30 : d === 'headZ' ? (p.angleZ || 0) : d === 'headY' ? (p.angleY || 0) * 18
      : d === 'bodyZ' ? (p.bodyZ || 0) : d === 'bounce' ? (p.bounce || 0) : d === 'bodyX' ? (p.bodyX || 0) * 20 : (p[d] || 0); };
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
    const layers = await Promise.all(man.layers.map(async l => ({ ...l, tex: texFrom(await loadImg(mdir + l.name + '.png')), m: mesh(l) })));
    const set = a => new Set(a || []);
    const head = set(R.head && R.head.layers), upper = set(R.body && R.body.upper), armOf = {};
    for (const s of ['L', 'R']) if (R.arms && R.arms[s]) for (const n of R.arms[s].layers) armOf[n] = s;
    const rig = { R, layers, head, upper, armOf, size: man.size };
    // mouth: a small canvas texture, redrawn when the mouth is open
    if (R.mouth) { rig.mc = document.createElement('canvas'); rig.mc.width = 256; rig.mc.height = 160; rig.mtex = gl.createTexture(); }
    rig.draw = (X, t, P, T) => draw(rig, X, t, P, T);
    return rig;
  }

  function deform(rig, l, p, sp, out) {
    const R = rig.R, H = R.head, B = R.body || {}, rest = l.m.rest, name = l.name;
    const ax = clamp(p.angleX || 0, -1, 1) * 30 * Math.PI / 180, ay = clamp(p.angleY || 0, -1, 1) * 18 * Math.PI / 180;
    const breath = p.breath !== undefined ? p.breath : .5 + .5 * Math.sin(p._t * 2 * Math.PI / 3.6);
    const inHead = rig.head.has(name), inUpper = inHead || rig.upper.has(name) || rig.armOf[name];
    const sw = R.sway && R.sway[name], arm = rig.armOf[name] ? R.arms[rig.armOf[name]] : null;
    let dep = H && H.depth && H.depth[name] !== undefined ? H.depth[name] : 0;
    for (let k = 0; k < rest.length; k += 2) {
      let x = rest[k], y = rest[k + 1];
      // 1. secondary motion (a bend that grows from the root)
      if (sw) {
        const f = clamp((y - sw.root) / sw.len, 0, 1.2), amt = (sp[sw.spring] || 0) * (sw.amp || 1);
        if (sw.axis === 'rot') [x, y] = rot(x, y, sw.pivot[0], sw.pivot[1], amt * f);
        else if (sw.axis === 'y') y += amt * f * f; else x += amt * f * f;
      }
      // 2. the head turn: a cylinder with depth (near layers travel further; the far side compresses)
      if (inHead) {
        const d = Array.isArray(dep) ? dep[0] + (dep[1] - dep[0]) * clamp(Math.abs(x - H.center[0]) / H.radius[0], 0, 1) : dep;
        const u = clamp((x - H.center[0]) / H.radius[0], -.985, .985), v = clamp((y - H.center[1]) / H.radius[1], -.985, .985);
        const rx = H.radius[0] * (1 + d), ry = H.radius[1] * (1 + d * .6);
        const extraX = (x - H.center[0]) - H.radius[0] * u, extraY = (y - H.center[1]) - H.radius[1] * v;   // beyond the cylinder: carried rigidly
        x = H.center[0] + rx * Math.sin(Math.asin(u) + ax) - (rx - H.radius[0]) * u + extraX * Math.cos(ax);
        y = H.center[1] + ry * Math.sin(Math.asin(v) - ay) - (ry - H.radius[1]) * v + extraY * Math.cos(ay);
        [x, y] = rot(x, y, H.neck[0], H.neck[1], (p.angleZ || 0));
      }
      // 3. arms at the shoulder (the sleeve follows part of the way)
      if (arm) { const a = (rig.armOf[name] === 'L' ? 1 : -1) * (p['arm' + rig.armOf[name]] || 0) * (name === arm.sleeve ? (arm.sleeveFollow || .4) : 1); [x, y] = rot(x, y, arm.shoulder[0], arm.shoulder[1], a); }
      // 4. breath: the upper body stretches a little above the waist; everything above rides along
      if (inUpper && B.waist) { const s = .006 * breath; if (y < B.waist[1]) y = B.waist[1] + (y - B.waist[1]) * (1 + s); }
      // 5. lean from the hips, and the bounce
      if (B.hip) {
        const w = inUpper ? 1 : (y < B.hip[1] ? .6 : .15);
        [x, y] = rot(x, y, B.hip[0], B.hip[1] + 600, (p.bodyZ || 0) * w);
        x += (p.bodyX || 0) * 18 * (inHead ? 1.4 : inUpper ? 1 : .3);
        y += (p.bounce || 0) * (inUpper ? 1 : y < B.hip[1] ? .7 : .2);
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

  function drawMesh(l, pos, T, tex, alpha = 1) {
    const n = pos.length, sc = new Float32Array(n);
    for (let k = 0; k < n; k += 2) { sc[k] = T.x + (pos[k] - T.ox) * T.s; sc[k + 1] = T.y + (pos[k + 1] - T.oy) * T.s; }
    const loc = n2 => gl.getAttribLocation(prog, n2);
    gl.bindBuffer(gl.ARRAY_BUFFER, buf.p); gl.bufferData(gl.ARRAY_BUFFER, sc, gl.DYNAMIC_DRAW); gl.enableVertexAttribArray(loc('p')); gl.vertexAttribPointer(loc('p'), 2, gl.FLOAT, false, 0, 0);
    gl.bindBuffer(gl.ARRAY_BUFFER, buf.uv); gl.bufferData(gl.ARRAY_BUFFER, l.m.uv, gl.DYNAMIC_DRAW); gl.enableVertexAttribArray(loc('uv')); gl.vertexAttribPointer(loc('uv'), 2, gl.FLOAT, false, 0, 0);
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, buf.idx); gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, l.m.idx, gl.DYNAMIC_DRAW);
    gl.bindTexture(gl.TEXTURE_2D, tex); gl.uniform1f(gl.getUniformLocation(prog, 'alpha'), alpha);
    gl.drawElements(gl.TRIANGLES, l.m.n, gl.UNSIGNED_SHORT, 0);
  }

  function draw(rig, X, t, P, T) {
    const W = X.canvas.width, Hh = X.canvas.height; glInit(W, Hh);
    const Pt = tt => ({ ...P(tt), _t: tt }), p = Pt(t), sp = springs(rig.R, Pt, t);
    const TT = { x: T.x, y: T.y, s: T.s, ox: rig.R.origin[0], oy: rig.R.origin[1] };
    for (const l of rig.layers) {
      const pos = new Float32Array(l.m.rest.length); deform(rig, l, p, sp, pos);
      drawMesh(l, pos, TT, l.tex);
      if (rig.R.mouth && l.name === rig.R.mouth.layer && (p.mouthOpen || 0) > .02) {
        // the open mouth: a quad over the mouth patch, deformed with the head (carried by the patch's own mesh centre)
        const M = rig.R.mouth, q = { m: { uv: new Float32Array([0, 0, 1, 0, 0, 1, 1, 1]), idx: new Uint16Array([0, 1, 2, 1, 3, 2]), n: 6,
          rest: new Float32Array([M.center[0] - M.w / 2, M.center[1] - M.h / 2, M.center[0] + M.w / 2, M.center[1] - M.h / 2, M.center[0] - M.w / 2, M.center[1] + M.h / 2, M.center[0] + M.w / 2, M.center[1] + M.h / 2]) }, name: l.name };
        const qp = new Float32Array(8); deform(rig, q, p, sp, qp); drawMouth(rig, p); drawMesh(q, qp, TT, rig.mtex);
      }
    }
    X.save(); X.setTransform(1, 0, 0, 1, 0, 0); X.drawImage(cv, 0, 0); X.restore();
  }

  return { load };
})();
