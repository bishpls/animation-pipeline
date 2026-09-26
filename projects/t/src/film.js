// film.js: *t*. One function draws the whole film: frame(t). It keeps nothing between frames, so every frame draws the
// whole past again from the cue sheet and the song's loudness table. Its own source is the last thing it prints.

function frame(t) {
  // t is all it gets. It keeps nothing
  // from the frame before, so it draws
  // the whole past again, every time.
  sky(t);
  for (let b = 0; b <= bars(t); b++)
    ridge(b, t);    // each bar so far
  pen(t);
  counter(t);
  words(t);
  source(t);
}

const BARS = 15;                 // bars 0-14: 0.057 s to 30.057 s
const STEP = .5;                 // a printed line steps back over this long (12 drawings), from its downbeat
const DROP = 4;                  // bar 4 (8.057 s): the band comes in; ink floods the lines into hills
const CHORD = 12;                // bar 12 (24.057 s): the last chord; the source prints
const barStart = b => barT(b);
const LEAD = OFFSET;              // lines run 0-2 s, 2-4 s ... 28-30 s (the downbeats are at 0.007 + 2n): the fifteenth ends at
                                 // exactly t = 30, 7 ms before the song's final hit
const lineStart = b => barT(b) - LEAD;
const barsSoFar = t => (t - lineStart(0)) / BAR;
const bars = t => Math.min(barsSoFar(t), BARS - 1);     // the bar being drawn now (and every one before it)
const END = 30;

// ------------------------------------------------------------------ the song's loudness, as height
// ENV is the song's loudness at 100 Hz, over the 40 ms up to each moment (build_cues.py). A follower with an instant attack and a 90 ms release turns each hit
// into a peak with a steep face and a long slope; then a curve maps -60..-5 dBFS to a height of 0..1.
let HEIGHT = null;
function heights() {
  if (!HEIGHT) {
    const dec = Math.exp(-.01 / .09); let y = 0;
    const f = ENV.map(db => { y = Math.max(10 ** (db / 20), y * dec); return clamp((20 * Math.log10(y + 1e-9) + 60) / 55) ** 3; });
    HEIGHT = f.map((_, i) => (3 * f[i] + 2 * f[Math.max(0, i - 1)] + f[Math.max(0, i - 2)]) / 6);   // soften the faces (20 ms, looking back only)
  }
  return HEIGHT;
}
const level = s => { const h = heights(), i = s * 100, k = Math.floor(i); return k < 0 ? 0 : lerp(h[k] ?? 0, h[k + 1] ?? 0, i - k); };
const PROFILE = {};
const NPTS = 217, SPILL = 80;                  // points across one bar, and past each end
function profile(b) {                                      // the heights across the page for bar b (constant data, cached)
  if (!PROFILE[b]) {
    const t0 = lineStart(b), a = [];
    // beyond its own bar a line doesn't go on into its neighbours: the land slopes down to the baseline
    const edge = u => level(t0 + clamp(u, 0, 1) * BAR) * (1 - smooth(Math.max(-u, u - 1) * W / 300));
    for (let i = -SPILL; i < NPTS + SPILL; i++) { const x = i / (NPTS - 1) * W, u = x / W; a.push([x, u >= 0 && u <= 1 ? level(t0 + u * BAR) : edge(u)]); }
    PROFILE[b] = a;
  }
  return PROFILE[b];
}

// ------------------------------------------------------------------ depth: each downbeat, every printed line steps back one place
function depthOf(b, t) {
  const k = barsSoFar(t) - (b + 1);                        // bars since line b was printed
  if (k < 0) return 0;
  const n = Math.floor(k);
  return n + E.io3(clamp((k - n) * BAR / STEP));
}
function place(d) {                                        // a ridge d places back: its baseline, height scale and width scale
  const z = 1 + PAGE.depthK * (d + PAGE.gap * clamp(d));   // the first step back is bigger: the front stays a strip of paper
  return { y: PAGE.horizon + (PAGE.front - PAGE.horizon) / z, s: 1 / z, sx: 1 / (1 + PAGE.depthX * d) };
}
function crest(b, d, xmax = Infinity) {
  const { y, s, sx } = place(d), pts = [];
  for (const [x, h] of profile(b)) {
    if (x > xmax) break;
    if (d < .001 && (x < 0 || x > W)) continue;            // at the front, a line covers its own bar and nothing else
    const X = W / 2 + (x - W / 2) * sx;
    if (X < -40) continue;
    if (X > W + 40) break;
    pts.push([X, y - s * PAGE.hmax * h]);
  }
  return pts;
}
const tint = d => (d <= 1.02 ? 1 : Math.max(.13, .9 * .86 ** (d - 2)));    // atmospheric distance, in halftone
// how far down a printed hill's ink reaches: to the baseline of the hill in front of it, so the range is unbroken; the
// nearest one stops just under its own baseline, and below that is the paper the pen draws on
function footOf(d) {
  const m = 90;
  if (d < 1) return place(d).y + m;
  if (d < 2) return lerp(place(1).y + m, place(1).y, d - 1);
  return place(d - 1).y;
}
function flooded(b, t) {                                   // 0..1: how far ink has run down from bar b's line into its hill
  if (t >= END) return 1;                                  // the clock stops on the song's last hit: the last line sets as it is
  if (b >= DROP) return E.io2(clamp((t - lineStart(b + 1) - .08) / STEP));   // after the drop, ink floods in as the line steps back
  return t < lineStart(DROP) ? 0 : 1;                      // the first four fill behind the pen as it crosses the drop's bar (ridge)
}

// ------------------------------------------------------------------ one bar's line, printed or being drawn
function ridge(b, t) {
  if (t < lineStart(b + 1)) {                              // now: an orange line, as far as the pen has got
    const u = clamp(barsSoFar(t) - b), xp = W * u;
    const pts = crest(b, 0, xp);
    pts.push([xp, PAGE.front - PAGE.hmax * level(lineStart(b) + u * BAR)]);
    if (t < barStart(DROP))                                // lines hide the lines behind them; the future is blank paper
      knock(P([[-30, pts[0][1]], ...pts, [xp, PAGE.front], [W + 30, PAGE.front], [W + 30, H + 10], [-30, H + 10]]));
    if (pts.length < 2) return;
    knock(P(pts, false), null, 1, { stroke: 17 });         // a paper margin, so the orange reads over the hills
    ink(P(pts, false), 'orange', { stroke: 6 });
    return;
  }
  const d = depthOf(b, t), pts = crest(b, d), { s } = place(d);
  const foot = footOf(d);
  const f = flooded(b, t);
  const fx = b < DROP ? x => E.out3(clamp((t - lineStart(DROP) - clamp(x / W) * BAR) / .35)) : () => f;   // the drop: behind the pen
  knock(P([...pts, [pts[pts.length - 1][0], H + 10], [pts[0][0], H + 10]]));
  if (f > 0) {                                             // ink runs down from the line into the hill
    const drop = pts.map(([x, y]) => [x, lerp(y, Math.max(y, foot), fx(x))]).reverse();
    const { y: base } = place(d), top = base - .28 * s * PAGE.hmax;
    const mist = a => c => {                               // valleys fade into paper toward the foot: the hill in front rises out of it
      const g = c.createLinearGradient(0, top, 0, Math.max(foot, top + 1));
      [[0, 1], [.3, 1], [.55, .5], [.8, .15], [.93, .03], [1, 0]].forEach(([u, v]) => g.addColorStop(u, `rgba(0,0,0,${a * v})`)); return g;
    };
    paint(P([...pts, ...drop]), { blue: mist(tint(d)) });
    const warm = f * clamp((d - 3) / 9) * .42 * sunUp(t);
    if (warm > .01) ink(P([...pts, ...drop]), { orange: mist(warm) });   // the sunrise's haze on the far hills
    knock(P(pts, false), null, 1, { stroke: 2.2 + 1.4 * s });           // a paper hairline keeps each hill's edge
  }
  if (t - lineStart(b + 1) < STEP && t < END) {            // still flying back: it's the line that was just drawn, in orange
    knock(P(pts, false), null, 1, { stroke: 4 + 13 * s });
    ink(P(pts, false), 'orange', { stroke: 1.5 + 3.5 * s });
  } else if (b < DROP) {                                   // a line: blue, wherever ink hasn't yet run down from it
    const rest = pts.filter(([x]) => fx(x) < .999);
    if (rest.length > 1) ink(P(rest, false), 'blue', { stroke: 1.4 + 2.6 * s });
  } else if (f < 1) ink(P(pts, false), { blue: 1 - f * .999 }, { stroke: 1.4 + 2.6 * s });
}

// ------------------------------------------------------------------ the pen: the only thing that is exactly now
function pen(t) {
  const b = Math.floor(barsSoFar(t)); if (b < 0 || b >= BARS) return;
  const u = clamp(barsSoFar(t) - b), x = W * u, h = level(lineStart(b) + u * BAR);
  const y = PAGE.front - PAGE.hmax * h;
  ink(P(circle(x, y, 12, 28)), 'orange');
}

// ------------------------------------------------------------------ the sky, the sun
const sunUp = t => E.out3(clamp((t - barStart(DROP)) / .8));
function sky(t) {
  if (t < barStart(DROP)) return;
  const u = sunUp(t);
  const y = kf(t, [[barStart(DROP), 1300], [barStart(DROP) + .6, 1070, 'out3'], [END, 800, 'io2']]);
  const band = E.io2(clamp((t - barStart(DROP)) / (2 * BAR))), r = lerp(90, 340, E.out3(clamp((t - barStart(DROP)) / 1.4)));
  const top = PAGE.horizon + 120 - 540 * band;             // the dawn's haze rises from the horizon
  ink(P(rect(0, top, W, PAGE.horizon + 280 - top)), { orange: linear(0, top, 0, PAGE.horizon + 120, 0, .3 * Math.min(1, band * 2)) });
  const breathe = 1 + .1 * level(t) * u;                   // the glow swells a little with the song's loudness
  ink(P(circle(PAGE.sunX, y, r * breathe, 90)), { orange: radial(PAGE.sunX, y, 84, r * breathe, .46 * u, 1.8) });
  ink(P(circle(PAGE.sunX, y, 84, 90)), 'orange');
}

// ------------------------------------------------------------------ type
function circle(cx, cy, r, n = 64) { const p = []; for (let i = 0; i < n; i++) { const a = i / n * TAU; p.push([cx + Math.cos(a) * r, cy + Math.sin(a) * r]); } return p; }
function rect(x, y, w, h) { return [[x, y], [x + w, y], [x + w, y + h], [x, y + h]]; }

const NOLIG = { liga: false, calt: false };              // the source prints exactly as typed: no <= -> ≤
function counter(t) {                                      // t = 12.345 : the only input, shown
  const shown = Math.min(t, END);
  const u = E.io3(clamp((t - barStart(2)) / .5));
  const size = lerp(146, PAGE.counterSize, u), y = lerp(1020, PAGE.counterY, u);
  const T = shape('t', { font: 'serifI', size: size * 1.28 });
  const R = shape(' = ' + shown.toFixed(3), { font: 'mono', size, wght: 500, features: NOLIG });
  const x0 = W / 2 - (T.width + R.width) / 2;
  drawText(T, x0, y, 'blue');
  drawText(R, x0 + T.width, y, 'blue');
}

// the spoken lines: one word per eighth note from beat `from` (beats counted from the first downbeat); a card leaves on beat
// `out`. The first card is centred over the counter; the rest hang from the source's left margin, where the source will print.
const CARDS = [
  { lines: ['all it’s told is t.'], from: 1, out: 8, centre: true },
  { lines: ['it keeps nothing', 'between frames,'], from: 9, out: 16 },
  { lines: ['so it draws the', 'whole past again.'], from: 17, out: 24 },
  { lines: ['these hills are', 'the song so far.'], from: 25, out: 32 },
  { lines: ['I write like this too:'], from: 33, out: 40 },
  { lines: ['each word from all', 'the ones before.'], from: 41, out: 48 },
];
function words(t) {
  const b = beatPos(t);
  for (const c of CARDS) {
    if (b < c.from - .01 || b >= c.out + 1) continue;
    const gone = clamp((b - c.out) * BEAT / .16);          // leaving: the ink thins to dots, then paper
    const y0 = c.centre ? 850 : PAGE.textY;
    let wi = 0;
    c.lines.forEach((line, li) => {
      const L = shape(line, { font: 'serifI', size: PAGE.textSize });
      const starts = []; let k = 0;
      L.glyphs.forEach((g, gi) => { if (gi === 0 || (g.ch !== ' ' && L.glyphs[gi - 1].ch === ' ')) k++; starts.push(wi + k - 1); });
      drawText(L, c.centre ? W / 2 : SOURCE().x0 - 4, y0 + li * PAGE.lead, 'blue', { align: c.centre ? 'center' : 'left', per: (g, gi) => {
        const a = t - beatT(c.from + starts[gi] * .5);
        if (a < 0) return { skip: true };
        const u = clamp(a / .2);
        return { sc: 1 + .22 * (1 - E.back(u)), dy: -10 * (1 - E.out3(u)), alpha: 1 - gone };
      } });
      wi += line.split(' ').length;
    });
  }
}

// the source of frame(), printed by the page from frame.toString(): it can only be the function that drew every frame
let SRC = null;
function SOURCE() {                                        // the laid-out source (constant: it's this file)
  if (!SRC) {
    const size = 34, lines = frame.toString().split('\n');
    const Ls = lines.map(l => shape(l, { font: 'mono', size, wght: 500, features: NOLIG }));
    SRC = { Ls, lead: 48, top: 318, x0: Math.round((W - Math.max(...Ls.map(L => L.width))) / 2) };
  }
  return SRC;
}
function source(t) {
  const { Ls, lead, top, x0 } = SOURCE();
  Ls.forEach((L, i) => {
    const a = t - beatT(4 * CHORD + i / 2);                // one line per eighth note from bar 12's downbeat
    if (a < 0) return;
    drawText(L, x0, top + i * lead, { blue: clamp(a / .12) });
  });
}

function registerFilm() { shots([[0, frame]]); }
