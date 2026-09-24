// EMBER III · hand-animated — engine core: time, easing, noise, tracks, camera, shape drawing.
// Every frame is a pure function of t (seconds). No hidden state.

export const W = 1920, H = 1080, FPS = 24, BPM = 150;
export const BEAT = 60 / BPM;           // 0.4 s
export const b2t = (b) => b * BEAT;
export const t2b = (t) => t / BEAT;

// ------------------------------------------------------------------ math
export const clamp = (x, a = 0, b = 1) => (x < a ? a : x > b ? b : x);
export const lerp = (a, b, u) => a + (b - a) * u;
export const mix2 = (p, q, u) => [lerp(p[0], q[0], u), lerp(p[1], q[1], u)];
export const smooth = (u) => { u = clamp(u); return u * u * (3 - 2 * u); };
export const ease = {
  lin: (u) => u,
  in: (u) => u * u * u,
  out: (u) => 1 - (1 - u) ** 3,
  io: (u) => (u < 0.5 ? 4 * u ** 3 : 1 - (-2 * u + 2) ** 3 / 2),
  in2: (u) => u * u,
  out2: (u) => 1 - (1 - u) ** 2,
  outx: (u) => 1 - (1 - u) ** 5,       // snap
  inx: (u) => u ** 5,
  back: (u) => 1 + 2.7 * (u - 1) ** 3 + 1.7 * (u - 1) ** 2,   // overshoot then settle
  step: (u) => (u < 1 ? 0 : 1),
  s: smooth,
};
export const TAU = Math.PI * 2, D2R = Math.PI / 180;
export const rot = (p, a) => [p[0] * Math.cos(a) - p[1] * Math.sin(a), p[0] * Math.sin(a) + p[1] * Math.cos(a)];
export const add = (p, q) => [p[0] + q[0], p[1] + q[1]];
export const sub = (p, q) => [p[0] - q[0], p[1] - q[1]];
export const mul = (p, s) => [p[0] * s, p[1] * s];
export const len = (p) => Math.hypot(p[0], p[1]);
export const norm = (p) => { const l = len(p) || 1; return [p[0] / l, p[1] / l]; };
export const perp = (p) => [-p[1], p[0]];

// deterministic hash noise
export function hash(n) { n = Math.sin(n * 127.1 + 311.7) * 43758.5453; return n - Math.floor(n); }
export function hash2(x, y) { return hash(x * 12.9898 + y * 78.233); }
export function noise1(x) { const i = Math.floor(x), f = x - i; const u = f * f * (3 - 2 * f); return lerp(hash(i), hash(i + 1), u) * 2 - 1; }
export function fbm(x, oct = 3) { let s = 0, a = 0.5, f = 1; for (let i = 0; i < oct; i++) { s += a * noise1(x * f + i * 17.3); a *= 0.5; f *= 2; } return s; }
export function rng(seed) { let a = seed >>> 0; return () => { a |= 0; a = (a + 0x6d2b79f5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }

// anime timing: hold drawings on twos / threes
export const onN = (t, n) => Math.floor(t * FPS / n) * n / FPS;

// ------------------------------------------------------------------ keyframe track (sparse, per-param)
export class Track {
  constructor(defaults) { this.d = { ...defaults }; this.k = {}; }
  key(t, ez, vals) {
    for (const [p, v] of Object.entries(vals)) {
      (this.k[p] ||= []).push([t, v, ez]);
      this.k[p].sort((a, b) => a[0] - b[0]);
    }
    return this;
  }
  get(p, t) {
    const ks = this.k[p];
    if (!ks) return this.d[p];
    if (t <= ks[0][0]) return ks[0][1];
    for (let i = 1; i < ks.length; i++) {
      if (t < ks[i][0]) {
        const [t0, v0] = ks[i - 1], [t1, v1, e] = ks[i];
        const u = (ease[e] || ease.io)(clamp((t - t0) / (t1 - t0)));
        return v0 + (v1 - v0) * u;
      }
    }
    return ks[ks.length - 1][1];
  }
  eval(t) { const o = {}; for (const p of Object.keys(this.d)) o[p] = this.get(p, t); return o; }
}

// Follow-through without a simulation: a damped 2nd-order response over the recent history of fn.
// Returns fn's lagged value (vector) — pure in t.
export function lagged(fn, t, { freq = 3.0, damp = 0.35, win = 0.9, n = 24 } = {}) {
  const w0 = TAU * freq, wd = w0 * Math.sqrt(1 - damp * damp);
  let sx = 0, sy = 0, ws = 0;
  for (let i = 0; i < n; i++) {
    const tau = (i / (n - 1)) * win;
    const wgt = Math.exp(-damp * w0 * tau) * Math.sin(wd * tau + 1.2) + 0.0001;   // impulse response (shifted)
    const v = fn(t - tau);
    sx += v[0] * wgt; sy += v[1] * wgt; ws += wgt;
  }
  return [sx / ws, sy / ws];
}

// ------------------------------------------------------------------ camera
export class Cam {
  constructor(x = W / 2, y = H / 2, zoom = 1, rot = 0, sx = 0, sy = 0) { Object.assign(this, { x, y, zoom, rot, sx, sy }); }
  apply(ctx, par = 1) {
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.translate(W / 2 + this.sx * par, H / 2 + this.sy * par);
    ctx.rotate(this.rot * Math.min(1, 0.4 + 0.6 * par));
    const z = 1 + (this.zoom - 1) * par;
    ctx.scale(z, z);
    ctx.translate(-(this.x - W / 2) * par - W / 2, -(this.y - H / 2) * par - H / 2);
  }
}
export function shake(t, amt, seed = 0, freq = 38) {
  return [amt * fbm(t * freq + seed, 2), amt * fbm(t * freq + seed + 50, 2)];
}

// ------------------------------------------------------------------ shapes
export function pathPoly(ctx, pts, close = true) {
  ctx.beginPath();
  ctx.moveTo(pts[0][0], pts[0][1]);
  for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]);
  if (close) ctx.closePath();
}
// Catmull-Rom smooth closed/open path
export function pathSmooth(ctx, pts, close = true, tension = 1) {
  const n = pts.length;
  ctx.beginPath();
  ctx.moveTo(pts[0][0], pts[0][1]);
  const last = close ? n : n - 1;
  for (let i = 0; i < last; i++) {
    const p0 = pts[close ? (i - 1 + n) % n : Math.max(0, i - 1)];
    const p1 = pts[i], p2 = pts[(i + 1) % n];
    const p3 = pts[close ? (i + 2) % n : Math.min(n - 1, i + 2)];
    const k = tension / 6;
    ctx.bezierCurveTo(p1[0] + (p2[0] - p0[0]) * k, p1[1] + (p2[1] - p0[1]) * k,
      p2[0] - (p3[0] - p1[0]) * k, p2[1] - (p3[1] - p1[1]) * k, p2[0], p2[1]);
  }
  if (close) ctx.closePath();
}
// tapered stroke along a polyline -> filled polygon (anime line art / hair strands / smears)
export function taper(pts, w0, w1, wmid = null) {
  const L = [], R = [];
  const n = pts.length;
  for (let i = 0; i < n; i++) {
    const a = pts[Math.max(0, i - 1)], b = pts[Math.min(n - 1, i + 1)];
    const d = norm(sub(b, a)), p = perp(d);
    const u = i / (n - 1);
    let w = wmid == null ? lerp(w0, w1, u) : (u < 0.5 ? lerp(w0, wmid, u * 2) : lerp(wmid, w1, (u - 0.5) * 2));
    L.push(add(pts[i], mul(p, w / 2)));
    R.push(sub(pts[i], mul(p, w / 2)));
  }
  return L.concat(R.reverse());
}
// capsule polygon between two points with radii (limbs)
export function capsule(a, ra, b, rb, seg = 8) {
  const d = sub(b, a), ang = Math.atan2(d[1], d[0]);
  const pts = [];
  for (let i = 0; i <= seg; i++) { const q = ang + Math.PI / 2 + (i / seg) * Math.PI; pts.push([a[0] + Math.cos(q) * ra, a[1] + Math.sin(q) * ra]); }
  for (let i = 0; i <= seg; i++) { const q = ang - Math.PI / 2 + (i / seg) * Math.PI; pts.push([b[0] + Math.cos(q) * rb, b[1] + Math.sin(q) * rb]); }
  return pts;
}

// Cel shading: base fill, then a hard shadow = the shape minus itself shifted toward the light.
export function cel(ctx, drawPath, base, shade, light = [-0.6, -0.8], k = 0.18, size = 60, line = null, lw = 3) {
  drawPath(ctx);
  ctx.fillStyle = shade;
  ctx.fill();
  ctx.save();
  drawPath(ctx);
  ctx.clip();
  ctx.translate(light[0] * k * size, light[1] * k * size);
  drawPath(ctx);
  ctx.fillStyle = base;
  ctx.fill();
  ctx.restore();
  if (line) {
    drawPath(ctx);
    ctx.lineWidth = lw;
    ctx.strokeStyle = line;
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';
    ctx.stroke();
  }
}

// 2-bone IK (screen space); bend = +1/-1 chooses the elbow/knee side
export function ik2(a, t, l1, l2, bend) {
  const d = sub(t, a);
  let L = len(d);
  L = clamp(L, Math.abs(l1 - l2) + 0.1, l1 + l2 - 0.1);
  const ang = Math.atan2(d[1], d[0]);
  const c = clamp((l1 * l1 + L * L - l2 * l2) / (2 * l1 * L), -1, 1);
  const A = Math.acos(c) * bend;
  const j = [a[0] + l1 * Math.cos(ang + A), a[1] + l1 * Math.sin(ang + A)];
  const e = [a[0] + L * Math.cos(ang), a[1] + L * Math.sin(ang)];
  return [j, e];
}
