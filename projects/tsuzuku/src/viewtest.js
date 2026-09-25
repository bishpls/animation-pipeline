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
