// film.js: what runs over every shot. Lyrics (unless the shot sets its own), the subtitle card.
PROJECT.overlay = (t, ret, s) => {
  // a finished line never carries across a cut into a new shot
  const st = lyricState(t);
  const spill = st && st.L.t1 < s.t0 - .02;
  // one lyric system: Kruger bars at a phone-legible size, unless a shot sets its own type (lyric: false) or opts out (noPlate)
  if (ret.lyric !== false && !spill) {
    const o = { ...(ret.lyric || {}) };
    if (!o.noPlate) { o.plate = o.plate || 'black'; o.size = Math.max(o.size || 0, 84); o.lh = 1.2; o.maxW = Math.min(Math.max(o.maxW || 0, 1300), 1700); }
    drawLyric(t, o);
  }
  if (ret.subtitle && PROJECT.subtitleAt && PROJECT.subtitleAt(t)) {
    const a = clamp((t - 6.1) / .3) * (1 - clamp((t - 7.1) / .2));
    if (a > .5) type('a love song for the ads', 110, 180, { font: 'serif', size: 84, knock: true, knockInks: ['blue', 'black'] });
  }
};
