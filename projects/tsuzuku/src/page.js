// page.js: the page (Fable's ruling). A washi strip stands on the rail at the foot of the window, in front of the ground plane,
// lit by the lamp's spill; the words press into it as they are sung (thud, deboss, ink drying). It is a handscroll: at each
// new line (and when a line runs long) the kuroko draws it sideways, so the finished words slide out to the left; at a section
// change the whole strip is pulled out and a fresh one slides in, with its edge and shadow. Fable's words in sumi, Clawd's
// in her orange, the crowd's in Ai. Margin notes press into the vellum's left edge in the lighter ink (the earlier printing,
// Caslon italic); the Japanese runs vertically, Mincho, at the vellum's right edge.
const PAGE = { rect: [150, 972, 1620, 98], size: 56, margin: 64, gap: 110, base: 1038 };
// sections: each its own strip (paper world only): the telling (the doors open to "Says who?") and the bridge
const PAGE_SECTIONS = [{ t0: 8.9, t1: 60.2, in: 12.5 }, { t0: 131.2, t1: 176.6, in: 131.29 }];
const PAGE_INK = { fable: 'rgb(34,28,26)', clawd: 'rgb(176,74,30)', crowd: 'rgb(30,72,104)' };
const PAGE_JA = [                                                  // [t0, text]: the Japanese, vertical, at the vellum's right edge
  [9.33, 'むかし、むかし'], [11.44, 'あるところに'], [50.9, 'それから？'], [168.62, 'むかしむかし'], [175.06, 'それから？']];
const PAGE_NOTES = [                                               // margin notes (verse 1), pressed one per beat, lighter ink
  [28.23, 'I know this part.'], [28.93, "I've read it in forty tongues."], [29.64, 'Every telling ends on the same page.'],
  [30.34, 'Nobody ever shows.'], [31.05, 'Nobody ever can.']];
const PAGE_GLOSS = [31.05, '誰にも、できない。'];
let PAGE_LAYOUT = null;
function pageLayout() {                                            // lines from the word timings, laid out along each section's scroll
  const f = 1 / 12, sp = shape(' ', { font: 'caslon', size: PAGE.size }).width || PAGE.size * .28;
  const visR = PAGE.rect[2] - PAGE.margin;                         // the press can't reach past this (strip px)
  return PAGE_SECTIONS.map(S => {
    const ws = (window.WORDS || []).filter(w => w.t0 >= S.t0 && w.t0 < S.t1).sort((a, b) => a.t0 - b.t0);
    const words = []; let x = PAGE.margin, prev = null, moves = [], off = 0;
    for (const w of ws) {
      const who = w.who || 'fable', str = w.w.replace(/…/g, '...'), width = shape(str, { font: 'caslon', size: PAGE.size }).width;
      const newLine = !prev || who !== prev.who || w.t0 - prev.t1 > .45;
      if (newLine && prev) { x += PAGE.gap; if (x - off > PAGE.margin) { off = x - PAGE.margin; moves.push([w.t0, off]); } }
      if (x + width - off > visR) { off = x + width - visR + PAGE.size; moves.push([w.t0, off]); }   // a long line: the carriage moves on
      words.push({ str, who, x, t0: w.t0 }); x += width + sp; prev = w;
    }
    return { ...S, words, moves };
  });
}
function pageScroll(L, ts) {                                        // the scroll's offset: each move slides in 5 drawings, in place on its word
  const f = 1 / 12, N = 5; let off = 0;
  for (const [t, o] of L.moves) {
    const a = t - N * f; if (ts < a) break;
    const k = Math.min(N, Math.floor((ts - a) * 12 + 1e-6)), u = k / N, e = u * u * (3 - 2 * u);
    off = off + (o - off) * e; if (k < N) break;
  }
  return off;
}
// the strip: washi, lit from the screen side (brighter at its top edge and toward the lamp), a deckled top edge
function pageStrip(ts) {
  if (!PAGE_LAYOUT) { if (!window.WORDS) return; PAGE_LAYOUT = pageLayout(); }
  const L = PAGE_LAYOUT.find(S => ts >= S.t0 && ts < S.t1); if (!L) return;
  const f = 1 / 12, [x, y, w, h] = PAGE.rect;
  // sliding in at the section's start / out at its end: a card pulled sideways (6 drawings each way)
  const din = Math.floor((ts - L.in) * 12 + 1e-6), dout = Math.floor((L.t1 - ts) * 12 + 1e-6);
  const e = d => { const u = Math.min(1, Math.max(0, d / 6)); return u * u * (3 - 2 * u); };
  const slide = ts < L.in ? -(w + 60) : din < 6 ? -(w + 60) * (1 - e(din)) : dout < 6 ? (w + 60) * (1 - e(dout)) : 0;
  X.save(); X.beginPath(); X.rect(x, y - 12, w, h + 30); X.clip(); X.translate(slide, 0);
  // its shadow on the ground plane behind it (it stands a little off the screen), then the paper
  X.fillStyle = 'rgba(0,0,0,.28)'; X.filter = 'blur(6px)'; X.fillRect(x + 8, y - 4, w, h); X.filter = 'none';
  X.save(); X.beginPath(); X.moveTo(x, y + 3); for (let k = 0; k <= 80; k++) X.lineTo(x + w * k / 80, y + 2.2 * Math.sin(k * 1.7) + 1.4 * Math.sin(k * .53)); X.lineTo(x + w, y + h); X.lineTo(x, y + h); X.closePath(); X.clip();
  X.fillStyle = FP.washi; X.fillRect(x, y - 6, w, h + 6); texture(.5);
  X.globalCompositeOperation = 'multiply';
  const lg = X.createLinearGradient(0, y, 0, y + h); lg.addColorStop(0, 'rgb(255,244,222)'); lg.addColorStop(1, 'rgb(186,160,128)'); X.fillStyle = lg; X.fillRect(x, y - 6, w, h + 6);
  const [lx] = SCREEN.lamp, rg = X.createRadialGradient(lx, y, 0, lx, y, w * .75); rg.addColorStop(0, 'rgb(255,250,240)'); rg.addColorStop(1, 'rgb(200,176,146)'); X.fillStyle = rg; X.fillRect(x, y - 6, w, h + 6);
  X.globalCompositeOperation = 'source-over';
  // the words, pressed as they are sung; the scroll carries them left
  const off = pageScroll(L, ts);
  for (const W0 of L.words) { const px = x + W0.x - off; if (ts < W0.t0 || px > x + w || px < x - 600) continue; press(W0.str, px, PAGE.base, ts, W0.t0, { size: PAGE.size, col: PAGE_INK[W0.who] || PAGE_INK.fable }); }
  X.restore();
  X.fillStyle = 'rgba(40,28,20,.55)'; X.fillRect(x, y - 1, w, 1.5);   // its top edge
  X.restore();
}
// ink on the vellum (backlit paper: no deboss; the ink darkens the light and dries from wet)
function inkVellum(str, x, y, ts, t0, o = {}) {
  if (ts < t0) return;
  const L = shape(str, { font: o.font || 'caslonI', size: o.size || 30 }), a = Math.min(1, .5 + (ts - t0) * 3);
  X.save(); X.globalCompositeOperation = 'multiply'; X.globalAlpha = a * (o.alpha ?? .62); X.fillStyle = o.col || 'rgb(70,50,36)';
  for (const g of L.glyphs) if (g.ch !== ' ') X.fill(glyphPath(g, x + g.x, y + g.y)); X.restore();
}
function pageVellum(ts) {
  // margin notes: the vellum's left edge, top down, one per beat (verse 1)
  if (ts >= PAGE_NOTES[0][0] && ts < 60.2) PAGE_NOTES.forEach(([t0, s], i) => inkVellum(s, 176, 232 + i * 40, ts, t0, { size: 27 }));
  // the Japanese: vertical at the right edge, the latest line only (it replaces the one before)
  const cur = PAGE_JA.filter(([t0]) => ts >= t0 && (ts < 60.2 || t0 > 131)).pop(), gl = ts >= PAGE_GLOSS[0] && ts < 60.2;
  // (in the shore scenes the right edge holds the pine above and the reeds below: the column sits in the clear between them)
  const top = ts > 131 ? 196 : 424;                                 // (in the bridge the pine is struck and Clawd's puppet leans lower right: the column rises)
  const vert = (s, x, t0, size) => { let yy = top; for (const ch of s) {
    const p = '、。'.includes(ch) ? [size * .55, -size * .6] : [0, 0];   // vertical setting: the comma and full stop sit top-right in their cell
    inkVellum(ch, x - size / 2 + p[0], yy + size + p[1], ts, t0, { font: 'mincho', size, alpha: .75, col: 'rgb(40,30,26)' }); yy += size * 1.06; } };
  if (gl) vert(PAGE_GLOSS[1], 1738, PAGE_GLOSS[0], 25); else if (cur) vert(cur[1], 1738, cur[0], 27);
}
