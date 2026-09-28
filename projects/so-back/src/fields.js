// SO BACK: the drop's fields (Y2K / hyperpop grounds behind keyed fighters) and the keyed-fighter treatments.
// Every field fills the frame and is a pure function of t. Keep pink fields away from Puff (she is pink).
function fieldBurst(t, a = PAL.pink, b = '#ff5cb4', cx = W / 2, cy = H * .48, spin = .35) {
  flat(a); sunburst(cx, cy, a, b, 22, t * spin);
}
// a perspective checker floor racing toward the lens under a gradient sky (the PS2-era floor)
function fieldFloor(t, a = PAL.lime, b = '#8fd400', sky0 = '#2e0a5c', sky1 = PAL.pink, speed = 3) {
  const hz = H * .44, g = X.createLinearGradient(0, 0, 0, hz);
  g.addColorStop(0, sky0); g.addColorStop(1, sky1); X.fillStyle = g; X.fillRect(0, 0, W, hz);
  X.fillStyle = a; X.fillRect(0, hz, W, H - hz);
  const rows = 18, cols = 10, off = (t * speed) % 1;
  X.fillStyle = b;
  for (let r = 0; r < rows; r++) {
    const z0 = 1 / (r + 1 - off + .6), z1 = 1 / (r + 2 - off + .6);            // depth -> screen y
    const y0 = hz + (H - hz) * z0 * 1.4, y1 = hz + (H - hz) * z1 * 1.4;
    if (y1 >= H) continue;
    for (let c = -cols; c < cols; c++) {
      if ((c + r + Math.floor(t * speed)) % 2) continue;
      const xa = W / 2 + c * 260 * z0 * 1.4, xb = W / 2 + (c + 1) * 260 * z0 * 1.4, xc = W / 2 + (c + 1) * 260 * z1 * 1.4, xd = W / 2 + c * 260 * z1 * 1.4;
      X.beginPath(); X.moveTo(xa, Math.min(y0, H)); X.lineTo(xb, Math.min(y0, H)); X.lineTo(xc, y1); X.lineTo(xd, y1); X.closePath(); X.fill();
    }
  }
}
// a chrome sky: deep violet to cyan to white horizon bands, with twinkling four-point sparkles
function fieldChrome(t) {
  const g = X.createLinearGradient(0, 0, 0, H);
  [[0, '#1a0640'], [.35, '#5a2eff'], [.55, '#2ee6ff'], [.62, '#ffffff'], [.7, '#ff9ad8'], [1, '#2e0a5c']].forEach(([k, c]) => g.addColorStop(k, c));
  X.fillStyle = g; X.fillRect(0, 0, W, H);
  for (let i = 0; i < 26; i++) {
    const x = hash(i * 3.1) * W, y = hash(i * 7.7) * H, tw = .5 + .5 * Math.sin(t * 9 + i * 1.7);
    sparkle(x, y, 10 + 26 * tw * hash(i * 1.3), '#fff', 0);
  }
}
// radial speed lines over a flat colour (the anime focus burst)
function fieldSpeed(t, col = PAL.cyan, line = '#fff', cx = W / 2, cy = H * .5) {
  flat(col); speedLines(cx, cy, line, 70, Math.floor(t * 30), 260, .9);
}

// ---- keyed fighters
// a keyed plate composited with its outline, optionally scaled about (cx, cy) and shaken; `outlineCol` null skips the outline
function keyed(K, pt, o = {}) {
  const z = o.z || 1, [cx, cy] = o.c || [W / 2, H / 2], [dx, dy] = o.d || [0, 0];
  X.save(); zoomAt(cx, cy, z, dx, dy);
  if (o.outline !== null) keyedOutline(K, pt, o.outline || PAL.white, o.ow || 12);
  drawKeyed(K, pt);
  X.restore();
}
// the impact frame (anime/hard-edit): ONE frame of the scene as a hard negative, on the big hits only. Call present(b, NEG).
const NEG = 'invert(1) grayscale(1) contrast(2.2)';
// (a flat silhouette from the matte: glows make it a blob on shines and lasers, so it's only for clean bodies)
function impactFrame(K, pt, fg = '#fff', bg = '#000', o = {}) {
  if (NEED) { _need(K, pt); return; }
  const z = o.z || 1, [cx, cy] = o.c || [W / 2, H / 2];
  flat(bg);
  const m = K.a.img(pt); if (!m) return;
  const s = buf('impact'); s.x.save(); s.x.translate(cx, cy); s.x.scale(z, z); s.x.translate(-cx, -cy); s.x.drawImage(m, 0, 0, W, H); s.x.restore();
  s.x.globalCompositeOperation = 'source-in'; s.x.fillStyle = fg; s.x.fillRect(0, 0, W, H);
  X.drawImage(s.c, 0, 0);
}
