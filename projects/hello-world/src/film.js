// film.js: the cut, the karaoke, the crowd calls, and shared set pieces (stage, crowd, cut-in frame, image sequences).
//
// A shot is fn(t, lt, dur) -> { karaoke: false | {y, size, ...}, calls: false, } and draws the whole frame into X.
// Register with SHOT['07'] = fn. Unbuilt shots show a slate.

// ------------------------------------------------------------------ the cut (from STORYBOARD.md)
const CUT = [
  [0, '01'], [1.55, '02'], [4.15, '03'], [5.65, '04'], [11.3, '05'], [14.1, '06'], [16.94, '07'], [22.6, '08'], [26.0, '09'],
  [28.23, '10'], [31.1, '11'], [33.95, '12'], [39.53, '13'], [42.4, '14'], [45.2, '15'], [48.1, '16'], [50.8, '17'], [53.7, '18'], [56.5, '19'], [59.3, '20'],
  [62.12, '21'], [67.76, '22'], [70.5, '23'], [73.3, '24'], [76.1, '25'], [79.06, '26'], [81.8, '27'],
  [84.7, '28'], [87.6, '29'], [90.3, '30'], [93.3, '31'], [96.0, '32'], [98.9, '33'], [101.6, '34'], [104.5, '35'],
  [107.29, '36'], [110.4, '37'], [113.2, '38'], [118.59, '39'], [121.3, '40'], [124.2, '41'], [127.3, '42'],
  [129.88, '43'], [132.8, '44'], [138.3, '45'], [141.2, '46'], [149.6, '47'], [152.47, '48'], [154.2, '49'],
];
const SHOT = {};
function slate(id) {
  const f = (t, lt, dur) => { stripes(C_.night, C_.nightD, 50, -.4, lt * 80); pop(id, 120, 260, { font: 'dela', size: 200, fill: C_.lemon, lw: 10 }); pop('shot ' + id, 120, 360, { size: 60, fill: C_.cream }); return {}; };
  Object.defineProperty(f, 'name', { value: 's' + id + '_slate' }); return f;
}
function registerFilm() { shots(CUT.map(([t0, id]) => [t0, SHOT[id] ? Object.defineProperty(SHOT[id], 'name', { value: 's' + id + (SHOT[id].label ? '_' + SHOT[id].label : '') }) : slate(id)])); }

// ------------------------------------------------------------------ karaoke
const GLOSS = { hajimemashite: ['はじめまして', 'nice to meet you'], arigatou: ['ありがとう', 'thank you'], ikuzo: ['いくぞ！', "let's go!"], yosha: ['よっしゃ', 'alright'] };
const nw = w => w.toLowerCase().replace(/[^a-z0-9]/g, '');
function lineAt(t) { for (let i = LINES.length - 1; i >= 0; i--) { const L = LINES[i], nx = LINES[i + 1]; if (t >= L.t0 - .25 && t < Math.min(nx ? nx.t0 - .1 : 1e9, L.t1 + 1.1)) return L; } return null; }
// o: { y (baseline), size, maxW, fill, sungFill, stroke, calls: true }
function karaoke(t, o = {}) {
  const L = lineAt(t); if (!L) return;
  const size = o.size || 62, y = o.y ?? 1012, main = L.words.filter(w => !w.call);
  if (!main.length) return;
  const sp = size * .3, pieces = main.map(w => ({ w, S: shape(w.w, { font: 'round', size }) }));
  const rows = [[]]; let rw = 0, maxW = o.maxW || 1640;
  for (const p of pieces) { if (rw + p.S.width > maxW && rows[rows.length - 1].length) { rows.push([]); rw = 0; } rows[rows.length - 1].push(p); rw += p.S.width + sp; }
  const lh = size * 1.18, fade = clamp((t - (L.t0 - .25)) / .15);
  rows.forEach((row, ri) => {
    const width = row.reduce((a, p) => a + p.S.width, 0) + sp * (row.length - 1);
    let x = W / 2 - width / 2; const yy = y - (rows.length - 1 - ri) * lh + (1 - E.out3(fade)) * 20;
    for (const p of row) {
      const u = clamp((t - p.w.t0) / Math.max(.08, p.w.t1 - p.w.t0));
      pop(null, x, yy, { L: p.S, fill: o.fill || C_.white, lw: size * .12, stroke: C_.ink });
      if (u > 0) { X.save(); X.beginPath(); X.rect(x - 10, yy - size, (p.S.width + 20) * u, size * 1.4); X.clip(); pop(null, x, yy, { L: p.S, fill: o.sungFill || C_.pink, lw: size * .12 }); X.restore(); }
      const g = GLOSS[nw(p.w.w)];
      if (g && t >= p.w.t0 - .3) {
        pop(g[0], x + p.S.width / 2, yy - size * 1.02, { font: 'mochi', size: size * .5, align: 'center', fill: C_.lemon, lw: 5 });
        pop(g[1], x + p.S.width / 2, yy + size * .62, { font: 'roundB', size: size * .36, align: 'center', fill: C_.cream, lw: 4 });
      }
      x += p.S.width + sp;
    }
  });
  return rows.length;
}
// crowd calls: MIX stamps at the frame edges, on the call's sung time
function calls(t, o = {}) {
  const L = lineAt(t); if (!L) return;
  // group contiguous call words (gap < .3 s) into one shouted phrase
  const ph = []; for (const w of L.words) { if (!w.call) { ph.push(null); continue; } const last = ph[ph.length - 1]; if (last && w.t0 - last.t1 < .3) { last.w += ' ' + w.w; last.t1 = w.t1; } else ph.push({ w: w.w, t0: w.t0, t1: w.t1 }); }
  let side = 0;
  ph.forEach(w => {
    if (!w) return;
    side++;
    const a = t - w.t0; if (a < -.02 || a > .9) return;
    const k = slamK(t, w.t0, .12), out = clamp((a - .7) / .2);
    const x = side % 2 ? 300 : W - 300, y = 170 + (side % 3) * 60;
    X.save(); X.translate(x, y); X.rotate(side % 2 ? -.12 : .1); X.scale(k * (1 - out * .3), k * (1 - out * .3)); X.globalAlpha = 1 - out;
    pop(w.w.toUpperCase().replace(/[.,]/g, ''), 0, 0, { font: 'dela', size: w.w.length > 12 ? 70 : 92, align: 'center', fill: side % 2 ? C_.cyan : C_.lemon, lw: 9, shadow: [8, 8, C_.ink] });
    X.restore();
  });
}
PROJECT.overlay = (t, ret, s) => {
  if (ret.karaoke !== false) karaoke(t, ret.karaoke || {});
  if (ret.calls !== false) calls(t, ret.calls || {});
  if (ret.after) ret.after();
};

// ------------------------------------------------------------------ set pieces
// the idol stage: floor, LED wall with an optional screen word, truss lights. o: { hue: [a, b], word, wordT }
function stage(t, o = {}) {
  const [a, b] = o.hue || [C_.night, C_.violet];
  flat(a);
  // LED wall: a grid of dots that shows a word
  X.save(); X.fillStyle = b;
  for (let i = 0; i < 64; i++) for (let j = 0; j < 20; j++) { const x = 30 + i * 29.5, y = 40 + j * 29.5; X.globalAlpha = .18 + .12 * Math.sin(t * 3 + i * .3 + j * .5); X.fillRect(x, y, 20, 20); }
  X.restore();
  // truss + lights
  lin([[0, 30], [W, 30]], 18, C_.ink);
  for (let i = 0; i < 8; i++) { const x = 120 + i * 240, sw = Math.sin(t * 1.3 + i) * .25; X.save(); X.globalAlpha = .22; X.fillStyle = i % 2 ? C_.pink : C_.cyan; X.beginPath(); X.moveTo(x, 40); X.lineTo(x + Math.sin(sw) * 900 - 180, 900); X.lineTo(x + Math.sin(sw) * 900 + 180, 900); X.fill(); X.restore(); shp(rrect(x - 22, 26, 44, 34, 8), C_.ink, 0); }
  // floor
  shp([[-100, 820], [W + 100, 820], [W + 100, H + 100], [-100, H + 100]], C_.nightD, 6);
  lin([[0, 820], [W, 820]], 10, b);
}
// the crowd: penlights waving on the beat. o: { y, rows, cols: [..], n }
function crowd(t, o = {}) {
  const rows = o.rows || 3, y0 = o.y || 900, cols = o.cols || [C_.pink, C_.cyan, C_.lemon];
  for (let r = rows - 1; r >= 0; r--) {
    const n = 16 + r * 3, yy = y0 + r * 70, sz = 1 - r * .12;
    for (let i = 0; i < n; i++) {
      const x = (i + .5 + (r % 2) * .5) / n * (W + 200) - 100, sw = Math.sin((beatPos(t) + i * .13 + r * .4) * Math.PI) * .45 * (o.wave ?? 1);
      const hx = x + Math.sin(sw) * 70 * sz, hy = yy - Math.cos(sw) * 90 * sz;
      lin([[x, yy], [hx, hy]], 9 * sz, cols[(i + r) % cols.length]);
      glow(hx, hy, 50 * sz, cols[(i + r) % cols.length], .35);
      shp(ellipse(x, yy + 30, 34 * sz, 42 * sz), C_.ink, 0);
    }
  }
}
// sakuga cut-in: a colour flash on entry, a bold background, the rigged illustration with parallax push.
// o: { bg: 'burst'|'speed'|'void'|'soft'|fn, cols, img, h (px), x, y, push (zoom over the shot), sway, flashCol, anchorY }
function cutin(t, lt, dur, o = {}) {
  const push = 1 + (o.push ?? .06) * E.io2(clamp(lt / dur));
  X.save(); X.translate(W / 2, H / 2); X.scale(push, push); X.translate(-W / 2, -H / 2);
  const [a, b] = o.cols || [C_.pink, C_.lemon];
  if (typeof o.bg === 'function') o.bg(t);
  else if (o.bg === 'speed') { flat(a); speedLines(W / 2, H * .45, b, 70, 3, 300); }
  else if (o.bg === 'void') tvoid(t);
  else if (o.bg === 'soft') { flat(a); dots(b, 30, 6, .5, (x, y) => clamp(1 - Math.hypot(x - W / 2, y - H / 2) / 1100)); }
  else sunburst(W / 2, H * .5, a, b, 24, t * .12);
  const img = IMG[o.img];
  if (img) rig(o.img, (o.x ?? W / 2) + noise1(t * .7) * 6, (o.y ?? H / 2) + noise1(t * .6 + 3) * 5, o.h || H * .98, { t, sway: o.sway ?? 7, anchorY: o.anchorY ?? .6, breath: o.breath ?? .008 });
  X.restore();
  if (lt < 2 / 24) flash(1, o.flashCol || C_.white);          // the one-frame hit into sakuga
  else if (lt < 5 / 24) flash(.5 - (lt - 2 / 24) * 4, o.flashCol || C_.white);
}
// image sequences (e.g. Seedance clips as JPG frames): SEQ.name = { n, frames: [Image] }
const SEQ = {};
async function loadSeq(name, dir, n) { SEQ[name] = { n, frames: [] }; await Promise.all(Array.from({ length: n }, (_, i) => new Promise(ok => { const im = new Image(); im.onload = ok; im.onerror = ok; im.src = `${dir}/f${String(i + 1).padStart(3, '0')}.jpg`; SEQ[name].frames[i] = im; }))); }
// draw frame for source time st (seconds at 24 fps), held on n frames (twos) if hold > 1; covers the frame
function seqDraw(name, st, hold = 1) {
  const S = SEQ[name]; if (!S) return;
  let f = Math.floor(st * 24 / hold) * hold; f = clamp(f, 0, S.n - 1);
  const im = S.frames[f]; if (im && im.width) X.drawImage(im, 0, 0, W, H);
}
