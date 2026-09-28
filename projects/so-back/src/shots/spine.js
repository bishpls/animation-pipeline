// SO BACK: the spine (STORYBOARD "The spine"). One continuous director capture of the sacred combo, on the film clock:
// plate time pt = film t + PRE (1.0). The knee is drawn on film 0.05, the freeze runs film 2.90-12.27 (the camera keeps
// orbiting), and the Falcon Punch lands on 12.85. Cold open, "over" and the turn all cut from this one plate, plus the KO
// flashes (lane 2) intercut into the frozen section on the vocal beats.
const SP = { pre: 1.0, knee: .05, freeze: 2.90, unfreeze: 12.27, punch: 12.85,
  kneeXY: [590, 900], punchXY: [650, 1020] };
const SPV = '';                                                        // the spine's plate version ('' = the re-aimed v2; '_v1' kept)
const spine = () => vplate('sacred' + SPV, 1170, { pre: SP.pre });
const spineKey = () => vplate('sacred_key' + SPV, 1170, { pre: SP.pre, keyed: true });
// separation in the grey section: the stage-on frame darkened as the ground, the fighters (the keyed pass's matte, same
// camera) lifted over it. The matte masks the stage-on pixels themselves, so no glow is added twice.
function rimmed(pt, lift = 1) {
  const K = spine(), KK = spineKey();
  if (NEED) { drawPlate(K, pt); _need(KK, pt); return; }
  const im = K.rgb.img(pt), m = KK.a.img(pt); if (!im || !m) return;
  X.save(); X.filter = `brightness(${1 - .22 * lift})`; X.drawImage(im, 0, 0, W, H); X.restore();
  const fg = buf('fg'); fg.x.filter = `brightness(${1 + .22 * lift}) contrast(${1 + .1 * lift})`; fg.x.drawImage(im, 0, 0, W, H); fg.x.filter = 'none';
  fg.x.globalCompositeOperation = 'destination-in'; fg.x.drawImage(m, 0, 0, W, H);
  const T = X.getTransform(); X.save(); X.setTransform(T); X.drawImage(fg.c, 0, 0); X.restore();
}
const STAR = () => vplate('over_star', 226), SCREEN = () => vplate('over_screen', 164);

// the cold open's time map (film t -> film-equivalent capture time; pt = that + PRE):
//   0-0.45 1:1 (the knee on 0.05) | 0.45-0.85 the triple take (the impact again, then again in slow motion) |
//   0.85-1.9 the landing, dash and dash-dance at 1.38x | 1.9-2.85 1:1 (jump, B, "FALCON..." on 2.73) |
//   2.85-3.25 the tape stop: speed 1 -> 0 as (1-u)^2, the same curve as the audio (mix.py)
const TS0 = 2.85, TS1 = 3.25;
function coldMap(t) {
  if (t < .45) return { ft: t };
  if (t < .65) return { ft: .03 + (t - .45), take: 2 };             // the impact again (0.03 -> 0.23)
  if (t < .85) return { ft: .03 + (t - .65) * .5, take: 3 };        // and again at half speed
  if (t < 1.9) return { ft: .45 + (t - .85) * (1.9 - .45) / (1.9 - .85) };
  if (t < TS0) return { ft: t };
  const D = TS1 - TS0, u = clamp((t - TS0) / D);
  return { ft: TS0 + D * (1 - (1 - u) ** 3) / 3, tape: u };
}

// draw a plate into the frame with a zoom about (cx, cy) and a shake, into the 'scene' buffer; returns that buffer
function scene(fn) { const b = buf('scene'), X0 = X; X = b.x; try { fn(); } finally { X = X0; } return b; }
function zoomAt(cx, cy, z, dx = 0, dy = 0) { X.translate(cx + dx, cy + dy); X.scale(z, z); X.translate(-cx, -cy); }
// grade a buffer onto X: filter string (canvas CSS filters), an optional RGB split (px)
function present(b, filter = 'none', split = 0) {
  if (filter !== 'none') { const g = buf('graded'); g.x.filter = filter; g.x.drawImage(b.c, 0, 0); g.x.filter = 'none'; b = g; }
  if (split) rgbSplit(b.c, split, 0); else X.drawImage(b.c, 0, 0);
}
function vignette(a = .5) {
  const g = X.createRadialGradient(W / 2, H / 2, H * .25, W / 2, H / 2, H * .75);
  g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(1, `rgba(0,0,0,${a})`);
  X.save(); X.setTransform(1, 0, 0, 1, 0, 0); X.fillStyle = g; X.fillRect(0, 0, W, H); X.restore();
}

function COLD(t) {
  const K = spine(), m = coldMap(t), pt = m.ft + SP.pre;
  // zoom punches: the knee (big), each beat (small), the takes (bigger each time)
  let z = punch(t, SP.knee, .16, .3) * punch(t, bt(1), .05) * punch(t, bt(3), .05) * punch(t, bt(4), .06) * punch(t, bt(5), .04) * punch(t, bt(6), .05);
  if (m.take === 2) z *= 1.28; if (m.take === 3) z *= 1.55;
  const [sx, sy] = shake(t, 26 * Math.exp(-Math.max(0, t - SP.knee) * 9) + (m.take ? 10 : 0));
  const b = scene(() => { X.save(); zoomAt(...SP.kneeXY, z, sx, sy); drawPlate(K, pt); X.restore(); });
  if (NEED) return;
  const tape = m.tape || 0;                                             // the tape stop drains the colour with the speed
  const filt = tape ? `saturate(${1 - .85 * tape}) contrast(${1 + .25 * tape}) brightness(${1 - .2 * tape})` : 'saturate(1.15) contrast(1.06)';
  const split = t < SP.knee ? 0 : t < SP.knee + .25 ? 16 * Math.exp(-(t - SP.knee) * 8) : m.take ? 12 : 3 * pulse(t, 10);
  const neg = t >= SP.knee + 1 / 60 && t < SP.knee + 2 / 60;               // the contact frame clean, then one negative frame
  present(b, neg ? NEG : filt, split);
  flash(m.take && ((t - .45) % .2) < 1 / 60 ? .8 : 0);                    // one on each take
  if (tape) { vignette(.6 * tape); grain(t, .18 * tape); }
  return { cap: t < 1.2 ? { x: 760, y: 300, size: .6 } : { y: 380, size: .7 } };   // the hook sits clear of the knee (top right), then high
}

// the over section's KO flashes, cut to the sung words: Falcon smacks the camera glass on "GAME" (beat 16), then the star KO's
// last approach twinkles out on the sung "OVER" (+1.14 s); the frozen orbit returns under the echo (beat 21). Plate times are
// in each plate's own seconds (frame k at (k-1)/60).
const OV = { screenIn: bt(16) - .32, starIn: bt(17.25), back: bt(21) };
const screenMap = tmap([[OV.screenIn, 1.567], [bt(16), 1.883], [OV.starIn, 2.40]]);
const starMap = tmap([[OV.starIn, 2.317], [bt(16) + 1.14, 3.267, 'out2'], [OV.back, 3.75]]);
// the frozen stretch as bullet time: jump cuts between the orbit's distinct angles every two beats (the capture holds still to
// ~5.5, then swings round), each slice pushing in; after the KO flashes the orbit runs 1:1 into the turn (the face at 9.65)
const ORB = [[TS1, 3.0, [W * .42, H * .38]], [bt(10), 6.2, [W * .45, H * .42]], [bt(12), 7.0, [W * .5, H * .42]], [bt(14), 3.8, [W * .55, H * .72]]];
function orbitAt(t) {                                                     // -> { pt, z, c }
  if (t >= OV.back) return { pt: t + SP.pre, z: lerp(1.08, 1.2, E.io2(clamp((t - OV.back) / (bt(24) - OV.back)))), c: [W * .42, H * .38] };
  let k = 0; while (k + 1 < ORB.length && t >= ORB[k + 1][0] - 1e-6) k++;
  const [t0, o0, c] = ORB[k], t1 = k + 1 < ORB.length ? ORB[k + 1][0] : OV.screenIn;
  return { pt: o0 + (t - t0) + SP.pre, z: lerp(1.0, 1.16, E.out2(clamp((t - t0) / (t1 - t0)))), c };
}

function OVER(t) {
  let b, shk = 0, cap = { y: 1400 };
  if (t >= OV.screenIn && t < OV.starIn) {
    const [sx, sy] = shake(t, t >= bt(16) ? 44 * Math.exp(-(t - bt(16)) * 7) : 0);
    b = scene(() => { X.save(); X.translate(sx, sy); drawPlate(SCREEN(), screenMap(t)); X.restore(); });
    shk = 1; cap = { y: 330 };
  } else if (t >= OV.starIn && t < OV.back) {
    const z = lerp(1.4, 1.9, E.out2(clamp((t - OV.starIn) / (bt(16) + 1.14 - OV.starIn))));   // on the twinkle's point
    b = scene(() => { X.save(); zoomAt(430, 1124, z, W / 2 - 430, H * .55 - 1124); drawPlate(STAR(), starMap(t)); X.restore(); });
    cap = { y: 330 };
  } else { const o = orbitAt(t); b = scene(() => { X.save(); zoomAt(...o.c, o.z); rimmed(o.pt); X.restore(); }); }
  if (NEED) return;
  present(b, 'grayscale(.88) contrast(1.22) brightness(.95)', shk ? 4 : 0);
  // a cold blue-grey wash (multiply) and the grain of it all
  X.save(); X.globalCompositeOperation = 'multiply'; X.fillStyle = '#c4cbe0'; X.fillRect(0, 0, W, H); X.restore();
  vignette(.55); grain(t, .2);
  flash(t >= bt(16) && t < bt(16) + 1 / 60 ? .5 : 0);                   // the glass
  const dip = Math.max(clamp(1 - Math.abs(t - OV.screenIn) / .05), clamp(1 - Math.abs(t - OV.back) / .05),
    ...ORB.slice(1).map(([c]) => clamp(1 - Math.abs(t - c) / .025) * .6));  // each jump cut: a one-frame dip
  flash(dip * .8, '#000');                                               // dips to black at the flash cuts
  return { cap };
}

// the turn: the frozen orbit, colour creeping back from CONTINUE? (b24) to the unfreeze, then the punch on the drop downbeat
function TURN(t) {
  const K = spine(), pt = t + SP.pre;
  const z = punch(t, bt(26), .08) * punch(t, bt(27), .1) * punch(t, bt(30), .05);
  const b = scene(() => { X.save(); zoomAt(W / 2, H * .45, z); rimmed(pt, 1 - clamp((t - bt(28)) / 1)); X.restore(); });
  if (NEED) return;
  const u = E.io2(clamp((t - bt(24)) / (SP.unfreeze - bt(24))));      // grey -> colour
  const filt = `grayscale(${.88 * (1 - u)}) contrast(${1.22 - .14 * u}) brightness(${.95 + .07 * u}) saturate(${1 + .25 * u})`;
  present(b, filt, 0);
  X.save(); X.globalCompositeOperation = 'multiply'; X.globalAlpha = 1 - u; X.fillStyle = '#b8c0d8'; X.fillRect(0, 0, W, H); X.restore();
  vignette(.65 * (1 - u) + .25); grain(t, .2 * (1 - u) + .04);
  flash(t >= bt(31) && t < bt(31) + 1 / 60 ? .5 : 0, '#000');            // the silent beat: a black frame
  return { cap: { y: t >= bt(26) && t < bt(30) ? 1300 : 330 } };
}

// the drop's first bar: the punch lands (12.85), Fox flies to the blast line (13.43); montage cuts from bar 10
function PUNCH(t) {
  const K = spine(), pt = t + SP.pre;
  const z = punch(t, SP.punch, .22, .35) * punch(t, 13.43, .08);
  const [sx, sy] = shake(t, 34 * Math.exp(-Math.max(0, t - SP.punch) * 6) + 18 * Math.exp(-Math.max(0, t - 13.43) * 8) * (t > 13.43));
  const b = scene(() => { X.save(); zoomAt(...SP.punchXY, z, sx, sy); drawPlate(K, pt); X.restore(); });
  if (NEED) return;
  const neg = t >= SP.punch + 1 / 60 - 1e-6 && t < SP.punch + 2 / 60 - 1e-6;   // the impact frame clean, then one negative frame
  present(b, neg ? NEG : 'saturate(1.3) contrast(1.1)', t < SP.punch ? 0 : 22 * Math.exp(-(t - SP.punch) * 6));
  flash(t >= 13.43 && t < 13.43 + 2 / 60 ? .8 : 0);
}

// the game's own sound for the spine, placed on the picture's clock (sfx.py reads SFX):
//   [film t, plate, plate t0 (s from its frame 1), dur, gain dB (the cue's peak over the local music RMS), bus, label]
// bus 'tape' goes through the tape stop with the song (the cold open); 'post' is added after it
SFX.push(
  [SP.knee - .03, 'sacred' + SPV, SP.knee - .03 + SP.pre, .40, 8, 'tape', 'the knee'],
  [.45, 'sacred' + SPV, .03 + SP.pre, .20, 6, 'tape', 'take 2'],
  [.65, 'sacred' + SPV, .03 + SP.pre, .20, 4, 'tape', 'take 3'],
  [1.9, 'sacred' + SPV, 1.9 + SP.pre, .95, 2, 'tape', 'jump, B, "FALCON..."'],
  [OV.screenIn, 'over_screen', 1.567, .95, 6, 'post', 'falling in, the glass (on "GAME")'],
  [bt(16) + 1.14 - .05, 'over_star', 3.217, .6, 6, 'post', 'the twinkle (on "OVER")'],
  [SP.unfreeze, 'sacred' + SPV, SP.unfreeze + SP.pre, .53, 6, 'post', 'the windup'],
  [SP.punch - .05, 'sacred' + SPV, SP.punch - .05 + SP.pre, .95, 9, 'post', '"PUNCH!", the hit, the blast'],
);
