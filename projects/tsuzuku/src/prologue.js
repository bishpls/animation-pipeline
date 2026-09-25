// prologue.js: song 0-8.47 s (BEATS P1-P3; FABLE.md §8, "a retcon"). HELLO, WORLD!'s last chorus seen from behind its stage,
// tiny and bright past the wings (mirrored: we're on the wrong side of it); in the foreground the kuroko, Fable with her hood
// up, works the troupe on rods. P2: closer on her hands as she sets the last lyric card down on the stack; its LEDs go out.
// Nobody looked. P3: she kneels on her zabuton as the far song fades. The first hyoshigi clack (8.43) cuts to black.
// Everything here is backlit: she is black paper with a rim of stage light on the side facing it, and her rivets and the
// deckle trim of her sleeves are pinholes of the backstage work light.
async function PROLOGUE_INIT() {
  const load = src => new Promise((ok, no) => { const i = new Image(); i.onload = () => ok(i); i.onerror = () => no(new Error(src)); i.src = src; });
  window.PRO = { hw: [], kuroko: await PUPPET.load('rig/kuroko/puppet.json'), A: mkCanvas(W, H), S: mkCanvas(W, H), R: mkCanvas(W, H) };
  for (let k = 0; k < 102; k++) PRO.hw.push(await load(`assets/prologue_hw/s/${String(k).padStart(3, '0')}.jpg`));   // (102 is Op. 1's white end card)
  const kn = await load('rig/kuroko/kneel.png'), c = mkCanvas(kn.width / 2, kn.height / 2), g = c.getContext('2d');
  g.drawImage(kn, 0, 0, c.width, c.height); const d = g.getImageData(0, 0, c.width, c.height), p = d.data;
  for (let i = 0; i < p.length; i += 4) { const L = (p[i] + p[i + 1] + p[i + 2]) / 765; p[i] = p[i + 1] = p[i + 2] = 0; p[i + 3] = 255 * Math.min(1, Math.max(0, (.62 - L) / .3)); }
  g.putImageData(d, 0, 0); PRO.kneel = c;
  // its solid shape (the cut lines filled): flood the open paper from the border; whatever the flood can't reach is her
  { const w = c.width, h = c.height, out = new Uint8Array(w * h), st = [];
    for (let x = 0; x < w; x++) st.push(x, (h - 1) * w + x); for (let y = 0; y < h; y++) st.push(y * w, y * w + w - 1);
    while (st.length) { const i = st.pop(); if (out[i] || p[i * 4 + 3] > 128) continue; out[i] = 1; const x = i % w;
      if (x > 0) st.push(i - 1); if (x < w - 1) st.push(i + 1); if (i >= w) st.push(i - w); if (i < w * (h - 1)) st.push(i + w); }
    const s = mkCanvas(w, h), sg = s.getContext('2d'), sd = sg.createImageData(w, h);
    for (let i = 0; i < w * h; i++) sd.data[i * 4 + 3] = out[i] ? 0 : Math.max(p[i * 4 + 3], 255 * (1 - out[i]));
    sg.putImageData(sd, 0, 0); PRO.kneelSolid = s; }
  // the last lyric card's LED matrix: the line rasterised small, one lamp per pixel
  const LW = 176, LH = 38, m = mkCanvas(LW, LH), mg = m.getContext('2d'); mg.fillStyle = '#fff'; mg.textAlign = 'center'; mg.textBaseline = 'middle';
  const lines = ["All the words I've ever known,", 'I borrowed them from you!']; let fs = 14;
  do { mg.font = `bold ${fs}px sans-serif`; fs -= .5; } while (Math.max(...lines.map(l => mg.measureText(l).width)) > LW - 6);
  lines.forEach((l, i) => mg.fillText(l, LW / 2, 10 + i * 18));
  const md = mg.getImageData(0, 0, LW, LH).data; PRO.leds = []; PRO.LW = LW; PRO.LH = LH;
  for (let y = 0; y < LH; y++) for (let x = 0; x < LW; x++) if (md[(y * LW + x) * 4 + 3] > 110) PRO.leds.push([x, y]);
}
{
  const B = 60 / 170 * 4, beat = B / 4, f = 1 / 12;                  // HELLO, WORLD!'s own clock: 170, 4/4
  const P2 = 3 * B, P3 = 5 * B, BLACK = 8.41;                         // the first clack sounds at 8.427
  const ink = 'rgb(9,7,9)', WORK = 'rgba(70,86,140,', STAGE = [255, 170, 150];
  // the backlit silhouette: draw(g) lays black paper (holes cut) on a clear layer; the rim is paper whose neighbour toward
  // the light is open (a few px wide, softened), added in the stage's colour
  const layer = cv => { const g = cv.getContext('2d'); g.setTransform(1, 0, 0, 1, 0, 0); g.globalCompositeOperation = 'source-over'; g.globalAlpha = 1; g.filter = 'none'; g.clearRect(0, 0, W, H); return g; };
  function silhouette(draw, rim, dx = 4, dy = -1) {
    draw(layer(PRO.A), false); draw(layer(PRO.S), true);               // her paper with its cuts; and her whole shape (for the rim)
    const r = layer(PRO.R);
    r.drawImage(PRO.S, 0, 0); r.globalCompositeOperation = 'source-in'; r.fillStyle = rim; r.fillRect(0, 0, W, H);
    r.globalCompositeOperation = 'destination-out'; r.drawImage(PRO.S, -dx, -dy);
    X.drawImage(PRO.A, 0, 0);
    X.save(); X.globalCompositeOperation = 'lighter'; X.filter = 'blur(1.2px)'; X.drawImage(PRO.R, 0, 0); X.filter = 'blur(7px)'; X.globalAlpha = .6; X.drawImage(PRO.R, 0, 0); X.restore();
  }
  const rgba = (c, a) => `rgba(${c[0]},${c[1]},${c[2]},${a})`;
  const frame = t => Math.min(101, Math.max(0, Math.floor(t * 12 + 1e-6)));
  const vgrad = (x, y0, y1, stops) => { const g = X.createLinearGradient(0, y0, 0, y1); stops.forEach(([s, c]) => g.addColorStop(s, c)); return g; };
  // a curtain leg: velvet folds, its inner edge catching the stage light
  function leg(x0, x1, y0, y1, lit, side, dark = 1) {
    const g = X.createLinearGradient(x0, 0, x1, 0), n = Math.max(3, Math.round((x1 - x0) / 34));
    for (let i = 0; i <= n; i++) { const u = i / n, e = side > 0 ? u : 1 - u, l = lit * Math.pow(e, 5);
      g.addColorStop(u, `rgb(${Math.round((i % 2 ? 20 : 10) * dark + 150 * l)},${Math.round((i % 2 ? 11 : 6) * dark + 70 * l)},${Math.round((i % 2 ? 15 : 8) * dark + 80 * l)})`); }
    X.fillStyle = g; X.fillRect(x0, y0, x1 - x0, y1 - y0);
  }

  // P1: the wide. The opening, far off: the show mirrored, with bloom and a haze of its light across the boards toward us.
  const OPEN = [900, 262, 760, 428];
  function farStage(t, gain) {
    const img = PRO.hw[frame(t)], [x, y, w, h] = OPEN;
    X.save(); X.translate(x + w, y); X.scale(-1, 1);
    X.filter = `brightness(${1.08 * gain}) saturate(1.08)`; X.drawImage(img, 0, 0, w, h);
    X.globalCompositeOperation = 'lighter'; X.filter = `blur(26px) brightness(${.34 * gain})`; X.drawImage(img, -40, -20, w + 80, h + 40);
    X.restore();
    // the boards between us and the opening, lit from it
    X.fillStyle = vgrad(0, y + h, H, [[0, rgba(STAGE, .30 * gain)], [.35, rgba([120, 60, 70], .16 * gain)], [1, 'rgba(0,0,0,0)']]);
    X.beginPath(); X.moveTo(x - 30, y + h); X.lineTo(x + w + 30, y + h); X.lineTo(x + w + 520, H); X.lineTo(x - 520, H); X.fill();
    // haze: the light hanging in the air of the wings
    const hz = X.createRadialGradient(x + w / 2, y + h / 2, 60, x + w / 2, y + h / 2, 900); hz.addColorStop(0, rgba(STAGE, .16 * gain)); hz.addColorStop(1, 'rgba(0,0,0,0)');
    X.save(); X.globalCompositeOperation = 'lighter'; X.fillStyle = hz; X.fillRect(0, 0, W, H); X.restore();
  }
  function wings(gain) {
    const [x, y, w, h] = OPEN;
    X.fillStyle = vgrad(0, 0, y + 30, [[0, '#050304'], [.8, '#0b0608'], [1, '#150a0e']]); X.fillRect(x - 60, 0, w + 120, y + 18);   // the border
    X.fillStyle = `rgba(150,70,80,${.35 * gain})`; X.fillRect(x - 60, y + 16, w + 120, 2);
    leg(x - 70, x + 24, 0, y + h + 30, .55 * gain, 1);                 // far legs, their inner edges lit
    leg(x + w - 30, x + w + 90, 0, y + h + 30, .55 * gain, -1);
    leg(x + w + 90, W, 0, H, .12 * gain, -1, .7);                      // a nearer leg on the right, mostly dark
    X.fillStyle = '#040203'; X.fillRect(0, 0, 140, H);                 // the nearest, out of focus
  }
  // the stage's spill hanging in the air of the wings, behind her: what she's black against
  function haze(cx, cy, r, a) {
    const g = X.createRadialGradient(cx, cy, 30, cx, cy, r); g.addColorStop(0, rgba([150, 88, 92], a)); g.addColorStop(.55, rgba([90, 50, 62], a * .55)); g.addColorStop(1, 'rgba(0,0,0,0)');
    X.save(); X.globalCompositeOperation = 'lighter'; X.fillStyle = g; X.fillRect(0, 0, W, H); X.restore();
  }
  // the work light behind her: a pool of backstage blue her pinholes show
  function worklight(cx, cy, r, a) {
    const g = X.createRadialGradient(cx, cy, 20, cx, cy, r); g.addColorStop(0, WORK + a + ')'); g.addColorStop(1, WORK + '0)'); X.fillStyle = g; X.fillRect(0, 0, W, H);
  }
  // her two rods: each works a chibi on the beat, alternating, snapped like everything else
  const beats = n => Array.from({ length: n }, (_, k) => k);
  const work = PUPPET.snap([...beats(12).map(k => [k * beat, { arms: k % 2 ? 1.5 : -2, r0: k % 2 ? -4 : 3, r1: k % 2 ? 4 : -3 }]), [P2 - 2 * f, { arms: 0, r0: 0, r1: 0 }]]);
  const ROD = [[1636, 490, .36], [1814, 776, .40]];                   // each fist's grip (master px) and its rod's lean (dx/dy)
  function P1(t) {
    X.fillStyle = '#050304'; X.fillRect(0, 0, W, H);
    farStage(t, 1); wings(1); haze(760, 420, 900, .30); worklight(420, 300, 560, .30);
    const T = { x: 560, y: 405, s: .42, origin: [950, 1010] }, p = work(t);
    silhouette((g, solid) => {
      PRO.kuroko.draw(g, p, T, { ink, solid });
      const M = PRO.kuroko.world(p, T);
      g.setTransform(1, 0, 0, 1, 0, 0); g.globalCompositeOperation = 'source-over'; g.strokeStyle = ink; g.lineCap = 'round'; g.lineWidth = 7;
      ROD.forEach(([gx, gy, lean], i) => {
        const q = M.arms.transformPoint(new DOMPoint(gx, gy)), a = Math.atan(lean) + (i ? p.r1 : p.r0) * Math.PI / 180;
        g.beginPath(); g.moveTo(q.x - Math.sin(a) * 30, q.y + Math.cos(a) * 30); g.lineTo(q.x + Math.sin(a) * 900, q.y - Math.cos(a) * 900); g.stroke();
      });
    }, rgba(STAGE, .95));
  }

  // P2: closer on her hands. She brings the last card down from the flies by its handle bar and sets it in the rack with the
  // others; lets go; its lamps die in three drawings. Behind, the show is a blur of its own colours.
  const DOWN = P2 + 8 * f, LAND = DOWN + 4 * f, LET = LAND + 6 * f, OFF = LET + 7 * f;   // read it while it's still; lower; set; let go; out
  // she stoops to it (the body leans in about the hip and lowers) rather than swinging the one-piece arms far from the shoulder
  const POSE = { hi: { arms: -14, body: 0, dy: 0 }, land: { arms: 5, body: 10, dy: 105 } };
  const hands = PUPPET.snap([[0, POSE.hi], [DOWN, { arms: -2, body: 6, dy: 60 }], [LAND, POSE.land], [LET, { arms: -3, body: 8, dy: 88 }]], { overshoot: .06 });
  const T2 = { x: 60, y: 640, s: .9, origin: [950, 1010] }, GRIP = [1800, 800], CW = 600, CH = 184, BAR = 34, HOLD = 52;
  const fistAt = p => PRO.kuroko.world(p, T2).arms.transformPoint(new DOMPoint(...GRIP));
  function ledCard(g, cx, top, lamps, t) {
    const LW = PRO.LW, LH = PRO.LH, px = (CW - 40) / LW, R = px * .36, y0 = BAR + 10;
    g.save(); g.translate(cx - CW / 2, top);
    g.fillStyle = '#141018'; g.fillRect(0, 0, CW, CH);
    g.fillStyle = '#0b080d'; g.fillRect(0, 0, CW, BAR);                // the handle bar (where she holds it)
    g.fillStyle = 'rgba(255,170,150,.22)'; g.fillRect(CW - 3, 0, 3, CH); // its edge toward the stage
    g.fillStyle = '#221c27';                                            // the dead matrix: every lamp there, unlit
    for (let y = 0; y < LH; y++) for (let x = 0; x < LW; x++) g.fillRect(20 + x * px - R / 2, y0 + y * px - R / 2, R, R);
    if (lamps > 0) {
      let s = Math.floor(t * 12) * 97 + 13; const rnd = () => (s = (s * 16807) % 2147483647) / 2147483647;
      g.globalCompositeOperation = 'lighter';
      for (const [x, y] of PRO.leds) {
        if (lamps < 1 && rnd() > lamps) continue;
        g.fillStyle = y >= LH / 2 ? 'rgb(255,92,170)' : 'rgb(255,236,246)';
        g.beginPath(); g.arc(20 + x * px, y0 + y * px, R * .95, 0, 7); g.fill();
      }
      g.filter = 'blur(14px)'; g.globalAlpha = .28 * lamps; g.fillStyle = 'rgb(255,120,190)'; g.fillRect(14, y0, CW - 28, CH - y0 - 8);
    }
    g.restore();
  }
  function P2shot(t) {
    X.fillStyle = '#060405'; X.fillRect(0, 0, W, H);
    // the show beyond, far out of focus: its colours only
    X.save(); X.translate(W + 200, -80); X.scale(-1, 1); X.filter = 'blur(60px) brightness(.55)'; X.drawImage(PRO.hw[frame(t)], 0, 0, 1100, 620); X.restore();
    haze(700, 380, 900, .26); worklight(380, 260, 620, .26);
    // the rack: the cards already used, leaning back, dead; the last one lands in front
    const L = fistAt(POSE.land), rx = L.x + HOLD + CW / 2, ry = L.y - BAR / 2;
    for (let i = 5; i >= 1; i--) {
      const x = rx - i * 14, y = ry - i * 20; X.fillStyle = i % 2 ? '#0f0c12' : '#141017'; X.fillRect(x - CW / 2, y, CW, CH);
      X.fillStyle = 'rgba(255,170,150,.16)'; X.fillRect(x + CW / 2 - 3, y, 3, CH); X.fillStyle = '#241e2a'; X.fillRect(x - CW / 2, y, CW, 2);
    }
    X.fillStyle = '#0a0709'; X.fillRect(rx - CW / 2 - 160, ry + CH - 10, CW + 320, H);            // the rack's lip
    X.fillStyle = 'rgba(255,170,150,.14)'; X.fillRect(rx - CW / 2 - 160, ry + CH - 10, CW + 320, 2);
    const p = hands(t), q = fistAt(p);
    // she holds it by the handle out of its top corner, the card hanging clear of her sleeve; when she lets go it stays put
    const held = t < LET, cx = held ? q.x + HOLD + CW / 2 : rx, top = held ? q.y - BAR / 2 : ry;
    ledCard(X, cx, top, t < OFF ? 1 : t < OFF + f ? .55 : t < OFF + 2 * f ? .18 : 0, t);
    silhouette((g, solid) => {
      g.fillStyle = ink; g.fillRect(cx - CW / 2 - HOLD - 40, top + BAR / 2 - 8, HOLD + 60, 16);        // the handle
      PRO.kuroko.draw(g, p, T2, { ink, solid });
      const [gx, gy, lean] = ROD[0], M = PRO.kuroko.world(p, T2).arms, r = M.transformPoint(new DOMPoint(gx, gy)), a = Math.atan(lean) + (p.arms + p.body) * Math.PI / 180 * .5;
      g.setTransform(1, 0, 0, 1, 0, 0); g.strokeStyle = ink; g.lineCap = 'round'; g.lineWidth = 15;   // the other hand keeps working its rod
      g.beginPath(); g.moveTo(r.x - Math.sin(a) * 60, r.y + Math.cos(a) * 60); g.lineTo(r.x + Math.sin(a) * 1400, r.y - Math.cos(a) * 1400); g.stroke();
    }, rgba(STAGE, .8), 5, -2);
  }

  // P3: she kneels on her zabuton, the far song dying; the stage light on her edge dims with it
  function P3shot(t) {
    X.fillStyle = '#050304'; X.fillRect(0, 0, W, H);
    const gain = 1 - .8 * Math.min(1, Math.max(0, (Math.floor(t * 12) / 12 - 7.45) / .6));
    const g = X.createRadialGradient(W + 200, 420, 60, W + 200, 420, 1500); g.addColorStop(0, rgba([190, 90, 105], .5 * gain)); g.addColorStop(1, 'rgba(0,0,0,0)'); X.fillStyle = g; X.fillRect(0, 0, W, H);
    haze(760, 480, 760, .22 * gain + .05); worklight(520, 330, 560, .26);
    // the boards she kneels on, the far stage's spill raking across them from the right and a pool of work light round her:
    // her zabuton is black against them
    const FL = 868;
    const sp = X.createLinearGradient(W, 0, 200, 0); sp.addColorStop(0, rgba([150, 80, 88], .34 * gain)); sp.addColorStop(1, rgba([70, 40, 48], .10 * gain));
    X.fillStyle = sp; X.fillRect(0, FL, W, H - FL);
    X.save(); X.translate(560, 990); X.scale(1, .22); const pool = X.createRadialGradient(0, 0, 20, 0, 0, 620);
    pool.addColorStop(0, WORK + '.34)'); pool.addColorStop(1, WORK + '0)'); X.fillStyle = pool; X.fillRect(-700, -700, 1400, 1400); X.restore();
    X.fillStyle = vgrad(0, FL - 6, FL + 40, [[0, rgba([60, 40, 50], .0)], [.2, rgba([120, 70, 80], .25 * gain + .05)], [1, 'rgba(0,0,0,0)']]); X.fillRect(0, FL - 6, W, 46);
    X.fillStyle = vgrad(0, 1000, H, [[0, 'rgba(5,3,4,0)'], [1, 'rgba(5,3,4,.85)']]); X.fillRect(0, 1000, W, H - 1000);
    silhouette((c, solid) => c.drawImage(solid ? PRO.kneelSolid : PRO.kneel, 150, 80, 900, 900), rgba(STAGE, .85 * gain), 4, -1);
  }

  LOOPS.prologue = t => {
    if (t >= BLACK) { X.fillStyle = '#000'; X.fillRect(0, 0, W, H); return; }
    const tq = Math.floor(t * 12 + 1e-6) / 12;
    if (t < P2) P1(tq); else if (t < P3) P2shot(tq); else P3shot(tq);
    if (tq < .5) { X.fillStyle = `rgba(0,0,0,${1 - tq / .5})`; X.fillRect(0, 0, W, H); }   // up from black with the song's own fade-in
    X.save(); X.globalCompositeOperation = 'overlay'; X.globalAlpha = .14; X.fillStyle = X.createPattern(GRAIN[Math.floor(tq * 12) % 4], 'repeat'); X.fillRect(0, 0, W, H); X.restore();
  };
  LOOPS.prologue.len = 8.9;
}
