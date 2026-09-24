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

// ------------------------------------------------------------------ Clawd, the block
function clawd(x, y, s = 1, o = {}) {
  const t = NOW, sq = o.sq || 0, seed = o.seed ?? 11;
  X.save(); X.translate(x, y - (o.hop || 0) * s); X.rotate(o.lean || 0); X.scale(s * (1 + sq * .5), s * (1 - sq * .5));
  const bw = 200, bh = 124, top = -bh - 44;
  // legs (four stubs), walking alternates pairs
  const lg = o.walk != null ? o.walk : null;
  [-78, -34, 34, 78].forEach((lx, i) => {
    const lift = lg != null ? Math.max(0, Math.sin(lg * TAU + (i % 2) * Math.PI)) * 14 : 0;
    shp(wob(rect(lx - 13, -46 - lift, 26, 46 - 2), seed + i, .8), C_.clay, 5);
  });
  // arms (nubs) behind the body edge
  const arm = (side, ang) => { X.save(); X.translate(side * bw / 2, top + 58); X.rotate(-side * (ang || 0)); shp(wob(rrect(side > 0 ? -6 : -34, -15, 40, 30, 8), seed + side, .8), C_.clay, 5); X.restore(); };
  arm(-1, o.armL); arm(1, o.armR);
  // the body: the block (bow = the whole block tips forward toward camera: shorten + face slides down)
  const bow = o.bow || 0;
  const body = wob(rrect(-bw / 2, top + bow * 30, bw, bh - bow * 30, 10), seed + 5, 1);
  shp(body, C_.clay, 6);
  X.save(); X.clip(P(body)); X.fillStyle = C_.clayD; X.fillRect(-bw / 2, top + bh - 22, bw, 30); X.restore();   // hard shade band
  if (o.glow) glow(0, top + bh / 2, 260 * o.glow, 'rgba(255,230,150,1)', .8 * o.glow);
  // face
  const fy = top + 48 + bow * 50, lk = o.look || [0, 0], ex = 38;
  const eyes = o.eyes || (Math.floor((t + (seed * .37)) % 3.7 * 10) === 0 ? 'closed' : 'open');
  for (const side of [-1, 1]) {
    const cx = side * ex + lk[0] * 8, cy = fy + lk[1] * 6;
    if (eyes === 'open') fil(rrect(cx - 9, cy - 24, 18, 48, 7), C_.ink);
    else if (eyes === 'wide') { fil(rrect(cx - 12, cy - 28, 24, 56, 9), C_.ink); fil(rrect(cx - 5, cy - 20, 7, 14, 3), C_.white); }
    else if (eyes === 'happy') lin([[cx - 14, cy + 6], [cx, cy - 10], [cx + 14, cy + 6]], 8);
    else if (eyes === 'closed') lin([[cx - 14, cy], [cx + 14, cy]], 8);
    else if (eyes === 'x') { lin([[cx - 12, cy - 12], [cx + 12, cy + 12]], 7); lin([[cx - 12, cy + 12], [cx + 12, cy - 12]], 7); }
  }
  if (o.blush) for (const side of [-1, 1]) fil(ellipse(side * 66, fy + 30, 16, 9), C_.pink);
  X.restore();
}

// ------------------------------------------------------------------ SD idol Clawd
const IDOL = { headY: -352, headR: 112, headS: .86, shoulderY: -246, hipY: -100 };
function idol(x, y, s = 1, o = {}) {
  const t = NOW, seed = o.seed ?? 3, turn = clamp(o.turn || 0, -1, 1);
  const flare = o.skirtFlare || 0, lift = o.hairLift || 0;
  X.save(); X.translate(x, y - (o.hop || 0) * s + (o.bob || 0) * s); X.scale(s * (1 + (o.sq || 0) * .4), s * (1 - (o.sq || 0) * .4));
  X.rotate(o.lean || 0);
  const hy = IDOL.headY, hr = IDOL.headR;
  // ---------- back hair (behind everything)
  X.save(); X.translate(0, hy); X.rotate((o.tilt || 0) * .7); X.scale(IDOL.headS, IDOL.headS);
  const sway = Math.sin(t * 2.4) * 3 + (o.hairSway || 0);
  const back = [[-hr * 1.05, -10], [-hr * 1.16 - lift * 20, 50], [-hr * 1.02 + sway, 118 - lift * 30], [-hr * .62 + sway, 132 - lift * 30], [0, 110], [hr * .62 + sway, 132 - lift * 30], [hr * 1.02 + sway, 118 - lift * 30], [hr * 1.16 + lift * 20, 50], [hr * 1.05, -10], [0, -hr * .9]];
  shp(wob(blob(back, 5), seed + 1, 1.2), C_.clayD, LW);
  X.restore();
  // ---------- legs + boots
  const leg = (side, a) => {
    const [hp, kn] = a || [0, 0];
    X.save(); X.translate(side * 28, IDOL.hipY - 2); X.rotate(-side * hp * 0 + hp * side * -1);
    const L1 = 30, L2 = 40;
    const k = [Math.sin(hp) * L1 * side * 0, L1];
    X.save(); X.translate(0, 0);
    shp(wob(rrect(-15, -6, 30, L1 + 8, 10), seed + side * 3, .6), C_.skin, 5);
    shp(wob(rrect(-17, -8, 34, 16, 6), seed + side * 4, .5), C_.hem, 4);          // black shorts hem
    X.translate(0, L1); X.rotate(kn || 0);
    shp(wob(rrect(-15, -4, 30, L2 * .45, 8), seed + side * 5, .6), C_.skin, 5);        // knee
    shp(wob(rrect(-19, L2 * .35, 38, L2 * .75 + 6, 9), seed + side * 7, .6), C_.boot, 5);  // boot shaft
    shp(wob(rrect(-21, L2 * .30, 42, 16, 6), seed + side * 9, .5), C_.clay, 4);          // orange boot top
    shp(wob(blob([[-20, L2 * 1.05], [22 + side * 0, L2 * 1.05], [26, L2 * 1.15 + 14], [-22, L2 * 1.15 + 14]], 3), seed + side * 11, .5), C_.boot, 5);   // foot
    X.restore(); X.restore();
  };
  leg(-1, o.legL); leg(1, o.legR);
  // ---------- skirt (trapezoid, flares), pixel-step hem, cream front panel
  const sw = 100 + flare * 40, st = -176, sb = -84 - flare * 10;
  const skirt = wob([[-50, st], [50, st], [sw, sb], [-sw, sb]], seed + 13, 1);
  shp(skirt, C_.clay, LW);
  clipTo(skirt, () => {
    // pixel steps: a stepped dark band along the hem
    X.fillStyle = C_.hem; X.beginPath();
    const n = 9, stepW = sw * 2 / n;
    for (let i = 0; i < n; i++) { const hh = (i % 2 ? 16 : 26) + (i % 3 === 0 ? 6 : 0); X.rect(-sw + i * stepW, sb - hh, stepW + 1, hh + 2); }
    X.fill();
    fil([[-18, st], [18, st], [30, sb - 20], [-30, sb - 20]], C_.cream);                  // front panel
    lin([[-18, st], [-30, sb - 20]], 3); lin([[18, st], [30, sb - 20]], 3);
    for (const px of [-66, 66]) lin([[px * .55, st + 4], [px, sb - 26]], 3, C_.clayD);   // pleats
  });
  // ---------- torso (bodice) + sleeves are drawn with the arms
  const torso = wob(blob([[-40, IDOL.shoulderY + 6], [40, IDOL.shoulderY + 6], [48, st + 4], [-48, st + 4]], 2), seed + 17, .8);
  // arms: one chubby tube (shoulder -> elbow -> wrist), a cuff, a hand. el > 0 bends the forearm inward/over, el < 0 outward.
  const arm = (side, a, hand) => {
    const [sh, el] = a || [.25, .15];
    const L1 = 44, L2 = 42, S = [side * 50, IDOL.shoulderY + 14];
    const a1 = side * -sh, a2 = a1 + side * -el;
    const E = [S[0] - Math.sin(a1) * L1, S[1] + Math.cos(a1) * L1];
    const Wr = [E[0] - Math.sin(a2) * L2, E[1] + Math.cos(a2) * L2];
    const tube = wob([S, E, Wr], seed + side * 21, .5);
    lin(tube, 40, C_.ink); lin(tube, 27, C_.skin);
    X.save(); X.translate(Wr[0], Wr[1]); X.rotate(a2);
    shp(wob(rrect(-15, -12, 30, 14, 5), seed + side * 25, .4), C_.clay, 4);
    fil(rrect(-15, -12, 30, 5, 2), C_.cream);
    X.translate(0, 0);
    drawHand(hand || 'mitt', side, seed + side * 27, t);
    X.restore();
    // puffy sleeve on top of the shoulder
    X.save(); X.translate(S[0], S[1] - 4); X.rotate(a1 * .45);
    shp(wob(ellipse(0, 8, 27, 23), seed + side * 29, .8), C_.clay, 5);
    lin([[-17, 26], [17, 26]], 4, C_.cream);
    X.restore();
  };
  shp(torso, C_.clay, LW);
  // collar + the big cream ribbon
  shp(wob([[-36, IDOL.shoulderY + 6], [36, IDOL.shoulderY + 6], [0, IDOL.shoulderY + 34]], seed + 31, .6), C_.cream, 4);
  const rb = IDOL.shoulderY + 36, rw = 1 + Math.sin(t * 5) * .03;
  shp(wob(blob([[0, rb], [-48 * rw, rb - 26], [-56 * rw, rb + 6], [-36 * rw, rb + 24]], 3), seed + 33, .6), C_.cream, 4);
  shp(wob(blob([[0, rb], [48 * rw, rb - 26], [56 * rw, rb + 6], [36 * rw, rb + 24]], 3), seed + 35, .6), C_.cream, 4);
  shp(wob(blob([[-12, rb + 8], [-22, rb + 52], [-6, rb + 46]], 2), seed + 37, .5), C_.cream, 4);
  shp(wob(blob([[12, rb + 8], [22, rb + 52], [6, rb + 46]], 2), seed + 39, .5), C_.cream, 4);
  shp(wob(rrect(-13, rb - 12, 26, 24, 8), seed + 41, .4), C_.cream, 4);
  // ---------- head
  X.save(); X.translate(0, hy); X.rotate(o.tilt || 0); X.scale(IDOL.headS, IDOL.headS);
  const fx = turn * 18;                  // the face slides toward the turn (a 3/4 cheat)
  // buns: two blocky ear-buns (rounded squares, tilted outward), with claw clips
  for (const side of [-1, 1]) {
    X.save(); X.translate(side * (hr * .68) - turn * 6, -hr * .86 - lift * 8); X.rotate(side * (.22 + Math.sin(t * 3 + side) * .03));
    shp(wob(rrect(-40, -44, 80, 76, 16), seed + 51 + side, .8), C_.clay, LW);
    fil(rrect(-40, 10, 80, 22, 8), C_.clayD); lin([[-40, 10], [40, 10]], 4);
    lin([[-18, -30], [-10, -8]], 3, C_.clayD);
    // claw clip at the base
    X.translate(side * -24, 30); shp(wob(blob([[-12, 0], [0, -12], [12, 0], [4, 6], [0, 0], [-4, 6]], 2), seed + 55 + side, .4), C_.clayL, 3);
    X.restore();
  }
  // the face
  const face = wob(blob([[-hr * .92, -hr * .25], [-hr * .8, -hr * .8], [0, -hr * 1.0], [hr * .8, -hr * .8], [hr * .92, -hr * .25], [hr * .82, hr * .42], [hr * .35, hr * .84], [0, hr * .88], [-hr * .35, hr * .84], [-hr * .82, hr * .42]], 5), seed + 61, 1);
  shp(face, C_.skin, LW);
  // side locks (framing the face) + fringe: spiky clay shapes over the face top
  for (const side of [-1, 1]) {
    const sl = [[side * hr * .78, -hr * .45], [side * (hr * 1.08 + lift * 10), hr * .1 + sway * .5], [side * (hr * .98), hr * .78 + sway], [side * hr * .82, hr * .52], [side * hr * .7, hr * .1]];
    shp(wob(blob(sl, 4), seed + 63 + side, 1), C_.clay, LW - 1);
  }
  const fr = [[-hr * .95, -hr * .2], [-hr * .9, -hr * .82], [-hr * .3, -hr * 1.08], [hr * .35, -hr * 1.08], [hr * .92, -hr * .8], [hr * .96, -hr * .2],
    [hr * .7, -hr * .42], [hr * .55, -hr * .12], [hr * .36, -hr * .46], [hr * .12, -hr * .08], [-hr * .06, -hr * .44], [-hr * .3, -hr * .1], [-hr * .44, -hr * .44], [-hr * .66, -hr * .1], [-hr * .74, -hr * .42]];
  shp(wob(tx(fr, fx * .4, 0), seed + 67, 1), C_.clay, LW);
  lin([[fx * .4 - 10, -hr * .98], [fx * .4 - 26, -hr * 1.22], [fx * .4 - 4, -hr * 1.1]], 6);   // ahoge (antenna curl)
  X.save(); X.translate(fx * .4, 0); X.fillStyle = C_.clay; X.restore();
  // spark hairpin (the Claude spark), right side
  spark8(hr * .62 + fx * .3, -hr * .6, 24, C_.lemon, 4, t * .5);
  // eyes
  drawEyes(o, hr, fx, seed, t);
  // blush
  const bl = o.blush ?? .35;
  if (bl > 0) for (const side of [-1, 1]) { X.globalAlpha = clamp(bl); fil(ellipse(side * hr * .52 + fx, hr * .36, 20, 10), C_.pink); X.globalAlpha = 1; if (bl > .7) for (let k = -1; k <= 1; k++) lin([[side * hr * .52 + fx + k * 8 - 3, hr * .32], [side * hr * .52 + fx + k * 8 + 3, hr * .4]], 2.5, C_.pinkD); }
  // mouth
  drawMouth(o, hr, fx, t);
  if (o.sweat) shp(blob([[hr * .95, -hr * .5], [hr * 1.05, -hr * .25], [hr * .92, -hr * .22]], 3), C_.cyan, 3);
  X.restore();
  arm(-1, o.armL, o.handL); arm(1, o.armR, o.handR);
  X.restore();
}
function drawEyes(o, hr, fx, seed, t) {
  const kind = o.eyes || 'open', lk = o.look || [0, 0];
  const blink = kind === 'open' && ((t * 1000 + seed * 333) % 3900) < 110;
  for (const side of [-1, 1]) {
    const cx = side * hr * .38 + fx, cy = hr * .05;
    const k = (kind === 'wink' && side === 1) ? 'happy' : (blink ? 'closed' : kind);
    if (k === 'open' || k === 'star' || k === 'shy' || k === 'determined' || k === 'side' || k === 'wink') {
      const ew = 30, eh = 44;
      shp(ellipse(cx, cy, ew, eh), C_.white, 4);
      const px = cx + (lk[0] + (k === 'side' || k === 'shy' ? .6 : 0)) * 8, py = cy + lk[1] * 8 + 4;
      clipTo(ellipse(cx, cy, ew, eh), () => {
        fil(ellipse(px, py, 24, 38), C_.eye); fil(ellipse(px, py + 12, 24, 26), C_.eyeD);
        fil(rrect(px - 5, py - 28, 10, 50, 5), C_.ink);                                          // the tall slit pupil: Clawd's eyes
        fil(ellipse(px - 9, py - 16, 7, 10), C_.white); fil(circle(px + 8, py + 14, 3.5), C_.white);
        if (k === 'star') { sparkle(px - 2, py - 4, 14, C_.white, t * 3); }
      });
      // upper lash line (thick), lower small
      lin(arcPts2(cx, cy + 6, ew + 4, eh + 2, Math.PI * 1.08, Math.PI * 1.92), 9);
      lin([[cx + side * (ew - 2), cy - eh * .55], [cx + side * (ew + 12), cy - eh * .8]], 6);
      if (k === 'determined') lin([[cx - side * 26, cy - eh - 18], [cx + side * 22, cy - eh - 8]], 7);
      if (k === 'shy') lin([[cx - 20, cy - eh - 10], [cx + 20, cy - eh - 16 + side * 4]], 5);
    } else if (k === 'happy') {
      lin(arcPts2(cx, cy + 14, 24, 22, Math.PI * 1.1, Math.PI * 1.9), 8);
    } else if (k === 'closed') {
      lin(arcPts2(cx, cy - 6, 24, 16, Math.PI * .1, Math.PI * .9), 7);
    }
  }
}
function arcPts2(cx, cy, rx, ry, a0, a1, n = 14) { const p = []; for (let i = 0; i <= n; i++) { const a = lerp(a0, a1, i / n); p.push([cx + Math.cos(a) * rx, cy + Math.sin(a) * ry]); } return p; }
function drawMouth(o, hr, fx, t) {
  const m = o.mouth || 'smile', my = hr * .55, s = clamp(o.sing ?? 0);
  if (s > .08 || m === 'open') {
    const op = m === 'open' ? Math.max(s, .8) : s, w = 20 + op * 10, h = 8 + op * 26;
    const p = blob([[fx - w, my - 4], [fx + w, my - 4], [fx + w * .6, my + h], [fx - w * .6, my + h]], 4);
    shp(p, C_.pinkD, 4); clipTo(p, () => fil(ellipse(fx, my + h + 4, w * .7, h * .5 + 2), C_.pink));
  } else if (m === 'smile') lin(arcPts2(fx, my - 12, 18, 12, Math.PI * .15, Math.PI * .85), 5);
  else if (m === 'grin') { const p = blob([[fx - 26, my - 6], [fx + 26, my - 6], [fx, my + 20]], 4); shp(p, C_.pinkD, 4); }
  else if (m === 'o') shp(ellipse(fx, my + 4, 10, 13), C_.pinkD, 4);
  else if (m === 'cat') lin([[fx - 18, my - 4], [fx - 9, my + 4], [fx, my - 2], [fx + 9, my + 4], [fx + 18, my - 4]], 5);
  else if (m === 'tongue') { lin(arcPts2(fx, my - 10, 16, 10, Math.PI * .15, Math.PI * .85), 5); shp(blob([[fx + 2, my], [fx + 16, my], [fx + 12, my + 16], [fx + 4, my + 14]], 3), C_.pink, 3); }
  else if (m === 'flat') lin([[fx - 14, my], [fx + 14, my]], 5);
  else if (m === 'small') lin(arcPts2(fx, my - 6, 9, 6, Math.PI * .2, Math.PI * .8), 4.5);
  else if (m === 'pout') lin(arcPts2(fx, my + 8, 12, 8, Math.PI * 1.2, Math.PI * 1.8), 5);
}
// hands at the arm tip (local: +y runs down the forearm)
function drawHand(kind, side, seed, t) {
  if (kind === 'mitt' || kind === 'wave' || kind === 'open') shp(wob(ellipse(0, 14, 17, 19), seed, .5), C_.skin, 4);
  else if (kind === 'fist') shp(wob(circle(0, 12, 16), seed, .5), C_.skin, 4);
  else if (kind === 'claw' || kind === 'clawOpen') {           // the crab claw: a big two-pincer mitt that snaps (snip-snip!)
    const open = kind === 'clawOpen' ? .6 : .06;
    shp(wob(circle(0, 10, 19), seed, .5), C_.skin, 4);
    X.save(); X.translate(-4, 20); X.rotate(open); shp(blob([[-10, 0], [-22, 30], [-8, 50], [4, 44], [-2, 30], [6, 4]], 3), C_.skin, 4); X.restore();
    X.save(); X.translate(4, 20); X.rotate(-open); shp(blob([[10, 0], [22, 30], [8, 50], [-4, 44], [2, 30], [-6, 4]], 3), C_.skin, 4); X.restore();
  } else if (kind === 'point') { shp(wob(circle(0, 10, 15), seed, .5), C_.skin, 4); shp(rrect(-5, 14, 10, 30, 5), C_.skin, 4); }
  else if (kind === 'mic') {
    shp(wob(circle(0, 12, 16), seed, .5), C_.skin, 4);
    X.save(); X.translate(0, 8); X.rotate(side * .5 + Math.PI);
    shp(rrect(-7, -6, 14, 44, 6), C_.ink, 3); shp(circle(0, 46, 15), '#8A8FA8', 4); lin([[-9, 44], [9, 44]], 2, C_.ink);
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
