// charkit/render/toon.wgsl: charkit's cel look as Blender's node graphs compute it (charkit/shade.py toon3, hair_toon's
// streaks, flat, plate; charkit/faceshade.py material), read from the export's OPENADS_charkit_look (charkit/gltf.py).
// WGSL, so the same source can run in a browser's WebGPU (engine/three/charkit/look.js is the TSL port of the same maths).
//
//   vs_surface  the surface Blender draws: the original surface (co) moved inward by this view's line width x the
//               vertex's outline factor along the hull direction (the outline SOLIDIFY: offset 1, negative thickness)
//   vs_hull     the inverted hull at the original surface (co), drawn with front faces culled, in the line colour
//   vs_holdout  the skin at co (qa.features_pass turns its SOLIDIFY off), writing depth and a transparent black
//   fs_surface  toon3 | face | flat | plate, premultiplied (plates with alpha blend over what is behind)
//
// Textures are read with textureLoad (no sampler: exact, and float32 needs no filterable format): bilinear or cubic
// B-spline (Blender's 'Linear' / 'Cubic' image interpolation), EXTEND clamps, CLIP reads zero outside (the border).

const PI: f32 = 3.14159265358979;

struct ViewU {
  viewproj: mat4x4<f32>,
  cam_pos: vec4<f32>,        // xyz: the eye (glTF frame); w: 1 orthographic
  cam_back: vec4<f32>,       // xyz: toward the camera (orthographic views)
  light: vec4<f32>,          // xyz: toward the key light, world
  head_light: vec4<f32>,     // xyz: the same in the head's rest frame (= world in the build pose)
  line: vec4<f32>,           // x: screen lines' width (m) before the region factor; 0 = each outline's build width
};

struct MatU {
  kind: vec4<u32>,           // x: 0 flat, 1 toon3, 2 face, 3 plate; y: flags; z: streak columns; w: the part's id
  samp: vec4<u32>,           // per texture slot (sdf, fringe, blush, ink): filter | wrap << 4
  samp2: vec4<u32>,          // x: the material texture (plate / multiply)
  lit: vec4<f32>,
  shade: vec4<f32>,
  deep: vec4<f32>,
  color: vec4<f32>,          // flat
  tone: vec4<f32>,           // threshold, deep threshold, softness, rim amount
  rim_color: vec4<f32>,
  rim: vec4<f32>,            // Layer Weight exponent, map-range from, to
  hl_centre: vec4<f32>,      // xyz: the streaks' centre; w: columns
  hl: vec4<f32>,             // length (rad), duty, amount
  hl_face: vec4<f32>,        // facing from, to, Layer Weight exponent
  hl_color: vec4<f32>,
  face: vec4<f32>,           // softness, fringe range from, to
  face_lit: vec4<f32>,
  face_shade: vec4<f32>,
  outline: vec4<f32>,        // build width (m), region factor, 1 outlined
  line_color: vec4<f32>,
  hl_keep: array<vec4<f32>, 16>,   // per column (64 max): kept (0 / 1)
  hl_el0: array<vec4<f32>, 16>,    // per column: the streak's middle elevation (rad)
};

const F_RIM: u32 = 1u;
const F_STREAKS: u32 = 2u;
const F_TEXTURE: u32 = 4u;
const F_FRINGE: u32 = 8u;
const F_BLUSH: u32 = 16u;
const F_INK: u32 = 32u;
const F_BLEND: u32 = 64u;

@group(0) @binding(0) var<uniform> V: ViewU;
@group(1) @binding(0) var<uniform> M: MatU;
@group(1) @binding(1) var t_sdf: texture_2d<f32>;
@group(1) @binding(2) var t_fringe: texture_2d<f32>;
@group(1) @binding(3) var t_blush: texture_2d<f32>;
@group(1) @binding(4) var t_ink: texture_2d<f32>;
@group(1) @binding(5) var t_tex: texture_2d<f32>;

struct VIn {
  @location(0) pos: vec3<f32>,
  @location(1) nor: vec3<f32>,
  @location(2) hull: vec3<f32>,
  @location(3) ow: f32,
  @location(4) uv0: vec2<f32>,
  @location(5) uv1: vec2<f32>,
  @location(6) fmask: f32,
  @location(7) inkw: f32,
};

struct VOut {
  @builtin(position) clip: vec4<f32>,
  @location(0) wpos: vec3<f32>,
  @location(1) nor: vec3<f32>,
  @location(2) uv0: vec2<f32>,
  @location(3) uv1: vec2<f32>,
  @location(4) fmask: f32,
  @location(5) inkw: f32,
};

fn build_w() -> f32 { return M.outline.x * M.outline.z; }
fn view_w() -> f32 {
  if (M.outline.z == 0.0) { return 0.0; }
  if (V.line.x > 0.0) { return V.line.x * M.outline.y; }
  return M.outline.x;
}

fn out_of(p: vec3<f32>, v: VIn) -> VOut {
  var o: VOut;
  o.clip = V.viewproj * vec4<f32>(p, 1.0);
  o.wpos = p; o.nor = v.nor; o.uv0 = v.uv0; o.uv1 = v.uv1; o.fmask = v.fmask; o.inkw = v.inkw;
  return o;
}

@vertex
fn vs_surface(v: VIn) -> VOut {
  // POSITION = co - hull * build_w * ow  ->  co - hull * view_w * ow
  return out_of(v.pos + v.hull * ((build_w() - view_w()) * v.ow), v);
}

@vertex
fn vs_hull(v: VIn) -> VOut {
  return out_of(v.pos + v.hull * (build_w() * v.ow), v);
}

// ------------------------------------------------------------------------------------------------ texture reads
fn texel(t: texture_2d<f32>, ij: vec2<i32>, wrap: u32) -> vec4<f32> {
  let sz = vec2<i32>(textureDimensions(t));
  var p = ij;
  if (wrap == 1u) {
    if (p.x < 0 || p.y < 0 || p.x >= sz.x || p.y >= sz.y) { return vec4<f32>(0.0); }
  } else if (wrap == 2u) {
    p = ((p % sz) + sz) % sz;
  } else {
    p = clamp(p, vec2<i32>(0), sz - vec2<i32>(1));
  }
  return textureLoad(t, p, 0);
}

fn tex_linear(t: texture_2d<f32>, uv: vec2<f32>, wrap: u32) -> vec4<f32> {
  let st = uv * vec2<f32>(textureDimensions(t)) - 0.5;
  let fl = floor(st);
  let f = st - fl;
  let i = vec2<i32>(fl);
  let a = mix(texel(t, i, wrap), texel(t, i + vec2<i32>(1, 0), wrap), f.x);
  let b = mix(texel(t, i + vec2<i32>(0, 1), wrap), texel(t, i + vec2<i32>(1, 1), wrap), f.x);
  return mix(a, b, f.y);
}

fn bspline(f: f32) -> vec4<f32> {
  let f2 = f * f;
  let f3 = f2 * f;
  let w3 = f3 / 6.0;
  let w0 = -w3 + f2 * 0.5 - f * 0.5 + 1.0 / 6.0;
  let w1 = f3 * 0.5 - f2 + 2.0 / 3.0;
  return vec4<f32>(w0, w1, 1.0 - w0 - w1 - w3, w3);
}

fn tex_cubic(t: texture_2d<f32>, uv: vec2<f32>, wrap: u32) -> vec4<f32> {
  let st = uv * vec2<f32>(textureDimensions(t)) - 0.5;
  let fl = floor(st);
  let f = st - fl;
  let i = vec2<i32>(fl);
  let wx = bspline(f.x);
  let wy = bspline(f.y);
  var acc = vec4<f32>(0.0);
  for (var y = 0; y < 4; y++) {
    var row = vec4<f32>(0.0);
    for (var x = 0; x < 4; x++) {
      row += texel(t, i + vec2<i32>(x - 1, y - 1), wrap) * wx[x];
    }
    acc += row * wy[y];
  }
  return acc;
}

fn tex_nearest(t: texture_2d<f32>, uv: vec2<f32>, wrap: u32) -> vec4<f32> {
  let st = uv * vec2<f32>(textureDimensions(t));
  return texel(t, vec2<i32>(floor(st)), wrap);
}

fn tex(t: texture_2d<f32>, uv: vec2<f32>, mode: u32) -> vec4<f32> {
  let filt = mode & 15u;
  let wrap = mode >> 4u;
  if (filt == 1u) { return tex_cubic(t, uv, wrap); }
  if (filt == 2u) { return tex_nearest(t, uv, wrap); }
  return tex_linear(t, uv, wrap);
}

// ------------------------------------------------------------------------------------------------ the look
fn sat(x: f32) -> f32 { return clamp(x, 0.0, 1.0); }
fn map_range(x: f32, a: f32, b: f32) -> f32 { return sat((x - a) / (b - a)); }

// Blender's Layer Weight 'Facing': 1 - |N.V|^e
fn facing(n: vec3<f32>, vd: vec3<f32>, e: f32) -> f32 {
  return 1.0 - pow(max(abs(dot(n, vd)), 1e-12), e);
}

struct Toon { col: vec3<f32>, s_lit: f32, };

fn toon3(n: vec3<f32>, vd: vec3<f32>, wpos: vec3<f32>) -> Toon {
  let h = dot(n, V.light.xyz) * 0.5 + 0.5;
  let s = M.tone.z;
  let s_lit = sat((h - (M.tone.x - s)) / (2.0 * s));
  let s_deep = sat((h - (M.tone.y - s)) / (2.0 * s));
  let base = mix(mix(M.deep.xyz, M.shade.xyz, s_deep), M.lit.xyz, s_lit);
  var col = base;
  let fl = M.kind.y;
  if ((fl & F_RIM) != 0u) {
    let f = map_range(facing(n, vd, M.rim.x), M.rim.y, M.rim.z) * M.tone.w * s_lit;
    // Blender's Mix 'Screen': 1 - (1 - f + f (1 - B)) (1 - A)
    col = vec3<f32>(1.0) - (vec3<f32>(1.0 - f) + f * (vec3<f32>(1.0) - M.rim_color.xyz)) * (vec3<f32>(1.0) - base);
  }
  if ((fl & F_STREAKS) != 0u) {
    // charkit.shade.hair_toon: columns of azimuth round the centre; the kept ones carry a short streak
    let p = wpos - M.hl_centre.xyz;
    let el = atan2(p.y, length(p.xz));
    let az = atan2(p.x, p.z);
    let count = M.hl_centre.w;
    let c = (az + PI) * count / (2.0 * PI);
    let idx = clamp(i32(floor(c)), 0, 63);
    let keep = M.hl_keep[idx / 4][idx % 4];
    let el0 = M.hl_el0[idx / 4][idx % 4];
    let along = 1.0 - abs(el - el0) / (M.hl.x * 0.5);
    let across = 1.0 - abs(fract(c) - 0.5) / (M.hl.y * 0.5);
    let shape = sat(along * 3.0) * sat(across * 3.0);
    let fc = map_range(facing(n, vd, M.hl_face.z), M.hl_face.x, M.hl_face.y);
    let f = sat(shape * keep * fc * s_lit * M.hl.z);
    col = mix(col, M.hl_color.xyz, f);
  }
  var o: Toon;
  o.col = col;
  o.s_lit = s_lit;
  return o;
}

fn face(toon: vec3<f32>, uv1: vec2<f32>, fmask: f32, inkw: f32) -> vec3<f32> {
  let lh = V.head_light.xyz;
  let t = atan2(abs(lh.x), lh.z) / PI;                 // 0 light from the front .. 1 from behind
  var u = uv1.x;
  if (lh.x < 0.0) { u = 1.0 - uv1.x; }                 // light from her right: the map mirrored
  let sdf = tex(t_sdf, vec2<f32>(u, uv1.y), M.samp.x).x;
  let fs = M.face.x;
  var sh = sat((t - sdf + fs) / (2.0 * fs));
  let fl = M.kind.y;
  if ((fl & F_FRINGE) != 0u) {
    let fr = tex(t_fringe, uv1, M.samp.y).x;
    sh = max(sh, map_range(fr, M.face.y, M.face.z));
  }
  sh = sat(sh);
  var col = mix(M.face_lit.xyz, M.face_shade.xyz, sh);
  if ((fl & F_BLUSH) != 0u) {
    let b = tex(t_blush, uv1, M.samp.z);
    col = mix(col, col * b.xyz, sat(b.w));
  }
  var out = mix(toon, col, sat(fmask));
  if ((fl & F_INK) != 0u) {
    let k = tex(t_ink, uv1, M.samp.w);
    out = mix(out, k.xyz, sat(k.w * inkw));
  }
  return out;
}

@fragment
fn fs_surface(v: VOut, @builtin(front_facing) ff: bool) -> @location(0) vec4<f32> {
  let kind = M.kind.x;
  if (kind == 0u) { return vec4<f32>(M.color.xyz, 1.0); }
  if (kind == 3u) {
    let c = tex(t_tex, v.uv0, M.samp2.x);
    if ((M.kind.y & F_BLEND) != 0u) {
      let a = sat(c.w);
      return vec4<f32>(c.xyz * a, a);                   // straight colour (the Alpha output is used), over
    }
    return vec4<f32>(c.xyz * c.w, 1.0);                 // the Color output alone: premultiplied, opaque
  }
  var n = normalize(v.nor);
  if (!ff) { n = -n; }                                  // Blender's Geometry Normal faces the viewer
  var vd = normalize(V.cam_pos.xyz - v.wpos);
  if (V.cam_pos.w > 0.5) { vd = V.cam_back.xyz; }
  let t = toon3(n, vd, v.wpos);
  var col = t.col;
  if (kind == 2u) { col = face(col, v.uv1, v.fmask, v.inkw); }
  if ((M.kind.y & F_TEXTURE) != 0u) {
    let c = tex(t_tex, v.uv0, M.samp2.x);
    col = col * (c.xyz * c.w);                           // Mix 'Multiply' by the Color output alone: premultiplied
  }
  return vec4<f32>(col, 1.0);
}

@fragment
fn fs_hull() -> @location(0) vec4<f32> {
  return vec4<f32>(M.line_color.xyz, 1.0);
}

@fragment
fn fs_holdout() -> @location(0) vec4<f32> {
  return vec4<f32>(0.0);
}

// ------------------------------------------------------------------------------------------------ ids (measurement)
// which part each pixel shows: (the part's id, 0 surface | 1 hull), for per-part measures of a frame
@fragment
fn fs_surface_id() -> @location(0) vec4<f32> {
  return vec4<f32>(f32(M.kind.w), 0.0, 0.0, 1.0);
}

@fragment
fn fs_hull_id() -> @location(0) vec4<f32> {
  return vec4<f32>(f32(M.kind.w), 1.0, 0.0, 1.0);
}
