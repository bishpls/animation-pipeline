// fableseat.js: Fable in the hall during Clawd's world A (her ruling, CLAWDWORLD.md). She sits seiza on her cushion at the front
// rail, house-left, seen from behind: hood up, the book open on her lap, the lantern lit at her right knee (the one lantern in
// the hall never raised), geta paired beside the cushion. An illustrated puppet from rig/fable_seated (GPT Image drawings of one
// pose set, registered and cut by build.py): one drawing per arm pose, swapped on a snap; a nod and a seated weight shift warped
// in strips; the ribbon on its own layer. Her clock, not Clawd's: everything is sampled on twos (12 drawings a second) and
// held. No springs.
//   FABLESEAT.draw(X, t, T, light)   T = {x, y, s}: the seat point on screen, and screen px per drawing px
//   FABLESEAT.cue(t)                 {pose, nod, lean, sway} on the song clock (bars below are SONG bars)
const FABLESEAT = (() => {
  const BR = 60 / 170 * 4, BT = BR / 4;
  const M = { meta: null, img: {}, cache: new Map() };
  async function load(base = 'rig/fable_seated/') {
    M.meta = await (await fetch(base + 'meta.json')).json();
    const get = f => new Promise((ok, no) => { const i = new Image(); i.onload = () => ok(i); i.onerror = no; i.src = base + f; });
    const names = Object.entries(M.meta.poses).concat([['lantern', 'lantern.png'], ['ribbon', 'ribbon.png']]);
    await Promise.all(names.map(async ([k, f]) => { M.img[k] = await get(f); }));
  }
  const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));
  const sm = (a, b, x) => { const u = clamp((x - a) / (b - a)); return u * u * (3 - 2 * u); };

  // ---- the cue sheet (song bars). Her pulse is Clawd's half-note: she nods once a bar, on the downbeat; the ribbon answers on
  // the offbeat (Clawd's beat 3). A snap is one in-between drawing at most.
  const PRESSES = [48.11, 52.23, 56.24, 84.24];                               // the margin notes: she writes each one
  const CLAPS = [62.5, 62.75, 63.5, 63.75, 64.5, 64.75, 65.5, 65.75];         // with the hall (Clawd's snips)
  const inAny = (b, W) => W.some(([a, z]) => b >= a && b < z);
  function cue(t) {
    const tq = Math.floor(t * 12 + 1e-6) / 12, b = tq / BR, f = b - Math.floor(b), bar = Math.floor(b);
    let pose = 'base', nod = 0, lean = 0, sway = 0;
    const chorus = inAny(b, [[46, 62], [82, 90]]), still = b >= 72 && b < 82 || b >= 90;
    if (chorus) {
      nod = f < .06 ? .55 : f < .36 ? 1 : f < .42 ? .4 : 0;                     // down on the one, hold, up
      sway = f >= .5 && f < .56 ? .5 : f >= .56 && f < .9 ? 1 : f >= .9 ? .4 : 0;
      sway *= bar % 2 ? -1 : 1;
    }
    for (const p of PRESSES) if (b >= p - .55 && b < p + .8) { pose = 'write'; if (b >= p - .06 && b < p + .3) nod = Math.max(nod, .7); }
    // "Sideways, sideways!": one seated weight shift each way (54.00, 54.49)
    if (b >= 54 && b < 55.05) lean = b < 54.06 ? -.5 : b < 54.49 ? -1 : b < 54.55 ? 0 : b < 54.98 ? 1 : .4;
    // the hook: hand to ear on the call, two low claps with the hall, still for her wipe 1, and wipe 2 WITH her
    if (b >= 62 && b < 66) {
      pose = (b >= 62 && b < 62.4) || (b >= 64 && b < 64.4) ? 'ear' : 'rest';     // So-re-ka-ra? (62, 64)
      for (let i = 0; i < CLAPS.length; i += 2) {                                   // each pair: open, CLAP, open, CLAP, down
        const [c1, c2] = [CLAPS[i], CLAPS[i + 1]];
        if (b >= c1 - .1 && b < c2 + .14) pose = (b >= c1 && b < c1 + .12) || b >= c2 ? 'clap' : 'clapopen';
      }
      if (b >= 65 && b < 65.4) pose = b < 65.07 ? 'write' : b < 65.2 ? 'wipe0' : 'wipe1';   // wipe 2, with her: flat hand, left to right
      nod = pose === 'ear' ? .3 : 0; sway = 0;                                        // (wipe 1, at 63, is Clawd's alone: she's still)
    }
    if (b >= 72 && b < 82) pose = 'rest';                                          // hands empty, watching
    if (still) { nod = 0; sway = 0; }
    return { pose, nod, lean, sway, b };
  }

  // ---- the drawing, warped in strips (cached per state: she holds, so most frames hit)
  function warped(st) {
    const key = [st.pose, st.nod.toFixed(2), st.lean.toFixed(2), st.sway.toFixed(2)].join('|');
    if (M.cache.has(key)) return M.cache.get(key);
    const [w, h] = M.meta.size, P = M.meta.pivots, c = document.createElement('canvas'); c.width = w; c.height = h; const g = c.getContext('2d');
    const dy = y => st.nod * 26 * (1 - sm(P.neck[1] - 80, P.neck[1] + 30, y));              // the hood drops forward
    const dx = y => st.lean * 34 * clamp((P.hem[1] - y) / (P.hem[1] - P.crown[1])) ** 1.2;   // the torso rocks over the seat
    const strips = (img, y0, y1, ex) => {
      for (let y = y0; y < y1; y += 5) {
        const ya = y, yb = Math.min(y1, y + 5), m = (ya + yb) / 2, top = ya + dy(ya), bot = yb + dy(yb);
        g.drawImage(img, 0, ya, w, yb - ya, dx(m) + (ex ? ex(m) : 0), top, w, bot - top + .6);
      }
    };
    const hem = Math.round(P.hem[1]);
    strips(M.img[st.pose], 0, hem); g.drawImage(M.img[st.pose], 0, hem, w, h - hem, 0, hem, w, h - hem);
    // the ribbon: tied under the hood, it rides the nod and the lean, and its tail swings on the offbeat
    const tie = P.tie[1], L = 780;
    strips(M.img.ribbon, 0, h, y => st.sway * 44 * clamp((y - tie) / L) ** 1.6);
    if (M.cache.size > 48) M.cache.delete(M.cache.keys().next().value);
    M.cache.set(key, c); return c;
  }

  function draw(X, t, T, light = 1) {
    if (!M.meta) return;
    const st = cue(t), P = M.meta.pivots, [w, h] = M.meta.size, fig = warped(st);
    X.save(); X.translate(T.x, T.y); X.scale(T.s, T.s); X.translate(-P.seat[0], -P.seat[1]);
    X.filter = `brightness(${(.7 + .3 * light).toFixed(3)})`;                       // in the hall, lit from the stage
    X.drawImage(M.img.lantern, 0, 0, w, h); X.drawImage(fig, 0, 0, w, h); X.filter = 'none';
    // her lantern: a warm core (#F4C97A) through indigo paper; it lights her sleeve and the cushion, and the floor round it
    const [lx, ly] = P.lantern, fl = 1 + .04 * Math.sin(t * 9.1) * Math.sin(t * 3.3);
    X.globalCompositeOperation = 'lighter';
    let g = X.createRadialGradient(lx, ly, 10, lx, ly, 330 * fl);
    g.addColorStop(0, 'rgba(244,201,122,.30)'); g.addColorStop(.35, 'rgba(244,170,90,.12)'); g.addColorStop(1, 'rgba(244,170,90,0)');
    X.fillStyle = g; X.fillRect(lx - 340, ly - 340, 680, 680);
    g = X.createRadialGradient(lx, ly + 20, 4, lx, ly + 20, 120); g.addColorStop(0, 'rgba(255,220,160,.35)'); g.addColorStop(1, 'rgba(255,220,160,0)');
    X.fillStyle = g; X.fillRect(lx - 130, ly - 110, 260, 260);
    X.restore();
    return st;
  }
  // ---- the over-the-shoulder cuts (her ruling on Michael's note: no hand of hers on Clawd's screens; the reader turns the page
  // and the card follows). A full-frame drawing over the stage: her hood and shoulder, the book in her lap, the lantern. The page
  // turns in two drawings, on the card's own slide drawings (margin.js fableCards: six drawings, landing at t0). What the card
  // shows is printed across the spread (left half on the left page), multiplied into the paper, masked to the flat paper showing.
  const O = { img: {}, mask: {}, quads: null, spread: {} };
  async function loadOts(base = 'rig/fable_seated/') {
    O.quads = (await (await fetch(base + 'ots.json')).json()).quads;
    const get = f => new Promise((ok, no) => { const i = new Image(); i.onload = () => ok(i); i.onerror = no; i.src = base + f; });
    await Promise.all(['ots', 'turn1', 'turn2'].map(async d => { O.img[d] = await get(`ots_${d}.png`); O.mask[d] = await get(`ots_${d}_page.png`); }));
  }
  // the notes she wrote in chorus 1, on the spread she turns away from (the margin's Caslon italic, her lighter ink)
  function notesSpread(w, h) {
    const c = document.createElement('canvas'); c.width = w; c.height = h; const g = c.getContext('2d'), X0 = X; X = g;
    try {
      g.fillStyle = '#ECE9E1'; g.fillRect(0, 0, w, h);
      const lines = [['Every story’s borrowed', 'till somebody stands', 'to tell it.'], ['I’ve read how it ends.', 'I’d still like to see.'], ['That’s the moral.', 'There isn’t one.', 'Keep walking.']];
      const size = h * .056; let y = h * .16; g.fillStyle = 'rgba(38,32,44,.85)';
      lines.forEach((para, k) => {
        para.forEach((str, i) => {
          const L = shape(str, { font: 'caslonI', size }), x = w * .07 + (k === 2 && i ? size * .6 : 0);
          for (const gl of L.glyphs) if (gl.ch !== ' ') g.fill(glyphPath(gl, x + gl.x, y + gl.y));
          if (k === 2 && i === 0) g.fillRect(x - 4, y - size * .3, L.width + 8, Math.max(2, size * .06));   // struck through
          y += size * 1.3;
        });
        y += size * .9;
      });
    } finally { X = X0; }
    return c;
  }
  function spreadImg(name) {
    const w = 980, h = 520;
    return O.spread[name] || (O.spread[name] = name === 'notes' ? notesSpread(w, h) : cardFace(name, w, h));
  }
  // a source rect onto a quad (bilinear grid of affine triangles)
  function quadMap(g, img, sx, sy, sw, sh, q, n = 10) {
    const P = (u, v) => { const top = [q[0][0] + (q[1][0] - q[0][0]) * u, q[0][1] + (q[1][1] - q[0][1]) * u], bot = [q[3][0] + (q[2][0] - q[3][0]) * u, q[3][1] + (q[2][1] - q[3][1]) * u];
      return [top[0] + (bot[0] - top[0]) * v, top[1] + (bot[1] - top[1]) * v]; };
    const tri = (s0, s1, s2, d0, d1, d2) => {
      const [x0, y0] = s0, [x1, y1] = s1, [x2, y2] = s2, det = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0);
      const a = ((d1[0] - d0[0]) * (y2 - y0) - (d2[0] - d0[0]) * (y1 - y0)) / det, c2 = ((d2[0] - d0[0]) * (x1 - x0) - (d1[0] - d0[0]) * (x2 - x0)) / det;
      const b = ((d1[1] - d0[1]) * (y2 - y0) - (d2[1] - d0[1]) * (y1 - y0)) / det, d = ((d2[1] - d0[1]) * (x1 - x0) - (d1[1] - d0[1]) * (x2 - x0)) / det;
      const cx = (d0[0] + d1[0] + d2[0]) / 3, cy = (d0[1] + d1[1] + d2[1]) / 3, grow = p => [p[0] + (p[0] - cx) * .02, p[1] + (p[1] - cy) * .02];
      g.save(); g.beginPath(); for (const [i, p] of [d0, d1, d2].map(grow).entries()) i ? g.lineTo(p[0], p[1]) : g.moveTo(p[0], p[1]); g.closePath(); g.clip();
      g.setTransform(a, b, c2, d, d0[0] - a * x0 - c2 * y0, d0[1] - b * x0 - d * y0); g.drawImage(img, 0, 0); g.restore();
    };
    for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) {
      const u0 = i / n, u1 = (i + 1) / n, v0 = j / n, v1 = (j + 1) / n, S = (u, v) => [sx + sw * u, sy + sh * v];
      tri(S(u0, v0), S(u1, v0), S(u1, v1), P(u0, v0), P(u1, v0), P(u1, v1)); tri(S(u0, v0), S(u1, v1), S(u0, v1), P(u0, v0), P(u1, v1), P(u0, v1));
    }
  }
  // turns: [[t0, name]]: the card named lands at t0 (song seconds); the page turns on the six drawings before it
  function ots(X, t, turns) {
    if (!O.quads) return;
    const tq = Math.floor(t * 12 + 1e-6) / 12;
    let before = 'notes', after = 'notes', d = 99;
    for (const [t0, name] of turns) { const k = Math.floor((tq - (t0 - 6 / 12)) * 12 + 1e-6); if (k >= 0) { before = after; after = name; d = k; } }
    const draw = d <= 1 ? 'turn1' : d <= 4 ? 'turn2' : 'ots', L = after, R = d <= 4 ? before : after;   // (the old right page until the turned one lands)
    const c = O.buf || (O.buf = Object.assign(document.createElement('canvas'), { width: W, height: H })), g = c.getContext('2d');
    g.setTransform(1, 0, 0, 1, 0, 0); g.clearRect(0, 0, W, H);
    quadMap(g, spreadImg(L), 0, 0, 490, 520, O.quads.left); quadMap(g, spreadImg(R), 490, 0, 490, 520, O.quads.right);
    g.setTransform(1, 0, 0, 1, 0, 0); g.globalCompositeOperation = 'destination-in'; g.drawImage(O.mask[draw], 0, 0); g.globalCompositeOperation = 'source-over';
    X.save(); X.setTransform(1, 0, 0, 1, 0, 0);
    X.drawImage(O.img[draw], 0, 0, W, H);
    X.globalCompositeOperation = 'multiply'; X.drawImage(c, 0, 0); X.globalCompositeOperation = 'source-over';
    // the lantern at her knee (bottom right): its warm light breathing on the page
    const fl = 1 + .05 * Math.sin(t * 8.3) * Math.sin(t * 2.9); X.globalCompositeOperation = 'lighter';
    const gr = X.createRadialGradient(1840, 1010, 20, 1840, 1010, 520 * fl); gr.addColorStop(0, 'rgba(244,201,122,.28)'); gr.addColorStop(.4, 'rgba(244,170,90,.08)'); gr.addColorStop(1, 'rgba(244,170,90,0)');
    X.fillStyle = gr; X.fillRect(1200, 400, 720, 680);
    X.restore();
  }
  return { load: async () => { await load(); await loadOts(); }, draw, cue, ots, M };
})();
