// outro.js: the end, song 202.59-209.65 (BEATS O1-O3; FABLE.md §6, §9). On the hyoshigi the book closes: the paper theatre,
// the music box, and the kuroko slides in the last card: つづく, printed large on the vellum. On the end of Fable's "...tsuzuku."
// her seal 語 is pressed onto it in vermilion (shu, the one red thing she owns; the one beat of it in the film). On "See you
// next prompt!" Clawd's paper puppet pops up in the card's corner, jaw on her words. The music box rings out; the butai's doors
// swing shut.
{
  const S0 = 202.59, S1 = 209.65, f = 1 / 12, FLOOR = 962, SHU = '#D93A2E';
  let K = null, SEAL = null;
  function keys() {
    const W = window.WORDS || [], w = n => (W.find(x => x.t0 > 200 && x.w.toLowerCase().replace(/[^a-z]/g, '') === n) || {});
    const ts = w('tsuzuku'), see = w('see');
    K = { card: S0, seal: ts.t1 - .55, pop: see.t0 - 4 * f, doors: 208.15 };
  }
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
    let yy = 250; for (const ch of 'つづく') { inkVellum(ch, 1010 - 95, yy + 190, ts, K.card, { font: 'mincho', size: 190, alpha: .9, col: 'rgb(30,24,22)' }); yy += 210; }
    if (ts >= K.seal) {                                                // the seal: pressed (one drawing squashed), lifted, the impression left
      if (!SEAL) SEAL = makeSeal();
      const k = Math.floor((ts - K.seal) * 12 + 1e-6), sq = k === 0 ? 1.06 : 1, a = k === 0 ? .7 : .92;
      X.save(); X.translate(1160, 800); X.scale(sq, sq); X.globalAlpha = a; X.drawImage(SEAL, -60, -60, 120, 120); X.restore();
    }
    X.restore();
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
  LOOPS.outro = t => {
    if (!K) keys();
    const ts = S0 + Math.floor(t * 12 + 1e-6) / 12;
    const dc = Math.min(1, Math.max(0, Math.floor((ts - K.doors) * 12 + 1e-6) / 12)), doors = 1 - dc * dc * (3 - 2 * dc);   // the book closes
    const e = Math.min(1, Math.max(0, (ts - 205.9) / 2.2)), cam = camLerp(CAM_WINDOW, CAM_WIDE, e * e * (3 - 2 * e) * .7);
    stage(ts, scene, { cam, doors, lit: ts > 209.3 ? Math.max(0, 1 - (ts - 209.3) / .3) : 1 });
    audience(ts, { y: H + 330 - 147 * e, lift: 120, scale: .52 * (1 - .25 * e) });
    if (ts > 209.3) { X.fillStyle = `rgba(0,0,0,${Math.min(1, (ts - 209.3) / .3)})`; X.fillRect(0, 0, W, H); }
  };
  LOOPS.outro.len = S1 - S0;
}
