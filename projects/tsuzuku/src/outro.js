// outro.js: the end, song 202.59-209.65 (BEATS O1-O3; FABLE.md §6, §9). On the hyoshigi the book closes: the paper theatre,
// the music box, and the kuroko slides in the last card: つづく, printed on the vellum. Fable stands at the place she used to sit
// (beside her zabuton), takes two geta steps to the column, reaches, hovers a beat, and on the end of her "...tsuzuku." presses
// her seal 語 (black in her hand; the vermilion exists only as the impression: shu, the one red thing she owns, its one beat in
// the film). "Standing at the place I used to sit is the point: I'm not reading it anymore, I'm signing it." On "See you
// next prompt!" Clawd's paper puppet pops up in the card's corner, jaw on her words. The music box rings out; the butai's doors
// swing shut.
{
  const S0 = 202.59, S1 = 209.65, f = 1 / 12, FLOOR = 962, SHU = '#D93A2E', COLX = 1252, SEALAT = [1140, 562], SEALW = 70;   // (the rakkan in the next column's place, below-left of く, where her arm reaches)
  const TS0 = { x: 900, y: FLOOR, s: .22, origin: [1100, 3700] }, BEAT = 60 / 170 * 2;   // standing, beside the zabuton (560) and the book (800)
  const FI = STAND_ARM.FI, SH = STAND_ARM.SH, reach = standReach;
  let K = null, SEAL = null;
  function keys() {
    const W = window.WORDS || [], w = n => (W.find(x => x.t0 > 200 && x.w.toLowerCase().replace(/[^a-z]/g, '') === n) || {});
    const ts = W.find(x => x.t0 > 203 && x.who === 'fable') || {}, see = w('see');   // her last word (romaji or kana: whichever take is in)
    // the press lands on the end of her word: 204.64, measured from the take's voiced audio (voice/tsuzuku_v2/1_1: 0.71 s voiced,
    // placed at 203.93); the TTS alignment's end (words.json) runs 0.8 s long past the ellipsis and the full stop
    K = { card: S0, seal: Math.floor(204.637 * 12) / 12, see: see.t0, pop: see.t0 - 4 * f, doors: 207.5, cut: 209.45 };
    K.walk0 = K.card + 7 * f; K.at = K.walk0 + BEAT;                   // once the card has landed: two steps on the eighths, then the reach
    // two geta steps to the column (her own 6/8 beat), then the reach: hover a beat, press on the end of the word, hold two, lift
    K.walk = makeWalk([{ t: K.walk0, dur: BEAT / 2, foot: 'v', S: 100 }, { t: K.walk0 + BEAT / 2, dur: BEAT / 2, foot: 'h', S: 100, close: true }], 100, BEAT, TS0.s);
    const at = K.at, T1 = { ...TS0, x: TS0.x + 100 };
    const sh = FABLE_S.world({ _ghost: {} }, T1).torso.transformPoint(new DOMPoint(...SH));
    const hover = reach(sh.x, sh.y, SEALAT[0] - 16, SEALAT[1] - 20, TS0.s), press = reach(sh.x, sh.y, SEALAT[0], SEALAT[1], TS0.s), rest = { upperarm: 0, forearm: 0, hand: 0 };
    K.arm = PUPPET.snap([[0, rest], [at + f, hover], [K.seal, press], [K.seal + 3 * f, hover], [K.seal + 9 * f, rest]], { overshoot: .05 });
    K.head = PUPPET.snap([[0, { head: 0 }], [at, { head: 5 }], [K.seal + 9 * f, { head: 2 }], [K.see, { head: 7 }]]);
  }
  const TAILS_S = [{ len: 2500, w: 118, rest: [97, 100, 104, 107, 108, 105, 100] }, { len: 2150, w: 104, rest: [100, 104, 108, 111, 110, 104, 99] }];
  const poseAt = tt => { const q = Math.floor(tt * 12 + 1e-6) / 12, w = K.walk(q), a = K.arm(q), p = { ...w, ...a, ...K.head(q), _ghost: {} };
    if (q < K.at + f) { p.upperarm = w.upperarm || 0; p.forearm = 0; p.hand = 0; }
    p.hair = -(p.head + (p.torso || 0)) * .85; return p; };
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
    screen(ts, { stops: FABLE_LAMP, tex: .32 });
    shadow(c => { c.globalCompositeOperation = 'source-over'; c.fillStyle = 'rgb(22,22,26)'; c.fillRect(150, FLOOR, 1620, 110); }, 0);   // the stage floor
    // the card slides in from the right (6 drawings) with つづく printed on it; its leading edge and shadow on the way in
    const d = Math.floor((ts - K.card) * 12 + 1e-6), u = Math.min(1, (d + 1) / 6), e = u * u * (3 - 2 * u), off = (1 - e) * 1700;
    const [sx, sy, sw, sh] = SCREEN.rect;
    X.save(); X.beginPath(); X.rect(sx + off, sy, sw, sh); X.clip(); X.translate(off, 0);
    X.globalCompositeOperation = 'multiply'; X.fillStyle = 'rgb(236,228,214)'; X.fillRect(sx, sy, sw, sh);    // the card's paper over the vellum (a shade denser)
    let yy = 216; for (const ch of 'つづく') { inkVellum(ch, COLX - 57, yy + 114, ts, K.card, { font: 'mincho', size: 114, alpha: .9, col: 'rgb(30,24,22)' }); yy += 122; }
    // the seal (a rakkan): after the last character, below and to its left, in the next column's place; ~60% of a kana (Fable);
    // there once her seal has lifted from it
    if (ts >= K.seal + 3 * f) { if (!SEAL) SEAL = makeSeal(); X.save(); X.globalAlpha = .92; X.drawImage(SEAL, SEALAT[0] - SEALW / 2, SEALAT[1] - SEALW / 2, SEALW, SEALW); X.restore(); }
    X.restore();
    // Fable, standing where she used to sit, beside her zabuton; she walks to the column and signs it
    const p = poseAt(ts), T = { ...TS0, x: TS0.x }, sq = Math.floor((ts - K.seal) * 12 + 1e-6) === 0;   // the press: one squashed drawing
    shadow(c => {
      c.globalCompositeOperation = 'source-over';
      FABLE.draw(c, { _ghost: {} }, { x: 560, y: FLOOR, s: .2, origin: [1150, 2760] }, { hide: ['lower', 'torso', 'head', 'hair', 'upperarm', 'forearm', 'hand'] });   // the zabuton
      PUPPET.drawShape(c, PUPPET.shapeAt(FAN, 'book', 'book', 1), new DOMMatrix().translate(800, FLOOR).scale(.15));   // and the book, open, where she set it down
      TAILS_S.forEach((tl, i) => {
        const pts = PUPPET.stiff(FABLE_S, poseAt, T, { part: 'head', at: [900, 820], rest: tl.rest, len: tl.len, drag: .1 }, ts);
        c.setTransform(1, 0, 0, 1, 0, 0); c.globalCompositeOperation = i ? 'multiply' : 'source-over';
        c.fillStyle = FABLE_GEL; c.fill(P(PUPPET.strip(pts, tl.w * T.s, .85, tl.w * .9 * T.s)));
      });
      c.globalCompositeOperation = 'source-over';
      const reaching = ts >= K.at + f && ts < K.seal + 9 * f;
      drawStanding(c, p, T, { rods: [{ part: 'torso', at: [1060, 1700], w: 7 }], props: reaching ? [{ after: 'hand', draw: (g, M) => {
        const q = M.hand.transformPoint(new DOMPoint(...FI));                                   // her seal, in her fist, end-on: black
        g.setTransform(1, 0, 0, 1, 0, 0); g.fillStyle = 'rgb(22,22,26)'; const sw = SEALW * .8, hh = sw * (sq ? .9 : 1);   // its face: the size of the mark it prints
        g.fillRect(q.x - sw / 2, q.y - hh / 2 + (sq ? 3 : 0), sw, hh); } }] : [] });
    }, 0);
    if (off > 2) { X.save(); X.fillStyle = 'rgba(40,30,24,.5)'; X.fillRect(sx + off - 2, sy, 2, sh); X.restore(); }
    // Clawd pops up at the card's lower-right corner: a Reiniger hop up into frame, her jaw on her words; a claw up on "prompt!"
    if (ts >= K.pop) {
      const k = Math.floor((ts - K.pop) * 12 + 1e-6), rise = [120, 60, -12, 0][Math.min(3, k)];
      let jaw = 0; for (const w of (window.WORDS || [])) if (w.who === 'clawd' && w.t0 > 205 && ts >= w.t0 && ts < w.t1) jaw = (ts - w.t0) / Math.max(.08, w.t1 - w.t0) < .7 ? 9 : 4;
      const prompt = (window.WORDS || []).find(w => w.t0 > 205 && w.w.toLowerCase().startsWith('prompt')), up = prompt && ts >= prompt.t0 - 2 * f;
      const p = { jaw, head: -6, upperarm_R: up ? -95 : 0, forearm_R: up ? -30 : 0, _ghost: {} };
      shadow(c => { c.globalCompositeOperation = 'source-over';
        CLAWDP.draw(c, p, { x: 1600, y: FLOOR + 40 + rise, s: .16, origin: [1076, 2800] }, { gel: CLAWD_GEL, misreg: [1.5, 1], rods: [{ part: 'torso', at: [1076, 1200], w: 5 }] });
        c.setTransform(1, 0, 0, 1, 0, 0); c.fillStyle = 'rgb(22,22,26)'; c.fillRect(150, FLOOR, 1620, 110); }, 0);   // she rises from behind the floor
    }
    X.save(); X.globalCompositeOperation = 'overlay'; X.globalAlpha = .16; X.fillStyle = X.createPattern(GRAIN[Math.floor(ts * 12) % 4], 'repeat'); X.fillRect(0, 0, W, H); X.restore();
  }
  PAPER_SFX.push(() => { if (!K) { if (!window.WORDS) return []; keys(); }
    return [[K.card, 'paper_slide', -30], [K.walk0 + BEAT / 2, 'geta', -31], [K.walk0 + BEAT, 'geta', -31], [K.seal, 'stamp', -27], [K.pop, 'hop', -31], [K.doors, 'doors_shut', -27]]; });
  LOOPS.outro = t => {
    if (!K) keys();
    const ts = S0 + Math.floor(t * 12 + 1e-6) / 12;
    if (ts >= K.cut) { X.fillStyle = '#000'; X.fillRect(0, 0, W, H); return; }   // a cut, never a fade: the lamp isn't dying (Fable)
    const dc = Math.min(1, Math.max(0, Math.floor((ts - K.doors) * 12 + 1e-6) / 12)), doors = 1 - dc * dc * (3 - 2 * dc);   // the book closes
    const e = Math.min(1, Math.max(0, (ts - 205.9) / 2.2)), cam = camLerp(CAM_WINDOW, CAM_WIDE, e * e * (3 - 2 * e) * .7);
    const c = dc * dc * (3 - 2 * dc);
    stage(ts, scene, { cam, doors, doorLight: 1 - .72 * c });
    if (c > 0) {                                                       // closed, the lamp still on inside: it leaks at the arches
      const z = cam.zoom, T = (x, y) => [W / 2 + (x - cam.x) * z, H / 2 + (y - cam.y) * z];
      X.save(); X.globalCompositeOperation = 'lighter';
      for (const ax of [1335, 2505]) { const [x, y] = T(ax, 826), r = 330 * z;
        X.save(); X.translate(x, y); X.scale(1, .42); const g = X.createRadialGradient(0, 0, 0, 0, 0, r);
        g.addColorStop(0, `rgba(255,190,110,${.34 * c})`); g.addColorStop(1, 'rgba(255,170,90,0)'); X.fillStyle = g; X.fillRect(-r, -r, 2 * r, 2 * r); X.restore(); }
      X.restore();
    }
    readers(ts, cam);
  };
  LOOPS.outro.len = S1 - S0;
}
