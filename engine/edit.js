// engine/edit.js: plates in an edit. A film cut from captures (a game, footage rendered elsewhere) plays each plate through a
// time map (velocity ramps, freezes, stutters, replays), so a shot draws plate frames at arbitrary plate times, and keyed
// plates composite exactly over anything the film draws. Load after engine/plate.js. (Promoted from SO BACK.)
//
//   const K = keyedPlate('assets/plates/fight/v', 1170, { keyed: true, pre: 1.0 })   // f00001.jpg... (+ m00001.png mattes)
//   drawPlate(K, pt)                   the frame at plate time pt (s from frame 1) into the whole frame (or a box), on X
//   drawKeyed(K, pt)                   a keyed pair over whatever X holds: out = colour + (1 - a) * X
//   keyedOutline(K, pt, '#fff', 12)    the subject's outline (bodies only), drawn under the subject
//   const m = tmap([[t0, p0], [t1, p1, 'out3'], ...]); drawPlate(K, m(t))   film time -> plate time, eased per segment
//   stutter(t, t0, p0, len, period)    loop a plate span on a grid
//
// Keyed plates are two captures of one deterministic render: on black and on a mid grey. The difference gives the coverage
// exactly, and the black pass is the premultiplied colour, additive glows included (tools/machinima/dmatte.py, prep_plates.py).
// A frame dir holds f00001.jpg (the frame or the black pass) and, for keyed plates, m00001.png: an LA PNG whose ALPHA is the
// coverage (browsers read a grey 'L' PNG as opaque).
//
// Preloading follows what is drawn. Before each rendered frame, PREFRAME runs the frame once in record mode: drawPlate,
// drawKeyed and keyedOutline only note the plate frames they would draw. It loads exactly those, then the real draw happens,
// however the time maps bend. Plates made with plate() directly (not through keyedPlate) are still prepared at film time t,
// as engine/plate.js does.
const PL = {};
function keyedPlate(dir, n, o = {}) {        // o.keyed: has mattes; o.pre: film time of frame 1 is -pre (plates on the film clock)
  if (PL[dir]) return PL[dir];
  const K = { dir, n, pre: o.pre || 0, keyed: !!o.keyed,
    rgb: plate(dir, { n, fps: o.fps || 60, t0: 0, ext: o.ext || 'jpg', keep: o.keep || 24, ahead: 0 }) };
  K.rgb.managed = true;
  if (o.keyed) {
    K.a = plate(dir, { n, fps: o.fps || 60, t0: 0, ext: 'png', keep: o.keep || 24, ahead: 0 });
    K.a.url = i => `${dir}/m${String(i + 1).padStart(5, '0')}.png`; K.a.managed = true;
  }
  return (PL[dir] = K);
}
let NEED = null;                             // record mode: [[plate, plate t], ...] while PREFRAME runs the frame
function _need(K, pt) { NEED.push([K.rgb, pt]); if (K.a) NEED.push([K.a, pt]); }
function drawPlate(K, pt, x = 0, y = 0, w = W, h = H) {
  if (NEED) { _need(K, pt); return; }
  K.rgb.draw(X, pt, x, y, w, h);
}
function drawKeyed(K, pt, x = 0, y = 0, w = W, h = H) {
  if (NEED) { _need(K, pt); return; }
  const im = K.rgb.img(pt), m = K.a.img(pt); if (!im || !m) return;
  X.save(); X.globalCompositeOperation = 'destination-out'; X.drawImage(m, x, y, w, h);
  X.globalCompositeOperation = 'lighter'; X.drawImage(im, x, y, w, h); X.restore();   // (the black pass is opaque: alpha returns to 1)
}
// the outline: the matte thresholded to solid bodies first (alpha >= .7), then dilated and tinted. Stamping the raw matte
// sums a faint full-frame hit flash (12% in Melee) to a white wash and balloons glows into blobs.
(() => {
  if (typeof document === 'undefined' || document.getElementById('editSolid')) return;
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('width', '0'); svg.setAttribute('height', '0'); svg.style.position = 'absolute';
  svg.innerHTML = '<filter id="editSolid" color-interpolation-filters="sRGB"><feComponentTransfer>' +
    '<feFuncA type="discrete" tableValues="0 0 0 0 0 0 0 1 1 1"/></feComponentTransfer></filter>';
  (document.body || document.documentElement).appendChild(svg);
})();
function keyedOutline(K, pt, col = '#fff', wpx = 10, x = 0, y = 0, w = W, h = H) {
  if (NEED) { _need(K, pt); return; }
  const m = K.a.img(pt); if (!m) return;
  const sm = buf('ksolid'); sm.x.filter = 'url(#editSolid)'; sm.x.drawImage(m, x, y, w, h); sm.x.filter = 'none';
  const o = buf('kout'); o.x.setTransform(X.getTransform());
  for (let i = 0; i < 16; i++) { const a = i / 16 * TAU; o.x.drawImage(sm.c, Math.cos(a) * wpx, Math.sin(a) * wpx); }
  o.x.setTransform(1, 0, 0, 1, 0, 0); o.x.globalCompositeOperation = 'source-in'; o.x.fillStyle = col; o.x.fillRect(0, 0, W, H);
  X.save(); X.setTransform(1, 0, 0, 1, 0, 0); X.drawImage(o.c, 0, 0); X.restore();
}
window.PREFRAME = async t => {
  NEED = [];
  try { drawFrame(t); } finally { var need = NEED; NEED = null; }
  await Promise.all(need.map(([P, pt]) => P.prep(pt)).concat(PLATES.filter(P => !P.managed).map(P => P.prep(t))));
};

// ---- time maps (film t -> plate t)
// piecewise keys [[film t, plate t, ease], ...]: each segment eased by its ease ('lin' default, or an E.* name); outside the
// keys the plate runs 1:1
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
