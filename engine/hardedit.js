// engine/hardedit.js: the hard-edit grammar for plain Canvas2D films. A short-form "edit" (a hyperpop or velocity edit) lives
// on zoom punches, flash and impact frames, chromatic splits, grades and grain, all as pure functions of t. (Promoted from
// SO BACK.)
//
//   const b = scene(() => { X.save(); zoomAt(cx, cy, punch(t, hitT, .16)); drawPlate(K, pt); X.restore(); });
//   present(b, 'saturate(1.2)', 14 * Math.exp(-(t - hitT) * 8))    // grade + an RGB split that decays after the hit
//   present(b, NEG)                                                 // the impact frame: ONE frame, on big hits only
//   grain(t, .2); vignette(.5)
//
// What SO BACK learned (docs/CRAFT.md section 15):
// - Leave a hit's contact frame clean, so the source's own spark reads, then one negative frame. Full-frame white flashes
//   on the hit wash out the very image the edit is about.
// - A split reads as an accent, not a style: small and decaying. HARDEDIT.split scales every split in a film.
// - Draw a shot into scene() and grade it once with present(); keep type and overlays outside it.
const HARDEDIT = { split: 1 };

// offscreen canvases by name, reused per frame (cleared unless clear = false)
const BUF = {};
function buf(name, w = W, h = H, clear = true) {
  let b = BUF[name];
  if (!b) { const c = document.createElement('canvas'); c.width = w; c.height = h; b = BUF[name] = { c, x: c.getContext('2d') }; }
  if (b.c.width !== w || b.c.height !== h) { b.c.width = w; b.c.height = h; }
  b.x.setTransform(1, 0, 0, 1, 0, 0); b.x.globalAlpha = 1; b.x.globalCompositeOperation = 'source-over'; b.x.filter = 'none';
  if (clear) b.x.clearRect(0, 0, b.c.width, b.c.height);
  return b;
}
// draw fn with X pointed at the 'scene' buffer; returns the buffer (grade it with present)
function scene(fn) { const b = buf('scene'), X0 = X; X = b.x; try { fn(); } finally { X = X0; } return b; }
// scale about (cx, cy), then offset (a shake)
function zoomAt(cx, cy, z, dx = 0, dy = 0) { X.translate(cx + dx, cy + dy); X.scale(z, z); X.translate(-cx, -cy); }

// a zoom punch: 1 + amt at t0, easing back over d seconds
const punch = (t, t0, amt = .12, d = .22) => (t < t0 || t > t0 + d ? 1 : 1 + amt * (1 - E.out3((t - t0) / d)));
// the latest event time <= t in a list (the hit a shot is reacting to)
const lastHit = (t, ts) => { let r = -1e9; for (const x of ts) if (x <= t && x > r) r = x; return r; };

// the impact frame: a hard negative (pass as present's filter)
const NEG = 'invert(1) grayscale(1) contrast(2.2)';
// grade a buffer onto X: a canvas CSS filter string, then an optional RGB split (px)
function present(b, filter = 'none', split = 0) {
  if (filter !== 'none') { const g = buf('graded'); g.x.filter = filter; g.x.drawImage(b.c, 0, 0); g.x.filter = 'none'; b = g; }
  if (split) rgbSplit(b.c, split, 0); else X.drawImage(b.c, 0, 0);
}

// RGB split: red and blue pushed apart by (dx, dy) px (x HARDEDIT.split). Each shifted channel is scaled up about the centre
// just enough (1 + 2|d|/size) that it still covers the frame: no coloured bars at the edges.
function rgbSplit(src, dx, dy = 0) {
  dx *= HARDEDIT.split; dy *= HARDEDIT.split;
  if (Math.abs(dx) < .5 && Math.abs(dy) < .5) { X.drawImage(src, 0, 0); return; }
  const c = buf('rgbc'), sx = 1 + 2 * Math.abs(dx) / W, sy = 1 + 2 * Math.abs(dy) / H, s = Math.max(sx, sy);
  X.save(); X.setTransform(1, 0, 0, 1, 0, 0); X.fillStyle = '#000'; X.fillRect(0, 0, W, H); X.globalCompositeOperation = 'lighter';
  for (const [col, ox, oy] of [['#f00', -dx, -dy], ['#0f0', 0, 0], ['#00f', dx, dy]]) {
    c.x.clearRect(0, 0, W, H);
    const k = col === '#0f0' ? 1 : s;
    c.x.setTransform(k, 0, 0, k, W / 2 * (1 - k) + ox, H / 2 * (1 - k) + oy); c.x.drawImage(src, 0, 0); c.x.setTransform(1, 0, 0, 1, 0, 0);
    c.x.globalCompositeOperation = 'multiply'; c.x.fillStyle = col; c.x.fillRect(0, 0, W, H);
    c.x.globalCompositeOperation = 'source-over';
    X.drawImage(c.c, 0, 0);
  }
  X.restore();
}

// film grain: a noise tile regenerated per frame (seeded by the frame), overlaid
function grain(t, amt = .08, size = 256) {
  const f = Math.floor(t * FPS), g = buf('grain', size, size, false);
  if (g.f !== f) {
    const d = g.x.createImageData(size, size), a = d.data;
    let s = (f * 9301 + 49297) >>> 0;
    for (let i = 0; i < a.length; i += 4) { s = (s * 1664525 + 1013904223) >>> 0; const v = s >>> 24; a[i] = a[i + 1] = a[i + 2] = v; a[i + 3] = 255; }
    g.x.putImageData(d, 0, 0); g.f = f;
  }
  X.save(); X.setTransform(1, 0, 0, 1, 0, 0); X.globalAlpha = amt; X.globalCompositeOperation = 'overlay';
  X.fillStyle = X.createPattern(g.c, 'repeat'); X.fillRect(0, 0, W, H); X.restore();
}
// a dark radial vignette over the frame
function vignette(a = .5) {
  const g = X.createRadialGradient(W / 2, H / 2, H * .25, W / 2, H / 2, H * .75);
  g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(1, `rgba(0,0,0,${a})`);
  X.save(); X.setTransform(1, 0, 0, 1, 0, 0); X.fillStyle = g; X.fillRect(0, 0, W, H); X.restore();
}
