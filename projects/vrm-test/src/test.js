// VRM test: Clawd exported by charkit/export.py, in three.js, posed by the hook clip. Cameras match the Blender boards
// (projects/clawd3d/build/retarget_test.py for the hook, clawd.render_views for the model views) so the two runtimes can
// be laid side by side.
const VRM_URL = '../../charkit/out/export/clawd.vrm';
const CLIP_URL = 'assets/hook_v1.motion.json';
let CTX, STAGE, VRMOBJ, PERF, INFO = {};

async function setupTest(gl) {
  const t0 = performance.now();
  CTX = await V3.renderer({ w: W, h: H, backend: gl });
  STAGE = V3.stage({ bg: 0xffffff });
  VRMOBJ = await V3.load(CTX, VRM_URL);
  STAGE.scene.add(VRMOBJ.scene);
  const clip = await (await fetch(CLIP_URL)).json();
  PERF = V3.performer(VRMOBJ, clip, { fps: FPS, face: V3.blinks(DUR) });
  PERF.at(0);
  await V3.warm(CTX, STAGE.scene, V3.camera({ az: 0, dist: 4.2, height: 0.25, target: [0, 0.8, 0], lens: 40, aspect: W / H }));
  let tris = 0, meshes = 0;
  VRMOBJ.scene.traverse(o => { if (o.isMesh) { meshes++; const g = o.geometry; tris += (g.index ? g.index.count : g.attributes.position.count) / 3; } });
  INFO = { backend: CTX.backend, webgpu: CTX.gpu, meshes, tris: Math.round(tris), load_ms: Math.round(performance.now() - t0),
    expressions: VRMOBJ.expressionManager.expressions.map(e => e.expressionName),
    springs: [...VRMOBJ.springBoneManager.joints].map(j => j.bone.name), meta: VRMOBJ.meta.name,
    ua: navigator.userAgent };
  window.INFO = INFO;
  console.log('vrm-test: ' + CTX.backend + ', ' + INFO.tris + ' tris, ' + INFO.load_ms + ' ms');
}

function label(text, x, y) {
  X.save(); X.font = '22px ui-monospace, monospace'; X.fillStyle = '#555'; X.fillText(text, x, y); X.restore();
}

// the hook: front | three-quarter, the retarget_test cameras (4.2 m, 40 mm, 25 cm above a target 80 cm up)
function hook(t) {
  PERF.at(t);
  const w = W / 2, cams = [0, 35].map(az => V3.camera({ az, dist: 4.2, height: 0.25, target: [0, 0.8, 0], lens: 40, aspect: w / H }));
  V3.draw(CTX, STAGE.scene, [[cams[0], 0, 0, w, H], [cams[1], w, 0, w, H]]);
  X.drawImage(CTX.canvas, 0, 0);
  label(`three.js · ${CTX.backend} · t ${t.toFixed(2)} f${Math.round(t * FPS) + 1}`, 16, 32);
}
shots([[0, hook]]);
LOOPS.hook = hook; LOOPS.hook.len = DUR;

// model views in (roughly) the build's A-pose: clawd.render_views' cameras (3.6 m, 50 mm, 35 cm above 82 cm)
const APOSE = { leftUpperArm: [0, 0, -62], rightUpperArm: [0, 0, 62], leftLowerArm: [0, 0, 1.5], rightLowerArm: [0, 0, -1.5],
  leftUpperLeg: [0, 0, 6.5], rightUpperLeg: [0, 0, -6.5], leftLowerLeg: [0, 0, -6.5], rightLowerLeg: [0, 0, 6.5] };
function apose() {
  const H_ = VRMOBJ.humanoid;
  H_.resetNormalizedPose();
  for (const [b, e] of Object.entries(APOSE)) H_.getNormalizedBoneNode(b).quaternion.setFromEuler(new THREE.Euler(...e.map(d => d * Math.PI / 180)));
  VRMOBJ.springBoneManager && VRMOBJ.springBoneManager.reset();
  PERF.invalidate();
  H_.update(); VRMOBJ.scene.updateMatrixWorld(true);
  PERF.setFace({});
}
LOOPS.views = t => {
  const az = [0, 35, 90, 180, 215][Math.max(0, Math.min(4, Math.round(t)))];
  apose();
  const cam = V3.camera({ az, dist: 3.6, height: 0.35, target: [0, 0.82, 0], lens: 50, aspect: W / H });
  V3.draw(CTX, STAGE.scene, [[cam, 0, 0, W, H]]);
  X.drawImage(CTX.canvas, 0, 0);
  label(`three.js · ${CTX.backend} · az ${az}`, 16, 32);
};
LOOPS.views.len = 5;

// the expression sheet: face close-ups (85 mm, 1.1 m), one expression per cell, front and three-quarter
const FACES = ['neutral', 'blink', 'blinkLeft', 'happy', 'relaxed', 'surprised', 'angry', 'eyesHalf',
  'aa', 'ih', 'ou', 'ee', 'oh', 'mouthGrin', 'mouthMBP', 'mouthAm'];
LOOPS.faces = t => {
  apose();
  const az = t < 0.5 ? 0 : 32, cols = 8, rows = 2, w = W / cols, h = H / rows;
  const head = [0, 1.358, -0.004];                        // clawd.HC (Blender (0, 0.004, 1.368)) a centimetre down
  const views = FACES.map((name, i) => {
    const cam = V3.camera({ az, dist: 1.1, height: 0.02, target: head, lens: 85, aspect: w / h });
    return [cam, (i % cols) * w, Math.floor(i / cols) * h, w, h, () => PERF.setFace(name === 'neutral' ? {} : { [name]: 1 })];
  });
  V3.draw(CTX, STAGE.scene, views);
  X.drawImage(CTX.canvas, 0, 0);
  FACES.forEach((name, i) => label(name, (i % cols) * w + 8, Math.floor(i / cols) * h + 26));
};
LOOPS.faces.len = 2;

// one face close-up in a 1:1 box on the left, as clawd.render_views' face.png (85 mm, 1.1 m, az 32)
LOOPS.face = t => {
  apose();
  const cam = V3.camera({ az: t < 0.5 ? 32 : 0, dist: 1.1, height: 0.02, target: [0, 1.358, -0.004], lens: 85, aspect: 1 });
  V3.draw(CTX, STAGE.scene, [[cam, 0, 0, H, H]]);
  X.fillStyle = '#fff'; X.fillRect(0, 0, W, H);
  X.drawImage(CTX.canvas, 0, 0, H, H, 0, 0, H, H);
};
LOOPS.face.len = 2;

// every board also under another renderer, for A/B: --loop=hook@webgl (classic WebGLRenderer + MToonMaterial),
// --loop=views@webgpu-gl (WebGPURenderer on its WebGL2 backend); index.html picks the backend from the suffix
for (const k of Object.keys(LOOPS)) for (const b of ['webgpu', 'webgpu-gl', 'webgl']) LOOPS[k + '@' + b] = LOOPS[k];
