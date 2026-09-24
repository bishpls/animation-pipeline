// 01–02 · INTRO: the sign flickers on; the block wakes.
(() => {
  // neon ignition: a stutter pattern of (time offset, on) pairs, then steady. Deterministic per letter.
  const stutter = (t, t0, pat = [[0, 1], [.04, 0], [.12, 1], [.16, 0], [.26, 1], [.29, .35], [.33, 1]]) => {
    if (t < t0) return 0;
    let v = 0; for (const [dt, on] of pat) if (t >= t0 + dt) v = on;
    return v;
  };
  const ON = [.14, .52, .74, .95], BORDER = 2.02;
  const signState = t => ON.map((t0, i) => stutter(t, t0, i === 3 ? [[0, 1], [.05, 0], [.09, .6], [.13, 0], [.22, 1]] : undefined));

  function s01_sign(t, lt) {
    const bloom = lt > 2.96 ? 1 - E.out3(clamp((lt - 2.96) / .5)) : 0;
    const z = 1 + .035 * E.io2(clamp(lt / 2.9)) + .07 * E.out5(clamp((lt - 2.96) / .35));
    const [sx, sy] = lt > 2.96 ? [noise1(lt * 40) * 6 * bloom, noise1(lt * 40 + 9) * 6 * bloom] : [0, 0];
    save(); cam(W / 2 + sx, H / 2 + sy, z);
    flood('blue', 1);
    // the shop window frame: black mullions and sill, the glass beyond
    ink(P(cut(rect(-200, 985, W + 400, 400), 11, 2)), 'black');
    ink(P(cut(rect(-200, -300, 190, H + 600), 12, 2)), 'black');
    ink(P(cut(rect(W + 10, -300, 300, H + 600), 13, 2)), 'black');
    ink(P(cut(rect(-200, -300, W + 400, 250), 14, 2)), 'black');
    const on = signState(lt), bord = stutter(lt, BORDER, [[0, 1], [.06, 0], [.1, 1]]);
    const hum = lt > 1 ? 1 : 0;
    openSign(W / 2, 400, 240 * (1 + .02 * hum * Math.sin(lt * 50) * 0), on.map(v => v * (1 + bloom * .0)), { border: bord });
    if (bloom > 0) { knock(P(circle(W / 2, 420, 900)), ['blue', 'black'], radial(W / 2, 420, 100, 900, .8 * bloom, 1.2)); }
    // ALL NIGHT: knocked out of the sill, slammed in on the sung words
    const L = shape('ALL NIGHT', { font: 'arch', size: 170, wdth: 62, wght: 900, track: .02, space: .12 });
    const wAll = shape('ALL ', { font: 'arch', size: 190, wdth: 62, wght: 900, track: .02, space: .12 }).width;
    drawText(L, W / 2, 905, null, { align: 'center', knock: true, knockInks: ['black', 'blue'], per: (g, i) => {
      const tw = i < 3 ? 2.02 : 2.96, a = lt - tw + .03;
      if (a < 0) return { skip: true };
      const u = clamp(a / .16); return { sc: 1 + .5 * (1 - E.out3(u)), dy: -30 * (1 - E.out3(u)) };
    } });
    restore();
    return { lyric: false };
  }

  function s02_block(t, lt, dur) {
    // tilt up the facade, then push into the kid's window
    const B = BLDG, [kx, ky, kw, kh] = winRect(B.kid[0], B.kid[1]);
    const tilt = E.io3(clamp(lt / (dur - .75)));
    const push = E.inExpo(clamp((lt - (dur - .85)) / .85));
    const cy = lerp(800, 60, tilt), cx = lerp(W / 2, kx + kw / 2, tilt * .25);
    const zoom = lerp(1.18, 1.0, tilt) * lerp(1, 7.5, push);
    save(); cam(lerp(cx, kx + kw / 2, push), lerp(cy, ky + kh / 2, push), zoom);
    nightSky({ moon: [1560, -120, 70], w: 2400, ox: 250, h: 1400, oy: 450 });
    // neighbours: shorter blocks either side (black, a few lit windows)
    ink(P(cut(rect(-400, 360, 900, 900), 21)), 'black');
    ink(P(cut(rect(1420, 180, 900, 1100), 22)), 'black');
    for (let i = 0; i < 14; i++) { const x = -330 + (i % 7) * 115, y = 420 + Math.floor(i / 7) * 150; if (hash(i + 3) > .55) { knock(P(rect(x, y, 50, 80)), ['black']); if (hash(i + 9) > .5) { knock(P(rect(x, y, 50, 80)), ['blue']); ink(P(rect(x, y, 50, 80)), { yellow: 1 }); } } }
    for (let i = 0; i < 18; i++) { const x = 1480 + (i % 6) * 120, y = 250 + Math.floor(i / 6) * 160; if (hash(i + 7) > .45) { knock(P(rect(x, y, 54, 86)), ['black']); if (hash(i + 2) > .6) { knock(P(rect(x, y, 54, 86)), ['blue']); ink(P(rect(x, y, 54, 86)), { yellow: 1 }); } } }
    // windows wake in clusters on the beats of the horn riff; the kid's window glows first (the tablet)
    const order = [[0, 1], [2, 3], [1, 0], [4, 1], [3, 2], [6, 0], [2, 1], [7, 3], [0, 3], [5, 0], [4, 3], [6, 2], [1, 2], [3, 0], [7, 1], [5, 3]];
    const lit = (f, c) => {
      if (f === B.kid[0] && c === B.kid[1]) return .55 + .1 * Math.sin(lt * 9);
      const k = order.findIndex(([a, b]) => a === f && b === c);
      if (k < 0) return 0;
      const tb = beatT(8 + k * .5);                                   // eighth notes from bar 2
      return t >= tb ? 1 : 0;
    };
    building({ lit, sign: [1, 1, 1, 1], inWindow: (f, c, x, y, w, h) => {
      if (f === B.kid[0] && c === B.kid[1]) { knock(P(rect(x, y, w, h)), ['blue']); ink(P(rect(x, y, w, h)), { yellow: .5 }); ink(P(rect(x + w * .55, y + h * .55, w * .3, h * .45)), { blue: .9 }); }
    } });
    restore();
    return { lyric: false, subtitle: true };
  }

  SHOT_FN['01'] = s01_sign; SHOT_FN['02'] = s02_block;

  // the subtitle rides over s02
  PROJECT.subtitleAt = t => (t > 4.3 && t < 7.2);
})();
