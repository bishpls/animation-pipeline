// sway.js: the full-body hip-sway test (LOOPS.sway): 8 bars at the song's tempo. Hips shift on the downbeat and settle
// (Helltaker-style), a small dip on each beat, contrapposto and a level head from RIG.perform, a little head acting on top.
{
  const B = 60 / 170 * 4, beat = B / 4, S = Math.sin, PI = Math.PI;
  const hips = RIG.keys([
    [0, { hipX: 0 }], [B * .5, { hipX: .9 }], [B * 1.5, { hipX: -.9 }], [B * 2.5, { hipX: .9 }], [B * 3.5, { hipX: -.9 }],
    [B * 4.5, { hipX: 1 }], [B * 5, { hipX: -1 }], [B * 5.5, { hipX: 1 }], [B * 6, { hipX: -1 }], [B * 6.5, { hipX: .9 }], [B * 7.5, { hipX: 0 }],
  ], { move: .2, anticipate: .06, overshoot: .1 });
  const head = RIG.keys([[0, { angleX: 0, angleY: 0 }], [B * 2, { angleX: .3, angleY: -.2 }], [B * 3, { angleX: 0, angleY: 0 }],
                         [B * 4.5, { view: 'HR' }], [B * 5.5, { view: 'F' }], [B * 6.5, { angleY: .25 }], [B * 7, { angleY: 0 }]], { twos: true, move: .18 });
  const P = t => {
    const p = { view: 'F', ...hips(t), ...head(t) }, ph = (t % beat) / beat;
    p.hipY = 10 * Math.max(0, S(PI * Math.min(1, ph / .45)));                   // a dip on every beat
    p.breath = .5 + .5 * S(2 * PI * t / 3.23);
    return p;
  };
  const PP = t => RIG.perform(RIGS.clawd, P)(t);
  LOOPS.sway = t => {
    const g = X.createLinearGradient(0, 0, 0, H); g.addColorStop(0, '#2a2440'); g.addColorStop(1, '#141220'); X.fillStyle = window.DEBUG_BG || g; X.fillRect(0, 0, W, H);
    RIGS.clawd.draw(X, t, PP, { x: 700, y: 1060, s: .27 });                                        // full body
    RIGS.clawd.draw(X, t, PP, { x: 1450, y: 1060 + (3700 - 1950) * .62 - 480, s: .62 });            // the hips, close
  };
  LOOPS.sway.len = B * 8;
}
