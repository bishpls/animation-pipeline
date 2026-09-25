// viewtest.js: head views for model review (LOOPS.views). t<5: all five views, one eye state per second.
// t>=5: one view per second, large, mid-turn-settle pose (L, HL, F, HR, R)
LOOPS.views = t => {
  X.fillStyle = '#ddd8d0'; X.fillRect(0, 0, W, H);
  if (t < 5) {
    const e = [null, 'half', 'closed', 'happy', null][Math.floor(t)], m = [null, null, null, 'grin', 'A'][Math.floor(t)];
    ['L', 'HL', 'F', 'HR', 'R'].forEach((v, i) => RIGS.clawd.draw(X, 0, () => ({ view: v, eyes: e, mouth: m }), { x: 190 + i * 385, y: 540 + (3700 - 560) * .62, s: .62 }));
    return;
  }
  const v = ['L', 'HL', 'F', 'HR', 'R'][Math.min(4, Math.floor(t) - 5)];
  RIGS.clawd.draw(X, 0, () => ({ view: v }), { x: 960, y: 540 + (3700 - 700) * 1.25, s: 1.25 });
};
LOOPS.views.len = 10;
// (check) one view at rest at base scale 0.5 on a flat background, to diff against its aligned source drawing
LOOPS.viewrest = t => {
  X.fillStyle = '#1e1c32'; X.fillRect(0, 0, W, H);
  const v = ['F', 'L', 'R', 'HL', 'HR'][Math.min(4, Math.floor(t))];
  RIGS.clawd.draw(X, 0, () => ({ view: v, breath: 0, nocouple: 1 }), { x: 960, y: 1800, s: .5 });
};
LOOPS.viewrest.len = 5;
