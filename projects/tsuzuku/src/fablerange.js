// fablerange.js: Fable's range test (LOOPS.fablerange): each second shows one joint held at one extreme, so every hidden edge
// a pose can reveal gets looked at. Framed on the upper body.
{
  const R = [['head', -12], ['head', 12], ['torso', -8], ['torso', 8], ['upperarm', -12], ['upperarm', 12], ['forearm', -25], ['forearm', 25], ['hand', -35], ['hand', 35]];
  LOOPS.fablerange = t => {
    const [part, a] = R[Math.min(R.length - 1, Math.floor(t))];
    X.fillStyle = '#0d0b0a'; X.fillRect(0, 0, W, H);
    screen(0, { stops: FABLE_LAMP, tex: .32 });
    shadow(c => { c.globalCompositeOperation = 'source-over'; FABLE.draw(c, { [part]: a, hair: part === 'head' || part === 'torso' ? -a * .85 : 0 }, { x: 820, y: 1000, s: .34, origin: [1150, 2760] }); }, 0);
    X.fillStyle = '#ffdc5a'; X.font = '28px monospace'; X.fillText(`${part} ${a > 0 ? '+' : ''}${a}°`, 40, 60);
  };
  LOOPS.fablerange.len = R.length;
  // the standing puppet's range (LOOPS.fablerange_s)
  const RS = [['head', -12], ['head', 12], ['torso', -6], ['torso', 6], ['upperarm', -15], ['upperarm', 15], ['forearm', -25], ['forearm', 25], ['skirt', -8], ['skirt', 8]];
  LOOPS.fablerange_s = t => {
    const [part, a] = RS[Math.min(RS.length - 1, Math.floor(t))];
    X.fillStyle = '#0d0b0a'; X.fillRect(0, 0, W, H);
    screen(0, { stops: FABLE_LAMP, tex: .32 });
    shadow(c => { c.globalCompositeOperation = 'source-over'; FABLE_S.draw(c, { [part]: a, hair: part === 'head' || part === 'torso' ? -a * .85 : 0 }, { x: 960, y: 1040, s: .26, origin: [1100, 3700] }); }, 0);
    X.fillStyle = '#ffdc5a'; X.font = '28px monospace'; X.fillText(`${part} ${a > 0 ? '+' : ''}${a}°`, 40, 60);
  };
  LOOPS.fablerange_s.len = RS.length;
}
