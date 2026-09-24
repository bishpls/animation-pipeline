// engine/riso.js: a risograph print simulator. Shots draw COVERAGE into separate ink layers (Canvas2D, alpha = ink),
// then the compositor prints them on paper (WebGL): overprint by multiply, halftone for tints, solid-edge AA kept
// crisp, ink mottling + speckle, rough ink edges, per-drawing misregistration and paper grain.
//
//   risoSetup({ paper: '#f3ede2', inks: [{ name: 'blue', hex: '#2b3fd6', angle: 15 }, ...], cell: 9 })
//   ink(path, { blue: 1, pink: .35 })        fill a Path2D (or point list) into one or more inks (value = coverage 0..1)
//   ink(path, 'black')                       same, full coverage
//   ink(path, { black: 1 }, { stroke: 6 })   stroke instead of fill
//   paint(path, { pink: 1 })               OPAQUE: knock the other inks under the shape, then ink (objects)
//   knock(path)  knock(path, ['blue'])       erase ink (paper shows through): knockouts are how print makes light
//   layer('pink')                            the raw Canvas2D context of one ink, for anything custom
//   save() restore() translate() rotate() scale() cam(cx, cy, zoom, rot)   transform ALL inks together
// Coverage below ~.97 prints as halftone dots in that ink's screen angle; solids print solid.

const RISO = { inks: [], byName: {}, paper: [0.953, 0.929, 0.886], cell: 9, misreg: 1.6, gl: null, out: null, frameT: 0 };

function hexRGB(h) { h = h.replace('#', ''); return [0, 2, 4].map(i => parseInt(h.slice(i, i + 2), 16) / 255); }

function risoSetup(o) {
  RISO.paper = hexRGB(o.paper || '#f3ede2');
  RISO.cell = o.cell || 9;
  RISO.misreg = o.misreg ?? 1.6;
  RISO.inks = o.inks.map((k, i) => {
    const c = document.createElement('canvas'); c.width = W; c.height = H;
    const ctx = c.getContext('2d', { willReadFrequently: false });
    const ink = { name: k.name, rgb: hexRGB(k.hex), hex: k.hex, angle: (k.angle ?? [15, 75, 0, 45, 30][i]) * D2R, canvas: c, ctx, i,
      reg: k.reg || [hash(i * 7.1) * 2 - 1, hash(i * 3.3) * 2 - 1] };
    RISO.byName[k.name] = ink;
    return ink;
  });
  glSetup();
}

// ------------------------------------------------------------------ transforms: mirrored on every ink
const _all = fn => { for (const k of RISO.inks) fn(k.ctx); };
const save = () => _all(c => c.save());
const restore = () => _all(c => c.restore());
const translate = (x, y) => _all(c => c.translate(x, y));
const rotate = a => _all(c => c.rotate(a));
const scale = (x, y = x) => _all(c => c.scale(x, y));
const resetT = () => _all(c => c.setTransform(1, 0, 0, 1, 0, 0));
// camera: world point (cx, cy) lands at screen centre. Call inside save()/restore().
function cam(cx, cy, zoom = 1, rot = 0) { translate(W / 2, H / 2); rotate(rot); scale(zoom); translate(-cx, -cy); }
// world -> screen with the current transform (for irises, screen-space type anchored to a world thing)
function toScreen(x, y) { const m = RISO.inks[0].ctx.getTransform(); return [m.a * x + m.c * y + m.e, m.b * x + m.d * y + m.f]; }

// ------------------------------------------------------------------ paths
function P(pts, close = true) {        // point list -> Path2D
  if (pts instanceof Path2D) return pts;
  const p = new Path2D(); if (!pts.length) return p;
  p.moveTo(pts[0][0], pts[0][1]);
  for (let i = 1; i < pts.length; i++) p.lineTo(pts[i][0], pts[i][1]);
  if (close) p.closePath();
  return p;
}
function layer(name) { return RISO.byName[name].ctx; }

// ink(path, spec, opts): spec = 'name' | { name: coverage | (ctx) => fillStyle }
function ink(path, spec, o = {}) {
  const p = P(path, o.close !== false && !o.stroke);
  const s = typeof spec === 'string' ? { [spec]: 1 } : spec;
  for (const [name, v] of Object.entries(s)) {
    const k = RISO.byName[name]; if (!k) throw new Error('no ink ' + name);
    const c = k.ctx;
    if (typeof v === 'number' && v <= 0) continue;
    c.save();
    const style = typeof v === 'function' ? v(c) : `rgba(0,0,0,${clamp(v)})`;
    if (o.alpha != null) c.globalAlpha = o.alpha;
    if (o.stroke) {
      c.strokeStyle = style; c.lineWidth = o.stroke; c.lineCap = o.cap || 'round'; c.lineJoin = o.join || 'round';
      if (o.dash) c.setLineDash(o.dash);
      c.stroke(p);
    } else { c.fillStyle = style; c.fill(p, o.rule || 'nonzero'); }
    c.restore();
  }
}
// paint(path, spec): OPAQUE ink. Knocks every other ink out under the shape first, so a pink blanket on a blue
// night prints pink (ink() alone overprints: pink on blue = violet). Use paint for objects, ink for overprint effects.
function paint(path, spec, o = {}) {
  const s = typeof spec === 'string' ? { [spec]: 1 } : spec;
  const others = RISO.inks.map(k => k.name).filter(n => !(n in s) || s[n] <= 0);
  if (others.length) knock(path, others, 1, o.stroke ? { stroke: o.stroke } : {});
  ink(path, s, o);
}
// knock(path, which = all inks, amount = 1 | gradient fn): erase ink so paper shows through (o.stroke, o.blur)
function knock(path, which = null, amount = 1, o = {}) {
  const p = P(path, !o.stroke);
  for (const k of RISO.inks) {
    if (which && !which.includes(k.name)) continue;
    const c = k.ctx; c.save(); c.globalCompositeOperation = 'destination-out';
    const st = typeof amount === 'function' ? amount(c) : `rgba(0,0,0,${amount})`;
    if (o.blur) c.filter = `blur(${o.blur}px)`;
    if (o.stroke) { c.strokeStyle = st; c.lineWidth = o.stroke; c.lineCap = 'round'; c.lineJoin = 'round'; c.stroke(p); }
    else { c.fillStyle = st; c.fill(p); }
    c.restore();
  }
}
// flood a whole ink (screen space) at a coverage
function flood(name, v = 1) { const c = layer(name); c.save(); c.setTransform(1, 0, 0, 1, 0, 0); c.fillStyle = `rgba(0,0,0,${v})`; c.fillRect(0, 0, W, H); c.restore(); }
// radial halftone glow: coverage falls from a at r0 to 0 at r1 (world space)
const radial = (x, y, r0, r1, a = 1, curve = 1.6) => c => {
  const g = c.createRadialGradient(x, y, r0, x, y, r1);
  for (let i = 0; i <= 8; i++) { const u = i / 8; g.addColorStop(u, `rgba(0,0,0,${a * (1 - u) ** curve})`); }
  return g;
};
const linear = (x0, y0, x1, y1, a0 = 1, a1 = 0) => c => {
  const g = c.createLinearGradient(x0, y0, x1, y1); g.addColorStop(0, `rgba(0,0,0,${a0})`); g.addColorStop(1, `rgba(0,0,0,${a1})`); return g;
};

function risoClear() {
  for (const k of RISO.inks) { const c = k.ctx; c.setTransform(1, 0, 0, 1, 0, 0); c.globalAlpha = 1; c.globalCompositeOperation = 'source-over'; c.clearRect(0, 0, W, H); }
}

// ------------------------------------------------------------------ the press (WebGL)
const VS = `attribute vec2 p; varying vec2 uv; void main(){ uv = p * .5 + .5; gl_Position = vec4(p, 0., 1.); }`;
const FS = (n) => `precision highp float;
varying vec2 uv;
uniform vec2 res; uniform vec3 paper; uniform float seed, cell, bf, paperOn;
${Array.from({ length: n }, (_, i) => `uniform sampler2D L${i}; uniform vec3 C${i}; uniform vec2 O${i}; uniform float A${i}, D${i};`).join('\n')}
float h21(vec2 p){ p = fract(p * vec2(123.34, 456.21)); p += dot(p, p + 45.32); return fract(p.x * p.y); }
float vn(vec2 p){ vec2 i = floor(p), f = fract(p); f = f*f*(3.-2.*f);
  return mix(mix(h21(i), h21(i+vec2(1,0)), f.x), mix(h21(i+vec2(0,1)), h21(i+vec2(1,1)), f.x), f.y); }
float spot(vec2 px, float a){ float s = sin(a), c = cos(a); vec2 q = mat2(c, -s, s, c) * px / cell; vec2 f = fract(q) - .5;
  return .5 - .25 * (cos(6.2831853 * f.x) + cos(6.2831853 * f.y)); }
float cov(sampler2D L, vec2 px){ return texture2D(L, px / res).a; }
vec3 layerK(sampler2D L, vec3 col, vec2 off, float ang, float dens, vec2 px, vec3 acc){
  vec2 warp = vec2(vn(px / 5. + seed), vn(px / 5. - seed + 9.)) - .5;
  vec2 q = px - off + warp * 1.1;
  float c = cov(L, q);
  if (c < .002) return acc;
  float mx = max(max(cov(L, q + vec2(1.5, 0)), cov(L, q - vec2(1.5, 0))), max(cov(L, q + vec2(0, 1.5)), cov(L, q - vec2(0, 1.5))));
  float k;
  if (c > .965 || mx > .965) k = c;                                  // solid, or the AA edge of a solid: keep it crisp
  else {                                                              // a tint: halftone with riso grain
    float g = (h21(px + seed) - .5) * .16 + (vn(px / 2.5 + seed) - .5) * .12;
    float th = spot(px, ang) + g;
    float aa = 1.2 / cell;
    k = smoothstep(th - aa, th + aa, c);
  }
  float d = dens * (.9 + .1 * vn(px / 70. + seed * .1 + ang)) * (1. - .55 * step(.9965, h21(floor(px / 1.5) + seed * 3.1)));
  return acc * mix(vec3(1.), col, clamp(k * d, 0., 1.));
}
void main(){
  vec2 px = vec2(uv.x, 1. - uv.y) * res;
  float fib = vn(px * vec2(.012, .22) + 3.) * .6 + vn(px * vec2(.2, .015) + 7.) * .4;
  float grain = h21(px + bf * 1.37);
  vec3 acc = paperOn > .5 ? paper * (1. - .045 * fib) * (1. - .03 * grain) : vec3(1.);
  ${Array.from({ length: n }, (_, i) => `acc = layerK(L${i}, C${i}, O${i}, A${i}, D${i}, px, acc);`).join('\n  ')}
  gl_FragColor = vec4(acc, 1.);
}`;

function glSetup() {
  const out = document.getElementById('out') || document.createElement('canvas');
  out.width = W; out.height = H; RISO.out = out;
  const gl = out.getContext('webgl', { preserveDrawingBuffer: true, antialias: false, premultipliedAlpha: false });
  RISO.gl = gl;
  const n = RISO.inks.length;
  const sh = (type, src) => { const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s); if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s)); return s; };
  const prog = gl.createProgram();
  gl.attachShader(prog, sh(gl.VERTEX_SHADER, VS)); gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, FS(n)));
  gl.linkProgram(prog); gl.useProgram(prog);
  const buf = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buf);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
  const loc = gl.getAttribLocation(prog, 'p'); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
  gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
  RISO.tex = RISO.inks.map((k, i) => {
    const t = gl.createTexture(); gl.activeTexture(gl.TEXTURE0 + i); gl.bindTexture(gl.TEXTURE_2D, t);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.uniform1i(gl.getUniformLocation(prog, 'L' + i), i);
    return t;
  });
  RISO.u = name => gl.getUniformLocation(prog, name);
  gl.uniform2f(RISO.u('res'), W, H);
}

// print the inks onto paper. o.density = { ink: 0..1 } to fade a whole ink (e.g. for fades), o.paper = false for no paper texture
function risoPrint(t, o = {}) {
  const gl = RISO.gl, u = RISO.u, bf = BF(t);
  gl.viewport(0, 0, W, H);
  gl.uniform3fv(u('paper'), o.paperRGB || RISO.paper);
  gl.uniform1f(u('seed'), (bf % 97) * 1.618);
  gl.uniform1f(u('bf'), bf);
  gl.uniform1f(u('cell'), o.cell || RISO.cell);
  gl.uniform1f(u('paperOn'), o.paper === false ? 0 : 1);
  RISO.inks.forEach((k, i) => {
    gl.activeTexture(gl.TEXTURE0 + i); gl.bindTexture(gl.TEXTURE_2D, RISO.tex[i]);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, k.canvas);
    gl.uniform3fv(u('C' + i), k.rgb);
    const m = o.misreg ?? RISO.misreg;     // fixed per-ink offset + a small per-drawing wander (each frame is a new print)
    gl.uniform2f(u('O' + i), k.reg[0] * m + (hash(bf * 1.3 + i) - .5) * m * .6, k.reg[1] * m + (hash(bf * 2.9 + i * 5) - .5) * m * .6);
    gl.uniform1f(u('A' + i), k.angle);
    gl.uniform1f(u('D' + i), o.density && o.density[k.name] != null ? o.density[k.name] : 1);
  });
  gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
}
