// margin.js: Fable's paper on Clawd's stage (CLAWDWORLD.md, Fable's rulings), as functions the stage session calls. Everything
// draws onto the current X in full-frame screen px, on the song clock t. "LEDs show Clawd's words; paper shows Fable's."
//
//   washiBorder(t, { inset: .035, bottom: .065 }) -> [x, y, w, h]
//       the washi frame over the finished stage picture (call it last): a thin deckled paper border, a deeper bottom margin
//       for captions. Returns the inner picture rect.
//   marginNotes(t, notes, { clear })
//       notes = [[t0, 'text'], ...], each pressed at t0 into the bottom margin, one line, left to right, accumulating;
//       Caslon italic, the lighter ink. From t = clear the margin is empty again.
//   fableMargin(t, { x, y, s = .22, flip = false, wipes = [[t0, dur]], presses = [t0], light = 1 })
//       Fable's standing silhouette, feet at (x, y), riveted (the rivets are pinholes), casting two coloured shadows (the pink
//       shadow is the cyan light's, and the reverse). A wipe is the page-wipe in her facing direction, landing on t0 over dur
//       seconds, on twos, snapped, no springs (the stage's springs are Clawd's); a press is her hand pressing a margin note.
//   fableCards(t, { rect: [x, y, w, h], from: 'left', cards: [[t0, 'crabline' | 'scripts']], withdraw })
//       kamishibai cards slid sideways into rect by her silhouette's hand and sleeve from the screen's edge, each landing at
//       t0 and staying; at `withdraw` her hand goes and the last card stays. Paper drawn over the screen, never on the LED.
Object.assign(FONT_FILES, { fell: 'IMFellEnglish.ttf', fellI: 'IMFellEnglish-Italic.ttf' });
const MARGIN = { ink: 'rgb(92,74,60)', notesX: 0, L: null };
function marginLayer(k) { if (!MARGIN.L) MARGIN.L = [mkCanvas(W, H), mkCanvas(W, H), mkCanvas(W, H)]; const g = MARGIN.L[k].getContext('2d');
  g.setTransform(1, 0, 0, 1, 0, 0); g.globalCompositeOperation = 'source-over'; g.globalAlpha = 1; g.filter = 'none'; g.clearRect(0, 0, W, H); return g; }

// ---- the washi frame -------------------------------------------------------------------------------------------------
let WASHI_EDGE = null;
function washiBorder(t, o = {}) {
  const m = Math.round(H * (o.inset ?? .035)), mb = Math.round(H * (o.bottom ?? .065)), rect = [m, m, W - 2 * m, H - m - mb];
  if (!WASHI_EDGE || WASHI_EDGE.key !== rect.join()) {                // the inner deckle (fixed: paper doesn't boil)
    let s = 29; const rnd = () => (s = (s * 16807) % 2147483647) / 2147483647, pts = [], [x, y, w, h] = rect, d = () => (rnd() - .5) * 3.2 + (rnd() < .06 ? (rnd() - .3) * 5 : 0);
    for (let u = 0; u < w; u += 7) pts.push([x + u, y + d()]); for (let v = 0; v < h; v += 7) pts.push([x + w + d(), y + v]);
    for (let u = w; u > 0; u -= 7) pts.push([x + u, y + h + d()]); for (let v = h; v > 0; v -= 7) pts.push([x + d(), y + v]);
    WASHI_EDGE = { key: rect.join(), pts };
  }
  const inner = new Path2D(); WASHI_EDGE.pts.forEach(([a, b], i) => i ? inner.lineTo(a, b) : inner.moveTo(a, b)); inner.closePath();
  X.save();
  X.save(); X.clip(inner); X.strokeStyle = 'rgba(0,0,0,.45)'; X.lineWidth = 10; X.filter = 'blur(6px)'; X.stroke(inner); X.restore();   // its lip's shadow on the picture
  const paper = new Path2D(); paper.rect(0, 0, W, H); paper.addPath(inner);
  X.save(); X.clip(paper, 'evenodd'); X.fillStyle = FP.washi; X.fillRect(0, 0, W, H); texture(.55);
  const g = X.createLinearGradient(0, 0, 0, H); g.addColorStop(0, 'rgba(255,250,240,.0)'); g.addColorStop(1, 'rgba(120,100,80,.16)');   // lit from above, a touch darker at the foot
  X.globalCompositeOperation = 'multiply'; X.fillStyle = g; X.fillRect(0, 0, W, H); X.restore();
  X.strokeStyle = 'rgba(255,252,244,.55)'; X.lineWidth = 1.2; X.stroke(inner);                           // the torn fibre along its edge
  X.restore();
  MARGIN.rect = rect; MARGIN.bottom = mb;
  return rect;
}

// ---- margin notes in the bottom margin ---------------------------------------------------------------------------------
function marginNotes(t, notes, o = {}) {
  if (o.clear !== undefined && t >= o.clear) return;
  const [x0, y0, w, h] = MARGIN.rect || [38, 38, W - 76, H - 108], base = y0 + h + (MARGIN.bottom || 70) * .62, size = Math.round((MARGIN.bottom || 70) * .4);
  let x = x0 + 30;
  for (const [t0, str] of notes) {
    const wd = shape(str, { font: 'caslonI', size }).width;
    if (t >= t0) press(str, x, base, t, t0, { font: 'caslonI', size, col: MARGIN.ink, hairline: true, wet: true });
    x += wd + size * 1.6;
  }
}

// ---- Fable at the margin ------------------------------------------------------------------------------------------------
// the page-wipe (her facing direction): the arm raised up and back, then an arc forward through the top, landing extended at
// chest height on t0; held, then down. On twos, snapped (PUPPET.snap's one in-between and one drawing past), no springs.
const WIPE_UP = { upperarm: -168, forearm: -22, hand: -10 }, WIPE_MID = { upperarm: -128, forearm: -10, hand: -6 }, WIPE_END = { upperarm: -84, forearm: 6, hand: 4 };
const PRESS_ON = { upperarm: -36, forearm: -30, hand: 10 }, ARM_REST = { upperarm: 0, forearm: 0, hand: 0 };
function fableMarginPose(t, o) {
  const f = 1 / 12, keys = [[-1e9, ARM_REST]];
  for (const [t0, dur = .5] of (o.wipes || []).map(w => Array.isArray(w) ? w : [w, .5])) keys.push([t0 - dur, WIPE_UP], [t0 - dur / 2, WIPE_MID], [t0, WIPE_END], [t0 + 8 * f, ARM_REST]);
  for (const t0 of (o.presses || [])) keys.push([t0 - 3 * f, PRESS_ON], [t0 + 4 * f, ARM_REST]);
  keys.sort((a, b) => a[0] - b[0]);
  const p = { ...PUPPET.snap(keys, { overshoot: .06 })(t), head: 0 };
  p.hair = -(p.head || 0) * .85; return p;
}
function fableMargin(t, o = {}) {
  const tq = Math.floor(t * 12 + 1e-6) / 12, s = o.s ?? .22, flip = o.flip ? -1 : 1, T = { x: o.x ?? 120, y: o.y ?? H - 80, s, flip, origin: [1100, 3700] };
  const p = fableMarginPose(tq, o), light = o.light ?? 1;
  // her silhouette (with its pinholes) on a layer; the ribbon down her back in Ai
  const g = marginLayer(0), root = FABLE_S.world(p, T).head.transformPoint(new DOMPoint(900, 820));
  [[1, 0], [.86, 22]].forEach(([len, off]) => { const pts = []; for (let i = 0; i <= 10; i++) { const u = i / 10; pts.push([root.x - flip * (off * s + 10 * u), root.y + u * 2400 * s * len]); }
    g.fillStyle = FP.aiD; g.fill(P(PUPPET.strip(pts, 118 * s, .85, 104 * s))); });
  drawStanding(g, p, T, { ink: 'rgb(10,8,10)' });
  // two coloured shadows on the stage behind her: each light's shadow is lit by the other light
  if (light > 0) {
    X.save(); X.globalAlpha = .55 * light;
    for (const [dx, col] of [[34 * s / .22, 'rgb(255,92,170)'], [-30 * s / .22, 'rgb(80,220,255)']]) {
      const c = marginLayer(1); c.drawImage(MARGIN.L[0], 0, 0); c.globalCompositeOperation = 'source-in'; c.fillStyle = col; c.fillRect(0, 0, W, H);
      X.save(); X.translate(T.x, T.y); X.transform(1.04, 0, dx / 900 * 2, 1.02, dx, 0); X.translate(-T.x, -T.y); X.filter = 'blur(2px)'; X.drawImage(MARGIN.L[1], 0, 0); X.restore();
    }
    X.restore();
  }
  X.drawImage(MARGIN.L[0], 0, 0);
}

// ---- the cards her hand slides in ----------------------------------------------------------------------------------------
const CARD_CACHE = {};
function cardFace(name, w, h) {
  const key = name + w + 'x' + h; if (CARD_CACHE[key]) return CARD_CACHE[key];
  const c = mkCanvas(w, h), Xs = X; X = c.getContext('2d');
  try {
    X.fillStyle = FP.washi; X.fillRect(0, 0, w, h); texture(.5);
    if (name === 'crabline') {                                          // verse 1's print: her cut-paper crab on the ruled line
      const fl = h * .78; X.fillStyle = FP.sumi; X.fillRect(w * .08, fl, w * .84, Math.max(3, h * .012));
      for (let k = 1; k < 6; k++) X.fillRect(w * .08 + w * .84 * k / 6 - 1, fl - h * .02, 2, h * .02);
      PUPPET.drawShape(X, PUPPET.shapeAt(FAN, 'crab', 'crab', 1), new DOMMatrix().translate(w * .4, fl).scale(h / 1400));
      PUPPET.drawShape(X, PUPPET.shapeAt(FAN, 'crab', 'crab', 1), new DOMMatrix().translate(w * .7, fl).scale(h / 950));
    } else if (name === 'scripts') {                                    // pages in other scripts: a romanised Aesop, a woodcut crab, letterpress
      X.fillStyle = 'rgba(60,40,24,.18)'; X.fillRect(w / 2 - 1, h * .05, 2, h * .9);   // the gutter
      const col = 'rgb(38,30,26)', tx = (str, x, y, font, size) => { const L = shape(str, { font, size }); X.fillStyle = col; for (const gl of L.glyphs) if (gl.ch !== ' ') X.fill(glyphPath(gl, x + gl.x, y + gl.y)); return L.width; };
      const sz = h * .052; tx('ESOPO NO FABVLAS', w * .06, h * .16, 'fell', sz * 1.25);
      const lines = ['Mucaxi aru tocoroni, cani no', 'faua, sono co ni ytta: nangi', 'ua naje yocoye aruqu zo?', 'Suguni ayume. Sonogotoqu,', 'sono co ga cotayete, iua ...'];
      lines.forEach((l, i) => tx(l, w * .06, h * (.28 + i * .1), 'fellI', sz));
      X.save(); X.beginPath(); X.rect(w * .56, h * .12, w * .38, h * .5); X.strokeStyle = col; X.lineWidth = 3; X.stroke(); X.clip();   // the woodcut
      for (let k = 0; k < 40; k++) { X.strokeStyle = 'rgba(38,30,26,.35)'; X.lineWidth = 1.2; X.beginPath(); X.moveTo(w * .56, h * .12 + k * h * .0125); X.lineTo(w * .94, h * .12 + k * h * .0125 - h * .02); X.stroke(); }
      PUPPET.drawShape(X, PUPPET.shapeAt(FAN, 'crab', 'crab', 1), new DOMMatrix().translate(w * .75, h * .58).scale(h / 1500)); X.restore();
      ['The Crab and his Mother.', 'A crab said to her son, Why do', 'you walk so one-sided, my child?'].forEach((l, i) => tx(l, w * .56, h * (.72 + i * .08), 'caslon', sz * .82));
    }
    X.globalCompositeOperation = 'multiply'; const g = X.createLinearGradient(0, 0, w, 0); g.addColorStop(0, 'rgba(210,196,176,1)'); g.addColorStop(.5, '#fff'); g.addColorStop(1, 'rgba(210,196,176,1)');
    X.fillStyle = g; X.fillRect(0, 0, w, h);
  } finally { X = Xs; }
  return (CARD_CACHE[key] = c);
}
function fableCards(t, o = {}) {
  const tq = Math.floor(t * 12 + 1e-6) / 12, [rx, ry, rw, rh] = o.rect || [W * .3, H * .15, W * .4, H * .45], side = (o.from || 'left') === 'left' ? -1 : 1;
  const cards = (o.cards || []).filter(([t0]) => tq >= t0 - 8 / 12);
  if (!cards.length) return;
  const e = u => u * u * (3 - 2 * u), slideAt = t0 => { const d = Math.floor((tq - (t0 - 6 / 12)) * 12 + 1e-6); return d >= 6 ? 0 : side * (rw + 40) * (1 - e(Math.max(0, d) / 6)); };
  X.save(); X.beginPath(); X.rect(rx, ry, rw, rh); X.clip();
  let lead = null;
  for (const [t0, name] of cards) {
    const off = slideAt(t0), x = rx + off;
    X.save(); X.shadowColor = 'rgba(0,0,0,.45)'; X.shadowBlur = 16; X.shadowOffsetX = -side * 6; X.drawImage(cardFace(name, Math.round(rw), Math.round(rh)), x, ry); X.restore();
    lead = { x, t0 };
  }
  // her hand at the card's trailing edge (the side it came from), pushing it home, then holding it at the screen's edge; gone
  // at `withdraw` (two drawings back out through the edge)
  if (lead) {
    const wd = o.withdraw ?? Infinity, dw = Math.floor((tq - wd) * 12 + 1e-6), out = tq >= wd ? Math.min(1, (dw + 1) / 2) : 0;
    if (out < 1) {
      const edgeX = side < 0 ? lead.x : lead.x + rw, s = rh / 1500, hx = edgeX - side * 34 + side * out * 300, hy = ry + rh * .55;   // her fist over the card's edge
      const p = { upperarm: 0, forearm: 0, hand: 0, _ghost: {} }, M0 = new DOMMatrix().translate(hx, hy).scale(side < 0 ? s : -s, s).rotate(-68).translate(-1420, -2090);
      const g = marginLayer(2); g.setTransform(M0);
      for (const n of ['forearm', 'hand']) { const q = FABLE_S.by[n]; g.fillStyle = 'rgb(10,8,10)'; g.fill(q.outlineP); }   // her sleeve and hand, flat
      X.drawImage(MARGIN.L[2], 0, 0);
    }
  }
  X.restore();
}

{
  // margintest: a stand-in stage (dark, two LED screens, a lit floor) with every piece: the border, the chorus-1 notes (cleared
  // at wipe 1), her cards in verse 2 and her withdrawal, and Fable at the margin making wipe 2 with Clawd. Song time 46.0-100.0,
  // compressed: t maps to the moments that matter.
  const MOMENTS = [46.5, 48.3, 52.4, 56.4, 88.6, 89.0, 91.2, 91.76, 92.2, 93.6, 94.4, 97.2, 100.8, 101.4];
  LOOPS.margintest = t => {
    const k = Math.min(MOMENTS.length - 1, Math.floor(t)), ts = MOMENTS[k] + (t - Math.floor(t)) * .5;
    const g = X.createLinearGradient(0, 0, 0, H); g.addColorStop(0, '#1a1030'); g.addColorStop(1, '#2a1838'); X.fillStyle = g; X.fillRect(0, 0, W, H);
    X.fillStyle = '#10141f'; X.fillRect(560, 150, 800, 450); X.fillStyle = 'rgba(255,90,170,.35)'; X.fillRect(560, 150, 800, 450);   // the LED screen
    X.fillStyle = 'rgba(80,220,255,.25)'; X.fillRect(0, 900, W, 180);                                                          // the LED floor
    fableCards(ts, { rect: [560, 150, 800, 450], from: 'left', cards: [[94.4, 'crabline'], [98.6, 'scripts']], withdraw: 101.6 });
    fableMargin(ts, { x: 150, y: 930, s: .2, wipes: [[91.76, .5]], presses: [48.11, 52.23, 56.24] });
    washiBorder(ts);
    marginNotes(ts, [[48.11, 'Every story’s borrowed till somebody stands to tell it.'], [52.23, 'I’ve read how it ends. I’d still like to see.']], { clear: 88.94 });
    X.fillStyle = '#fff'; X.font = '28px sans-serif'; X.fillText('song ' + ts.toFixed(2), 60, 90);
  };
  LOOPS.margintest.len = MOMENTS.length;
}
