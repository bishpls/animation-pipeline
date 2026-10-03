// engine/meleetype.js: Melee's own text (the game's word graphics, menu font, HUD digits and name plates, extracted from the
// disc by tools/machinima/melee/type/). Promoted from SO BACK. Plain Canvas2D, global functions like plate.js/edit.js.
//   await MT.load()                       // once, before rendering (loads manifest.js and every image; ~120 small PNGs)
//   mword('game', x, y, { h: 220 })       // the game's own graphic for a word, centred on (x, y), h px tall
//   mtext("WE'RE SO BACK", x, y, { size: 180, style: 'game' })   // our words in the game's menu font, dressed like its
//                                          // word graphics: black outline, white inner stroke, gradient fill with streaks
//   mname('falcon', x, y, { h: 70, set: 'banner' | 'label', panel: true })   // the results screen's name plate
//   mdigits('5.5', x, y, { h: 300 })      // the HUD's damage digits (the percent font); '.' and '%' included
//   mtext('↓ + B (hold to ★3)', x, y, { size: 64, sym: true })   // sym: symbols the font lacks, drawn as glyphs in its
//                                          // dress: arrows ↑↗→↘↓↙←↖ and [A:22.5] (any angle, 0 right, 90 up), ★, ·, °
// (x, y) is the centre of the text's cap height; align: 'center' (default) | 'left' | 'right'.
// Game-derived images live outside the repo (e.g. ~/games/melee/type, served through the film's assets/plates symlink):
// pass their served path to MT.load(base).
const MT = { base: 'assets/plates/melee_type', img: {}, M: null, cache: new Map() };

// the word graphics' own fills (measured per row inside the letters of each IfAll word graphic: dark at the top, saturated,
// bright at the bottom), plus their light diagonal streaks
const MT_STYLES = {
  game:     { stops: [[0, '#1c0008'], [.42, '#4a0010'], [.7, '#ac0018'], [1, '#ff6848']], streak: '#ffd0c0' },
  time:     { stops: [[0, '#04061e'], [.42, '#08104a'], [.7, '#181894'], [1, '#6a48e0']], streak: '#c8c0ff' },
  failure:  { stops: [[0, '#06061c'], [.42, '#181841'], [.7, '#4129a4'], [1, '#8f5cf0']], streak: '#d8c8ff' },
  success:  { stops: [[0, '#101006'], [.42, '#403414'], [.7, '#a48331'], [1, '#fff27a']], streak: '#fffbd0' },
  go:       { stops: [[0, '#140a04'], [.42, '#4a2918'], [.7, '#b0661e'], [1, '#ffd05a']], streak: '#fff0c0' },
  complete: { stops: [[0, '#120804'], [.42, '#502010'], [.7, '#cd5a29'], [1, '#ffa050']], streak: '#ffe0b0' },
  death:    { stops: [[0, '#120004'], [.42, '#521820'], [.7, '#a43141'], [1, '#ec6a6a']], streak: '#ffd0d0' },
  white:    { stops: [[0, '#ffffff'], [1, '#ffffff']], streak: null },
};

MT.load = async function (base) {
  if (base) MT.base = base;
  if (!window.MTYPE) await new Promise((ok, bad) => { const s = document.createElement('script'); s.src = MT.base + '/manifest.js'; s.onload = ok; s.onerror = () => bad(new Error('meleetype: no manifest at ' + MT.base)); document.head.appendChild(s); });
  MT.M = window.MTYPE;
  const want = [['font', MT.M.font.atlas]];
  for (const k in MT.M.words) want.push(['w:' + k, `words/${k}.png`]);
  for (const k in MT.M.hud) want.push(['h:' + k, `hud/${k}.png`]);
  for (const set of ['banner', 'label']) for (const k in MT.M.names[set]) want.push([`n:${set}:${k}`, `names/${set}/${k}.png`]);
  await Promise.all(want.map(([k, p]) => new Promise(ok => { const im = new Image(); im.onload = () => { MT.img[k] = im; ok(); }; im.onerror = () => ok(); im.src = `${MT.base}/${p}`; })));
};

// a scratch canvas per key (sized on demand)
function mtBuf(key, w, h) {
  let b = MT[key]; if (!b) { const c = document.createElement('canvas'); b = MT[key] = { c, x: c.getContext('2d') }; }
  if (b.c.width < w || b.c.height < h) { b.c.width = Math.max(b.c.width, w); b.c.height = Math.max(b.c.height, h); }
  b.x.setTransform(1, 0, 0, 1, 0, 0); b.x.globalCompositeOperation = 'source-over'; b.x.globalAlpha = 1; b.x.clearRect(0, 0, b.c.width, b.c.height);
  return b;
}
const mtAnchor = (w, align) => (align === 'left' ? 0 : align === 'right' ? -w : -w / 2);

// ---- the game's word graphics, as they are (tint: colour the white-intensity ones, e.g. the GAME OVER letters)
function mword(name, x, y, o = {}) {
  const im = MT.img['w:' + name], m = MT.M && MT.M.words[name]; if (!im || !m) return;
  const h = o.h || m.h, w = o.w || m.w * h / m.h;
  X.save(); X.translate(x + mtAnchor(w, o.align), y - h / 2);
  if (o.tint) {
    const b = mtBuf('tint', Math.ceil(w), Math.ceil(h)); b.x.drawImage(im, 0, 0, w, h);
    b.x.globalCompositeOperation = 'source-in'; b.x.fillStyle = o.tint; b.x.fillRect(0, 0, w, h);
    X.drawImage(b.c, 0, 0, w, h, 0, 0, w, h);
  } else X.drawImage(im, 0, 0, w, h);
  X.restore();
  return { w, h };
}

// ---- our words in the game's menu font, dressed like the word graphics
// symbols the menu font lacks (opt-in, o.sym): drawn into the letters' mask, so they take the same outline, stroke and fill.
// adv: the advance as a share of the size
const MT_ARROWS = { '↑': 90, '↗': 45, '→': 0, '↘': -45, '↓': -90, '↙': -135, '←': 180, '↖': 135 };
const MT_SYM_ADV = { arrow: .84, star: .8, dot: .36, deg: .3 };
function mtTokens(str, sym) {
  if (!sym) return [...str];
  const out = [], re = /\[A:(-?[\d.]+)\]|\[(U|UR|R|DR|D|DL|L|UL|STAR|DEG)\]|./gsu;
  const NAMED = { U: 90, UR: 45, R: 0, DR: -45, D: -90, DL: -135, L: 180, UL: 135 };
  for (const m of str.matchAll(re)) {
    if (m[1] !== undefined) out.push({ sym: 'arrow', deg: +m[1] });
    else if (m[2] === 'STAR') out.push({ sym: 'star' });
    else if (m[2] === 'DEG') out.push({ sym: 'deg' });
    else if (m[2] !== undefined) out.push({ sym: 'arrow', deg: NAMED[m[2]] });
    else if (MT_ARROWS[m[0]] !== undefined) out.push({ sym: 'arrow', deg: MT_ARROWS[m[0]] });
    else if (m[0] === '★') out.push({ sym: 'star' });
    else if (m[0] === '·') out.push({ sym: 'dot' });
    else if (m[0] === '°') out.push({ sym: 'deg' });
    else out.push(m[0]);
  }
  return out;
}
function mtLayout(str, size, track = 0, sym = false) {
  const F = MT.M.font, k = size / F.native, out = []; let x = 0;
  for (const ch of mtTokens(str, sym)) {
    if (typeof ch === 'object') {
      const adv = MT_SYM_ADV[ch.sym] * size;
      out.push({ sym: ch.sym, deg: ch.deg, x, adv }); x += adv + track * size; continue;
    }
    if (ch === ' ') { x += size * .32; continue; }
    const g = F.glyphs[ch] || F.glyphs[ch.toUpperCase()] || F.glyphs[{ "'": '’', '-': '−', '"': '”' }[ch] || ''];
    if (!g) { x += size * .5; continue; }
    const [i, left, right] = g, adv = (F.native - left - right) * k;
    out.push({ i, x: x - left * k }); x += adv + track * size;
  }
  return { glyphs: out, w: x - track * size };
}
// a symbol's shape, white, into the mask at its cell (x0, y0 the cell's top left; the caps run ~14%-90% of the cell)
function mtSymbol(c, g, x0, y0, size) {
  const cx = x0 + g.adv / 2, cy = y0 + size * .52;
  c.save(); c.fillStyle = '#fff'; c.translate(cx, cy);
  if (g.sym === 'arrow') {
    c.rotate(-g.deg * Math.PI / 180);
    const L = size * .8, w = size * .19, hw = size * .32, hl = size * .34;
    c.beginPath(); c.moveTo(-L / 2, -w / 2); c.lineTo(L / 2 - hl, -w / 2); c.lineTo(L / 2 - hl, -hw); c.lineTo(L / 2, 0);
    c.lineTo(L / 2 - hl, hw); c.lineTo(L / 2 - hl, w / 2); c.lineTo(-L / 2, w / 2); c.closePath(); c.fill();
  } else if (g.sym === 'star') {
    const R = size * .4, r = R * .45; c.beginPath();
    for (let i = 0; i < 10; i++) { const a = -Math.PI / 2 + i * Math.PI / 5, q = i % 2 ? r : R; c.lineTo(Math.cos(a) * q, Math.sin(a) * q + size * .03); }
    c.closePath(); c.fill();
  } else if (g.sym === 'dot') {
    c.beginPath(); c.arc(0, 0, size * .075, 0, Math.PI * 2); c.fill();
  } else if (g.sym === 'deg') {
    c.translate(0, -size * .25); c.beginPath(); c.arc(0, 0, size * .1, 0, Math.PI * 2); c.arc(0, 0, size * .05, 0, Math.PI * 2, true); c.fill();
  }
  c.restore();
}
function mtext(str, x, y, o = {}) {
  if (!MT.M || !MT.img.font) return;
  const size = o.size || 120, style = MT_STYLES[o.style || 'game'] || MT_STYLES.game;
  const key = [str, size, o.style, o.fill, o.outline, o.track ?? .075, o.stroke, o.shadow, o.sym].join('|');
  let c = MT.cache.get(key);
  if (!c) { c = mtRender(str, size, style, o); MT.cache.set(key, c); if (MT.cache.size > 200) MT.cache.delete(MT.cache.keys().next().value); }
  X.save(); X.translate(x + mtAnchor(c.tw, o.align), y);
  if (o.italic) X.transform(1, 0, -Math.tan(o.italic === true ? .18 : o.italic), 1, 0, 0);
  X.drawImage(c.cv, -c.pad, -c.cy);
  X.restore();
  return { w: c.tw, h: size };
}
function mtRender(str, size, style, o) {
  const F = MT.M.font, L = mtLayout(str, size, o.track ?? .075, !!o.sym), s = size / F.native;
  const ro = o.outline === false ? 0 : (o.outline || .1) * size, rw = o.stroke === 0 ? 0 : (o.stroke || .045) * size;
  const sh = o.shadow === false ? 0 : (o.shadow || .07) * size, pad = Math.ceil(ro + sh + 6);
  const W2 = Math.ceil(L.w + 2 * pad), H2 = Math.ceil(size + 2 * pad);
  // the letters' mask (the atlas's white glyphs)
  const m = mtBuf('mask', W2, H2), cell = F.cell, cols = F.cols;
  for (const g of L.glyphs) {
    if (g.sym) mtSymbol(m.x, g, pad + g.x, pad, size);
    else m.x.drawImage(MT.img.font, (g.i % cols) * cell, Math.floor(g.i / cols) * cell, cell, cell, pad + g.x, pad, size, size);
  }
  // dilate the mask by r into buffer b (stamping on two rings), tinted col
  const dil = (name, r, col, dx = 0, dy = 0) => {
    const b = mtBuf(name, W2, H2);
    if (r <= 0) b.x.drawImage(m.c, dx, dy);
    else for (const rr of [r, r * .5]) for (let i = 0; i < 20; i++) { const a = i / 20 * TAU; b.x.drawImage(m.c, dx + Math.cos(a) * rr, dy + Math.sin(a) * rr); }
    b.x.globalCompositeOperation = 'source-in'; b.x.fillStyle = col; b.x.fillRect(0, 0, W2, H2);
    return b;
  };
  const cv = document.createElement('canvas'); cv.width = W2; cv.height = H2; const x = cv.getContext('2d');
  if (sh) { x.globalAlpha = .55; x.drawImage(dil('d1', ro, '#000', sh * .6, sh).c, 0, 0); x.globalAlpha = 1; }
  if (ro) x.drawImage(dil('d2', ro, '#000').c, 0, 0);
  if (rw) x.drawImage(dil('d3', rw, '#fff').c, 0, 0);
  // the fill: the word graphics' vertical gradient over the cap height, with light diagonal streaks, inside the letters
  const f = mtBuf('fill', W2, H2), top = pad + size * .14, bot = pad + size * .9;
  if (o.fill) f.x.fillStyle = o.fill;
  else { const gr = f.x.createLinearGradient(0, top, 0, bot); style.stops.forEach(([k, col]) => gr.addColorStop(k, col)); f.x.fillStyle = gr; }
  f.x.fillRect(0, 0, W2, H2);
  if (!o.fill && style.streak) {
    f.x.save(); f.x.globalAlpha = .28; f.x.strokeStyle = style.streak; f.x.lineCap = 'round';
    for (let i = 0; i < W2 / (size * .09); i++) {
      const sx = i * size * .09 + hash(i * 7.3 + str.length) * size * .06, y0 = top + (bot - top) * (.35 + .3 * hash(i * 3.1));
      f.x.lineWidth = size * (.008 + .02 * hash(i * 1.7)); f.x.beginPath(); f.x.moveTo(sx, bot); f.x.lineTo(sx + (bot - y0) * .35, y0); f.x.stroke();
    }
    f.x.restore();
  }
  f.x.globalCompositeOperation = 'destination-in'; f.x.drawImage(m.c, 0, 0);
  x.drawImage(f.c, 0, 0);
  // the text's centre: the cap height's middle (the glyph cell's caps run ~14%-90% of the cell)
  return { cv, pad, tw: L.w, cy: pad + size * .52 };
}

// ---- the results screen's name plates (banner: outlined serif caps; label: bold sans caps)
function mname(key, x, y, o = {}) {
  const set = o.set || 'banner', im = MT.img[`n:${set}:${key}`], m = MT.M && MT.M.names[set][key]; if (!im) return;
  const h = o.h || m.h, w = m.w * h / m.h;
  X.save(); X.imageSmoothingQuality = 'high'; X.translate(x + mtAnchor(w, o.align), y - h / 2);
  if (o.panel) {                                                     // a dark plate like the results panel's
    const px = h * .45, py = h * .22; X.fillStyle = o.panel === true ? 'rgba(10,8,24,.88)' : o.panel;
    X.beginPath(); X.roundRect(-px, -py, w + 2 * px, h + 2 * py, h * .25); X.fill();
  }
  if (o.tint) {
    const b = mtBuf('tint', Math.ceil(w), Math.ceil(h)); b.x.drawImage(im, 0, 0, w, h);
    b.x.globalCompositeOperation = 'source-in'; b.x.fillStyle = o.tint; b.x.fillRect(0, 0, w, h); X.drawImage(b.c, 0, 0, w, h, 0, 0, w, h);
  } else X.drawImage(im, 0, 0, w, h);
  X.restore();
  return { w, h };
}

// ---- the HUD's damage digits (the percent font: white, black outline); '.' is drawn in the digits' own style, '%' is the game's
function mdigits(str, x, y, o = {}) {
  const h = o.h || 200, d0 = MT.M && MT.M.hud.dmg_0; if (!d0) return;
  const k = h / d0.h, adv = d0.w * k * .82, parts = [];
  let w = 0;
  for (const ch of str) {
    if (ch >= '0' && ch <= '9') { parts.push([MT.img['h:dmg_' + ch + '_hi'] ? 'h:dmg_' + ch + '_hi' : 'h:dmg_' + ch, w, d0.w * k]); w += adv; }
    else if (ch === '%') { const m = MT.M.hud.dmg_pct; parts.push([MT.img['h:dmg_pct_hi'] ? 'h:dmg_pct_hi' : 'h:dmg_pct', w, m.w * k]); w += m.w * k * .9; }
    else if (ch === '.') { parts.push(['.', w, h * .3]); w += h * .3; }
  }
  // drawn white into a buffer, then (o.color) multiplied so the white takes the colour and the outline stays black, the way
  // the HUD's percent turns yellow, orange and red as damage builds
  w = Math.max(...parts.map(([, px, pw]) => px + pw));                 // the real extent (the last digit's full width)
  const pad = Math.ceil(h * .05), b = mtBuf('digits', Math.ceil(w) + 2 * pad, Math.ceil(h) + 2 * pad);
  b.x.translate(pad, pad);
  for (const [key, px, pw] of parts) {
    if (key === '.') {
      const r = h * .1, cx = px + pw / 2, cy = h * .84;
      b.x.fillStyle = '#000'; b.x.beginPath(); b.x.arc(cx, cy, r + h * .045, 0, TAU); b.x.fill();
      b.x.fillStyle = '#fff'; b.x.beginPath(); b.x.arc(cx, cy, r, 0, TAU); b.x.fill();
    } else if (MT.img[key]) {
      const r = h * .035;                                            // the outline, rebuilt under the digit
      const u = mtBuf('dig1', Math.ceil(pw + 2 * r) + 2, Math.ceil(h + 2 * r) + 2);
      for (let i = 0; i < 12; i++) { const a = i / 12 * TAU; u.x.drawImage(MT.img[key], r + Math.cos(a) * r, r + Math.sin(a) * r, pw, h); }
      u.x.globalCompositeOperation = 'source-in'; u.x.fillStyle = '#000'; u.x.fillRect(0, 0, pw + 2 * r + 2, h + 2 * r + 2);
      b.x.drawImage(u.c, px - r, -r); b.x.drawImage(MT.img[key], px, 0, pw, h);
    }
  }
  if (o.color) {
    b.x.setTransform(1, 0, 0, 1, 0, 0);
    const a = mtBuf('digitsA', b.c.width, b.c.height); a.x.drawImage(b.c, 0, 0);
    b.x.globalCompositeOperation = 'multiply'; b.x.fillStyle = o.color; b.x.fillRect(0, 0, b.c.width, b.c.height);
    b.x.globalCompositeOperation = 'destination-in'; b.x.drawImage(a.c, 0, 0);
  }
  X.save(); X.translate(x + mtAnchor(w, o.align) - pad, y - h / 2 - pad); X.drawImage(b.c, 0, 0); X.restore();
  return { w, h };
}
