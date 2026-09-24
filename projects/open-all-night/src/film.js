// film.js: what runs over every shot. Lyrics (unless the shot sets its own), the subtitle card.
PROJECT.overlay = (t, ret, s) => {
  if (ret.lyric !== false) drawLyric(t, ret.lyric || {});
  if (ret.subtitle && PROJECT.subtitleAt && PROJECT.subtitleAt(t)) {
    const a = clamp((t - 6.1) / .3) * (1 - clamp((t - 7.1) / .2));
    if (a > .5) type('a love song for the ads', 110, 180, { font: 'serif', size: 84, knock: true, knockInks: ['blue', 'black'] });
  }
};
