// stage.js: the kamishibai butai around the shadow theatre (FABLE.md §4: "a wooden frame with two small doors ... a 'zoom' is
// the camera physically approaching the frame"). A scene draws the theatre as usual (screen + shadows, full frame); stage()
// renders it offscreen, sets its SCREEN.rect into the butai's window, lays the wooden frame over it, swings the doors on their
// hinges (in perspective), and films it all with a camera in butai-art pixels.
//   stage(t, sceneFn, { cam: { x, y, zoom }, doors: 0..1 (1 = open) })
const BUTAI = { win: [1009, 805, 2830, 1801], hingeL: 872, hingeR: 2968, doorL: [39, 868], doorR: [2968, 3801], size: [3840, 2160] };
async function STAGE_INIT() {
  const img = await new Promise((ok, no) => { const i = new Image(); i.onload = () => ok(i); i.onerror = no; i.src = 'rig/butai/butai.png'; });
  const cut = (x0, x1) => { const c = mkCanvas(x1 - x0, img.height); c.getContext('2d').drawImage(img, -x0, 0); return c; };
  BUTAI.frame = mkCanvas(img.width, img.height); const f = BUTAI.frame.getContext('2d'); f.drawImage(img, 0, 0);
  f.clearRect(0, 0, BUTAI.doorL[1], img.height); f.clearRect(BUTAI.doorR[0], 0, img.width - BUTAI.doorR[0], img.height);
  BUTAI.dl = cut(...BUTAI.doorL); BUTAI.dr = cut(...BUTAI.doorR);
  BUTAI.theatre = mkCanvas(W, H);
}
// the default cameras: the whole stage, and the window filling the frame (rails just visible)
const CAM_WIDE = { x: 1920, y: 1180, zoom: .5 }, CAM_WINDOW = { x: 1920, y: 1303, zoom: 1.0 };
const camLerp = (a, b, u) => ({ x: a.x + (b.x - a.x) * u, y: a.y + (b.y - a.y) * u, zoom: a.zoom * Math.pow(b.zoom / a.zoom, u) });
function stage(t, sceneFn, o = {}) {
  // 1. the theatre, offscreen
  const Xs = X; X = BUTAI.theatre.getContext('2d'); X.setTransform(1, 0, 0, 1, 0, 0); X.globalAlpha = 1; X.globalCompositeOperation = 'source-over'; X.filter = 'none';
  try { sceneFn(t); } finally { X = Xs; }
  // 2. the room, the theatre in the window, the frame, the doors, through the camera
  const cam = o.cam || CAM_WINDOW, z = cam.zoom, T = (px, py) => [W / 2 + (px - cam.x) * z, H / 2 + (py - cam.y) * z];
  X.save(); X.setTransform(1, 0, 0, 1, 0, 0);
  X.fillStyle = '#0b0908'; X.fillRect(0, 0, W, H);
  const [wx0, wy0, wx1, wy1] = BUTAI.win, [sx, sy, sw, sh] = SCREEN.rect, [a0, b0] = T(wx0 - 6, wy0 - 6), [a1, b1] = T(wx1 + 6, wy1 + 6);
  X.drawImage(BUTAI.theatre, sx, sy, sw, sh, a0, b0, a1 - a0, b1 - b0);
  const [fx, fy] = T(0, 0); X.save(); X.translate(fx, fy); X.scale(z, z);
  X.filter = 'brightness(.62)'; X.drawImage(BUTAI.frame, 0, 0); X.filter = 'none';                      // the wood, in the room's low light
  // light spilling from the lit screen onto the inner rails
  X.globalCompositeOperation = 'screen'; const sp = X.createLinearGradient(0, wy0 - 140, 0, wy0); sp.addColorStop(0, 'rgba(255,190,110,0)'); sp.addColorStop(1, 'rgba(255,190,110,.16)');
  X.fillStyle = sp; X.fillRect(wx0 - 140, wy0 - 140, wx1 - wx0 + 280, 140); X.globalCompositeOperation = 'source-over';
  // the doors: open = lying flat beside the frame; closed = over the window; mid-swing, foreshortened, the free edge nearer the lens
  const open = Math.max(0, Math.min(1, o.doors ?? 1)), phi = (1 - open) * Math.PI;                       // 0 open .. PI closed
  const doorPanel = (img, hinge, side) => {                                                              // side -1 = left door
    const w = img.width, h = img.height, c = Math.cos(phi), reach = side < 0 ? (hinge - 1920) : (hinge - 1920);
    const closedW = Math.abs(1920 - hinge) + 4, ww = c >= 0 ? w * c : closedW * -c, dir = c >= 0 ? side : -side;
    if (ww < 2) return;
    const grow = 1 + .1 * Math.sin(phi), shade = .55 + .45 * Math.abs(c);
    X.save(); X.translate(hinge, 0);
    // the panel as a trapezoid: the hinge edge at full height, the free edge taller (nearer the lens)
    const face = c >= 0 ? img : img;                                                                     // (the outer face reads as the same wood)
    const N = 24; for (let i = 0; i < N; i++) {
      const u0 = i / N, u1 = (i + 1) / N, g0 = 1 + (grow - 1) * u0, g1 = 1 + (grow - 1) * u1;
      const srcX = side < 0 ? (c >= 0 ? w * (1 - u1) : w * u0) : (c >= 0 ? w * u0 : w * (1 - u1));
      const dx = dir * ww * u0, dw = dir * ww * (u1 - u0), mid = h / 2;
      X.save(); X.filter = `brightness(${.62 * shade})`;
      X.setTransform(new DOMMatrix([1, 0, 0, 1, 0, 0]).multiply(X.getTransform()));
      X.drawImage(face, srcX, 0, w / N, h, Math.min(dx, dx + dw), mid - mid * (g0 + g1) / 2, Math.abs(dw) + .6, h * (g0 + g1) / 2);
      X.restore();
    }
    X.restore();
  };
  doorPanel(BUTAI.dl, BUTAI.doorL[1], -1); doorPanel(BUTAI.dr, BUTAI.doorR[0], 1);
  X.restore();
  X.restore();
}
{
  // stagetest: the doors open (1 s), the camera pushes from the whole stage to the window (3 s), the seated phrase plays inside
  LOOPS.stagetest = t => {
    const doors = Math.min(1, Math.max(0, (Math.floor(t * 12) / 12 - .5) / 1.0)), u = Math.min(1, Math.max(0, (t - 1.8) / 3)), e = u * u * (3 - 2 * u);
    stage(t, tt => LOOPS.fable(tt), { doors: doors * doors * (3 - 2 * doors), cam: camLerp(CAM_WIDE, CAM_WINDOW, e) });
  };
  LOOPS.stagetest.len = 7;
}
