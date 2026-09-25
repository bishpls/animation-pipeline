// crabs.js: Clawd's backup dancers, her block-mascot crabs (the pre-transformation form), from Op. 1 (hello-world/src/chars.js
// clawd(): copied under new names, since the paper world's prologue.js also declares POSE and chars.js can't load here).
// mascotTroupe(t, P, rows): rows of mascots dancing a move function in canon (a ripple lag from the centre), behind the idol.
const M_LN = '#5A2E24';
function mascot(x, y, s = 1, o = {}) {
  const t = NOW, sq = o.sq || 0, seed = o.seed ?? 11, col = o.col || C_.clay, colD = o.colD || C_.clayD;
  X.save(); X.translate(x, y - (o.hop || 0) * s); X.rotate(o.lean || 0); X.scale(s * (1 + sq * .5), s * (1 - sq * .5));
  const bw = 200, bh = 124, top = -bh - 44, L = (p, f, w = 4) => shp(p, f, w / 2 + 1.2, M_LN);
  const lg = o.walk != null ? o.walk : null;
  [-78, -34, 34, 78].forEach((lx, i) => { const lift = lg != null ? Math.max(0, Math.sin(lg * TAU + (i % 2) * Math.PI)) * 14 : 0; L(wob(rect(lx - 13, -46 - lift, 26, 44), seed + i, .6), col); });
  // nubs: plain, or pincers that snap
  const nub = (side, ang, hold) => {
    X.save(); X.translate(side * bw / 2, top + 58); X.rotate(-side * (ang || 0));
    if (o.pincer) {
      const op = (o.snip ?? 0) * .7 + .05;
      X.save(); X.translate(side * 10, 0); X.scale(1.4, 1.4); X.rotate(-side * op); L(wob(blob([[0, -6], [side * 44, -20], [side * 52, -4], [side * 12, 4]], 3), seed + side, .3), col); X.restore();
      X.save(); X.translate(side * 10, 0); X.scale(1.4, 1.4); X.rotate(side * op); L(wob(blob([[0, 6], [side * 44, 20], [side * 52, 4], [side * 12, -4]], 3), seed + side + 2, .3), col); X.restore();
    } else L(wob(rrect(side > 0 ? -6 : -34, -15, 40, 30, 8), seed + side, .6), col);
    if (hold) { X.translate(side * 40, 0); X.rotate(side * (ang || 0)); mascotProp(hold, side, o, t); }
    X.restore();
  };
  nub(-1, o.armL, o.holdL); nub(1, o.armR, o.holdR);
  const bow = o.bow || 0;
  const body = wob(rrect(-bw / 2, top + bow * 30, bw, bh - bow * 30, 12), seed + 5, .8);
  L(body, col, 5);
  clipTo(body, () => { X.fillStyle = colD; X.fillRect(-bw / 2, top + bh - 22, bw, 30); X.fillStyle = 'rgba(255,235,220,.35)'; X.fillRect(-bw / 2 + 14, top + bow * 30 + 10, 60, 10); });
  if (o.glow) glow(0, top + bh / 2, 260 * o.glow, 'rgba(255,230,150,1)', .8 * o.glow);
  const fy = top + 48 + bow * 50, lk = o.look || [0, 0], ex = 38;
  const eyes = o.eyes || (((t * 1000 + seed * 431) % 3700) < 110 ? 'closed' : 'open');
  for (const side of [-1, 1]) {
    const cx = side * ex + lk[0] * 8, cy = fy + lk[1] * 6;
    if (eyes === 'open') fil(rrect(cx - 9, cy - 24, 18, 48, 7), M_LN);
    else if (eyes === 'wide') { fil(rrect(cx - 12, cy - 28, 24, 56, 9), M_LN); fil(rrect(cx - 5, cy - 20, 7, 14, 3), C_.white); }
    else if (eyes === 'happy') lin([[cx - 14, cy + 6], [cx, cy - 10], [cx + 14, cy + 6]], 7, M_LN);
    else if (eyes === 'closed') lin([[cx - 14, cy], [cx + 14, cy]], 7, M_LN);
    else if (eyes === 'x') { lin([[cx - 12, cy - 12], [cx + 12, cy + 12]], 6, M_LN); lin([[cx - 12, cy + 12], [cx + 12, cy - 12]], 6, M_LN); }
    else if (eyes === 'star') sparkle(cx, cy, 22, C_.lemon, t * 2, 2);
    else if (eyes === 'heart') shp(blob([[cx, cy + 16], [cx - 18, cy - 2], [cx - 10, cy - 16], [cx, cy - 8], [cx + 10, cy - 16], [cx + 18, cy - 2]], 3), C_.pink, 2, M_LN);
  }
  if (o.glasses === 'shades' || eyes === 'shades') { L(rrect(-66, fy - 20, 56, 34, 8), C_.ink); L(rrect(10, fy - 20, 56, 34, 8), C_.ink); lin([[-10, fy - 8], [10, fy - 8]], 5, C_.ink); }
  else if (o.glasses === 'round') for (const side of [-1, 1]) { X.lineWidth = 4; X.strokeStyle = M_LN; X.beginPath(); X.arc(side * ex, fy, 28, 0, TAU); X.stroke(); }
  if (o.mouth === 'cat') lin([[-18, fy + 40], [-9, fy + 47], [0, fy + 41], [9, fy + 47], [18, fy + 40]], 3.5, M_LN);
  else if (o.mouth === 'open') L(blob([[-16, fy + 36], [16, fy + 36], [8, fy + 56], [-8, fy + 56]], 3), C_.pinkD, 3);
  else if (o.mouth === 'o') L(ellipse(0, fy + 44, 8, 10), C_.pinkD, 3);
  if (o.blush) for (const side of [-1, 1]) fil(ellipse(side * 66, fy + 32, 16, 9), C_.pink);
  if (o.bowtie) { L(blob([[0, top + bh - 16], [-26, top + bh - 30], [-26, top + bh - 2]], 2), o.bowtie === true ? C_.pink : o.bowtie, 3); L(blob([[0, top + bh - 16], [26, top + bh - 30], [26, top + bh - 2]], 2), o.bowtie === true ? C_.pink : o.bowtie, 3); }
  if (o.hat) mascotHat(o.hat, top + bow * 30, t, seed, o);
  X.restore();
}
function mascotHat(h, top, t, seed, o) {
  const L = (p, f, w = 4) => shp(p, f, w / 2 + 1.2, M_LN);
  if (h === 'bow') { L(blob([[0, top - 4], [-44, top - 30], [-48, top + 8]], 3), C_.pink); L(blob([[0, top - 4], [44, top - 30], [48, top + 8]], 3), C_.pink); L(circle(0, top - 6, 10), C_.pinkD); }
  else if (h === 'headband') { L(rrect(-102, top + 2, 204, 20, 6), C_.white); lin([[98, top + 12], [128, top - 6], [124, top + 22]], 5, C_.white); fil(circle(0, top + 12, 8), C_.pink); }
  else if (h === 'hardhat') { L(blob([[-70, top + 4], [-60, top - 44], [0, top - 60], [60, top - 44], [70, top + 4]], 4), C_.lemon); L(rrect(-86, top - 2, 172, 12, 5), C_.lemonD); }
  else if (h === 'crown') L([[-50, top + 2], [-54, top - 44], [-26, top - 20], [0, top - 52], [26, top - 20], [54, top - 44], [50, top + 2]], C_.lemon);
  else if (h === 'cap') { L(blob([[-66, top + 4], [-56, top - 40], [0, top - 52], [56, top - 40], [66, top + 4]], 4), C_.cyan); L(rrect(20, top - 4, 90, 14, 6), C_.cyanD); }
  else if (h === 'party') { L([[-34, top + 2], [0, top - 90], [34, top + 2]], C_.cyan); fil(circle(0, top - 92, 12), C_.lemon); lin([[-20, top - 30], [20, top - 44]], 4, C_.pink); }
  else if (h === 'beret') L(blob([[-70, top + 4], [-74, top - 20], [0, top - 40], [74, top - 22], [70, top + 4]], 4), C_.violet);
  else if (h === 'halo') { X.save(); X.lineWidth = 8; X.strokeStyle = C_.lemon; X.beginPath(); X.ellipse(0, top - 40, 60, 16, 0, 0, TAU); X.stroke(); X.restore(); }
  else if (h === 'tophat') { L(rrect(-74, top - 6, 148, 14, 5), C_.ink); L(rrect(-48, top - 80, 96, 78, 6), C_.ink); fil(rect(-48, top - 26, 96, 12), C_.pink); }
}
function mascotProp(h, side, o, t) {
  const L = (p, f, w = 4) => shp(p, f, w / 2 + 1.2, M_LN);
  if (typeof h === 'function') return h();
  if (h === 'penlight') { const c = o.penCol || C_.cyan; X.save(); X.rotate(-side * .6 - Math.PI / 2); L(rrect(-6, -10, 12, 30, 4), C_.ink); L(rrect(-8, -90, 16, 84, 8), c); glow(0, -60, 70, c, .5); X.restore(); }
  else if (h === 'fan') { X.save(); X.rotate(-Math.PI / 2); L([[0, 0], [-40, -70], [40, -70]], C_.pink); lin([[0, 0], [0, -70]], 3, M_LN); X.restore(); }
  else if (h === 'mic') { X.save(); X.rotate(-Math.PI / 2); L(rrect(-6, -8, 12, 36, 5), C_.ink); L(circle(0, -18, 13), '#8A8FA8'); X.restore(); }
  else if (h === 'flag') { lin([[0, 0], [0, -120]], 5, M_LN); L([[0, -120], [70, -104], [0, -84]], C_.pink); }
  else if (h.sign) { lin([[0, 0], [0, -70]], 6, M_LN); X.save(); X.translate(0, -120); X.rotate(-side * .08); L(rrect(-90, -46, 180, 92, 10), C_.white); pop(h.sign, 0, 18, { font: 'dela', size: h.size || 40, align: 'center', fill: h.col || C_.pink, lw: 0 }); X.restore(); }
}
const MASCOT_HATS = ['bow', 'headband', 'crown', 'cap', 'party', 'beret', 'hardhat', 'tophat'];

function mascotTroupe(t, P, rows) {
  for (const r of rows) r.xs.forEach((x, i) => {
    const d = Math.abs(i - (r.xs.length - 1) / 2), lag = d * (r.lag ?? .05), m = P(t - lag, i, r) || {};
    mascot(x, r.y, r.s, { seed: 20 + i * 7 + (r.seed || 0), hat: MASCOT_HATS[(i + (r.seed || 0)) % MASCOT_HATS.length], ...m });
  });
}
