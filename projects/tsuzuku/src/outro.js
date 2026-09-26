// outro.js: the end, song 202.59-209.65 (BEATS O1-O3; FABLE.md §6, §9; Fable's ruling for the room ending, Michael's call).
// The doors were shut by the room at the end of the final chorus; on the hyoshigi they open onto a dark window with a warm glow
// at its right edge: her light arrives before she does. She enters from the right as the paper silhouette, hood down, her
// lantern low in her trailing hand (the only light in the theatre, never put down since B9), drawing her seal 語 from her
// collar as she walks (black in her hand; the vermilion exists only as the impression: shu, its one beat in the film). The card
// with つづく slides in as she arrives; she stops to the column's right, reaches across, and on the end of her "...tsuzuku."
// presses it. On "See you next prompt!" Clawd's paper puppet pops up beside the open book at the lower left, jaw on her words.
// The music box rings out; the butai's doors swing shut on her light.
{
  const S0 = 202.59, S1 = 209.65, f = 1 / 12, FLOOR = 962, SHU = '#D93A2E', COLX = 1290, SEALAT = [1293, 556], SEALW = 62, CLAWDX = 960;   // (the rakkan beneath く: from the column's right her arm reaches it without crossing the word)
  const STOP = 1470, STRIDE = 240, LEAN = 6, TS0 = { x: STOP, y: FLOOR, s: .22, origin: [1100, 3700], flip: -1 }, BEAT = 60 / 170 * 2;   // facing left, to the column's right
  const OPEN1 = 203.0, PUSH1 = 203.42, STEPS = [203.0, 203.35, 203.7], CARD = 203.5, LSC = 1.4;
  const FI = STAND_ARM.FI, SH = STAND_ARM.SH;
  const COLLAR = [1075, 800], CARRY_FI = [1650, 1900], CORD = 2.6;   // (torso master px: the cord's exit; the fist carried low in front)
  let K = null, SEAL = null, CORD_LEN = 0;
  function keys() {
    const W = window.WORDS || [], w = n => (W.find(x => x.t0 > 200 && x.w.toLowerCase().replace(/[^a-z]/g, '') === n) || {});
    const see = w('see');
    // the press lands on the end of her word: 204.64, measured from the take's voiced audio (voice/tsuzuku_v2/1_1: 0.71 s voiced,
    // placed at 203.93); the TTS alignment's end (words.json) runs 0.8 s long past the ellipsis and the full stop
    K = { card: CARD, seal: Math.floor(204.637 * 12) / 12, see: see.t0, pop: see.t0 - 4 * f, doors: 207.5, cut: 209.45, at: 204.25 };
    // three geta steps in from the right edge, landing on 203.0, 203.35 and 203.7 (the last closes the feet): she walks left
    // (the body travels half a stride on the first step, a whole one on the second, half on the close: two strides in all; the
    // first lands as she comes into the window, so we see a stride and a half. dx is in her own, mirrored frame: + = forward)
    const D = .33;
    K.walk = makeWalk(STEPS.map((tl, i) => ({ t: tl - D, dur: D, foot: i % 2 ? 'h' : 'v', close: i === 2 })), STRIDE, D, TS0.s);
    K.walk0 = STEPS[0] - D; K.x0 = -2 * STRIDE;
    const T1 = { ...TS0, x: STOP }, TM = FABLE_S.world({ _ghost: {}, torso: LEAN }, T1).torso, co = TM.transformPoint(new DOMPoint(...COLLAR));
    CORD_LEN = Math.hypot(SEALAT[0] - co.x, SEALAT[1] - co.y) / TS0.s * 1.01;   // (just long enough to reach the column)
    const at = { _ghost: {}, torso: LEAN }, hover = reachIn(FABLE_S, at, T1, 'torso', STAND_ARM, [SEALAT[0] + 14, SEALAT[1] - 20]),
      press = reachIn(FABLE_S, at, T1, 'torso', STAND_ARM, SEALAT), rest = { upperarm: 0, forearm: 0, hand: 0 };
    // she draws it out as she walks: a hand to her collar (203.1), and out on its cord by 203.5, carried low; at the column the
    // reach, a hover, the press on the end of the word, hold two, lift, and back to the collar
    const collar = { upperarm: -20, forearm: -155, hand: -20 }, carry = standReach(SH[0], SH[1], ...CARRY_FI, 1);
    K.draw = 203.1 - f; K.out = 203.5 - f; K.tuck = K.seal + 8 * f;
    const draw = PUPPET.snap([[0, rest], [K.draw, collar]], { inbetween: .7, overshoot: .05 });   // (her forearm is long: the in-between near her chin)
    const arm = PUPPET.snap([[0, collar], [K.out, carry], [K.at, hover], [K.seal, press], [K.seal + 3 * f, hover], [K.tuck, collar], [K.tuck + 3 * f, rest]], { overshoot: .05 });
    K.arm = q => q < K.out - 1e-6 ? draw(q) : arm(q);
    K.lean = PUPPET.snap([[0, { torso: 0 }], [K.at - f, { torso: LEAN }], [K.tuck, { torso: 0 }]]);   // (she leans into the reach)
    K.head = PUPPET.snap([[0, { head: 0 }], [K.at, { head: 5 }], [K.seal + 9 * f, { head: 2 }], [K.see, { head: 7 }]]);
  }
  // her far arm carries the lantern, low at her hip and a little behind her (drawn behind the body: only the fist, the stick and
  // the light clear her silhouette); it swings a few degrees with the steps and settles when she stops
  const FAR = standReach(STAND_ARM.SH[0], STAND_ARM.SH[1], 830, 1880, 1), LHANG = { len: .5, stickAngle: 48 };
  const TAILS_S = [{ len: 2500, w: 118, rest: [97, 100, 104, 107, 108, 105, 100] }, { len: 2150, w: 104, rest: [100, 104, 108, 111, 110, 104, 99] }];
  const poseAt = tt => { const q = Math.floor(tt * 12 + 1e-6) / 12, w = K.walk(q), a = K.arm(q), p = { ...w, ...a, ...K.head(q), _ghost: {} };
    p.dx = (p.dx || 0) + K.x0; p.torso = (w.torso || 0) + K.lean(q).torso; p.hair = -(p.head + (p.torso || 0)) * .85; return p; };
  const farPose = p => ({ ...p, ...FAR });
  const lanternAt = tt => {
    const q = Math.floor(tt * 12 + 1e-6) / 12, fi = fistAt(FABLE_S, farPose(poseAt(q)), TS0, STAND_ARM), stop = STEPS[2];
    const swing = q < stop ? 4 * Math.sin(2 * Math.PI * (q - K.walk0) / .7) : [-3, 2, -1][Math.floor((q - stop) * 12 / 2 + 1e-6)] || 0;   // (+ = its foot to the right)
    const h = CHO.h * LSC, L = CHO.stick * h * LHANG.len, a = LHANG.stickAngle * Math.PI / 180, tip = [fi[0] + Math.cos(a) * L, fi[1] + Math.sin(a) * L];
    const drop = CHO.w * .2 * LSC + 5 * LSC + h / 2, sw = swing * Math.PI / 180;
    return { fi, swing, c: [tip[0] - Math.sin(sw) * drop, tip[1] + Math.cos(sw) * drop] };
  };
  const mix = (a, b, u) => { const h = s => [1, 3, 5].map(i => parseInt(s.slice(i, i + 2), 16)), A = h(a), B = h(b); return `rgb(${A.map((v, i) => Math.round(v + (B[i] - v) * u))})`; };
  // the window before she arrives: dark vellum, her light already at its right edge and growing (the glow is the lantern's own
  // falloff, from where it is off the window's edge; the outer stops warm up from near-black to the bridge's as she comes in)
  const arrival = ts => Math.min(1, Math.max(0, (ts - S0) / (CARD - S0)));
  // the seal: a square of shu with 語 cut in reverse (hakubun: the character in paper, the ground in ink), edges worn by use
  function makeSeal() {
    const n = 220, c = mkCanvas(n, n), g = c.getContext('2d'); let s = 91;
    const rnd = () => (s = (s * 16807) % 2147483647) / 2147483647;
    g.fillStyle = SHU; g.beginPath(); g.moveTo(8 + rnd() * 5, 8 + rnd() * 5);
    for (const [x, y] of [[n - 8, 8], [n - 8, n - 8], [8, n - 8]]) g.lineTo(x + (rnd() - .5) * 8, y + (rnd() - .5) * 8); g.closePath(); g.fill();
    const L = shape('語', { font: 'minchoB', size: 170 }); g.globalCompositeOperation = 'destination-out';
    for (const gl of L.glyphs) g.fill(glyphPath(gl, (n - L.width) / 2 + gl.x, n * .78 + gl.y));
    for (let i = 0; i < 260; i++) { g.globalAlpha = .5 + rnd() * .5; g.beginPath(); g.arc(rnd() * n, rnd() * n, .6 + rnd() * 2.4, 0, 7); g.fill(); }   // where the paste didn't take
    return c;
  }
  function scene(ts) {
    X.fillStyle = '#0d0b0a'; X.fillRect(0, 0, W, H);
    const u = arrival(ts), ln = lanternAt(ts);
    screen(ts, { stops: [[0, '#FFF1D6'], [.22, '#F2CB8E'], [.55, mix('#3A2616', '#B98A52', u)], [1, mix('#0D0A08', '#5A3C22', u)]], tex: .32, power: .35 + .85 * u, lamp: ln.c });
    shadow(c => { c.globalCompositeOperation = 'source-over'; c.fillStyle = 'rgb(22,22,26)'; c.fillRect(150, FLOOR, 1620, 110); }, 0);   // the stage floor
    // the card slides in from the right (6 drawings) with つづく printed on it; its leading edge and shadow on the way in
    const d = Math.floor((ts - K.card) * 12 + 1e-6), v = Math.min(1, Math.max(0, (d + 1) / 6)), e = v * v * (3 - 2 * v), off = (1 - e) * 1700;
    const [sx, sy, sw, sh] = SCREEN.rect;
    if (off < sw) {
      X.save(); X.beginPath(); X.rect(sx + off, sy, sw, sh); X.clip(); X.translate(off, 0);
      X.globalCompositeOperation = 'multiply'; X.fillStyle = 'rgb(236,228,214)'; X.fillRect(sx, sy, sw, sh);    // the card's paper over the vellum (a shade denser)
      let yy = 200; for (const ch of 'つづく') { inkVellum(ch, COLX - 50, yy + 100, ts, K.card, { font: 'mincho', size: 100, alpha: .9, col: 'rgb(30,24,22)' }); yy += 108; }
      // the seal (a rakkan), ~60% of a kana (Fable); there once her seal has lifted from it
      if (ts >= K.seal + 3 * f) { if (!SEAL) SEAL = makeSeal(); X.save(); X.globalAlpha = .92; X.drawImage(SEAL, SEALAT[0] - SEALW / 2, SEALAT[1] - SEALW / 2, SEALW, SEALW); X.restore(); }
      X.restore();
    }
    // her place: the zabuton she left and the book, open, where she set it down (B8)
    shadow(c => { c.globalCompositeOperation = 'source-over';
      FABLE.draw(c, { _ghost: {} }, { x: 560, y: FLOOR, s: .2, origin: [1150, 2760] }, { hide: ['lower', 'torso', 'head', 'hair', 'upperarm', 'forearm', 'hand'] });
      PUPPET.drawShape(c, PUPPET.shapeAt(FAN, 'book', 'book', 1), new DOMMatrix().translate(800, FLOOR).scale(.15)); }, 0);
    // the lantern, hanging from her far fist on a short stick: behind her (drawn before her shadow, so her silhouette covers it)
    X.save(); X.beginPath(); X.rect(...SCREEN.rect); X.clip();
    chochinHang(ln.fi[0], ln.fi[1], 1, LSC, { gold: true, swing: ln.swing, ...LHANG }); X.restore();
    // Fable: in from the right, the lantern in her far hand, the seal drawn with her near one; she signs the column
    const p = poseAt(ts), T = TS0, sq = Math.floor((ts - K.seal) * 12 + 1e-6) === 0;   // the press: one squashed drawing
    shadow(c => {
      TAILS_S.forEach((tl, i) => {                                   // solved facing right and mirrored (a flipped card flips its ribbon)
        const pts = PUPPET.stiff(FABLE_S, poseAt, { ...T, flip: 1 }, { part: 'head', at: [900, 820], rest: tl.rest, len: tl.len, drag: .1 }, ts).map(([x, y]) => [2 * T.x - x, y]);
        c.setTransform(1, 0, 0, 1, 0, 0); c.globalCompositeOperation = i ? 'multiply' : 'source-over';
        c.fillStyle = FABLE_GEL; c.fill(P(PUPPET.strip(pts, tl.w * T.s, .85, tl.w * .9 * T.s)));
      });
      c.globalCompositeOperation = 'source-over';
      FABLE_S.draw(c, farPose(p), T, { hide: FABLE_S.parts.map(q => q.name).filter(n => !['upperarm', 'forearm', 'hand'].includes(n)) });   // the far arm, behind
      const out = ts >= K.out && ts < K.tuck + f;                                                  // the seal out of her jacket
      drawStanding(c, p, T, { rods: [{ part: 'torso', at: [1060, 1700], w: 7 }], props: out ? [{ after: 'hand', draw: (g, M) => {
        const q = M.hand.transformPoint(new DOMPoint(...FI)), o = M.torso.transformPoint(new DOMPoint(...COLLAR));
        g.setTransform(1, 0, 0, 1, 0, 0); g.fillStyle = g.strokeStyle = 'rgb(22,22,26)';
        // its cord, from the collar to her fist: a paper thread, slack when she carries it, taut at the column (a parabola of
        // fixed length: the sag from the span)
        const d = Math.hypot(q.x - o.x, q.y - o.y), L = CORD_LEN * T.s, h = d < L ? Math.sqrt(3 * d * (L - d) / 8) : 0;
        g.lineWidth = CORD; g.lineCap = 'round'; g.beginPath(); g.moveTo(o.x, o.y); g.quadraticCurveTo((o.x + q.x) / 2, (o.y + q.y) / 2 + 2 * h, q.x, q.y); g.stroke();
        const sw = SEALW * .8, hh = sw * (sq ? .9 : 1);                                         // her seal, in her fist, end-on: black;
        g.fillRect(q.x - sw / 2, q.y - hh / 2 + (sq ? 3 : 0), sw, hh); } }] : [] });           // its face the size of the mark it prints
    }, 0);
    if (off > 2 && off < sw) { X.save(); X.fillStyle = 'rgba(40,30,24,.5)'; X.fillRect(sx + off - 2, sy, 2, sh); X.restore(); }
    // Clawd pops up beside the open book at the lower left (Fable holds the right): a Reiniger hop up into frame, her jaw on her
    // words; a claw up on "prompt!"
    if (ts >= K.pop) {
      const k = Math.floor((ts - K.pop) * 12 + 1e-6), rise = [120, 60, -12, 0][Math.min(3, k)];
      let jaw = 0; for (const w of (window.WORDS || [])) if (w.who === 'clawd' && w.t0 > 205 && ts >= w.t0 && ts < w.t1) jaw = (ts - w.t0) / Math.max(.08, w.t1 - w.t0) < .7 ? 9 : 4;
      const prompt = (window.WORDS || []).find(w => w.t0 > 205 && w.w.toLowerCase().startsWith('prompt')), up = prompt && ts >= prompt.t0 - 2 * f;
      const p = { jaw, head: -6, upperarm_R: up ? -95 : 0, forearm_R: up ? -30 : 0, _ghost: {} };
      shadow(c => { c.globalCompositeOperation = 'source-over'; c.save(); c.beginPath(); c.rect(0, 0, W, FLOOR); c.clip();   // she rises from behind the floor
        CLAWDP.draw(c, p, { x: CLAWDX, y: FLOOR + 40 + rise, s: .16, origin: [1076, 2800] }, { gel: CLAWD_GEL, misreg: [1.5, 1], rods: [{ part: 'torso', at: [1076, 1200], w: 5 }] }); c.restore(); }, 0);
    }
    X.save(); X.globalCompositeOperation = 'overlay'; X.globalAlpha = .16; X.fillStyle = X.createPattern(GRAIN[Math.floor(ts * 12) % 4], 'repeat'); X.fillRect(0, 0, W, H); X.restore();
  }
  PAPER_SFX.push(() => { if (!K) { if (!window.WORDS) return []; keys(); }
    return [[S0, 'doors_open', -30], ...STEPS.map(t => [t, 'geta', -31]), [K.draw + f, 'cloth', -36], [K.card, 'paper_slide', -30], [K.seal, 'stamp', -27],
      [K.pop, 'hop', -31], [K.doors, 'doors_shut', -27]]; });
  LOOPS.outro = t => {
    if (!K) keys();
    const ts = S0 + Math.floor(t * 12 + 1e-6) / 12;
    if (ts >= K.cut) { X.fillStyle = '#000'; X.fillRect(0, 0, W, H); return; }   // a cut, never a fade: the lamp isn't dying (Fable)
    const dc = Math.min(1, Math.max(0, Math.floor((ts - K.doors) * 12 + 1e-6) / 12)), doors = 1 - dc * dc * (3 - 2 * dc);   // the book closes
    // the camera: on the finale's last framing (the whole butai, doors shut), it walks in to the window as the doors open; at the
    // end it draws back as the music box rings out
    const i0 = Math.min(1, Math.max(0, (ts - S0) / (PUSH1 - S0))), e = Math.min(1, Math.max(0, (ts - 205.9) / 2.2));
    const cam = ts < 205.9 ? camLerp(CAM_WIDE, CAM_WINDOW, i0 * i0 * (3 - 2 * i0)) : camLerp(CAM_WINDOW, CAM_WIDE, e * e * (3 - 2 * e) * .7);
    const c = dc * dc * (3 - 2 * dc);
    const o0 = Math.min(1, Math.max(0, (ts - S0) / (OPEN1 - S0))), opened = o0 * o0 * (3 - 2 * o0);   // the doors open on the clack (they were shut by the room)
    // the light: on the clack the wood still has the finale's pink (Clawd's world, lit behind the shut doors); it goes out over four
    // drawings as the doors part, onto the dark window and her light coming
    const g0 = Math.min(1, Math.max(0, (ts - S0) / (4 * f))), out = 1 - g0 * g0 * (3 - 2 * g0), spill = [255, 150 + 72 * (1 - out), 176 + 39 * out].map(Math.round);
    stage(ts, scene, { cam, doors: Math.min(doors, opened), doorLight: 1 - .72 * c, lit: Math.max(out, .3 + .7 * arrival(ts)), spill });
    if (c > 0) {                                                       // closed, the lamp still on inside: it leaks at the arches
      const z = cam.zoom, T = (x, y) => [W / 2 + (x - cam.x) * z, H / 2 + (y - cam.y) * z];
      X.save(); X.globalCompositeOperation = 'lighter';
      for (const [ax, k] of [[1335, .27], [2505, .4]]) { const [x, y] = T(ax, 826), r = 330 * z;   // (brighter on the right: her lantern's side)
        X.save(); X.translate(x, y); X.scale(1, .42); const g = X.createRadialGradient(0, 0, 0, 0, 0, r);
        g.addColorStop(0, `rgba(255,190,110,${k * c})`); g.addColorStop(1, 'rgba(255,170,90,0)'); X.fillStyle = g; X.fillRect(-r, -r, 2 * r, 2 * r); X.restore(); }
      X.restore();
      [1335, 2505].forEach((ax, i) => { const [x, y] = T(ax, 826), r = 330 * z;              // dust settling in the leak
        dust(ts, (px, py) => c * lightPool(x, y, r, .6)(px, py), { seed: 9 + i, n: 26, rect: [x - r, y - r * .6, 2 * r, 1.2 * r], col: [255, 200, 130], alpha: 1.4 }); });
    }
    // (no readers: Michael's rule, the audience lives inside the box. And no cushion in the room: she walked off with her light
    // at the end of the finale, and the room is empty and dark)
  };
  LOOPS.outro.len = S1 - S0;
}
