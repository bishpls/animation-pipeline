// board.js: look development for the paper theatre
LOOPS.look = t => {
  flat(FP.sumi);
  screen(t, { lamp: [900, 380] });
  // far plane: rolling hills (depth .55: large and soft)
  shadow(c => { inkP(c, cutp([[150, 780], [400, 640], [700, 700], [1000, 610], [1300, 690], [1770, 620], [1770, 980], [150, 980]], 3, 3, .6), .55); }, .55);
  // mid plane: pines (depth .25)
  shadow(c => { for (let i = 0; i < 7; i++) { const x = 260 + i * 210 + (i % 2) * 40, y = 820, h = 170 + (i % 3) * 50;
      inkP(c, cutp([[x, y], [x - h * .28, y], [x, y - h], [x + h * .28, y]], 10 + i, 1.5, .5), .9); } }, .25);
  // near plane: the ground strip + the narrator, seated (depth 0: crisp)
  shadow(c => {
    inkP(c, cutp([[150, 900], [1770, 890], [1770, 980], [150, 980]], 30, 2, .5));
    // Fable, seated seiza in profile facing right: cushion, pleated skirt mass, torso, hooded head, sleeves, ribbon
    const x = 620, y = 900;
    inkP(c, cutp(rrect(x - 110, y - 30, 220, 34, 14), 41));                               // cushion (zabuton)
    inkP(c, cutp([[x - 95, y - 26], [x - 100, y - 130], [x + 70, y - 120], [x + 105, y - 28]], 42, 1.5));   // folded legs / skirt
    inkP(c, cutp([[x - 60, y - 120], [x - 70, y - 300], [x + 30, y - 310], [x + 55, y - 125]], 43, 1.5));  // torso (haori)
    inkP(c, cutp(blob([[x - 70, y - 300], [x - 88, y - 380], [x - 30, y - 440], [x + 40, y - 430], [x + 70, y - 370], [x + 58, y - 318], [x + 40, y - 300]], 4), 44, 1.2)); // hood
    inkP(c, cutp([[x + 40, y - 360], [x + 76, y - 350], [x + 80, y - 330], [x + 60, y - 318], [x + 40, y - 318]], 45, .8));   // profile face under the hood
    inkP(c, cutp([[x + 20, y - 270], [x + 120, y - 215], [x + 150, y - 150], [x + 70, y - 160], [x + 10, y - 200]], 46, 1.5));   // sleeve + arm holding the fan
    inkP(c, cutp([[x + 150, y - 150], [x + 230, y - 210], [x + 245, y - 160]], 47, .8));                        // the fan (open)
    for (let k = 0; k < 12; k++) { const a = -.1 + k * .08, r = 12 + k * 13; inkP(c, circle(x - 78 - Math.sin(t * 1.3 + k * .4) * k * 1.4, y - 320 + r, 5 - k * .2, 10)); }   // the ribbon (bookmark), trailing
    for (const [rx, ry] of [[x + 22, y - 262], [x + 104, y - 205], [x + 146, y - 158], [x - 20, y - 128]]) hole(c, circle(rx, ry, 4.5, 12));   // rivets: light through the pins
    hole(c, [[x + 60, y - 348], [x + 70, y - 347], [x + 66, y - 343]]);                  // one eye: a sliver of light
  }, 0);
  // Clawd as a visitor: a black keyline puppet with a clay-orange cellophane plate (misregistered), slit eyes of light
  shadow(c => {
    const x = 1240, y = 880, body = blob([[x - 90, y - 60], [x - 110, y - 200], [x - 70, y - 300], [x + 70, y - 300], [x + 110, y - 200], [x + 90, y - 60]], 4);
    inkP(c, cutp(body.map(([a, b]) => [a, b]), 51, 1.4));
    film(c, cutp(body.map(([a, b]) => [a + (a - x) * -.1 + 2, b + (b - (y - 180)) * -.12 + 2]), 52, 1.2), '#D97757', .9);   // the plate, inset + misregistered 2px
    for (const s of [-1, 1]) { inkP(c, cutp(rrect(x + s * 100 - 28, y - 330, 56, 60, 18), 53 + s)); }   // buns
    for (const s of [-1, 1]) hole(c, rrect(x + s * 34 - 6, y - 235, 12, 44, 5));                       // her eyes: tall slits of lantern light
    for (const [rx, ry] of [[x - 95, y - 150], [x + 95, y - 150]]) hole(c, circle(rx, ry, 4.5, 12));  // she gets rivets in this world
    c.strokeStyle = 'rgba(22,22,26,1)'; c.lineWidth = 4; c.beginPath(); c.moveTo(x, y - 60); c.lineTo(x - 20, 1000); c.stroke();   // the rod
  }, .08);
  butai(t);
  // the page strip below the stage, where lyrics are pressed
  X.fillStyle = FP.washi; X.fillRect(0, 1000, W, 80); texture(.5);
  press('Once upon a time there was a crab,', 960, 1052, t, .05, { align: 'center', size: 44 });
  pressV('むかしむかし', 1830, 150, t, .1, { size: 44 });
  // film grain + flicker (stop motion)
  X.save(); X.globalCompositeOperation = 'overlay'; X.globalAlpha = .18; X.fillStyle = X.createPattern(GRAIN[BF(t) % 4], 'repeat'); X.fillRect(0, 0, W, H); X.restore();
};
LOOPS.look.len = 2;
