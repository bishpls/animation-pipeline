// charkit/render/measure.wgsl: the measurement passes (charkit/render/buffers.py), compiled appended to toon.wgsl's
// source, so they read the same view and material blocks, vertex stages and texture reads (toon.wgsl's streak and
// outline code is its own; nothing here changes it). What the QA reads of a frame (charkit.qa3d's buffers), per
// pixel of the measuring grid, one sample at its centre:
//
//   aux     x: the part (the export's primitive, buffers.py's index + 1; 0 background), y: 1 on an outline hull,
//           z: the tone class (0 lit .. 1 shade .. 2 deep: toon3's two steps, continuous across their soft edges, as
//           charkit.qa3d._toon gives it; on the face the SDF shadow (0 lit .. 1 shade) blended in by the face mask;
//           -2 under the face's drawn ink; -1 off the toon materials), w: the distance along the view from the camera
//   nor     xyz: the shading normal (world, glTF frame, turned to the viewer on a back face), w 1 on a surface
//
//   vs_co   the surface where it is (the outline off: no inward move), for measures that draw an object without its
//           line (charkit.qa3d.surfaces(outline=False)); co_w() is written by buffers.py: the inward move POSITION
//           carries (the build width, or its capped move where toon.wgsl has inward())
//
// The tone thresholds repeat toon3's (toon.wgsl) and the face's SDF step repeats face()'s: a test holds them to the
// colour those functions give (charkit/tests/test_render_buffers.py).

// (the targets are rgba32uint holding the floats' bits: float32 targets aren't colour-renderable on every backend, wgpu's
// GL on the build box's llvmpipe among them; integer ones are in core GLES 3.0. The readback reads the same bytes as
// float32, so the values are exact everywhere)
struct MOut {
  @location(0) aux: vec4<u32>,
  @location(1) nor: vec4<u32>,
};

@vertex
fn vs_co(v: VIn) -> VOut {
  return out_of(v.pos + v.hull * (co_w() * v.ow), v);
}

fn m_depth(wpos: vec3<f32>) -> f32 {
  return dot(V.cam_pos.xyz - wpos, V.cam_back.xyz);
}

// face(): the SDF threshold at the light's angle (mirrored for light from her right), the fringe's shadow and the cast
// shadow (cs) over it
fn m_face_shade(uv1: vec2<f32>, cs: f32) -> f32 {
  let lh = V.head_light.xyz;
  let t = atan2(abs(lh.x), lh.z) / PI;
  var u = uv1.x;
  if (lh.x < 0.0) { u = 1.0 - uv1.x; }
  let sdf = tex(t_sdf, vec2<f32>(u, uv1.y), M.samp.x).x;
  let fs = M.face.x;
  var sh = sat((t - sdf + fs) / (2.0 * fs));
  if ((M.kind.y & F_FRINGE) != 0u) {
    let fr = tex(t_fringe, uv1, M.samp.y).x;
    sh = max(sh, map_range(fr, M.face.y, M.face.z));
  }
  return sat(max(sat(sh), cs));
}

fn m_tone(n: vec3<f32>, v: VOut) -> f32 {
  let kind = M.kind.x;
  if (kind != 1u && kind != 2u) { return -1.0; }
  let cs = cast_shadow(v.shadow);
  let h = half_lambert(n, cs);
  let s = M.tone.z;
  let s_lit = sat((h - (M.tone.x - s)) / (2.0 * s));
  let s_deep = sat((h - (M.tone.y - s)) / (2.0 * s));
  var tone = (1.0 - s_lit) * (2.0 - s_deep);
  if (kind == 2u) {
    let mk = sat(v.fmask);
    tone = tone * (1.0 - mk) + m_face_shade(v.uv1, cs) * mk;
    if ((M.kind.y & F_INK) != 0u) {
      if (tex(t_ink, v.uv1, M.samp.w).w * v.inkw > 0.5) { tone = -2.0; }
    }
  }
  return tone;
}

@fragment
fn fs_measure(v: VOut, @builtin(front_facing) ff: bool) -> MOut {
  var n = normalize(v.nor);
  if (!ff) { n = -n; }
  var o: MOut;
  o.aux = bitcast<vec4<u32>>(vec4<f32>(f32(M.kind.w), 0.0, m_tone(n, v), m_depth(v.wpos)));
  o.nor = bitcast<vec4<u32>>(vec4<f32>(n, 1.0));
  return o;
}

// a blended plate counts where it is at least half opaque (the iris over the white)
@fragment
fn fs_measure_plate(v: VOut, @builtin(front_facing) ff: bool) -> MOut {
  let c = tex(t_tex, v.uv0, M.samp2.x);
  if (c.w < 0.5) { discard; }
  var n = normalize(v.nor);
  if (!ff) { n = -n; }
  var o: MOut;
  o.aux = bitcast<vec4<u32>>(vec4<f32>(f32(M.kind.w), 0.0, -1.0, m_depth(v.wpos)));
  o.nor = bitcast<vec4<u32>>(vec4<f32>(n, 1.0));
  return o;
}

@fragment
fn fs_measure_hull(v: VOut) -> MOut {
  var o: MOut;
  o.aux = bitcast<vec4<u32>>(vec4<f32>(f32(M.kind.w), 1.0, -1.0, m_depth(v.wpos)));
  o.nor = bitcast<vec4<u32>>(vec4<f32>(0.0));
  return o;
}
