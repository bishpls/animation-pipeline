// globe.js: the Earth at night as a riso graphic. A disc of night, land as a dot matrix, city lights in yellow,
// pink arcs and pings between cities, and a sunrise terminator.
//
//   globe(cx, cy, R, o)
//     o.lon0 (deg, the longitude facing us; animate it to turn), o.lat0 (deg tilt, default 18)
//     o.night: ink spec for the night disc (default { black: 1 })   o.land: ink spec for land dots (default: paper, knocked out; o.landK amount)
//     o.lights: 0..1 fraction of city lights on (a wave out from o.from city, default 'nyc')   o.t: time (twinkle, pings)
//     o.arcs: [{ a: 'nyc', b: 'rome', t0, dur }] travelling pink arcs (drawn from a to b, then a comet tail)
//     o.pings: [{ city, t0 }] expanding pink rings     o.pingAll: t0 -> every lit city pings in a wave
//     o.sun: longitude (deg) of the subsolar point -> day side printed yellow, lights only at night; null = all night
//     o.dotR: land-dot radius scale   o.arcW: arc stroke scale
//   globeProject(lat, lon, o) -> [x, y, z] (relative to the centre, R = 1; z > 0 is facing us)
//   CITIES: { key: [lat, lon] }

const CITIES = {
  nyc: [40.7, -74], la: [34, -118], chi: [41.9, -87.6], tor: [43.7, -79.4], mex: [19.4, -99.1], sao: [-23.5, -46.6], ba: [-34.6, -58.4],
  bog: [4.7, -74], lima: [-12, -77], scl: [-33.4, -70.6], lon: [51.5, -.1], par: [48.9, 2.35], rome: [41.9, 12.5], ber: [52.5, 13.4],
  mad: [40.4, -3.7], mos: [55.8, 37.6], ist: [41, 29], cai: [30, 31.2], lag: [6.5, 3.4], nai: [-1.3, 36.8], jnb: [-26.2, 28],
  kin: [-4.3, 15.3], dxb: [25.2, 55.3], teh: [35.7, 51.4], kar: [24.9, 67], bom: [19, 72.8], del: [28.6, 77.2], dac: [23.8, 90.4],
  bkk: [13.7, 100.5], sin: [1.35, 103.8], jak: [-6.2, 106.8], man: [14.6, 121], bei: [39.9, 116.4], sha: [31.2, 121.5],
  seo: [37.6, 127], tok: [35.7, 139.7], syd: [-33.9, 151.2], akl: [-36.8, 174.8], anc: [61.2, -149.9], rek: [64.1, -21.9], hnl: [21.3, -157.9],
};
const LAND = [
  [[-168, 66], [-162, 70], [-141, 70], [-128, 70], [-115, 68], [-95, 72], [-82, 73], [-75, 68], [-65, 60], [-60, 55], [-56, 50], [-66, 45], [-70, 42], [-75, 38], [-76, 35], [-81, 31], [-80, 25], [-83, 29], [-90, 30], [-97, 27], [-97, 22], [-92, 18], [-87, 21], [-88, 16], [-83, 10], [-79, 9], [-85, 11], [-92, 14], [-105, 20], [-110, 24], [-112, 30], [-117, 32], [-121, 35], [-124, 40], [-124, 46], [-127, 50], [-133, 55], [-140, 59], [-150, 60], [-158, 57], [-165, 60]],
  [[-73, 78], [-60, 82], [-30, 83], [-20, 75], [-22, 70], [-40, 65], [-45, 60], [-52, 64], [-55, 70]],
  [[-80, 9], [-72, 12], [-62, 10], [-52, 5], [-50, 0], [-45, -2], [-35, -6], [-39, -14], [-41, -22], [-48, -26], [-53, -34], [-58, -38], [-65, -42], [-68, -50], [-72, -54], [-75, -50], [-74, -40], [-72, -30], [-71, -18], [-76, -14], [-81, -6], [-80, 1], [-78, 7]],
  [[-10, 36], [-9, 43], [-1, 44], [-4, 48], [2, 51], [8, 54], [10, 57], [5, 59], [6, 62], [14, 68], [22, 71], [30, 70], [40, 68], [55, 70], [70, 73], [80, 73], [100, 77], [112, 74], [130, 72], [140, 72], [160, 70], [170, 67], [180, 65], [180, 62], [163, 60], [157, 51], [155, 58], [143, 59], [137, 54], [140, 48], [133, 43], [129, 41], [126, 37], [122, 40], [121, 31], [117, 24], [110, 21], [108, 16], [109, 12], [105, 9], [104, 1], [100, 7], [98, 16], [94, 17], [91, 22], [88, 22], [80, 15], [77, 8], [73, 19], [67, 25], [58, 25], [57, 20], [52, 16], [44, 12], [42, 16], [35, 28], [35, 33], [36, 36], [30, 36], [27, 37], [26, 40], [23, 38], [21, 40], [19, 42], [16, 41], [18, 40], [16, 38], [15.5, 38], [12, 42], [10, 44], [8, 44], [3, 43], [3, 40], [-1, 37], [-6, 36]],
  [[-5, 50], [1, 51], [2, 53], [-1, 55], [-3, 58], [-6, 58], [-5, 55], [-3, 54], [-5, 52]],
  [[-10, 52], [-6, 52], [-6, 55], [-10, 54]],
  [[-17, 21], [-16, 28], [-9, 32], [-5, 36], [10, 37], [11, 33], [20, 31], [25, 32], [32, 31], [35, 28], [43, 12], [51, 12], [48, 5], [40, -3], [40, -11], [35, -20], [33, -26], [27, -34], [20, -35], [17, -29], [12, -17], [13, -5], [9, 4], [5, 6], [-8, 5], [-13, 8], [-17, 15]],
  [[44, -25], [47, -25], [50, -15], [49, -12], [44, -17]],
  [[114, -22], [122, -18], [130, -12], [137, -12], [142, -11], [145, -15], [153, -25], [150, -37], [141, -38], [131, -31], [115, -34]],
  [[130, 31], [135, 34], [140, 35], [142, 39], [141, 45], [140, 41], [136, 37], [132, 34]],
  [[95, 5], [106, -6], [104, -5], [98, 0]], [[109, 1], [117, 7], [119, 1], [116, -4], [110, -3]], [[106, -6], [114, -7], [114, -8.5], [106, -7.5]],
  [[131, -1], [141, -3], [150, -10], [141, -9], [137, -5]], [[172, -34], [178, -38], [174, -41], [172, -44], [167, -46], [171, -41], [174, -37]],
  [[120, 18], [122, 18], [126, 7], [122, 7]], [[-25, 66], [-13, 66], [-14, 64], [-22, 63]],
];
function _inPoly(x, y, poly) { let c = false; for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) { const [xi, yi] = poly[i], [xj, yj] = poly[j]; if (((yi > y) !== (yj > y)) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) c = !c; } return c; }
// land dots on an (approximately) equal-area grid; city-light dots clustered around the cities
const GLOBE_DOTS = (() => {
  const land = [];
  for (let lat = -58; lat <= 82; lat += 2.1) {
    const step = 2.1 / Math.max(.2, Math.cos(lat * D2R));
    for (let lon = -180; lon < 180; lon += step) {
      const jl = lon + (hash(lat * 3.1 + lon) - .5) * step * .3;
      if (LAND.some(p => _inPoly(jl, lat, p))) land.push([lat, jl]);
    }
  }
  const lights = [], R = rng(21);
  for (const [k, [la, lo]] of Object.entries(CITIES)) {
    const n = 7 + Math.floor(R() * 7);
    for (let i = 0; i < n; i++) { const r = Math.sqrt(R()) * (i ? 3.2 : 0), a = R() * TAU; lights.push({ lat: la + Math.sin(a) * r * .8, lon: lo + Math.cos(a) * r / Math.max(.3, Math.cos(la * D2R)), s: i ? .55 + R() * .6 : 1.5, city: k, id: lights.length }); }
  }
  // scattered small-town lights over land
  land.forEach(([la, lo], i) => { if (hash(i * 1.7) > .86 && la > -45 && la < 70) lights.push({ lat: la, lon: lo, s: .45, city: null, id: lights.length }); });
  return { land, lights };
})();

function globeProject(lat, lon, o) {
  const la = lat * D2R, dl = (lon - (o.lon0 || 0)) * D2R, l0 = (o.lat0 ?? 18) * D2R;
  const x = Math.cos(la) * Math.sin(dl);
  const y = -(Math.cos(l0) * Math.sin(la) - Math.sin(l0) * Math.cos(la) * Math.cos(dl));
  const z = Math.sin(l0) * Math.sin(la) + Math.cos(l0) * Math.cos(la) * Math.cos(dl);
  return [x, y, z];
}
function _angDist(a, b) { const [la1, lo1] = a.map(v => v * D2R), [la2, lo2] = b.map(v => v * D2R); return Math.acos(clamp(Math.sin(la1) * Math.sin(la2) + Math.cos(la1) * Math.cos(la2) * Math.cos(lo1 - lo2), -1, 1)); }
function _slerpLL(a, b, u) {
  const v = ([la, lo]) => [Math.cos(la * D2R) * Math.cos(lo * D2R), Math.cos(la * D2R) * Math.sin(lo * D2R), Math.sin(la * D2R)];
  const p = v(a), q = v(b), d = Math.acos(clamp(p[0] * q[0] + p[1] * q[1] + p[2] * q[2], -1, 1)) || 1e-6;
  const s0 = Math.sin((1 - u) * d) / Math.sin(d), s1 = Math.sin(u * d) / Math.sin(d);
  const r = [p[0] * s0 + q[0] * s1, p[1] * s0 + q[1] * s1, p[2] * s0 + q[2] * s1];
  return [Math.asin(clamp(r[2], -1, 1)) / D2R, Math.atan2(r[1], r[0]) / D2R];
}
// is a lat/lon on the day side for subsolar longitude sun (sun over the equator)
const _isDay = (lat, lon, sun) => sun != null && Math.cos(lat * D2R) * Math.cos((lon - sun) * D2R) > 0;

function globe(cx, cy, R, o = {}) {
  const t = o.t ?? NOW, night = o.night || { black: 1 };
  const disc = P(cut(circle(cx, cy, R, 96), 777, Math.min(2, R * .004), .6));
  paint(disc, night);
  // day side (sunrise): the projected hemisphere facing the sun, printed yellow
  if (o.sun != null) {
    const sv = globeProject(0, o.sun, o);                       // sun direction in view space
    const len2 = Math.hypot(sv[0], sv[1]) || 1e-6;
    const a = [-sv[1] / len2, sv[0] / len2, 0];                 // in the screen plane, perpendicular to the sun's projection
    const b = [sv[1] * a[2] - sv[2] * a[1], sv[2] * a[0] - sv[0] * a[2], sv[0] * a[1] - sv[1] * a[0]];   // s x a
    const pts = [];
    const th0 = Math.atan2(a[1], a[0]);
    const side = (sv[0] * Math.cos(th0 + Math.PI / 2) + sv[1] * Math.sin(th0 + Math.PI / 2)) > 0 ? 1 : -1;
    for (let i = 0; i <= 48; i++) { const th = th0 + side * i / 48 * Math.PI; pts.push([cx + Math.cos(th) * R, cy + Math.sin(th) * R]); }
    const vis = b[2] >= 0;                                      // which half of the terminator circle faces us
    for (let i = 0; i <= 48; i++) { const ph = vis ? Math.PI - i / 48 * Math.PI : Math.PI + i / 48 * Math.PI; const P3 = [Math.cos(ph) * a[0] + Math.sin(ph) * b[0], Math.cos(ph) * a[1] + Math.sin(ph) * b[1]]; pts.push([cx + P3[0] * R, cy + P3[1] * R]); }
    if (sv[2] > .999) paint(disc, { yellow: 1 }); else if (Math.hypot(sv[0], sv[1]) > 1e-3) paint(P(pts), o.day || { yellow: 1 });
  }
  // land: a dot matrix, foreshortened toward the limb
  const dr = R * .0078 * (o.dotR || 1), land = new Path2D(), landDay = new Path2D();
  for (const [la, lo] of GLOBE_DOTS.land) {
    const [x, y, z] = globeProject(la, lo, o); if (z <= .02) continue;
    const r = dr * (.45 + .55 * Math.sqrt(z));
    (_isDay(la, lo, o.sun) ? landDay : land).moveTo(cx + x * R + r, cy + y * R), (_isDay(la, lo, o.sun) ? landDay : land).arc(cx + x * R, cy + y * R, r, 0, TAU);
  }
  // single-ink logic (no registration fringes): night land = paper dots knocked out of the night; day land = pink overprint
  if (o.land) paint(land, o.land); else knock(land, Object.keys(night), o.landK ?? .9);
  if (o.sun != null) ink(landDay, o.landDay || { pink: 1 });
  // city lights: yellow, switching on in a wave out from o.from
  const from = CITIES[o.from || 'nyc'], lit = o.lights ?? 1;
  const glowP = new Path2D(), dotP = new Path2D();
  for (const L of GLOBE_DOTS.lights) {
    if (_isDay(L.lat, L.lon, o.sun)) continue;
    const d = _angDist(from, [L.lat, L.lon]) / Math.PI;           // 0..1 from the source city
    if (d > lit * 1.05 + (hash(L.id) - .5) * .06) continue;
    const [x, y, z] = globeProject(L.lat, L.lon, o); if (z <= .05) continue;
    const tw = hash(L.id * 7.3 + BF(t) * .31) > .93 ? .6 : 1;
    const r = R * .011 * L.s * (.5 + .5 * Math.sqrt(z)) * tw, px = cx + x * R, py = cy + y * R;
    dotP.moveTo(px + r, py); dotP.arc(px, py, r, 0, TAU);
    if (L.s > 1) { glowP.moveTo(px + r * 3.2, py); glowP.arc(px, py, r * 3.2, 0, TAU); }
  }
  knock(glowP, Object.keys(night), .3);
  paint(dotP, o.lightInk || { yellow: 1 });
  // arcs: great circles lifted off the surface, drawn from a to b; a comet tail follows the head
  for (const A of o.arcs || []) {
    const u = (t - A.t0) / (A.dur || .6); if (u <= 0) continue;
    const head = clamp(u), tail = clamp(u - .55) / .45 * (A.keep ? 0 : 1);
    const a = CITIES[A.a], b = CITIES[A.b], lift = .08 + .22 * _angDist(a, b) / Math.PI;
    const pts = []; let hidden = false;
    for (let i = 0; i <= 40; i++) {
      const s = lerp(tail, head, i / 40), [la, lo] = _slerpLL(a, b, s), h = 1 + lift * Math.sin(s * Math.PI);
      const [x, y, z] = globeProject(la, lo, o);
      if (z < -.15) { hidden = true; continue; }
      pts.push([cx + x * R * h, cy + y * R * h]);
    }
    if (pts.length > 1 && head > tail) paint(P(pts, false), { pink: 1 }, { stroke: Math.max(3, R * .012 * (o.arcW || 1)) });
    if (u >= 1 && u < 1.7) ping(cx, cy, R, b, u - 1, o);
    if (u > 0 && u < .6) ping(cx, cy, R, a, u, o);
  }
  for (const pg of o.pings || []) { const u = t - pg.t0; if (u > 0 && u < .8) ping(cx, cy, R, CITIES[pg.city], u, o); }
  if (o.pingAll != null) {
    for (const [k, c] of Object.entries(CITIES)) {
      const u = t - o.pingAll - _angDist(from, c) / Math.PI * .7;
      if (u > 0 && u < .7) ping(cx, cy, R, c, u, o);
    }
  }
  return disc;
}
function ping(cx, cy, R, ll, u, o) {
  const [x, y, z] = globeProject(ll[0], ll[1], o); if (z <= .05) return;
  const r = R * (.012 + .075 * E.out3(clamp(u / .7))), w = R * .009 * (1 - clamp(u / .7));
  if (w > .4) paint(P(circle(cx + x * R, cy + y * R, r, 28)), { pink: 1 }, { stroke: w });
}
