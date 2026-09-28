// EMBER · Round 5 — 2D compositor over the Blender cel renders.
// Reads r5/frames/<shot>/f####.png + meta.json (projected points, blade sweep, events) and layers the drawn FX:
// blade smears from the true 3D sweep, impact frames, spark/ink sheets, bloom from emissives, snow, grade, shake.
import { Canvas, loadImage } from 'skia-canvas';
import fs from 'fs';
import path from 'path';
import { X, G, W, H, clearFrame, post, embers, snow, sheet, fxPlay, speedLines, shakeFrom, rng, fbm, clamp, lerp, ease }
  from '../../ep4/film/lib.js';
import { SHOTS, loadShotAssets } from './shots.mjs';

const R5 = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
export const FPS = 24, BEAT = 0.4;
export const bfr = (b) => Math.round(b * BEAT * FPS);
const small = new Canvas(480, 270), sx = small.getContext('2d');

export const FX = {};
export async function loadFX() {
  FX.ink = await sheet('fx/FX_ink.png'); FX.slash = await sheet('fx/FX_slash.png'); FX.fire = await sheet('fx/FX_fire.png');
  FX.snow = await sheet('fx/FX_snow.png');
  await loadShotAssets();
}

export function loadShot(name) {
  const dir = path.join(R5, 'frames', name);
  const m = JSON.parse(fs.readFileSync(path.join(dir, 'meta.json'), 'utf8'));
  m.dir = dir;
  m.at = (f) => m.meta[String(f)] || {};
  m.hits = m.events.filter((e) => e[1] === 'hit').map((e) => bfr(e[0]));
  return m;
}

// base cel render, scaled to 1080p, plus a bloom source: threshold on emissive-bright / saturated pixels
export async function base(shot, f) {
  const im = await loadImage(path.join(shot.dir, `f${String(f).padStart(4, '0')}.png`));
  X.drawImage(im, 0, 0, W, H);
  sx.drawImage(im, 0, 0, 480, 270);
  const d = sx.getImageData(0, 0, 480, 270), p = d.data;
  for (let i = 0; i < p.length; i += 4) {
    const r = p[i], g = p[i + 1], b = p[i + 2], mx = Math.max(r, g, b), mn = Math.min(r, g, b);
    const k = mx > 235 && mx - mn > 60 ? 1 : (mx > 200 && mx - mn > 120 ? 0.7 : 0);   // emissive eyes / fire / clasp
    p[i] *= k; p[i + 1] *= k; p[i + 2] *= k; p[i + 3] = 255 * k;
  }
  sx.putImageData(d, 0, 0);
  G.save(); G.setTransform(1, 0, 0, 1, 0, 0); G.drawImage(small, 0, 0, W, H); G.restore();
}

// blade smear from the sampled 3D sweep: a crescent ribbon between the blade's mid-line and its tip path
export function smear(tr, { alpha = 1, core = '#ffffff', glow = '#9fd8ff', inner = 0.45, width = 1 } = {}) {
  if (!tr || tr.length < 2) return;
  const n = tr.length - 1;
  const outer = tr.map((q) => [q[2], q[3]]);
  const inn = tr.map((q, i) => { const u = i / n, k = inner + (1 - inner) * (1 - width * (0.25 + 0.75 * u)); return [lerp(q[0], q[2], k), lerp(q[1], q[3], k)]; });
  const poly = [...outer, ...inn.reverse()];
  const draw = (ctx, col, a) => {
    ctx.save(); ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalAlpha = a; ctx.fillStyle = col;
    ctx.beginPath(); poly.forEach((q, i) => (i ? ctx.lineTo(...q) : ctx.moveTo(...q))); ctx.closePath(); ctx.fill(); ctx.restore();
  };
  // tapered: the older half of the sweep fades (gradient along the arc approximated by 3 nested passes)
  draw(X, glow, 0.35 * alpha);
  const half = Math.floor(n / 2);
  const sub = tr.slice(half);
  if (sub.length > 1) {
    const o2 = sub.map((q) => [q[2], q[3]]), i2 = sub.map((q) => [lerp(q[0], q[2], 0.72), lerp(q[1], q[3], 0.72)]).reverse();
    X.save(); X.setTransform(1, 0, 0, 1, 0, 0); X.globalAlpha = 0.95 * alpha; X.fillStyle = core;
    X.beginPath(); [...o2, ...i2].forEach((q, i) => (i ? X.lineTo(...q) : X.moveTo(...q))); X.closePath(); X.fill(); X.restore();
  }
  draw(G, glow, 0.8 * alpha);
  // speed hairlines trailing the tip
  X.save(); X.setTransform(1, 0, 0, 1, 0, 0); X.strokeStyle = core; X.lineCap = 'round';
  for (let k = 0; k < 4; k++) {
    X.globalAlpha = alpha * (0.5 - k * 0.1); X.lineWidth = 3 - k * 0.6; X.beginPath();
    tr.forEach((q, i) => { const u = 0.08 + k * 0.1; const x = lerp(q[2], q[0], u), y = lerp(q[3], q[1], u); i ? X.lineTo(x, y) : X.moveTo(x, y); });
    X.stroke();
  }
  X.restore();
}

export async function render(name, frames, out) {
  const shot = loadShot(name);
  const spec = SHOTS[name];
  await loadFX();
  fs.mkdirSync(out, { recursive: true });
  const fl = frames || Array.from({ length: shot.f1 - shot.f0 }, (_, i) => shot.f0 + i);
  const t0 = Date.now();
  for (const f of fl) {
    clearFrame();
    await base(shot, f);
    const ctx = { f, t: f / FPS, b: f / FPS / BEAT, m: shot.at(f), shot, prev: (k) => shot.at(f - k) };
    const P = spec(ctx) || {};
    post({ vign: 0.5, grain: 0.035, bloom: 1, fi: f, ...P });
    await main_write(path.join(out, `f${String(f).padStart(4, '0')}.png`));
  }
  console.log(`[comp ${name}] ${fl.length} frames in ${((Date.now() - t0) / 1000).toFixed(1)}s`);
}

import { main } from '../../ep4/film/lib.js';
async function main_write(p) { await main.toFile(p); }

if (process.argv[1] && process.argv[1].endsWith('comp.mjs')) {
  const name = process.argv[2];
  let frames = null;
  const fa = process.argv.find((a) => a.startsWith('--frames='));
  if (fa) {
    const v = fa.slice(9);
    frames = v.includes('-') ? (() => { const [a, b] = v.split('-').map(Number); return Array.from({ length: b - a + 1 }, (_, i) => a + i); })() : v.split(',').map(Number);
  }
  const avail = fs.readdirSync(path.join(R5, 'frames', name)).filter((x) => x.endsWith('.png')).map((x) => +x.slice(1, 5));
  if (!frames) frames = avail.sort((a, b) => a - b);
  else frames = frames.filter((f) => avail.includes(f));
  await render(name, frames, path.join(R5, 'out', 'comp', name));
}
