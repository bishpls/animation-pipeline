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

  // ---------------------------------------------------------------- 28 · the city spells OPEN (the climax)
  // Reads: (1) one window, with its own little OPEN sign (83.78); (2) pull back over the whole skyline at first light (to 85.6);
  //        (3) the windows light up as giant pixel letters, O on "keep" 85.70, P on "it" 86.02, E on "open" 86.30, N on the eighth after;
  //        (4) "all night!": the whole city flashes on, and holds (86.72 / 86.94).
  const GLYPH = {            // 5x7 block letters, drawn as windows
    O: ['.###.', '#...#', '#...#', '#...#', '#...#', '#...#', '.###.'],
    P: ['####.', '#...#', '#...#', '####.', '#....', '#....', '#....'],
    E: ['#####', '#....', '#....', '####.', '#....', '#....', '#####'],
    N: ['#...#', '##..#', '#.#.#', '#.#.#', '#..##', '#...#', '#...#'],
  };
  const PX = 2, COLW = 30, ROWH = 38, ROWS = 7 * PX + 4, GAPC = 3;
  const cols = Math.ceil(W / COLW) + 16, LOFF = Math.floor((cols - (4 * 5 * PX + 3 * GAPC)) / 2);   // the grid spans the frame; the word sits centred
  const X0 = W / 2 - cols * COLW / 2, YB = 1010;               // skyline: windows grid, bottom row just above the street
  const letterAt = (c, r) => {                                 // which letter (0..3) a window cell belongs to, or -1
    const cc = c - LOFF, rr = r - 2;
    if (rr < 0 || rr >= 7 * PX) return -1;
    for (let k = 0; k < 4; k++) {
      const lc = cc - k * (5 * PX + GAPC);
      if (lc >= 0 && lc < 5 * PX) { const g = GLYPH['OPEN'[k]]; return g[6 - Math.floor(rr / PX)][Math.floor(lc / PX)] === '#' ? k : -1; /* rows count up from the street */ }
    }
    return -1;
  };
  // buildings: runs of columns with their own heights (in rows); all tall enough to hold the letters
  const BLOCKS = (() => { const out = []; let c = 0, i = 0; while (c < cols) { const w = 3 + Math.floor(hash(i * 3.7) * 5); out.push({ c0: c, c1: Math.min(cols, c + w), top: ROWS + Math.floor(hash(i * 9.1) * 6), i }); c += w; i++; } return out; })();
  const LIT = [85.70, 86.02, 86.30, 86.54];
  function s28_open(t, lt, dur) {
    // camera: from one window (a sign in it), pulling back over the whole skyline by 85.6
    const TC = LOFF, TR = 6, target = [X0 + TC * COLW + COLW / 2, YB - TR * ROWH + ROWH / 2];    // a window inside the O
    const u = E.ioExpo(seg(t, 83.95, 85.2));
    const z = lerp(9, 1, u), cx = lerp(target[0], W / 2, u), cy = lerp(target[1], 540, u);
    const flash = t >= 86.94 ? 1 - E.out3(clamp((t - 86.94) / .45)) : 0, allOn = t >= 86.72;
    const kickZ = 1 + .06 * wobble(t, 86.72, 2.5, 5) + .05 * wobble(t, 86.94, 3, 6) + .02 * [85.7, 86.02, 86.3, 86.54].reduce((a, tb) => a + (t > tb ? Math.exp(-(t - tb) * 12) : 0), 0);
    save(); cam(cx, cy, z * kickZ);
    // sky: first light. blue above, a pink band and a yellow sliver at the horizon (solid bands, no gradients)
    paint(P(rect(-2000, -2000, W + 4000, 4000)), { blue: 1 });
    paint(P(rect(-2000, YB - ROWS * ROWH - 120, W + 4000, 4000)), { pink: 1 });
    paint(P(rect(-2000, YB - ROWS * ROWH - 30, W + 4000, 4000)), { pink: 1, yellow: 1 });
    // far skyline (pink-black overprint silhouettes) for depth
    for (let i = 0; i < 18; i++) { const x = -300 + i * 150, h = 180 + hash(i * 5.5) * 260; paint(P(cut(rect(x, YB - ROWS * ROWH - h + 140, 132, h + 400), 960 + i)), { pink: 1, black: 1 }); }
    // the blocks
    for (const b of BLOCKS) {
      const x = X0 + b.c0 * COLW - 6, w = (b.c1 - b.c0) * COLW + 6, top = YB - b.top * ROWH - 20;
      paint(P(cut(rect(x, top, w, YB - top + 400), 970 + b.i, 1.4)), 'black');
      if (hash(b.i * 2.3) > .6) paint(P(cut(rect(x + w * .3, top - 60, w * .3, 60), 980 + b.i)), 'black');   // water tanks, stair heads
      for (let r = 0; r < b.top; r++) for (let c = b.c0; c < b.c1; c++) {
        const k = letterAt(c, r), wx = X0 + c * COLW + 6, wy = YB - (r + 1) * ROWH + 8, ww = COLW - 12, wh = ROWH - 16;
        const story = c === TC && r === TR - 1;             // the window we start in
        const on = story || (k >= 0 ? t >= LIT[k] : (allOn ? hash(c * 13.1 + r * 7.7) > .45 : hash(c * 3.1 + r * 5.3) > .86));
        if (!on) continue;
        const win = P(rect(wx, wy, ww, wh));
        if (k >= 0 && !story) {                         // letter cells fill the whole cell: the windows fuse into solid letterforms
          const cell = P(rect(X0 + c * COLW + 1, YB - (r + 1) * ROWH + 1, COLW - 2, ROWH - 2));
          const age = t - LIT[k], pop = age < .1 ? (BF(t) % 2 ? 1 : .0) : 1;
          if (pop > .5) knock(cell, null);
          if (pop > .5 && allOn) paint(cell, { pink: 1 });
          continue;
        }
        if (story) {                          // letter windows: paper-bright, each with its little pink OPEN sign
          const age = t - (story ? 0 : LIT[k]), pop = age < .12 ? (BF(t) % 2 ? 1 : .3) : 1;
          knock(win, null);
          if (allOn && !story) paint(win, { pink: 1 });
          else { paint(P(rect(wx + 2, wy + wh * .3, ww - 4, wh * .4)), { pink: pop }); knock(P(rect(wx + 5, wy + wh * .44, ww - 10, wh * .12)), ['pink']); }
        } else paint(win, { yellow: 1 });
      }
    }
    // the letters' glow: a pink halftone halo over each lit letter's windows
    for (let k = 0; k < 4; k++) if (t >= LIT[k]) {
      const lx = X0 + (LOFF + k * (5 * PX + GAPC) + 5 * PX / 2) * COLW, ly = YB - (2 + 7 * PX / 2) * ROWH;
      ink(P(circle(lx, ly, 420)), { pink: radial(lx, ly, 120, 420, .35 * (allOn ? 1 : .8), 1.3) });
    }
    paint(P(rect(-2000, YB, W + 4000, 3000)), 'black');                       // the street
    // the window you started in: its own little sign, big while we're close
    restore();
    if (flash > 0) knock(P(rect(0, 0, W, H)), ['black', 'blue'], flash * .7);
    return { lyric: { slot: 'uc', plate: 'black', size: 70, y: 120, maxW: 1700 } };
  }
  SHOT_FN['28'] = s28_open;
})();
