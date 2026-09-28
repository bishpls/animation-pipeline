// SO BACK: plates in the edit. A plate is played through a time map (velocity ramps, freezes, stutters), so a shot draws
// plate frames at arbitrary plate times. Preloading follows what is actually drawn: before each rendered frame, PREFRAME
// runs the frame once in record mode (drawPlate/drawKeyed only note what they would draw), loads exactly those frames, then
// the real draw happens. Plates live in assets/plates/<name>/v (prep_plates.py): f00001.jpg = the frame (or the black pass
// of a keyed pair, premultiplied colour), m00001.png = the matte (LA, alpha = coverage).
const PL = {};
function vplate(name, n, o = {}) {        // o.keyed: has mattes; o.pre: film time of frame 1 is -pre (for plates on the film clock)
  if (PL[name]) return PL[name];
  const dir = `assets/plates/soback_${name}/v`;
  const K = { name, n, pre: o.pre || 0, keyed: !!o.keyed,
    rgb: plate(dir, { n, fps: 60, t0: 0, ext: 'jpg', keep: 24, ahead: 0 }) };
  if (o.keyed) { K.a = plate(dir, { n, fps: 60, t0: 0, ext: 'png', keep: 24, ahead: 0 }); K.a.url = i => `${dir}/m${String(i + 1).padStart(5, '0')}.png`; }
  return (PL[name] = K);
}
// plate time -> clamped frame time (frame k shows over [k/60, (k+1)/60))
let NEED = null;
function _need(K, pt) { NEED.push([K.rgb, pt]); if (K.a) NEED.push([K.a, pt]); }
// draw the plate's frame at plate time pt (seconds from its frame 1) into box (default full frame), on X
function drawPlate(K, pt, x = 0, y = 0, w = W, h = H) {
  if (NEED) { _need(K, pt); return; }
  K.rgb.draw(X, pt, x, y, w, h);
}
// a keyed plate over whatever X holds: out = black + (1 - a) * BG
function drawKeyed(K, pt, x = 0, y = 0, w = W, h = H) {
  if (NEED) { _need(K, pt); return; }
  const im = K.rgb.img(pt), m = K.a.img(pt); if (!im || !m) return;
  X.save(); X.globalCompositeOperation = 'destination-out'; X.drawImage(m, x, y, w, h);
  X.globalCompositeOperation = 'lighter'; X.drawImage(im, x, y, w, h); X.restore();   // (the black pass is opaque: alpha returns to 1)
}
// the matte alone, thresholded to solid bodies (alpha >= .7: glows and Melee's translucent full-frame hit flash drop out),
// dilated, tinted: the hard-edit subject outline, drawn under the subject. (Stamping the raw matte 16 times summed a 12% hit
// flash to ~88% and ballooned glows into blobs: found by the drop agent.)
(() => {
  if (document.getElementById('sbSolidE')) return;
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('width', '0'); svg.setAttribute('height', '0'); svg.style.position = 'absolute';
  svg.innerHTML = '<filter id="sbSolidE" color-interpolation-filters="sRGB"><feComponentTransfer>' +
    '<feFuncA type="discrete" tableValues="0 0 0 0 0 0 0 1 1 1"/></feComponentTransfer></filter>';
  document.body.appendChild(svg);
})();
function keyedOutline(K, pt, col = '#fff', wpx = 10, x = 0, y = 0, w = W, h = H) {
  if (NEED) { _need(K, pt); return; }
  const m = K.a.img(pt); if (!m) return;
  const sm = buf('ksolid'); sm.x.filter = 'url(#sbSolidE)'; sm.x.drawImage(m, x, y, w, h); sm.x.filter = 'none';
  const o = buf('kout'); o.x.setTransform(X.getTransform());
  for (let i = 0; i < 16; i++) { const a = i / 16 * TAU; o.x.drawImage(sm.c, Math.cos(a) * wpx, Math.sin(a) * wpx); }
  o.x.setTransform(1, 0, 0, 1, 0, 0); o.x.globalCompositeOperation = 'source-in'; o.x.fillStyle = col; o.x.fillRect(0, 0, W, H);
  X.save(); X.setTransform(1, 0, 0, 1, 0, 0); X.drawImage(o.c, 0, 0); X.restore();
}
window.PREFRAME = async t => {
  NEED = [];
  try { drawFrame(t); } finally { var need = NEED; NEED = null; }
  await Promise.all(need.map(([P, pt]) => P.prep(pt)));
};

// ---- time maps (film t -> plate t)
// piecewise keys [[film t, plate t], ...] with an ease per segment ('lin' default, or an E.* name)
function tmap(keys) {
  return t => {
    if (t <= keys[0][0]) return keys[0][1] + (t - keys[0][0]);
    for (let i = 0; i + 1 < keys.length; i++) {
      const [a, pa, e] = keys[i], [b, pb] = keys[i + 1];
      if (t < b) { const u = (t - a) / (b - a); return lerp(pa, pb, e ? E[e](u) : u); }
    }
    const [a, pa] = keys[keys.length - 1]; return pa + (t - a);
  };
}
// a stutter: from t0, loop the plate span [p0, p0 + len) every `period` film seconds
const stutter = (t, t0, p0, len, period) => p0 + ((t - t0) % period) * (len / period);
