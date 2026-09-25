// engine/puppet.js: jointed cut-paper shadow puppets (Reiniger). Parts are traced vector silhouettes pinned at rivets; a
// parent carries its children. Drawn into a Canvas2D context (e.g. inside paper.js's shadow() callback), back to front:
// each part's paper, then its cut-outs punched through (light passes a slit unless a part in front covers it).
//
//   const f = await PUPPET.load('rig/fable/puppet.json');
//   f.draw(c, { torso: -3, head: 6, forearm: -20, hand: 10 }, { x, y, s, origin: [mx, my] }, { rods: [...] })
//
// Pose angles are degrees about each part's own rivet, relative to its parent. T maps master pixels to the canvas:
// the master point `origin` lands at (x, y), scaled by s (flip: -1 mirrors).
// Motion is authored with PUPPET.snap(): stop-motion holds; a paper limb snaps to its new angle through one in-between.

const PUPPET = (() => {
  const P2 = paths => { const p = new Path2D(); for (const pts of paths) { p.moveTo(pts[0][0], pts[0][1]); for (let i = 1; i < pts.length; i++) p.lineTo(pts[i][0], pts[i][1]); p.closePath(); } return p; };

  async function load(url) {
    const J = await (await fetch(url)).json();
    const parts = J.parts.map(q => ({ ...q, outlineP: P2(q.outline), holesP: P2(q.holes), holeList: q.holes.map(h => ({ pts: h, path: P2([h]) })),
      filmP: q.film && q.film.length ? P2(q.film) : null }));
    const by = Object.fromEntries(parts.map(q => [q.name, q]));
    const pup = { J, parts, by };
    pup.world = (pose, T) => world(pup, pose, T);
    pup.draw = (c, pose, T, o) => draw(pup, c, pose, T, o);
    return pup;
  }

  function world(pup, pose, T) {
    const o = T.origin || [0, 0], base = new DOMMatrix().translate(T.x, T.y).scale(T.s * (T.flip || 1), T.s).translate(-o[0], -o[1]);
    const M = {};
    const get = name => {
      if (M[name]) return M[name];
      const q = pup.by[name], parent = q.parent ? get(q.parent) : base.translate((pose.dx || 0) / T.s, (pose.dy || 0) / T.s);
      const a = pose[name] || 0, [px, py] = q.pivot || [0, 0], ty = pose[name + '.y'] || 0;   // name.y: a lift along the parent (master px)
      return (M[name] = parent.translate(0, ty).translate(px, py).rotate(a).translate(-px, -py));
    };
    for (const q of pup.parts) get(q.name);
    return M;
  }

  const inPoly = (pts, x, y) => { let ins = false; for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) { const [xi, yi] = pts[i], [xj, yj] = pts[j]; if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) ins = !ins; } return ins; };
  let GL = null;
  const ghostLayer = c => {
    if (!GL || GL.canvas.width !== c.canvas.width || GL.canvas.height !== c.canvas.height) { const cv = document.createElement('canvas'); cv.width = c.canvas.width; cv.height = c.canvas.height; GL = cv.getContext('2d'); }
    return GL;
  };

  function draw(pup, c, pose, T, o = {}) {
    const M = world(pup, pose, T);
    c.save();
    const G = (o.ghosts && pose._ghost) || {};
    for (const q of pup.parts) {
      if (o.hide && o.hide.includes(q.name)) continue;
      if (o.ghosts && o.ghosts.includes(q.name) && G[q.name]) {        // three fanned afterimages (Fable: instead of a smear)
        // older echoes read as cutouts held further from the screen: lighter, softer shadows; the newest is full black paper.
        // Each echo is drawn on its own layer so its cut-outs don't punch through the others.
        const [a0, a1] = G[q.name];
        for (const [a, al, bl] of [[a0 + (a1 - a0) * .1, .28, 3], [(a0 + a1) / 2, .5, 1.5], [a1 - (a1 - a0) * .15, 1, 0]]) {
          const L = ghostLayer(c); L.setTransform(1, 0, 0, 1, 0, 0); L.clearRect(0, 0, L.canvas.width, L.canvas.height);
          L.setTransform(world(pup, { ...pose, [q.name]: a }, T)[q.name]);
          L.globalCompositeOperation = 'source-over'; L.fillStyle = o.ink || 'rgb(22,22,26)'; L.fill(q.outlineP);
          L.globalCompositeOperation = 'destination-out'; L.fill(q.holesP);
          c.save(); c.setTransform(1, 0, 0, 1, 0, 0); c.globalCompositeOperation = 'source-over'; c.globalAlpha = al; c.filter = bl ? `blur(${bl}px)` : 'none';
          c.drawImage(L.canvas, 0, 0); c.restore();
        }
        continue;
      }
      c.setTransform(M[q.name]);
      c.globalCompositeOperation = 'source-over'; c.fillStyle = o.ink || 'rgb(22,22,26)'; c.fill(q.outlineP);
      c.globalCompositeOperation = 'destination-out'; c.fill(q.holesP);
      if (q.filmP && o.gel) {                     // cellophane: cut the plate's area out of the paper, then lay the gel in it,
        c.fill(q.filmP);                           // offset from the keyline (misregistered): a sliver of open light on one side
        c.save(); c.clip(q.filmP); c.globalCompositeOperation = 'source-over'; c.globalAlpha = o.gelAlpha ?? .9; c.fillStyle = o.gel;
        const [mx, my] = o.misreg || [2, 2]; c.setTransform(new DOMMatrix([1, 0, 0, 1, mx, my]).multiply(M[q.name])); c.fill(q.filmP); c.restore();
      }
      for (const pr of o.props || []) if (pr.after === q.name) { c.save(); pr.draw(c, M); c.restore(); }
    }
    // cover: close a cut-out with paper cut to its exact shape (a blink closes the eye slit): {part: [[x, y] master px inside the hole]}
    for (const [pn, pts] of Object.entries(o.cover || {})) {
      const q = pup.by[pn]; c.setTransform(M[pn]); c.globalCompositeOperation = 'source-over'; c.fillStyle = o.ink || 'rgb(22,22,26)';
      for (const [px, py] of pts) for (const h of q.holeList) if (inPoly(h.pts, px, py)) { c.fill(h.path); c.lineWidth = 3; c.strokeStyle = c.fillStyle; c.stroke(h.path); }
    }
    c.globalCompositeOperation = 'source-over'; c.fillStyle = o.ink || 'rgb(22,22,26)';
    for (const r of o.rods || []) {            // rods: from a point on a part (master px) straight down out of frame
      const m = M[r.part], p = m.transformPoint(new DOMPoint(r.at[0], r.at[1]));
      c.setTransform(1, 0, 0, 1, 0, 0); c.lineWidth = r.w || 5; c.strokeStyle = o.ink || 'rgb(22,22,26)'; c.lineCap = 'round';
      c.beginPath(); c.moveTo(p.x, p.y); c.lineTo(p.x + (r.lean || 0), c.canvas.height + 20); c.stroke();
    }
    c.restore();
    return M;
  }

  // stop-motion posing: keys [[t, {part: deg}], ...]. Every change runs: one in-between drawing, one drawing past the new pose
  // (the paper's overshoot), then the pose, held. No easing curves. On the in-between drawing, out._ghost[part] = [from, to]
  // (draw() can fan three afterimages there instead of a smear).
  function snap(list, o = {}) {
    const fps = o.fps || 12, inb = o.inbetween ?? .5, over = o.overshoot ?? .12;
    const names = [...new Set(list.flatMap(([, k]) => Object.keys(k)))];
    const tr = Object.fromEntries(names.map(n => [n, list.filter(([, k]) => n in k).map(([t, k]) => [t, k[n]])]));
    return t => {
      const q = Math.floor(t * fps + 1e-6) / fps, out = { _ghost: {} };
      for (const n of names) {
        const a = tr[n]; let v = a[0][1];
        for (let i = 1; i < a.length; i++) {
          const [t1, v1] = a[i], [, v0] = a[i - 1]; if (q < t1 - 1e-6) break;
          const d = Math.floor((q - t1) * fps + 1e-6);   // drawings since the key (floor: a key between grid lines still gets its in-between)
          if (d === 0 && v0 !== v1) { v = v0 + (v1 - v0) * inb; out._ghost[n] = [v0, v1]; }
          else if (d === 1 && v0 !== v1) v = v1 + (v1 - v0) * over;
          else v = v1;
        }
        out[n] = v;
      }
      return out;
    };
  }

  // a hanging strip (ribbon, sleeve tassel) on a Verlet chain whose root rides a part: stepped at 1/120 s from a pre-roll,
  // so a frame is a pure function of t. Returns the strip's centre points in canvas coordinates.
  function chain(pup, poseAt, T, o, t) {
    const n = o.n || 12, seg = (o.len || 1400) / n * T.s, dt = 1 / 120, pre = o.preroll || 2.5, g = (o.gravity || 2600) * T.s, damp = o.damp ?? .985;
    const root = tt => { const M = world(pup, poseAt(tt), T)[o.part], p = M.transformPoint(new DOMPoint(o.at[0], o.at[1])); return [p.x, p.y]; };
    let r0 = root(t - pre); const P = [], Q = [];
    for (let i = 0; i <= n; i++) { P.push([r0[0] + (o.dx || 0) * i * T.s, r0[1] + seg * i]); Q.push([...P[i]]); }
    const steps = Math.round(pre / dt);
    for (let k = 1; k <= steps; k++) {
      const tt = t - pre + k * dt, r = root(tt); P[0] = r; Q[0] = r;
      const wind = (o.wind || 0) * T.s * Math.sin(tt * 1.7 + (o.seed || 0));
      for (let i = 1; i <= n; i++) {
        const p = P[i], q = Q[i], vx = (p[0] - q[0]) * damp, vy = (p[1] - q[1]) * damp;
        Q[i] = [p[0], p[1]]; P[i] = [p[0] + vx + wind * dt * dt, p[1] + vy + g * dt * dt];
      }
      for (let it = 0; it < 4; it++) for (let i = 1; i <= n; i++) {
        const a = P[i - 1], b = P[i], dx = b[0] - a[0], dy = b[1] - a[1], d = Math.hypot(dx, dy) || 1, e = (d - seg) / d;
        if (i === 1) { P[i] = [b[0] - dx * e, b[1] - dy * e]; } else { P[i - 1] = [a[0] + dx * e * .5, a[1] + dy * e * .5]; P[i] = [b[0] - dx * e * .5, b[1] - dy * e * .5]; }
      }
      P[0] = r;
    }
    return P;
  }
  // a strip polygon around chain points, `w` wide (canvas px), tapering to `tip`
  function strip(pts, w, tip = .6, notch = 0) {
    const L = [], R = [];
    for (let i = 0; i < pts.length; i++) {
      const a = pts[Math.max(0, i - 1)], b = pts[Math.min(pts.length - 1, i + 1)], dx = b[0] - a[0], dy = b[1] - a[1], d = Math.hypot(dx, dy) || 1;
      const hw = w / 2 * (1 - (1 - tip) * i / (pts.length - 1)), nx = -dy / d * hw, ny = dx / d * hw;
      L.push([pts[i][0] + nx, pts[i][1] + ny]); R.push([pts[i][0] - nx, pts[i][1] - ny]);
    }
    if (notch) {                                   // a bookmark's swallowtail: the end cut in a V
      const e = pts[pts.length - 1], f = pts[pts.length - 2], dx = e[0] - f[0], dy = e[1] - f[1], d = Math.hypot(dx, dy) || 1;
      return [...L, [e[0] - dx / d * notch, e[1] - dy / d * notch], ...R.reverse()];
    }
    return [...L, ...R.reverse()];
  }

  // a stiff cellophane strip that holds its drawn curve (Fable's ribbon): segments with rest angles in the root part's frame,
  // pulled back toward rest and toward hanging each drawing (it lags one drawing and settles in about three). No wind.
  // Stepped per drawing (fps) from a pre-roll, so a frame is a pure function of t. Returns canvas points.
  function stiff(pup, poseAt, T, o, t) {
    const fps = o.fps || 12, n = o.rest.length, seg = o.len / n * T.s, k = o.follow ?? .55, gw = o.gravity ?? .35;
    const q0 = Math.floor(t * fps + 1e-6) / fps, pre = o.preroll || 1.5;
    const frame = tt => { const M = world(pup, poseAt(tt), T)[o.part]; const p = M.transformPoint(new DOMPoint(o.at[0], o.at[1])); return { x: p.x, y: p.y, rot: Math.atan2(M.b, M.a) * 180 / Math.PI * (T.flip || 1) }; };
    let ang = null, prev = null, pprev = null;
    for (let tt = q0 - pre; tt <= q0 + 1e-6; tt += 1 / fps) {
      const F = prev || frame(tt);                                          // the strip answers the previous drawing (a lag of one)
      const vx = pprev ? (F.x - pprev.x) / T.s : 0;                          // the root's travel per drawing (master px): the strip trails it
      const want = o.rest.map((r, i) => (1 - gw) * (r + F.rot) + gw * 90 + Math.max(-40, Math.min(40, vx * (o.drag ?? .09) * (T.flip || 1) * (i + 1) / n)));
      pprev = F;
      ang = ang ? ang.map((a, i) => a + (want[i] - a) * k) : want;
      prev = frame(tt);
    }
    const F = frame(q0); const P = [[F.x, F.y]];
    for (let i = 0; i < n; i++) { const a = ang[i] * Math.PI / 180, p = P[i]; P.push([p[0] + Math.cos(a) * seg * (T.flip || 1), p[1] + Math.sin(a) * seg]); }
    return P;
  }

  // ---- morphing cut-paper shapes (the fan and every noun it becomes: rig/fable/fan/fan.json)
  // Outlines share a point count and start near the grip; a pair is aligned by the cyclic shift that minimises the travel,
  // so an in-between is a plausible cut shape. Slits (constant count) interpolate end to end.
  async function loadShapes(url) {
    const J = await (await fetch(url)).json(), S = {};
    for (const [n, v] of Object.entries(J.shapes)) S[n] = { o: v.outline, sl: v.slits };
    return { S, shift: {} };
  }
  function bestShift(A, B) {
    const m = A.length; let best = 0, bd = Infinity;
    for (let k = 0; k < m; k += 2) { let d = 0; for (let i = 0; i < m; i += 4) { const b = B[(i + k) % m]; d += (A[i][0] - b[0]) ** 2 + (A[i][1] - b[1]) ** 2; } if (d < bd) { bd = d; best = k; } }
    return best;
  }
  // Fable's rule: the slits lead, the outline follows. Card 1 (u = 1/3) is the source outline already cut with the target's
  // slits (the cut comes before the shape, as in real paper); card 2 (u = 2/3) is the outline 2/3 of the way; card 3 the pose.
  function shapeAt(SH, a, b, u, lead = true) {
    const A = SH.S[a], B = SH.S[b]; if (u <= 0 || a === b) return A; if (u >= 1) return B;
    const ou = lead ? (u < .5 ? 0 : u) : u;
    const key = a + '>' + b; if (SH.shift[key] === undefined) SH.shift[key] = bestShift(A.o, B.o);
    const k = SH.shift[key], m = A.o.length, o = new Array(m);
    for (let i = 0; i < m; i++) { const p = A.o[i], q = B.o[(i + k) % m]; o[i] = [p[0] + (q[0] - p[0]) * ou, p[1] + (q[1] - p[1]) * ou]; }
    const sl = lead ? B.sl : A.sl.map((s, i) => s.map((v, j) => v + (B.sl[i][j] - v) * u));
    return { o, sl };
  }
  // draw a shape into c under matrix Mx (a DOMMatrix: shape px -> canvas): black paper, slits cut through
  function drawShape(c, sh, Mx, ink = 'rgb(22,22,26)', o = {}) {
    c.save(); c.setTransform(Mx);
    const p = new Path2D(); p.moveTo(sh.o[0][0], sh.o[0][1]); for (let i = 1; i < sh.o.length; i++) p.lineTo(sh.o[i][0], sh.o[i][1]); p.closePath();
    if (o.gel) {                                   // coloured paper, backlit: the sheet is gel, its folds darker lines (more layers)
      c.globalCompositeOperation = 'source-over'; c.fillStyle = o.gel; c.fill(p);
      c.clip(p);                                   // a fold line exists only on the paper (when creases lead, the next shape's folds
      c.strokeStyle = o.crease || 'rgba(120,40,12,.75)'; c.lineCap = 'round';   // show where they cross the current sheet)
      for (const [x0, y0, x1, y1, w] of sh.sl) if (w > .5) { c.lineWidth = w * (o.creaseScale || 1); c.beginPath(); c.moveTo(x0, y0); c.lineTo(x1, y1); c.stroke(); }
      c.restore(); return;
    }
    c.globalCompositeOperation = 'source-over'; c.fillStyle = ink; c.fill(p);
    c.globalCompositeOperation = 'destination-out'; c.strokeStyle = '#000'; c.lineCap = 'round';
    for (const [x0, y0, x1, y1, w] of sh.sl) if (w > .5) { c.lineWidth = w; c.beginPath(); c.moveTo(x0, y0); c.lineTo(x1, y1); c.stroke(); }
    c.restore();
  }
  // a sequence of shapes over time, each change in three held drawings (u = 1/3, 2/3, 1), each held `hold` drawings at `fps`
  function morphs(list, o = {}) {
    const fps = o.fps || 12, hold = o.hold || 2;
    return t => {
      const q = Math.floor(t * fps + 1e-6) / fps; let cur = list[0][1], prev = cur, u = 1;
      for (let i = 1; i < list.length; i++) {
        const [t1, s1] = list[i]; if (q < t1 - 1e-6) break;
        const d = Math.floor((q - t1) * fps / hold + 1e-6); prev = list[i - 1][1]; cur = s1; u = Math.min(1, (d + 1) / 3);
      }
      return [prev, cur, u];
    };
  }

  return { load, snap, chain, strip, stiff, loadShapes, shapeAt, drawShape, morphs };
})();
