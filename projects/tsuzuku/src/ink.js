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
    return { k: mk(K), i: mk(I), x: x0, y: y0, w, h };
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
  g.fillStyle = '#EDE7DA'; g.fillRect(0, 0, w, h);
  // washi fibre, one tile stretched over the whole card (the 1024 px tile isn't seamless: no repeats inside a card)
  g.globalCompositeOperation = 'multiply'; g.globalAlpha = .22; g.drawImage(FIBRE, 0, 0, w, h); g.globalAlpha = 1;
  const plateSet = [C.base, ...((o.variant && C.V[o.variant]) || [])];
  // a variant patch replaces what's under it: paper it over first, then print its plates
  for (const P of plateSet.slice(1)) { g.globalCompositeOperation = 'source-over'; g.save(); g.globalCompositeOperation = 'destination-out'; g.drawImage(P.k, P.x, P.y); g.restore(); }
  const [mx, my] = o.misreg || [5, 3];                                            // master px (the card is printed large)
  g.globalCompositeOperation = 'multiply';
  for (const P of plateSet) g.drawImage(P.i, P.x + mx, P.y + my);
  for (const P of plateSet) g.drawImage(P.k, P.x, P.y);
  return INK._c;
}
{
  // B5, the bridge close-up (song 156.2-159.5): "...I didn't know this one." Held; the camera approaches the card (the grain
  // grows); on "I didn't" the paper bends back along a fold under her chin (the smallest head movement, as paper); after the
  // line, one blink (half, closed, half, on twos); the fold settles.
  const S0 = 156.2, S1 = 159.53, LINE = 157.21, BLINK = 158.55;
  const bend = s => { const u = Math.max(0, Math.min(1, (s - LINE) / .5)); return 7 * (u < 1 ? Math.sin(u * Math.PI / 2) : 1) * (s > BLINK + .6 ? Math.max(.4, 1 - (s - BLINK - .6) / 1.5) : 1); };   // degrees
  LOOPS.inkcloseup = t => {
    const s = S0 + Math.floor(t * 12 + 1e-6) / 12;                                // song time; the card moves on twos
    const sc = S0 + t;                                                           // the camera on ones
    const d = Math.round((s - BLINK) * 12), variant = d === 0 || d === 2 ? 'half' : d === 1 ? 'closed' : null;
    const src = inkPrint(INK.closeup, { variant });
    X.fillStyle = '#0d0b0a'; X.fillRect(0, 0, W, H);
    const zoom = 1 + .06 * Math.min(1, (sc - S0) / (S1 - S0)), CH = 1060 * zoom, CW = CH * src.width / src.height, cx = W / 2, cy = H / 2 + 8;
    const FOLD = .72, th = bend(s) * Math.PI / 180;                              // the fold: 66% down the card (under her chin)
    const map = (u, v) => {
      let y = v; if (v < FOLD) y = FOLD - (FOLD - v) * Math.cos(th);           // above the fold the card tips back: foreshortened
      const xL = (u - .5) * (1 - .018 * Math.sin(th) * (FOLD - Math.min(v, FOLD)) / FOLD);   // and narrows a touch at the top
      return [cx + xL * CW, cy + (y - .5) * CH];
    };
    // the card's shadow on the stage, then the card
    X.save(); X.filter = 'blur(18px)'; X.fillStyle = 'rgba(0,0,0,.7)'; X.fillRect(cx - CW / 2 + 14, cy - CH / 2 + 22, CW, CH); X.restore();
    WARP.draw(X, src, map, { cols: 32, rows: 48, shade: (u, v) => {
      const lamp = 1;
      const fold = v < FOLD ? 1 + .9 * Math.sin(th) * (v / FOLD) ** 3 : 1;      // the tipped paper catches a little more light toward the fold
      const crease = 1 + .55 * Math.sin(th) * Math.exp(-(((v - FOLD) / .008) ** 2));
      return lamp * fold * crease; } });
    // the lantern: warm light on the card, falling off to its edges
    X.save(); X.globalCompositeOperation = 'multiply'; const lg = X.createRadialGradient(cx + 60, cy - 80, 80, cx, cy, CW * .8);
    lg.addColorStop(0, '#FFF6E4'); lg.addColorStop(.6, '#F6DDB0'); lg.addColorStop(1, '#C9965A'); X.fillStyle = lg;
    X.fillRect(cx - CW / 2 - 40, cy - CH / 2 - 40, CW + 80, CH + 80); X.restore();
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
    const s = S0 + Math.floor(t * 12 + 1e-6) / 12, src = inkPrint(INK.lamp, { misreg: [6, 4] });
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
    if (lit > 0) { glow(at(LANTERN), 1650 * k * (.55 + .45 * lit), 'rgba(255,200,132,A)', lit); glow(at(LANTERN), 760 * k, 'rgba(255,214,148,A)', lit); }
    X.save(); X.globalCompositeOperation = 'multiply'; X.drawImage(INK._L, 0, 0); X.restore();
    if (lit > 0) {                                                             // the lantern's paper, glowing from inside
      X.save(); X.globalCompositeOperation = 'screen'; const [lx, ly] = at(LANTERN), g = X.createRadialGradient(lx, ly, 0, lx, ly, 440 * k);
      g.addColorStop(0, `rgba(255,190,105,${.4 * lit})`); g.addColorStop(1, 'rgba(255,190,105,0)'); X.fillStyle = g; X.fillRect(lx - 460 * k, ly - 460 * k, 920 * k, 920 * k); X.restore();
    }
    X.save(); X.globalCompositeOperation = 'overlay'; X.globalAlpha = .14; X.fillStyle = X.createPattern(GRAIN[Math.floor(s * 12) % 4], 'repeat'); X.fillRect(0, 0, W, H); X.restore();
  };
  LOOPS.inklamp.len = S1 - S0;
}
