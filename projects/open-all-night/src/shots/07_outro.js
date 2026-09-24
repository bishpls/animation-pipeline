// 29 · OUTRO: asleep at dawn; the sign still on; the title; the sign dies into frame 0 (the film loops).
(() => {
  // Reads: (1) morning light across the room, the kid asleep with the tablet dimming on her chest (87.25–89.5)
  //        (2) on "all" (89.58) cut to the bakery window at dawn: the OPEN sign still glowing, the title settles
  //        (3) the last choir note: the sign flickers and dies -> the exact frame the film opened on.
  function room(t, lt) {
    const z = 1.06 - .04 * E.io2(clamp(lt / 2.3));
    save(); cam(930, 560, z);
    flood('blue', 1);
    // window: dawn. yellow sky, a pink sun rising behind the building opposite
    const wx = 1230, wy = 80, ww = 540, wh = 440;
    for (const k of RISO.inks) { k.ctx.save(); k.ctx.clip(P(rect(wx, wy, ww, wh))); }
    paint(P(rect(wx, wy, ww, wh)), { yellow: 1 });
    paint(P(cut(circle(wx + 400, wy + 250 - 30 * E.out2(clamp(lt / 2.3)), 70, 40), 90)), { pink: 1, yellow: 1 });
    paint(P(cut(rect(wx + 40, wy + 190, 290, 400), 33)), 'black');
    for (let i = 0; i < 6; i++) { const x = wx + 72 + (i % 3) * 82, y = wy + 225 + Math.floor(i / 3) * 105; knock(P(rect(x, y, 40, 58)), ['black']); ink(P(rect(x, y, 40, 58)), { yellow: 1 }); }
    for (const k of RISO.inks) k.ctx.restore();
    // sunbeam: the window's light falls across the wall and bed (paper + a yellow tint), the only soft thing
    const beam = [[wx, wy + wh], [wx + ww, wy + wh], [wx + ww - 240, 1000], [wx - 760, 1000]];
    knock(P(beam), ['blue'], .85); ink(P(beam), { yellow: .28 });
    paint(P(cut(rect(wx - 20, wy - 20, ww + 40, wh + 40), 34)), 'black', { stroke: 26 });
    paint(P(rect(wx + ww / 2 - 8, wy, 16, wh)), 'black'); paint(P(rect(wx, wy + wh * .45, ww, 14)), 'black');
    // the clock: now 6:10
    const ck = [250, 240], cr = 118;
    knock(P(cut(circle(ck[0], ck[1], cr, 48), 35, .8)), null);
    paint(P(cut(circle(ck[0], ck[1], cr, 48), 35, .8)), 'black', { stroke: 16 });
    const hand = (a, l, w, spec) => paint(P([[ck[0] - Math.sin(a) * 14, ck[1] + Math.cos(a) * 14], [ck[0] + Math.sin(a) * l, ck[1] - Math.cos(a) * l]], false), spec, { stroke: w });
    hand((6 + 10 / 60) / 12 * TAU, cr * .5, 14, 'black'); hand(10 / 60 * TAU, cr * .74, 9, 'black');
    paint(P(circle(ck[0], ck[1], 10)), 'pink');
    // floor, bed, pillow
    paint(P(cut(rect(-100, 950, W + 200, 300), 36)), 'black');
    paint(P(cut(blob([[400, 1100], [400, 540], [430, 470], [520, 470], [550, 540], [550, 1100]], 4), 37)), 'black');
    paint(P(cut(rect(520, 790, 1500, 170), 38)), 'black');
    knock(P(cut(blob([[540, 800], [530, 700], [610, 640], [860, 630], [900, 700], [880, 800]], 5), 40, 1.2)), null);
    // asleep: eyes closed, a slow breath, the blanket pulled up to her chin, the tablet face-down on her chest
    const br = Math.sin(lt * 1.9) * 7;
    head(CAST.kid, 720, 700, 2.3, { head: -Math.PI / 2 + .45, eyes: 'closed', blush: 0, smile: 1 });
    const bl = [[800, 800], [790, 690 - br], [850, 615 - br], [1150, 590 - br], [1420, 540], [1590, 600], [2000, 640], [2000, 820], [800, 830]];
    paint(P(cut(blob(bl, 5), 41, 1.6, .8)), { pink: 1 });
    for (let i = 0; i < 6; i++) knock(P([[1000 + i * 190, 600 + Math.sin(i * 1.7) * 20], [970 + i * 190, 820]], false), ['pink'], 1, { stroke: 4, dash: [12, 14] });
    save(); translate(930, 612 - br); rotate(-.12);
    paint(P(rrect(-95, -18, 190, 22, 7)), 'black');
    const dim = 1 - E.io2(clamp(lt / 2.2));
    if (dim > .05) knock(P(rect(-110, -90, 220, 72)), ['blue'], linear(0, -18, 0, -90, .6 * dim, 0));   // the last of its glow
    restore();
    restore();
  }

  function storefront(t, lt, dur) {
    // the bakery window at dawn: yellow sky beyond the glass, the sign still glowing; the title settles on the sill
    const lastT = 91.95;                                    // the choir's last breath
    const dying = t >= lastT;
    const z = 1.0 + .03 * E.out3(clamp(lt / 1.6));
    if (!dying) {
      save(); cam(W / 2, H / 2, z);
      flood('yellow', 1);                                   // dawn through the glass
      paint(P(cut(rect(-200, 985, W + 400, 400), 11, 2)), 'black');
      paint(P(cut(rect(-200, -300, 190, H + 600), 12, 2)), 'black');
      paint(P(cut(rect(W + 10, -300, 300, H + 600), 13, 2)), 'black');
      paint(P(cut(rect(-200, -300, W + 400, 250), 14, 2)), 'black');
      // on a yellow ground the tubes print pink with paper cores; the halo is pink halftone over yellow (warm)
      const fl = t > 91.5 ? (hash(BF(t) * 3.3) > .45 ? 1 : .0) : 1;         // one stutter before the end
      openSign(W / 2, 400, 240, [fl, fl, fl, fl], { border: fl, darkInks: ['yellow', 'black'], flood: 'yellow' });
      // the title
      const a = E.out3(seg(t, 89.58, 90.2)), b = E.out3(seg(t, 90.1, 90.9));
      const L = shape('OPEN ALL NIGHT', { font: 'arch', size: 150, wdth: 62, wght: 900, track: .02, space: .12 });
      drawText(L, W / 2, 900 + (1 - a) * 40, 'black', { align: 'center', per: (g, i) => (seg(t, 89.58 + i * .025, 89.9 + i * .025) > 0 ? { dy: (1 - E.back(seg(t, 89.58 + i * .025, 89.9 + i * .025))) * 50 } : { skip: true }) });
      if (b > 0) type('a love song for the ads', W / 2, 1060, { font: 'serif', size: 62, align: 'center', knock: true, knockInks: ['black'] });
      restore();
    } else {
      // exactly the film's first frame: dead glass on the night window (the loop)
      SHOT_FN['01'](0, 0, 3.977);
    }
    return { lyric: false };
  }

  function s29_asleep(t, lt, dur) {
    if (t < 89.54) {
      room(t, lt);
      const a = seg(t, 88.1, 88.4);                                  // the whisper: "open…" in the serif, knocked out of the floor
      if (a > 0) type('open…', 110, 1040, { font: 'serif', size: 76, knock: true, knockInks: ['black'], per: (g, i) => (seg(t, 88.1 + i * .06, 88.3 + i * .06) > 0 ? {} : { skip: true }) });
      return { lyric: false };
    }
    return storefront(t, t - 89.54, dur);
  }
  SHOT_FN['29'] = s29_asleep;
})();
