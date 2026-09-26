// film.js: the whole film on the song clock (LOOPS.film, t = song seconds, 0-209.65). Each section is its own loop; this
// dispatches to it. Clocks (HANDOFF.md; the paper session): every paper-world loop takes LOCAL seconds from its start; Clawd's
// world (chorus, finale) takes song seconds. The sections tile exactly.
//   node engine/render.mjs projects/tsuzuku --loop=film --frames --workers=4 --clean &&
//   node engine/render.mjs projects/tsuzuku --encode --audio=projects/tsuzuku/out/paper_mix.wav      (song + the whole-film SFX stem)
{
  const SECTIONS = [                                       // [loop, start, end, clock]  ('local': t - start; 'song': t)
    ['prologue', 0, 9.0, 'local'], ['inklamp', 9.0, 12.7, 'local'], ['telling', 12.7, 24.0, 'local'], ['verse1', 24.0, 36.0, 'local'],
    ['exchange', 36.0, 61.0, 'local'],
    ['chorus', 61.0, 131.29, 'song'],                      // Clawd's world A (src/chorus.js)
    ['bridge', 131.29, 156.2, 'local'], ['inkcloseup', 156.2, 159.53, 'local'], ['bridgeB6', 159.53, 161.0, 'local'],
    ['inkstand', 161.0, 166.0, 'local'], ['bridgeB8', 166.0, 177.8, 'local'],
    ['finale', 177.8, 202.59, 'song'],                     // Clawd's world, the final chorus (src/finale.js)
    ['outro', 202.59, 209.65, 'local'],
  ];
  const FILM = { sections: SECTIONS, at: t => SECTIONS.find(([, a, b]) => t >= a && t < b) || SECTIONS[SECTIONS.length - 1] };
  window.FILM = FILM;
  LOOPS.film = t => {
    const [name, a, , clock] = FILM.at(t), L = LOOPS[name];
    X.setTransform(1, 0, 0, 1, 0, 0); X.globalAlpha = 1; X.globalCompositeOperation = 'source-over'; X.filter = 'none';
    if (!L) { X.fillStyle = '#000'; X.fillRect(0, 0, W, H); return; }
    L(clock === 'local' ? t - a : t);
  };
  LOOPS.film.len = 209.65;
}
