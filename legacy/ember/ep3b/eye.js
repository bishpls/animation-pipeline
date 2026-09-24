// Extreme close-up anime eye, drawn from scratch.  open: 0 closed .. 1 open.  look: [-1..1, -1..1].
import { TAU, lerp, clamp, add, mul, rot, pathPoly, pathSmooth, taper, noise1, rng } from './engine.js';
import { P } from './palette.js';
import { flame } from './fx.js';

export function drawEye(ctx, glow, cx, cy, k, { open = 1, look = [0, 0], pupil = 1, fire = 0, t = 0, snow = 1, hairShift = 0 } = {}) {
  const X = (x, y) => [cx + x * k, cy + y * k];
  // --- skin plane with one hard shadow band (from brow)
  ctx.fillStyle = P.skin; ctx.fillRect(cx - 2 * k, cy - 1.2 * k, 4 * k, 2.4 * k);
  pathSmooth(ctx, [X(-2, -1.2), X(2, -1.2), X(2, -0.52), X(0.6, -0.42), X(-0.4, -0.5), X(-2, -0.62)], true, 0.6);
  ctx.fillStyle = P.skinS; ctx.fill();
  // --- lid curves (open shape = almond)
  const upO = (u) => [lerp(-0.95, 0.95, u), -0.38 * Math.sin(Math.PI * Math.pow(u, 0.85)) - 0.02];
  const lo = (u) => [lerp(-0.95, 0.95, u), 0.2 * Math.sin(Math.PI * u) + 0.05 * u];
  const upC = (u) => { const q = lo(u); return [q[0], q[1] - 0.012]; };
  const oo = clamp(open);
  const up = (u) => { const a = upO(u), b = upC(u); return [a[0], lerp(b[1], a[1], oo)]; };
  const N = 28;
  const upper = [], lower = [];
  for (let i = 0; i <= N; i++) { upper.push(X(...up(i / N))); lower.push(X(...lo(i / N))); }
  const socket = upper.concat([...lower].reverse());
  if (oo > 0.02) {
    ctx.save();
    pathSmooth(ctx, socket, true, 0.5); ctx.clip();
    // sclera + lid shadow
    ctx.fillStyle = '#f4f3ff'; ctx.fillRect(cx - k, cy - k, 2 * k, 2 * k);
    pathSmooth(ctx, upper.concat([X(0.95, -0.05), X(-0.95, 0.02)]), true, 0.5); ctx.fillStyle = '#b9b4e6'; ctx.fill();
    // iris
    const ic = X(0.05 + look[0] * 0.35, -0.06 + look[1] * 0.12);
    const ir = 0.36 * k;
    const ipal = fire > 0.5 ? [P.pink, P.orange, P.yellow, '#fff'] : [P.irisD, P.iris, P.yellow, '#fff'];
    ctx.save(); ctx.translate(...ic); ctx.scale(0.86, 1);
    ctx.beginPath(); ctx.arc(0, 0, ir, 0, TAU); ctx.fillStyle = ipal[0]; ctx.fill();
    ctx.beginPath(); ctx.arc(0, ir * 0.12, ir * 0.86, 0, TAU); ctx.fillStyle = ipal[1]; ctx.fill();
    // lower bright crescent
    ctx.beginPath(); ctx.arc(0, ir * 0.18, ir * 0.78, 0.15 * Math.PI, 0.85 * Math.PI); ctx.arc(0, ir * 0.02, ir * 0.62, 0.8 * Math.PI, 0.2 * Math.PI, true);
    ctx.fillStyle = ipal[2]; ctx.fill();
    // striations
    ctx.strokeStyle = ipal[0]; ctx.lineWidth = Math.max(1, k * 0.006);
    for (let i = 0; i < 24; i++) {
      const a = (i / 24) * TAU, r0 = ir * 0.3, r1 = ir * (0.7 + 0.15 * Math.sin(i * 3.7));
      ctx.beginPath(); ctx.moveTo(Math.cos(a) * r0, Math.sin(a) * r0); ctx.lineTo(Math.cos(a) * r1, Math.sin(a) * r1); ctx.stroke();
    }
    if (fire > 0) {   // fire inside the iris
      for (let i = 0; i < 5; i++) flame(ctx, (i - 2) * ir * 0.3, ir * 0.55, ir * 0.35, ir * (0.7 + 0.3 * Math.sin(i)), t * fire, i + 3);
    }
    // pupil: vertical ellipse, constricts with `pupil`
    ctx.save(); ctx.scale(0.55 * pupil + 0.1, 1);
    ctx.beginPath(); ctx.arc(0, -ir * 0.02, ir * 0.36, 0, TAU); ctx.fillStyle = fire > 0.5 ? '#3a0418' : P.pupil; ctx.fill();
    ctx.restore();
    // iris ring
    ctx.beginPath(); ctx.arc(0, 0, ir, 0, TAU); ctx.lineWidth = k * 0.018; ctx.strokeStyle = P.line; ctx.stroke();
    ctx.restore();
    // lid shadow over iris top
    pathSmooth(ctx, upper.concat([X(0.95, -0.15), X(-0.95, -0.1)]), true, 0.5); ctx.fillStyle = 'rgba(60,20,70,0.35)'; ctx.fill();
    // highlights
    const hl = add(ic, [-0.14 * k, -0.16 * k]);
    ctx.save(); ctx.translate(...hl); ctx.rotate(-0.5);
    ctx.beginPath(); ctx.ellipse(0, 0, 0.1 * k, 0.065 * k, 0, 0, TAU); ctx.fillStyle = '#ffffff'; ctx.fill(); ctx.restore();
    ctx.beginPath(); ctx.arc(ic[0] + 0.13 * k, ic[1] + 0.12 * k, 0.03 * k, 0, TAU); ctx.fill();
    if (glow && fire > 0) { glow.beginPath(); glow.arc(...ic, ir * 1.1, 0, TAU); glow.fillStyle = P.orange; glow.globalAlpha = fire; glow.fill(); glow.globalAlpha = 1; }
    ctx.restore();
  }
  // --- upper lash line: thick tapered stroke + outer-corner flick lashes
  const lash = [];
  for (let i = 0; i <= N; i += 2) lash.push(upper[i]);
  pathSmooth(ctx, taper(lash, 0.02 * k, 0.07 * k, 0.075 * k), true, 0.6); ctx.fillStyle = P.line; ctx.fill();
  const outer = upper[N];
  for (let j = 0; j < 3; j++) {
    const base = upper[N - 2 - j * 2];
    const tip = add(base, rot([0.2 * k, -0.06 * k * (1 + j * 0.3) * (0.3 + 0.7 * oo)], -0.3 - j * 0.25));
    pathSmooth(ctx, taper([base, mix(base, tip, 0.5), tip], 0.035 * k, 0.003 * k, 0.025 * k), true, 0.6); ctx.fill();
  }
  // lower lash (thin, partial)
  const ll = lower.slice(Math.floor(N * 0.45));
  pathSmooth(ctx, taper(ll, 0.004 * k, 0.018 * k, 0.012 * k), true, 0.6); ctx.fillStyle = P.line; ctx.fill();
  // crease line above
  const crease = [];
  for (let i = 4; i <= N - 2; i += 3) { const q = upO(i / N); crease.push(X(q[0] * 1.02, q[1] - 0.14 - 0.04 * Math.sin(Math.PI * i / N))); }
  pathSmooth(ctx, taper(crease, 0.003 * k, 0.012 * k, 0.014 * k), true, 0.6); ctx.fillStyle = P.skinS; ctx.fill();
  // brow (half off-frame)
  pathSmooth(ctx, taper([X(-1.3, -0.95), X(-0.2, -1.05), X(0.9, -0.92)], 0.08 * k, 0.03 * k, 0.1 * k), true, 0.6);
  ctx.fillStyle = P.hairS; ctx.fill();
  // snow crystals caught on the lashes
  if (snow > 0) {
    const r = rng(5);
    for (let i = 0; i < 6; i++) {
      const q = upper[Math.floor(r() * N)];
      const s = (0.018 + r() * 0.02) * k;
      ctx.save(); ctx.translate(q[0], q[1] - s * 0.5); ctx.rotate(r() * TAU);
      ctx.strokeStyle = '#ffffff'; ctx.lineWidth = Math.max(1.2, s * 0.25);
      for (let a = 0; a < 3; a++) { ctx.rotate(Math.PI / 3); ctx.beginPath(); ctx.moveTo(-s, 0); ctx.lineTo(s, 0); ctx.stroke(); }
      ctx.restore();
    }
  }
  // hair clumps falling across the frame: broad flat locks with a shadow side, swaying
  const locks = [[-1.9, -1.5, -0.7, -0.35, 0.34, P.hair, P.hairS], [-1.35, -1.5, -0.55, 0.15, 0.14, P.streak, P.streakS],
    [1.25, -1.5, 1.75, 0.35, 0.4, P.hair, P.hairS]];
  locks.forEach(([x0, y0, x1, y1, w, c, cs], i) => {
    const sw = hairShift * (0.04 + i * 0.03) + 0.015 * noise1(t * 1.3 + i);
    const pts = [X(x0, y0), X(lerp(x0, x1, 0.45) + sw, lerp(y0, y1, 0.5)), X(lerp(x0, x1, 0.8) + sw * 1.6, lerp(y0, y1, 0.85)), X(x1 + sw * 2, y1)];
    const poly = taper(pts, w * k, 0.004 * k, w * 0.75 * k);
    pathSmooth(ctx, poly, true, 0.8); ctx.fillStyle = cs; ctx.fill();
    ctx.save(); pathSmooth(ctx, poly, true, 0.8); ctx.clip(); ctx.translate(-0.05 * k, -0.02 * k);
    pathSmooth(ctx, taper(pts, w * k * 0.7, 0.002 * k, w * 0.5 * k), true, 0.8); ctx.fillStyle = c; ctx.fill(); ctx.restore();
    pathSmooth(ctx, poly, true, 0.8); ctx.lineWidth = k * 0.009; ctx.strokeStyle = P.line; ctx.stroke();
  });
}
function mix(a, b, u) { return [lerp(a[0], b[0], u), lerp(a[1], b[1], u)]; }
