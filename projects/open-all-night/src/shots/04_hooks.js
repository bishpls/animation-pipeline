// 11, 14, 15, 24, 27 · hook type and the world (owns src/hook.js, src/globe.js)
(() => {
  // A justified poster block: rows of text fitted to one width, block height solved to `maxH`, centred at (cx, cy).
  function posterBlock(rows, cx, cy, maxW, maxH, gap = .07) {
    const probe = rows.map(r => fitRow(r.txt, 1000, r));
    const capSum = probe.reduce((a, L) => a + L.cap, 0);
    const w = Math.min(maxW, 1000 * maxH / (capSum * (1 + gap * (rows.length - 1) / rows.length * 1.0) + 1e-6));
    const Ls = rows.map(r => fitRow(r.txt, w, r));
    const g = Ls.reduce((a, L) => a + L.cap, 0) * gap;
    const H0 = Ls.reduce((a, L) => a + L.cap, 0) + g * (rows.length - 1);
    let y = cy - H0 / 2;
    return Ls.map(L => { y += L.cap; const o = { L, x: cx - w / 2, y, w }; y += g; return o; });
  }

  // ---------------------------------------------------------------- 11 · KEEP IT OPEN ALL NIGHT (chorus 1)
  // Reads: pink smash on the downbeat, rays burst; KEEP / IT / OPEN / ALL NIGHT! land on the syllables;
  // O-P-E-N swing open like doors with yellow light behind; the choir stamps (ALL NIGHT!).
  function s11_hook(t, lt, dur) {
    const W9 = LINES[9].words, T = { keep: W9[0].t0, it: W9[1].t0, open: W9[2].t0, all: W9[3].t0, night: W9[4].t0, ad: W9[5].t0 };
    const beats = [0, 1, 2, 3].map(i => beatT(Math.ceil(beatPos(32.9)) + i));
    const k = kick(t, [31.07, T.keep, T.it, T.open, T.all, T.night], 1) + kick(t, beats, .45, 11);
    const [sx, sy] = [noise1(t * 31) * 7 * k, noise1(t * 29 + 5) * 7 * k];
    save(); cam(W / 2 + sx, H / 2 + sy, 1 + .018 * k + .03 * E.out2(lt / dur));
    paint(P(rect(-200, -200, W + 400, H + 400)), { pink: 1 });
    // rays: burst out from behind the block on the downbeat, then turn slowly
    const grow = E.out5(seg(t, 31.07, 31.55));
    const rays = 18, rr = 1700 * grow;
    for (let i = 0; i < rays; i++) {
      const a0 = lt * .09 + i / rays * TAU, a1 = a0 + TAU / rays * .42;
      knock(P([[W / 2, H / 2], [W / 2 + Math.cos(a0) * rr, H / 2 + Math.sin(a0) * rr], [W / 2 + Math.cos(a1) * rr, H / 2 + Math.sin(a1) * rr]]), ['pink'], radial(W / 2, H / 2, 150, rr, .55, .6));
    }
    const B = posterBlock([{ txt: 'KEEP IT', wdth: 100, space: .16 }, { txt: 'OPEN', wdth: 125 }, { txt: 'ALL NIGHT!', wdth: 72, space: .1 }], W / 2, H / 2 + 6, 1600, 840, .085);
    slamWords(B[0].L, B[0].x, B[0].y, t, [T.keep, T.it], 'black', { from: 1.5, rot: -.05 });
    // OPEN: closed black doors slam in, then swing open one by one on eighth notes, light behind
    const so = slamT(t, T.open, { from: 1.35 });
    if (so.vis) {
      const L = B[1].L, px = B[1].x + L.width / 2, py = B[1].y - L.cap / 2;
      save(); translate(px, py); scale(so.sc); translate(-px, -py);
      doorLetters(L, B[1].x, B[1].y, t, T.open + .14, { stagger: BEAT / 4, dur: .38, light: { yellow: 1 }, field: ['pink'] });
      restore();
    }
    // ALL NIGHT!: paper, with a black offset shadow (second-colour drop, poster style)
    const off = B[2].L.cap * .045;
    slamWords(B[2].L, B[2].x + off, B[2].y + off, t, [T.all, T.night], { black: 1 }, { from: 1.5, rot: .04 });
    slamWords(B[2].L, B[2].x, B[2].y, t, [T.all, T.night], null, { knock: true, from: 1.5, rot: .04 });
    restore();
    stampAt('ALL NIGHT!', 1330, 700, t, T.ad, { size: 84, ink: 'black', fill: { black: 1 }, knockText: true, rot: -.11, hold: .95 });
    return { lyric: false };
  }

  SHOT_FN['11'] = s11_hook;
})();
