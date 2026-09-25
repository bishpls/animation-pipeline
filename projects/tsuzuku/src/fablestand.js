// fablestand.js: the standing puppet (LOOPS.fablestand): she stands, holds, walks two geta steps toward the frame's edge (B8),
// looks back, and stops. A walk under an ankle-length skirt reads through the skirt: in each step the hem kicks forward as the
// leg swings under it, the body rises through the passing position and settles on the contact, the foot lifts heel-first and
// lands flat, the arm counter-swings. The body advances a little on every drawing (on twos), not in a jump.
// makeWalk(STEPS, S, dur): a walk as a pure function of time. STEPS [{t, foot: 'v' | 'h', close}] (the visible foot, the hidden
// one; close = bring it level with the other), stride S (canvas px), each step taking `dur` s. Returns tq -> pose
// {dx, dy, skirt, leg, foot, foot.y, upperarm, torso} for the standing puppet at scale SC.
function makeWalk(STEPS, S = 130, dur = 60 / 170 * 2, SC = .22, LEG = 1280) {
  const plan = (() => {                                                // each foot's plants (world x, canvas px) after each step
    let v = 0, h = 0; const P = [{ v, h }];
    for (const st of STEPS) { const s = st.S ?? S; if (st.foot === 'v') v = st.close ? h : h + s; else h = st.close ? v : v + s; P.push({ v, h }); }   // (a step may set its own stride)
    return P;
  })();
  const ease = u => u * u * (3 - 2 * u), D = st => st.dur ?? dur;     // (a step may set its own duration)
  return tq => {
    let k = STEPS.findIndex(st => tq < st.t + D(st) && tq >= st.t), u = 0;
    let feet, body;
    if (k < 0) { const done = STEPS.filter(st => tq >= st.t + D(st)).length; feet = plan[done]; body = (feet.v + feet.h) / 2; }
    else {
      u = (tq - STEPS[k].t) / D(STEPS[k]); const a = plan[k], b = plan[k + 1], e = ease(u);
      feet = { v: a.v + (b.v - a.v) * e, h: a.h + (b.h - a.h) * e };   // the swinging foot eases; the planted one stays put
      body = (a.v + a.h) / 2 + ((b.v + b.h) - (a.v + a.h)) / 2 * u;     // the body glides through the step (no stop at each footfall)
    }
    const ang = f => -Math.asin(Math.max(-.9, Math.min(.9, (f - body) / SC / LEG))) * 180 / Math.PI;
    const av = ang(feet.v), ah = ang(feet.h);
    const swingV = k >= 0 && STEPS[k].foot === 'v', swingH = k >= 0 && STEPS[k].foot === 'h', stance = swingV ? ah : av;
    const r = stance * Math.PI / 180, OX = -44;                        // (the ankle sits 44 master px behind the hip)
    const p = { dx: body, dy: (LEG - (OX * Math.sin(r) + LEG * Math.cos(r))) * SC };   // the stance leg sets the hip height: its foot stays on the rail
    p.skirt = .25 * av;                                                // the hem kicks a little with the near leg (a quarter as far): both ankles stay under it
    p.leg = av - p.skirt;
    const w = k >= 0 ? Math.sin(Math.PI * u) : 0;
    p.foot = -av;                                                      // a foot on the rail stays flat (undo the leg's angle)
    if (swingV) {                                                      // the swinging foot lifts clear: heel first, then the toe up to land
      p['foot.y'] = -55 * w; p.foot += u < .6 ? 10 * Math.sin(Math.PI * u / .6) : -5 * Math.sin(Math.PI * (u - .6) / .4);
    }
    // the far foot (its own geta, behind the skirt): the hidden leg's angle, lifting when it swings
    p._far = { leg: ah - p.skirt, foot: -ah + (swingH ? (u < .6 ? 10 * Math.sin(Math.PI * u / .6) : -5 * Math.sin(Math.PI * (u - .6) / .4)) : 0), 'foot.y': swingH ? -55 * w : 0 };
    const t0 = STEPS.length ? STEPS[0].t : 0, span = STEPS.length ? STEPS[STEPS.length - 1].t + D(STEPS[STEPS.length - 1]) - t0 : 1;
    p.upperarm = 5 * Math.sin(Math.PI * 2 * Math.min(1, (tq - t0) / span) * Math.max(1, STEPS.length / 3)) * (tq > t0 && tq < t0 + span ? 1 : 0);   // arm counter-swing
    p.torso = -1.2 * w;                                                // a slight lean into each step
    return p;
  };
}
// her arm as two links (standing master px): shoulder, elbow, and her fist's grip (the forearm and hand as one). standReach()
// returns the pose that puts the fist on a target (canvas px), given the shoulder's canvas position and the puppet's scale;
// the elbow drops (it bends down, never up)
const STAND_ARM = (() => { const SH = [1036, 960], EL = [1156, 1422], FI = [1420, 2090];
  return { SH, EL, FI, L1: Math.hypot(EL[0] - SH[0], EL[1] - SH[1]), L2: Math.hypot(FI[0] - EL[0], FI[1] - EL[1]),
    R1: Math.atan2(EL[1] - SH[1], EL[0] - SH[0]), R2: Math.atan2(FI[1] - EL[1], FI[0] - EL[0]) }; })();
function standReach(sx, sy, tx, ty, sc) {
  const { L1, L2, R1, R2 } = STAND_ARM, D = 180 / Math.PI;
  const Dx = (tx - sx) / sc, Dy = (ty - sy) / sc, d = Math.min(Math.hypot(Dx, Dy), L1 + L2 - 1), phi = Math.atan2(Dy, Dx);
  const a = Math.acos(Math.max(-1, Math.min(1, (L1 * L1 + d * d - L2 * L2) / (2 * L1 * d)))), t1 = phi + a;
  const t2 = Math.atan2(Dy - L1 * Math.sin(t1), Dx - L1 * Math.cos(t1));
  return { upperarm: (t1 - R1) * D, forearm: ((t2 - R2) - (t1 - R1)) * D, hand: 0 };
}
// the standing puppet with both feet: the far foot first (behind the skirt), then the puppet
function drawStanding(c, p, T, o = {}) {
  if (p._far) {                                                        // the geta and its ankle, not the tall stub above it
    const pf = { ...p, leg: p._far.leg, foot: p._far.foot, 'foot.y': p._far['foot.y'] }, M = FABLE_S.world(pf, T);
    c.save(); c.setTransform(M.foot); c.beginPath(); c.rect(-3000, 3396 - 95, 8000, 3000); c.clip();   // the geta and a short ankle post (it reaches the hem)
    FABLE_S.draw(c, pf, T, { hide: FABLE_S.parts.map(q => q.name).filter(n => n !== 'foot') }); c.restore();   // the far geta cut like the near one (Michael: solid read as a bug)
  }
  FABLE_S.draw(c, p, T, o);
}
{
  const B = 60 / 170 * 4, beat = B / 2;
  // three steps, one per beat: the visible foot, the hidden foot, the visible foot again (ending feet together)
  const walk = makeWalk([{ t: 3 * beat, foot: 'v' }, { t: 4 * beat, foot: 'h' }, { t: 5 * beat, foot: 'v', close: true }], 130, beat);
  const rest = PUPPET.snap([[0, { head: 0 }], [7 * beat, { head: -9 }], [9 * beat, { head: 0 }]]);
  const pose = tt => { const tq = Math.floor(tt * 12 + 1e-6) / 12, p = { ...walk(tq), head: rest(tq).head, _ghost: {} }; p.hair = -(p.head + p.torso) * .85; return p; };
  const TAILS = [{ len: 2500, w: 118, rest: [97, 100, 104, 107, 108, 105, 100] }, { len: 2150, w: 104, rest: [100, 104, 108, 111, 110, 104, 99] }];
  LOOPS.fablestand = t => {
    const tq = Math.floor(t * 12 + 1e-6) / 12;
    X.fillStyle = '#0d0b0a'; X.fillRect(0, 0, W, H);
    screen(tq, { stops: FABLE_LAMP, tex: .32 });
    const T = { x: 700, y: 905, s: .22, origin: [1100, 3700] }, p = pose(tq);
    shadow(c => {
      TAILS.forEach((tl, i) => {
        const pts = PUPPET.stiff(FABLE_S, pose, T, { part: 'head', at: [900, 820], rest: tl.rest, len: tl.len, drag: .1 }, tq);
        c.setTransform(1, 0, 0, 1, 0, 0); c.globalCompositeOperation = i ? 'multiply' : 'source-over';
        c.fillStyle = FABLE_GEL; c.fill(P(PUPPET.strip(pts, tl.w * T.s, .85, tl.w * .9 * T.s)));
      });
      c.globalCompositeOperation = 'source-over';
      drawStanding(c, p, T, { rods: [{ part: 'torso', at: [1060, 1700], w: 7 }] });
      c.setTransform(1, 0, 0, 1, 0, 0); c.fillStyle = 'rgb(22,22,26)'; c.fillRect(150, 905, 1620, 16);   // the stage floor rail
    }, 0);
    X.save(); X.globalCompositeOperation = 'overlay'; X.globalAlpha = .16; X.fillStyle = X.createPattern(GRAIN[Math.floor(tq * 12) % 4], 'repeat'); X.fillRect(0, 0, W, H); X.restore();
  };
  LOOPS.fablestand.len = 10 * beat;
}
