// film.js: what runs over every shot. Lyrics (unless the shot sets its own), the subtitle card.
PROJECT.overlay = (t, ret, s) => {
  if (ret.lyric !== false) drawLyric(t, ret.lyric || {});
  if (ret.subtitle && PROJECT.subtitleAt && PROJECT.subtitleAt(t)) {
    const a = clamp((t - 4.3) / .3) * (1 - clamp((t - 6.9) / .3));
    type('a love song for the ads', 110, 180, { font: 'serif', size: 84, knock: a > .5, knockInks: ['blue', 'black'] });
  }
};
