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
    for (const q of pup.parts) {
      if (o.hide && o.hide.includes(q.name)) continue;
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

  // stop-motion posing: keys [[t, {part: deg}], ...]; every change snaps through one in-between drawing (a 1/12 s smear-free
  // step at 1/3 and 2/3 of the way... on threes: a hold, one in-between, the new pose) and holds. No easing curves.
  function snap(list, o = {}) {
    const fps = o.fps || 12, inb = o.inbetween ?? .55;
    const names = [...new Set(list.flatMap(([, k]) => Object.keys(k)))];
    const tr = Object.fromEntries(names.map(n => [n, list.filter(([, k]) => n in k).map(([t, k]) => [t, k[n]])]));
    return t => {
      const q = Math.floor(t * fps) / fps, out = {};
      for (const n of names) {
        const a = tr[n]; let v = a[0][1];
        for (let i = 1; i < a.length; i++) {
          const [t1, v1] = a[i], [, v0] = a[i - 1]; if (q < t1) break;
          v = q < t1 + 1 / fps ? v0 + (v1 - v0) * inb : v1;          // one in-between drawing, then the new pose
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
  function strip(pts, w, tip = .6) {
    const L = [], R = [];
    for (let i = 0; i < pts.length; i++) {
      const a = pts[Math.max(0, i - 1)], b = pts[Math.min(pts.length - 1, i + 1)], dx = b[0] - a[0], dy = b[1] - a[1], d = Math.hypot(dx, dy) || 1;
      const hw = w / 2 * (1 - (1 - tip) * i / (pts.length - 1)), nx = -dy / d * hw, ny = dx / d * hw;
      L.push([pts[i][0] + nx, pts[i][1] + ny]); R.push([pts[i][0] - nx, pts[i][1] - ny]);
    }
    return [...L, ...R.reverse()];
  }

  return { load, snap, chain, strip };
})();
