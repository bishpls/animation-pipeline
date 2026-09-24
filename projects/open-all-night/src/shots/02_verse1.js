// 03–06 · VERSE 1: the kid, the stars, grandma in Rome, the sink.
(() => {
  // ---------------------------------------------------------------- 03 · Two a.m. and a kid can't sleep
  // Reads: (1) a dark bedroom, light leaking from under a blanket; (2) the blanket slides down: a kid, wide awake,
  // face lit by a tablet; (3) she glances at the clock (2:00) and back; (4) the tablet light blooms up.
  function s03_kid(t, lt, dur) {
    const z = 1.0 + .06 * E.io2(lt / dur);
    save(); cam(930, 560, z);
    flood('blue', 1);
    // window, upper right: the building across the street, the moon
    const wx = 1230, wy = 80, ww = 540, wh = 440;
    for (const k of RISO.inks) { k.ctx.save(); k.ctx.clip(P(rect(wx, wy, ww, wh))); }
    const mdisk = P(cut(circle(wx + 420, wy + 110, 48, 40), 32)); knock(mdisk, ['blue']); ink(mdisk, { yellow: .2 });
    paint(P(cut(rect(wx + 40, wy + 190, 290, 400), 33)), 'black');
    for (let i = 0; i < 6; i++) { const x = wx + 72 + (i % 3) * 82, y = wy + 225 + Math.floor(i / 3) * 105; knock(P(rect(x, y, 40, 58)), ['black']); if (hash(i * 5 + 1) > .45) paint(P(rect(x, y, 40, 58)), { yellow: 1 }); }
    for (const k of RISO.inks) k.ctx.restore();
    paint(P(cut(rect(wx - 20, wy - 20, ww + 40, wh + 40), 34)), 'black', { stroke: 26 });
    paint(P(rect(wx + ww / 2 - 8, wy, 16, wh)), 'black'); paint(P(rect(wx, wy + wh * .45, ww, 14)), 'black');
    // the clock: paper face, black hands at 2:00, a pink second hand that ticks on the beat
    const ck = [250, 240], cr = 118;
    knock(P(cut(circle(ck[0], ck[1], cr, 48), 35, .8)), null);
    paint(P(cut(circle(ck[0], ck[1], cr, 48), 35, .8)), 'black', { stroke: 16 });
    for (let i = 0; i < 12; i++) { const a = i / 12 * TAU; ink(P([[ck[0] + Math.sin(a) * cr * .76, ck[1] - Math.cos(a) * cr * .76], [ck[0] + Math.sin(a) * cr * .88, ck[1] - Math.cos(a) * cr * .88]], false), 'black', { stroke: i % 3 ? 4 : 9 }); }
    const hand = (a, l, w, spec) => paint(P([[ck[0] - Math.sin(a) * 14, ck[1] + Math.cos(a) * 14], [ck[0] + Math.sin(a) * l, ck[1] - Math.cos(a) * l]], false), spec, { stroke: w });
    hand(2 / 12 * TAU, cr * .5, 14, 'black'); hand(0, cr * .74, 9, 'black');
    const bt = beatPos(t), tick = Math.floor(bt) + E.back(clamp(frac(bt) / .12));
    hand(tick / 60 * TAU + 1.1, cr * .82, 4.5, 'pink');
    paint(P(circle(ck[0], ck[1], 10)), 'pink');
    // floor + bed
    paint(P(cut(rect(-100, 950, W + 200, 300), 36)), 'black');
    paint(P(cut(blob([[400, 1100], [400, 540], [430, 470], [520, 470], [550, 540], [550, 1100]], 4), 37)), 'black');   // headboard
    paint(P(cut(rect(520, 790, 1500, 170), 38)), 'black');                                                             // mattress side
    // pillow (paper, with a yellow halftone where the tablet lights it)
    const pil = cut(blob([[540, 800], [530, 700], [610, 640], [860, 630], [900, 700], [880, 800]], 5), 40, 1.2);
    knock(P(pil), null);
    // the kid: the blanket slides down on "and a kid" (9.34): she is wide awake, lit from below by the tablet
    const reveal = E.back(seg(t, 9.30, 9.75));
    const hx = 720, hy = 700;
    const look = t < 10.1 ? [0, 0] : t < 10.95 ? [-1, -.6] : [0, 0];
    const turn = kf(t, [[10.05, 0], [10.2, -.4, 'out3'], [10.9, -.4], [11.05, 0, 'out3']]);
    head(CAST.kid, hx, hy, 2.3, { head: -Math.PI / 2 + .3 + turn, eyes: t < 9.42 ? 'closed' : 'wide', look, light: reveal > .5 ? 1 : 0, blush: 0, smile: t > 11.05 ? 1 : 0 });
    // blanket: a pink mountain with quilting stitches; its top edge slides down past her face
    const edge = lerp(hx - 150, hx + 115, reveal), breath = Math.sin(lt * 2.4) * 8;
    const bl = [[edge, 800], [edge - 20, 690 - breath], [edge + 70, 610 - breath], [1150, 600 - breath], [1420, 540], [1590, 600], [2000, 640], [2000, 820], [edge, 830]];
    const blP = P(cut(blob(bl, 5), 41, 1.6, .8));
    paint(blP, { pink: 1 });
    for (let i = 0; i < 6; i++) knock(P([[edge + 200 + i * 190, 600 + Math.sin(i * 1.7) * 20], [edge + 170 + i * 190, 820]], false), ['pink'], 1, { stroke: 4, dash: [12, 14] });
    // the tablet over her face; its light is paper, its halo halftone yellow
    const tp = [hx + 230, hy - 250], glow = .72 + .12 * Math.sin(lt * 11) * Math.sin(lt * 3.7) + reveal * .15;
    const R0 = 560;
    knock(P(circle(tp[0], tp[1] + 80, R0)), ['blue'], radial(tp[0], tp[1] + 80, 40, R0, .75 * glow, 1.3));
    ink(P(circle(tp[0], tp[1] + 80, R0)), { yellow: radial(tp[0], tp[1] + 80, 30, R0 * .75, .5 * glow, 1.3) });
    if (reveal < .5) knock(blP, ['pink'], radial(hx + 40, hy + 30, 10, 320, .55 * glow, 1.5));      // light leaking through the blanket
    // her arm from under the blanket, holding it up
    paint(P(ribbon([[hx + 200, 690], [hx + 250, hy - 130], [tp[0] + 10, tp[1] + 60]], 34, 26, 42)), { pink: 1 });
    save(); translate(tp[0], tp[1]); rotate(.22);
    paint(P(rrect(-150, -105, 300, 210, 18)), 'black');
    knock(P(rrect(-134, -89, 268, 178, 8)), null);
    restore();
    paint(P(cut(circle(tp[0] + 22, tp[1] + 72, 22, 14), 43)), { pink: 1 });          // thumb over the edge
    const sc = toScreen(tp[0], tp[1]);
    restore();
    // out: the tablet's light swells to fill the frame (a paper iris with a halftone fringe) -> the ceiling of stars
    const bl2 = E.in3(seg(t, 11.12, 11.72));
    if (bl2 > 0) { const r = 60 + bl2 * 2300; knock(P(circle(sc[0], sc[1], r + 260)), null, radial(sc[0], sc[1], r, r + 260, 1, .7)); knock(P(circle(sc[0], sc[1], r, 64)), null); }
    return { lyric: { slot: 'll', ink: 'knock', accentInk: 'yellow', y: 1030, size: 64 } };
  }

  SHOT_FN['03'] = s03_kid;
})();
