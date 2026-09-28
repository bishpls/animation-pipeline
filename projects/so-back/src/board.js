// SO BACK: look boards (--loop=type, --loop=fields). Not part of the film.
LOOPS.type = t => {
  // four panels, one per text role, each on the kind of field it will sit on
  const hw = W / 2, hh = H / 2;
  const panel = (i, bg, fn) => { const x = (i % 2) * hw, y = Math.floor(i / 2) * hh; X.save(); X.beginPath(); X.rect(x, y, hw, hh); X.clip(); X.translate(x, y); X.scale(.5, .5); bg(); fn(); X.restore(); };
  panel(0, () => { flat('#6a6a74'); grain(t, .25); }, () => {                  // over: blackletter, lowercase, soft
    X.save(); X.shadowColor = 'rgba(255,255,255,.55)'; X.shadowBlur = 40;
    slam("it's so", W / 2, 860, { font: 'frak', size: 190, stroke: 0, fill: '#f2f0f6' });
    slam('over', W / 2, 1080, { font: 'frak', size: 250, stroke: 0, fill: '#f2f0f6' });
    X.restore();
  });
  panel(1, () => { flat(PAL.pink); sunburst(W / 2, H * .45, PAL.pink, '#ff5cb4', 24, t * .3); }, () => {   // hook: chrome
    chrome("WE'RE", W / 2, 760, { size: 190 }); chrome('SO', W / 2, 960, { size: 210 }); chrome('BACK', W / 2, 1180, { size: 250 });
  });
  panel(2, () => { flat(PAL.lime); checker(120, PAL.lime, '#b4f000', .3); }, () => {   // stamps: stickers
    const st = (s, x, y, r, bg, fg) => { X.save(); X.translate(x, y); X.rotate(r); const { L } = tpath(s, 0, 0, { font: 'any', size: 104, wdth: 70, wght: 900 });
      X.fillStyle = PAL.ink; X.fillRect(-L.width / 2 - 30 + 10, -104 - 12 + 10, L.width + 60, 150); X.fillStyle = bg; X.fillRect(-L.width / 2 - 30, -104 - 12, L.width + 60, 150);
      slam(s, 0, 0, { font: 'any', size: 104, wdth: 70, wght: 900, fill: fg, stroke: 0 }); X.restore(); };
    st('SUCCESS!', W / 2 - 60, 700, -.08, PAL.ink, PAL.lime); st('COMPLETE!', W / 2 + 40, 950, .06, PAL.pink, PAL.white);
    st('A NEW RECORD!', W / 2, 1200, -.04, PAL.white, PAL.ink);
    // lexicon chips
    const chip = (s, x, y) => { const { L } = tpath(s, 0, 0, { font: 'arch', size: 58, wght: 800, wdth: 100 }); X.fillStyle = PAL.ink; X.fillRect(x - L.width / 2 - 18, y - 58, L.width + 36, 78); slam(s, x, y, { font: 'arch', size: 58, wght: 800, fill: PAL.white, stroke: 0 }); };
    chip('20XX', 300, 1500); chip('NO JOHNS', 760, 1500); chip('FRAME PERFECT', W / 2, 1620);
  });
  panel(3, () => { flat(PAL.violet); dots('#9a5cff', 40, 9, .4); }, () => {       // numbers
    chrome('5.5', W / 2, 1150, { size: 560, font: 'dela' });
    slam('CONTINUE?', W / 2, 560, { font: 'dela', size: 110, fill: PAL.white });
  });
};
LOOPS.type.len = 1;
// the keyed composite, end to end: a hot field, the subject outline, the keyed pair, a zoom punch and an RGB split
LOOPS.keytest = t => {
  const K = vplate('keytest', 318, { keyed: true });
  const pt = 2.0 + t;
  const z = punch(t, .1, .15), [sx, sy] = shake(t, 14 * Math.exp(-t * 6));
  const b = buf('scene'); const X0 = X; X = b.x;
  flat(PAL.pink); sunburst(W / 2, H * .5, PAL.pink, '#ff5cb4', 24, t * .4);
  X.save(); X.translate(W / 2 + sx, H / 2 + sy); X.scale(z, z); X.translate(-W / 2, -H / 2);
  keyedOutline(K, pt, PAL.lime, 12);
  drawKeyed(K, pt);
  X.restore();
  X = X0;
  rgbSplit(b.c, 10 * Math.exp(-t * 5), 0);
};
LOOPS.keytest.len = 2;
