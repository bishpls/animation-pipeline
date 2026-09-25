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
// (check) arm range: both arms out to 0, 10, 20, 30, 40 degrees, full body (LOOPS.armrange)
LOOPS.armrange = t => {
  X.fillStyle = '#2a2440'; X.fillRect(0, 0, W, H);
  // the shoulder, close: t selects the angle (0, 15, 25, 35, 45)
  const k = Math.min(4, Math.floor(t * 5)), a = [0, 15, 25, 35, 20][k], e = [0, 30, 60, 90, 110][k];
  RIGS.clawd.draw(X, 0, () => ({ armL: a, elbowL: e }), { x: 960 + (1080 - 740) * .9, y: 540 + (3700 - 1150) * .9, s: .9 });
};
LOOPS.armrange.len = 1;
// (check) inward arms: claps and a page-wipe across the body (LOOPS.inward), t selects the pose
LOOPS.inward = t => {
  X.fillStyle = '#2a2440'; X.fillRect(0, 0, W, H);
  const P = [{ armL: 14, elbowL: -118, armR: 14, elbowR: -118 }, { armL: 10, elbowL: -128, armR: 10, elbowR: -128 }, { armL: 8, elbowL: -136, armR: 8, elbowR: -136 },
             { armL: 18, elbowL: -145, armR: 18, elbowR: -145 }, { armL: 22, elbowL: -150, armR: 22, elbowR: -150 }][Math.min(4, Math.floor(t * 5))];
  RIGS.clawd.draw(X, 0, () => P, { x: 960, y: 540 + (3700 - 1300) * .45, s: .45 });
};
LOOPS.inward.len = 1;
