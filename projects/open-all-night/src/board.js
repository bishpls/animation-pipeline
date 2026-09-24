// board.js: look-development boards (standalone loops). node engine/render.mjs projects/open-all-night --loop=look --sheet=0
LOOPS.look = t => {
  // left: night window with the sign
  save();
  const night = P(rect(0, 0, 1000, H));
  ink(night, { blue: 1 });
  const fl = t < .3 ? [1, 0, 1, 1] : [1, 1, 1, 1];
  openSign(500, 430, 190, fl, { border: 1 });
  // window frame silhouette
  ink(P(cut(rect(40, 820, 920, 40), 3)), 'black');
  type('OPEN ALL NIGHT', 500, 1000, { font: 'arch', size: 92, wdth: 62, wght: 900, track: .01, align: 'center', knock: true });
  restore();

  // right top: swatches + overprints + tint ramps
  const names = ['blue', 'pink', 'yellow', 'black'];
  names.forEach((n, i) => {
    ink(P(cut(rect(1040 + i * 215, 40, 190, 120), i + 10)), n);
    for (let k = 0; k < 8; k++) ink(P(rect(1040 + i * 215 + k * 23.75, 170, 23.75, 60)), { [n]: (k + 1) / 9 });
  });
  // overprints: two circles each pair
  [['blue', 'pink'], ['pink', 'yellow'], ['blue', 'yellow'], ['pink', 'black']].forEach(([a, b], i) => {
    const x = 1110 + i * 215, y = 320;
    ink(P(cut(circle(x, y, 62), i * 3 + 1)), a);
    ink(P(cut(circle(x + 55, y, 62), i * 3 + 2)), b);
  });
  // halftone glow
  ink(P(rect(1040, 410, 840, 110)), { pink: linear(1040, 0, 1880, 0, 1, 0) });
  ink(P(rect(1040, 410, 840, 110)), { blue: linear(1040, 0, 1880, 0, 0, 1) });

  // right bottom: type
  type('KEEP IT OPEN', 1040, 640, { font: 'arch', size: 118, wdth: 62, wght: 900, ink: 'black' });
  type('every kid gets a light', 1040, 720, { font: 'serif', size: 76, ink: 'pink' });
  type('ALL IT COSTS IS A GLANCE', 1040, 800, { font: 'any', size: 62, wdth: 150, wght: 900, ink: 'blue' });
  type('Grandma’s laughing on a call from Rome', 1040, 870, { font: 'arch', size: 44, wdth: 100, wght: 600, ink: 'black' });
  type('TWO A.M.', 1040, 1000, { font: 'shoulders', size: 130, wght: 900, ink: { yellow: 1, pink: 1 } });
  type('bread', 1600, 1000, { font: 'brico', size: 110, wdth: 75, wght: 800, ink: 'blue' });
};
LOOPS.look.len = 1;
LOOPS.neontest = t => {
  flood('blue', 1);
  const seg = (x) => [[x, 300], [x + 300, 300]];
  // A: plain stroke
  ink(P(seg(100), false), { pink: 1 }, { stroke: 24 });
  // B: halo pass (blur, source-over) then solid
  { const c = layer('pink'); c.save(); c.filter = 'blur(20px)'; c.strokeStyle = 'rgba(0,0,0,.6)'; c.lineWidth = 80; c.stroke(P(seg(500), false)); c.restore(); }
  ink(P(seg(500), false), { pink: 1 }, { stroke: 24 });
  // C: solid then blurred core knock
  ink(P(seg(900), false), { pink: 1 }, { stroke: 24 });
  { const c = layer('pink'); c.save(); c.globalCompositeOperation = 'destination-out'; c.filter = 'blur(5px)'; c.strokeStyle = 'rgba(0,0,0,1)'; c.lineWidth = 8; c.stroke(P(seg(900), false)); c.restore(); }
  // D: full neon()
  neon(seg(1300), 24, 1);
};
LOOPS.neontest.len = 1;
LOOPS.cast = t => {
  ink(P(rect(0, 760, W, 320)), { yellow: .0 });
  figure(CAST.kid, 150, 520, 1.5, {});
  figure(CAST.kid, 380, 520, 1.5, { eyes: 'wide', light: 1, aN: [1.9, -1.3], mouth: .5, hold: p => ink(P(rrect(p[0] - 4, p[1] - 50, 44, 60, 5)), 'black') });
  figure(CAST.dad, 640, 520, 1.1, { aN: [1.5, -.5], hold: p => ink(P(ribbon([[p[0] - 10, p[1] + 10], [p[0] + 40, p[1] - 40]], 12, 10)), { black: 1 }) });
  figure(CAST.grandma, 900, 520, 1.25, { eyes: 'happy', head: -.4, mouth: 1, aN: [2.3, -1.6], aF: [-.6, -.4] });
  figure(CAST.baker, 1170, 520, 1.15, { eyes: 'happy', mouth: .5, aN: [1.2, -1.0], aF: [1.0, -.9], hold: p => { ink(P(cut(ellipse(p[0] + 10, p[1] - 6, 70, 20, -.15), 4)), { yellow: 1 }); for (let k = -1; k <= 1; k++) knock(P([[p[0] + 10 + k * 30 - 8, p[1] - 12], [p[0] + 10 + k * 30 + 8, p[1] + 2]], false), ['yellow'], 1, { stroke: 3 }); } });
  figure(CAST.newsboy, 1420, 520, 1.3, { mouth: .8, aN: [2.8, -.2], hold: p => ink(P(rect(p[0] - 10, p[1] - 60, 55, 70)), { yellow: 1 }) });
  for (let i = 0; i < 5; i++) figure(CAST.anon, 150 + i * 190, 1000, 1.0, { var: i, walk: t * 1.1 + i * .23, face: i % 2 ? 1 : -1 });
  ink(P(rect(1040, 580, 880, 500)), { blue: 1 });
  figure(CAST.kid, 1150, 1000, 1.1, { eyes: 'closed' });
  figure(CAST.dad, 1360, 1000, .9, { walk: t, face: -1, ink: { black: 1 } });
  figure(CAST.grandma, 1560, 1000, .9, { mouth: .6, head: -.2 });
  figure(CAST.baker, 1780, 1000, .9, { walk: t + .5 });
};
LOOPS.cast.len = 2;
