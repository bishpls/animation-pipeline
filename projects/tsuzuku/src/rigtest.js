// rigtest.js: the Clawd idol rig motion test (LOOPS.rig): a turntable of the parameters on the beat grid.
LOOPS.rig = t => {
  const g = X.createLinearGradient(0, 0, 0, H); g.addColorStop(0, '#2a2440'); g.addColorStop(1, '#141220'); X.fillStyle = g; X.fillRect(0, 0, W, H);
  const B = 60 / 170 * 4, S = Math.sin, T2 = Math.PI * 2;
  const P = tt => ({
    angleX: .85 * S(T2 * tt / (4 * B)), angleY: .45 * S(T2 * tt / (3 * B) + 1), angleZ: 7 * S(T2 * tt / (5 * B) + 2),
    bodyZ: 3.5 * S(T2 * tt / (4 * B) + .6), bodyX: .5 * S(T2 * tt / (4 * B)),
    bounce: -16 * Math.abs(S(Math.PI * tt / (B / 2))),
    armL: 4 + 8 * S(T2 * tt / (2 * B)), armR: 4 + 8 * S(T2 * tt / (2 * B) + Math.PI),
    mouthOpen: Math.max(0, S(T2 * tt / (B / 2))) ** 1.5 * (S(T2 * tt / (8 * B)) > 0 ? 1 : 0), mouthWide: .3 * S(T2 * tt / B)
  });
  RIGS.clawd.draw(X, t, P, { x: 560, y: 1060, s: .27 });              // full body
  RIGS.clawd.draw(X, t, P, { x: 1400, y: 1060 + (3700 - 560) * 1.15 - 700, s: 1.15 });   // the head, close
};
LOOPS.rig.len = 8 * 60 / 170 * 4;
