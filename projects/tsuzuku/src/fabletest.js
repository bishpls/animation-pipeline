// fabletest.js: Fable's shadow-puppet motion test (LOOPS.fable), per Fable's review:
// one clock (everything in the frame on twos: pose, ribbon, lantern flicker, grain); fewer, bigger moves with long holds;
// each move = one in-between, one drawing past the pose, the pose (held); the two big fan moves fan three afterimages on the
// in-between; the ribbon is a stiff cellophane bookmark knotted at the nape under the hair, a gel that shows only where it
// clears her silhouette; the cushion and rods in frame; a warm lantern.
async function FABLE_INIT() { window.FABLE = await PUPPET.load('rig/fable/puppet.json'); window.FABLE_S = await PUPPET.load('rig/fable/puppet_standing.json'); }
const FABLE_LAMP = [[0, '#FFEBC0'], [.3, '#F8CD83'], [.7, '#D28F45'], [1, '#5E3516']];
{
  const B = 60 / 170 * 4, b = n => n * B;
  const pose = PUPPET.snap([
    [0,        { head: 0, torso: 0, upperarm: 0, forearm: 0, hand: 0 }],
    [b(.75),   { head: 10 }],                                        // a nod to the story
    [b(1.5),   { forearm: -18, hand: -12 }],                         // the fan comes up
    [b(2.5),   { hand: -34 }],                                       // the fan tips back (afterimages)
    [b(3.5),   { torso: 6, head: 5 }],                               // she leans in
    [b(4.5),   { torso: 0, head: 0, forearm: 0, hand: 0 }],
    [b(5.25),  { head: -9 }],                                        // she looks up
    [b(6),     { forearm: 22, hand: 32, upperarm: 8 }],              // the fan lowers to point (afterimages)
    [b(7.25),  { head: 0, forearm: 0, hand: 0, upperarm: 0 }],
  ]);
  const BLINKS = [1.2, 3.1, 5.6, 7.9];
  const GEL = 'rgba(38, 104, 205, .82)';   // multiplied through the warm vellum, this lands near Ai; folds double darker
  const TAILS = [                           // the bookmark's two tails: drawn curves (degrees, 90 = down) that trail off her back
    { len: 1900, w: 118, rest: [96, 101, 107, 112, 114, 110, 103] },
    { len: 1600, w: 104, rest: [99, 106, 113, 118, 116, 108, 100] }];
  LOOPS.fable = t => {
    const tq = Math.floor(t * 12 + 1e-6) / 12;                      // one clock: everything on twos
    X.fillStyle = '#0d0b0a'; X.fillRect(0, 0, W, H);
    screen(tq, { stops: FABLE_LAMP, tex: .32 });
    const T = window.FABLE_T || { x: 760, y: 880, s: .2, origin: [1150, 2760] }, p = pose(tq);
    shadow(c => {
      // the ribbon first (a gel on the vellum); the puppet's black paper then covers it wherever it crosses her
      TAILS.forEach((tl, i) => {
        const pts = PUPPET.stiff(FABLE, pose, T, { part: 'head', at: [905, 640], rest: tl.rest, len: tl.len }, tq);
        c.setTransform(1, 0, 0, 1, 0, 0); c.globalCompositeOperation = i ? 'multiply' : 'source-over';   // folds double darker
        c.fillStyle = GEL; c.fill(P(PUPPET.strip(pts, tl.w * T.s, .85, tl.w * .9 * T.s)));
      });
      const M = FABLE.draw(c, p, T, { ghosts: ['hand'], rods: [{ part: 'torso', at: [1080, 1900], w: 7 }, { part: 'hand', at: [1905, 1300], w: 5, lean: -70 }] });
      if (BLINKS.some(b0 => tq >= b0 && tq < b0 + 2 / 12)) {         // the blink: paper over the eye slit for two drawings
        c.save(); c.setTransform(M.head); c.fillStyle = 'rgb(22,22,26)'; c.beginPath(); c.ellipse(1482, 494, 70, 22, -.12, 0, 7); c.fill(); c.restore();
      }
    }, 0);
    X.save(); X.globalCompositeOperation = 'overlay'; X.globalAlpha = .16; X.fillStyle = X.createPattern(GRAIN[Math.floor(tq * 12) % 4], 'repeat'); X.fillRect(0, 0, W, H); X.restore();
  };
  LOOPS.fable.len = b(8);
}
