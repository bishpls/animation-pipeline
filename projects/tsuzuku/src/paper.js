// paper.js: FABLE's world, a paper theatre (see FABLE.md §4). Plain mode (X = Canvas2D).
// Light is physical: one lantern behind a vellum screen. Puppets are ink masks with holes (light passes) and cellophane films
// (light is tinted). A puppet's distance from the screen makes its shadow larger (projected from the lamp) and softer (penumbra).
// Front-lit mode draws kamishibai cards: ink on washi, with the indigo plate misregistered by a pixel or two.
//
//   screen(t, o)                          the backlit vellum inside the frame; o: { lamp: [x,y], power, rect: [x,y,w,h] }
//   shadow(drawFn, depth, o)              render a puppet layer (drawFn draws into PX: black ink = shadow, film() = colour)
//   PX                                    the puppet context (an offscreen Canvas2D the size of the frame)
//   film(path, hex, alpha)                cellophane inside a puppet: tinted light
//   hole(path)                            a cut-out: pure light passes (eyes, rivets)
//   card(t, drawFn, o)                    a front-lit kamishibai card (ink + misregistered indigo plate) inside the frame
//   butai(t, o)                           the wooden kamishibai stage around the frame (doors, grain)
//   press(str, x, y, t, t0, o)            letterpress type pressed into the page at t0 (thud, deboss, ink spreads into fibre)

const FP = { sumi: '#16161A', washi: '#ECE9E1', ai: '#165E83', shu: '#D93A2E', lantern: '#F4C97A', aiD: '#0E3F5A', wood: '#3A2A1E', woodD: '#24190F', woodL: '#5C4432' };
const FONT_FILES_PAPER = { caslon: 'LibreCaslonText.ttf', caslonI: 'LibreCaslonText-Italic.ttf', mincho: 'ShipporiMincho.ttf', minchoB: 'ShipporiMincho-ExtraBold.ttf' };
Object.assign(FONT_FILES, FONT_FILES_PAPER);

let PX = null, PXC = null, FIBRE = null, GRAIN = null;
const mkCanvas = (w, h) => { const c = document.createElement('canvas'); c.width = w; c.height = h; return c; };

async function PAPER_INIT() {
  PXC = mkCanvas(W, H); PX = PXC.getContext('2d');
  // washi fibre: long soft fibres + mottling, seeded (stable), used as a multiply texture
  FIBRE = mkCanvas(1024, 1024); const f = FIBRE.getContext('2d'), R = rng(77);
  f.fillStyle = '#808080'; f.fillRect(0, 0, 1024, 1024);
  for (let i = 0; i < 2600; i++) {
    const x = R() * 1024, y = R() * 1024, a = R() * TAU, L = 20 + R() * 120, c = R() > .5 ? 170 : 90;
    f.strokeStyle = `rgba(${c},${c},${c},${.05 + R() * .12})`; f.lineWidth = .6 + R() * 1.4; f.beginPath(); f.moveTo(x, y);
    f.bezierCurveTo(x + Math.cos(a) * L * .3 + (R() - .5) * 20, y + Math.sin(a) * L * .3 + (R() - .5) * 20, x + Math.cos(a) * L * .7, y + Math.sin(a) * L * .7, x + Math.cos(a) * L, y + Math.sin(a) * L); f.stroke();
  }
  const img = f.getImageData(0, 0, 1024, 1024);
  for (let i = 0; i < img.data.length; i += 4) { const x = (i / 4) % 1024, y = Math.floor(i / 4 / 1024); const m = (noise1(x * .013 + y * .011) + noise1(y * .017 - x * .007 + 9)) * 9 + (R() - .5) * 10; img.data[i] += m; img.data[i + 1] += m; img.data[i + 2] += m; }
  f.putImageData(img, 0, 0);
  // make the tile seamless: mirror it into a 2048 tile (every edge meets its own mirror image)
  const M2 = mkCanvas(2048, 2048), m = M2.getContext('2d');
  for (const [sx, sy] of [[1, 1], [-1, 1], [1, -1], [-1, -1]]) { m.save(); m.translate(sx < 0 ? 2048 : 0, sy < 0 ? 2048 : 0); m.scale(sx, sy); m.drawImage(FIBRE, sx < 0 ? 0 : 0, 0); m.restore(); }
  FIBRE = M2;
  // film grain frames (stop-motion flicker)
  GRAIN = Array.from({ length: 4 }, (_, k) => { const g = mkCanvas(512, 512), x = g.getContext('2d'), d = x.createImageData(512, 512), r = rng(k + 3); for (let i = 0; i < d.data.length; i += 4) { const v = 128 + (r() - .5) * 60; d.data[i] = d.data[i + 1] = d.data[i + 2] = v; d.data[i + 3] = 255; } x.putImageData(d, 0, 0); return g; });
}

function texture(alpha = 1, mode = 'multiply', scale = 1) {
  X.save(); X.globalCompositeOperation = mode; X.globalAlpha = alpha;
  X.fillStyle = X.createPattern(FIBRE, 'repeat'); if (scale !== 1) X.fillStyle.setTransform(new DOMMatrix().scale(scale));
  X.fillRect(-W, -H, W * 3, H * 3); X.restore();
}

// ------------------------------------------------------------------ the screen (backlit vellum)
const SCREEN = { rect: [150, 170, 1620, 900], lamp: [1180, 560], power: 1 };   // the lamp: at the actors' head height, over the story (Fable). The window shows y 170-1070: room under the floor (962) for the page strip
function screen(t, o = {}) {
  const [x, y, w, h] = o.rect || SCREEN.rect, [lx, ly] = o.lamp || SCREEN.lamp, pw = (o.power ?? 1) * (1 + .025 * noise1(t * 7.3) + .015 * noise1(t * 19));   // lantern flicker
  X.save();
  X.beginPath(); X.rect(x, y, w, h); X.clip();
  // the lantern's light through vellum: warm, bright at the lamp, falling to dim warm grey at the edges (physical falloff, not a style gradient)
  const g = X.createRadialGradient(lx, ly, 0, lx, ly, Math.max(w, h) * .75 * pw);
  for (const [k, c] of (o.stops || [[0, '#FFF1CF'], [.35, '#F7D99B'], [.75, '#C99A5E'], [1, '#6E5236']])) g.addColorStop(k, c);
  X.fillStyle = g; X.fillRect(x, y, w, h);
  texture(o.tex ?? .55);
  X.restore();
}

// ------------------------------------------------------------------ puppets as shadows
// drawFn draws into PX in screen coordinates: fill black for ink (use ink()), film() for cellophane, hole() to cut.
function shadow(drawFn, depth = 0, o = {}) {
  const [lx, ly] = o.lamp || SCREEN.lamp;
  PX.setTransform(1, 0, 0, 1, 0, 0); PX.globalCompositeOperation = 'source-over'; PX.globalAlpha = 1; PX.filter = 'none'; PX.clearRect(0, 0, W, H);
  drawFn(PX);
  // project: a puppet at depth d (0..1, fraction of the lamp distance) casts a shadow scaled 1/(1-d) about the lamp, blurred by d
  const s = 1 / (1 - clamp(depth, 0, .8) * .5), blur = depth * 26 + .6;
  X.save();
  if (o.clip !== false) { const [x, y, w, h] = o.rect || SCREEN.rect; X.beginPath(); X.rect(x, y, w, h); X.clip(); }
  X.translate(lx, ly); X.scale(s, s); X.translate(-lx, -ly);
  X.globalCompositeOperation = 'multiply'; X.globalAlpha = o.alpha ?? 1;
  if (o.penumbra && depth > .02) {             // an extended lamp: a soft fringe (penumbra) around a crisp dark core (umbra)
    X.filter = `blur(${blur * .8}px)`; X.globalAlpha = (o.alpha ?? 1) * .75; X.drawImage(PXC, 0, 0);
    X.filter = `blur(${.6 + depth * 2}px)`; X.globalAlpha = o.alpha ?? 1; X.drawImage(PXC, 0, 0);
  } else { X.filter = `blur(${blur}px)`; X.drawImage(PXC, 0, 0); }
  X.restore();
}
// inside a shadow drawFn:
const inkP = (c, path, a = 1) => { c.globalCompositeOperation = 'source-over'; c.fillStyle = `rgba(22,22,26,${a})`; c.fill(P(path)); };
const hole = (c, path) => { c.save(); c.globalCompositeOperation = 'destination-out'; c.fillStyle = '#000'; c.fill(P(path)); c.restore(); };
function film(c, path, hex, a = .85) {        // cellophane: coloured light. Punch a hole, then lay the colour (multiplied onto the lit screen)
  c.save(); c.globalCompositeOperation = 'destination-out'; c.fillStyle = '#000'; c.fill(P(path)); c.restore();
  c.save(); c.globalCompositeOperation = 'source-over'; c.globalAlpha = a; c.fillStyle = hex; c.fill(P(path)); c.restore();
}
// cut-paper edge: a subdivided outline with a stable wander + stop-motion boil
function cutp(pts, seed = 0, amp = 1.2, boil = .5, step = 18) {
  const out = [], n = pts.length;
  for (let i = 0; i < n; i++) {
    const a = pts[i], b = pts[(i + 1) % n], L = Math.hypot(b[0] - a[0], b[1] - a[1]), m = Math.max(1, Math.ceil(L / step)), nx = -(b[1] - a[1]) / (L || 1), ny = (b[0] - a[0]) / (L || 1);
    for (let k = 0; k < m; k++) { const u = k / m, d = noise1(seed * 5.1 + (i + u) * 1.7) * amp + jit(seed * 31 + i * 7 + k, boil); out.push([lerp(a[0], b[0], u) + nx * d, lerp(a[1], b[1], u) + ny * d]); }
  }
  return out;
}
// deckle edge (handmade paper): rougher, fibrous
const deckle = (pts, seed) => cutp(pts, seed, 3.2, .8, 7);

// ------------------------------------------------------------------ front-lit cards (kamishibai) and the stage
function card(t, drawFn, o = {}) {
  const [x, y, w, h] = o.rect || SCREEN.rect, off = o.pull || 0;   // pull: slide the card out to the side (hiki-nuki)
  X.save(); X.beginPath(); X.rect(x, y, w, h); X.clip(); X.translate(off, 0);
  X.fillStyle = FP.washi; X.fillRect(x, y, w, h);
  drawFn(X, t);
  texture(.5);
  // lantern from the front-left: warm on one side, falling off (physical light on paper)
  X.globalCompositeOperation = 'multiply'; const g = X.createRadialGradient(x + w * .3, y + h * .2, 0, x + w * .3, y + h * .2, w * 1.1);
  g.addColorStop(0, 'rgba(255,238,205,1)'); g.addColorStop(1, 'rgba(120,96,70,1)'); X.fillStyle = g; X.fillRect(x, y, w, h);
  X.globalCompositeOperation = 'source-over';
  if (off) { X.fillStyle = 'rgba(0,0,0,.35)'; X.fillRect(x + w - 30, y, 30, h); }
  X.restore();
}
function butai(t, o = {}) {
  const [x, y, w, h] = o.rect || SCREEN.rect, fw = 46;
  X.save();
  // frame: four wooden rails with grain and a bevel
  const rail = (rx, ry, rw, rh, seed) => { X.fillStyle = FP.wood; X.fillRect(rx, ry, rw, rh); X.save(); X.beginPath(); X.rect(rx, ry, rw, rh); X.clip();
    const R = rng(seed); for (let i = 0; i < 40; i++) { X.strokeStyle = `rgba(0,0,0,${.12 + R() * .15})`; X.lineWidth = 1 + R() * 2; X.beginPath(); const hz = rw > rh; const p = R(); if (hz) { X.moveTo(rx, ry + p * rh); X.bezierCurveTo(rx + rw * .3, ry + p * rh + (R() - .5) * 10, rx + rw * .6, ry + p * rh + (R() - .5) * 10, rx + rw, ry + p * rh); } else { X.moveTo(rx + p * rw, ry); X.bezierCurveTo(rx + p * rw + (R() - .5) * 10, ry + rh * .3, rx + p * rw + (R() - .5) * 10, ry + rh * .6, rx + p * rw, ry + rh); } X.stroke(); }
    X.fillStyle = 'rgba(255,220,170,.08)'; X.fillRect(rx, ry, rw, 4); X.fillStyle = 'rgba(0,0,0,.35)'; X.fillRect(rx, ry + rh - 4, rw, 4); X.restore(); };
  rail(x - fw, y - fw, w + fw * 2, fw, 1); rail(x - fw, y + h, w + fw * 2, fw, 2); rail(x - fw, y, fw, h, 3); rail(x + w, y, fw, h, 4);
  // doors (open amount 0..1): hinged at the outer edges
  const open = o.doors ?? 1;
  if (open < 1) for (const side of [-1, 1]) { const dw = (w / 2) * (1 - open); const dx = side < 0 ? x : x + w - dw; rail(dx, y, dw, h, 7 + side); }
  X.restore();
}

// ------------------------------------------------------------------ letterpress: type pressed into the page
// Each word appears as the type is pressed (a tiny scale-in + deboss + ink spreading). Horizontal (caslon) or vertical (mincho).
function press(str, x, y, t, t0, o = {}) {
  if (t < t0) return;
  const a = t - t0, sq = a < .06 ? 1.04 - a * .6 : 1, ink = o.wet ? 1 - .16 * clamp(a / .5, 0, 1) : clamp(.55 + a * 3, 0, 1);   // wet: pressed dark, settling lighter
  const L = shape(str, { font: o.font || 'caslon', size: o.size || 58, wght: o.wght || 500 });
  const x0 = o.align === 'center' ? x - L.width / 2 : o.align === 'right' ? x - L.width : x;
  X.save(); X.translate(x0 + L.width / 2, y); X.scale(sq, sq); X.translate(-(x0 + L.width / 2), -y);
  const draw = (dx, dy, col) => { X.fillStyle = col; for (const g of L.glyphs) if (g.ch !== ' ') X.fill(glyphPath(g, x0 + g.x + dx, y + g.y + dy)); };
  if (o.hairline) draw(.6, .7, 'rgba(60,40,20,.28)');     // letterpress: a hairline shadow on one side (Fable), not a bevel
  else { draw(-1, -1.2, 'rgba(255,248,230,.55)');          // the deboss: lit upper-left rim
    draw(1, 1.2, 'rgba(60,40,20,.35)'); }                 // shadowed lower-right rim
  X.globalAlpha = ink; draw(0, 0, o.col || FP.sumi);
  X.restore();
  return L.width;
}
function pressV(str, x, y, t, t0, o = {}) {              // vertical Japanese, top to bottom
  const size = o.size || 46; let yy = y;
  [...str].forEach((ch, i) => { press(ch, x, yy + size, t, t0 + i * (o.stagger ?? .05), { ...o, font: o.font || 'mincho', size, align: 'center' }); yy += size * 1.08; });
}

// ------------------------------------------------------------------ her lantern (the canon's chōchin; FABLE.md: "the only light
// source in my world, and I carry it into other people's"): a barrel of paper on a bamboo spiral, black lacquer caps, a bail
// and a carrying stick. Lit, it's the brightest thing in the frame. In the paper world it's backlit through the vellum, so it
// reads gold (#F4C97A, "backlight through paper; never a surface colour": o.gold); elsewhere its paper is the canon's indigo.
// chochin(): standing on its base at (x, y); o.stick = degrees the carrying stick leans from upright (+ = to the right), or
// null. Returns the stick's free end (or the bail). chochinHang(): hanging from its stick's tip at (tx, ty), swung by `swing`
// degrees. Both return { top, cx, cy } (the stick's end or the bail; the light's centre).
const CHO = { w: 58, h: 88, stick: 1.35 };
function chochinBody(cx, cy, sc, rot, o) {
  const w = CHO.w * sc, h = CHO.h * sc, lit = o.lit ?? 1;
  X.save(); X.translate(cx, cy); X.rotate(rot * Math.PI / 180);
  if (lit > 0 && o.halo !== false) { X.save(); X.globalCompositeOperation = 'lighter'; const R = h * 2.4, g = X.createRadialGradient(0, 0, 0, 0, 0, R);
    g.addColorStop(0, `rgba(244,201,122,${.3 * lit})`); g.addColorStop(1, 'rgba(244,201,122,0)'); X.fillStyle = g; X.fillRect(-R, -R, 2 * R, 2 * R); X.restore(); }
  X.save(); const body = new Path2D(); body.ellipse(0, 0, w / 2, h / 2, 0, 0, 7); X.clip(body);
  const g = X.createRadialGradient(0, h * .08, 0, 0, 0, h * .62);
  if (o.gold) { g.addColorStop(0, '#FFF6E2'); g.addColorStop(.35, '#F4C97A'); g.addColorStop(.75, 'rgb(200,128,58)'); g.addColorStop(1, 'rgb(96,52,24)'); }
  else if (lit > 0) { g.addColorStop(0, '#FFF3D6'); g.addColorStop(.3, '#F4C97A'); g.addColorStop(.72, 'rgb(74,104,172)'); g.addColorStop(1, 'rgb(22,36,80)'); }
  else { g.addColorStop(0, 'rgb(28,40,70)'); g.addColorStop(1, 'rgb(12,18,36)'); }
  X.fillStyle = g; X.fillRect(-w, -h, 2 * w, 2 * h);
  X.strokeStyle = o.gold ? 'rgba(70,36,14,.42)' : 'rgba(10,14,40,.4)'; X.lineWidth = Math.max(1, 1.6 * sc);   // the bamboo ribs, bowed
  for (let k = 1; k < 10; k++) { const yy = -h / 2 + h * k / 10, hw = w / 2 * Math.sqrt(1 - (yy / (h / 2)) ** 2);
    X.beginPath(); X.moveTo(-hw, yy); X.quadraticCurveTo(0, yy + 3 * sc, hw, yy); X.stroke(); }
  X.restore();
  X.fillStyle = 'rgb(12,10,12)';                                                                    // the lacquer caps and the bail
  X.fillRect(-w * .33, -h / 2 - 5 * sc, w * .66, 9 * sc); X.fillRect(-w * .33, h / 2 - 4 * sc, w * .66, 11 * sc);
  X.strokeStyle = 'rgb(12,10,12)'; X.lineWidth = 2.4 * sc; X.beginPath(); X.arc(0, -h / 2 - 5 * sc, w * .2, Math.PI, 0); X.stroke();
  X.restore();
}
function chochin(x, y, sc = 1, o = {}) {
  const h = CHO.h * sc, cx = x, cy = y - 7 * sc - h / 2, bail = [x, cy - h / 2 - 5 * sc - CHO.w * .2 * sc];
  chochinBody(cx, cy, sc, 0, o);
  if (o.stick == null) return { top: bail, cx, cy };
  const a = o.stick * Math.PI / 180, L = CHO.stick * h, top = [bail[0] + Math.sin(a) * L, bail[1] - Math.cos(a) * L];
  X.save(); X.strokeStyle = 'rgb(12,10,12)'; X.lineWidth = 3.2 * sc; X.lineCap = 'round'; X.beginPath(); X.moveTo(...bail); X.lineTo(...top); X.stroke(); X.restore();
  return { top, cx, cy };
}
function chochinHang(fx, fy, dir, sc = 1, o = {}) {                   // from her fist: the stick forward and a little down, the lantern hanging from its tip
  const h = CHO.h * sc, L = CHO.stick * h * (o.len ?? .8), a = (o.stickAngle ?? 28) * Math.PI / 180, tip = [fx + dir * Math.cos(a) * L, fy + Math.sin(a) * L];
  X.save(); X.strokeStyle = 'rgb(12,10,12)'; X.lineWidth = 3.2 * sc; X.lineCap = 'round'; X.beginPath(); X.moveTo(fx, fy); X.lineTo(...tip); X.stroke(); X.restore();
  const sw = (o.swing || 0) * Math.PI / 180, drop = CHO.w * .2 * sc + 5 * sc + h / 2, cx = tip[0] - Math.sin(sw) * drop, cy = tip[1] + Math.cos(sw) * drop;
  chochinBody(cx, cy, sc, o.swing || 0, o);
  return { top: tip, cx, cy };
}
