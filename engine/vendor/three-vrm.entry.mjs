// engine/vendor/three-vrm.entry.mjs: the recipe for engine/vendor/three-vrm.js, a browser bundle (like fontkit.js) of
//   three.js r186 (0.186.1, MIT)            WebGLRenderer, WebGPURenderer (with its WebGL2 fallback backend), TSL, GLTFLoader
//   @pixiv/three-vrm 3.5.5 (MIT)            VRM 1.0 / 0.x loader, MToonMaterial (WebGL) and MToonNodeMaterial (WebGPU)
// loaded with a plain <script> tag; it sets window.THREE (the three namespace, plus GLTFLoader, TSL, VRM, MToonNodeMaterial).
// Licences: engine/vendor/three-vrm.LICENSE.txt, THIRD_PARTY.md. Rebuild (from the repo root; esbuild is in package.json):
//   T=$(mktemp -d) && (cd $T && npm init -y >/dev/null && npm i three@0.186.1 @pixiv/three-vrm@3.5.5)
//   NODE_PATH=$T/node_modules node_modules/.bin/esbuild engine/vendor/three-vrm.entry.mjs --bundle --minify --format=iife \
//     --legal-comments=inline --target=chrome120 --outfile=engine/vendor/three-vrm.js
import * as THREE_GL from 'three';
import * as THREE_GPU from 'three/webgpu';
import * as TSL from 'three/tsl';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import * as VRM from '@pixiv/three-vrm';
import { MToonNodeMaterial } from '@pixiv/three-vrm/nodes';

window.THREE = Object.assign({}, THREE_GL, THREE_GPU, { GLTFLoader, TSL, VRM, MToonNodeMaterial });
