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
// seated row: a stable arrangement (seeded), people at mixed heights along the bottom edge. They sit between us and the lit
// stage, so we see their backs: black, but never lost in the dark. The floor and air in front of the stage behind them are
// lit by its spill, so their heads stand out against a warm band; the stage light rims their top edges; their own lanterns
// light their hands and sleeves indigo. A crowd call starts each of them on their next hop, and a hop in progress when the call
// ends is finished: nobody stops in mid-air.
const AUD_CALLS = [[11.44, 14.04], [35.12, 37.72]];                     // the crowd calls (timeline.json), song seconds
let AUD_L = null, AUD_R = null;
function audience(t, o = {}) {
  if (!window.AUD) return;
  if (!AUD_L) { AUD_L = mkCanvas(W, H); AUD_R = mkCanvas(W, H); }
  const n = o.n || 9, y0 = o.y ?? H + 30, sc0 = o.scale || .52, B = 60 / 170 * 4, beat = o.beat || B / 2, L = o.lift || 26;
  let seed = 11; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  const calls = o.calls || AUD_CALLS, tq = Math.floor(t * 12 + 1e-6) / 12;
  const hop = ph => { const u = tq / beat + ph * .25, k = Math.floor(u), t0 = (k - ph * .25) * beat;   // this hop began at t0
    return calls.some(([a, b]) => t0 >= a - 1e-6 && t0 < b) ? Math.sin(Math.PI * (u - k)) : 0; };
  const P = [];
  for (let i = 0; i < n; i++) {
    const q = AUD[Math.floor(rnd() * AUD.length)], x = (i + .5) / n * W + (rnd() - .5) * 60, sc = sc0 * (.85 + .3 * rnd()), ph = rnd();
    const h = hop(ph), lift = h > 0 ? -L * h : -3 * Math.sin(2 * Math.PI * (tq / (3.1 + ph) + ph));
    const live = calls.some(([a, b]) => tq >= a && tq < b + beat), sway = q.lantern ? (live ? 6 : 2) * Math.sin(2 * Math.PI * (tq / (beat * 2) + ph)) : 0;
    const M = new DOMMatrix().translate(x, y0 + lift).scale(sc).rotate(sway);
    P.push({ q, x, sc, ph, M, lc: q.lantern ? M.transformPoint(new DOMPoint(q.lc[0], q.lc[1])) : null });
  }
  // 1. the lit floor behind them: a warm band at the height of their heads
  const gl = o.glow ?? 1;
  if (gl > 0) { X.save(); X.globalCompositeOperation = 'lighter'; X.translate(W / 2, y0 - 330 * sc0); X.scale(1, .3);
    const g = X.createRadialGradient(0, 0, 0, 0, 0, W * .62); g.addColorStop(0, `rgba(150,96,60,${.26 * gl})`); g.addColorStop(.6, `rgba(110,66,42,${.12 * gl})`); g.addColorStop(1, 'rgba(0,0,0,0)');
    X.fillStyle = g; X.fillRect(-W, -W, 2 * W, 2 * W); X.restore(); }
  // 2. their silhouettes on a layer; their lanterns' light on their hands and sleeves
  const A = AUD_L.getContext('2d'); A.setTransform(1, 0, 0, 1, 0, 0); A.globalCompositeOperation = 'source-over'; A.filter = 'none'; A.clearRect(0, 0, W, H);
  for (const p of P) { A.setTransform(p.M); A.fillStyle = '#0a0808'; A.fill(p.q.outlineP); }
  A.setTransform(1, 0, 0, 1, 0, 0); A.globalCompositeOperation = 'source-atop';
  for (const p of P) if (p.lc) { const R = p.q.lc[2] * p.sc * 3.2, g = A.createRadialGradient(p.lc.x, p.lc.y, 0, p.lc.x, p.lc.y, R);
    g.addColorStop(0, 'rgba(70,98,190,.7)'); g.addColorStop(1, 'rgba(10,8,8,0)'); A.fillStyle = g; A.fillRect(p.lc.x - R, p.lc.y - R, 2 * R, 2 * R); }
  // 3. the rim: the stage light catching their top edges (from behind them)
  const Rg = AUD_R.getContext('2d'); Rg.setTransform(1, 0, 0, 1, 0, 0); Rg.globalCompositeOperation = 'source-over'; Rg.filter = 'none'; Rg.clearRect(0, 0, W, H);
  Rg.drawImage(AUD_L, 0, 0); Rg.globalCompositeOperation = 'source-in'; Rg.fillStyle = `rgba(255,186,128,${.85 * gl})`; Rg.fillRect(0, 0, W, H);
  Rg.globalCompositeOperation = 'destination-out'; Rg.drawImage(AUD_L, 0, 4);
  X.save(); X.filter = `blur(${o.blur ?? 1.2}px)`; X.drawImage(AUD_L, 0, 0);
  X.globalCompositeOperation = 'lighter'; X.filter = 'blur(1px)'; X.drawImage(AUD_R, 0, 0); X.filter = 'blur(6px)'; X.globalAlpha = .5; X.drawImage(AUD_R, 0, 0); X.restore();
  // 4. the lanterns themselves, then their glow in the dark hall
  X.save(); X.filter = `blur(${(o.blur ?? 1.2) * .6}px)`;
  for (const p of P) if (p.q.holesP) { X.setTransform(p.M); lantern(p.q.lc, p.sc, tq, p.ph); }
  X.restore();
  X.save(); X.globalCompositeOperation = 'screen';
  for (const p of P) if (p.lc) { const R = p.q.lc[2] * p.sc * 2.6, g = X.createRadialGradient(p.lc.x, p.lc.y, 0, p.lc.x, p.lc.y, R);
    g.addColorStop(0, 'rgba(60,96,190,.26)'); g.addColorStop(1, 'rgba(60,96,190,0)'); X.fillStyle = g; X.fillRect(p.lc.x - R, p.lc.y - R, 2 * R, 2 * R); }
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
