// paperink.js: C2 and B7 restaged in the paper theatre (Michael: "the stylistic shift of the image-composited internal
// narrative is jarring... reconceptualize via the language of the paper-puppet stage"; Fable's rulings, verbatim in the
// comments below). This file redefines LOOPS.inklamp and LOOPS.inkstand; ink.js keeps its ink drawings and loops (the
// making-of shows them) and is overridden here by script order. Same names, S0 and len; film.js dispatches them in local
// seconds. Sound: C2's match is registered here (at the strike); ink.js keeps the lantern's handle (RAISE - 1/12) and
// the geta (GETA); B7's lamp slide is registered here too. The pictures land on those times.
{
  const f = 1 / 12, FLOOR = 962, INK = 'rgb(22,22,26)';
  const q12 = t => Math.floor(t * 12 + 1e-6) / 12;
  const ease = u => { u = Math.max(0, Math.min(1, u)); return u * u * (3 - 2 * u); };
  const mix = (a, b, u) => a + (b - a) * u, mix2 = (a, b, u) => [mix(a[0], b[0], u), mix(a[1], b[1], u)];
  // a camera (stage() takes butai px) from the theatre point it centres and its theatre -> screen scale
  const KX = () => (BUTAI.win[2] - BUTAI.win[0]) / SCREEN.rect[2], KY = () => (BUTAI.win[3] - BUTAI.win[1]) / SCREEN.rect[3];
  const camAt = (tx, ty, k) => ({ x: BUTAI.win[0] + (tx - SCREEN.rect[0]) * KX(), y: BUTAI.win[1] + (ty - SCREEN.rect[1]) * KY(), zoom: k / KX() });
  const grain = (ts, a = .16) => { X.save(); X.globalCompositeOperation = 'overlay'; X.globalAlpha = a; X.fillStyle = X.createPattern(GRAIN[Math.floor(ts * 12) % 4], 'repeat'); X.fillRect(0, 0, W, H); X.restore(); };
  // one part of a puppet under a matrix: its paper, then its cut-outs punched through
  function part(c, pup, name, M, ink = INK) {
    const q = pup.by[name]; c.setTransform(M); c.globalCompositeOperation = 'source-over'; c.fillStyle = ink; c.fill(q.outlineP);
    c.globalCompositeOperation = 'destination-out'; c.fill(q.holesP); c.globalCompositeOperation = 'source-over';
  }
  // a stiff cellophane strip (the ribbon) on a root that may change puppets: PUPPET.stiff's rule (lags one drawing, settles in
  // about three, pulled toward its drawn curve and toward hanging), with the root given as a function of time. rootAt(tt) ->
  // { x, y, rot (deg), s (px per master px), rest: [deg], len (master px) }, always computed facing right; the caller mirrors
  function stiffAt(rootAt, q0, o = {}) {
    const k = o.follow ?? .55, gw = o.gravity ?? .35, pre = o.preroll ?? 1.5;
    let ang = null, prev = null, pprev = null;
    for (let tt = q0 - pre; tt <= q0 + 1e-6; tt += f) {
      const F = prev || rootAt(tt), n = F.rest.length, vx = pprev ? (F.x - pprev.x) / F.s : 0;
      const g = F.gw ?? gw, want = F.rest.map((r, i) => (1 - g) * (r + F.rot) + g * 90 + Math.max(-40, Math.min(40, vx * (o.drag ?? .09) * (i + 1) / n)));
      pprev = F; ang = ang ? ang.map((a, i) => a + (want[i] - a) * k) : want; prev = rootAt(tt);
    }
    const F = rootAt(q0), seg = F.len / F.rest.length * F.s, P = [[F.x, F.y]];
    for (let i = 0; i < ang.length; i++) { const a = ang[i] * Math.PI / 180, p = P[i]; P.push([p[0] + Math.cos(a) * seg, p[1] + Math.sin(a) * seg]); }
    return P;
  }
  const mirror = (P, cx) => P.map(([x, y]) => [2 * cx - x, y]);
  const ribbonStrip = (c, P, w) => { c.setTransform(1, 0, 0, 1, 0, 0); c.fillStyle = FABLE_GEL; c.fill(window.P(PUPPET.strip(P, w, .85, w * .9))); };
  const TAILS_SEAT = [{ len: 1900, w: 118, rest: [96, 101, 107, 112, 114, 110, 103] }, { len: 1600, w: 104, rest: [99, 106, 113, 118, 116, 108, 100] }];
  const TAILS_STAND = [{ len: 2500, w: 118, rest: [97, 100, 104, 107, 108, 105, 100] }, { len: 2150, w: 104, rest: [100, 104, 108, 111, 110, 104, 99] }];

  // =========================================================================================================================
  // B7, the standing up (song 161.0-166.0). Fable: "The puppet, close. The camera close to the window as at 'Hm.', the pool
  // low, the figure rising out of it into the darker vellum, pleats unstacking, geta clack, the hands' two small starts.
  // 'Standing up out of the light' survives literally."
  // One static camera, close on the vellum (her whole standing height fills it; no wood, no readers). The light is B6's: the
  // lamp on the floor behind her (428), its pool low at the left of the frame, the vellum darkening up and to the right.
  //   161.0   seated with the book on "down the book...", still: the longest hold in the film (two seconds)
  //   163.0   the book lifted (a small start); she bows and sets it on the floor in front of her knees; she straightens,
  //           hands empty in her lap
  //   164.33  she kneels up (the seated card replaced by the standing one, its old self faint for two drawings); the near knee
  //           comes up over the book, the foot planted beyond it (the book is under her knee until she rises); held
  //   164.83  the rise, four drawings, the head always higher than the drawing before (weight rising: no collapse): the
  //           pleats unstack as the skirt lengthens (its earlier states faint behind it); in the last in-between she turns on
  //           the planted foot to face what she set down
  //   165.17  standing, feet together, on the geta clack (165.18)
  //   165.33  her empty hands: two small starts toward the book, and back
  //   166.0   cut to B8 at the window (bridge.js): the same pose (standing, facing left, arms at rest, head 6, the ribbon
  //           settled), her screen x within ~60 px of B8's, the book at her feet, the cushion empty behind it. The lamp is the
  //           one thing that doesn't carry: B6 leaves it at 428 (left of the cushion, no stick) and B8 opens with it at 830
  //           (right of the cushion, stick leaning); this shot keeps B6's, in its pool, so it moves across the cut to B8.
  {
    const S0 = 161.0, S1 = 166.0, NOTE = 159.53, BEAT = 60 / 170 * 2, GETA = NOTE + 8 * BEAT;   // (165.18: ink.js registers the clack)
    const HOT = [[0, '#FFF7E6'], [.3, '#FDE6B8'], [.7, '#EDB878'], [1, '#93643A']], LSC = 1.4, LAMPX = 428;   // B6's light (bridge.js bare())
    const CP = { x: 1640, y: FLOOR, s: .16, origin: [1076, 2800] }, CPOSE = { skirt: 11, head: 15, upperarm_L: -41, forearm_L: -6, upperarm_R: 18, forearm_R: 6, _ghost: {} };
    const TSEAT = { x: 560, y: 960, s: .2, origin: [1150, 2760] };                // B6's seated puppet
    const LAP = { forearm: 40, hand: 25, upperarm: 6 }, LIFTED = { forearm: 28, hand: 16, upperarm: 2 };
    const CAM7 = () => camAt(846, 612, 1.45);
    // the beats (song s, on the drawing grid)
    const LIFT = 163.0, BOW0 = 163.25, BOW1 = BOW0 + 4 * f, REL = BOW1 + 2 * f, UP0 = REL, UP1 = UP0 + 4 * f;
    const K0B = 164 + 4 * f, K1 = K0B + f, K2 = K1 + 2 * f, R1 = 164 + 10 * f, LAND = 165 + 2 * f, START = LAND + 2 * f;
    const BOOK = { x: 825, s: .15 };                                              // on the floor in front of her knees (B8 draws it at .15)
    const BOW = 48;                                                               // (the reach to the floor from seiza)
    // ---- the seated card (161.0-164.25) -----------------------------------------------------------------------------
    const lift = PUPPET.snap([[0, LAP], [LIFT, LIFTED]]);
    const torsoAt = q => q < BOW0 ? 0 : q < BOW1 + 1e-6 ? BOW * ease((q - BOW0) / (BOW1 - BOW0)) : q < UP0 ? BOW : BOW * (1 - ease((q - UP0) / (UP1 - UP0)));
    const headAt = q => q < BOW0 ? 8 : q < UP1 ? 8 + 6 * ease((q - BOW0) / (BOW1 - BOW0)) * (q < UP0 ? 1 : 1 - ease((q - UP0) / (UP1 - UP0))) : 12;   // she watches the book
    const bookGrip = [BOOK.x, FLOOR];
    function seatPose(tt) {
      const q = q12(tt), p = { torso: torsoAt(q), head: headAt(q), _ghost: {} };
      let arm = lift(q);
      if (q >= BOW0) {                                                             // down to the floor with the bow, and back to her lap
        const reach = reachIn(FABLE, p, TSEAT, 'torso', SEAT_ARM, bookGrip);
        const u = q < BOW1 + 1e-6 ? ease((q - BOW0) / (BOW1 - BOW0)) : q < UP0 ? 1 : 1 - ease((q - UP0) / (UP1 - UP0));
        const from = q < UP0 ? LIFTED : LAP;
        arm = { upperarm: mix(from.upperarm, reach.upperarm, u), forearm: mix(from.forearm, reach.forearm, u), hand: mix(from.hand, reach.hand, u) };
      }
      if (q >= K0B - 1e-6) { p.torso = 9; p['torso.y'] = -120; p.head = 6; Object.assign(p, reachIn(FABLE, p, TSEAT, 'torso', SEAT_ARM, [700, 860])); }   // (the swap's first in-between: off her heels, hands pushing on her thighs)
      else Object.assign(p, arm);
      p.hair = -(p.head + p.torso * .3) * .85; return p;
    }
    const bookSeq = () => ['book', 'book', 1];
    // the book this drawing: in her fist (a prop) until she lets go, then on the floor; it shrinks to the floor size (B8's) as
    // it's lowered (the drawings of the bow), so what she sets down is what B8 finds
    const bookScale = q => q < BOW0 ? .2 : q >= BOW1 ? BOOK.s : mix(.2, BOOK.s, ease((q - BOW0) / (BOW1 - BOW0)));
    function drawSeated(c, tt, o = {}) {
      const q = q12(tt), p = seatPose(q), held = q < REL;
      if (!o.solid) drawRibbon(c, q);
      const props = held ? [fanProp(bookSeq, q, M => { const Mx = M.hand.translate(FAN_GRIP[0], FAN_GRIP[1]), o0 = Mx.transformPoint(new DOMPoint(0, 0));
        return new DOMMatrix().translate(o0.x, o0.y).scale(bookScale(q)); })] : [];
      FABLE.draw(c, p, TSEAT, { props, rods: FABLE_RODS, ink: o.ink });
    }
    // ---- the standing card, from kneeling up to standing (164.33 on) ---------------------------------------------------
    // Built from the standing puppet's parts: its upper body as drawn; its skirt re-cut in code for the kneel (warped: the
    // pleats stack as it shortens and unstack as it lengthens); its feet placed on the floor. Each drawing: the hip (canvas
    // px), the scale (the seated card is drawn larger than the standing one: the standing parts start at its size and settle
    // to .2 through the rise), the lean, the head, the skirt's shape, the feet, the near fist.
    const HIPM = [1030, 2116], HEMY = 3380, ANK = [986, 3396];
    const FRONT = { x: 955 };                                                     // the planted foot's ankle (beyond the book)
    // the rise, drawing by drawing ([t, {...}]): hip, s, torso, head, skirt { lam (0 = its own cut, 1 = the knelt shape),
    // back: the back hem on the floor, knee: the raised knee, hem: the front hem }, back foot { x, lift, tilt }, fist target
    const KEYS = [
      [K1, { hip: [650, 845], s: .25, torso: 16, head: -4, sk: { lam: 1, back: [560, FLOOR - 2], knee: null, hem: [784, FLOOR - 2] }, bf: null, fist: 'thigh', front: false }],
      [K1 + f, { hip: [722, 834], s: .248, torso: 13, head: -2, sk: { lam: 1, back: [610, FLOOR - 2], knee: [892, 842], hem: [958, 932] }, bf: null, fist: 'thigh', front: false, lifted: { x: 912, lift: 16 } }],   // (the knee coming up, the foot in the air)
      [K2, { hip: [785, 824], s: .245, torso: 10, head: 0, sk: { lam: 1, back: [660, FLOOR - 2], knee: [950, 818], hem: [1005, 912] }, bf: null, fist: 'knee', front: true }],
      [R1, { hip: [825, 795], s: .24, torso: 16, head: -5, sk: { lam: .85, back: [705, FLOOR - 3], knee: [965, 790], hem: [1008, 908] }, bf: { x: 728, lift: 0, tilt: 40 }, fist: 'knee', front: true }],
      [R1 + f, { hip: [875, 750], s: .228, torso: 12, head: -3, sk: { lam: .55, back: [770, FLOOR - 4], knee: [975, 752], hem: [1005, 902] }, bf: { x: 800, lift: 0, tilt: 24 }, fist: 'hang', front: true }],
      [R1 + 2 * f, { hip: [918, 705], s: .214, torso: 6, head: 2, sk: { lam: .25, back: [870, 910], knee: [982, 722], hem: [1000, 900] }, bf: { x: 885, lift: 24, tilt: 8 }, fist: 'rest', front: true }],
      [R1 + 3 * f, { hip: [946, 668], s: .205, torso: 2, head: 5, flip: true, sk: { lam: .05 }, bf: { x: 0, lift: 8, tilt: 0 }, fist: 'rest', front: true }],
      [LAND, { hip: [946, 645], s: .2, torso: -1.5, head: 6, flip: true, sk: { lam: 0 }, bf: { x: 0, lift: 0, tilt: 0 }, fist: 'rest', front: true }],
      [LAND + f, { hip: [946, 645], s: .2, torso: 0, head: 6, flip: true, sk: { lam: 0 }, bf: { x: 0, lift: 0, tilt: 0 }, fist: 'rest', front: true }],
    ];
    const keyAt = q => { let k = KEYS[0][1]; for (const [t, v] of KEYS) if (q >= t - 1e-6) k = v; return k; };
    // the hands' two small starts (after the clack): toward the book and back, on twos, snapped (in-between, past, pose)
    const starts = PUPPET.snap([[0, { u: 0 }], [START, { u: 1 }], [START + 2 * f, { u: 0 }], [START + 3 * f, { u: .8 }], [START + 5 * f, { u: 0 }]]);
    // the skirt's own cut: its edges at a master height (straight fits of its sides, hip to hem)
    const SKL = y => 808 - (y - 2200) * .128, SKR = y => 1311 + (y - 2200) * .098;
    function standT(k) { const s = k.s, d = k.flip ? -1 : 1; return { x: k.hip[0] + d * (1100 - HIPM[0]) * s, y: k.hip[1] + (3700 - HIPM[1]) * s, s, origin: [1100, 3700], flip: d }; }
    // the skirt's warp: master point -> canvas (facing right; the caller mirrors). Above the hip it rides the hip rigidly
    function skirtMap(k) {
      const [hx, hy] = k.hip, s = k.s, lam = k.sk.lam, own = y => [[hx + (SKL(y) - HIPM[0]) * s, hy + (y - HIPM[1]) * s], [hx + (SKR(y) - HIPM[0]) * s, hy + (y - HIPM[1]) * s]];
      const [h0L, h0R] = own(HIPM[1]);
      const bez = (a, c, b, t) => [(1 - t) * (1 - t) * a[0] + 2 * (1 - t) * t * c[0] + t * t * b[0], (1 - t) * (1 - t) * a[1] + 2 * (1 - t) * t * c[1] + t * t * b[1]];
      const knelt = v => {
        const back = k.sk.back || [h0L[0], FLOOR], hem = k.sk.hem || [h0R[0], FLOOR];
        const B = bez(h0L, [h0L[0] - 20 * s / .2, (h0L[1] + back[1]) / 2], back, v);   // the back falls, a little full
        let F;
        if (k.sk.knee) { const K = k.sk.knee, C = [2 * K[0] - (h0R[0] + hem[0]) / 2, 2 * K[1] - (h0R[1] + hem[1]) / 2]; F = bez(h0R, C, hem, v); }   // over the knee
        else F = bez(h0R, [hem[0] + 6, h0R[1] + (hem[1] - h0R[1]) * .45], hem, v);                                           // down to the knees
        return [B, F];
      };
      return (mx, my) => {
        if (my <= HIPM[1]) return [hx + (mx - HIPM[0]) * s, hy + (my - HIPM[1]) * s];
        const v = Math.min(1.02, (my - HIPM[1]) / (HEMY - HIPM[1])), y = my, [oL, oR] = own(y), a = (mx - SKL(y)) / (SKR(y) - SKL(y));
        let L = oL, R = oR;
        if (lam > 0) { const [kL, kR] = knelt(Math.min(1, v)); L = mix2(oL, kL, lam); R = mix2(oR, kR, lam); }
        return [L[0] + a * (R[0] - L[0]), L[1] + a * (R[1] - L[1])];
      };
    }
    // the skirt, re-cut through the map (outline and slits), its rivets kept round
    let SKD = null;
    function skirtData() {
      if (SKD) return SKD;
      const q = FABLE_S.by.skirt, rv = [], cuts = [];
      for (const h of q.holes) { const xs = h.map(p => p[0]), ys = h.map(p => p[1]), w = Math.max(...xs) - Math.min(...xs), hh = Math.max(...ys) - Math.min(...ys);
        if (w < 48 && hh > 16 && Math.abs(w - hh) < 10) rv.push([(Math.max(...xs) + Math.min(...xs)) / 2, (Math.max(...ys) + Math.min(...ys)) / 2, w / 2]); else cuts.push(h); }
      return (SKD = { outline: q.outline, cuts, rv });
    }
    function drawSkirt(c, k, flipX, o = {}) {
      const D = skirtData(), m = skirtMap(k), fx = p => flipX == null ? p : [2 * flipX - p[0], p[1]];
      const path = polys => { const P2 = new Path2D(); for (const poly of polys) { poly.forEach((pt, i) => { const [x, y] = fx(m(pt[0], pt[1])); i ? P2.lineTo(x, y) : P2.moveTo(x, y); }); P2.closePath(); } return P2; };
      c.setTransform(1, 0, 0, 1, 0, 0); c.globalCompositeOperation = 'source-over'; c.fillStyle = o.ink || INK; c.fill(path(D.outline));
      if (o.solid) return;
      c.globalCompositeOperation = 'destination-out'; c.fill(path(D.cuts));
      for (const [x, y, r] of D.rv) { const [px, py] = fx(m(x, y)); c.beginPath(); c.arc(px, py, r * k.s, 0, 7); c.fill(); }
      c.globalCompositeOperation = 'source-over';
    }
    // a geta (the standing puppet's foot part) with its ankle at (ax, FLOOR - lift - ankle height), tilted (+ = heel up) about
    // its toe; cut to the geta and a short ankle post (as drawStanding cuts the far foot), so no post shows above the skirt
    function drawFoot(c, ax, lift, tilt, s, dir, o = {}) {
      const ay = FLOOR - (3682 - ANK[1]) * s - lift;                               // (its sole on the rail, as the lamp and the book sit on it)
      let M = new DOMMatrix().translate(ax, ay).rotate(dir * tilt).scale(dir * s, s).translate(-ANK[0], -ANK[1]);
      if (tilt) { const toe = M.transformPoint(new DOMPoint(1290, 3680)); M = new DOMMatrix().translate(0, FLOOR - lift - toe.y).multiply(M); }
      c.save(); c.setTransform(M); c.beginPath(); c.rect(-3000, ANK[1] - 95, 8000, 3000); c.clip();
      part(c, FABLE_S, 'foot', M, o.ink); c.restore();
    }
    const shoulderOf = (p, T) => FABLE_S.world({ ...p, upperarm: 0, forearm: 0, hand: 0 }, T).torso.transformPoint(new DOMPoint(...STAND_ARM.SH));
    function standPose(q, k) {
      const T = standT(k), dir = T.flip, p = { torso: k.torso, head: k.head, _ghost: {} };
      const sh = shoulderOf(p, T), g = k.s / .2;
      const rest = [sh.x + dir * 18 * g, sh.y + 228 * g];                                        // (B8's 'rest')
      let tgt = rest;
      if (k.fist === 'thigh') tgt = [sh.x + dir * 70 * g, sh.y + 200 * g];
      else if (k.fist === 'knee' && k.sk.knee) tgt = [k.sk.knee[0] - 8, k.sk.knee[1] - 16];
      else if (k.fist === 'hang') tgt = [sh.x + dir * 40 * g, sh.y + 222 * g];
      if (q >= START - 1e-6) { const u = starts(q).u; tgt = [rest[0] + dir * 64 * u, rest[1] - 24 * u]; }   // forward, toward the book, clear of her sleeve; and back
      Object.assign(p, reachIn(FABLE_S, p, T, 'torso', STAND_ARM, tgt));
      p.hair = -(p.head + p.torso) * .85; return { p, T };
    }
    function drawStand(c, q, k, o = {}) {
      const { p, T } = standPose(q, k), dir = T.flip, fx = dir < 0 ? k.hip[0] : null, s = k.s;
      // the feet first (behind the skirt): the back foot, then the planted front one
      // (the feet at the standing scale throughout: a planted geta doesn't change size; flipped, the back foot lands beside the front)
      if (k.bf) drawFoot(c, dir < 0 ? FRONT.x + (k.bf.lift > 0 ? 20 : 0) : k.bf.x, k.bf.lift, k.bf.tilt, .2, dir, o);
      if (k.front) drawFoot(c, FRONT.x, 0, 0, .2, dir, o);
      else if (k.lifted) drawFoot(c, k.lifted.x, k.lifted.lift, 0, .2, dir, o);
      drawSkirt(c, k, fx, o);
      FABLE_S.draw(c, p, T, { hide: ['skirt', 'leg', 'foot'], rods: o.solid ? [] : [{ part: 'torso', at: [1060, 1700], w: 7 }], ink: o.ink, solid: o.solid });
      return { p, T };
    }
    // the ribbon's root: the seated head until she kneels up, then the standing head (lengths and curves blend with the rise)
    function ribbonRoot(i) {
      return tt => {
        const q = q12(tt);
        if (q < K1) { const p = seatPose(q), M = FABLE.world(p, TSEAT).head, pt = M.transformPoint(new DOMPoint(905, 640)), tl = TAILS_SEAT[i];
          return { x: pt.x, y: pt.y, rot: Math.atan2(M.b, M.a) * 180 / Math.PI, s: .2, rest: tl.rest, len: tl.len, gw: .35 + .4 * p.torso / BOW }; }   // (in the bow it hangs more: a bookmark, not a flag)
        const k = keyAt(q), T = { ...standT(k), flip: 1, x: k.hip[0] - (1100 - HIPM[0]) * k.s }, { p } = standPose(q, { ...k, flip: false });
        const M = FABLE_S.world(p, T).head, pt = M.transformPoint(new DOMPoint(900, 820)), u = Math.min(1, Math.max(0, (845 - k.hip[1]) / 200));
        const a = TAILS_SEAT[i], b = TAILS_STAND[i];
        return { x: pt.x, y: pt.y, rot: Math.atan2(M.b, M.a) * 180 / Math.PI, s: k.s, rest: a.rest.map((r, j) => mix(r, b.rest[j], u)), len: mix(a.len * .2 / k.s, b.len, u) };   // (canvas length: seated 380 px -> standing 2500 s)
      };
    }
    function drawRibbon(c, q) {
      const k = keyAt(q), flip = q >= K1 && k.flip;
      [0, 1].forEach(i => {
        let P = stiffAt(ribbonRoot(i), q, { drag: .03 });
        if (flip) P = mirror(P, k.hip[0]);
        c.globalCompositeOperation = i ? 'multiply' : 'source-over'; ribbonStrip(c, P, TAILS_STAND[i].w * (q < K1 ? .2 : k.s));   // (seated and standing tails are the same widths)
      });
      c.globalCompositeOperation = 'source-over';
    }
    // the figure this drawing, into the shadow layer
    const HIDE_SEATED = ['lower', 'torso', 'head', 'hair', 'upperarm', 'forearm', 'hand'];
    function figure(c, q) {
      if (q < K1) { drawSeated(c, q); return; }
      FABLE.draw(c, { _ghost: {} }, TSEAT, { hide: HIDE_SEATED });                  // her zabuton, empty (as B8 has it)
      const k = keyAt(q);
      drawRibbon(c, q);
      drawStand(c, q, k);
    }
    // the book on the floor once she lets go
    const floorBook = (c, q) => { if (q >= REL - 1e-6) PUPPET.drawShape(c, PUPPET.shapeAt(FAN, 'book', 'book', 1), new DOMMatrix().translate(BOOK.x, FLOOR).scale(BOOK.s)); };
    // the lamp brought to her: B6 leaves it at 428 (left of the cushion); B8 opens with it at her feet on its rod, its stick
    // tipped toward her for the take. While she rises (the eye is on her), a kuroko slides it along the rail on its rod: on
    // twos, a start and a stop, the same distance every drawing (a rod-slid thing moves like a hand, not a curve), and the
    // pool travels with it. Its stick, drawn from B7's first drawing, leans away from her until then (clear of her kneeling
    // back, against the lit vellum) and tips over toward her as it comes.
    const GLIDE0 = 164 + 5 * f, GLIDEN = 7, L8 = 720, LEAN8 = 25;                   // (164.42 to 165.0; 720: just left of the book, clear of it, as far from her as B8 has it)
    const lampXAt = q => { const u = q < GLIDE0 - 1e-6 ? 0 : Math.min(1, (Math.floor((q - GLIDE0) * 12 + 1e-6) + 1) / (GLIDEN + 1)); return [LAMPX + (L8 - LAMPX) * u, u]; };
    PAPER_SFX.push(() => [[GLIDE0, 'paper_slide', -37]]);
    function scene7(ts) {
      const q = q12(ts), [lx, lu] = lampXAt(q), lamp = [lx, FLOOR - (7 + CHO.h / 2) * LSC];
      X.fillStyle = '#0d0b0a'; X.fillRect(0, 0, W, H);
      screen(ts, { stops: HOT, tex: .24, power: 1.02, lamp });
      shadow(c => {
        c.globalCompositeOperation = 'source-over'; c.fillStyle = INK; c.fillRect(150, FLOOR, 1620, 10);
        CLAWDP.draw(c, CPOSE, CP, { gel: CLAWD_GEL, misreg: [1.5, 1], rods: [{ part: 'torso', at: [1076, 1200], w: 5, lean: -70 }, { part: 'claw_R', at: [1640, 1600], w: 2.5, lean: 26 }] });
        c.setTransform(1, 0, 0, 1, 0, 0); floorBook(c, q);
        figure(c, q);
      }, 0);
      X.save(); X.strokeStyle = INK; X.lineWidth = 5; X.lineCap = 'round'; X.beginPath(); X.moveTo(lx, FLOOR - 4); X.lineTo(lx - 18, H + 20); X.stroke(); X.restore();   // its rod
      chochin(lx, FLOOR, LSC, { gold: true, stick: LEAN8 * (2 * lu - 1) });   // (its stick from B7's first drawing: it arrives at a cut, not mid-shot)
      grain(ts);
    }
    LOOPS.inkstand = t => {
      const ts = S0 + q12(t);
      stage(ts, scene7, { cam: CAM7(), doors: 1 });
    };
    LOOPS.inkstand.len = S1 - S0;
    window.PAPERINK_B7 = { KEYS, keyAt, standPose, seatPose, TSEAT, K1, LAND, START, BOOK, FRONT };   // (for --eval checks)
  }

  // =========================================================================================================================
  // C2, the lamp-lighting (song 9.0-12.7). Fable: "Silhouette. It's an action, and shadow does actions best: the match flare
  // in black, the chōchin blooming, the hood's outline, the eye-holes lit from below, the hands raising it out of frame. What
  // must survive is the lamp being lit, and it survives whole. What goes is my face at nine seconds, and losing it is a gain:
  // nobody should see the narrator's face before the story."
  // The camera close on the vellum (the butai's doors, shut until 12.8, are never in frame), on the teller's place (where the
  // doors will open on her, 12.8); the screen dark but for what the match and then the lantern light. She is the kuroko of
  // the prologue on her own screen: the seated puppet with her hood up (the hood's opening cut as a line of light), the
  // lantern in her lap. Nothing lit, nothing seen: every light here arrives with its source.
  //   8.43    black from the prologue's clack
  //   9.33    the match strikes on her first "Mukashi" (two drawings of flare), then a small flame: her fingers, the match and
  //           the lantern's cap in black, the hood's edge caught in its wider, fainter reach (a rim, not a fill)
  //   9.58    she brings it down to the lantern's mouth and holds it there through "...mukashi"
  //   11.44   "ARU TOKORO NI!": the chōchin blooms (three drawings); the vellum lights round her: the hood, its opening, the
  //           eye-hole lit from below; the match shaken out
  //   12.17   her far hand takes the lantern (the handle's sound), the near one back in her lap; 12.25 she raises it, up past
  //           her face and out of the top of the frame (five drawings): the light climbs her profile from below to above and
  //           leaves; cut to the butai (the telling)
  {
    const S0 = 9.0, S1 = 12.7, MATCH = 9 + 4 * f, LAMP = 11.44, RAISE = 12.25;     // (the strike on WORDS' first 'Mukashi,' 9.33; ink.js registers the lantern)
    PAPER_SFX.push(() => [[MATCH, 'match', -24]]);                                   // (moved here from ink.js with the strike)
    const TC = { x: 560, y: 960, s: .2, origin: [1150, 2760] };                   // the teller's place (verse.js T)
    const CAMC = () => camAt(640, 670, 2.0);
    const LS = 1.2, LB = [722, 858];                                              // the chōchin's scale; its base on her lap
    // her hood, up (the prologue's kneel, re-cut for the seated puppet's head; head-part master px): over the crown and down
    // the back to the shoulders, its opening from the brim down behind the eye and the jaw to the collar
    const HOOD = [[1690, 300], [1650, 220], [1560, 128], [1440, 58], [1300, 20], [1160, 30], [1030, 88], [940, 190], [890, 330], [870, 500],
      [858, 680], [838, 850], [808, 990], [850, 1040], [990, 1050], [1130, 1010], [1240, 970], [1320, 952],
      [1374, 900], [1392, 800], [1398, 700], [1402, 610], [1410, 525], [1440, 462], [1520, 420], [1600, 360]];
    const OPEN = HOOD.slice(17).concat([HOOD[0]]);                                // the opening's edge (collar -> brim)
    const hoodP = new Path2D(); HOOD.forEach(([x, y], i) => i ? hoodP.lineTo(x, y) : hoodP.moveTo(x, y)); hoodP.closePath();
    const openP = new Path2D(); OPEN.forEach(([x, y], i) => i ? openP.lineTo(x, y) : openP.moveTo(x, y));
    const hoodProp = { after: 'head', draw: (c, M) => {
      c.setTransform(M.head); c.globalCompositeOperation = 'source-over'; c.fillStyle = INK; c.fill(hoodP);
      c.globalCompositeOperation = 'destination-out'; c.lineWidth = 18; c.lineJoin = 'round'; c.lineCap = 'round'; c.strokeStyle = '#000'; c.stroke(openP);   // the opening: a line of light
      c.beginPath(); c.arc(1250, 822, 20, 0, 7); c.fill();                                                                               // the neck rivet, through the hood
      c.globalCompositeOperation = 'source-over';
    } };
    // the near fist (the match) and the far fist (steadying the lantern), as targets (canvas px), by drawing
    const BASE = () => 7 * LS + CHO.h * LS / 2;                                   // (the lantern's centre to its base)
    // the lantern's centre: on her lap until the raise; then up in front of her face and out of the top, five drawings
    const RISE = [[722, 720], [724, 620], [722, 515], [716, 415], [708, 326]];     // (up a hand's width in front of her face)
    const ARCH = [0, 0, -2, -4, -6];                                                 // she arches back a little as it goes over her (the arm clears her profile)
    const lc = q => q < RAISE ? [LB[0], LB[1] - BASE()] : RISE[Math.min(4, Math.floor((q - RAISE) * 12 + 1e-6))];
    const MOUTH = [LB[0] + 4, LB[1] - 7 * LS - CHO.h * LS - 6 * LS];                 // the lantern's mouth (its top cap)
    const M0 = [760, 690], M2 = [772, 706], matchTip = 26;                           // the match after the strike; withdrawn
    const AT = [MOUTH[0] + 4, MOUTH[1] - matchTip + 8];                              // (the fist that puts the match's head in the mouth)
    const OUT = LAMP + 3 * f, TAKE0 = RAISE - 2 * f, TAKE1 = RAISE - f;              // match withdrawn and shaken out; the near hand down, the far hand to the lantern
    const LOW = [700, 818];                                                          // the near hand, back in her lap
    function nearTarget(q) {
      const TO = MATCH + 3 * f;                                                      // (to the mouth: four drawings, eased)
      if (q < TO) return M0;
      if (q < TO + 4 * f + 1e-6) return mix2(M0, AT, ease((q - TO) / (4 * f)));
      if (q < OUT) return AT;
      if (q < TAKE0) return M2;
      return mix2(M2, LOW, ease((q - TAKE0) / (2 * f)));                             // the match put away, the hand stays low
    }
    // the far arm (drawn behind her, so her profile, the eye-hole and the hood's opening stay cut clean over it) steadies the
    // lantern in her lap, takes it from under its base and raises it out of the top of the frame
    function farTarget(q) { const [cx, cy] = lc(q); return q < TAKE1 ? [cx - 26, cy + 10] : [cx - 2, cy + BASE() + 10]; }
    const headKeys = PUPPET.snap([[0, { head: 10 }], [OUT + f, { head: 6 }], [RAISE + f, { head: -4 }], [RAISE + 3 * f, { head: -16 }]]);
    function poseC(q, target) {
      const p = { torso: q < RAISE ? 0 : ARCH[Math.min(4, Math.floor((q - RAISE) * 12 + 1e-6))], ...headKeys(q), _ghost: {} }; p.hair = 0;
      Object.assign(p, reachIn(FABLE, p, TC, 'torso', SEAT_ARM, target));
      return p;
    }
    const fistC = (q, target) => FABLE.world(poseC(q, target), TC).hand.translate(FAN_GRIP[0], FAN_GRIP[1]).transformPoint(new DOMPoint(0, 0));
    // the light: the match (a flare of two drawings, then a small flame) and the lantern (blooming over three drawings)
    const MA = -60 * Math.PI / 180;                                                  // the match points up and forward from the fist
    const flameAt = q => {
      if (q < MATCH - 1e-6 || q >= OUT + f) return null;
      const d = Math.floor((q - MATCH) * 12 + 1e-6), o = fistC(q, nearTarget(q));
      return { x: o.x + Math.cos(MA) * matchTip, y: o.y + Math.sin(MA) * matchTip, flare: d < 2 ? 1 - .3 * d : 0 };
    };
    const lampLit = q => q < LAMP - 1e-6 ? 0 : Math.min(1, (Math.floor((q - LAMP) * 12 + 1e-6) + 1) / 3);
    function vellumC2(ts, q) {
      const [x, y, w, h] = SCREEN.rect, fl = flameAt(q), lit = lampLit(q), [cx, cy] = lc(q);
      X.save(); X.beginPath(); X.rect(x, y, w, h); X.clip();
      X.fillStyle = '#070605'; X.fillRect(x, y, w, h);
      X.globalCompositeOperation = 'lighter';
      const pool = (px, py, r, a) => { const g = X.createRadialGradient(px, py, 0, px, py, r);
        g.addColorStop(0, `rgba(255,236,196,${a})`); g.addColorStop(.22, `rgba(247,206,142,${.78 * a})`); g.addColorStop(.55, `rgba(196,128,66,${.34 * a})`); g.addColorStop(1, 'rgba(0,0,0,0)');
        X.fillStyle = g; X.fillRect(px - r, py - r, 2 * r, 2 * r); };
      const flick = 1 + .05 * Math.sin(q * 23) + .03 * Math.sin(q * 41);
      if (fl) pool(fl.x, fl.y, fl.flare ? 250 + 110 * fl.flare : 190 * flick * (1 - .6 * lit), fl.flare ? .95 : .62 * (1 - .5 * lit));
      if (fl && !fl.flare && lit === 0) pool(fl.x, fl.y, 640 * flick, .2);         // its faint reach: enough for her hood's edge and her hands to read, black on it
      if (lit > 0) pool(cx, cy, 980 * (.45 + .55 * lit) * flick, .92 * lit);
      X.globalCompositeOperation = 'source-over';
      texture(.45);
      X.restore();
    }
    // the chōchin as black paper (unlit: it only stops light)
    function lanternShape(c, cx, cy, sc) {
      const w = CHO.w * sc, h = CHO.h * sc;
      c.setTransform(1, 0, 0, 1, 0, 0); c.globalCompositeOperation = 'source-over'; c.fillStyle = INK; c.strokeStyle = INK;
      c.beginPath(); c.ellipse(cx, cy, w / 2, h / 2, 0, 0, 7); c.fill();
      c.fillRect(cx - w * .33, cy - h / 2 - 5 * sc, w * .66, 9 * sc); c.fillRect(cx - w * .33, cy + h / 2 - 4 * sc, w * .66, 11 * sc);
      c.lineWidth = 2.4 * sc; c.beginPath(); c.arc(cx, cy - h / 2 - 5 * sc, w * .2, Math.PI, 0); c.stroke();
    }
    function sceneC2(ts) {
      const q = q12(ts), lit = lampLit(q), [cx, cy] = lc(q), fl = flameAt(q);
      X.fillStyle = '#050404'; X.fillRect(0, 0, W, H);
      if (q < MATCH - 1e-6) return;                                                  // in the dark, nothing: nothing is lit
      vellumC2(ts, q);
      const pN = poseC(q, nearTarget(q)), pF = poseC(q, farTarget(q));
      shadow(c => {
        c.globalCompositeOperation = 'source-over';
        // the far arm first (behind her), then her, hood up; the match in the near fist; the lantern, unlit, is paper
        FABLE.draw(c, pF, { ...TC, x: TC.x - 5, y: TC.y - 4 }, { hide: ['cushion', 'lower', 'torso', 'head', 'hair'] });   // (the far arm alone, behind her)
        FABLE.draw(c, pN, TC, { hide: ['hair'], props: [hoodProp], rods: FABLE_RODS });
        if (q < TAKE0) {
          const o = fistC(q, nearTarget(q));
          c.setTransform(1, 0, 0, 1, 0, 0); c.strokeStyle = INK; c.lineWidth = 2.6; c.lineCap = 'round';
          c.beginPath(); c.moveTo(o.x - Math.cos(MA) * 6, o.y - Math.sin(MA) * 6); c.lineTo(o.x + Math.cos(MA) * matchTip, o.y + Math.sin(MA) * matchTip); c.stroke();
        }
        if (lit < 1) lanternShape(c, cx, cy, LS);
      }, 0, { lamp: [cx, cy] });
      // the chōchin blooming (over the screen: it is the light), and the match's flame
      X.save(); X.beginPath(); X.rect(...SCREEN.rect); X.clip();
      if (lit > 0) { X.globalAlpha = lit; chochinBody(cx, cy, LS, 0, { gold: true, lit, halo: false }); X.globalAlpha = 1; }
      if (fl) {
        X.globalCompositeOperation = 'lighter'; const r = fl.flare ? 7 + 4 * fl.flare : 5;
        const g = X.createRadialGradient(fl.x, fl.y - r * .5, 0, fl.x, fl.y - r * .5, r * 2.4); g.addColorStop(0, 'rgba(255,250,232,1)'); g.addColorStop(.35, 'rgba(255,212,140,.85)'); g.addColorStop(1, 'rgba(255,150,60,0)');
        X.fillStyle = g; X.fillRect(fl.x - r * 3, fl.y - r * 3.5, r * 6, r * 6);
        X.globalCompositeOperation = 'source-over';
      }
      X.restore();
      grain(ts);
    }
    LOOPS.inklamp = t => {
      const ts = S0 + q12(t);
      stage(ts, sceneC2, { cam: CAMC(), doors: 1 });
    };
    LOOPS.inklamp.len = S1 - S0;
  }
}
