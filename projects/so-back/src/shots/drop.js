// SO BACK: the drop montage (bars 9-12 after the punch: beat 35 "BACK" to beat 48 "CHOOSE YOUR CHARACTER"). Keyed tech
// moments from lane 3 over the Y2K fields, each move's key hit on a beat or a sung accent. Plate hit times (plate s = (k-1)/60)
// come from each plate's info.json. The first shot is the TEMPLATE for the drop's language:
//   keyed pair + white outline over a field; a 1-2 frame impact frame (the matte, white on black) on each hit;
//   a zoom punch and shake on the hit; an RGB split that decays; cuts on beats; the field changes with every cut.
const DP = {
  waveshine: () => vplate('drop_waveshine', 124, { keyed: true }),
  tipper: () => vplate('drop_tipper', 120, { keyed: true }),
  rest: () => vplate('drop_rest', 156, { keyed: true }),
  lasers: () => vplate('drop_lasers', 204, { keyed: true }),
  thunder: () => vplate('drop_thunder', 180, { keyed: true }),
};
const pf = k => (k - 1) / 60;                                   // plate frame k -> plate seconds

// WAVESHINE (b35-b37): shine on b35 ("BACK"), the wavedash-shine on b36 ("SUCCESS!"), the JC up-smash on b36.5
const WS = { t0: bt(35) - .12, t1: bt(37), hits: [bt(35), bt(36), bt(36.5)] };
const wsMap = tmap([[WS.t0, pf(47) - .12], [bt(35), pf(47)], [bt(36), pf(69)], [bt(36.5), pf(82)], [WS.t1, pf(97)]]);   // (past f97 both have left the frame)
function WAVESHINE(t) {
  const K = DP.waveshine(), pt = wsMap(t), h = last(t, WS.hits);
  const z = 1.08 * punch(t, h, .14, .25), [sx, sy] = shake(t, 22 * Math.exp(-Math.max(0, t - h) * 10));
  const impact = h === bt(36.5) && negAt(t, h);                          // the negative frame: the up-smash only
  const b = scene(() => {
    (h >= bt(36) ? fieldSpeed(t, PAL.violet, PAL.cyan) : fieldChrome(t));
    keyedS(K, pt, { z, c: [W / 2, H * .6], d: [sx, sy], outline: PAL.white });
  });
  if (NEED) return;
  present(b, dehaze('waveshine', pt) + (impact ? NEG : 'saturate(1.12)'), 14 * Math.exp(-Math.max(0, t - h) * 9));
  return { cap: { y: 360 } };                                      // the fighters fill the lower frame: words go high
}
SFX.push(
  [bt(35) - .03, 'drop_waveshine', pf(47) - .03, .35, 4, 'post', 'shine'],
  [bt(36) - .03, 'drop_waveshine', pf(69) - .03, .35, 4, 'post', 'shine'],
  [bt(36.5) - .03, 'drop_waveshine', pf(82) - .03, .45, 6, 'post', 'up-smash'],
);

// ---- the game's hit flash, undone: on a big hit Melee lays a near-uniform translucent flash over the whole frame (measured from
// each plate's least-covered corner: alpha h per frame from the hit, colour c). Over any field it reads as a pale wash, so
// most of it is inverted on the final frame: out = c h + (1 - h) S  =>  S = (out - c h) / (1 - h), as CSS contrast + brightness.
// KEEP of it stays (the flash still registers).
const HAZE = {
  waveshine: { f0: 82, c: 255, h: [0.125, 0.114, 0.106, 0.082, 0.094, 0.063, 0.063, 0.063, 0.031, 0.031] },
  tipper: { f0: 64, c: 255, h: [0.125, 0.114, 0.106, 0.082, 0.094, 0.063, 0.063, 0.063, 0.031, 0.031] },
  rest: { f0: 100, c: 180, h: [0.125, 0.125, 0.106, 0.106, 0.09, 0.082, 0.063, 0.063, 0.051, 0.035, 0.031] },
  lasers: { f0: 181, c: 255, h: [0.125, 0.114, 0.106, 0.082, 0.094, 0.063, 0.063, 0.063, 0.031, 0.031] },
  thunder: { f0: 150, c: 185, h: [0.125, 0.11, 0.11, 0.09, 0.09, 0.071, 0.063, 0.043, 0.039, 0.031] },
};
const HAZE_KEEP = .15;
function dehaze(plate, pt) {
  const d = HAZE[plate]; if (!d) return '';
  const i = Math.floor(pt * 60 + 1e-6) + 1 - d.f0, h = (i >= 0 && i < d.h.length ? d.h[i] : 0) * (1 - HAZE_KEEP);
  if (h <= 0) return '';
  const k = 1 / (1 - h), q = d.c * h / 127.5, b = k * (1 - q), s = 1 / (1 - q);
  return `contrast(${s.toFixed(4)}) brightness(${b.toFixed(4)}) `;
}
// ---- a solid-body outline. keyedOutline (edit.js) dilates the raw matte by stamping it 16 times, so a 12% full-frame hit flash
// accumulates to ~88% (1 - .875^16) and paints the whole frame white, and glows balloon into blobs. Here the matte is first
// thresholded (alpha >= .7: bodies only) through an SVG alpha filter, then dilated.
(() => {
  if (document.getElementById('sbSolid')) return;
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('width', '0'); svg.setAttribute('height', '0'); svg.style.position = 'absolute';
  svg.innerHTML = '<filter id="sbSolid" color-interpolation-filters="sRGB"><feComponentTransfer>' +
    '<feFuncA type="discrete" tableValues="0 0 0 0 0 0 0 1 1 1"/></feComponentTransfer></filter>';
  document.body.appendChild(svg);
})();
function outlineSolid(K, pt, col = '#fff', wpx = 12) {
  if (NEED) { _need(K, pt); return; }
  const m = K.a.img(pt); if (!m) return;
  const sm = buf('solidm'); sm.x.filter = 'url(#sbSolid)'; sm.x.drawImage(m, 0, 0, W, H); sm.x.filter = 'none';
  const o = buf('kout2'); o.x.setTransform(X.getTransform());
  for (let i = 0; i < 16; i++) { const a = i / 16 * TAU; o.x.drawImage(sm.c, Math.cos(a) * wpx, Math.sin(a) * wpx, W, H); }
  o.x.setTransform(1, 0, 0, 1, 0, 0); o.x.globalCompositeOperation = 'source-in'; o.x.fillStyle = col; o.x.fillRect(0, 0, W, H);
  X.save(); X.setTransform(1, 0, 0, 1, 0, 0); X.drawImage(o.c, 0, 0); X.restore();
}
function keyedS(K, pt, o = {}) {
  const z = o.z || 1, [cx, cy] = o.c || [W / 2, H / 2], [dx, dy] = o.d || [0, 0];
  X.save(); zoomAt(cx, cy, z, dx, dy);
  if (o.outline !== null) outlineSolid(K, pt, o.outline || PAL.white, o.ow || 12);
  drawKeyed(K, pt);
  X.restore();
}
// ---- helpers local to the montage
// a velocity ramp into a hit and out of it: keys [[film t, plate t, ease of the segment that starts here], ...] (tmap)
const hitFX = (t, h, amt = .14, sh = 22) => ({ z: punch(t, h, amt, .25), s: shake(t, sh * Math.exp(-Math.max(0, t - h) * 10)) });
const negAt = (t, h) => t - h >= -1e-6 && t - h < 1 / 60 - 1e-6;          // (float-safe: bt() sums carry error)
function mirrored(fn) { X.save(); X.translate(W, 0); X.scale(-1, 1); fn(); X.restore(); }
function darkField(t, line = PAL.lime, bg = '#0d0620', cx = W / 2, cy = H * .55) { flat(bg); speedLines(cx, cy, line, 60, Math.floor(t * 30), 300, .55); }
// On a hit the field flips to a dark one: Melee's hit glows are alpha-blended, so over a bright field they turn into a pale
// haze (a white-out); over dark they glow as they do in the game. Bright on the approach, dark on the hit: the drop's rhythm.

// TIPPER (b37-b39): Fox's short-hop nair falls short and L-cancels; Marth's tipper (f64, 20%) lands on b38 ("COMPLETE!").
// Fast through the wavedash back, slow into the swing, the hitlag holds, then Fox flies past the lens.
const TP = { t0: bt(37), t1: bt(39), hit: bt(38) };
const tpMap = tmap([[TP.t0, pf(40)], [bt(37.55), pf(57), 'out3'], [TP.hit, pf(64)], [bt(38.35), pf(74)], [TP.t1, pf(92)]]);
function TIPPER(t) {
  const K = DP.tipper(), pt = tpMap(t), { z, s: [sx, sy] } = hitFX(t, TP.hit, .18, 30);
  const zz = (t < TP.hit ? lerp(1.0, 1.12, E.io2(clamp((t - TP.t0) / (TP.hit - TP.t0)))) : 1.12) * z;   // a push-in to the swing
  const b = scene(() => {
    if (t < TP.hit) fieldFloor(t, PAL.lime, '#9be000', '#2e0a5c', PAL.violet, 4); else darkField(t, PAL.lime, '#0d0620', W * .7, H * .55);
    keyedS(K, pt, { z: zz, c: [W * .72, H * .62], d: [sx, sy] });
  });
  if (NEED) return;
  present(b, dehaze('tipper', pt) + (negAt(t, TP.hit) ? NEG : 'saturate(1.1) contrast(1.05)'), 16 * Math.exp(-Math.max(0, t - TP.hit) * 8));
  return { cap: { y: 470 } };
}

// LASERS (b39-b42.75): Falco's two low short-hop lasers hit on b40 and b41 ("WE'RE", "SO"), the forward smash on b42
// ("BACK"). The second laser plays mirrored (a pattern interrupt); the smash snaps back, with the negative frame.
const LZ = { t0: bt(39), t1: bt(42.75), hits: [bt(40), bt(41), bt(42)] };
const lzMap = tmap([[LZ.t0, pf(54)], [bt(39.7), pf(68), 'out3'], [bt(40), pf(73)], [bt(40.25), pf(96)], [bt(40.7), pf(119), 'out3'],
  [bt(41), pf(125)], [bt(41.3), pf(150)], [bt(41.75), pf(175), 'out3'], [bt(42), pf(181)], [bt(42.3), pf(189)], [LZ.t1, pf(203)]]);
function LASERS(t) {
  const K = DP.lasers(), pt = lzMap(t), h = last(t, LZ.hits), { z, s: [sx, sy] } = hitFX(t, h, h === bt(42) ? .2 : .1, h === bt(42) ? 34 : 16);
  const flip = t >= bt(40.5) && t < bt(41.5);                                          // the second laser, mirrored
  const b = scene(() => {
    const dark = t - h < .3;                                                           // the dark flip on each hit
    if (dark && h > 0) darkField(t, t < bt(41.5) ? PAL.lime : PAL.cyan, h === bt(42) ? '#10031f' : '#0d0620', W * .5, H * .62);
    else if (t < bt(40.5)) fieldBurst(t, PAL.violet, '#9b5cff', W / 2, H * .6, .5);
    else if (flip) fieldBurst(t, PAL.lime, '#e2ff7a', W / 2, H * .6, -.6);
    else fieldSpeed(t, PAL.cyan, '#fff', W * .55, H * .58);
    const draw = () => keyedS(K, pt, { z: 1.06 * z, c: [W * .5, H * .66], d: [sx - 150, sy + 150] });   // (Fox sits at the plate's right edge)
    flip ? mirrored(draw) : draw();
  });
  if (NEED) return;
  present(b, dehaze('lasers', pt) + (negAt(t, bt(42)) ? NEG : 'saturate(1.12)'), 12 * Math.exp(-Math.max(0, t - h) * 9));
  return { cap: { y: 470 } };
}

// REST (b42.75-b46): Puff's drill (f52-82, a hit every 5 frames) as a buzz on the 16ths with a zoom staircase, the fast fall
// and L-cancel, then Rest (f101, 28%) on b44 ("A NEW RECORD!") with the negative frame; Fox burns off the top; the sleep
// bubble (f156) lands just before the cut. Puff is pink: no pink fields.
const RS = { t0: bt(42.75), t1: bt(46), hit: bt(44) };
const rsMap = tmap([[RS.t0, pf(49)], [bt(43.5), pf(82), 'out3'], [RS.hit, pf(101)], [bt(44.4), pf(113)],
  [bt(45.2), pf(140)], [bt(45.9), pf(156), 'out2'], [RS.t1, pf(156)]]);
function REST(t) {
  const K = DP.rest(), pt = rsMap(t), { z, s: [sx, sy] } = hitFX(t, RS.hit, .22, 36);
  const step = t < RS.hit ? 1 + .08 * clamp(Math.floor((t - bt(43)) / (BEAT / 4)) + 1, 0, 4) : 1;   // the 16th staircase
  const asleep = t >= bt(45);
  const b = scene(() => {
    if (asleep) fieldSpeed(t, PAL.lime, '#fff', W * .55, H * .55);
    else if (t >= RS.hit) darkField(t, PAL.cyan, '#0b0720', W * .55, H * .5);
    else fieldFloor(t, '#2ee6ff', '#12b8d8', '#1a0640', PAL.violet, 5);
    keyedS(K, pt, { z: 1.02 * step * z, c: [W * .55, H * .58], d: [sx, sy], outline: asleep ? PAL.violet : PAL.white });
  });
  if (NEED) return;
  present(b, dehaze('rest', pt) + (negAt(t, RS.hit) ? NEG : 'saturate(1.08)'), 18 * Math.exp(-Math.max(0, t - RS.hit) * 7) + (t < RS.hit ? 4 * pulse(t, 20, .25) : 0));
  return { cap: { y: 420 } };
}

// THUNDER (b46-b48): Pikachu's up-throw (a snap), a jump cut to Fox's missed tech, Thunder (f150) on b47; the bolt spans the
// portrait frame, lingers in slow motion, and the shot hands over at bt(48) to CHOOSE YOUR CHARACTER.
const TH = { t0: bt(46), t1: bt(48), hit: bt(47), jump: bt(46.4) };
const thMap = tmap([[TH.t0, pf(64)], [TH.jump, pf(90)], [TH.jump + .001, pf(124), 'out3'], [TH.hit, pf(150)],
  [bt(47.5), pf(157), 'in2'], [TH.t1, pf(178)]]);
function THUNDER(t) {
  const K = DP.thunder(), pt = thMap(t), { z, s: [sx, sy] } = hitFX(t, TH.hit, .16, 30);
  const b = scene(() => {
    if (t < TH.jump) fieldChrome(t); else darkField(t, t < TH.hit ? PAL.cyan : PAL.lime);
    keyedS(K, pt, { z: (t < TH.jump ? 1.05 : 1.0) * z, c: [W * .5, H * .7], d: [sx, sy] });
  });
  if (NEED) return;
  present(b, dehaze('thunder', pt) + (negAt(t, TH.hit) ? NEG : 'saturate(1.1) contrast(1.05)'), 14 * Math.exp(-Math.max(0, t - TH.hit) * 6));
  flash(t >= TH.jump && t < TH.jump + 1 / 60 ? .5 : 0, '#000');                        // the jump cut: one black frame
  return { cap: { y: 400 } };
}

// the game's own sound for the montage (the plates' audio.wav), each hit on its film time
SFX.push(
  [TP.hit - .04, 'drop_tipper', pf(64) - .04, .55, 7, 'post', 'tipper'],
  [bt(40) - .14, 'drop_lasers', pf(73) - .14, .4, 4, 'post', 'laser 1 (fire, hit)'],
  [bt(41) - .14, 'drop_lasers', pf(125) - .14, .4, 4, 'post', 'laser 2 (fire, hit)'],
  [bt(42) - .06, 'drop_lasers', pf(181) - .06, .6, 7, 'post', 'forward smash'],
  ...[0, 1, 2, 3, 4, 5, 6].map(i => { const f = 52 + 5 * i, ft = RS.t0 + (bt(43.5) - RS.t0) * (pf(f) - pf(49)) / (pf(82) - pf(49));
    return [ft - .01, 'drop_rest', pf(f) - .01, .07, i === 0 ? 3 : 0, 'post', `drill ${i + 1}`]; }),
  [RS.hit - .03, 'drop_rest', pf(101) - .03, .9, 8, 'post', 'Rest'],
  [TH.t0, 'drop_thunder', pf(77) - .02, .2, 2, 'post', 'up-throw'],
  [TH.hit - .45, 'drop_thunder', pf(150) - .45, 1.0, 7, 'post', 'Thunder'],
);

shots([
  [WS.t0, WAVESHINE],
  [TP.t0, TIPPER],
  [LZ.t0, LASERS],
  [RS.t0, REST],
  [TH.t0, THUNDER],
]);
