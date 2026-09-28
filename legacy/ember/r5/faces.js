// Anime face decals, 1024x1024, alpha. Mapped by front projection onto the head: u = x across the face, v = height.
// Layout (px): eye centres at (330,560) and (694,560); nose ~ (512,690); mouth ~ (512,790).
import { Canvas } from 'skia-canvas';
import fs from 'fs';
const S = 1024, LINE = '#2a1422', IRIS0 = '#7a1e08', IRIS1 = '#e0520e', IRIS2 = '#ffa531', IRIS3 = '#ffe08a';
function eye(x, cx, cy, side, e) {
  // side: -1 = her right (screen left), +1 = her left.  e: {open, look:[dx,dy], brow, fire, lid}
  const o = e.open, w = 150, h = 118 * o;
  x.save(); x.translate(cx, cy); x.scale(-side, 1);          // draw as the left-screen eye, mirror for the other
  if (o > 0.08) {
    // sclera clip
    x.beginPath(); x.moveTo(-w * 0.62, 6); x.bezierCurveTo(-w * 0.45, -h * 0.95, w * 0.35, -h * 1.05, w * 0.62, -h * 0.35 + 10);
    x.bezierCurveTo(w * 0.5, h * 0.35, -w * 0.2, h * 0.45, -w * 0.62, 6); x.closePath();
    x.save(); x.clip();
    x.fillStyle = '#fbf6fb'; x.fillRect(-w, -h * 1.5, w * 2, h * 3);
    x.fillStyle = '#c9bde0'; x.fillRect(-w, -h * 1.5, w * 2, h * 0.55 + h * 0.15);   // lid shadow band
    const ix = -e.look[0] * 26 * side, iy = e.look[1] * 14 - 6, ir = 64;
    const g = x.createLinearGradient(0, iy - ir, 0, iy + ir);
    const pal = e.fire ? ['#8a0a3a', '#ff2e88', '#ff9a2a', '#fff2a0'] : [IRIS0, IRIS1, IRIS2, IRIS3];
    g.addColorStop(0, pal[0]); g.addColorStop(0.45, pal[1]); g.addColorStop(0.8, pal[2]); g.addColorStop(1, pal[3]);
    x.beginPath(); x.ellipse(ix, iy, ir * 0.82, ir, 0, 0, Math.PI * 2); x.fillStyle = g; x.fill();
    x.lineWidth = 5; x.strokeStyle = pal[0]; x.stroke();
    // pupil
    x.beginPath(); x.ellipse(ix, iy - 4, ir * 0.3 * (e.fire ? 0.6 : 1), ir * 0.52, 0, 0, Math.PI * 2); x.fillStyle = e.fire ? '#4a0418' : '#3a0a04'; x.fill();
    // iris shadow under the lid
    x.fillStyle = 'rgba(60,10,40,0.35)'; x.beginPath(); x.ellipse(ix, iy - ir * 0.75, ir * 0.9, ir * 0.45, 0, 0, Math.PI * 2); x.fill();
    // highlights
    x.fillStyle = '#ffffff';
    x.beginPath(); x.ellipse(ix - 18, iy - 26, 17, 12, -0.5, 0, Math.PI * 2); x.fill();
    x.beginPath(); x.arc(ix + 20, iy + 26, 7, 0, Math.PI * 2); x.fill();
    x.restore();
  }
  // upper lash line (thick, tapered, with an outer flick); lowers into a closed curve as open -> 0
  const lid = (t) => { const a = -w * 0.66 + t * w * 1.34; const yy = o > 0.08 ? (-Math.sin(t * Math.PI) * h * 0.95 + t * (-h * 0.35 + 10) + (1 - t) * 6) : (e.smile ? -Math.sin(t * Math.PI) * 22 + 10 : Math.sin(t * Math.PI) * 14 + 8); return [a, yy]; };
  x.beginPath();
  for (let i = 0; i <= 30; i++) { const [a, yy] = lid(i / 30); i ? x.lineTo(a, yy - (5 + 12 * Math.sin(i / 30 * Math.PI * 0.9 + 0.2))) : x.moveTo(a, yy); }
  for (let i = 30; i >= 0; i--) { const [a, yy] = lid(i / 30); x.lineTo(a, yy + 3); }
  x.closePath(); x.fillStyle = LINE; x.fill();
  // outer-corner flick + lashes
  const [ex, ey] = lid(1);
  x.beginPath(); x.moveTo(ex - 30, ey - 14); x.quadraticCurveTo(ex + 20, ey - 26, ex + 44, ey - 34 * (0.4 + 0.6 * Math.max(o, 0.3))); x.lineTo(ex + 6, ey + 2); x.closePath(); x.fill();
  if (o > 0.08) {  // lower lash hint + inner corner
    x.lineWidth = 5; x.strokeStyle = LINE; x.lineCap = 'round';
    x.beginPath(); x.moveTo(w * 0.1, h * 0.36); x.quadraticCurveTo(w * 0.4, h * 0.22, w * 0.58, -h * 0.15 + 12); x.stroke();
  }
  // brow
  const b = e.brow;  // +1 angry (inner end down), -1 sad/soft
  x.lineWidth = 13; x.lineCap = 'round'; x.strokeStyle = '#7d7a9c';
  x.beginPath(); x.moveTo(-w * 0.55, -150 - 10 * b * -1 + (e.brow < 0 ? -8 : 0)); x.quadraticCurveTo(0, -178 + (b > 0 ? 6 : 0), w * 0.6, -150 + 18 * b); x.stroke();
  x.restore();
}
function mouth(x, m) {
  x.save(); x.translate(512, 800);
  x.lineCap = 'round'; x.strokeStyle = LINE; x.fillStyle = '#6a1a2c';
  if (m.shout) {
    x.beginPath(); x.moveTo(-70, -10); x.quadraticCurveTo(0, -30, 70, -10); x.quadraticCurveTo(46, 90, 0, 96); x.quadraticCurveTo(-46, 90, -70, -10); x.closePath(); x.fill();
    x.lineWidth = 7; x.stroke();
    x.fillStyle = '#fff'; x.beginPath(); x.moveTo(-58, -8); x.quadraticCurveTo(0, -24, 58, -8); x.lineTo(50, 10); x.quadraticCurveTo(0, -4, -50, 10); x.fill();
    x.fillStyle = '#c0485a'; x.beginPath(); x.ellipse(0, 70, 34, 16, 0, 0, Math.PI * 2); x.fill();
  } else if (m.open) {
    x.beginPath(); x.moveTo(-34, 0); x.quadraticCurveTo(0, -8, 34, 0); x.quadraticCurveTo(0, 40 * m.open, -34, 0); x.closePath(); x.fill(); x.lineWidth = 6; x.stroke();
  } else {
    x.lineWidth = 7; x.beginPath(); x.moveTo(-30, 0); x.quadraticCurveTo(0, m.smile ? 14 : (m.frown ? -6 : 3), 30, m.smile ? -6 : 0); x.stroke();
  }
  x.restore();
}
function face(name, e) {
  const c = new Canvas(S, S), x = c.getContext('2d');
  // blush / cheek shading (soft) and a nose tick
  if (e.blush) { x.fillStyle = 'rgba(255,120,130,0.25)'; for (const cx of [300, 724]) { x.beginPath(); x.ellipse(cx, 700, 70, 26, 0, 0, Math.PI * 2); x.fill(); } }
  x.strokeStyle = '#b07a86'; x.lineWidth = 6; x.lineCap = 'round';
  x.beginPath(); x.moveTo(520, 682); x.lineTo(508, 702); x.stroke();
  eye(x, 330, 560, 1, e); eye(x, 694, 560, -1, e);
  mouth(x, e.mouth || {});
  fs.writeFileSync(`tex/face_${name}.png`, c.toBufferSync ? c.toBufferSync('png') : null);
  return c;
}
const EX = {
  neutral: { open: 1, look: [0, 0], brow: 0.2, mouth: {} },
  fierce: { open: 0.82, look: [0, 0], brow: 1, mouth: { frown: 1 } },
  shout: { open: 0.95, look: [0, 0], brow: 1, mouth: { shout: 1 } },
  closed: { open: 0, look: [0, 0], brow: -0.2, mouth: {} },
  half: { open: 0.45, look: [0, 0.3], brow: -0.3, mouth: {} },
  pain: { open: 0.3, look: [0, 0.4], brow: -1, mouth: { open: 0.5 } },
  fire: { open: 1, look: [0, 0], brow: 1, fire: 1, mouth: { frown: 1 } },
  roar: { open: 0.9, look: [0, -0.3], brow: 1, fire: 1, mouth: { shout: 1 } },
  smile: { open: 0, smile: 1, look: [0, 0], brow: -0.5, blush: 1, mouth: { smile: 1 } },
  lookL: { open: 0.95, look: [-1, 0], brow: 0.5, mouth: {} },
  up: { open: 1, look: [0, -1], brow: -0.2, mouth: { open: 0.3 } },
};
const sheet = new Canvas(S * 4, S * 3), sx = sheet.getContext('2d');
sx.fillStyle = '#f2d8d0'; sx.fillRect(0, 0, S * 4, S * 3);
Object.entries(EX).forEach(([k, e], i) => {
  const c = face(k, e);
  sx.drawImage(c, (i % 4) * S, Math.floor(i / 4) * S);
});
for (const k of Object.keys(EX)) { const c = face(k, EX[k]); fs.writeFileSync(`tex/face_${k}.png`, await c.toBuffer('png')); }
fs.writeFileSync('tex/_faces.jpg', await sheet.toBuffer('jpg', { quality: 0.8 }));
console.log('faces ok');
