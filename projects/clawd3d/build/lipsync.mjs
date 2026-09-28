// Clawd's mouth track for 3D shots, baked from the 2D film's own lip-sync (engine/moves.js MOVES.lips: syllables from a
// pronunciation table, the mouth one frame ahead of the voice, in-betweens on every change, m/b/p pressed first, held notes
// kept open from the vocal's loudness), so 2D and 3D Clawd sing with the same mouth. Writes one drawing name per 24 fps frame
// of song time ('rest' = the closed smile).
//   node projects/clawd3d/build/lipsync.mjs [OUT.json]      (default projects/clawd3d/out/tex/mouth_track.json)
import fs from 'fs';
import path from 'path';
import vm from 'vm';
import { fileURLToPath } from 'url';

const here = path.dirname(fileURLToPath(import.meta.url));
const AP = path.join(process.env.HOME, 'animation-pipeline');
const TSU = path.join(AP, 'projects/tsuzuku');
const out = process.argv[2] || path.join(here, '..', 'out', 'tex', 'mouth_track.json');

const ctx = vm.createContext({ Math, console });
vm.runInContext(fs.readFileSync(path.join(AP, 'engine/moves.js'), 'utf8') + '\n;globalThis.MOVES = MOVES;', ctx);
const words = JSON.parse(fs.readFileSync(path.join(TSU, 'assets/words.json'), 'utf8'));
const env = JSON.parse(fs.readFileSync(path.join(TSU, 'assets/vocal_env.json'), 'utf8'));
const mouth = ctx.MOVES.lips(words, 'clawd', env);
const F = 24, dur = env.clawd.length / env.fps;
const track = [];
for (let f = 0; f < Math.ceil(dur * F); f++) track.push(mouth((f + 0.5) / F) || 'rest');
fs.mkdirSync(path.dirname(out), { recursive: true });
fs.writeFileSync(out, JSON.stringify({ fps: F, clock: 'song', who: 'clawd', mouth: track }));
const used = {}; for (const m of track) used[m] = (used[m] || 0) + 1;
console.log(track.length, 'frames ->', out, used);
