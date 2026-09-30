// charkit/render/resolve.wgsl: the supersampled frame down to the picture, as EEVEE's film filters its samples (a
// Gaussian fitted to Blackman-Harris, sigma = 0.284 x the filter radius, taps within the radius; Blender's default
// filter_size 1.5 px), then 'Standard' view transform (the sRGB curve), and the features pass laid over the frame at
// `through` x its alpha in sRGB, as charkit.qa.features_blend does with the two saved PNGs.

struct RU {
  p: vec4<f32>,       // ss (hi-res px per output px), sigma (output px), radius (output px), through
  q: vec4<f32>,       // x: 1 when there is a features pass; y: offset (hi-res px) of the output's origin
};

@group(0) @binding(0) var<uniform> R: RU;
@group(0) @binding(1) var t_main: texture_2d<f32>;
@group(0) @binding(2) var t_feat: texture_2d<f32>;

struct VOut { @builtin(position) pos: vec4<f32>, };

@vertex
fn vs_full(@builtin(vertex_index) i: u32) -> VOut {
  var p = array<vec2<f32>, 3>(vec2<f32>(-1.0, -1.0), vec2<f32>(3.0, -1.0), vec2<f32>(-1.0, 3.0));
  var o: VOut;
  o.pos = vec4<f32>(p[i], 0.0, 1.0);
  return o;
}

fn oetf(c: vec3<f32>) -> vec3<f32> {
  let x = max(c, vec3<f32>(0.0));
  let lo = x * 12.92;
  let hi = 1.055 * pow(x, vec3<f32>(1.0 / 2.4)) - 0.055;
  return select(hi, lo, x <= vec3<f32>(0.0031308));
}

@fragment
fn fs_resolve(v: VOut) -> @location(0) vec4<f32> {
  let ss = R.p.x;
  let sigma = R.p.y;
  let rad = R.p.z;
  let px = floor(v.pos.xy);                              // the output pixel
  let centre = (px + 0.5) * ss;                           // its centre in hi-res px
  let r = i32(ceil(rad * ss));
  let base = vec2<i32>(floor(centre));
  let sz = vec2<i32>(textureDimensions(t_main));
  var a = vec4<f32>(0.0);
  var b = vec4<f32>(0.0);
  var wsum = 0.0;
  let k = -0.5 / (sigma * sigma);
  let has_feat = R.q.x > 0.5;
  for (var y = -r; y <= r; y++) {
    for (var x = -r; x <= r; x++) {
      let ij = base + vec2<i32>(x, y);
      if (ij.x < 0 || ij.y < 0 || ij.x >= sz.x || ij.y >= sz.y) { continue; }
      let d = (vec2<f32>(ij) + 0.5 - centre) / ss;         // output px
      let d2 = dot(d, d);
      if (d2 > rad * rad) { continue; }
      let w = exp(k * d2);
      a += textureLoad(t_main, ij, 0) * w;
      if (has_feat) { b += textureLoad(t_feat, ij, 0) * w; }
      wsum += w;
    }
  }
  a /= wsum;
  var out = oetf(a.xyz);
  if (has_feat) {
    b /= wsum;
    let al = clamp(b.w, 0.0, 1.0);
    if (al > 1e-5) {
      let bs = oetf(b.xyz / al);
      out = mix(out, bs, R.p.w * al);
    }
  }
  return vec4<f32>(out, 1.0);
}
