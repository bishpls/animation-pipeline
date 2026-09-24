// board.js: model sheets for the code characters
LOOPS.chars = t => {
  checker(80, C_.cream, '#F1DDB6', .0);
  const H8 = ['bow', 'headband', 'crown', 'cap', 'party', 'beret', 'hardhat', 'tophat'];
  H8.forEach((h, i) => clawd(120 + i * 225, 540, .8, { hat: h, seed: i * 5, pincer: i % 2 === 0, snip: (Math.sin(t * 8 + i) + 1) / 2, armL: i % 3 === 0 ? 1.2 : .3, armR: .9,
    eyes: ['open', 'happy', 'star', 'open', 'heart', 'happy', 'wide', 'shades'][i], mouth: i % 2 ? 'cat' : null, blush: i === 4, bowtie: i === 7,
    holdR: ['penlight', { sign: 'HELLO!' }, 'fan', 'mic', 'flag', null, null, null][i], penCol: C_.pink }));
  const P7 = ['idle', 'wave', 'sing', 'claw', 'up', 'point', 'shrug', 'offer', 'heart', 'tehe', 'cupEar'];
  const E7 = [{}, { eyes: 'happy', mouth: 'open' }, { eyes: 'closed', sing: .7 }, { eyes: 'star', mouth: 'grin' }, { eyes: 'happy', mouth: 'open', hop: 20 }, { eyes: 'wink', mouth: 'grin' },
    { eyes: 'open', mouth: 'cat', sweat: 1 }, { eyes: 'happy', mouth: 'smile' }, { eyes: 'shy', blush: 1, mouth: 'small' }, { eyes: 'wink', mouth: 'tongue', tilt: -.12 }, { eyes: 'side', mouth: 'o', look: [1, 0] }];
  P7.slice(0, 6).forEach((p, i) => idol(160 + i * 320, 1070, .78, { ...pose(p), ...E7[i] }));
};
LOOPS.chars.len = 2;
// the transformation void (magical-girl sparkle space), shared by the Seedance frames and the code shots around them
function tvoid(t, k = 1) {
  const g = X.createLinearGradient(0, 0, W, H);
  g.addColorStop(0, '#FFB3D9'); g.addColorStop(.35, '#C7B8FF'); g.addColorStop(.65, '#9FF0FF'); g.addColorStop(1, '#FFF3A8');
  X.fillStyle = g; X.fillRect(0, 0, W, H);
  X.save(); X.globalAlpha = .35; sunburst(W / 2, H / 2, 'rgba(0,0,0,0)', '#FFFFFF', 28, t * .15); X.restore();
  for (let i = 0; i < 70; i++) { const x = hash(i * 3.1) * W, y = hash(i * 7.7) * H, r = 6 + hash(i * 1.3) * 20, tw = .5 + .5 * Math.sin(t * 4 + i); sparkle(x, y, r * tw, '#FFFFFF', i); }
  glow(W / 2, H / 2, 700, 'rgba(255,255,255,1)', .6 * k);
}
LOOPS.tstart = t => { tvoid(t); clawd(W / 2, H / 2 + 200, 2.1, { eyes: 'closed', glow: 1, armL: .5, armR: .5 }); spark8(W / 2, H / 2 - 230, 70, C_.lemon, 6); glow(W / 2, H / 2 - 230, 200, 'rgba(255,240,150,1)', .9); };
LOOPS.tstart.len = 1;
LOOPS.tend = t => { tvoid(t); const i = IMG.k02_pose; const h = 1000; X.drawImage(i, W / 2 - i.width * h / i.height / 2, H - h - 20, i.width * h / i.height, h); };
LOOPS.tend.len = 1;
const kcBg = t => { sunburst(W / 2, H * .55, C_.pink, C_.lemon, 26, t * .2); dots(C_.white, 34, 6, .5, (x, y) => clamp(Math.hypot(x - W / 2, y - H * .55) / 1100)); };
const keyFrame = (name, h, y) => t => { kcBg(t); const i = IMG[name]; X.drawImage(i, W / 2 - i.width * h / i.height / 2, y, i.width * h / i.height, h); };
LOOPS.kcstart = keyFrame('k10a', 900, 180); LOOPS.kcstart.len = 1;
LOOPS.kcend = keyFrame('k10b', 1000, 40); LOOPS.kcend.len = 1;
