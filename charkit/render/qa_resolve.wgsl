// charkit/render/qa_resolve.wgsl: a measuring frame's picture (charkit/render/buffers.py) filtered as EEVEE's film
// filters its samples (resolve.wgsl's Gaussian: sigma = 0.284 x the filter radius, taps within the radius), kept linear,
// premultiplied and with its alpha (a transparent film: the QA's pictures carry coverage, charkit.qa3d.draw's), the
// sRGB curve and the 8 bits applied on the CPU.

struct RU {
  p: vec4<f32>,       // ss (hi-res px per output px), sigma (output px), radius (output px)
};

@group(0) @binding(0) var<uniform> R: RU;
@group(0) @binding(1) var t_main: texture_2d<f32>;

struct VOut { @builtin(position) pos: vec4<f32>, };

@vertex
fn vs_full(@builtin(vertex_index) i: u32) -> VOut {
  var p = array<vec2<f32>, 3>(vec2<f32>(-1.0, -1.0), vec2<f32>(3.0, -1.0), vec2<f32>(-1.0, 3.0));
  var o: VOut;
  o.pos = vec4<f32>(p[i], 0.0, 1.0);
  return o;
}

@fragment
fn fs_resolve(v: VOut) -> @location(0) vec4<u32> {     // (the float bits: measure.wgsl's targets)
  let ss = R.p.x;
  let sigma = R.p.y;
  let rad = R.p.z;
  let px = floor(v.pos.xy);
  let centre = (px + 0.5) * ss;
  let r = i32(ceil(rad * ss));
  let base = vec2<i32>(floor(centre));
  let sz = vec2<i32>(textureDimensions(t_main));
  var a = vec4<f32>(0.0);
  var wsum = 0.0;
  let k = -0.5 / (sigma * sigma);
  for (var y = -r; y <= r; y++) {
    for (var x = -r; x <= r; x++) {
      let ij = base + vec2<i32>(x, y);
      if (ij.x < 0 || ij.y < 0 || ij.x >= sz.x || ij.y >= sz.y) { continue; }
      let d = (vec2<f32>(ij) + 0.5 - centre) / ss;
      let d2 = dot(d, d);
      if (d2 > rad * rad) { continue; }
      let w = exp(k * d2);
      a += textureLoad(t_main, ij, 0) * w;
      wsum += w;
    }
  }
  return bitcast<vec4<u32>>(a / wsum);
}
