// timeline.js: the cut. Every shot boundary from STORYBOARD.md, locked to the song. Unbuilt shots show a slate.
const CUT = [
  [0.000, '01', 'sign on'], [3.977, '02', 'the block wakes'],
  [7.848, '03', 'the kid'], [11.72, '04', 'stars'], [15.59, '05', 'grandma, rome'], [19.46, '06', 'the sink'],
  [23.33, '07', 'underneath'], [25.84, '08', 'the blink'], [27.88, '09', 'sold'], [29.70, '10', 'everything opens'],
  [31.07, '11', 'hook: keep it open'], [34.24, '12', 'every kid gets a light'], [38.95, '13', 'the glance'], [41.94, '14', 'the world'], [45.06, '15', 'sign'],
  [46.56, '16', 'bakery at dawn'], [50.43, '17', 'the paper plane'], [54.30, '18', 'history'], [57.90, '19', 'the patron'],
  [62.04, '20', 'the poster'], [65.60, '21', 'the machine'], [67.56, '22', 'the choir'], [69.52, '23', 'the city sings'],
  [71.72, '24', 'hook: sunrise'], [74.94, '25', 'the skyline'], [78.95, '26', 'the wink'], [81.36, '27', 'the world lit'], [83.78, '28', 'a thousand signs'],
  [87.25, '29', 'asleep'],
];
const SHOT_FN = {};   // id -> fn, filled by the shot files
function slate(id, name) {
  const f = (t, lt, dur) => {
    flood('black', .0);
    ink(P(rect(0, 0, W, H)), { yellow: .0 });
    type(id, 110, 300, { font: 'arch', size: 220, wdth: 62, wght: 900, ink: 'black' });
    type(name, 110, 420, { font: 'serif', size: 90, ink: 'pink' });
    ink(P(rect(110, 470, (W - 220) * clamp(lt / dur), 10)), 'blue');
    return { lyric: { slot: 'll' } };
  };
  Object.defineProperty(f, 'name', { value: 's' + id + '_slate' });
  return f;
}
function registerCut() {
  shots(CUT.map(([t0, id, name]) => [t0, SHOT_FN[id] || slate(id, name)]));
}
