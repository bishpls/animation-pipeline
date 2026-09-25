// audience.js: the shadow audience at the bottom of frame (BEATS X2 and the crowd calls): black silhouettes in front of the
// lit screen, closer to the camera than the stage (larger, a touch soft), holding lit indigo paper lanterns (Fable's
// lightstick: a hall full of her world's only light source). On a crowd call they lift on the beat; the lanterns sway.
async function AUD_INIT() {
  const J = await (await fetch('rig/audience/audience.json')).json();
  const P2 = paths => { const p = new Path2D(); for (const pts of paths) { p.moveTo(pts[0][0], pts[0][1]); for (let i = 1; i < pts.length; i++) p.lineTo(pts[i][0], pts[i][1]); p.closePath(); } return p; };
  window.AUD = J.people.map(q => ({ ...q, outlineP: P2(q.outline), holesP: q.holes.length ? P2(q.holes) : null }));
}
// a chōchin (Fable: paper, lit from inside, ribs, no highlight): indigo washi on a bamboo spiral, black lacquer caps top and
// bottom; the candle sits low in the middle, so the paper is brightest there and dims toward the sides as it curves away; the
// ribs are shadows on the lit paper. Drawn in the person's frame at the traced lantern's centre and radius.
function lantern([cx, cy, r], sc, tq, ph) {
  const w = r * .86, h = r * 1.08, fl = 1 + .05 * Math.sin(tq * 23 + ph * 9);      // (the flame's small breathing, on twos)
  X.save(); X.beginPath(); X.ellipse(cx, cy, w, h, 0, 0, 7); X.clip();
  X.fillStyle = 'rgb(14,18,40)'; X.fillRect(cx - w, cy - h, 2 * w, 2 * h);
  X.save(); X.translate(cx, cy + h * .22); X.scale(w / h, 1);           // the glow: round about the candle, squeezed to the paper
  const g = X.createRadialGradient(0, 0, 0, 0, 0, h * 1.25 * fl);
  g.addColorStop(0, 'rgb(150,172,238)'); g.addColorStop(.35, 'rgb(84,112,206)'); g.addColorStop(.75, 'rgb(40,58,146)'); g.addColorStop(1, 'rgb(18,24,70)');
  X.fillStyle = g; X.fillRect(-h * 2, -h * 2, h * 4, h * 4); X.restore();
  X.strokeStyle = 'rgba(8,10,30,.42)'; X.lineWidth = Math.max(1.2, r * .035);    // the ribs, bowed a little (it's round)
  for (let k = 1; k < 9; k++) { const y = -h + 2 * h * k / 9, hw = w * Math.sqrt(1 - (y / h) ** 2);
    X.beginPath(); X.moveTo(cx - hw, cy + y); X.quadraticCurveTo(cx, cy + y + r * .07, cx + hw, cy + y); X.stroke(); }
  X.restore();
  X.fillStyle = '#0a0808';                                            // the caps
  for (const s of [-1, 1]) { X.beginPath(); X.ellipse(cx, cy + s * h * .93, w * .5, r * .13, 0, 0, 7); X.fill(); }
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
    const lift = inCall ? -(o.lift || 26) * Math.max(0, Math.sin(Math.PI * ((tq / beat + ph * .25) % 1))) : -3 * Math.sin(2 * Math.PI * (t / (3.1 + ph) + ph));
    const sway = q.lantern ? (inCall ? 6 : 2) * Math.sin(2 * Math.PI * (tq / (beat * 2) + ph)) : 0;
    X.setTransform(sc, 0, 0, sc, x, y0 + lift); X.rotate(sway * Math.PI / 180);
    X.fillStyle = '#0a0808'; X.fill(q.outlineP);
    if (q.holesP) lantern(q.lc, sc, tq, ph);                          // the lantern (drawn over the traced one)
  }
  X.restore();
  // the lanterns' glow in the dark hall (additive, unblurred sources are too hard)
  seed = 11; X.save(); X.globalCompositeOperation = 'screen';
  for (let i = 0; i < n; i++) {
    const q = AUD[Math.floor(rnd() * AUD.length)], x = (i + .5) / n * W + (rnd() - .5) * 60, sc = sc0 * (.85 + .3 * rnd()); rnd();
    if (!q.lantern) continue;
    const lx = x + q.lc[0] * sc, ly = y0 + q.lc[1] * sc, g = X.createRadialGradient(lx, ly, 0, lx, ly, q.lc[2] * sc * 2.6);
    const R = q.lc[2] * sc * 2.6; g.addColorStop(0, 'rgba(60,96,190,.26)'); g.addColorStop(1, 'rgba(60,96,190,0)'); X.fillStyle = g; X.fillRect(lx - R, ly - R, 2 * R, 2 * R);
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
