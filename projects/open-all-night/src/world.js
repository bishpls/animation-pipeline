// world.js: the building and the city. One apartment block (the kid lives on floor 5, window col 2),
// the all-night bakery at street level with the OPEN sign in its window. Night: black block on a blue sky,
// lit windows are paper + yellow, dark windows show the blue sky (black knocked out).

const BLDG = { x: 560, w: 800, floors: 8, cols: 4, floorH: 150, ground: 1080, storeH: 260, kid: [5, 2] };
// window rect (world coords) for floor f (0 = first floor above the shop), column c
function winRect(f, c, B = BLDG) {
  const top = B.ground - B.storeH - (f + 1) * B.floorH, colW = B.w / B.cols;
  return [B.x + c * colW + colW * .22, top + B.floorH * .2, colW * .56, B.floorH * .58];
}
function bldgTop(B = BLDG) { return B.ground - B.storeH - B.floors * B.floorH; }

// lit(f, c) -> 0..1 ; o.sign = sign brightness array or false ; o.day = 0..1 (dawn: windows paper, block blue-black)
function building(o = {}) {
  const B = { ...BLDG, ...(o.B || {}) }, top = bldgTop(B);
  // the block: black silhouette with a cornice and a water tower
  ink(P(cut([[B.x - 20, B.ground], [B.x - 20, top + 30], [B.x - 40, top + 30], [B.x - 40, top], [B.x + B.w + 40, top], [B.x + B.w + 40, top + 30], [B.x + B.w + 20, top + 30], [B.x + B.w + 20, B.ground]], 101, 1.2, .5)), o.blockInk || 'black');
  const wt = [B.x + B.w * .72, top];
  ink(P(cut([[wt[0] - 50, wt[1] - 110], [wt[0] + 50, wt[1] - 110], [wt[0] + 56, wt[1] - 50], [wt[0] - 56, wt[1] - 50]], 102)), o.blockInk || 'black');
  ink(P(cut([[wt[0] - 60, wt[1] - 110], [wt[0], wt[1] - 150], [wt[0] + 60, wt[1] - 110]], 103)), o.blockInk || 'black');
  for (const dx of [-44, 0, 44]) ink(P(rect(wt[0] + dx - 4, wt[1] - 52, 8, 52)), o.blockInk || 'black');
  // windows
  for (let f = 0; f < B.floors; f++) for (let c = 0; c < B.cols; c++) {
    const [x, y, w, h] = winRect(f, c, B), L = o.lit ? o.lit(f, c) : 0, sd = f * 7 + c;
    const shape = P(cut(rect(x, y, w, h), 200 + sd, .9, .4));
    knock(shape, ['black']);                                         // dark glass: the sky's blue shows
    if (L > 0) {
      knock(shape, ['blue'], 1);
      if (L >= .99) ink(shape, { yellow: 1 });
      else ink(shape, { yellow: L });                                // warming up: halftone
      if (o.glow !== false && L > .5) ink(P(rect(x - 30, y - 30, w + 60, h + 60)), { yellow: radial(x + w / 2, y + h / 2, 0, w * 1.3, .5 * L) });
    }
    ink(P(rect(x + w / 2 - 3, y, 6, h)), o.blockInk || 'black');      // mullion
    if (o.inWindow) o.inWindow(f, c, x, y, w, h, L);
  }
  // the bakery storefront
  const sy = B.ground - B.storeH;
  ink(P(rect(B.x - 20, sy, B.w + 40, 26)), o.blockInk || 'black');
  const aw = [B.x + 40, sy + 40, B.w - 80, 70];                      // striped awning
  for (let i = 0; i < 12; i++) ink(P(cut([[aw[0] + i * aw[2] / 12, aw[1]], [aw[0] + (i + 1) * aw[2] / 12, aw[1]], [aw[0] + (i + 1) * aw[2] / 12, aw[1] + aw[3]], [aw[0] + (i + .5) * aw[2] / 12, aw[1] + aw[3] + 18], [aw[0] + i * aw[2] / 12, aw[1] + aw[3]]], 300 + i, .6, .3)), i % 2 ? { pink: 1 } : { yellow: 1 });
  const sw = [B.x + 70, sy + 135, B.w * .55, B.storeH - 150];        // shop window
  knock(P(cut(rect(...sw), 310)), ['black']);
  if (o.shopLight) { knock(P(rect(...sw)), ['blue'], o.shopLight * .7); ink(P(rect(...sw)), { yellow: .35 * o.shopLight }); }
  if (o.sign !== false) {
    save(); const c = layer('blue'); c.save(); openSign(sw[0] + sw[2] / 2, sw[1] + sw[3] * .45, sw[3] * .34, o.sign || [1, 1, 1, 1], { border: o.border ?? 1, darkInks: ['blue', 'black'] }); c.restore(); restore();
  }
  const dr = [B.x + B.w * .72, sy + 120, B.w * .2, B.storeH - 120];  // door
  knock(P(cut(rect(...dr), 320)), ['black']);
  if (o.doorLight) { knock(P(rect(...dr)), ['blue']); ink(P(rect(...dr)), { yellow: 1 }); }
  return B;
}

// night sky: blue flood, knocked-out stars (stable per id, twinkle per drawing), a moon
function nightSky(o = {}) {
  flood('blue', 1);
  const n = o.stars ?? 90, R = rng(o.seed || 7);
  for (let i = 0; i < n; i++) {
    const x = R() * (o.w || W * 2) - (o.ox || 0), y = R() * (o.h || H) - (o.oy || 0), s = 1.5 + R() * 3.5, tw = hash(i * 3.1 + BF(NOW) * .37) > .92;
    if (tw) continue;
    knock(P(s > 4 ? starPts(x, y, s * 2.2, s * .6) : circle(x, y, s, 8)), ['blue']);
  }
  if (o.moon) {
    const [mx, my, mr] = o.moon;
    knock(P(circle(mx, my, mr * 3.2, 48)), ['blue'], radial(mx, my, mr * .95, mr * 3.2, .8, 1.8));   // halo: the blue thins toward the moon
    const disk = P(cut(circle(mx, my, mr, 48), 55, 1.2)); knock(disk, ['blue']); ink(disk, { yellow: .22 });
  }
}
function starPts(cx, cy, r, ri, n = 4) { const p = []; for (let i = 0; i < n * 2; i++) { const a = i / (n * 2) * TAU - Math.PI / 2, rr = i % 2 ? ri : r; p.push([cx + Math.cos(a) * rr, cy + Math.sin(a) * rr]); } return p; }
