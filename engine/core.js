// engine/core.js: time, easing, noise, keyframes, springs, the beat clock, boil.
// Every frame is a pure function of t (seconds). No state carries between frames; no Math.random().
// Loaded as a plain script: everything here is global on purpose (shots stay short and readable).

const W = 1920, H = 1080;
const FPS = (window.PROJECT && PROJECT.fps) || 24;
const TAU = Math.PI * 2, D2R = Math.PI / 180;

// ------------------------------------------------------------------ math
const clamp = (x, a = 0, b = 1) => (x < a ? a : x > b ? b : x);
const lerp = (a, b, u) => a + (b - a) * u;
const invlerp = (a, b, x) => clamp((x - a) / (b - a));
const remap = (x, a, b, c, d) => lerp(c, d, invlerp(a, b, x));
const frac = x => x - Math.floor(x);
const seg = (t, a, b) => clamp((t - a) / (b - a));           // 0..1 progress through [a, b]
const mixv = (p, q, u) => p.map((v, i) => lerp(v, q[i], u));
const smooth = u => { u = clamp(u); return u * u * (3 - 2 * u); };

// easings: all map 0..1 -> 0..1 (back/elastic overshoot)
const E = {
  lin: u => u,
  in2: u => u * u, out2: u => 1 - (1 - u) ** 2, io2: u => (u < .5 ? 2 * u * u : 1 - (-2 * u + 2) ** 2 / 2),
  in3: u => u ** 3, out3: u => 1 - (1 - u) ** 3, io3: u => (u < .5 ? 4 * u ** 3 : 1 - (-2 * u + 2) ** 3 / 2),
  in5: u => u ** 5, out5: u => 1 - (1 - u) ** 5, io5: u => (u < .5 ? 16 * u ** 5 : 1 - (-2 * u + 2) ** 5 / 2),
  outExpo: u => (u >= 1 ? 1 : 1 - 2 ** (-10 * u)), inExpo: u => (u <= 0 ? 0 : 2 ** (10 * u - 10)),
  ioExpo: u => (u <= 0 ? 0 : u >= 1 ? 1 : u < .5 ? 2 ** (20 * u - 10) / 2 : (2 - 2 ** (-20 * u + 10)) / 2),
  back: u => { const c = 1.9; return 1 + (c + 1) * (u - 1) ** 3 + c * (u - 1) ** 2; },     // overshoot, settle
  back2: u => { const c = 3.2; return 1 + (c + 1) * (u - 1) ** 3 + c * (u - 1) ** 2; },    // big overshoot
  inBack: u => { const c = 1.9; return (c + 1) * u ** 3 - c * u * u; },                    // wind-up then go
  elastic: u => (u <= 0 ? 0 : u >= 1 ? 1 : 2 ** (-10 * u) * Math.sin((u * 10 - .75) * TAU / 3) + 1),
  smooth, step: u => (u < 1 ? 0 : 1),
};
const ease = (name, u) => (typeof name === 'function' ? name : E[name] || E.io3)(clamp(u));

// ------------------------------------------------------------------ deterministic noise
function hash(n) { n = Math.sin(n * 127.1 + 311.7) * 43758.5453123; return n - Math.floor(n); }
const hash2 = (x, y) => hash(x * 12.9898 + y * 78.233);
const hashS = s => { let h = 2166136261; for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619); return (h >>> 0) / 4294967296; };
function noise1(x) { const i = Math.floor(x), f = x - i, u = f * f * (3 - 2 * f); return lerp(hash(i), hash(i + 1), u) * 2 - 1; }
function fbm(x, oct = 3) { let s = 0, a = .5, f = 1; for (let i = 0; i < oct; i++) { s += a * noise1(x * f + i * 17.3); a *= .5; f *= 2; } return s; }
function rng(seed) { let a = (seed * 2654435761) >>> 0; return () => { a |= 0; a = (a + 0x6d2b79f5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }

// ------------------------------------------------------------------ hand-made timing
// Boil: drawings are "redrawn" every BOIL_N frames (on twos). BF(t) is the drawing index.
const BOIL_N = 2;
const BF = t => Math.floor(t * FPS / BOIL_N + 1e-6);
const onN = (t, n) => Math.floor(t * FPS / n + 1e-6) * n / FPS;     // hold drawings for n frames
const onTwos = t => onN(t, 2);
// jitter that holds per drawing: jit(key, amp, t) in [-amp, amp], stable within a boil drawing
// NOW: the frame being drawn (set by the timeline), so helpers can boil without threading t everywhere
let NOW = 0;
const jit = (key, amp, t = NOW) => (hash(key * 13.37 + BF(t) * 7.77) * 2 - 1) * amp;

// ------------------------------------------------------------------ keyframes
// kf(t, [[t0, v0, ease?], [t1, v1, ease?], ...]) : the ease on key i shapes the segment arriving at key i. Values may be arrays.
function kf(t, keys, dflt = 'io3') {
  if (t <= keys[0][0]) return keys[0][1];
  for (let i = 1; i < keys.length; i++) {
    if (t < keys[i][0]) {
      const [t0, v0] = keys[i - 1], [t1, v1, e] = keys[i];
      const u = ease(e || dflt, (t - t0) / (t1 - t0));
      return Array.isArray(v0) ? mixv(v0, v1, u) : lerp(v0, v1, u);
    }
  }
  return keys[keys.length - 1][1];
}
// damped spring response to a step at t0 (0 before, -> 1 after, with overshoot). k = stiffness (Hz), z = damping ratio
function spring(t, t0, k = 3, z = .35) {
  const x = t - t0; if (x <= 0) return 0;
  const w = TAU * k, wd = w * Math.sqrt(1 - z * z);
  return 1 - Math.exp(-z * w * x) * (Math.cos(wd * x) + (z * w / wd) * Math.sin(wd * x));
}
// decaying wobble kicked at t0 (0 at rest): for follow-through, hits, settles
const wobble = (t, t0, k = 4, decay = 5) => (t < t0 ? 0 : Math.sin((t - t0) * TAU * k) * Math.exp(-(t - t0) * decay));
// arc between two points with a height (thrown things)
const arcPt = (p0, p1, h, u) => [lerp(p0[0], p1[0], u), lerp(p0[1], p1[1], u) - 4 * h * u * (1 - u)];

// ------------------------------------------------------------------ the beat clock (from CUES, written by tools/audio_analyze.py)
const C = window.CUES || { bpm: 120, offset: 0, duration: 10, words: [], sections: [], beats: [], rms: [] };
const BPM = C.bpm, BEAT = 60 / BPM, BAR = BEAT * 4, OFFSET = C.offset;
const DUR = (window.PROJECT && PROJECT.duration) || C.duration;
const beatPos = t => (t - OFFSET) / BEAT;                // continuous beat number (0 = first downbeat)
const barPos = t => (t - OFFSET) / BAR;
const beatT = b => OFFSET + b * BEAT;                     // time of beat b
const barT = n => OFFSET + n * BAR;
const beatN = t => Math.floor(beatPos(t) + 1e-6);
// 1 on each beat, decaying. every = beats between pulses (0.5 = eighths, 4 = bars). phase in beats.
const pulse = (t, decay = 6, every = 1, phase = 0) => { const p = (beatPos(t) - phase) / every; return p < 0 ? 0 : Math.exp(-frac(p) * every * BEAT * decay); };
// loudness envelope (0..1-ish), for audio-reactive secondary motion (never for primary acting)
const loud = t => { const r = C.rms || [], i = t * 10, a = r[Math.floor(i)] || 0, b = r[Math.floor(i) + 1] || 0; return lerp(a, b, frac(i)) / .35; };
