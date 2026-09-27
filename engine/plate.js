// engine/plate.js: image-sequence plates (a game's frame dump, footage rendered elsewhere) on the film clock, loaded on demand.
//   const FIGHT = plate('assets/plates/fight', { n: 2040, fps: 60, t0: 4.0, ext: 'jpg' });   // f00001.jpg ... from film time t0
//   FIGHT.draw(X, t, x, y, w, h)      the frame at film time t, stretched to the box (holds the first/last frame outside the range)
//   FIGHT.frame(t)                    the 0-based frame index at t;  FIGHT.img(t) the loaded Image or null
// A plate is data, not animation: every frame still comes from the pure function of t, because the index is. Headless renders
// await window.PREFRAME(t) (engine/studio.js), which loads each plate's frame for t plus a few ahead before drawing; the
// scrubbing studio draws the nearest loaded frame and fetches the rest. At most `keep` decoded frames stay in memory.
const PLATES = [];
function plate(dir, o = {}) {
  const P = { dir, n: o.n, fps: o.fps || 60, t0: o.t0 || 0, ext: o.ext || 'png', keep: o.keep || 48, ahead: o.ahead || 3, cache: new Map() };
  P.frame = t => Math.max(0, Math.min(P.n - 1, Math.floor((t - P.t0) * P.fps + 1e-6)));
  P.url = i => `${P.dir}/f${String(i + 1).padStart(5, '0')}.${P.ext}`;
  P.load = i => {
    let e = P.cache.get(i);
    if (!e) {
      const im = new Image(); im.src = P.url(i);
      e = { im, ok: false, p: im.decode().then(() => { e.ok = true; }, () => { e.ok = false; }) };
      P.cache.set(i, e);
      while (P.cache.size > P.keep) P.cache.delete(P.cache.keys().next().value);   // oldest first
    } else { P.cache.delete(i); P.cache.set(i, e); }                                 // refresh its place
    return e;
  };
  P.prep = async t => { const i = P.frame(t); const es = []; for (let k = 0; k <= P.ahead && i + k < P.n; k++) es.push(P.load(i + k)); await es[0].p; };
  P.img = t => {
    const i = P.frame(t), e = P.load(i);
    if (e.ok) return e.im;
    for (let d = 1; d < P.keep; d++) for (const j of [i - d, i + d]) { const f = P.cache.get(j); if (f && f.ok) return f.im; }
    return null;
  };
  P.draw = (x, t, bx = 0, by = 0, bw = W, bh = H) => { const im = P.img(t); if (im) x.drawImage(im, bx, by, bw, bh); return im; };
  PLATES.push(P);
  return P;
}
window.PREFRAME = t => Promise.all(PLATES.map(P => P.prep(t)));
