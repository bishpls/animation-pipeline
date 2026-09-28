// SO BACK: the words on screen, from the vocal build's own event list (assets/vox.js, written by vocals/arrange.py: one clock).
// Each sung or said word prints on its syllable. Words of one line gather into a phrase and hold until the phrase ends.
// One style per kind of line: hook = chrome, stacked; over/echo = blackletter; chop = white slam; stamp = sticker;
// num = the giant chrome number; thesis = the long line, fitted; finale = chrome name. Caption band: y 420-1100 (clear of
// the platform UI at the bottom ~420 px and the right ~140 px; CRAFT section 10).
const capSlam = (t, t0, d = .12) => (t < t0 ? 0 : 1 + .3 * (1 - E.back(clamp((t - t0) / d))));
const PHRASES = (() => {
  const V = (window.VOX || []).slice().sort((a, b) => a.t - b.t), out = [];
  for (const w of V) {
    const p = out[out.length - 1];
    if (p && p.kind === w.kind && w.t - p.words[p.words.length - 1].t < 1.3 && w.kind !== 'stamp' && w.kind !== 'num') p.words.push(w);
    else out.push({ kind: w.kind, words: [w] });
  }
  for (let i = 0; i < out.length; i++) {
    const p = out[i], lastT = p.words[p.words.length - 1].t, next = out[i + 1] ? out[i + 1].words[0].t : 1e9;
    const hold = { winner: .9, taunt: .9, hook: .55, over: 1.4, echo: 1.2, chop: .9, stamp: .75, num: .9, thesis: 1.3, finale: 3 }[p.kind] || .8;
    const cut = [bt(8), bt(32), bt(48), bt(64), 27.0].find(c => c > lastT) || 1e9;   // (27.0: the victory screen's cut)       // section downbeats end a phrase
    p.t0 = p.words[0].t; p.t1 = Math.min(lastT + hold, next - .02, cut - .02);
  }
  return out;
})();

// a shot may return { cap: { y, x } } to move the caption band's centre for its framing (default y by kind, x = W/2)
let CAPSLOT = {};
function captions(t, ret) {
  CAPSLOT = (ret && ret.cap) || {};
  if (CAPSLOT.hide) return;                                   // a shot may hide the words (the end card)
  const skip = CAPSLOT.skip || [];                            // kinds a shot draws itself (e.g. behind its subject)
  for (const p of PHRASES) if (t >= p.t0 - .001 && t < p.t1 && !skip.includes(p.kind)) drawPhrase(p, t);
}
// the same words drawn INSIDE a shot's scene (e.g. behind the keyed subject: text on the field, the fighter in front); the
// shot returns { cap: { skip: [kind] } } so the overlay doesn't draw them again
function captionsIn(t, kinds, slot = {}) {
  const keep = CAPSLOT; CAPSLOT = slot;
  for (const p of PHRASES) if (t >= p.t0 - .001 && t < p.t1 && kinds.includes(p.kind)) drawPhrase(p, t);
  CAPSLOT = keep;
}
function drawPhrase(p, t) {
  const S = Object.assign({}, CAPSLOT, CAPSLOT[p.kind] || {});      // a shot may give a slot per kind: { y, hook: { y }, stamp: { y } }
  const dy = S.y != null ? S.y - 760 : 0, dx = S.x != null ? S.x - W / 2 : 0;
  const on = p.words.filter(w => t >= w.t - .001);
  const out = clamp((p.t1 - t) / .1);                       // a 0.1 s exit
  const cs = S.size || 1;
  X.save(); X.translate(dx, dy); if (cs !== 1) { const cy = 760; X.translate(W / 2, cy); X.scale(cs, cs); X.translate(-W / 2, -cy); } X.globalAlpha = out;
  // Melee's own type (src/meleetype.js): the game's word graphics where the announcer says a word the game draws, and its menu
  // font in the word graphics' dress for everything else; colour carries the section (Michael: one unified, SSBM aesthetic)
  const fitText = (str, size, style, x, y, sc = 1, maxW = 860, o = {}) => {
    const w0 = mtLayout(str, size, .075).w, f = Math.min(1, maxW / w0);
    X.save(); X.translate(x, y); X.scale(f * sc, f * sc); mtext(str, 0, 0, Object.assign({ size, style }, o)); X.restore();
  };
  const WORDG = { 'SUCCESS!': 'success', 'COMPLETE!': 'complete', 'READY?': 'ready', 'GO!': 'go', 'GAME!': 'game', 'TIME!': 'time', 'FAILURE': 'failure' };
  if (p.kind === 'taunt' || p.kind === 'winner') {
    // his own voice answers: SHOW ME / YA MOVES!, words on their syllables, two lines
    const lines = (p.kind === 'winner' ? [on.slice(0, 1), on.slice(1)] : [on.slice(0, 2), on.slice(2)]).filter(l => l.length);
    const tst = p.kind === 'winner' ? 'time' : 'go';
    lines.forEach((l, i) => fitText(l.map(w => w.text).join(' '), 150, tst, W / 2, 760 + i * 150 - (lines.length - 1) * 75, capSlam(t, l[l.length - 1].t, .1) || 1));
  } else if (p.kind === 'hook' || p.kind === 'finale' || p.kind === 'thesis') {
    // stacked, one word per line (a stutter's repeats re-slam their line)
    const grp = [];
    for (const w of on) { const g = grp[grp.length - 1]; if (g && g.base === w.text) g.w = w; else grp.push({ base: w.text, text: w.text, w }); }
    const size = p.kind === 'thesis' ? 150 : p.kind === 'finale' ? 260 : 190, style = { hook: 'game', thesis: 'complete', finale: 'success' }[p.kind];
    const lh = size * .98, y0 = 760 - (grp.length - 1) * lh * .5;
    grp.forEach((g, i) => fitText(g.text, size, style, W / 2, y0 + i * lh, capSlam(t, g.w.t, .12) || 1));
  } else if (p.kind === 'over' || p.kind === 'echo') {
    // "it's so over" in the menu font's lowercase, the violet dress of Time!/Failure; words fade in on their syllables
    const size = p.kind === 'echo' ? 110 : 150, full = p.words.map(w => w.text).join(' '), Lw = mtLayout(full, size, .075).w;
    const f = Math.min(1, 900 / Lw); let x = W / 2 - Lw * f / 2;
    const y = p.kind === 'echo' ? 1000 : 800;
    p.words.forEach(w => {
      const lw = mtLayout(w.text, size, .075).w * f;
      if (t >= w.t) { X.save(); X.globalAlpha = out * (p.kind === 'echo' ? .6 : 1) * clamp((t - w.t) / .3); X.translate(x, y); X.scale(f, f); mtext(w.text, 0, 0, { size, style: 'time', align: 'left' }); X.restore(); }
      x += lw + size * .32 * f;
    });
  } else if (p.kind === 'num') {
    // the HUD's damage digits, warming like the damage ramp: 5 in white, 5.5 hot
    const w = on[on.length - 1], sc = capSlam(t, w.t, .1) || 1;
    X.translate(W / 2, 980); X.scale(sc, sc);
    mdigits(w.text, 0, 0, { h: w.text.length > 1 ? 380 : 440, color: w.text.length > 1 ? '#ff8a3a' : null });
  } else if (p.kind === 'stamp') {
    const w = on[on.length - 1], sc = capSlam(t, w.t, .1) || 1, g = WORDG[w.text];
    X.translate(W / 2 + (S.x == null ? (hash(w.t * 7) - .5) * 80 : 0), 620); X.rotate((hash(w.t * 13) - .5) * .08); X.scale(sc, sc);
    if (g) mword(g, 0, 0, { h: 240 });
    else fitText(w.text, 150, w.text.startsWith('A NEW') ? 'success' : 'go', 0, 0, 1, 900);
  } else if (p.kind === 'chop' && p.words[0].text === 'GAME') {
    // GAME OVER: the 1P screen's own serif letters, revealed word by word (GAME on "Game", OVER on "over")
    const m = MT.M && MT.M.words.gameover, h = m ? Math.min(150, 900 * m.h / m.w) : 0, w = m ? m.w * h / m.h : 0, half = on.length > 1 ? 1 : .47;
    const sc = capSlam(t, on[on.length - 1].t, .12) || 1;
    X.translate(W / 2, 700); X.scale(sc, sc);
    X.save(); X.beginPath(); X.rect(-w / 2 - 20, -h, (w + 40) * half, 2 * h); X.clip(); mword('gameover', 0, 0, { h, tint: '#e8e4f4' }); X.restore();
  } else {                                                   // chop / other lines: the menu font, one line, fitted
    const s = on.map(w => w.text).join(' '), w = on[on.length - 1], g = WORDG[s];
    const style = s.startsWith('CONTINUE') ? 'death' : s.startsWith('THIS') || s.startsWith('WINNER') ? 'time' : 'go';
    X.translate(0, -60);
    if (g) { const sc = capSlam(t, w.t, .1) || 1; X.translate(W / 2, 760); X.scale(sc, sc); mword(g, 0, 0, { h: 190 }); }
    else fitText(s, 140, style, W / 2, 760, capSlam(t, w.t, .1) || 1);
  }
  X.restore();
}
function sticker(s, x, y, size, bg = PAL.ink, fg = PAL.lime) {
  const { L } = tpath(s, 0, 0, { font: 'any', size, wdth: 70, wght: 900 });
  const w = L.width + size * .6, h = size * 1.45;
  X.fillStyle = PAL.ink; X.fillRect(x - w / 2 - 8, y - size * 1.12 - 8, w + 16, h + 16);
  X.fillStyle = PAL.pink; X.fillRect(x - w / 2 + 14, y - size * 1.12 + 14, w, h);
  X.fillStyle = bg; X.fillRect(x - w / 2, y - size * 1.12, w, h);
  slam(s, x, y, { font: 'any', size, wdth: 70, wght: 900, fill: fg, stroke: 0 });
}
