// Effects animation, Promare-geometric: fire, ink, smears, speed lines, shockwaves, snow puffs, embers, cracks.
import { W, H, TAU, rng, lerp, clamp, fbm, noise1, hash, pathPoly, pathSmooth, taper, ease, add, mul, rot, norm, perp, sub } from './engine.js';
import { P } from './palette.js';

// ---------------------------------------------------------------- triangle fire (Promare)
// A flame tongue: a tall pointed teardrop with sharp side-shards; inner bands shrink toward the BASE
// (hot core low, pink edges licking highest).  Redrawn on twos via tq.
export function flame(ctx, x, y, w, h, tq, seed = 0, dir = -Math.PI / 2, glow = null, pal = null) {
  const cols = pal || [P.pink, P.orange, P.yellow, P.white];
  const a = dir + Math.PI / 2;
  const T = (q) => add([x, y], rot(q, a));
  const ph = Math.floor(tq * 12) * 0.37 + seed * 1.7;
  const lean = 0.18 * noise1(ph);
  cols.forEach((c, b) => {
    if (b === 3 && h < 60) return;
    const s = 1 - b * 0.22;             // band scale
    const hh = h * s * (1 - b * 0.06), ww = w * 0.5 * s;
    const base = h * 0.05 * b;          // inner bands sit lower
    const pts = [[-ww * 0.7, base]];
    const n = 5;
    for (let i = 1; i <= n; i++) {       // left edge up to the tip, with shards pointing out
      const u = i / (n + 1);
      const ex = -ww * (1 - u) * (1 - u * 0.3) + lean * hh * u * u;
      pts.push([ex - (i % 2) * ww * 0.35 * (1 - u), base - hh * u + (i % 2) * hh * 0.06]);
    }
    pts.push([lean * hh + ww * 0.1 * noise1(ph + b), base - hh]);
    for (let i = n; i >= 1; i--) {
      const u = i / (n + 1);
      const ex = ww * (1 - u) * (1 - u * 0.3) + lean * hh * u * u;
      pts.push([ex + ((i + 1) % 2) * ww * 0.3 * (1 - u), base - hh * u * 0.92 + ((i + 1) % 2) * hh * 0.05]);
    }
    pts.push([ww * 0.7, base]);
    pathPoly(ctx, pts.map(T)); ctx.fillStyle = c; ctx.fill();
  });
  if (glow) { glow.globalAlpha = 0.35; pathPoly(glow, [[-w * 0.4, 0], [0, -h], [w * 0.4, 0]].map(T)); glow.fillStyle = P.orange; glow.fill(); glow.globalAlpha = 1; }
}

// A curved blade of fire (for wings / trails): tapered crescent along a spine, banded, jagged trailing edge.
export function fireBlade(ctx, spine, w, tq, seed = 0, glow = null) {
  const cols = [P.pink, P.orange, P.yellow];
  const ph = Math.floor(tq * 12) * 0.5 + seed;
  cols.forEach((c, b) => {
    const s = 1 - b * 0.3;
    const L = [], R = [];
    const n = spine.length;
    for (let i = 0; i < n; i++) {
      const q = spine[i], d = norm(sub(spine[Math.min(n - 1, i + 1)], spine[Math.max(0, i - 1)])), pp = perp(d);
      const u = i / (n - 1);
      const ww = w * s * Math.sin(Math.min(1, u * 1.4 + 0.08) * Math.PI) ** 0.8;
      const jag = (i % 2) * ww * 0.45 * (0.7 + 0.3 * noise1(ph + i));
      L.push(add(q, mul(pp, ww * 0.35)));
      R.push(sub(q, mul(pp, ww * 0.65 + jag)));
    }
    // inner bands only cover the root 70% so tips stay pink
    const cut = b === 0 ? n : Math.floor(n * (0.8 - b * 0.15));
    pathPoly(ctx, L.slice(0, cut).concat(R.slice(0, cut).reverse())); ctx.fillStyle = c; ctx.fill();
  });
  if (glow) { glow.globalAlpha = 0.3; pathPoly(glow, taper(spine, w * 0.6, 1, w * 0.5)); glow.fillStyle = P.orange; glow.fill(); glow.globalAlpha = 1; }
}

// ---------------------------------------------------------------- ink burst (void death): blobs + spinning shards
export function inkBurst(ctx, x, y, age, seed = 0, scale = 1, glow = null, dir = [0, 0]) {
  if (age < 0) return;
  const r = rng(seed * 7919 + 13);
  const life = 0.9;
  const u = clamp(age / life);
  const e = ease.outx(u);
  // core splash
  if (u < 0.35) {
    const rr = 120 * scale * ease.out(u / 0.35);
    ctx.beginPath();
    for (let i = 0; i <= 14; i++) {
      const a = (i / 14) * TAU, k = i % 2 ? 1 : 0.55 + 0.2 * r();
      const q = [x + Math.cos(a) * rr * k, y + Math.sin(a) * rr * k];
      i ? ctx.lineTo(...q) : ctx.moveTo(...q);
    }
    ctx.closePath(); ctx.fillStyle = P.void; ctx.fill();
    if (glow) { glow.beginPath(); glow.arc(x, y, rr * 0.7, 0, TAU); glow.fillStyle = P.voidEye; glow.globalAlpha = 0.5 * (1 - u / 0.35); glow.fill(); glow.globalAlpha = 1; }
  }
  // shards
  const n = 22;
  for (let i = 0; i < n; i++) {
    const a = r() * TAU, sp = (220 + r() * 520) * scale;
    const px = x + (Math.cos(a) * sp + dir[0] * 300) * e, py = y + (Math.sin(a) * sp + dir[1] * 300) * e + 260 * u * u * scale;
    const sz = (10 + r() * 26) * scale * (1 - u * 0.7);
    const spin = r() * TAU + age * (6 + r() * 10);
    const tri = [[sz, 0], [-sz * 0.6, sz * 0.55], [-sz * 0.4, -sz * 0.6]].map((q) => add([px, py], rot(q, spin)));
    pathPoly(ctx, tri);
    ctx.fillStyle = i % 5 === 0 ? P.voidRim : P.void; ctx.fill();
    if (i % 3 === 0) { ctx.lineWidth = 2; ctx.strokeStyle = P.voidEye; ctx.globalAlpha = 1 - u; ctx.stroke(); ctx.globalAlpha = 1; }
  }
  // droplets
  for (let i = 0; i < 16; i++) {
    const a = r() * TAU, sp = (100 + r() * 700) * scale;
    const px = x + Math.cos(a) * sp * e, py = y + Math.sin(a) * sp * e + 400 * u * u * scale;
    ctx.beginPath(); ctx.arc(px, py, (4 + r() * 9) * scale * (1 - u), 0, TAU); ctx.fillStyle = P.void; ctx.fill();
  }
}

// ---------------------------------------------------------------- smear arc (blade trail)
// crescent between radius r0..r1 from a0 to a1 (radians), thick at the leading end
export function smearArc(ctx, cx, cy, r0, r1, a0, a1, glow = null, alpha = 1, cols = null) {
  const c = cols || ['#ffffff', P.yellow, P.orange];
  const n = 26, outer = [], inner = [];
  for (let i = 0; i <= n; i++) {
    const u = i / n, a = lerp(a0, a1, u);
    const th = ease.in2(u);                     // thin tail -> thick head
    const ro = lerp(r1 * 0.97, r1, th), ri = lerp(r1 * 0.97, r0, th);
    outer.push([cx + Math.cos(a) * ro, cy + Math.sin(a) * ro]);
    inner.push([cx + Math.cos(a) * ri, cy + Math.sin(a) * ri]);
  }
  const poly = outer.concat(inner.reverse());
  ctx.globalAlpha = alpha;
  pathSmooth(ctx, poly, true, 0.5); ctx.fillStyle = c[2]; ctx.fill();
  // inner white core (offset)
  const core = [];
  for (let i = 0; i <= n; i++) {
    const u = i / n, a = lerp(a0, a1, u), th = ease.in2(u);
    core.push([cx + Math.cos(a) * lerp(r1 * 0.985, r1 * 0.99, th), cy + Math.sin(a) * lerp(r1 * 0.985, r1 * 0.99, th)]);
  }
  for (let i = n; i >= 0; i--) {
    const u = i / n, a = lerp(a0, a1, u), th = ease.in2(u);
    core.push([cx + Math.cos(a) * lerp(r1 * 0.98, lerp(r0, r1, 0.45), th), cy + Math.sin(a) * lerp(r1 * 0.98, lerp(r0, r1, 0.45), th)]);
  }
  pathSmooth(ctx, core, true, 0.5); ctx.fillStyle = c[0]; ctx.fill();
  ctx.globalAlpha = 1;
  if (glow) { pathSmooth(glow, poly, true, 0.5); glow.fillStyle = P.orange; glow.globalAlpha = alpha * 0.8; glow.fill(); glow.globalAlpha = 1; }
}

// polyline smear (for trails that are not circular): pts = blade tip history (newest first)
export function smearTrail(ctx, pts, w, glow = null, alpha = 1) {
  if (pts.length < 3) return;
  const poly = taper(pts, w, 1, w * 0.7);
  ctx.globalAlpha = alpha;
  pathSmooth(ctx, poly, true, 0.5); ctx.fillStyle = P.orange; ctx.fill();
  const core = taper(pts, w * 0.55, 0.5, w * 0.35);
  pathSmooth(ctx, core, true, 0.5); ctx.fillStyle = '#ffffff'; ctx.fill();
  ctx.globalAlpha = 1;
  if (glow) { pathSmooth(glow, poly, true, 0.5); glow.fillStyle = P.orange; glow.fill(); }
}

// ---------------------------------------------------------------- speed lines
export function radialLines(ctx, cx, cy, tq, amt = 1, col = '#ffffff', seed = 0, inner = 0.32, alpha = 0.8) {
  const r = rng(Math.floor(tq * 12) * 31 + seed);
  ctx.save(); ctx.globalAlpha = alpha; ctx.fillStyle = col;
  const n = Math.floor(70 * amt);
  for (let i = 0; i < n; i++) {
    const a = r() * TAU, w = (0.004 + r() * 0.012);
    const r0 = (inner + r() * 0.2) * W, r1 = r0 + (0.4 + r()) * W;
    pathPoly(ctx, [[cx + Math.cos(a - w) * r1, cy + Math.sin(a - w) * r1], [cx + Math.cos(a) * r0, cy + Math.sin(a) * r0],
      [cx + Math.cos(a + w) * r1, cy + Math.sin(a + w) * r1]]);
    ctx.fill();
  }
  ctx.restore();
}
export function streakLines(ctx, tq, dir = [-1, 0], amt = 1, col = '#ffffff', seed = 0, alpha = 0.7) {
  const r = rng(Math.floor(tq * 12) * 17 + seed);
  ctx.save(); ctx.globalAlpha = alpha; ctx.fillStyle = col;
  const n = Math.floor(40 * amt), d = norm(dir), pp = perp(d);
  for (let i = 0; i < n; i++) {
    const c = [r() * W, r() * H], L = 150 + r() * 600, th = 1 + r() * 4;
    pathPoly(ctx, [add(c, mul(pp, th)), add(c, mul(d, L)), sub(c, mul(pp, th))]);
    ctx.fill();
  }
  ctx.restore();
}

// ---------------------------------------------------------------- shockwave ring + snow puffs (flat cel smoke)
export function ring(ctx, x, y, age, rmax, col = '#ffffff', flat = 0.3, width = 30, glow = null) {
  if (age < 0 || age > 1) return;
  const r = rmax * ease.outx(age);
  ctx.save(); ctx.translate(x, y); ctx.scale(1, flat);
  ctx.beginPath(); ctx.arc(0, 0, r, 0, TAU);
  ctx.lineWidth = width * (1 - age) + 1; ctx.strokeStyle = col; ctx.globalAlpha = 1 - age * 0.6; ctx.stroke();
  ctx.restore();
  if (glow) { glow.save(); glow.translate(x, y); glow.scale(1, flat); glow.beginPath(); glow.arc(0, 0, r, 0, TAU); glow.lineWidth = width * 2; glow.strokeStyle = col; glow.globalAlpha = 0.6 * (1 - age); glow.stroke(); glow.restore(); }
}
// anime smoke/snow puffs: overlapping circles with a hard shadow band, expanding & thinning
export function puffs(ctx, x, y, age, seed = 0, scale0 = 1, col = P.snow, shade = P.snowS, dir = [0, -1], spread = 1) {
  if (age < 0 || age > 1.2) return;
  const scale = Math.min(scale0, 1.3) * 0.75;
  const r = rng(seed * 131 + 7);
  const n = 12;
  for (let i = 0; i < n; i++) {
    const a = Math.atan2(dir[1], dir[0]) + (r() - 0.5) * 2.2 * spread;
    const sp = (60 + r() * 260) * scale;
    const e = ease.outx(clamp(age / 1.0));
    const px = x + Math.cos(a) * sp * e, py = y + Math.sin(a) * sp * e;
    const rr = (26 + r() * 44) * scale * (0.4 + 0.8 * e) * (1 - clamp((age - 0.6) / 0.6));
    if (rr <= 0) continue;
    ctx.beginPath(); ctx.arc(px, py, rr, 0, TAU); ctx.fillStyle = shade; ctx.fill();
    ctx.beginPath(); ctx.arc(px - rr * 0.18, py - rr * 0.22, rr * 0.88, 0, TAU); ctx.fillStyle = col; ctx.fill();
  }
}

// ---------------------------------------------------------------- muzzle blast (geometric star + ring)
export function muzzle(ctx, x, y, dir, age, scale = 1, glow = null) {
  if (age < 0 || age > 0.25) return;
  const u = age / 0.25, a = Math.atan2(dir[1], dir[0]);
  const L = (180 + 120 * (1 - u)) * scale, Wd = 70 * scale * (1 - u);
  const cols = [P.pink, P.orange, P.yellow, '#ffffff'];
  cols.forEach((c, k) => {
    const s = 1 - k * 0.22;
    const pts = [[0, 0], [L * 0.3 * s, Wd * s], [L * s, 0], [L * 0.3 * s, -Wd * s]].map((q) => add([x, y], rot(q, a)));
    const side = [[L * 0.12 * s, 0], [L * 0.2 * s, Wd * 1.6 * s], [L * 0.3 * s, 0], [L * 0.2 * s, -Wd * 1.6 * s]].map((q) => add([x, y], rot(q, a)));
    pathPoly(ctx, pts); ctx.fillStyle = c; ctx.fill();
    pathPoly(ctx, side); ctx.fill();
  });
  if (glow) { glow.beginPath(); glow.arc(x, y, L * 0.8, 0, TAU); glow.fillStyle = P.orange; glow.globalAlpha = 1 - u; glow.fill(); glow.globalAlpha = 1; }
}

// ---------------------------------------------------------------- embers & snow (analytic particles)
export function embers(ctx, t, { n = 60, seed = 1, rise = 1, region = [0, 0, W, H], size = 1, glow = null, alpha = 1, drift = 20 } = {}) {
  const r = rng(seed);
  for (let i = 0; i < n; i++) {
    const x0 = region[0] + r() * region[2], y0 = region[1] + r() * region[3];
    const sp = (30 + r() * 80) * rise, ph = r() * TAU, s = (2 + r() * 5) * size;
    const x = x0 + Math.sin(t * 1.3 + ph) * drift + t * 10;
    const y = ((y0 - sp * t - region[1]) % region[3] + region[3]) % region[3] + region[1];
    const fl = 0.5 + 0.5 * Math.sin(t * (4 + r() * 6) + ph);
    const rotA = t * (2 + r() * 3) + ph;
    const q = [[s, 0], [0, s * 0.6], [-s, 0], [0, -s * 0.6]].map((p) => add([x, y], rot(p, rotA)));
    ctx.globalAlpha = alpha * (0.5 + 0.5 * fl);
    pathPoly(ctx, q); ctx.fillStyle = fl > 0.6 ? P.yellow : P.orange; ctx.fill();
    if (glow) { glow.globalAlpha = alpha * fl; glow.beginPath(); glow.arc(x, y, s * 2.4, 0, TAU); glow.fillStyle = P.orange; glow.fill(); }
  }
  ctx.globalAlpha = 1; if (glow) glow.globalAlpha = 1;
}
export function snowfall(ctx, tw, { n = 120, seed = 9, speed = 60, size = 1, alpha = 0.9, wind = -20, col = '#ffffff' } = {}) {
  const r = rng(seed);
  ctx.fillStyle = col;
  for (let i = 0; i < n; i++) {
    const x0 = r() * W, y0 = r() * H, sp = speed * (0.6 + r() * 0.8), s = (1.5 + r() * 3.5) * size, ph = r() * TAU;
    const x = ((x0 + wind * tw + Math.sin(tw * 0.9 + ph) * 18) % W + W) % W;
    const y = ((y0 + sp * tw) % H + H) % H;
    ctx.globalAlpha = alpha * (0.5 + 0.5 * r());
    ctx.beginPath(); ctx.arc(x, y, s, 0, TAU); ctx.fill();
  }
  ctx.globalAlpha = 1;
}

// ---------------------------------------------------------------- cracks (lightning polylines racing outward)
export function cracks(ctx, x, y, u, seed = 0, len = 900, glow = null, dirA = Math.PI / 2, spreadA = 1.2) {
  const r = rng(seed);
  const branches = 7;
  for (let b = 0; b < branches; b++) {
    let a = dirA + (r() - 0.5) * spreadA;
    let p = [x, y];
    const pts = [p];
    const L = len * (0.5 + r() * 0.6) * ease.out(clamp(u));
    const segs = 12;
    for (let i = 0; i < segs; i++) {
      a += (r() - 0.5) * 0.9;
      p = [p[0] + Math.cos(a) * L / segs, p[1] + Math.sin(a) * L / segs * 0.45];
      pts.push(p);
    }
    const poly = taper(pts, 7, 0.5, 4);
    pathPoly(ctx, poly); ctx.fillStyle = P.void; ctx.fill();
    if (glow) { glow.beginPath(); pts.forEach((q, i) => (i ? glow.lineTo(...q) : glow.moveTo(...q))); glow.lineWidth = 6; glow.strokeStyle = P.voidEye; glow.stroke(); }
    ctx.beginPath(); pts.forEach((q, i) => (i ? ctx.lineTo(...q) : ctx.moveTo(...q))); ctx.lineWidth = 1.5; ctx.strokeStyle = P.voidEye; ctx.stroke();
  }
}

// ---------------------------------------------------------------- impact frame (post): inverted, crushed, red kept
export function impactFrame(ctx, amount = 1) {
  const img = ctx.getImageData(0, 0, W, H), d = img.data;
  for (let i = 0; i < d.length; i += 4) {
    const r = d[i], g = d[i + 1], b = d[i + 2];
    const l = 0.3 * r + 0.59 * g + 0.11 * b;
    const warm = r - b > 60 && r > 120;
    let v = l > 110 ? 12 : 245;
    let o = warm ? [235, 30, 25] : [v, v, v];
    d[i] = lerp(r, o[0], amount); d[i + 1] = lerp(g, o[1], amount); d[i + 2] = lerp(b, o[2], amount);
  }
  ctx.putImageData(img, 0, 0);
}
