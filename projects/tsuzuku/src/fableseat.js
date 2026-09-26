// fableseat.js: Fable in her room during Clawd's world A (her ruling on Michael's structure, CLAWDWORLD.md): Clawd's world is a
// card in her butai, and she sits outside it, seiza on her cushion at the butai's right (the teller's side), seen three-quarters
// from behind, facing the window; her warm lantern (the bridge's chōchin) on the floor at her left, between her and the butai.
// Annotating (chorus 1), pulling the cards and watching (verse 2), joining in (chorus 2): the escalation is the story. An
// illustrated puppet from rig/fable_seated (GPT Image drawings of one pose set, registered and cut by build.py), drawn mirrored
// to face the window: one drawing per arm pose, swapped on a snap; a nod, a head tilt and a seated weight shift warped in strips;
// the ribbon on its own layer. Her clock, not Clawd's: everything is sampled on twos (12 drawings a second) and held. No springs.
//   FABLESEAT.draw(X, t, T, light)   T = {x, y, s, flip}: the seat point on screen, screen px per drawing px, mirrored
//   FABLESEAT.cue(t)                 {pose, nod, lean, sway, tilt} on the song clock (bars below are SONG bars)
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
  const PULLS = [[67, 67.2, 67.75], [70, 70.08, 70.42]];                     // [she reaches, the edge starts, it's through] (idolstage CARD_PULLS)
  const inAny = (b, W) => W.some(([a, z]) => b >= a && b < z);
  // pincer snips (both hands up as a crab's claws, Michael): open between, shut on each snip
  const snip = (b, hits, end) => hits.some(h => b >= h && b < h + .1) ? 'pincersnip' : b < end ? 'pincers' : null;
  function cue(t) {
    const tq = Math.floor(t * 12 + 1e-6) / 12, b = tq / BR, f = b - Math.floor(b), bar = Math.floor(b);
    const beat = Math.floor(b * 4), qb = b * 4 - beat;                          // Clawd's beat and its phase
    let pose = 'rest', nod = 0, lean = 0, sway = 0, tilt = 0;
    const breath = Math.round(4 * Math.sin(2 * Math.PI * b / 2)) / 4;          // she's always in frame: a slow breath, stepped
    // chorus 1, annotating: a nod on the one, the ribbon on the offbeat. 52: a small head bob side to side on her pulse. 56: she's
    // more into it: left-left, right-right on the beats (Michael), a nod on every beat, the shoulders going with it
    if (b >= 46 && b < 62) {
      nod = f < .06 ? .4 : f < .3 ? .7 : f < .36 ? .3 : 0;
      sway = (f >= .5 && f < .56 ? .5 : f >= .56 && f < .9 ? 1 : f >= .9 ? .4 : 0) * (bar % 2 ? -1 : 1);
      if (b >= 52 && b < 56) { const h = (b * 2) % 1, side = Math.floor(b * 2) % 2 ? -1 : 1; tilt = side * (h < .12 ? .5 : h < .88 ? 1 : .5); nod *= .5; }
      if (b >= 56) { const side = Math.floor(beat / 2) % 2 ? -1 : 1; tilt = side * (qb < .15 ? 1.1 : 1.5); nod = qb < .12 ? .5 : qb < .4 ? 1 : qb < .5 ? .4 : 0; lean = side * .45; }
    }
    for (const p of PRESSES) if (b >= p - .55 && b < p + .8) { pose = 'write'; if (b >= p - .06 && b < p + .3) nod = Math.max(nod, .7); }
    // "Sideways, sideways!": one seated weight shift each way (54.00, 54.49)
    if (b >= 54 && b < 55.05) lean = b < 54.06 ? -.5 : b < 54.49 ? -1 : b < 54.55 ? 0 : b < 54.98 ? 1 : .4;
    // the hook: hand to ear on the call, two low claps with the hall, the wipe with her on 65
    if (b >= 62 && b < 66) {
      pose = (b >= 62 && b < 62.4) || (b >= 64 && b < 64.4) ? 'ear' : 'rest';
      for (let i = 0; i < CLAPS.length; i += 2) { const [c1, c2] = [CLAPS[i], CLAPS[i + 1]];
        if (b >= c1 - .1 && b < c2 + .14) pose = (b >= c1 && b < c1 + .12) || b >= c2 ? 'clap' : 'clapopen'; }
      if (b >= 65 && b < 65.4) pose = b < 65.07 ? 'write' : b < 65.2 ? 'wipe0' : 'wipe1';
      nod = pose === 'ear' ? .3 : 0; sway = 0; tilt = 0;
    }
    // verse 2, watching and pulling the cards. The card slides out of Clawd's screen into her hand (idolstage draws it); on "a
    // little crab" both hands go up as pincers and snip with her; the second pull is livelier (she's getting into it), and she
    // answers "Sorekara?" (her own call) with a hand to her ear
    if (b >= 66 && b < 82) {
      nod = b < 72 ? (qb < .12 ? .25 : qb < .3 ? .5 : 0) : 0;
      // (67-68 and 70-70.7: the over-the-shoulder page turns; her room drawing isn't on screen)
      const s1 = snip(b, [68.25, 68.5], 68.85); if (b >= 68.17 && s1) { pose = s1; nod = 0; tilt = qb < .5 ? .6 : -.6; }
      const s2 = snip(b, [70.77, 71.02, 71.27], 71.5); if (b >= 70.7 && s2) { pose = s2; lean = Math.floor(beat) % 2 ? .5 : -.5; tilt = -lean * 1.2; nod = qb < .3 ? .6 : 0; }
      if (b >= 80.9 && b < 81.5) { pose = 'ear'; tilt = .5; }
      if (b >= 72 && !(b >= 80.9 && b < 81.5)) { sway = 0; tilt = .25 * Math.round(2 * Math.sin(2 * Math.PI * b / 4)) / 2; }   // watching, following her
    }
    // chorus 2, joining: she claps with the hall on the backbeat (half, CLAP, half, open), bobbing on the beat; 86: pincers with
    // Clawd's claws, snipping on every beat; 87: back to clapping, now with the seated sideways shift and the head going with it
    if (b >= 82 && b < 90) {
      const q = ((b * 4 - 1) % 2 + 2) % 2 / 2;                                 // 0 on beats 2 and 4
      pose = q < .1 ? 'clap' : q < .2 ? 'clapmid' : q < .88 ? 'clapopen' : 'clapmid';
      nod = qb < .15 ? .35 : qb < .5 ? .8 : qb < .62 ? .35 : 0;
      if (b >= 86 && b < 87) { pose = qb < .3 ? 'pincersnip' : 'pincers'; const side = beat % 2 ? -1 : 1; lean = side * .6; tilt = -side; }
      if (b >= 87) { const side = Math.floor(b * 2) % 2 ? -1 : 1, h = (b * 2) % 1; lean = side * (h < .12 ? .5 : h < .9 ? 1.1 : .5); tilt = -side * (h < .12 ? .5 : 1); }
      if (b >= 84.24 - .55 && b < 84.24 + .8) { pose = 'write'; lean = 0; tilt = 0; }
    }
    if (b >= 90) { pose = 'rest'; nod = 0; sway = 0; tilt = 0; lean = 0; }       // the lights die: still, the lantern lit
    return { pose, nod, lean, sway, tilt, breath, b };
  }

  // ---- the drawing, warped in strips (cached per state: she holds, so most frames hit)
  function warped(st) {
    const key = [st.pose, st.nod.toFixed(2), st.lean.toFixed(2), st.sway.toFixed(2), st.tilt.toFixed(2), (st.breath || 0).toFixed(2)].join('|');
    if (M.cache.has(key)) return M.cache.get(key);
    const [w, h] = M.meta.size, P = M.meta.pivots, c = document.createElement('canvas'); c.width = w; c.height = h; const g = c.getContext('2d');
    const hood = y => 1 - sm(P.neck[1] - 80, P.neck[1] + 30, y);
    const dy = y => st.nod * 26 * hood(y)                                                    // the hood drops forward
                  - (st.breath || 0) * 5 * clamp((P.hem[1] - y) / (P.hem[1] - P.crown[1]));   // and the whole back rises with a breath
    const dx = y => st.lean * 34 * clamp((P.hem[1] - y) / (P.hem[1] - P.crown[1])) ** 1.2   // the torso rocks over the seat
                  + st.tilt * 20 * hood(y) * clamp((P.neck[1] - y) / (P.neck[1] - P.crown[1]));   // the head tips side to side
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
    if (M.cache.size > 96) M.cache.delete(M.cache.keys().next().value);
    M.cache.set(key, c); return c;
  }

  function draw(X, t, T, light = 1) {
    if (!M.meta) return;
    const st = cue(t), P = M.meta.pivots, [w, h] = M.meta.size, fig = warped(st);
    X.save(); X.translate(T.x, T.y); X.scale(T.flip ? -T.s : T.s, T.s); X.translate(-P.seat[0], -P.seat[1]);
    X.filter = `brightness(${(.58 + .3 * light).toFixed(3)})`;                      // in her dark room, lit by the window and her lantern
    X.drawImage(M.img.lantern, 0, 0, w, h); X.drawImage(fig, 0, 0, w, h); X.filter = 'none';
    // her lantern: a warm core (#F4C97A) through washi; it lights her side and the cushion, and the floor round it
    const [lx, ly] = P.lantern, fl = 1 + .04 * Math.sin(t * 9.1) * Math.sin(t * 3.3);
    X.globalCompositeOperation = 'lighter';
    let g = X.createRadialGradient(lx, ly, 10, lx, ly, 380 * fl);
    g.addColorStop(0, 'rgba(244,190,110,.34)'); g.addColorStop(.35, 'rgba(244,160,80,.13)'); g.addColorStop(1, 'rgba(244,160,80,0)');
    X.fillStyle = g; X.fillRect(lx - 390, ly - 390, 780, 780);
    g = X.createRadialGradient(lx, ly, 4, lx, ly, 130); g.addColorStop(0, 'rgba(255,214,150,.4)'); g.addColorStop(1, 'rgba(255,214,150,0)');
    X.fillStyle = g; X.fillRect(lx - 140, ly - 140, 280, 280);
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
    await Promise.all(['ots', 'turn1', 'turn2', 'write'].map(async d => { O.img[d] = await get(`ots_${d}.png`); O.mask[d] = await get(`ots_${d}_page.png`); }));
  }
  // her book: the fable printed on the left page, and on the right page, in the margin's Caslon italic and her lighter ink, the
  // notes she writes (k of them so far, the last one written to `frac`: it writes on under her brush, with the margin's press)
  const NOTES = [['Every story’s borrowed', 'till somebody stands', 'to tell it.'], ['I’ve read how it ends.', 'I’d still like to see.'], ['That’s the moral.', 'There isn’t one.', 'Keep walking.']];
  const FABLE_TEXT = ['The Crab and her Mother.', '', 'A mother crab said to her', 'child, “Why do you walk', 'sideways? Walk straight.”', 'The young crab said,', '“Show me how, and I’ll', 'follow.” The mother tried,', 'and went sideways.'];
  function notesSpread(w, h, k = 3, frac = 1) {
    const c = document.createElement('canvas'); c.width = w; c.height = h; const g = c.getContext('2d'), X0 = X; X = g;
    const text = (str, x, y, font, size, col) => { const L = shape(str, { font, size }); g.fillStyle = col; for (const gl of L.glyphs) if (gl.ch !== ' ') g.fill(glyphPath(gl, x + gl.x, y + gl.y)); return L.width; };
    try {
      g.fillStyle = '#ECE9E1'; g.fillRect(0, 0, w, h);
      const size = h * .05; let y = h * .15;
      FABLE_TEXT.forEach(str => { if (str) text(str, w * .06, y, 'caslon', size * .92, 'rgba(34,28,24,.9)'); y += size * 1.32; });
      y = h * .15;
      NOTES.slice(0, k).forEach((para, j) => {
        const widths = para.map(str => shape(str, { font: 'caslonI', size }).width), total = widths.reduce((a, b) => a + b, 0);
        let left = j === k - 1 ? frac * total : total;
        para.forEach((str, i) => {
          const x = w * .56 + (j === 2 && i ? size * .6 : 0), show = Math.max(0, Math.min(widths[i], left)); left -= widths[i];
          if (show > 0) { g.save(); g.beginPath(); g.rect(x - 4, y - size * 1.1, show + 4, size * 1.6); g.clip(); text(str, x, y, 'caslonI', size, 'rgba(38,32,44,.85)'); g.restore(); }
          if (j === 2 && i === 0 && show >= widths[i]) g.fillRect(x - 4, y - size * .3, widths[i] + 8, Math.max(2, size * .06));   // struck through
          y += size * 1.3;
        });
        y += size * .9;
      });
    } finally { X = X0; }
    return c;
  }
  function spreadImg(name, t) {
    const w = 980, h = 520;
    if (name === 'notes') {                                                   // the notes so far; the newest writes on (on twos)
      const b = Math.floor(t * 12 + 1e-6) / 12 / BR; let k = 0, frac = 1;
      PRESSES.slice(0, 3).forEach((p, i) => { if (b >= p - .04) { k = i + 1; frac = clamp((b - (p - .04)) / .3); } });
      const key = `notes${k}_${frac.toFixed(3)}`; return O.spread[key] || (O.spread[key] = notesSpread(w, h, k, frac));
    }
    if (name === 'story') return typeof IDOLSTAGE !== 'undefined' ? IDOLSTAGE.storySpread(t, w, h) : cardFace('blank', w, h);   // (live: Clawd writing in it)
    const face = n => typeof IDOLSTAGE !== 'undefined' ? IDOLSTAGE.pageFace(n, w, h) : cardFace(n, w, h);
    return O.spread[name] || (O.spread[name] = face(name));
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
  function ots(X, t, turns, o = {}) {
    if (!O.quads) return;
    const tq = Math.floor(t * 12 + 1e-6) / 12;
    let before = o.initial || 'notes', after = o.initial || 'notes', d = 99;
    for (const [t0, name] of turns) { const k = Math.floor((tq - (t0 - 6 / 12)) * 12 + 1e-6); if (k >= 0) { before = after; after = name; d = k; } }
    let draw = d <= 1 ? 'turn1' : d <= 4 ? 'turn2' : 'ots', L = after, R = d <= 4 ? before : after;   // (the old right page until the turned one lands)
    if (o.draw) { draw = o.draw; L = R = o.spread || 'notes'; }
    // mirrored (her room: she faces the window, so we're over her left shoulder): the drawing and its mask flip, the print doesn't
    const mq = p => p.map(([x, y]) => [W - x, y]), sw = m => [m[1], m[0], m[3], m[2]];
    const QL = o.flip ? sw(mq(O.quads.right)) : O.quads.left, QR = o.flip ? sw(mq(O.quads.left)) : O.quads.right;
    const c = O.buf || (O.buf = Object.assign(document.createElement('canvas'), { width: W, height: H })), g = c.getContext('2d');
    g.setTransform(1, 0, 0, 1, 0, 0); g.clearRect(0, 0, W, H);
    quadMap(g, spreadImg(L, t), 0, 0, 490, 520, QL); quadMap(g, spreadImg(R, t), 490, 0, 490, 520, QR);
    g.setTransform(o.flip ? -1 : 1, 0, 0, 1, o.flip ? W : 0, 0); g.globalCompositeOperation = 'destination-in'; g.drawImage(O.mask[draw], 0, 0); g.globalCompositeOperation = 'source-over';
    X.save(); X.setTransform(o.flip ? -1 : 1, 0, 0, 1, o.flip ? W : 0, 0);
    X.drawImage(O.img[draw], 0, 0, W, H); X.setTransform(1, 0, 0, 1, 0, 0);
    X.globalCompositeOperation = 'multiply'; X.drawImage(c, 0, 0); X.globalCompositeOperation = 'source-over';
    // her lantern on the floor at her left, out of frame behind her: its warm light breathing on the page from the left
    const fl = 1 + .05 * Math.sin(t * 8.3) * Math.sin(t * 2.9); X.globalCompositeOperation = 'lighter';
    const gr = X.createRadialGradient(640, 1180, 30, 640, 1180, 820 * fl); gr.addColorStop(0, 'rgba(244,201,122,.30)'); gr.addColorStop(.45, 'rgba(244,170,90,.10)'); gr.addColorStop(1, 'rgba(244,170,90,0)');
    X.fillStyle = gr; X.fillRect(0, 340, 1500, 740);
    X.restore();
  }
  return { load: async () => { await load(); await loadOts(); }, draw, cue, ots, M };
})();
