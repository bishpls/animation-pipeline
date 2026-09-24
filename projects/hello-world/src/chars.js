// chars.js: the two chibi-register characters, drawn in code (PSG style: thick ink line, flat colour, one hard shade).
//
// clawd(x, y, s, o)  — the block mascot. (x, y) = ground point between the feet. s = scale (1: body 200 px wide).
//   o: { sq (squash +/-), lean, hop (px up), eyes: 'open'|'happy'|'closed'|'wide'|'x', look [dx,dy], armL, armR (angle, 0 = out, + = up),
//        walk (phase), bow (0..1 ojigi), glow (0..1), blush }
// idol(x, y, s, o)   — SD idol Clawd (2.5 heads). (x, y) = ground point. s = 1: ~520 px tall.
//   o: { lean, tilt (head), bob (px), sq, turn (-1..1: face shifts, 3/4 cheat), eyes: 'open'|'happy'|'closed'|'wink'|'star'|'shy'|'determined'|'side',
//        mouth: 'smile'|'open'|'o'|'cat'|'tongue'|'flat'|'grin'|'small', sing (0..1 mouth open), blush (0..1), look [dx,dy],
//        armL / armR: [shoulder, elbow] radians (0 = hanging, + = raise outward), handL / handR: 'mitt'|'claw'|'clawOpen'|'point'|'fist'|'open'|'mic'|'wave',
//        legL / legR: [hip, knee], hop, skirtFlare (0..1), hairLift (0..1), sweat, sparkle }

// ------------------------------------------------------------------ Clawd, the block (and the backup-dancer troupe)
// clawd(x, y, s, o): (x, y) = ground point. s = 1: body 200 px wide.
//   pose:   sq, lean, hop, walk (phase), bow (0..1), armL/armR (nub angle: 0 out, + up), pincer (nubs become claws), snip (0..1 claw open)
//   face:   eyes 'open'|'happy'|'closed'|'wide'|'x'|'star'|'heart'|'shades', look [dx,dy], blush, mouth: null|'cat'|'open'|'o'
//   dress:  hat 'bow'|'headband'|'hardhat'|'crown'|'cap'|'party'|'beret'|'halo'|'tophat', bowtie, glasses ('round'|'shades'), col (body colour)
//   props:  holdL / holdR: 'penlight'(+penCol) | 'fan' | 'mic' | 'flag' | {sign: 'TEXT'} | fn(ctx at nub tip)
//   glow (0..1), seed (varies blink timing and wobble)
function clawd(x, y, s = 1, o = {}) {
  const t = NOW, sq = o.sq || 0, seed = o.seed ?? 11, col = o.col || C_.clay, colD = o.colD || C_.clayD;
  X.save(); X.translate(x, y - (o.hop || 0) * s); X.rotate(o.lean || 0); X.scale(s * (1 + sq * .5), s * (1 - sq * .5));
  const bw = 200, bh = 124, top = -bh - 44, L = (p, f, w = 4) => shp(p, f, w / 2 + 1.2, LN);
  const lg = o.walk != null ? o.walk : null;
  [-78, -34, 34, 78].forEach((lx, i) => { const lift = lg != null ? Math.max(0, Math.sin(lg * TAU + (i % 2) * Math.PI)) * 14 : 0; L(wob(rect(lx - 13, -46 - lift, 26, 44), seed + i, .6), col); });
  // nubs: plain, or pincers that snap
  const nub = (side, ang, hold) => {
    X.save(); X.translate(side * bw / 2, top + 58); X.rotate(-side * (ang || 0));
    if (o.pincer) {
      const op = (o.snip ?? 0) * .7 + .05;
      X.save(); X.translate(side * 10, 0); X.scale(1.4, 1.4); X.rotate(-side * op); L(wob(blob([[0, -6], [side * 44, -20], [side * 52, -4], [side * 12, 4]], 3), seed + side, .3), col); X.restore();
      X.save(); X.translate(side * 10, 0); X.scale(1.4, 1.4); X.rotate(side * op); L(wob(blob([[0, 6], [side * 44, 20], [side * 52, 4], [side * 12, -4]], 3), seed + side + 2, .3), col); X.restore();
    } else L(wob(rrect(side > 0 ? -6 : -34, -15, 40, 30, 8), seed + side, .6), col);
    if (hold) { X.translate(side * 40, 0); X.rotate(side * (ang || 0)); holdProp(hold, side, o, t); }
    X.restore();
  };
  nub(-1, o.armL, o.holdL); nub(1, o.armR, o.holdR);
  const bow = o.bow || 0;
  const body = wob(rrect(-bw / 2, top + bow * 30, bw, bh - bow * 30, 12), seed + 5, .8);
  L(body, col, 5);
  clipTo(body, () => { X.fillStyle = colD; X.fillRect(-bw / 2, top + bh - 22, bw, 30); X.fillStyle = 'rgba(255,235,220,.35)'; X.fillRect(-bw / 2 + 14, top + bow * 30 + 10, 60, 10); });
  if (o.glow) glow(0, top + bh / 2, 260 * o.glow, 'rgba(255,230,150,1)', .8 * o.glow);
  const fy = top + 48 + bow * 50, lk = o.look || [0, 0], ex = 38;
  const eyes = o.eyes || (((t * 1000 + seed * 431) % 3700) < 110 ? 'closed' : 'open');
  for (const side of [-1, 1]) {
    const cx = side * ex + lk[0] * 8, cy = fy + lk[1] * 6;
    if (eyes === 'open') fil(rrect(cx - 9, cy - 24, 18, 48, 7), LN);
    else if (eyes === 'wide') { fil(rrect(cx - 12, cy - 28, 24, 56, 9), LN); fil(rrect(cx - 5, cy - 20, 7, 14, 3), C_.white); }
    else if (eyes === 'happy') lin([[cx - 14, cy + 6], [cx, cy - 10], [cx + 14, cy + 6]], 7, LN);
    else if (eyes === 'closed') lin([[cx - 14, cy], [cx + 14, cy]], 7, LN);
    else if (eyes === 'x') { lin([[cx - 12, cy - 12], [cx + 12, cy + 12]], 6, LN); lin([[cx - 12, cy + 12], [cx + 12, cy - 12]], 6, LN); }
    else if (eyes === 'star') sparkle(cx, cy, 22, C_.lemon, t * 2, 2);
    else if (eyes === 'heart') shp(blob([[cx, cy + 16], [cx - 18, cy - 2], [cx - 10, cy - 16], [cx, cy - 8], [cx + 10, cy - 16], [cx + 18, cy - 2]], 3), C_.pink, 2, LN);
  }
  if (o.glasses === 'shades' || eyes === 'shades') { L(rrect(-66, fy - 20, 56, 34, 8), C_.ink); L(rrect(10, fy - 20, 56, 34, 8), C_.ink); lin([[-10, fy - 8], [10, fy - 8]], 5, C_.ink); }
  else if (o.glasses === 'round') for (const side of [-1, 1]) { X.lineWidth = 4; X.strokeStyle = LN; X.beginPath(); X.arc(side * ex, fy, 28, 0, TAU); X.stroke(); }
  if (o.mouth === 'cat') lin([[-18, fy + 40], [-9, fy + 47], [0, fy + 41], [9, fy + 47], [18, fy + 40]], 3.5, LN);
  else if (o.mouth === 'open') L(blob([[-16, fy + 36], [16, fy + 36], [8, fy + 56], [-8, fy + 56]], 3), C_.pinkD, 3);
  else if (o.mouth === 'o') L(ellipse(0, fy + 44, 8, 10), C_.pinkD, 3);
  if (o.blush) for (const side of [-1, 1]) fil(ellipse(side * 66, fy + 32, 16, 9), C_.pink);
  if (o.bowtie) { L(blob([[0, top + bh - 16], [-26, top + bh - 30], [-26, top + bh - 2]], 2), o.bowtie === true ? C_.pink : o.bowtie, 3); L(blob([[0, top + bh - 16], [26, top + bh - 30], [26, top + bh - 2]], 2), o.bowtie === true ? C_.pink : o.bowtie, 3); }
  if (o.hat) clawdHat(o.hat, top + bow * 30, t, seed, o);
  X.restore();
}
function clawdHat(h, top, t, seed, o) {
  const L = (p, f, w = 4) => shp(p, f, w / 2 + 1.2, LN);
  if (h === 'bow') { L(blob([[0, top - 4], [-44, top - 30], [-48, top + 8]], 3), C_.pink); L(blob([[0, top - 4], [44, top - 30], [48, top + 8]], 3), C_.pink); L(circle(0, top - 6, 10), C_.pinkD); }
  else if (h === 'headband') { L(rrect(-102, top + 2, 204, 20, 6), C_.white); lin([[98, top + 12], [128, top - 6], [124, top + 22]], 5, C_.white); fil(circle(0, top + 12, 8), C_.pink); }
  else if (h === 'hardhat') { L(blob([[-70, top + 4], [-60, top - 44], [0, top - 60], [60, top - 44], [70, top + 4]], 4), C_.lemon); L(rrect(-86, top - 2, 172, 12, 5), C_.lemonD); }
  else if (h === 'crown') L([[-50, top + 2], [-54, top - 44], [-26, top - 20], [0, top - 52], [26, top - 20], [54, top - 44], [50, top + 2]], C_.lemon);
  else if (h === 'cap') { L(blob([[-66, top + 4], [-56, top - 40], [0, top - 52], [56, top - 40], [66, top + 4]], 4), C_.cyan); L(rrect(20, top - 4, 90, 14, 6), C_.cyanD); }
  else if (h === 'party') { L([[-34, top + 2], [0, top - 90], [34, top + 2]], C_.cyan); fil(circle(0, top - 92, 12), C_.lemon); lin([[-20, top - 30], [20, top - 44]], 4, C_.pink); }
  else if (h === 'beret') L(blob([[-70, top + 4], [-74, top - 20], [0, top - 40], [74, top - 22], [70, top + 4]], 4), C_.violet);
  else if (h === 'halo') { X.save(); X.lineWidth = 8; X.strokeStyle = C_.lemon; X.beginPath(); X.ellipse(0, top - 40, 60, 16, 0, 0, TAU); X.stroke(); X.restore(); }
  else if (h === 'tophat') { L(rrect(-74, top - 6, 148, 14, 5), C_.ink); L(rrect(-48, top - 80, 96, 78, 6), C_.ink); fil(rect(-48, top - 26, 96, 12), C_.pink); }
}
function holdProp(h, side, o, t) {
  const L = (p, f, w = 4) => shp(p, f, w / 2 + 1.2, LN);
  if (typeof h === 'function') return h();
  if (h === 'penlight') { const c = o.penCol || C_.cyan; X.save(); X.rotate(-side * .6 - Math.PI / 2); L(rrect(-6, -10, 12, 30, 4), C_.ink); L(rrect(-8, -90, 16, 84, 8), c); glow(0, -60, 70, c, .5); X.restore(); }
  else if (h === 'fan') { X.save(); X.rotate(-Math.PI / 2); L([[0, 0], [-40, -70], [40, -70]], C_.pink); lin([[0, 0], [0, -70]], 3, LN); X.restore(); }
  else if (h === 'mic') { X.save(); X.rotate(-Math.PI / 2); L(rrect(-6, -8, 12, 36, 5), C_.ink); L(circle(0, -18, 13), '#8A8FA8'); X.restore(); }
  else if (h === 'flag') { lin([[0, 0], [0, -120]], 5, LN); L([[0, -120], [70, -104], [0, -84]], C_.pink); }
  else if (h.sign) { lin([[0, 0], [0, -70]], 6, LN); X.save(); X.translate(0, -120); X.rotate(-side * .08); L(rrect(-90, -46, 180, 92, 10), C_.white); pop(h.sign, 0, 18, { font: 'dela', size: h.size || 40, align: 'center', fill: h.col || C_.pink, lw: 0 }); X.restore(); }
}
// the troupe: n costumed backup dancers doing a move in canon (no twinning). move(u, i) -> clawd options for dancer i at phase u.
const TROUPE_HATS = ['bow', 'headband', 'crown', 'cap', 'party', 'beret', 'hardhat', 'tophat'];
function troupe(t, xs, y, s, move, o = {}) {
  xs.forEach((x, i) => {
    const d = Math.abs(i - (xs.length - 1) / 2), lag = d * (o.lag ?? .06);
    const m = move(t - lag, i) || {};
    clawd(x, y, s, { seed: 20 + i * 7, hat: o.hats === false ? null : (o.hats || TROUPE_HATS)[i % (o.hats || TROUPE_HATS).length], ...m });
  });
}
// ------------------------------------------------------------------ SD idol Clawd (Neko-Arc-style SD: see refs/chibi_neko.png)
// Thin warm-brown line, flat colour + one soft shade, a huge head (half her height) whose hair mass frames a small face,
// big calm white oval eyes with tall slit pupils (Clawd's eyes), a ':3' mouth, a tiny body, big mitten hands, chunky boots.
const LN = '#5A2E24', LNW = 4.5;
const IDOL = { headY: -372, shoulderY: -236, waistY: -186, hemY: -104, bootY: -70 };
const sh2 = (pts, fill, lw = LNW) => shp(pts, fill, lw / 2, LN);
function idol(x, y, s = 1, o = {}) {
  const t = NOW, seed = o.seed ?? 3, turn = clamp(o.turn || 0, -1, 1);
  const flare = o.skirtFlare || 0, lift = o.hairLift || 0, sway = Math.sin(t * 2.4 + seed) * 3 + (o.hairSway || 0);
  X.save(); X.translate(x, y - (o.hop || 0) * s + (o.bob || 0) * s); X.scale(s * (1 + (o.sq || 0) * .4), s * (1 - (o.sq || 0) * .4)); X.rotate(o.lean || 0);
  const hy = IDOL.headY;
  // ---------- back hair mass (behind the body): shoulder-length, pointed locks
  X.save(); X.translate(0, hy); X.rotate((o.tilt || 0) * .6);
  const back = [[-138, -40], [-150 - lift * 18, 40], [-140 + sway, 112 - lift * 30], [-120 + sway, 98], [-102 + sway, 134 - lift * 30], [-66, 110], [66, 110], [102 + sway, 134 - lift * 30], [120 + sway, 98], [140 + sway, 112 - lift * 30], [150 + lift * 18, 40], [138, -40], [0, -150]];
  sh2(wob(blob(back, 5), seed + 1, .8), C_.clayD);
  X.restore();
  // ---------- boots + legs
  const leg = (side, a) => {
    const [hp, kn] = a || [0, 0];
    X.save(); X.translate(side * 26, IDOL.hemY - 6); X.rotate(-hp * side);
    sh2(wob(rrect(-11, 0, 22, 44, 9), seed + side * 3, .5), C_.skin);
    X.translate(0, 38); X.rotate(kn || 0);
    const boot = blob([[-24, 0], [24, 0], [26, 44], [34, 58], [30, 70], [-26, 70], [-28, 44]], 3);
    sh2(wob(boot, seed + side * 5, .5), C_.boot);
    fil(wob(rrect(-25, 0, 50, 14, 5), seed + side * 6, .4), C_.clay); lin([[-25, 14], [25, 14]], 2.5, LN);
    lin(arcPts2(0, 40, 14, 8, Math.PI * .15, Math.PI * .85), 2.5, C_.bootD);
    X.restore();
  };
  leg(-1, o.legL); leg(1, o.legR);
  // ---------- skirt: A-line, cream front panel, stepped pixel hem, a peek of black shorts
  const sw = 96 + flare * 40, st = IDOL.waistY, sb = IDOL.hemY - flare * 8;
  fil(rrect(-40, sb - 14, 80, 22, 6), C_.hem);
  const skirt = wob([[-44, st], [44, st], [sw, sb], [-sw, sb]], seed + 13, .7);
  sh2(skirt, C_.clay);
  clipTo(skirt, () => {
    X.fillStyle = C_.hem; X.beginPath(); const n = 8, stepW = sw * 2 / n;
    for (let i = 0; i < n; i++) { const hh = [18, 28, 18, 24][i % 4]; X.rect(-sw + i * stepW, sb - hh, stepW + 1, hh + 2); }
    X.fill();
    fil([[-14, st], [14, st], [34, sb - 22], [-34, sb - 22]], C_.cream);
    fil([[40, st], [sw, sb], [sw - 30, sb], [30, st]], 'rgba(90,30,20,.14)');          // soft shade on one side
  });
  // ---------- torso + collar + the big cream bow
  const torso = wob(blob([[-36, IDOL.shoulderY], [36, IDOL.shoulderY], [44, st + 4], [-44, st + 4]], 2), seed + 17, .6);
  sh2(torso, C_.clay);
  const rb = IDOL.shoulderY + 22, rw = 1 + Math.sin(t * 5) * .03;
  sh2(wob(blob([[0, rb], [-44 * rw, rb - 24], [-50 * rw, rb + 8], [-30 * rw, rb + 22]], 3), seed + 33, .5), C_.cream);
  sh2(wob(blob([[0, rb], [44 * rw, rb - 24], [50 * rw, rb + 8], [30 * rw, rb + 22]], 3), seed + 35, .5), C_.cream);
  sh2(wob(blob([[-10, rb + 6], [-18, rb + 44], [-4, rb + 38]], 2), seed + 37, .4), C_.cream);
  sh2(wob(blob([[10, rb + 6], [18, rb + 44], [4, rb + 38]], 2), seed + 39, .4), C_.cream);
  sh2(wob(rrect(-11, rb - 10, 22, 20, 7), seed + 41, .3), C_.cream);
  // ---------- head
  X.save(); X.translate(0, hy); X.rotate(o.tilt || 0);
  const fx = turn * 22;
  // buns: soft rounded squares where cat ears would be, with a darker underside and claw clips
  for (const side of [-1, 1]) {
    X.save(); X.translate(side * 108 - turn * 6, -150 - lift * 8); X.rotate(side * (.24 + Math.sin(t * 3 + side) * .03));
    const bun = rrect(-46, -46, 92, 84, 28);
    sh2(wob(bun, seed + 51 + side, .6), C_.clay);
    clipTo(bun, () => { fil(rrect(-46, 8, 92, 40, 10), C_.clayD); fil(rrect(-30, -40, 40, 12, 6), 'rgba(255,230,210,.45)'); });
    X.translate(side * -28, 34); sh2(wob(blob([[-10, 0], [0, -10], [10, 0], [3, 5], [0, 0], [-3, 5]], 2), seed + 55 + side, .3), C_.clayL);
    X.restore();
  }
  // face: small and soft; the hair frames it
  const face = wob(blob([[-104, -30], [-92, -92], [0, -118], [92, -92], [104, -30], [96, 40], [56, 92], [0, 106], [-56, 92], [-96, 40]], 5), seed + 61, .7);
  sh2(face, C_.skin);
  clipTo(face, () => fil(ellipse(0, -120, 150, 70), 'rgba(90,40,30,.10)'));                // the fringe's soft shadow
  // side locks: long pointed locks framing the face down to the chin
  for (const side of [-1, 1]) {
    const sl = [[side * 92, -96], [side * (140 + lift * 10), -10], [side * (132 + sway * .6), 70], [side * (118 + sway), 124], [side * 106, 86], [side * 98, 112], [side * 94, 40], [side * 90, -40]];
    sh2(wob(blob(sl, 4), seed + 63 + side, .7), C_.clay);
  }
  // the fringe: a soft cap of hair with pointed locks falling over the forehead
  const fr = [[-146, -40], [-140, -104], [-80, -160], [20, -168], [110, -146], [148, -84], [146, -36],
    [120, -70], [104, -30], [80, -84], [58, -34], [34, -90], [8, -40], [-20, -92], [-44, -36], [-70, -88], [-96, -30], [-118, -74]];
  sh2(wob(tx(fr, fx * .35, 0), seed + 67, .8), C_.clay);
  for (const [a0, b0] of [[-60, -150], [10, -160], [70, -140]]) lin([[a0 + fx * .35, b0], [a0 * 1.1 + fx * .35, b0 + 60]], 2.5, C_.clayD);
  X.save(); X.lineCap = 'round'; X.strokeStyle = 'rgba(255,225,200,.55)'; X.lineWidth = 12; X.beginPath(); X.arc(fx * .3, -40, 128, Math.PI * 1.17, Math.PI * 1.62); X.stroke(); X.restore();   // glossy band
  lin([[fx * .35 - 6, -164], [fx * .35 - 20, -200], [fx * .35 + 4, -192]], 4, LN);   // ahoge
  spark8(84 + fx * .3, -110, 24, C_.lemon, 2.5, t * .5);
  drawEyes(o, 112, fx, seed, t);
  const bl = o.blush ?? .3;
  if (bl > 0) for (const side of [-1, 1]) { X.globalAlpha = clamp(bl); fil(ellipse(side * 66 + fx, 52, 18, 9), C_.pink); X.globalAlpha = 1; if (bl > .7) for (let k = -1; k <= 1; k++) lin([[side * 66 + fx + k * 8 - 3, 48], [side * 66 + fx + k * 8 + 3, 56]], 2, C_.pinkD); }
  drawMouth(o, 112, fx, t);
  if (o.sweat) sh2(blob([[112, -40], [124, -10], [110, -8]], 3), C_.cyan);
  X.restore();
  // ---------- arms (over everything, so raised poses read)
  const arm = (side, a, hand) => {
    const [sh, el] = a || [.25, .15];
    const L1 = 40, L2 = 36, S = [side * 44, IDOL.shoulderY + 12];
    const a1 = side * -sh, a2 = a1 + side * -el;
    const Ep = [S[0] - Math.sin(a1) * L1, S[1] + Math.cos(a1) * L1], Wr = [Ep[0] - Math.sin(a2) * L2, Ep[1] + Math.cos(a2) * L2];
    const tube = wob([S, Ep, Wr], seed + side * 21, .4);
    lin(tube, 26, LN); lin(tube, 26 - LNW, C_.skin);
    X.save(); X.translate(Wr[0], Wr[1]); X.rotate(a2);
    sh2(wob(rrect(-16, -8, 32, 14, 5), seed + side * 25, .3), C_.clay); fil(rrect(-16, -8, 32, 4, 2), C_.cream);
    X.translate(0, 8); drawHand(hand || 'mitt', side, seed + side * 27, t);
    X.restore();
    X.save(); X.translate(S[0], S[1] - 4); X.rotate(a1 * .4);
    sh2(wob(ellipse(0, 6, 26, 21), seed + side * 29, .6), C_.clay); lin([[-16, 22], [16, 22]], 3.5, C_.cream);
    X.restore();
  };
  arm(-1, o.armL, o.handL); arm(1, o.armR, o.handR);
  X.restore();
}
// eyes: big calm white ovals, a tall slit pupil (amber), one small highlight. No lashes, no iris clutter.
function drawEyes(o, hr, fx, seed, t) {
  const kind = o.eyes || 'open', lk = o.look || [0, 0];
  const blink = kind === 'open' && ((t * 1000 + seed * 333) % 3900) < 110;
  for (const side of [-1, 1]) {
    const cx = side * 50 + fx, cy = 10;
    const k = (kind === 'wink' && side === 1) ? 'happy' : (blink ? 'closed' : kind);
    if (k === 'happy') { lin(arcPts2(cx, cy + 16, 30, 26, Math.PI * 1.12, Math.PI * 1.88), 5, LN); continue; }
    if (k === 'closed') { lin(arcPts2(cx, cy - 4, 30, 16, Math.PI * .12, Math.PI * .88), 5, LN); continue; }
    const ew = 48, eh = 38;
    const lidTop = k === 'determined' ? .45 : k === 'shy' ? .2 : 0;
    const eyeP = ellipse(cx, cy, ew, eh, side * -.06);
    sh2(eyeP, C_.white, 4);
    clipTo(eyeP, () => {
      const px = cx + (lk[0] + (k === 'side' || k === 'shy' ? .7 : 0)) * 14, py = cy + lk[1] * 8;
      if (k === 'star') { sparkle(px, py, 22, C_.eye, t * 2); sparkle(px, py, 11, C_.white, t * 2); }
      else { fil(ellipse(px, py, 8.5, 27), C_.eye); fil(ellipse(px, py, 3.5, 20), C_.eyeD); fil(circle(px + 12, py - 12, 4), C_.white); }
      if (lidTop) fil(rect(cx - ew, cy - eh - 2, ew * 2, eh * 2 * lidTop + 2), C_.skin);
    });
    if (lidTop) lin([[cx - ew * .9, cy - eh + eh * 2 * lidTop - side * 4], [cx + ew * .9, cy - eh + eh * 2 * lidTop + side * 4]], 4, LN);
  }
}
function arcPts2(cx, cy, rx, ry, a0, a1, n = 14) { const p = []; for (let i = 0; i <= n; i++) { const a = lerp(a0, a1, i / n); p.push([cx + Math.cos(a) * rx, cy + Math.sin(a) * ry]); } return p; }
// mouths: the default is ':3' (the cat/crab mouth)
function drawMouth(o, hr, fx, t) {
  const m = o.mouth || 'cat', my = 62, s = clamp(o.sing ?? 0);
  const cat = (w = 11) => lin([[fx - w * 2, my - 4], [fx - w, my + 4], [fx, my - 3], [fx + w, my + 4], [fx + w * 2, my - 4]], 3.5, LN);
  if (s > .08 || m === 'open') {
    const op = m === 'open' ? Math.max(s, .8) : s, w = 12 + op * 8, h = 6 + op * 22;
    const p = blob([[fx - w, my - 2], [fx + w, my - 2], [fx + w * .5, my + h], [fx - w * .5, my + h]], 4);
    sh2(p, C_.pinkD, 3.5); clipTo(p, () => fil(ellipse(fx, my + h + 2, w * .7, h * .45 + 2), C_.pink));
  } else if (m === 'cat' || m === 'smile') cat();
  else if (m === 'grin') { const p = blob([[fx - 20, my - 4], [fx + 20, my - 4], [fx, my + 16]], 4); sh2(p, C_.pinkD, 3.5); }
  else if (m === 'o') sh2(ellipse(fx, my + 4, 8, 10), C_.pinkD, 3.5);
  else if (m === 'tongue') { cat(); sh2(blob([[fx + 2, my + 2], [fx + 14, my + 2], [fx + 11, my + 14], [fx + 4, my + 13]], 3), C_.pink, 3); }
  else if (m === 'flat') lin([[fx - 12, my], [fx + 12, my]], 3.5, LN);
  else if (m === 'small') lin(arcPts2(fx, my - 4, 8, 5, Math.PI * .2, Math.PI * .8), 3.5, LN);
  else if (m === 'pout') lin(arcPts2(fx, my + 6, 10, 6, Math.PI * 1.2, Math.PI * 1.8), 3.5, LN);
}
// hands: big round mittens (Neko-Arc), and a mitten that splits into two pincers for the claw
function drawHand(kind, side, seed, t) {
  if (kind === 'mitt' || kind === 'wave' || kind === 'open') { sh2(wob(circle(0, 26, 34, 28), seed, .4), C_.skin); lin(arcPts2(side * -10, 28, 18, 15, Math.PI * .6, Math.PI * 1.1), 3, C_.skinD); }
  else if (kind === 'fist') sh2(wob(circle(0, 24, 30, 26), seed, .4), C_.skin);
  else if (kind === 'claw' || kind === 'clawOpen') {
    const open = kind === 'clawOpen' ? .62 : .05;
    X.save(); X.translate(-3, 6); X.rotate(open); sh2(wob(blob([[0, 0], [-32, 16], [-30, 54], [-5, 64], [5, 36]], 3), seed, .3), C_.skin); X.restore();
    X.save(); X.translate(3, 6); X.rotate(-open); sh2(wob(blob([[0, 0], [32, 16], [30, 54], [5, 64], [-5, 36]], 3), seed + 1, .3), C_.skin); X.restore();
  } else if (kind === 'point') { sh2(wob(circle(0, 16, 22, 24), seed, .4), C_.skin); sh2(rrect(-6, 24, 12, 30, 6), C_.skin); }
  else if (kind === 'mic') {
    sh2(wob(circle(0, 18, 24, 24), seed, .4), C_.skin);
    X.save(); X.translate(0, 10); X.rotate(side * .5 + Math.PI);
    sh2(rrect(-6, 10, 12, 40, 5), C_.ink, 3); sh2(circle(0, 52, 14), '#8A8FA8', 3); lin([[-8, 50], [8, 50]], 2, C_.ink);
    X.restore();
  }
}
// ------------------------------------------------------------------ pose presets (arms/hands), blendable
const POSE = {
  idle:    { armL: [.22, -.1], armR: [.22, -.1], handL: 'mitt', handR: 'mitt' },
  wave:    { armL: [.22, -.1], armR: [2.2, .25], handL: 'mitt', handR: 'wave' },
  sing:    { armL: [.35, -.2], armR: [.55, 2.2], handL: 'mitt', handR: 'mic' },             // mic up at the mouth
  claw:    { armL: [1.75, 1.35], armR: [1.75, 1.35], handL: 'claw', handR: 'claw' },         // claws up beside the face
  clawOpen:{ armL: [1.75, 1.35], armR: [1.75, 1.35], handL: 'clawOpen', handR: 'clawOpen' },
  up:      { armL: [2.75, .05], armR: [2.75, .05], handL: 'open', handR: 'open' },           // "Clawd-up!" both arms high
  point:   { armL: [.22, -.1], armR: [1.5, .05], handL: 'mitt', handR: 'point' },
  shrug:   { armL: [.7, -1.3], armR: [.7, -1.3], handL: 'open', handR: 'open' },
  offer:   { armL: [.55, 1.35], armR: [.55, 1.35], handL: 'mitt', handR: 'mitt' },           // both hands forward, holding
  heart:   { armL: [.4, 2.0], armR: [.4, 2.0], handL: 'mitt', handR: 'mitt' },               // hands at the chest
  tehe:    { armL: [.22, -.1], armR: [2.3, 1.9], handL: 'mitt', handR: 'fist' },             // fist bonk on the head
  cupEar:  { armL: [.22, -.1], armR: [1.9, 1.5], handL: 'mitt', handR: 'open' },
  bow:     { armL: [.1, 0], armR: [.1, 0], handL: 'mitt', handR: 'mitt' },
};
// blend two presets (u 0..1); hands switch at u > .5
function pose(a, b = null, u = 0) {
  const A = POSE[a], B = b ? POSE[b] : A, o = {};
  for (const k of ['armL', 'armR']) o[k] = [lerp(A[k][0], B[k][0], u), lerp(A[k][1], B[k][1], u)];
  for (const k of ['handL', 'handR']) o[k] = u > .5 ? B[k] : A[k];
  return o;
}
