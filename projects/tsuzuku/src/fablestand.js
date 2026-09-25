// fablestand.js: the standing puppet (LOOPS.fablestand): she stands, holds, takes two geta steps toward the frame's edge (B8),
// a look back, and stops. Each step: the foot lifts and swings forward (one in-between, one past, placed), the skirt swings a
// little, the body travels on the step's landing (a Reiniger step: move on the landing, hold between).
{
  const B = 60 / 170 * 4, b = n => n * B, beat = B / 2;               // her 6/8 beat: half a bar
  const keys = [[0, { head: 0, torso: 0, skirt: 0, foot: 0, upperarm: 0, forearm: 0, hand: 0, dx: 0 }]];
  let x = 0;
  for (const [k, n] of [[3, 1], [5, 2]]) {                           // steps on beats 3 and 5
    keys.push([k * beat, { foot: -16, skirt: 3, upperarm: -6 }]);
    keys.push([k * beat + beat * .5, { foot: 0, skirt: 0, upperarm: 0, dx: (x += 165) }]);
  }
  keys.push([7 * beat, { head: -8 }], [9 * beat, { head: 0 }]);
  const pose = PUPPET.snap(keys);
  const TAILS = [{ len: 2500, w: 118, rest: [97, 100, 104, 107, 108, 105, 100] }, { len: 2150, w: 104, rest: [100, 104, 108, 111, 110, 104, 99] }];
  LOOPS.fablestand = t => {
    const tq = Math.floor(t * 12 + 1e-6) / 12;
    X.fillStyle = '#0d0b0a'; X.fillRect(0, 0, W, H);
    screen(tq, { stops: FABLE_LAMP, tex: .32 });
    const T = { x: 700, y: 905, s: .22, origin: [1100, 3700] }, p = pose(tq);
    shadow(c => {
      TAILS.forEach((tl, i) => {
        const pts = PUPPET.stiff(FABLE_S, pose, T, { part: 'head', at: [900, 820], rest: tl.rest, len: tl.len }, tq);
        c.setTransform(1, 0, 0, 1, 0, 0); c.globalCompositeOperation = i ? 'multiply' : 'source-over';
        c.fillStyle = 'rgba(38, 104, 205, .82)'; c.fill(P(PUPPET.strip(pts, tl.w * T.s, .85, tl.w * .9 * T.s)));
      });
      FABLE_S.draw(c, p, T, { rods: [{ part: 'torso', at: [1060, 1700], w: 7 }] });
      c.setTransform(1, 0, 0, 1, 0, 0); c.fillStyle = 'rgb(22,22,26)'; c.fillRect(150, 905, 1620, 16);   // the stage floor rail
    }, 0);
    X.save(); X.globalCompositeOperation = 'overlay'; X.globalAlpha = .16; X.fillStyle = X.createPattern(GRAIN[Math.floor(tq * 12) % 4], 'repeat'); X.fillRect(0, 0, W, H); X.restore();
  };
  LOOPS.fablestand.len = 10 * beat;
}
