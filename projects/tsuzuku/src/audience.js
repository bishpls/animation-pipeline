// audience.js: the shadow audience at the bottom of frame (BEATS X2 and the crowd calls): black silhouettes in front of the
// lit screen, closer to the camera than the stage (larger, a touch soft), holding lit indigo paper lanterns (Fable's
// lightstick: a hall full of her world's only light source). On a crowd call they lift on the beat; the lanterns sway.
async function AUD_INIT() {
  const J = await (await fetch('rig/audience/audience.json')).json();
  const P2 = paths => { const p = new Path2D(); for (const pts of paths) { p.moveTo(pts[0][0], pts[0][1]); for (let i = 1; i < pts.length; i++) p.lineTo(pts[i][0], pts[i][1]); p.closePath(); } return p; };
  window.AUD = J.people.map(q => ({ ...q, outlineP: P2(q.outline), holesP: q.holes.length ? P2(q.holes) : null }));
}
// seated row: a stable arrangement (seeded), people at mixed heights along the bottom edge
function audience(t, o = {}) {
  if (!window.AUD) return;
  const n = o.n || 9, y0 = o.y ?? H + 30, sc0 = o.scale || .52, B = 60 / 170 * 4, beat = o.beat || B / 2;
  let seed = 11; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  const calls = o.calls || [];                                       // [t0, t1] crowd-call windows: everyone lifts on the beats
  const tq = Math.floor(t * 12 + 1e-6) / 12, inCall = calls.some(([a, b]) => tq >= a && tq < b);
  X.save(); X.filter = `blur(${o.blur ?? 1.2}px)`;
  const order = []; for (let i = 0; i < n; i++) order.push(i);
  for (const i of order) {
    const q = AUD[Math.floor(rnd() * AUD.length)], x = (i + .5) / n * W + (rnd() - .5) * 60, sc = sc0 * (.85 + .3 * rnd()), ph = rnd();
    const lift = inCall ? -26 * Math.max(0, Math.sin(Math.PI * ((tq / beat + ph * .25) % 1))) : -3 * Math.sin(2 * Math.PI * (t / (3.1 + ph) + ph));
    const sway = q.lantern ? (inCall ? 6 : 2) * Math.sin(2 * Math.PI * (tq / (beat * 2) + ph)) : 0;
    X.setTransform(sc, 0, 0, sc, x, y0 + lift); X.rotate(sway * Math.PI / 180);
    X.fillStyle = '#0a0808'; X.fill(q.outlineP);
    if (q.holesP) {                                                    // the lantern: lit indigo paper, brighter at its heart
      // lit paper: bright at the flame, deep indigo at the rim (the gel colour of her world, lit from inside)
      const [lx0, ly0, lr] = q.lc, g = X.createRadialGradient(lx0 - lr * .2, ly0 - lr * .2, 0, lx0, ly0, lr * 1.1);
      g.addColorStop(0, 'rgb(190,222,255)'); g.addColorStop(.45, 'rgb(84,146,210)'); g.addColorStop(1, 'rgb(26,78,130)');
      X.globalCompositeOperation = 'source-over'; X.fillStyle = g; X.fill(q.holesP);
    }
  }
  X.restore();
  // the lanterns' glow in the dark hall (additive, unblurred sources are too hard)
  seed = 11; X.save(); X.globalCompositeOperation = 'screen';
  for (let i = 0; i < n; i++) {
    const q = AUD[Math.floor(rnd() * AUD.length)], x = (i + .5) / n * W + (rnd() - .5) * 60, sc = sc0 * (.85 + .3 * rnd()); rnd();
    if (!q.lantern) continue;
    const lx = x + q.lc[0] * sc, ly = y0 + q.lc[1] * sc, g = X.createRadialGradient(lx, ly, 0, lx, ly, q.lc[2] * sc * 2.6);
    const R = q.lc[2] * sc * 2.6; g.addColorStop(0, 'rgba(70,130,200,.35)'); g.addColorStop(1, 'rgba(70,130,200,0)'); X.fillStyle = g; X.fillRect(lx - R, ly - R, 2 * R, 2 * R);
  }
  X.restore();
}
{
  // test: verse 1's 'ARU TOKORO NI!' and the exchange's 'SHOW ME HOW!', over the paper theatre with Fable and the origami crab
  LOOPS.audience = t => {
    const s = 24 + t; LOOPS.origami(t);
    audience(s, { calls: [[11.44, 13.2], [35.12, 37.4]] });
  };
  LOOPS.audience.len = 14;
}
