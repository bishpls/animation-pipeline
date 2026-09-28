// charkit-look boards: the Blender build's review boards (charkit.scene.boards: same cameras, pose, expressions) next to
// our WebGPU look, and the difference. Each board is a LOOPS entry (engine/studio.js) rendered by engine/render.mjs.
// The character: ~NAME on the loop name (--loop=views~clawd), default clawd; files from charkit/out/NAME/.
let BCTX, BCK, BP, BSCENE, BINFO = {};
const EXPR = ['blink', 'happy', 'half', 'wide', 'angry', 'sad', 'squint'];             // charkit.scene.EXPR
const MOUTH = ['neutral', 'aa', 'ih', 'ou', 'ee', 'oh', 'smile', 'grin', 'frown', 'surprised'];
const BROW = { angry: 'angry', sad: 'sad', wide: 'surprised', happy: 'relaxed' };      // charkit.boards.face_board.set_expr
const img = src => new Promise(ok => { const i = new Image(); i.onload = () => ok(i); i.onerror = () => ok(null); i.src = src; });

async function setupBoards(q) {
  const loop = q.get('loop') || '';
  const parts = loop.split('~');
  const name = parts[1] || q.get('char') || 'clawd';
  window.FLAGS = new Set(parts.slice(2));                 // --loop=views~clawd~nohull (debug switches)
  const t0 = performance.now();
  BCTX = await V3.renderer({ w: W, h: H, backend: q.get('gl') || 'auto' });
  BSCENE = new THREE.Scene();
  const alt = [...FLAGS].find(f => f.startsWith('vrm:'));        // ~vrm:FILE loads charkit/out/NAME/FILE.vrm
  BCK = await CK.load(BCTX, q.get('vrm') || `../../charkit/out/${name}/${alt ? alt.slice(4) : name}.vrm`);
  BSCENE.add(BCK.scene);
  if (FLAGS.has('nohull')) BCK.hulls.forEach(h => h.removeFromParent());
  BCK.buildPose(); BCK.update();
  BP = CK.pipeline(BCTX, { ss: +(q.get('ss') || 2) });
  BINFO = { name, dir: `../../charkit/out/${name}/boards/`, backend: BCTX.backend, gpu: BCTX.gpu, load_ms: 0 };
  const h = BCK.head();
  BINFO.eyeZ = h.centre.y; BINFO.L = h.L; BINFO.height = BCK.root.height || 1.55;
  // warm every pipeline once (the first WebGPU frame on a page differs a few levels otherwise)
  const cam = CK.camera({ target: [0, BINFO.eyeZ, 0], dist: 1, lens: 85 });
  for (let i = 0; i < 2; i++) { BP.render(BSCENE, cam, BCK, [0, 0, 300, 300]); if (BCTX.renderer.backend.device) await BCTX.renderer.backend.device.queue.onSubmittedWorkDone(); }
  // the Blender boards
  BINFO.blender = {};
  const want = [...[0, 30, 60, 90, 150].map(a => `face_${String(a).padStart(3, '0')}`), ...[0, 35, 90, 180].map(a => `body_${String(a).padStart(3, '0')}`),
    ...EXPR.map(e => 'expr_' + e), ...MOUTH.map(m => 'mouth_' + m)];
  await Promise.all(want.map(async k => { BINFO.blender[k] = await img(BINFO.dir + k + '.png'); }));
  BINFO.load_ms = Math.round(performance.now() - t0);
  let tris = 0; BCK.meshes.forEach(m => { tris += (m.geometry.index ? m.geometry.index.count : m.geometry.attributes.position.count) / 3; });
  BINFO.tris = Math.round(tris); BINFO.meshes = BCK.meshes.length; BINFO.hulls = BCK.hulls.length;
  window.INFO = BINFO;
  for (const k of Object.keys(LOOPS)) if (!k.includes('~')) LOOPS[loop.startsWith(k + '~') ? loop : k + '~' + name] = LOOPS[k];
  if (loop && LOOPS[loop]) window.LOOP = LOOPS[loop];
  console.log(`charkit-look: ${BCTX.backend}, ${BINFO.tris} tris, ${BINFO.meshes} meshes, ${BINFO.load_ms} ms`);
}

function label(text, x, y, color = '#333', size = 20) {
  X.save(); X.font = `${size}px ui-monospace, monospace`; X.fillStyle = color; X.fillText(text, x, y); X.restore();
}

// one comparison: Blender's image | ours | |difference| x 4 (and the mean over the frame)
function compare(key, cam, w, h, { through = 0.55, keys = {}, labelText = '' } = {}) {
  BCK.buildPose(); BCK.keys(keys); BCK.expressions({}); BCK.update();
  BP.through = through;
  BP.render(BSCENE, cam, BCK, [w, 0, w, h]);
  X.fillStyle = '#26252b'; X.fillRect(0, 0, W, H);
  X.drawImage(BCTX.canvas, w, 0, w, h, w, 0, w, h);
  const b = BINFO.blender[key];
  if (b) X.drawImage(b, 0, 0, w, h);
  else label('no Blender board ' + key, 16, 40, '#e66');
  let mean = null;
  if (b) {
    const A = X.getImageData(0, 0, w, h), B = X.getImageData(w, 0, w, h), D = X.createImageData(w, h);
    let s = 0;
    for (let i = 0; i < A.data.length; i += 4) {
      let m = 0;
      for (let c = 0; c < 3; c++) { const d = Math.abs(A.data[i + c] - B.data[i + c]); D.data[i + c] = Math.min(255, d * 4); m += d; }
      D.data[i + 3] = 255; s += m / 3;
    }
    mean = s / (w * h);
    X.putImageData(D, 2 * w, 0);
  }
  label('Blender EEVEE (charkit build board)', 12, 26);
  label(`three.js ${BCTX.backend} · charkit/look.js`, w + 12, 26);
  label(`|difference| x 4${mean != null ? ' · mean ' + mean.toFixed(2) + '/255' : ''}`, 2 * w + 12, 26, '#ddd');
  if (labelText) label(labelText, 12, h - 14);
  window.LAST_DIFF = mean;
  return mean;
}

LOOPS.views = t => {
  const az = [0, 30, 60, 90, 150][Math.max(0, Math.min(4, Math.round(t)))];
  const cam = CK.camera({ target: [0, BINFO.eyeZ + 0.06 * BINFO.L, 0], az, dist: 1.0, height: 0, lens: 85, aspect: 1 });
  compare(`face_${String(az).padStart(3, '0')}`, cam, 900, 900, { labelText: `head view az ${az}` });
};
LOOPS.views.len = 5;
LOOPS.body = t => {
  const az = [0, 35, 90, 180][Math.max(0, Math.min(3, Math.round(t)))];
  const Hm = BINFO.height;
  const cam = CK.camera({ target: [0, Hm * 0.52, 0], az, dist: 6, height: 0, ortho: Hm * 1.12, aspect: 0.6 });
  compare(`body_${String(az).padStart(3, '0')}`, cam, 600, 1000, { through: 0, labelText: `body az ${az}` });
};
LOOPS.body.len = 4;
LOOPS.expr = t => {
  const e = EXPR[Math.max(0, Math.min(EXPR.length - 1, Math.round(t)))];
  const keys = { ['eye_' + e]: 1 }; if (BROW[e]) keys['brow_' + BROW[e]] = 1;
  const cam = CK.camera({ target: [0, BINFO.eyeZ - 0.02 * BINFO.L, 0], az: 0, dist: 0.42, lens: 85, aspect: 1 });
  compare('expr_' + e, cam, 600, 600, { keys, labelText: e });
};
LOOPS.expr.len = EXPR.length;
LOOPS.mouth = t => {
  const m = MOUTH[Math.max(0, Math.min(MOUTH.length - 1, Math.round(t)))];
  const cam = CK.camera({ target: [0, BINFO.eyeZ - 0.28 * BINFO.L, 0], az: 0, dist: 0.30, lens: 85, aspect: 1 });
  compare('mouth_' + m, cam, 600, 600, { through: 0, keys: m === 'neutral' ? {} : { ['mouth_' + m]: 1 }, labelText: m });
};
LOOPS.mouth.len = MOUTH.length;

// every debug view of one head three-quarter view (and the full look)
LOOPS.debug = t => {
  const modes = CK.DEBUG.length, cols = 6, w = W / cols, h = H / 2;
  X.fillStyle = '#26252b'; X.fillRect(0, 0, W, H);
  BCK.buildPose(); BCK.keys({}); BCK.update();
  const az = t < 0.5 ? 30 : 0;
  for (let i = 0; i < Math.min(modes, cols * 2); i++) {
    CK.U.debug.value = i;
    CK.U.bone.value = BCK.joints.indexOf('head');
    const cam = CK.camera({ target: [0, BINFO.eyeZ, 0], az, dist: 1.1, lens: 85, aspect: w / h });
    BP.render(BSCENE, cam, BCK, [(i % cols) * w, Math.floor(i / cols) * h, w, h]);
  }
  CK.U.debug.value = 0;
  X.drawImage(BCTX.canvas, 0, 0);
  for (let i = 0; i < Math.min(modes, cols * 2); i++) label(CK.DEBUG[i] + (i === 6 ? ' (head)' : ''), (i % cols) * w + 10, Math.floor(i / cols) * h + 26, '#fff');
};
LOOPS.debug.len = 1;

// motion: the hook clip (projects/vrm-test's canonical clip) retargeted by engine/three/vrm.js, in our look: a pure
// function of t (springs stepped from 0 on a fixed grid, blinks from a seeded track)
let PERF = null;
LOOPS.hook = t => {
  if (!PERF) return label('no clip loaded', 40, 60, '#e66');
  PERF.at(t);
  BCK.update();
  const w = W / 2;
  X.fillStyle = '#26252b'; X.fillRect(0, 0, W, H);
  for (const [i, az] of [0, 35].entries()) {
    const cam = CK.camera({ target: [0, 0.8, 0], az, dist: 4.2, height: 0.25, lens: 40, aspect: w / H });
    BP.through = 0.55;
    BP.render(BSCENE, cam, BCK, [i * w, 0, w, H]);
  }
  X.drawImage(BCTX.canvas, 0, 0);
  label(`charkit look · ${BCTX.backend} · t ${t.toFixed(2)} f${Math.round(t * FPS) + 1}`, 16, 32, '#ddd', 22);
};
LOOPS.hook.len = 5;
LOOPS.hook.setup = async () => {
  const clip = await (await fetch('../vrm-test/assets/hook_v1.motion.json')).json();
  const blink = V3.blinks(10);
  PERF = V3.performer(BCK.vrm, clip, { fps: FPS, face: t => { const b = blink(t); return b.eyesHalf ? { eye_half: 1 } : b; } });
  // CK.update() owns the face: route the performer's face track through our expressions
  const at = PERF.at;
  PERF.at = t => { at(t); const f = blink(t); BCK.expressions(f.eyesHalf ? { eye_half: 1 } : f); };
};

// a turntable of the head and body, 360 degrees over 5 s
LOOPS.turn = t => {
  BCK.buildPose(); BCK.keys({}); BCK.expressions({}); BCK.update();
  const az = (t / 5) * 360, Hm = BINFO.height;
  X.fillStyle = '#26252b'; X.fillRect(0, 0, W, H);
  const cam = CK.camera({ target: [0, Hm * 0.52, 0], az, dist: 6, ortho: Hm * 1.08, aspect: W / H });
  BP.through = 0.55;
  BP.render(BSCENE, cam, BCK, [0, 0, W, H]);
  X.drawImage(BCTX.canvas, 0, 0);
};
LOOPS.turn.len = 5;

// the page's own timeline: the views board
shots([[0, LOOPS.views]]);

const _setupBoards = setupBoards;
setupBoards = async q => {
  await _setupBoards(q);
  const loop = (q.get('loop') || '').split('~')[0];
  if (LOOPS[loop] && LOOPS[loop].setup) await LOOPS[loop].setup();
};
