// viewtest.js: head views for model review (LOOPS.views): t<1 all views at rest; t>=1 one view, close, on magenta (holes show)
LOOPS.views = t => {
  if (t < 1) {
    X.fillStyle = '#ddd8d0'; X.fillRect(0, 0, W, H);
    ['L', 'HL', 'F', 'HR', 'R'].forEach((v, i) => RIGS.clawd.draw(X, 0, () => ({ view: v }), { x: 190 + i * 385, y: 1080 + (3700 - 560) * .5 - 120, s: .5 }));
    return;
  }
  X.fillStyle = '#ff00ff'; X.fillRect(0, 0, W, H);
  const v = ['L', 'HL', 'F', 'HR', 'R'][Math.min(4, Math.floor(t) - 1)];
  const sway = t % 1 > .5;                                                      // second half: the body swings, the hair springs lag
  RIGS.clawd.draw(X, sway ? t : 0, tt => ({ view: v, angleX: sway ? .3 * Math.sin(tt * 9) : .1, bodyZ: sway ? 3 * Math.sin(tt * 9) : 0 }), { x: 960, y: 540 + (3700 - 800) * 1.3, s: 1.3 });
};
LOOPS.views.len = 6;
