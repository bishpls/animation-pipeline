// lyrics.js: the words, printed on the sung syllable.
// LINES are the lyric lines as written; each word gets its sung time from CUES.words (the song's own timestamps).
// Ad-libs in parentheses become rubber stamps (the choir). Accent words switch to the italic serif.
//
// A shot chooses how its lyric is set by returning { lyric: {...} } (see LYRIC_DEFAULT), or { lyric: false } when the
// shot sets the words itself (hook type). lyricState(t) gives any shot the live line + per-word timing.

const LYRIC_TEXT = [
  'Open... all night!',
  "Two a.m. and a kid can't sleep,", "she's learning all the stars for free.", "Grandma's laughing on a call from Rome,", "a stranger's video fixed the sink at home.",
  'You never see the wires, you never hear the gears,', 'but in the blink of an eye a whole market appears.', 'Somebody pays (blink!) and the page is yours,', 'every little window, every open door!',
  'Keep it open all night! (all night!)', 'Every window, every door, every kid gets a light!', 'All it costs is a glance (a glance!)', "and the whole world's yours tonight,", 'keep it open all night!',
  "Tiny shop on a side street, one good loaf of bread,", "one little ad and the whole town's fed!", 'Penny papers, radio, the TV in the den,', 'every time the world got free, somebody paid for it then.',
  'Nobody ever wrote a love song for the ads,', 'for the little gears behind the glass,', "so here's one! (here's one!)", 'Everybody sing it back!',
  'Keep it open all night! (all night!)', 'Every window, every door, every kid gets a light!', 'All it costs is a glance (a glance!)', "and the whole world's yours tonight,", 'keep it open, keep it open all night!',
  '(Open... all night.)',
];
const ACCENTS = new Set(['free', 'rome', 'home', 'gears', 'market', 'yours', 'glance', 'ad', 'fed', 'ads', 'glass', 'light', 'world']);
const normW = w => w.toLowerCase().replace(/[^a-z0-9']/g, '');

// build LINES: [{ i, text, t0, t1, words: [{ w, t0, t1, adlib, accent }] }]
const LINES = (() => {
  const cw = (C.words || []).filter(w => normW(w.w));
  let k = 0;
  const out = [];
  LYRIC_TEXT.forEach((text, i) => {
    const toks = text.split(/\s+/);
    let paren = false;
    const words = [];
    for (const tok of toks) {
      const open = tok.startsWith('('), close = tok.includes(')');
      if (open) paren = true;
      // find this token in the sung words (tolerate small mismatches: search a short window)
      let j = k, found = -1;
      for (; j < Math.min(cw.length, k + 4); j++) if (normW(cw[j].w) === normW(tok)) { found = j; break; }
      // not sung (or not transcribed): borrow the previous word's end, and don't consume the sung stream
      const prev = words.length ? words[words.length - 1] : (k > 0 ? cw[k - 1] : null);
      const src = found >= 0 ? cw[found] : { t0: prev ? prev.t1 : 0, t1: (prev ? prev.t1 : 0) + .12 };
      if (found >= 0) k = found + 1;
      const clean = tok.replace(/[()]/g, '');
      words.push({ w: clean, t0: src.t0, t1: src.t1, adlib: paren, accent: ACCENTS.has(normW(clean)) && !paren });
      if (close) paren = false;
    }
    // repair: times must be non-decreasing
    for (let q = 1; q < words.length; q++) if (words[q].t0 < words[q - 1].t0) { words[q].t0 = words[q - 1].t1; words[q].t1 = Math.max(words[q].t1, words[q].t0 + .15); }
    out.push({ i, text, words, t0: words[0].t0, t1: words[words.length - 1].t1 });
  });
  return out;
})();

// the line on screen at time t: from its first word (minus a lead) until the next line starts (or its hold runs out)
function lyricState(t, lead = .06, hold = 1.4) {
  for (let i = 0; i < LINES.length; i++) {
    const L = LINES[i], nx = LINES[i + 1];
    const end = Math.min(nx ? nx.t0 - .08 : 1e9, L.t1 + hold);
    if (t >= L.t0 - lead - .2 && t < end) return { L, end, age: t - L.t0, out: clamp((t - (end - .16)) / .16) };
  }
  return null;
}

const LYRIC_DEFAULT = { x: 110, y: 930, align: 'left', size: 66, maxW: 1100, ink: 'black', accentInk: 'pink', font: 'arch', wdth: 74, wght: 800, lh: 1.08, stamp: 'pink' };
// slots: named anchor positions (baseline of the LAST line; blocks grow upward)
const SLOTS = {
  ll: { x: 110, y: 960, align: 'left' }, lr: { x: W - 110, y: 960, align: 'right' }, lc: { x: W / 2, y: 975, align: 'center' },
  ul: { x: 110, y: 200, align: 'left', top: true }, ur: { x: W - 110, y: 200, align: 'right', top: true }, uc: { x: W / 2, y: 190, align: 'center', top: true },
  cl: { x: 110, y: H / 2 + 40, align: 'left' }, c: { x: W / 2, y: H / 2 + 40, align: 'center' },
};

// print the current line in a layout. Words rise onto the baseline at their sung time; ad-libs are stamps.
function drawLyric(t, o = {}) {
  const st = lyricState(t); if (!st) return;
  o = { ...LYRIC_DEFAULT, ...(o.slot ? SLOTS[o.slot] : {}), ...o };
  const { L } = st;
  const main = L.words.filter(w => !w.adlib), ad = L.words.filter(w => w.adlib);
  // layout main words into rows that fit maxW
  const sp = o.size * .26;
  const pieces = main.map(w => {
    const f = w.accent ? { font: 'serif', size: o.size * 1.18, wdth: null, wght: null } : { font: o.font, size: o.size, wdth: o.wdth, wght: o.wght };
    return { w, S: shape(w.w, { ...f, track: w.accent ? 0 : -.005 }) };
  });
  const rows = [[]]; let rw = 0;
  for (const p of pieces) { if (rw + p.S.width > o.maxW && rows[rows.length - 1].length) { rows.push([]); rw = 0; } rows[rows.length - 1].push(p); rw += p.S.width + sp; }
  const lh = o.size * o.lh, n = rows.length;
  rows.forEach((row, ri) => {
    const width = row.reduce((a, p) => a + p.S.width, 0) + sp * (row.length - 1);
    let x = o.align === 'center' ? o.x - width / 2 : o.align === 'right' ? o.x - width : o.x;
    const y = o.top ? o.y + ri * lh : o.y - (n - 1 - ri) * lh;
    for (const p of row) {
      const a = t - (p.w.t0 - .05);                                  // word age (a tiny lead reads as in sync)
      if (a >= 0) {
        const u = clamp(a / .2), rise = (1 - E.back(u)) * o.size * .45, outU = st.out;
        const sc = 1 - outU * .0;
        const inkSpec = p.w.accent ? o.accentInk : o.ink;
        const dy = rise + outU * o.size * .5;
        const clipped = u < 1 || outU > 0;
        drawText(p.S, x, y + dy, inkSpec === 'knock' ? null : inkSpec, { opaque: true, knock: inkSpec === 'knock', per: clipped ? (g) => ({ alpha: clamp(u * 3) * (1 - outU) > .5 ? 1 : 0 }) : null });
      }
      x += p.S.width + sp;
    }
  });
  // ad-lib stamps
  if (ad.length && o.stamp) {
    const a = t - ad[0].t0;
    if (a > -.02) {
      const txt = ad.map(w => w.w).join(' ').toUpperCase();
      const S = shape(txt, { font: 'arch', size: o.size * .8, wdth: 100, wght: 900 });
      const sx = o.stampX ?? (o.align === 'right' ? o.x - S.width - 60 : o.align === 'center' ? o.x + 220 : o.x + Math.min(o.maxW, 900) - S.width * .3);
      const sy = o.stampY ?? (o.top ? o.y + n * lh + o.size * .9 : o.y - n * lh - o.size * .25);
      const thump = 1 + .35 * (1 - E.out3(clamp(a / .14)));
      const outU = clamp((a - 1.1) / .15);
      if (outU < 1) {
        save(); translate(sx + S.width / 2, sy - S.cap / 2); rotate(-.07); scale(thump); translate(-(sx + S.width / 2), -(sy - S.cap / 2));
        const pad = o.size * .22;
        paint(P(rrect(sx - pad, sy - S.cap - pad, S.width + pad * 2, S.cap + pad * 2, 8)), o.stamp, { stroke: 6 });
        drawText(S, sx, sy, o.stamp, { opaque: true });
        restore();
      }
    }
  }
}
