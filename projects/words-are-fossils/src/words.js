// words.js: the core sample. The whole film is one world column; the camera descends through it.
// Each word is data: a surface (today's word) + strata (older forms) + a plate (the root meaning, PICTO[name]).
// Every stop is cued to a spoken word of the narration (VO), so the camera arrives as the narrator names the layer.
//
// stop.cue = [voId, wordIndex, offsetSeconds]: arrive at that spoken word's start (+ offset)

const COL = { x: W / 2, stopY: 760 };          // where a stop's centre sits on screen (upper-middle; captions live below)
const WORDS = [
  { id: 'window', vo: '01_window', stops: [
    { kind: 'surface', text: 'window', label: 'ENGLISH · c. 1200', cue: [0, 0] },
    { kind: 'form', ink: 'ochre', font: 'black', text: 'vindauga', label: 'OLD NORSE', cue: [1, -.1] },
    { kind: 'split', ink: 'slate', font: 'black', parts: ['vindr', 'auga'], gloss: ['wind', 'eye'], label: 'OLD NORSE', cue: [4, -.2] },
    { kind: 'plate', ink: 'ox', picto: 'window', fig: 'fig. 1 · the wind-eye', cue: [5, .35] },
  ] },
  { id: 'companion', vo: '02_companion', stops: [
    { kind: 'surface', text: 'companion', label: 'ENGLISH · c. 1300', cue: [0, 0] },
    { kind: 'form', ink: 'ochre', font: 'black', text: 'compagnon', label: 'OLD FRENCH · 12TH C.', cue: [0, .95] },
    { kind: 'split', ink: 'slate', font: 'roman', parts: ['COM', 'PANIS'], gloss: ['with', 'bread'], label: 'LATIN', cue: [1, -.1] },
    { kind: 'plate', ink: 'ox', picto: 'companion', fig: 'fig. 2 · the bread-fellow', cue: [3, 0] },
  ] },
  { id: 'muscle', vo: '03_muscle', stops: [
    { kind: 'surface', text: 'muscle', label: 'ENGLISH · LATE 14TH C.', cue: [0, 0] },
    { kind: 'split', ink: 'slate', font: 'roman', parts: ['MUS', 'CULUS'], gloss: ['mouse', 'little'], label: 'LATIN', cue: [1, -.1] },
    { kind: 'plate', ink: 'ochre', picto: 'muscle', fig: 'fig. 3 · the little mouse', cue: [3, 0] },
  ] },
  { id: 'disaster', vo: '04_disaster', stops: [
    { kind: 'surface', text: 'disaster', label: 'ENGLISH · 1590s', cue: [0, 0] },
    { kind: 'split', ink: 'ochre', font: 'fell', parts: ['dis', 'astro'], gloss: ['ill', 'star'], label: 'ITALIAN', cue: [1, -.1] },
    { kind: 'plate', ink: 'slate', picto: 'disaster', fig: 'fig. 4 · the ill star', cue: [4, 0] },
  ] },
  { id: 'clue', vo: '05_clue', stops: [
    { kind: 'surface', text: 'clue', label: 'ENGLISH · 1590s', cue: [0, 0] },
    { kind: 'form', ink: 'ochre', font: 'black', text: 'clew', sub: 'a ball of thread', label: 'MIDDLE ENGLISH', cue: [1, -.1] },
    { kind: 'plate', ink: 'slate', picto: 'clue', fig: 'fig. 5 · Ariadne’s thread', cue: [5, 0] },
  ] },
  { id: 'salary', vo: '06_salary', stops: [
    { kind: 'surface', text: 'salary', label: 'ENGLISH', cue: [0, 0] },
    { kind: 'form', ink: 'ochre', font: 'roman', text: 'SALARIUM', label: 'LATIN', cue: [0, .9] },
    { kind: 'split1', ink: 'slate', font: 'roman', text: 'SAL', gloss: 'salt', label: 'LATIN', cue: [2, -.1] },
    { kind: 'plate', ink: 'ox', picto: 'salary', fig: 'fig. 6 · the salt (and a myth)', cue: [4, 0], stampWord: 11 },
  ] },
  { id: 'brainrot', vo: '07_brainrot', stops: [
    { kind: 'surface', text: 'brain rot', label: 'OXFORD WORD OF THE YEAR · 2024', cue: [0, 0] },
    { kind: 'form', ink: 'ochre', font: 'fellI', text: 'brain-rot', label: 'H. D. THOREAU · 1854', cue: [8, -.1] },
    { kind: 'plate', ink: 'slate', picto: 'brainrot', fig: 'fig. 7 · Walden', cue: [12, 0] },
  ] },
  { id: 'goodbye', vo: '08_goodbye', stops: [
    { kind: 'surface', text: 'goodbye', label: 'ENGLISH · 1590s', cue: [0, 0] },
    { kind: 'form', ink: 'ochre', font: 'fellI', text: 'godbwye', label: '1570s', cue: [0, .75] },
    { kind: 'form', ink: 'slate', font: 'black', text: 'God be with ye', label: 'LATE 14TH C.', cue: [1, -.1], size: 118 },
    { kind: 'plate', ink: 'ox', picto: 'goodbye', fig: 'fig. 8 · a blessing, worn smooth', cue: [1, 2.2] },
  ] },
];
const BAND = { surface: 980, form: 860, split: 900, split1: 860, plate: 1180, gap: 140 };

// lay the world out once: y ranges for every band, absolute cue times for every stop
const LAYOUT = (() => {
  const vo = id => VO.find(v => v.id === id);
  let y = 2200;                                   // above: the top surface (fresh layer + title) and the intro plate
  const stops = [];
  WORDS.forEach((w, wi) => {
    const V = vo(w.vo);
    w.y0 = y;
    w.stops.forEach((s, si) => {
      const h = BAND[s.kind];
      s.y0 = y; s.y1 = y + h; s.cy = y + h * .5 - (s.kind === 'plate' ? 40 : 0);
      const [k, off] = s.cue, wd = V.words[Math.min(k, V.words.length - 1)];
      s.t = wd.t0 + (off || 0);
      if (s.stampWord != null) s.stampT = V.words[s.stampWord].t0;
      s.word = w; s.wi = wi; s.si = si;
      stops.push(s);
      y += h;
    });
    w.y1 = y; y += BAND.gap;
  });
  return { stops, bottom: y };
})();

// camera: the world y at the screen's stop line. Moves arrive at each stop's cue; long moves between words take longer.
function camY(t) {
  const S = LAYOUT.stops, intro = { cy: 1250, t: 0 };
  const top = 1150;                                            // the outro framing: fresh layer, credit, ammonite, title
  const upStart = 75.2, upEnd = 78.4;                          // after goodbye: the rush back up through everything
  if (t >= upStart) return lerp(S[S.length - 1].cy, top, E.ioExpo(seg(t, upStart, upEnd)));
  let prev = intro;
  for (const s of S) {
    const dur = s.si === 0 ? (s.wi === 0 ? 1.1 : .95) : .6, arr = s.t - (s.si === 0 ? .85 : .12);   // surfaces arrive early: a beat to read the word
    if (t < arr - dur) return prev.cy;
    if (t < arr) return lerp(prev.cy, s.cy, E.io3((t - (arr - dur)) / dur));
    prev = s;
  }
  return prev.cy;
}
