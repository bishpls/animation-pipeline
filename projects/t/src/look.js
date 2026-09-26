// look.js: *t*. Two riso inks on cream stock. Orange is now (the pen, the line being drawn, the sun); blue is then
// (every printed line, the hills, the type). The present is paper: ink arrives when a bar is printed.
const FONT_FILES = {
  mono: 'assets/fonts/JetBrainsMono.ttf', // wght 100-800: the counter and the source
  serifI: 'InstrumentSerif-Italic.ttf',                      // the spoken lines, and the counter's t
};
const LOOK = {
  riso: {
    paper: '#f2ece1', cell: 8, misreg: 1.3,
    inks: [
      { name: 'orange', hex: '#ff6c2f', angle: 75 },
      { name: 'blue', hex: '#3d5588', angle: 15 },
    ],
  },
};

// the page: where things sit (px, 1080x1920). Text stays out of the bottom 420 px and the right 140 px.
const PAGE = {
  horizon: 860,        // the vanishing line: a ridge infinitely far away would sit here
  front: 1500,         // the baseline of the line being drawn now (above the bottom 420 px, where the platform's UI sits)
  gap: .9,             // extra depth on the first step back
  hmax: 460,           // the height of the loudest sound, at the front
  depthK: .34,         // perspective: a ridge d bars back sits at depth z = 1 + K d
  depthX: .045,        // and narrows toward the centre by 1 / (1 + X d)
  counterY: 212, counterSize: 62,
  textY: 470, textSize: 112, lead: 124,
  sunX: 792,
};
