// hook.js: kinetic hook type. The chorus words ARE the image: huge Archivo slammed on the sung syllable.
//
//   fitRow(txt, width, o)           a laid-out run whose width is exactly `width` (size solved; o.wdth/o.wght/o.track)
//   slamT(t, t0, o)                 slam transform at time t for a word landing at t0 -> { vis, sc, dy, rot, u }
//                                   (a 2-frame lead, big -> overshoot -> settle; o.from = start scale, o.dur)
//   slamText(L, x, y, t, t0, spec, o)   draw a run slammed in at t0 (baseline-left x, y; o.align, o.knock, o.pivotY)
//   slamWords(L, x, y, t, times, spec, o)  per-WORD slams inside one run: times[i] = landing time of word i
//   doorLetters(L, x, y, t, t0, o)   letters that swing open like doors on a hinge (their left edge), staggered by o.stagger,
//                                   revealing o.light (ink spec) letter-shaped light behind (o.rays: true adds a knocked-out ray fan)
//   stampAt(txt, x, y, t, t0, o)     a rubber-stamp ad-lib: thump in, hold, clear after o.hold s (o.ink, o.size, o.rot)
//   sunburst(cx, cy, n, rot, r, spec)   poster rays (alternate wedges), for behind hooks
//   hookLine(line, t, box, o)       a whole lyric line (LINES[i]) as huge progressive type in a box {x, y, w} (rows from the
//                                   bottom up), each word slamming on its sung time. o.rows = [[word indices], ...] optional
//   kick(t, times, amt)             a camera punch decaying after each time in times (sum), for shake/zoom on slams

function fitRow(txt, width, o = {}) {
  const probe = shape(txt, { font: o.font || 'arch', size: 100, wdth: o.wdth ?? 62, wght: o.wght ?? 900, track: o.track ?? 0, space: o.space ?? .04 });
  return shape(txt, { font: o.font || 'arch', size: 100 * width / probe.width, wdth: o.wdth ?? 62, wght: o.wght ?? 900, track: o.track ?? 0, space: o.space ?? .04 });
}

function slamT(t, t0, o = {}) {
  const lead = o.lead ?? .05, dur = o.dur ?? .22, from = o.from ?? 1.45;
  const a = t - (t0 - lead);
  if (a < 0) return { vis: false, sc: from, dy: 0, rot: 0, u: 0 };
  const u = clamp(a / dur);
  // arrives big, hits 1 at ~40%, overshoots under (0.965), settles
  const sc = u < .38 ? lerp(from, .955, E.in2(u / .38)) : lerp(.955, 1, E.back(clamp((u - .38) / .62)));
  return { vis: true, sc, dy: 0, rot: (o.rot ?? 0) * (1 - E.out3(u)), u };
}

function slamText(L, x, y, t, t0, spec, o = {}) {
  const s = slamT(t, t0, o); if (!s.vis) return s;
  const x0 = o.align === 'center' ? x - L.width / 2 : o.align === 'right' ? x - L.width : x;
  const px = x0 + L.width / 2, py = y - L.cap * (o.pivotY ?? .5);
  save(); translate(px, py); rotate(s.rot); scale(s.sc); translate(-px, -py);
  drawText(L, x0, y, o.knock ? null : spec, { knock: o.knock, knockInks: o.knockInks });
  restore();
  return s;
}

// per-word slams in one run: words are split at spaces; times[i] is word i's landing time
function slamWords(L, x, y, t, times, spec, o = {}) {
  const x0 = o.align === 'center' ? x - L.width / 2 : o.align === 'right' ? x - L.width : x;
  // group glyphs into words
  const words = [[]];
  L.glyphs.forEach(g => { if (g.ch === ' ') words.push([]); else words[words.length - 1].push(g); });
  words.forEach((gs, wi) => {
    if (!gs.length) return;
    const s = slamT(t, times[wi] ?? times[times.length - 1], o); if (!s.vis) return;
    const wx0 = x0 + gs[0].x, wx1 = x0 + gs[gs.length - 1].x + gs[gs.length - 1].w;
    const px = (wx0 + wx1) / 2, py = y - L.cap * .5;
    save(); translate(px, py); rotate(s.rot); scale(s.sc); translate(-px, -py);
    const sub = { ...L, glyphs: gs, width: L.width };
    drawText(sub, x0, y, o.knock ? null : spec, { knock: o.knock, knockInks: o.knockInks });
    restore();
  });
}

// letters that open like doors. Behind each glyph: the same glyph in light (o.light), plus rays of light knocked into the
// field. The door (the glyph in o.door ink) scales about its left edge from 1 to o.open (negative = swung past flat).
function doorLetters(L, x, y, t, t0, o = {}) {
  const stagger = o.stagger ?? .1, dur = o.dur ?? .42, x0 = o.align === 'center' ? x - L.width / 2 : x;
  const field = o.field || ['pink'];
  L.glyphs.forEach((g, i) => {
    if (g.ch === ' ') return;
    const a = t - (t0 + i * stagger);
    const u = a < 0 ? 0 : E.back(clamp(a / dur));
    const gx = x0 + g.x, gp = glyphPath(g, gx, y);
    if (u > 0) {
      // light spilling out of the doorway: a fan of rays knocked into the field, and the letter-shaped light
      if (o.rays) {
        const cx = gx + g.w * .55, cy = y - L.cap * .5, R = L.cap * 1.25 * clamp(u * 1.4);
        for (let k = 0; k < 7; k++) {
          const a0 = -Math.PI / 2 + (k - 3) * .32 + Math.sin(k * 2.1 + i) * .05, a1 = a0 + .12;
          const ray = [[cx, cy], [cx + Math.cos(a0) * R * 2.2, cy + Math.sin(a0) * R * 2.2], [cx + Math.cos(a1) * R * 2.2, cy + Math.sin(a1) * R * 2.2]];
          knock(P(ray), field, radial(cx, cy, R * .2, R * 2.2, .9 * clamp(u), 1.2));
        }
        knock(P(circle(cx, cy, R * 1.3)), field, radial(cx, cy, 0, R * 1.3, .85 * clamp(u), 1.1));
      }
      paint(gp, o.light || { yellow: 1 });
    }
    // the door: the glyph, hinged on its left edge; as it swings its visible width shrinks and it darkens a step
    // the door never mirrors: it narrows to an edge-on slab at the hinge (o.open = final visible fraction)
    const sx = lerp(1, o.open ?? .12, clamp(u));
    const m = new DOMMatrix().translate(gx, 0).scale(Math.max(sx, .04), 1).translate(-gx, 0);
    const dp = new Path2D(); dp.addPath(gp, m);
    paint(dp, u > .5 ? (o.doorBack || { black: 1, blue: 1 }) : (o.door || { black: 1 }));
  });
}

function stampAt(txt, x, y, t, t0, o = {}) {
  const a = t - t0; if (a < -.02) return;
  const hold = o.hold ?? 1.2; if (a > hold + .15) return;
  const S = shape(txt, { font: 'arch', size: o.size || 70, wdth: o.wdth ?? 100, wght: 900 });
  const thump = 1 + .45 * (1 - E.out3(clamp(a / .13)));
  const cx = x + S.width / 2, cy = y - S.cap / 2, pad = (o.size || 70) * .24;
  const clear = clamp((a - hold) / .15);
  if (clear >= 1) return;
  save(); translate(cx, cy); rotate(o.rot ?? -.08); scale(thump); translate(-cx, -cy);
  const spec = o.ink || 'black';
  if (o.fill) paint(P(rrect(x - pad, y - S.cap - pad, S.width + pad * 2, S.cap + pad * 2, 10)), o.fill);
  ink(P(rrect(x - pad, y - S.cap - pad, S.width + pad * 2, S.cap + pad * 2, 10)), spec, { stroke: (o.size || 70) * .09 });
  drawText(S, x, y, o.textInk || spec, o.knockText ? { knock: true } : {});
  if (clear > 0) knock(P(rect(x - pad * 2, y - S.cap - pad * 2, (S.width + pad * 4) * clear, S.cap + pad * 4)), null);
  restore();
}

function sunburst(cx, cy, n, rot, r, spec) {
  for (let i = 0; i < n; i++) {
    const a0 = rot + i / n * TAU, a1 = a0 + TAU / n / 2;
    paint(P([[cx, cy], [cx + Math.cos(a0) * r, cy + Math.sin(a0) * r], [cx + Math.cos(a1) * r, cy + Math.sin(a1) * r]]), spec);
  }
}

// a lyric line as huge progressive type. box = { x, y (baseline of the LAST row), w, lead (row gap, px) }.
// Main words only (ad-libs are stamps). Rows are justified to box.w; words slam on their sung times.
function hookLine(line, t, box, o = {}) {
  const words = line.words.filter(w => !w.adlib);
  const rows = o.rows || [words.map((_, i) => i)];
  const lead = box.lead ?? 26;
  const Ls = rows.map((r, ri) => fitRow(r.map(i => words[i].w.toUpperCase()).join(' '), box.w, { wdth: (o.wdth && o.wdth[ri]) ?? 62 }));
  let y = box.y;
  for (let ri = rows.length - 1; ri >= 0; ri--) {
    const times = rows[ri].map(i => words[i].t0);
    slamWords(Ls[ri], box.x, y, t, times, o.ink || 'black', { knock: o.knock, knockInks: o.knockInks, from: o.from ?? 1.3, rot: o.rot });
    y -= Ls[ri].cap + lead;
  }
  return Ls;
}

function kick(t, times, amt = 1, decay = 9) {
  let k = 0; for (const t0 of times) if (t >= t0 - .03) k += Math.exp(-(t - t0 + .03) * decay);
  return k * amt;
}
