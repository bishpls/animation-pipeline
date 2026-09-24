// film.js: WORDS ARE FOSSILS. One shot: a continuous descent through a core sample, then a rush back to the surface.
// Vertical 1080x1920. Social safe area: keep text out of the bottom ~420 px and the right ~140 px.

const SAFE = { capY: 1395 };
const FILM_START = 1.1667;          // the cut starts here (28 frames in): straight onto the first spoken line
const FORMS = new Set(['vindauga.', 'com,', 'panis.', 'musculus.', 'dis,', 'astro.', 'sal:', 'ye.']);   // spoken fossils: italic ox in captions

// ------------------------------------------------------------------ strata
function bandEdge(y, seed, amp = 16) { const p = []; for (let i = 0; i <= 30; i++) p.push([i / 30 * (W + 80) - 40, y + noise1(seed + i * .37) * amp + noise1(seed * 3 + i * 1.3) * amp * .35]); return p; }
function band(y0, y1, spec, seed) {
  const top = bandEdge(y0, seed), bot = bandEdge(y1, seed + 11).reverse();
  const path = P(top.concat(bot));
  if (spec) paint(path, spec); else knock(path, null);
  return path;
}
// sediment: pebbles (paper specks), hairline beds, the odd tiny shell. Stable per band.
function sediment(y0, y1, ink, seed) {
  if (!ink) return;
  const R = rng(seed * 7 + 3);
  for (let i = 0; i < 26; i++) {
    const x = R() * W, y = lerp(y0 + 40, y1 - 40, R()), r = 2 + R() * 7;
    knock(P(ellipse(x, y, r * (1 + R()), r, R() * 3, 10)), [ink]);
  }
  for (let i = 0; i < 3; i++) {
    const y = lerp(y0 + 60, y1 - 60, R()), pts = [];
    for (let k = 0; k <= 20; k++) pts.push([k / 20 * W, y + noise1(seed + i * 9 + k * .4) * 10]);
    knock(P(pts, false), [ink], .9, { stroke: 1.6, dash: [60 + R() * 80, 20 + R() * 40] });
  }
  if (R() > .35) { const x = 90 + R() * (W - 180), y = lerp(y0 + 80, y1 - 80, R()); shell(x, y, 14 + R() * 10, ink, R() * 6); }
}
function shell(x, y, r, ink, rot0) {         // a tiny ammonite: a spiral
  const p = []; for (let i = 0; i < 60; i++) { const a = rot0 + i * .22, rr = r * Math.exp(-i * .03); p.push([x + Math.cos(a) * rr, y + Math.sin(a) * rr]); }
  knock(P(p, false), [ink], 1, { stroke: 1.8 });
}

// ------------------------------------------------------------------ type that stamps in
const inkOf = s => (s ? { [s]: 1 } : null);
function stampText(str, x, y, t, t0, o) {
  const L = shape(str, o);
  if (t < t0) return L;
  drawText(L, x, y, o.onInk ? null : o.ink, { align: o.align || 'center', knock: !!o.onInk, knockInks: o.onInk ? [o.onInk] : null, opaque: true,
    per: (g, i) => { const a = t - (t0 + i * (o.stagger ?? .035)); if (a < 0) return { skip: true }; const u = E.out3(clamp(a / .16)); return { sc: 1 + .35 * (1 - u), dy: -18 * (1 - u) }; } });
  return L;
}
function label(txt, y, t, t0, onInk, colInk = 'black') {
  if (t < t0) return;
  const a = E.out3(clamp((t - t0) / .3));
  const L = shape(txt, { font: 'arch', size: 30, wdth: 100, wght: 700, track: .18 });
  const x0 = W / 2 - L.width / 2;
  drawText(L, W / 2, y, onInk ? null : colInk, { align: 'center', knock: !!onInk, knockInks: onInk ? [onInk] : null });
  const rule = (xa, xb) => onInk ? knock(P([[xa, y - 10], [xb, y - 10]], false), [onInk], 1, { stroke: 2 }) : ink(P([[xa, y - 10], [xb, y - 10]], false), colInk, { stroke: 2 });
  rule(x0 - 30 - 90 * a, x0 - 30); rule(x0 + L.width + 30, x0 + L.width + 30 + 90 * a);
}

// ------------------------------------------------------------------ one stop's content
function drawStop(s, t) {
  const g = s.kind === 'surface' ? null : s.ink, cy = s.cy;
  const lt = t - s.t;
  if (s.kind === 'surface') {
    label(s.label, cy - 150, t, s.t - .2, null, 'ox');
    const n = s.text.length, size = n > 8 ? 190 : 230;
    stampText(s.text, W / 2, cy + 60, t, s.t, { font: 'slab', size, ink: 'black', stagger: .03 });
    if (lt > 0) ink(P([[W / 2 - 60, cy + 130], [W / 2 + 60, cy + 130]], false), 'ox', { stroke: 4 });
  } else if (s.kind === 'form') {
    label(s.label, cy - 170, t, s.t - .1, g);
    stampText(s.text, W / 2, cy + 40, t, s.t, { font: s.font, size: s.size || 170, onInk: g, wght: 700 });
    if (s.sub) stampText(s.sub, W / 2, cy + 150, t, s.t + .6, { font: 'garaI', size: 64, onInk: g, stagger: .02 });
  } else if (s.kind === 'split' || s.kind === 'split1') {
    label(s.label, cy - 190, t, s.t - .1, g);
    const parts = s.parts || [s.text], gl = Array.isArray(s.gloss) ? s.gloss : [s.gloss];
    let sz = s.font === 'roman' ? 138 : 150;
    const meas = z => parts.map(p => shape(p, { font: s.font, size: z, wght: 700 })).reduce((a, L) => a + L.width, 0) + (parts.length - 1) * (z * .75 + 100);
    sz = Math.min(sz, sz * (W - 170) / meas(sz));                     // fit the frame
    const Ls = parts.map(p => shape(p, { font: s.font, size: sz, wght: 700 }));
    const plus = shape('+', { font: 'gara', size: sz * .8 });
    const gap = 50, total = Ls.reduce((a, L) => a + L.width, 0) + (Ls.length - 1) * (plus.width + gap * 2);
    let x = W / 2 - total / 2;
    Ls.forEach((L, i) => {
      const tt = s.t + i * .25;
      stampText(parts[i], x + L.width / 2, cy + 20, t, tt, { font: s.font, size: sz, onInk: g, wght: 700 });
      if (t > tt + .28) {       // the gloss under each part, hung from a hairline
        const a = E.out3(clamp((t - tt - .28) / .25));
        knock(P([[x + L.width / 2, cy + 50], [x + L.width / 2, cy + 50 + 50 * a]], false), [g], 1, { stroke: 2 });
        stampText(gl[i], x + L.width / 2, cy + 190, t, tt + .3, { font: 'garaI', size: 96, onInk: g, stagger: .025 });
      }
      x += L.width;
      if (i < Ls.length - 1) { if (t > s.t + .2) drawText(plus, x + gap + plus.width / 2, cy + 5, null, { align: 'center', knock: true, knockInks: [g] }); x += plus.width + gap * 2; }
    });
  } else if (s.kind === 'plate') {
    if (window.PICTO && PICTO[s.picto]) PICTO[s.picto](W / 2, cy - 30, 1, t, lt, g, { stampAt: s.stampT != null ? s.stampT - s.t : null });
    else if (lt > 0) { ink(P(circle(W / 2, cy - 30, 300)), g === 'ox' ? 'black' : 'ox', { stroke: 6 }); }
    stampText(s.fig, W / 2, cy + 440, t, s.t + .5, { font: 'garaI', size: 54, onInk: g, stagger: .015 });
  }
}

// ------------------------------------------------------------------ the top: the title plate (intro) and the fresh layer (outro)
function topOfWorld(t) {
  // the fresh layer (outro): a thin new stratum being laid down across the paper, a cursor riding its tip
  const OV = VO.find(v => v.id === '09_outro'), ow = OV.words, k0 = ow.findIndex(w => /^some/i.test(w.w));
  if (t > 78) {
    // the cursor types the second sentence onto a fresh layer, word by word as it's spoken; the ochre layer grows beneath
    const y = 700, typed = ow.slice(k0).filter(w => t >= w.t0 - .04).map(w => w.w).join(' ');
    const L = shape(typed || ' ', { font: 'garaI', size: 58 }), full = shape(ow.slice(k0).map(w => w.w).join(' '), { font: 'garaI', size: 58 });
    const x0 = W / 2 - full.width / 2;
    if (typed) drawText(L, x0, y - 22, 'black', { opaque: true });
    const x1 = typed ? x0 + L.width : x0;
    if (typed) paint(P(cut(rect(x0 - 10, y, x1 - x0 + 20, 16), 5, .8, .3)), { ochre: 1 });
    if (Math.floor(t * 1.8) % 2 === 0 || (typed && t < ow[ow.length - 1].t1 + .2)) paint(P(rect(x1 + 12, y - 70, 7, 86)), 'black');
  }
  // the title plate: an ammonite with the first line spiralling into it, then the title in wood type
  const ay = 1250, ar = 330;
  const press = E.out3(clamp((t - FILM_START) / .45));
  ammonite(W / 2, ay, ar * (1.12 - .12 * press), t);
  const V = VO[0], OW = VO.find(v => v.id === '09_outro').words;
  spiralText(V.words.map((w, i) => ({ ...w, again: OW[i] && i < 7 ? OW[i].t0 : null })), W / 2, ay, ar, t);
  const tw = VO[0].words, tt = tw[1].t0;                 // WORDS on "word", ARE FOSSILS on "fossil"
  stampText('WORDS', W / 2, 1760, t, tt, { font: 'slab', size: 150, ink: 'black', stagger: .05 });
  stampText('ARE FOSSILS', W / 2, 1900, t, tw[tw.length - 1].t0, { font: 'slab', size: 108, ink: 'ox', stagger: .04 });
}
function ammonite(cx, cy, r, t) {
  // chambers: a logarithmic spiral with septa (ribs); slate line-screen body, paper ribs
  const turns = 3.2, pts = [];
  for (let i = 0; i <= 240; i++) { const a = i / 240 * turns * TAU, rr = r * Math.exp(-a * .17); pts.push([cx + Math.cos(a + t * .05) * rr, cy + Math.sin(a + t * .05) * rr]); }
  paint(P(cut(circle(cx, cy, r * 1.03, 72), 71, 2.2)), { slate: .55 });
  ink(P(pts, false), 'black', { stroke: 7 });
  for (let i = 0; i < 44; i++) {        // ribs
    const a = i / 44 * turns * TAU + t * .05, rr = r * Math.exp(-(i / 44 * turns * TAU) * .17), rr2 = rr * Math.exp(-TAU * .17);
    knock(P([[cx + Math.cos(a) * rr * .97, cy + Math.sin(a) * rr * .97], [cx + Math.cos(a + .12) * rr2 * 1.02, cy + Math.sin(a + .12) * rr2 * 1.02]], false), ['slate'], 1, { stroke: 3.5 });
  }
  ink(P(cut(circle(cx, cy, r * 1.03, 72), 71, 2.2)), 'black', { stroke: 8 });
}
function spiralText(words, cx, cy, r, t) {
  // the first line prints along the ammonite's outer whorl, word by word as it's spoken
  let a = -Math.PI * .95;
  for (const w of words) {
    const L = shape(w.w.replace(/[.]/g, ''), { font: 'garaI', size: 64 });
    const rr = r * 1.14;
    for (const g of L.glyphs) {
      const ga = a + (g.x + g.w / 2) / rr;
      if (t >= w.t0 - .05) {
        const u = E.out3(clamp((t - w.t0 + .05) / .2));
        const px = cx + Math.cos(ga) * rr, py = cy + Math.sin(ga) * rr;
        save(); translate(px, py); rotate(ga + Math.PI / 2); scale(1 + .3 * (1 - u));
        drawText({ ...L, glyphs: [g], width: g.w }, -g.w / 2 - g.x, 0, w.again != null && t >= w.again ? 'ox' : 'black', { opaque: true });
        restore();
      }
    }
    a += (L.width + 22) / rr;
  }
}

// ------------------------------------------------------------------ captions: the narrator, as a museum label card
function captions(t) {
  const V = VO.find(v => t >= v.t0 - .1 && t < v.t1 + .7); if (!V || V.id === '00_intro' || V.id === '09_outro') return;   // the outro speaks through the spiral and the cursor
  // phrases: break the line at sentence punctuation
  const ph = [[]]; V.words.forEach(w => { ph[ph.length - 1].push(w); if (/[.?:!]$|\.\.\.$/.test(w.w)) ph.push([]); });
  const P0 = ph.filter(p => p.length);
  let cur = P0[0]; for (const p of P0) if (t >= p[0].t0 - .08) cur = p;
  const size = 74, font = 'gara';
  const Ls = cur.map(w => ({ w, L: shape(w.w, { font: FORMS.has(w.w.toLowerCase()) ? 'garaI' : font, size, wght: 500 }) }));
  const sp = size * .28, maxW = 860;
  const rows = [[]]; let rw = 0;
  for (const it of Ls) { if (rw + it.L.width > maxW && rows[rows.length - 1].length) { rows.push([]); rw = 0; } rows[rows.length - 1].push(it); rw += it.L.width + sp; }
  const lh = size * 1.18, cardW = Math.max(...rows.map(r => r.reduce((a, it) => a + it.L.width, 0) + sp * (r.length - 1))) + 90;
  const ent = E.back(clamp((t - (cur[0].t0 - .08)) / .15));
  save(); translate(W / 2, SAFE.capY); scale(.94 + .06 * ent); translate(-W / 2, -SAFE.capY + (1 - ent) * 18);
  const cardH = rows.length * lh + 56, cy = V.id === '09_outro' ? 430 : SAFE.capY, y0 = cy - cardH / 2;   // the outro's card sits under the fresh layer, clear of the title
  const card = P(cut(rect(W / 2 - cardW / 2, y0, cardW, cardH), 3, .6, .2));
  knock(card, null); ink(card, 'black', { stroke: 3 });
  ink(P(rect(W / 2 - cardW / 2 + 9, y0 + 9, cardW - 18, cardH - 18)), 'black', { stroke: 1.2 });
  rows.forEach((r, ri) => {
    const rwid = r.reduce((a, it) => a + it.L.width, 0) + sp * (r.length - 1);
    let x = W / 2 - rwid / 2; const y = y0 + 28 + (ri + 1) * lh - size * .28;
    for (const it of r) {
      if (t >= it.w.t0 - .04) drawText(it.L, x, y, FORMS.has(it.w.w.toLowerCase()) ? 'ox' : 'black', { opaque: true });
      x += it.L.width + sp;
    }
  });
  restore();
}

// ------------------------------------------------------------------ the frame
function frame(t) {
  const cyW = camY(t), top = cyW - COL.stopY;          // world y at the top of the screen
  const speed = Math.abs(camY(t + 1 / 24) - camY(t - 1 / 24)) * 12;   // px per second (for the rush's smear)
  save(); translate(0, -top);
  // bands in view
  if (top < 2250) { band(-400, 2200, null, 1); topOfWorld(t); }
  WORDS.forEach((w, wi) => {
    if (w.y1 < top - 200 || w.y0 > top + H + 200) return;
    w.stops.forEach((s, si) => {
      if (s.y1 < top - 200 || s.y0 > top + H + 200) return;
      band(s.y0, s.y1 + 30, s.kind === 'surface' ? null : { [s.ink]: 1 }, wi * 17 + si * 5);
      if (s.kind !== 'surface') sediment(s.y0, s.y1, s.ink, wi * 17 + si * 5);
    });
    // the core break between samples: a black seam with the specimen number
    const gy = w.y1 + 10;
    band(gy, gy + BAND.gap - 20, { black: 1 }, wi * 31 + 7);
    const no = `No. ${String(wi + 1).padStart(2, '0')}`;
    type(no, W / 2, gy + BAND.gap / 2 + 4, { font: 'arch', size: 30, wdth: 100, wght: 700, track: .2, align: 'center', knock: true, knockInks: ['black'] });
  });
  for (const s of LAYOUT.stops) if (s.y1 > top - 200 && s.y0 < top + H + 200) drawStop(s, t);
  restore();
  // the rush: speed lines scratched through the strata while flying up
  if (speed > 6000) { const a = clamp((speed - 6000) / 6000); for (let i = 0; i < 14; i++) { const x = 60 + hash(i * 3.3 + BF(t)) * (W - 120); knock(P([[x, 0], [x, H]], false), null, .5 * a, { stroke: 2 + hash(i) * 3 }); } }
  captions(t);
  // the last card
  if (t > 84.6) {
    const a = E.out3(seg(t, 84.6, 85.3));
    save(); translate(0, -(camY(t) - COL.stopY));
    stampText('made entirely in code by Claude', W / 2, 790, t, 84.9, { font: 'garaI', size: 46, ink: 'black', stagger: .012 });
    restore();
  }
  return { lyric: false };
}

function registerFilm() { shots([[0, frame]]); }
