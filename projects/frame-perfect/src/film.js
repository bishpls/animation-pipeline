// FRAME PERFECT: the composite. The picture is the director's capture of Super Smash Bros. Melee (plates, one per game frame,
// frame 0 = film time 0), with the engine's type on top: the title over the Arwing arrival, a small frame/beat readout during
// the fight that flashes on each logged hit (assets/hits.js, from the director's HIT log), and the end card.
const PL = plate('assets/plates', { n: 2040, fps: 60, t0: 0, ext: 'jpg' });
const WHITE = '#f4f1ea', ACC = '#ffd84d';

function txt(str, x, y, o) {                       // plain-mode type: the engine's glyph outlines, filled on X
  const L = shape(str, o), x0 = o.align === 'center' ? x - L.width / 2 : o.align === 'right' ? x - L.width : x;
  const p = new Path2D();
  L.glyphs.forEach((g, i) => { if (g.ch !== ' ') p.addPath(glyphPath(g, x0 + g.x, y + g.y + (o.dy ? o.dy(i) : 0))); });
  X.fillStyle = o.fill || WHITE; X.fill(p);
  return L;
}
const fade = (t, a, b, r = .35) => clamp(Math.min((t - a) / r, (b - t) / r), 0, 1);

function title(t) {                                // 0.2-1.95 s: only the wide shot of the Arwings arriving (it cuts at 2.0)
  const a = fade(t, .2, 1.96, .3);
  if (a <= 0) return;
  X.save(); X.globalAlpha = a;
  const word = 'FRAME PERFECT', n = word.length;
  txt(word, W / 2, 470, { font: 'big', size: 190, wght: 800, track: .04, align: 'center',
    dy: i => 30 * (1 - E.out3(clamp((t - .2 - i * .035) / .35, 0, 1))) });
  X.globalAlpha = a * fade(t, .75, 1.96, .3);
  txt('a Melee fight written on the beat', W / 2, 560, { font: 'serif', size: 52, align: 'center' });
  X.restore();
}

function readout(t) {                              // the fight: game frame, bar and beat; lights up on each hit
  if (t < 6.0 - 16 / 60 || t >= 31.3) return;
  const f = Math.round(t * 60), b = beatPos(t), bar = Math.floor(b / 4) + 1, beat = Math.floor(b % 4) + 1;
  const h = HITS.find(e => f >= e.f && f < e.f + 9);
  const a = fade(t, 5.7, 31.3, .3), k = h ? 1 - (f - h.f) / 9 : 0;
  X.save();
  X.globalAlpha = a * .5; X.fillStyle = '#07060c';                    // a backing, so the readout reads over any shot
  X.beginPath(); X.roundRect(44, H - 142, 470, 104, 14); X.fill();
  X.globalAlpha = a * .9;
  const s = `f${String(f).padStart(4, '0')}   bar ${String(bar).padStart(2, ' ')}  beat ${beat}`;
  txt(s, 64, H - 58, { font: 'arch', size: 30, wght: 600, wdth: 100, fill: WHITE });
  if (h) {
    X.globalAlpha = a * k;
    txt(`HIT  ${h.who} ${h.move}`, 64, H - 100, { font: 'arch', size: 30, wght: 800, fill: ACC });
  }
  X.restore();
}

function endcard(t) {                              // 31.3-34.0, over Fox's close-up
  const a = fade(t, 31.25, 34.2, .45);
  if (a <= 0) return;
  X.save(); X.globalAlpha = a * .55; X.fillStyle = '#000'; X.fillRect(0, 0, W, H); X.globalAlpha = a;
  txt('FRAME PERFECT', 120, 330, { font: 'big', size: 120, wght: 800, track: .04 });
  const lines = [
    `Every input was written as code on the song's beat grid: ${HITS.length} hits, every one on its frame.`,
    'Super Smash Bros. Melee (NTSC 1.02), rebuilt from the doldecomp decompilation,',
    'played by a director compiled into the game, captured frame by frame in Dolphin.',
    'No player touched a controller. Song: ElevenLabs Music. Direction, capture and composite: code.',
  ];
  lines.forEach((l, i) => txt(l, 124, 420 + i * 54, { font: 'arch', size: 34, wght: 500, fill: i ? '#d8d4ea' : WHITE }));
  X.restore();
}

LOOPS.film = t => {
  PL.draw(X, t, 0, 0, W, H);
  title(t); readout(t); endcard(t);
};
LOOPS.film.len = 34.0;
shots([[0, t => LOOPS.film(t)]]);
