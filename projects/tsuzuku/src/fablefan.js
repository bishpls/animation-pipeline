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
    const Mx = M.hand.translate(FAN_GRIP[0], FAN_GRIP[1]), ang = Math.atan2(Mx.b, Mx.a) * 180 / Math.PI;   // the hand's world angle
    // orientation: a fan follows the hand (with its lean); the line lies level; a creature stands upright in the world
    const rot = n => n.startsWith('fan') ? FAN_TILT : n === 'line' ? 90 - ang : -ang;
    // the fall (wings -> the falling figure, held by the ankles): not a morph down through her fist but a pitch forward over
    // the front of her hand, three cards: the wings tipped 70 degrees forward, the falling figure swung 50 out, hanging
    const fall = (a === 'wings' && b === 'falling') || (a === 'falling' && b === 'wings');
    if (fall && u < 1) {
      const first = u < .5, n = first ? a : b, swing = (a === 'wings') === first ? 70 : -50;
      PUPPET.drawShape(c, PUPPET.shapeAt(FAN, n, n, 1), Mx.rotate(rot(n) + swing).scale(mix(FAN_SCALE, 1)));
      return;
    }
    const sh = PUPPET.shapeAt(FAN, fanShape(a), fanShape(b), u), sc = mix(FAN_SCALE, 1);
    PUPPET.drawShape(c, sh, Mx.rotate(rot(a) + (rot(b) - rot(a)) * u).scale(sc));
  } };
}
{
  // The gallery as a script of props (Fable: what she sets down stays down; the next fan comes from her sleeve).
  // Each prop: appears in her hand at `from`, morphs through `seq` (out of the fan via fan_open), and may be released at
  // `rel.t`: 'set' lays it on the floor where it stays; 'fall' drops it (Icarus) to the floor, where it lies.
  const B = 60 / 170 * 4, b = n => n * B, FLOOR = 962, T = { x: 700, y: 960, s: .3, origin: [1150, 2760] };
  const viaOpen = keys => keys.flatMap(([t, n], i) => i && keys[i - 1][1].startsWith('fan') && !n.startsWith('fan') && n !== 'line' ? [[t, 'fan_open'], [t + .5, n]] : [[t, n]]);
  const PROPS = [
    { from: 0, seq: viaOpen([[0, 'fan_closed'], [b(2), 'crab'], [b(4), 'fan_closed'], [b(5), 'line']]), rel: { t: b(6.25), kind: 'set' } },
    { from: b(7.5), seq: viaOpen([[0, 'fan_closed'], [b(8.5), 'wings'], [b(10), 'falling']]), rel: { t: b(10) + 4 / 12, kind: 'fall' } },   // lets go on card 3: the morph is the fall
    { from: b(12.25), seq: viaOpen([[0, 'fan_closed'], [b(13), 'fox'], [b(14.5), 'crow'], [b(16), 'boy'], [b(17.5), 'mother'], [b(19), 'book'], [b(20.5), 'fan_closed']]) },
  ].map(P => ({ ...P, names: PUPPET.morphs(P.seq) }));
  const LAP = { forearm: 40, hand: 25, upperarm: 6 }, EYE = { forearm: -12, hand: 8, upperarm: 0 };
  const arm = PUPPET.snap([[0, { forearm: 0, hand: 0, upperarm: 0 }], [b(.9), EYE],
    [b(5) - B / 4, { forearm: -6, hand: 0, upperarm: 0 }], [b(5.75), { forearm: 30, hand: -30, upperarm: -20 }],   // the line, lowered to the floor
    [b(6.75), LAP], [b(7.75), EYE],                                                                                   // to her sleeve; a new fan
    [b(8.5) - B / 4, { upperarm: -60, forearm: 30, hand: -5 }],                                                       // wings held high, out front
    [b(11), LAP], [b(12.5), EYE],
    [b(13) - B / 4, { forearm: 34, hand: -12, upperarm: 14 }], [b(14.5) - B / 4, { upperarm: -50, forearm: 62, hand: -25 }],   // the crow, up and out: looking down at the fox's place [b(16) - B / 4, { forearm: 8, hand: -2, upperarm: 3 }],
    [b(17.5) - B / 4, { forearm: 30, hand: -14, upperarm: 18 }], [b(19) - B / 4, { forearm: 16, hand: -6, upperarm: 8 }], [b(20.5) - B / 4, EYE]]);
  const head = PUPPET.snap([[0, { head: 0 }], [b(6.3), { head: 9 }], [b(7.6), { head: 0 }], [b(10.6), { head: 12 }], [b(12.3), { head: 0 }]]);   // she watches what she set down
  const poseAt = tt => { const q = Math.floor(tt * 12 + 1e-6) / 12, p = { ...arm(q), ...head(q), _ghost: {} }; p.hair = -((p.head || 0) + (p.torso || 0)) * .85; return p; };
  const gripAt = tt => { const Mh = FABLE.world(poseAt(tt), T).hand.translate(FAN_GRIP[0], FAN_GRIP[1]), o = Mh.transformPoint(new DOMPoint(0, 0)); return { x: o.x, y: o.y, ang: Math.atan2(Mh.b, Mh.a) * 180 / Math.PI }; };
  LOOPS.fablefan = t => {
    const tq = Math.floor(t * 12 + 1e-6) / 12;
    X.fillStyle = '#0d0b0a'; X.fillRect(0, 0, W, H);
    screen(tq, { stops: FABLE_LAMP, tex: .32 });
    const p = poseAt(tq), props = [], loose = [];
    for (const P of PROPS) {
      if (tq < P.from) continue;
      const seq = tt => P.names(tt);                     // keys are absolute times
      if (!P.rel || tq < P.rel.t) { props.push(fanProp(seq, tq)); continue; }
      // released: from the grip at release time, to the floor (world coordinates, canvas px)
      const g = gripAt(P.rel.t), dt = tq - P.rel.t, [a0, b0, u0] = seq(P.rel.t), sh = PUPPET.shapeAt(FAN, fanShape(b0), fanShape(b0), 1);
      let Mx;
      if (P.rel.kind === 'set') {                        // lowered level onto the floor in two drawings, then it stays
        const k = Math.min(1, Math.floor(dt * 12 + 1e-6) / 2), y = g.y + (FLOOR - 12 - g.y) * k;
        Mx = new DOMMatrix().translate(g.x, y).rotate(90).scale(T.s);
      } else {                                           // Icarus falls (gravity, a slow tumble), lands and lies on the floor
        const d = Math.floor(dt * 12 + 1e-6) / 12, y = Math.min(FLOOR - 30, g.y + 2600 * d * d), landed = y >= FLOOR - 30;
        const x = g.x + 330 * Math.min(1, d / .45);    // tossed forward as he falls, clear of her sleeve and knees, onto open floor
        Mx = new DOMMatrix().translate(x, landed ? FLOOR - 30 : y).rotate(landed ? 88 : 60 * Math.min(1, d / .45)).scale(T.s);
      }
      loose.push(Mx.multiply(new DOMMatrix()).translate(0, 0)); loose[loose.length - 1].sh = sh;
    }
    shadow(c => {
      c.globalCompositeOperation = 'source-over';
      for (const Mx of loose) PUPPET.drawShape(c, Mx.sh, Mx);
      FABLE.draw(c, p, T, { props });
      c.setTransform(1, 0, 0, 1, 0, 0); c.fillStyle = 'rgb(22,22,26)'; c.fillRect(150, FLOOR, 1620, 10);
    }, 0);
    X.save(); X.globalCompositeOperation = 'overlay'; X.globalAlpha = .16; X.fillStyle = X.createPattern(GRAIN[Math.floor(tq * 12) % 4], 'repeat'); X.fillRect(0, 0, W, H); X.restore();
  };
  LOOPS.fablefan.len = b(22);
}

// LOOPS.fablecrab: the crab leaves the hand (verse 1: "once upon a time there was a crab"): the fan becomes the crab in her
// hand, it hops down to the stage floor, scuttles sideways (small hops on twos, a rock on each landing), stops, scuttles back,
// hops up into her hand, and is the fan again.
{
  const B = 60 / 170 * 4, b = n => n * B, beat = B / 2, FLOOR = 962, SC = .3;
  const seq = PUPPET.morphs([[0, 'fan_closed'], [b(1), 'crab'], [b(7), 'fan_closed']]);
  // the empty hand goes to her lap while the crab is out, and comes back up to receive it (Fable)
  const arm = PUPPET.snap([[0, { forearm: 0, hand: 0 }], [b(.6), { forearm: -12, hand: 8 }], [b(2) - B / 4, { forearm: 10, hand: -6 }], [b(2.6), { forearm: 40, hand: 25, upperarm: 6 }],
                           [b(5.6), { forearm: 10, hand: -6, upperarm: 0 }], [b(6.5), { forearm: -12, hand: 8 }], [b(8), { forearm: 0, hand: 0 }]]);
  // the crab's world path (canvas px of its grip point): keyed stops; each move between stops = hops of `step` px on twos
  const STOPS = [[b(2), 'hand'], [b(2.5), [1300, FLOOR]], [b(4), [1560, FLOOR]], [b(4.5), [1560, FLOOR]], [b(5.9), [1300, FLOOR]], [b(6.3), 'hand']];   // a crab-width clear of her hem
  const LOOPT = b(8.5);
  LOOPS.fablecrab = t => {
    const tq = Math.floor(t * 12 + 1e-6) / 12;
    X.fillStyle = '#0d0b0a'; X.fillRect(0, 0, W, H);
    screen(tq, { stops: FABLE_LAMP, tex: .32 });
    const T = { x: 620, y: 960, s: SC, origin: [1150, 2760] }, p = { ...arm(tq), _ghost: {} };
    // her head follows the crab while it's out (on twos, a step behind): tilted down toward where it is on the floor
    const out = tq >= STOPS[0][0] + 1 / 6 && tq < STOPS[STOPS.length - 1][0];
    p.head = out ? 7 + 5 * Math.min(1, Math.max(0, (tq - b(2.5)) / (b(4) - b(2.5)))) * (tq < b(4.5) ? 1 : Math.max(0, 1 - (tq - b(4.5)) / (b(5.9) - b(4.5)))) : 0;
    p.hair = -p.head * .85;
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

// LOOPS.fanpose: presentation-pose trials (one per second): which arm pose holds Icarus clear of her body
{
  const TRY = [{ upperarm: -35, forearm: -10, hand: 20 }, { upperarm: -50, forearm: 10, hand: 10 }, { upperarm: -60, forearm: 30, hand: -5 }, { upperarm: -45, forearm: -30, hand: 30 }];
  LOOPS.fanpose = t => {
    const k = Math.min(TRY.length - 1, Math.floor(t)), p = { ...TRY[k], _ghost: {} };
    X.fillStyle = '#0d0b0a'; X.fillRect(0, 0, W, H); screen(0, { stops: FABLE_LAMP, tex: .32 });
    shadow(c => { c.globalCompositeOperation = 'source-over'; FABLE.draw(c, p, { x: 700, y: 960, s: .3, origin: [1150, 2760] }, { props: [fanProp(() => ['falling', 'falling', 1], 0)] }); }, 0);
    X.fillStyle = '#ffdc5a'; X.font = '26px monospace'; X.fillText(JSON.stringify(TRY[k]), 30, 50);
  };
  LOOPS.fanpose.len = TRY.length;
}
