// scenery.js: multiplane cut-paper scenery (FABLE.md §4: "three to five paper planes with real parallax and real cast
// shadows between them, Reiniger's camera"). Each flat (rig/scenery/*.png, black paper, GPT Image) is a mask drawn into the
// shadow layer at a depth: a plane nearer the lamp casts a bigger shadow with a softer fringe. `place` computes where to hold
// the flat so its SHADOW lands on the target rect. The lantern's slow sway moves the deep planes more: that's the parallax.
const FLATS = {};
async function SCENERY_INIT() {
  const load = src => new Promise((ok, no) => { const i = new Image(); i.onload = () => ok(i); i.onerror = no; i.src = src; });
  for (const n of ['far', 'rocksL', 'rocksR', 'waves', 'ground', 'pine']) {
    const img = await load(`rig/scenery/${n}.png`), w = 1920, h = Math.round(img.height * w / img.width), c = mkCanvas(w, h), g = c.getContext('2d');
    g.drawImage(img, 0, 0, w, h); const d = g.getImageData(0, 0, w, h), p = d.data;
    for (let i = 0; i < p.length; i += 4) { const L = (p[i] * .299 + p[i + 1] * .587 + p[i + 2] * .114) / 255; p[i] = 22; p[i + 1] = 22; p[i + 2] = 26; p[i + 3] = 255 * Math.min(1, Math.max(0, (1 - L) * 1.15)); }
    g.putImageData(d, 0, 0); FLATS[n] = c;
  }
}
// hold the flat so its shadow (scaled about the lamp by 1/(1 - depth/2)) lands on [x, y, w, h]
function placeFlat(c, name, [x, y, w, h], depth, lamp, flip = false, src = [0, 1]) {
  const [lx, ly] = lamp, s = 1 / (1 - Math.min(depth, .8) * .5), f = FLATS[name];
  const px = lx + (x - lx) / s, py = ly + (y - ly) / s, sx = src[0] * f.width, sw = (src[1] - src[0]) * f.width;
  const sy = (src[2] ?? 0) * f.height, sh = ((src[3] ?? 1) - (src[2] ?? 0)) * f.height;           // src: [x0, x1, y0, y1] fractions
  c.save(); c.translate(px + (flip ? w / s : 0), py); c.scale(flip ? -1 : 1, 1); c.drawImage(f, sx, sy, sw, sh, 0, 0, w / s, h / s); c.restore();
}
// the shore (verse 1): far hills over the sea, waves, rocks and reeds at the sides, a pine leaning in from the right, the beach
function shore(t, o = {}) {
  const FLOOR = o.floor || 962, sway = o.sway ?? 1, [lx0, ly0] = SCREEN.lamp, ts = Math.min(t, o.still ?? Infinity);   // still: the lamp held (the bridge's clack)
  const lampAt = d => [lx0 + sway * 60 * d * Math.sin(ts * .37) + sway * 25 * d * Math.sin(ts * .91), ly0];   // deep planes drift more
  // o.lamp: the lamp has moved (the bridge: into her lap, onto the floor, into her hand). The flats stay where they were held
  // for the lamp above; their shadows now fall from the new one (a low lamp lengthens them upward)
  // the bridge (Fable): each plane struck, a card pulled sideways off the screen: {key: [u, dir]}, u 0 in place .. 1 gone.
  // Pulled, it comes a little off the screen toward the lamp (its shadow grows and softens) and its tissue card shows: the
  // straight edge of the paper it was cut on.
  const S = o.strike || {}, pull = key => S[key] || [0, 1];
  const card = (c, rect, depth, lamp, a) => { const [lx, ly] = lamp, s = 1 / (1 - Math.min(depth, .8) * .5), [x, y, w, h] = rect;
    c.fillStyle = `rgba(22,22,26,${a})`; c.fillRect(lx + (x - lx) / s, ly + (y - ly) / s, w / s, h / s); };
  // Reiniger's tissue paper: the further back a plane, the thinner its paper, the greyer its shadow; the actors (black card)
  // always read against it. `ink` = how much light the paper stops.
  const plane = (name, rect, depth, flip, src, ink, key = name) => {
    const [u, dir] = pull(key); if (u >= 1) return;
    const d = depth + (u > 0 ? .05 : 0), lamp = lampAt(depth), proj = o.lamp || lamp, r = [rect[0] + dir * u * 1900, rect[1], rect[2], rect[3]];
    shadow(c => { c.globalCompositeOperation = 'source-over'; if (u > 0) card(c, r, d, lamp, .1 * Math.min(1, u / .16)); placeFlat(c, name, r, d, lamp, flip, src); },
      d, { penumbra: true, lamp: proj, alpha: (o.alpha ?? 1) * ink });
  };
  // content bands (fraction of each flat's height): far .56-.94, waves ~.47-1; each placed so its base sits behind the beach
  plane('far', [100, FLOOR - 569, 1720, 573], .5, false, [0, 1], .34);                                   // hills over the sea, tops ~250 px above the floor
  plane('rocksL', [60, FLOOR - 470, 457, 470], .18, false, [0, 1], .62);                 // a reed clump at the left edge (its own flat: split_rocks.py)
  plane('rocksR', [1574, FLOOR - 400, 287, 400], .18, false, [0, 1], .62);                // and one under the pine, at the right
  plane('pine', [628, -40, 1392, 453], .1, true, [0, .87, 0, .85], .82);                  // the whole tree to its branch tips (no cut edge), true shape; the trunk runs off the right edge, high, clear of the actors' heads
  const [ug, dg] = pull('ground');
  if (ug < 1) shadow(c => { c.globalCompositeOperation = 'source-over'; const off = dg * ug * 1900;
    c.drawImage(FLATS.ground, 100 + off, FLOOR - 330, 1720, 573);                          // its top edge (.583 of the flat) is the floor
    // the stage floor stays plain where the actors play: the shells and seaweed only at the edges
    c.clearRect((o.clearX0 ?? 520) + off, 0, (o.clearX1 ?? 1480) - (o.clearX0 ?? 520), FLOOR - 1); }, 0);
}
{
  LOOPS.shoretest = t => { const tq = Math.floor(t * 12 + 1e-6) / 12; X.fillStyle = '#0d0b0a'; X.fillRect(0, 0, W, H); screen(tq, { stops: FABLE_LAMP, tex: .32 }); shore(tq); };
  LOOPS.shoretest.len = 8;
}

{
  // verse 1 in its world: the shore, Fable telling, the crab, the unfold; inside the butai, the audience in the room
  LOOPS.verse1 = t => {
    window.SHORE = true;
    try { stage(t, tt => LOOPS.origami(tt), { cam: CAM_WINDOW, doors: 1, page: 24 + Math.floor(t * 12 + 1e-6) / 12 }); } finally { window.SHORE = false; }
    readers(24 + t, CAM_WINDOW);                                   // the readers: heads and lanterns, lifting on the call
  };
  LOOPS.verse1.len = 12;
}
