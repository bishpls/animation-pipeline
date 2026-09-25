// fablefan.js: the fan and its nouns (LOOPS.fablefan). Fable: one black shape whose rib slits stay constant in number; each
// change in three held drawings, pinned at the wrist. The order is hers: crab, ruled line, wings -> falling figure, fox, crow,
// the boy who cried, mother crab (the crab scaled), book.
async function FAN_INIT() { window.FAN = await PUPPET.loadShapes('rig/fable/fan/fan.json'); }
const FAN_GRIP = [2040, 1062], FAN_TILT = 15;            // the pivot in her fist (master px) and the fan's lean in the master
// The prop in the hand's frame. `seq(t)` -> [from, to, u] noun names; 'mother' is the crab, larger; 'line' is laid level
// (the closed fan lengthened, then rotated flat: a rotation, not a morph, so the in-betweens stay a thin bar); creatures stand
// upright whatever the hand's angle.
const FAN_SCALE = { mother: 1.4 }, fanShape = n => n === 'mother' ? 'crab' : n;
function fanProp(seq, t, free = null) {
  return { after: 'forearm', draw: (c, M) => {
    if (free) { const [a, b, u] = seq(t); PUPPET.drawShape(c, PUPPET.shapeAt(FAN, fanShape(a), fanShape(b), u), free(M)); return; }
    const [a, b, u] = seq(t), mix = (T, d) => (T[a] ?? d) + ((T[b] ?? d) - (T[a] ?? d)) * u;
    const sh = PUPPET.shapeAt(FAN, fanShape(a), fanShape(b), u), sc = mix(FAN_SCALE, 1);
    const Mx = M.hand.translate(FAN_GRIP[0], FAN_GRIP[1]), ang = Math.atan2(Mx.b, Mx.a) * 180 / Math.PI;   // the hand's world angle
    // orientation: a fan follows the hand (with its lean); the line lies level; a creature stands upright in the world
    const rot = n => n.startsWith('fan') ? FAN_TILT : n === 'line' ? 90 - ang : -ang;
    PUPPET.drawShape(c, sh, Mx.rotate(rot(a) + (rot(b) - rot(a)) * u).scale(sc));
  } };
}
{
  const B = 60 / 170 * 4, b = n => n * B;
  const SEQ = ['fan_closed', 'crab', 'fan_closed', 'line', 'fan_closed', 'wings', 'falling', 'fox', 'crow', 'boy', 'mother', 'book', 'fan_closed'];
  const names = PUPPET.morphs(SEQ.map((n, i) => [i ? b(1 + i * 1.25) : 0, n]));
  // how she presents each noun: small ones raised to her eye line; big ones held out in front, clear of her face
  const PRESENT = { fan_closed: { forearm: -12, hand: 8 }, crab: { forearm: -12, hand: 8 }, line: { forearm: -6, hand: 0 },
    wings: { forearm: 14, hand: -4, upperarm: 6 }, falling: { forearm: 14, hand: -4, upperarm: 6 }, fox: { forearm: 8, hand: -2, upperarm: 3 },
    crow: { forearm: 8, hand: -2, upperarm: 3 }, boy: { forearm: 8, hand: -2, upperarm: 3 }, mother: { forearm: 30, hand: -14, upperarm: 18 },
    book: { forearm: 16, hand: -6, upperarm: 8 } };
  const arm = PUPPET.snap([[0, { forearm: 0, hand: 0, upperarm: 0 }], [b(.9), PRESENT.fan_closed],
    ...SEQ.slice(1).map((n, i) => [b(1 + (i + 1) * 1.25) - B / 4, PRESENT[n]])]);   // the arm moves a beat before the shape changes
  LOOPS.fablefan = t => {
    const tq = Math.floor(t * 12 + 1e-6) / 12;
    X.fillStyle = '#0d0b0a'; X.fillRect(0, 0, W, H);
    screen(tq, { stops: FABLE_LAMP, tex: .32 });
    const T = { x: 700, y: 960, s: .3, origin: [1150, 2760] }, p = { ...arm(tq), _ghost: {} };
    p.hair = -((p.head || 0) + (p.torso || 0)) * .85;
    const prop = fanProp(names, tq);
    shadow(c => { c.globalCompositeOperation = 'source-over'; FABLE.draw(c, p, T, { props: [prop] }); }, 0);
    X.save(); X.globalCompositeOperation = 'overlay'; X.globalAlpha = .16; X.fillStyle = X.createPattern(GRAIN[Math.floor(tq * 12) % 4], 'repeat'); X.fillRect(0, 0, W, H); X.restore();
  };
  LOOPS.fablefan.len = b(1 + SEQ.length * 1.25);
}

// LOOPS.fablecrab: the crab leaves the hand (verse 1: "once upon a time there was a crab"): the fan becomes the crab in her
// hand, it hops down to the stage floor, scuttles sideways (small hops on twos, a rock on each landing), stops, scuttles back,
// hops up into her hand, and is the fan again.
{
  const B = 60 / 170 * 4, b = n => n * B, beat = B / 2, FLOOR = 962, SC = .3;
  const seq = PUPPET.morphs([[0, 'fan_closed'], [b(1), 'crab'], [b(7), 'fan_closed']]);
  const arm = PUPPET.snap([[0, { forearm: 0, hand: 0 }], [b(.6), { forearm: -12, hand: 8 }], [b(2) - B / 4, { forearm: 10, hand: -6 }], [b(3), { forearm: -4, hand: 2 }],
                           [b(6) - B / 4, { forearm: 10, hand: -6 }], [b(6.5), { forearm: -12, hand: 8 }], [b(8), { forearm: 0, hand: 0 }]]);
  // the crab's world path (canvas px of its grip point): keyed stops; each move between stops = hops of `step` px on twos
  const STOPS = [[b(2), 'hand'], [b(2.5), [1160, FLOOR]], [b(4), [1560, FLOOR]], [b(4.5), [1560, FLOOR]], [b(5.9), [1160, FLOOR]], [b(6.3), 'hand']];
  const LOOPT = b(8.5);
  LOOPS.fablecrab = t => {
    const tq = Math.floor(t * 12 + 1e-6) / 12;
    X.fillStyle = '#0d0b0a'; X.fillRect(0, 0, W, H);
    screen(tq, { stops: FABLE_LAMP, tex: .32 });
    const T = { x: 620, y: 960, s: SC, origin: [1150, 2760] }, p = { ...arm(tq), _ghost: {} };
    const Mw = FABLE.world(p, T), hand = Mw.hand.translate(FAN_GRIP[0], FAN_GRIP[1]), hp = hand.transformPoint(new DOMPoint(0, 0));
    const ang = Math.atan2(hand.b, hand.a) * 180 / Math.PI;
    let free = null;
    if (tq >= STOPS[0][0] && tq < STOPS[STOPS.length - 1][0]) {
      let i = 0; while (i + 1 < STOPS.length - 1 && tq >= STOPS[i + 1][0]) i++;
      const [t0, a0] = STOPS[i], [t1, a1] = STOPS[i + 1], P0 = a0 === 'hand' ? [hp.x, hp.y] : a0, P1 = a1 === 'hand' ? [hp.x, hp.y] : a1;
      const dist = Math.hypot(P1[0] - P0[0], P1[1] - P0[1]), u = Math.min(1, (tq - t0) / (t1 - t0));
      const hops = Math.max(1, Math.round(dist / 70)), hu = u * hops, k = Math.min(hops - 1, Math.floor(hu)), f = hu - k;
      const x = P0[0] + (P1[0] - P0[0]) * u, big = a0 === 'hand' || a1 === 'hand';
      const y = P0[1] + (P1[1] - P0[1]) * u - (big ? 120 * Math.sin(Math.PI * u) : 18 * Math.sin(Math.PI * f));   // one big hop to/from the hand; small scuttle hops
      const rock = dist > 1 && !big ? 5 * Math.sin(Math.PI * 2 * f) : 0;
      free = () => new DOMMatrix().translate(x, y).rotate(rock).scale(SC);
    }
    const prop = fanProp(seq, tq, free);
    shadow(c => { c.globalCompositeOperation = 'source-over'; FABLE.draw(c, p, T, { props: [prop] });
      c.setTransform(1, 0, 0, 1, 0, 0); c.fillStyle = 'rgb(22,22,26)'; c.fillRect(150, FLOOR, 1620, 10); }, 0);
    X.save(); X.globalCompositeOperation = 'overlay'; X.globalAlpha = .16; X.fillStyle = X.createPattern(GRAIN[Math.floor(tq * 12) % 4], 'repeat'); X.fillRect(0, 0, W, H); X.restore();
  };
  LOOPS.fablecrab.len = LOOPT;
}
