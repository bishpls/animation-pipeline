// SO BACK: drop 2 (beats 48-64, 19.25-25.65). Owner: the drop2/end section agent.
//   b48-52  CHOOSE YOUR CHARACTER!  the roster strobe: 8 on 16ths, 16 on 32nds (accelerating), landing on Captain Falcon
//           on b51 with the P1 token (Melee's character-select d2chip); held to b52
//   b52-56  we're-we're so-so BACK  20XX: keyed waveshining Fox multiplying 1 -> 2x2 -> 4x4 on the stutters, the up-smash
//           big on BACK, then the whole grid waveshining (everyone plays Fox, frame perfect)
//   b56-60  D2W, INCREDIBLE!        everyone's back: Falcon's recovery (up-B), then Fox on the revival platform
//   b60-64  THIS GAME'S D2_WINNER IS... the punch's impact stuttered on the 16th-note fill, then the breakdown on Falcon's face
const D2 = {
  roster: [],                                  // [{ name, K, pt, c: [cx, cy], z }] : the strobe (placeholder until lane 2's roster)
};
const d2pkey = (name, n) => () => vplate(name, n, { keyed: true });
const D2_SKEY = () => spineKey();                                 // the keyed spine (through spine.js: SPV picks the version)

// ---- the roster. PLACEHOLDER: single-fighter frames of the existing keyed plates (swap for lane 2's soback_roster*)
const D2_ROSTER_PH = [
  { name: 'MARTH', K: d2pkey('drop_tipper', 120), pt: pf(118), c: [300, 1250], z: 1.2 },
  { name: 'JIGGLYPUFF', K: d2pkey('drop_rest', 156), pt: pf(124), c: [740, 1150], z: 1.0 },
  { name: 'PIKACHU', K: d2pkey('drop_thunder', 180), pt: pf(110), c: [290, 1640], z: 1.5 },
  { name: 'FALCO', K: d2pkey('drop_lasers', 204), pt: pf(200), c: [604, 1300], z: 1.25 },
  { name: 'FOX', K: D2_SKEY, pt: pf(1000), c: [563, 1000], z: 1.3 },
];
// lane 2's roster plate: all 26 in their own taunts, keyed, framed to a common height (info.json index: first frame, 30 each).
// The strobe order contrasts neighbours (silhouette, colour); Captain Falcon is the landing pick.
const D2_RPL = () => vplate('roster', 780, { keyed: true });
const D2_RFIRST = {"doc": 1, "mario": 31, "luigi": 61, "bowser": 91, "peach": 121, "yoshi": 151, "dk": 181, "falcon": 211, "ganon": 241, "falco": 271, "fox": 301, "ness": 331, "ics": 361, "kirby": 391, "samus": 421, "zelda": 451, "sheik": 481, "link": 511, "ylink": 541, "pichu": 571, "pikachu": 601, "puff": 631, "mewtwo": 661, "gnw": 691, "marth": 721, "roy": 751};
D2.roster = ["fox", "puff", "bowser", "pikachu", "marth", "kirby", "dk", "sheik", "samus", "yoshi", "gnw", "mewtwo", "link", "peach", "ganon", "pichu", "roy", "ics", "ness", "luigi", "zelda", "ylink", "mario", "falco"].map(k => ({ key: k, name: k, K: D2_RPL, pt: pf(D2_RFIRST[k] + 15), c: [W / 2, H / 2], z: 1 }));
// the landing pick (was the frozen orbit's face-and-hand frame) (keyed; the windup aura around him), film ~8.3
const D2_FALCON = { key: 'falcon', name: 'CAPTAIN FALCON', K: D2_RPL, pt: pf(D2_RFIRST.falcon + 18), c: [W / 2, H / 2], z: 1.06 };
const D2RS = { t0: bt(48), land: bt(51), t1: bt(52) };
// slot times: 8 sixteenths (b48-b50), then 16 thirty-seconds (b50-b51)
const D2_SLOTS = [...Array(8)].map((_, i) => bt(48 + i * .25)).concat([...Array(16)].map((_, i) => bt(50 + i * .125)));
const D2_FIELDS = [PAL.pink, PAL.lime, PAL.cyan, PAL.violet, PAL.gold, '#ff6a2e'];
function D2_ROSTER(t) {
  const land = t >= D2RS.land, i = land ? -1 : Math.max(0, D2_SLOTS.findIndex((s, k) => t >= s && (k + 1 === D2_SLOTS.length || t < D2_SLOTS[k + 1])));
  const R = D2.roster.length ? D2.roster : D2_ROSTER_PH;
  const c = land ? D2_FALCON : R[i % R.length];
  const K = c.K(), col = land ? PAL.gold : D2_FIELDS[i % D2_FIELDS.length];
  const z = c.z * (land ? punch(t, D2RS.land, .12, .3) * (1 + .04 * E.out3(clamp((t - D2RS.land) / .4))) : 1);
  const b = scene(() => {
    if (land) fieldBurst(t, col, '#ffe98a', W / 2, H * .5, .5); else { flat(col); dots(PAL.white, 46, 5, .4); }
    captionsIn(t, ['thesis'], { y: 700, size: 1.12 });              // the words behind the fighter: on the field, the pick in front
    keyed(K, c.pt, { z, c: c.c, d: [W / 2 - c.c[0], H * .5 - c.c[1]], outline: land ? PAL.ink : PAL.white, ow: land ? 14 : 10 });   // subject centred
  });
  if (NEED) return;
  present(b, 'saturate(1.1)', land ? 12 * Math.exp(-(t - D2RS.land) * 8) : 0);
  // the name plate: the game's own results-screen name texture (the label set on a dark plate; the banner serif on the pick)
  mname(c.key || D2_NAMEKEY[c.name] || 'falcon', W / 2, 1340, { h: land ? 110 : 84, set: land ? 'banner' : 'label', panel: true });
  if (land) d2p1token(t);
  return { cap: { y: 470, skip: ['thesis'] } };
}
// the P1 token dropping onto the pick (a red d2chip, "P1"): falls in over 0.12 s with a bounce
const D2_NAMEKEY = { 'MARTH': 'marth', 'JIGGLYPUFF': 'puff', 'PIKACHU': 'pikachu', 'FALCO': 'falco', 'FOX': 'fox', 'CAPTAIN FALCON': 'falcon' };
function d2p1token(t) {
  const u = clamp((t - D2RS.land) / .16), y = lerp(-120, 1180, E.back(u)), x = 760;   // onto his chest
  X.save(); X.translate(x, y); X.rotate(-.15 * (1 - u));
  X.fillStyle = 'rgba(0,0,0,.35)'; X.beginPath(); X.arc(8, 10, 74, 0, TAU); X.fill();
  X.fillStyle = '#e8262a'; X.beginPath(); X.arc(0, 0, 74, 0, TAU); X.fill();
  X.lineWidth = 10; X.strokeStyle = '#fff'; X.stroke();
  mtext('P1', 0, 4, { size: 78, style: 'white' });
  X.restore();
}

// ---- 20XX: the stutter hook. The waveshine plate: shines on f47, f69; the JC up-smash on f82
const D2XX = { t0: bt(52), hits: [bt(52), bt(52.5), bt(53), bt(53.5), bt(54)], grid: bt(55), t1: bt(56) };
// each stutter restarts a shine: we're/we're on shine 1, so/so on shine 2, BACK on the up-smash; then the grid replays it all
function d2xxPt(t) {
  const h = last(t, D2XX.hits), k = D2XX.hits.indexOf(h);
  if (t >= D2XX.grid) return pf(40) + ((t - D2XX.grid) * 1.6) % (pf(90) - pf(40));      // the whole chain, looping, a bit fast
  const hitF = [47, 47, 69, 69, 82][k];
  return pf(hitF) - .05 + (t - h);
}
function d2grid(t) {                                            // a green wire grid racing in on black (the digital floor)
  flat('#030805');
  const hz = H * .42; X.save(); X.strokeStyle = '#39ff6a'; X.lineWidth = 3; X.globalAlpha = .75;
  for (let c = -12; c <= 12; c++) { X.beginPath(); X.moveTo(W / 2 + c * 30, hz); X.lineTo(W / 2 + c * 520, H); X.stroke(); }
  const off = (t * 2.5) % 1;
  for (let r = 0; r < 16; r++) { const z = 1 / (r + 1 - off + .5), y = hz + (H - hz) * z * 1.2; if (y > H) continue; X.globalAlpha = .75 * clamp(z * 3); X.beginPath(); X.moveTo(0, y); X.lineTo(W, y); X.stroke(); }
  X.globalAlpha = .45;
  for (let c = -12; c <= 12; c++) { X.beginPath(); X.moveTo(W / 2 + c * 30, hz); X.lineTo(W / 2 + c * 520, 0); X.stroke(); }
  X.restore();
}
function d2tiles(src, n, mirror = true) {                            // src (a W x H canvas) as an n x n grid, alternate d2tiles flipped
  const w = W / n, h = H / n;
  for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) {
    const fx = mirror && i % 2, fy = mirror && j % 2 && n > 2;
    X.save(); X.translate(i * w + (fx ? w : 0), j * h + (fy ? h : 0)); X.scale((fx ? -1 : 1) * w / W, (fy ? -1 : 1) * h / H);
    X.drawImage(src, 0, 0); X.restore();
  }
}
function d2chip(s, x, y, size = 50, bg = PAL.ink, fg = PAL.lime) {    // in-group chips: the game's menu font, white dress
  mtext(s, x, y - size * .35, { size: size * 1.3, style: 'white' });
}
function D2_XXHOOK(t) {
  const K = DP.waveshine(), pt = d2xxPt(t), h = last(t, D2XX.hits);
  const big = t >= D2XX.hits[4] && t < D2XX.grid;                      // BACK: the up-smash alone, big
  const n = big ? 1 : t >= D2XX.grid ? 4 : t >= D2XX.hits[3] ? 4 : t >= D2XX.hits[1] ? 2 : 1;
  const z = (big ? 1.4 : n === 1 ? 1.25 : 1.1) * punch(t, h, big ? .2 : .12, big ? .3 : .2);
  // no outline here: the shine's glow is in the matte, and a dilated glow becomes a lime blob (the grid gives the contrast)
  const one = scene(() => { d2grid(t); keyed(K, pt, { z, c: [W * .42, H * .58], outline: n === 1 ? PAL.lime : null, ow: 10 }); });
  if (NEED) return;
  const neg = big && t - D2XX.hits[4] < 1 / 60;
  const dh = dehaze('waveshine', pt);                              // undo the game's full-frame hit flash (drop.js)
  if (n === 1) present(one, neg ? NEG : dh + 'saturate(1.15)', 12 * Math.exp(-(t - h) * 9));
  else {
    const g = buf('xxgrid'); const X0 = X; X = g.x; d2tiles(one.c, n, true); X = X0;
    present(g, dh + 'saturate(1.2) contrast(1.05)', 8 * Math.exp(-(t - h) * 9));
  }
  if (t >= D2XX.grid) { d2chip('20XX', 250, 300, 58); d2chip('FRAME PERFECT', 690, 1450, 46, PAL.lime, PAL.ink); }
  return { cap: { y: n === 1 ? 420 : 760 } };
}

// ---- D2W, INCREDIBLE! everyone's back. b56 "D2W,": Falcon's up-B from the abyss (the spine, film 14.3-15.0);
// "INCREDIBLE!" (23.2): Fox on the revival platform, keyed, over a heavenly gold burst (the spine film 14.95-15.65, the
// invincibility flash on 15.37 lands on the word's third syllable, ~23.5)
const D2W = { t0: bt(56), inc: 23.2, t1: bt(60) };
const d2wowMap = tmap([[D2W.t0, 14.30], [D2W.inc, 14.68]]);          // the Falcon Dive out of the abyss, in slow motion
const d2incMap = tmap([[D2W.inc, 14.95], [23.52, 15.37], [D2W.t1, 15.80]]);
function D2_WOW(t) {
  if (t < D2W.inc) {
    const K = spine(), pt = d2wowMap(t) + SP.pre, z = (1.1 + .12 * clamp((t - D2W.t0) / .75)) * punch(t, D2W.t0, .1, .3);
    const b = scene(() => { X.save(); zoomAt(W * .62, H * .3, z); drawPlate(K, pt); X.restore(); });
    if (NEED) return;
    present(b, 'saturate(1.35) contrast(1.08)', 10 * Math.exp(-(t - D2W.t0) * 8));
    return { cap: { y: 1560 } };                                   // the stamp low, under the dive
  }
  const K = D2_SKEY(), pt = d2incMap(t) + SP.pre, z = 1.3 * punch(t, D2W.inc, .08, .25) * punch(t, 23.52, .06, .2);
  const b = scene(() => { fieldBurst(t, '#ffd84d', '#fff3b0', W / 2, H * .45, .3); keyed(K, pt, { z, c: [560, 1000], outline: PAL.white, ow: 12 }); });
  if (NEED) return;
  present(b, 'saturate(1.15)', 0);                                  // (the game's own respawn flash is the accent)
  return { cap: { y: 470 } };
}

// ---- THIS GAME'S D2_WINNER IS... the fill (24.05-24.65): the punch's impact stuttered on 16ths (6 slices of 0.1 s),
// zooming in on every other, the negative on every third; the breakdown (24.65-25.45): Falcon's face in the frozen world,
// in full colour, pushing in slowly; the riser (25.45-25.65): a fast push into the stab
const D2WIN = { t0: bt(60), brk: 24.65, rise: 25.45, t1: bt(64), face: [10.30, 10.80] };   // face: frozen-orbit film span (re-aimed)
function D2_WINNER(t) {
  const K = spine();
  if (t < D2WIN.brk) {
    const k = Math.floor((t - D2WIN.t0) / .1), lt = (t - D2WIN.t0) - k * .1;
    const pt = 12.83 + lt * .8 + SP.pre, z = [1, 1.35, 1.1, 1.6, 1.2, 1.9][k % 6];
    const b = scene(() => { X.save(); zoomAt(...SP.punchXY, z); drawPlate(K, pt); X.restore(); });
    if (NEED) return;
    present(b, k % 2 ? 'saturate(1.5) contrast(1.35)' : 'saturate(1.2) contrast(1.05)', k % 2 ? 16 : 6);
    return { cap: { y: 420 } };
  }
  const u = clamp((t - D2WIN.brk) / (D2WIN.rise - D2WIN.brk)), r = clamp((t - D2WIN.rise) / (D2WIN.t1 - D2WIN.rise));
  const pt = lerp(D2WIN.face[0], D2WIN.face[1], u) + SP.pre;
  const z = 1.05 + .12 * E.io2(u) + .5 * E.in3(r);
  const b = scene(() => { X.save(); zoomAt(W / 2, H * .42, z); drawPlate(K, pt); X.restore(); });
  if (NEED) return;
  present(b, `saturate(${1.15 - .3 * (1 - r)}) contrast(1.15) brightness(${.8 + .3 * r})`, 6 * r);
  vignette(.7 - .4 * r); grain(t, .1);
  return { cap: { y: 1150 } };
}

shots([
  [D2RS.t0, D2_ROSTER],
  [D2XX.t0, D2_XXHOOK],
  [D2W.t0, D2_WOW],
  [D2WIN.t0, D2_WINNER],
]);

// the game's sound (see sfx.py): shines and the up-smash on the stutters; Fox's respawn; the punch's hit stuttered on the fill
SFX.push(
  [bt(52) - .03, 'drop_waveshine', pf(47) - .03, .25, 2, 'post', '20XX: shine'],
  [bt(52.5) - .03, 'drop_waveshine', pf(47) - .03, .25, 0, 'post', '20XX: shine again'],
  [bt(53) - .03, 'drop_waveshine', pf(69) - .03, .25, 2, 'post', '20XX: shine 2'],
  [bt(53.5) - .03, 'drop_waveshine', pf(69) - .03, .25, 0, 'post', '20XX: shine 2 again'],
  [bt(54) - .03, 'drop_waveshine', pf(82) - .03, .45, 4, 'post', '20XX: up-smash'],
  [D2W.t0, 'sacred' + SPV, 14.30 + SP.pre, .75, 0, 'post', 'Falcon recovers (the dive, 1:1 audio from its start)'],
  [23.44, 'sacred' + SPV, 15.29 + SP.pre, .5, 0, 'post', 'Fox respawns'],
  [D2WIN.t0, 'sacred' + SPV, 12.84 + SP.pre, .1, 2, 'post', 'fill: the hit 1'],
  [D2WIN.t0 + .2, 'sacred' + SPV, 12.84 + SP.pre, .1, 2, 'post', 'fill: the hit 2'],
  [D2WIN.t0 + .4, 'sacred' + SPV, 12.84 + SP.pre, .12, 3, 'post', 'fill: the hit 3'],
);
