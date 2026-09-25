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
    const parts = J.parts.map(q => ({ ...q, outlineP: P2(q.outline), holesP: P2(q.holes) }));
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
      const a = pose[name] || 0, [px, py] = q.pivot || [0, 0];
      return (M[name] = parent.translate(px, py).rotate(a).translate(-px, -py));
    };
    for (const q of pup.parts) get(q.name);
    return M;
  }

  function draw(pup, c, pose, T, o = {}) {
    const M = world(pup, pose, T);
    c.save();
    const G = (o.ghosts && pose._ghost) || {};
    for (const q of pup.parts) {
      if (o.hide && o.hide.includes(q.name)) continue;
      if (o.ghosts && o.ghosts.includes(q.name) && G[q.name]) {        // three fanned afterimages (Fable: instead of a smear)
        const [a0, a1] = G[q.name];
        for (const a of [a0, (a0 + a1) / 2, a1]) {
          const Mg = world(pup, { ...pose, [q.name]: a }, T)[q.name]; c.setTransform(Mg);
          c.globalCompositeOperation = 'source-over'; c.fillStyle = o.ink || 'rgb(22,22,26)'; c.fill(q.outlineP);
          c.globalCompositeOperation = 'destination-out'; c.fill(q.holesP);
        }
        continue;
      }
      c.setTransform(M[q.name]);
      c.globalCompositeOperation = 'source-over'; c.fillStyle = o.ink || 'rgb(22,22,26)'; c.fill(q.outlineP);
      c.globalCompositeOperation = 'destination-out'; c.fill(q.holesP);
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
          const d = Math.round((q - t1) * fps);
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
    let ang = null, prev = null;
    for (let tt = q0 - pre; tt <= q0 + 1e-6; tt += 1 / fps) {
      const F = prev || frame(tt);                                          // the strip answers the previous drawing (a lag of one)
      const want = o.rest.map(r => (1 - gw) * (r + F.rot) + gw * 90);     // its drawn curve, pulled toward hanging
      ang = ang ? ang.map((a, i) => a + (want[i] - a) * k) : want;
      prev = frame(tt);
    }
    const F = frame(q0); const P = [[F.x, F.y]];
    for (let i = 0; i < n; i++) { const a = ang[i] * Math.PI / 180, p = P[i]; P.push([p[0] + Math.cos(a) * seg * (T.flip || 1), p[1] + Math.sin(a) * seg]); }
    return P;
  }

  return { load, snap, chain, strip, stiff };
})();
