// tools/gltf_validate.mjs: the Khronos glTF validator (npm gltf-validator, Apache-2.0) on a .glb / .vrm, summarised.
//   node tools/gltf_validate.mjs charkit/out/clawd/clawd.vrm [--json]      exit code 1 on errors
// Unknown extensions (VRMC_vrm, VRMC_materials_mtoon, OPENADS_charkit_look) are reported as infos, not checked.
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const validator = require('gltf-validator');
const [file, ...rest] = process.argv.slice(2);
if (!file) { console.log('usage: node tools/gltf_validate.mjs FILE.glb|.vrm [--json]'); process.exit(2); }
const r = await validator.validateBytes(new Uint8Array(readFileSync(file)), { maxIssues: 500 });
if (rest.includes('--json')) { console.log(JSON.stringify(r, null, 1)); process.exit(r.issues.numErrors ? 1 : 0); }
const i = r.issues;
console.log(`${file}: ${i.numErrors} errors, ${i.numWarnings} warnings, ${i.numInfos} infos, ${i.numHints} hints (validator ${r.validatorVersion})`);
const by = {};
for (const m of i.messages) (by[`${['error', 'warning', 'info', 'hint'][m.severity]} ${m.code}`] ||= []).push(`${m.pointer || ''} ${m.message}`);
for (const [k, a] of Object.entries(by)) console.log(`  ${k} x${a.length}\n    ${a.slice(0, 3).join('\n    ')}`);
const info = r.info || {};
console.log(`  ${info.drawCallCount} draw calls, ${info.totalTriangleCount} triangles, ${info.totalVertexCount} vertices, ${info.materialCount} materials, ` +
  `${info.hasSkins ? 'skinned' : 'no skins'}, ${info.hasMorphTargets ? 'morph targets' : 'no morphs'}, extensions: ${(info.extensionsUsed || []).join(', ')}`);
process.exit(i.numErrors ? 1 : 0);
