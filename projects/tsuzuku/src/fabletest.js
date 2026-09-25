// fabletest.js: Fable's shadow-puppet motion test (LOOPS.fable). The paper theatre, one lantern, the puppet on rods, a telling
// phrase in stop-motion: holds, a snap through one in-between, holds (Fable's rule: no easing curves except physical ones).
async function FABLE_INIT() { window.FABLE = await PUPPET.load('rig/fable/puppet.json'); }
{
  const B = 60 / 170 * 4, b = n => n * B;
  const pose = PUPPET.snap([
    [0,       { head: 0, torso: 0, upperarm: 0, forearm: 0, hand: 0 }],
    [b(.5),   { head: 7 }],                                   // a nod to the story
    [b(1),    { forearm: -7, hand: -6 }],                     // the fan comes up
    [b(1.5),  { hand: -20 }],                                 // the fan tips back: 'once upon a time...'
    [b(2),    { torso: 4, head: 3 }],                         // she leans in
    [b(2.75), { forearm: 0, hand: 0, torso: 0, head: 0 }],
    [b(3.25), { head: -6 }],                                  // she looks up
    [b(3.75), { forearm: 16, hand: 24, upperarm: 5 }],        // the fan lowers, pointing
    [b(4.5),  { head: 0, forearm: 0, hand: 0, upperarm: 0 }],
  ]);
  const BLINKS = [1.3, 3.9, 6.1];
  LOOPS.fable = t => {
    X.fillStyle = '#0d0b0a'; X.fillRect(0, 0, W, H);
    screen(t);
    const T = window.FABLE_T || { x: 760, y: 905, s: .2, origin: [1150, 2760] }, p = pose(t);
    shadow(c => {
      const M = FABLE.draw(c, p, T, { rods: [{ part: 'torso', at: [1080, 1900], w: 6 }, { part: 'hand', at: [1905, 1300], w: 3, lean: -60 }] });
      // the blink: paper over the eye slit for two drawings
      const q = Math.floor(t * 12) / 12;
      if (BLINKS.some(b0 => q >= b0 && q < b0 + 2 / 12)) { c.save(); c.setTransform(M.head); c.fillStyle = 'rgb(22,22,26)'; c.beginPath(); c.ellipse(1482, 494, 70, 22, -.12, 0, 7); c.fill(); c.restore(); }
      // the ribbon: indigo cellophane on a chain from the back of the head (light through it, the world's one spot colour)
      c.setTransform(1, 0, 0, 1, 0, 0);
      for (const [len, seed, dx] of [[1500, 0, -14], [1250, 2.1, -22]]) {        // two tails, tied at the back of the head
        const pts = PUPPET.chain(FABLE, pose, T, { part: 'head', at: [835, 470], n: 22, len, dx, wind: 380, seed, damp: .975 }, t);
        film(c, PUPPET.strip(pts, 30 * T.s, .8), FP.ai, .92);
      }
    }, 0);
    X.save(); X.globalCompositeOperation = 'overlay'; X.globalAlpha = .16; X.fillStyle = X.createPattern(GRAIN[Math.floor(t * 12) % 4], 'repeat'); X.fillRect(0, 0, W, H); X.restore();
  };
  LOOPS.fable.len = b(5);
}
