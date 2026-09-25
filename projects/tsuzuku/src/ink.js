// ink.js: Fable's pen-and-ink cut-ins (FABLE.md §4, register 2): a pen-and-ink drawing printed on washi as two plates, black
// ink and a flat indigo second plate misregistered by a pixel or two; cards that move only as paper moves (a fold's bend,
// a crease highlight, the shadow under a lifted edge); drawn variants (the blink) swapped on twos.
const INK = {};
async function INK_INIT() {
  const load = src => new Promise((ok, no) => { const i = new Image(); i.onload = () => ok(i); i.onerror = () => no(new Error(src)); i.src = src; });
  // plate separation: each pixel = paper x (1 - k) x lerp(1, AI, i); solved from R and B (black darkens all, indigo mostly R)
  const AI = [22 / 255, 94 / 255, 131 / 255];
  const plates = (img, x0 = 0, y0 = 0) => {
    const w = img.width, h = img.height, c = document.createElement('canvas'); c.width = w; c.height = h;
    const g = c.getContext('2d'); g.drawImage(img, 0, 0); const d = g.getImageData(0, 0, w, h), px = d.data;
    const K = new ImageData(w, h), I = new ImageData(w, h), kp = K.data, ip = I.data;
    for (let p = 0; p < px.length; p += 4) {
      const a = px[p + 3] / 255; if (a < .02) continue;
      const R = Math.min(1, px[p] / 250), B = Math.min(1, px[p + 2] / 250);
      let i = 0, k = 1 - B;
      if (B > .03) { const q = R / B; i = Math.max(0, Math.min(1, (1 - q) / ((1 - AI[0]) - (1 - AI[2]) * q))); k = Math.max(0, Math.min(1, 1 - B / (1 - (1 - AI[2]) * i))); }
      kp[p] = 22; kp[p + 1] = 22; kp[p + 2] = 26; kp[p + 3] = 255 * k * a;
      ip[p] = 22; ip[p + 1] = 94; ip[p + 2] = 131; ip[p + 3] = 255 * i * a;
    }
    const mk = D => { const cc = document.createElement('canvas'); cc.width = w; cc.height = h; cc.getContext('2d').putImageData(D, 0, 0); return cc; };
    const M = new ImageData(w, h); for (let p = 0; p < px.length; p += 4) { M.data[p] = M.data[p + 1] = M.data[p + 2] = 255; M.data[p + 3] = px[p + 3]; }
    return { k: mk(K), i: mk(I), m: mk(M), x: x0, y: y0, w, h };                   // m: the patch's own footprint (feathered)
  };
  const card = async (dir, name, varFile) => {
    const base = plates(await load(`${dir}/${name}.png`)), V = {};
    if (varFile) for (const [patch, vs] of Object.entries(await (await fetch(`${dir}/${varFile}`)).json()))
      for (const [vn, e] of Object.entries(vs)) (V[vn] = V[vn] || []).push(plates(await load(`${dir}/build/${e.file}`), e.x, e.y));
    return { base, V };
  };
  INK.closeup = await card('rig/fable_ink', 'closeup', 'build/variants.json');
  INK.lamp = await card('rig/fable_ink', 'lamp');
}
// print a card: washi, then the indigo plate (misregistered), then the ink plate; variant plates printed over their patches
function inkPrint(C, o = {}) {
  const w = C.base.w, h = C.base.h;
  if (!INK._c || INK._c.width !== w) { INK._c = document.createElement('canvas'); INK._c.width = w; INK._c.height = h; }
  const g = INK._c.getContext('2d'); g.setTransform(1, 0, 0, 1, 0, 0); g.globalCompositeOperation = 'source-over'; g.globalAlpha = 1;
  g.fillStyle = '#ECE9E1'; g.fillRect(0, 0, w, h);                              // washi, cool and grey (FABLE.md palette)
  // washi fibre, one tile stretched over the whole card (the 1024 px tile isn't seamless: no repeats inside a card)
  g.globalCompositeOperation = 'multiply'; g.globalAlpha = .22; g.drawImage(FIBRE, 0, 0, w, h); g.globalAlpha = 1;
  const plateSet = [C.base, ...((o.variant && C.V[o.variant]) || [])];
  const [mx, my] = o.misreg || [5, 3];                                            // master px (the card is printed large)
  g.globalCompositeOperation = 'multiply'; g.drawImage(C.base.i, mx, my); g.drawImage(C.base.k, 0, 0);
  // a variant patch REPLACES what's under it: fresh washi (fibre and all) through its footprint, then its own plates
  for (const P of plateSet.slice(1)) {
    if (!INK._p || INK._p.width < P.w || INK._p.height < P.h) { INK._p = document.createElement('canvas'); INK._p.width = Math.max(P.w, 64); INK._p.height = Math.max(P.h, 64); }
    const q = INK._p.getContext('2d'); q.setTransform(1, 0, 0, 1, 0, 0); q.globalCompositeOperation = 'source-over'; q.globalAlpha = 1; q.clearRect(0, 0, INK._p.width, INK._p.height);
    q.fillStyle = '#ECE9E1'; q.fillRect(0, 0, P.w, P.h);
    q.globalCompositeOperation = 'multiply'; q.globalAlpha = .22; q.drawImage(FIBRE, -P.x, -P.y, w, h); q.globalAlpha = 1;
    q.globalCompositeOperation = 'multiply'; q.drawImage(P.i, mx, my); q.drawImage(P.k, 0, 0);
    q.globalCompositeOperation = 'destination-in'; q.drawImage(P.m, 0, 0);
    g.globalCompositeOperation = 'source-over'; g.drawImage(INK._p, 0, 0, P.w, P.h, P.x, P.y, P.w, P.h);
  }
  for (const [x, y, r] of o.rivets || []) {                                      // brass pins, drawn in ink: a ring, a dot of highlight
    g.globalCompositeOperation = 'source-over'; g.fillStyle = '#ECE9E1'; g.beginPath(); g.arc(x, y, r, 0, 7); g.fill();
    g.strokeStyle = 'rgb(22,22,26)'; g.lineWidth = r * .32; g.stroke();
    g.fillStyle = 'rgb(22,22,26)'; g.beginPath(); g.arc(x + r * .18, y + r * .18, r * .32, 0, 7); g.fill();
  }
  return INK._c;
}
{
  // B5, the bridge close-up (song 156.2-159.5): "...I didn't know this one." Held; the camera approaches the card (the grain
  // grows); on "I didn't" the paper bends back along a fold under her chin (the smallest head movement, as paper); after the
  // line, one blink (half, closed, half, on twos); the fold settles.
  const S0 = 156.2, S1 = 159.53, LINE = 157.21, BLINK = 158.55, TH = 7;
  // the fold snaps in over two drawings (no ease), holds; after the blink it springs back 80% and stays faintly creased
  const bend = s => { if (s < LINE) return 0; const d = Math.floor((s - LINE) * 12 + 1e-6); if (d === 0) return TH * .5;
    if (s < BLINK + .5) return TH; const e = Math.floor((s - BLINK - .5) * 12 + 1e-6); return e === 0 ? TH * .55 : TH * .2; };
  LOOPS.inkcloseup = t => {
    const s = S0 + Math.floor(t * 12 + 1e-6) / 12, sc = S0 + t;               // the card on twos; the camera on ones
    const d = Math.round((s - BLINK) * 12), variant = d === 0 || d === 2 ? 'half' : d === 1 ? 'closed' : null;
    const src = inkPrint(INK.closeup, { variant });
    X.fillStyle = '#0d0b0a'; X.fillRect(0, 0, W, H);
    // the camera approaches the card (the grain grows), ending tight on her eyes so the quotation marks read
    const a = Math.min(1, (sc - S0) / (S1 - S0)), e = a * a * (3 - 2 * a), zoom = 1 + 1.35 * e;
    const CH = 1060 * zoom, CW = CH * src.width / src.height, fu = .5 + (.535 - .5) * e, fv = .5 + (.345 - .5) * e;
    const cx = W / 2 - (fu - .5) * CW, cy = H / 2 + 8 - (fv - .5) * CH;
    const FOLD = .72, th = bend(s) * Math.PI / 180;
    const map = (u, v) => { let y = v; if (v < FOLD) y = FOLD - (FOLD - v) * Math.cos(th);
      const xL = (u - .5) * (1 - .018 * Math.sin(th) * (FOLD - Math.min(v, FOLD)) / FOLD); return [cx + xL * CW, cy + (y - .5) * CH]; };
    X.save(); X.filter = 'blur(18px)'; X.fillStyle = 'rgba(0,0,0,.7)'; X.fillRect(cx - CW / 2 + 14, cy - CH / 2 + 22, CW, CH); X.restore();
    WARP.draw(X, src, map, { cols: 32, rows: 48, shade: (u, v) => v < FOLD ? 1 + .6 * Math.sin(th) * (v / FOLD) ** 3 : 1 });
    if (th > 0) {                                                                // the crease: a ridge line, highlight above and shadow below
      const [x0, yf] = map(0, FOLD), [x1] = map(1, FOLD), k = Math.min(1, Math.sin(th) / Math.sin(TH * Math.PI / 180));
      X.save(); X.globalAlpha = .18 + .55 * k; X.fillStyle = 'rgba(255,255,250,.9)'; X.fillRect(x0, yf - 2.5 * zoom, x1 - x0, 1.6 * zoom);
      X.fillStyle = 'rgba(60,55,50,.55)'; X.fillRect(x0, yf, x1 - x0, 2.2 * zoom); X.restore();
    }
    // lamplight: near neutral on this card (the washi stays cool), a gentle falloff to its edges
    X.save(); X.globalCompositeOperation = 'multiply'; const lg = X.createRadialGradient(W / 2, H / 2 - 40, 100, W / 2, H / 2, W * .7);
    lg.addColorStop(0, '#FFFFFF'); lg.addColorStop(.7, '#EDEBE6'); lg.addColorStop(1, '#BDB6AA'); X.fillStyle = lg; X.fillRect(0, 0, W, H); X.restore();
    X.save(); X.globalCompositeOperation = 'overlay'; X.globalAlpha = .14; X.fillStyle = X.createPattern(GRAIN[Math.floor(s * 12) % 4], 'repeat'); X.fillRect(0, 0, W, H); X.restore();
  };
  LOOPS.inkcloseup.len = S1 - S0;
}

{
  // C2, the lamp-lighting (song 9.0-12.7): black; 'Mukashi, mukashi...' in the dark; the match strikes (a flare of two
  // drawings, then a small flame light); on the crowd's 'ARU TOKORO NI!' the lantern lights: warm light blooms across the card
  // over three drawings, the lantern paper glowing from inside. The card breathes (a faint bend) once it's lit.
  const S0 = 9.0, S1 = 12.7, MATCH = 10.25, LAMP = 11.44;
  const FLAME = [1975, 1012], LANTERN = [2050, 1500];
  LOOPS.inklamp = t => {
    const s = S0 + Math.floor(t * 12 + 1e-6) / 12, src = inkPrint(INK.lamp, { misreg: [6, 4], rivets: [[1500, 1265, 17]] });
    X.fillStyle = '#050404'; X.fillRect(0, 0, W, H);
    const CW = W * 1.02, CH = CW * src.height / src.width, cx = W / 2, cy = H / 2, k = CW / src.width;
    const at = ([x, y]) => [cx + (x - src.width / 2) * k, cy + (y - src.height / 2) * k];
    const lit = Math.min(1, Math.max(0, Math.floor((s - LAMP) * 12 + 1e-6) + 1) / 3);   // 0, then 1/3, 2/3, 1 over three drawings
    const br = lit > 0 ? .8 * Math.sin(Math.PI * Math.min(1, (s - LAMP) / 2.4)) * .05 : 0;
    WARP.draw(X, src, (u, v) => [cx + (u - .5) * CW * (1 - br * v * .3), cy + (v - .5) * CH]);
    // the light map: darkness, plus the match and the lantern (additive), multiplied onto the card
    if (!INK._L) { INK._L = document.createElement('canvas'); INK._L.width = W; INK._L.height = H; }
    const L = INK._L.getContext('2d'); L.globalCompositeOperation = 'source-over'; L.fillStyle = 'rgb(4,3,3)'; L.fillRect(0, 0, W, H);
    L.globalCompositeOperation = 'lighter';
    const glow = ([x, y], r, col, a) => { const g = L.createRadialGradient(x, y, 0, x, y, r); g.addColorStop(0, col.replace('A', a)); g.addColorStop(1, col.replace('A', 0)); L.fillStyle = g; L.fillRect(x - r, y - r, 2 * r, 2 * r); };
    const dm = s - MATCH;
    if (dm >= 0) {                                                             // the match: a flare, then a small steady flame light
      const f = Math.floor(dm * 12 + 1e-6);
      glow(at(FLAME), (f < 2 ? 420 : 280) * (1 - .5 * lit), 'rgba(255,186,105,A)', f < 2 ? 1 : .45 + .06 * Math.sin(s * 23));
    }
    if (lit > 0) { glow(at(LANTERN), 1650 * k * (.55 + .45 * lit), 'rgba(255,200,132,A)', lit); glow(at(LANTERN), 760 * k, 'rgba(244,201,122,A)', lit * .8); }
    X.save(); X.globalCompositeOperation = 'multiply'; X.drawImage(INK._L, 0, 0); X.restore();
    if (lit > 0) {                                                             // the lantern's paper, glowing from inside
      X.save(); X.globalCompositeOperation = 'screen'; const [lx, ly] = at(LANTERN), g = X.createRadialGradient(lx, ly, 0, lx, ly, 440 * k);
      g.addColorStop(0, `rgba(244,201,122,${.2 * lit})`); g.addColorStop(1, 'rgba(244,201,122,0)');   // Lantern #F4C97A, capped: the ribs stay X.fillStyle = g; X.fillRect(lx - 460 * k, ly - 460 * k, 920 * k, 920 * k); X.restore();
    }
    X.save(); X.globalCompositeOperation = 'overlay'; X.globalAlpha = .14; X.fillStyle = X.createPattern(GRAIN[Math.floor(s * 12) % 4], 'repeat'); X.fillRect(0, 0, W, H); X.restore();
  };
  LOOPS.inklamp.len = S1 - S0;
}
