// scene-dump: a read-only look at a scene model as the renderer sees it, for rebuilding 2D art (the title logo) from it.
//   scene-dump FILE MODEL [OUT.json] [--frames F,...]
// MODEL names a model the way mscan prints it (MenusGeno.Models). The JSON holds, per joint (depth-first index, the order
// lb_80011E24 counts in): parent, flags, rest T/R/S, every joint-animation track's keys and the sampled T/R/S at each
// requested frame; per DOBJ: the MOBJ render flags, material colours and alpha, the PE (blend) descriptor, every TOBJ
// (texmap, colour/alpha ops, blending, wrap, repeat, UV scale/translate, TEV registers), every POBJ's primitives with
// their vertices (position, UVs, colour), and the material animation (material tracks, texture-animation tracks) with
// values sampled at the requested frames. Every HSD_Camera, HSD_FogDesc and light list in the file is printed too.
using System.Globalization;
using System.Text.Json;
using HSDRaw;
using HSDRaw.Common;
using HSDRaw.Common.Animation;
using HSDRaw.GX;
using HSDRaw.Tools;

static class SceneDump
{
    static readonly CultureInfo CI = CultureInfo.InvariantCulture;

    static object Keys(HSD_FOBJDesc fd) =>
        fd.GetDecodedKeys().Select(k => new object[] { k.Frame, k.Value, k.Tan, k.InterpolationType.ToString().Replace("HSD_A_OP_", "") }).ToList();

    static Dictionary<string, float> Sample(HSD_FOBJDesc fd, float[] frames)
    {
        var p = new FOBJ_Player(fd);
        return frames.ToDictionary(f => f.ToString(CI), f => p.GetValue(f));
    }

    static object Aobj(HSD_AOBJ ao) => ao == null ? null : new { end = ao.EndFrame, flags = ao.Flags.ToString() };

    static object Color(byte r, byte g, byte b, byte a) => new[] { (int)r, g, b, a };

    static object Tev(HSD_TOBJ_TEV t) => t == null ? null : new
    {
        color_op = t.color_op.ToString(), alpha_op = t.alpha_op.ToString(),
        color_bias = t.color_bias.ToString(), alpha_bias = t.alpha_bias.ToString(),
        color_scale = t.color_scale.ToString(), alpha_scale = t.alpha_scale.ToString(),
        color_clamp = t.color_clamp, alpha_clamp = t.alpha_clamp,
        color_in = new[] { t.color_a_in.ToString(), t.color_b_in.ToString(), t.color_c_in.ToString(), t.color_d_in.ToString() },
        alpha_in = new[] { t.alpha_a_in.ToString(), t.alpha_b_in.ToString(), t.alpha_c_in.ToString(), t.alpha_d_in.ToString() },
        konst = new[] { (int)t.constant.R, t.constant.G, t.constant.B, t.constantAlpha },
        tev0 = new[] { (int)t.tev0.R, t.tev0.G, t.tev0.B, t.tev0Alpha },
        tev1 = new[] { (int)t.tev1.R, t.tev1.G, t.tev1.B, t.tev1Alpha },
        active = t.active.ToString()
    };

    static object Tobj(HSD_TOBJ t, int i) => new
    {
        index = i, texmap = t.TexMapID.ToString(), gensrc = t.GXTexGenSrc.ToString(),
        flags = t.Flags.ToString(), flags_raw = (uint)t.Flags, coord = t.CoordType.ToString(),
        colormap = t.ColorOperation.ToString(), alphamap = t.AlphaOperation.ToString(), blending = t.Blending,
        wrap = new[] { t.WrapS.ToString(), t.WrapT.ToString() }, repeat = new[] { (int)t.RepeatS, t.RepeatT },
        scale = new[] { t.SX, t.SY, t.SZ }, rotate = new[] { t.RX, t.RY, t.RZ }, translate = new[] { t.TX, t.TY, t.TZ },
        mag = t.MagFilter.ToString(), min = t.LOD?.MinFilter.ToString(),
        image = t.ImageData == null ? null : new { w = (int)t.ImageData.Width, h = (int)t.ImageData.Height, fmt = t.ImageData.Format.ToString(), bytes = t.ImageData.ImageData?.Length ?? 0,
            raw = (t.ImageData.ImageData?.Length ?? 0) <= 64 ? Convert.ToHexString(t.ImageData.ImageData ?? new byte[0]) : null },
        tlut = t.TlutData == null ? null : new { fmt = t.TlutData.Format.ToString(), n = (int)t.TlutData.ColorCount },
        tev = Tev(t.TEV)
    };

    static object Pobj(HSD_POBJ p)
    {
        GX_DisplayList dl; try { dl = p.ToDisplayList(); } catch (Exception e) { return new { error = e.Message }; }
        var attrs = dl.Attributes.Select(x => x.AttributeName.ToString()).ToList();
        bool Has(GXAttribName n) => dl.Attributes.Any(x => x.AttributeName == n);
        int o = 0; var prims = new List<object>();
        foreach (var pg in dl.Primitives)
        {
            var vs = dl.Vertices.Skip(o).Take(pg.Count).Select(v => new
            {
                pos = new[] { v.POS.X, v.POS.Y, v.POS.Z },
                uv0 = Has(GXAttribName.GX_VA_TEX0) ? new[] { v.TEX0.X, v.TEX0.Y } : null,
                uv1 = Has(GXAttribName.GX_VA_TEX1) ? new[] { v.TEX1.X, v.TEX1.Y } : null,
                uv2 = Has(GXAttribName.GX_VA_TEX2) ? new[] { v.TEX2.X, v.TEX2.Y } : null,
                clr0 = Has(GXAttribName.GX_VA_CLR0) ? new[] { v.CLR0.R, v.CLR0.G, v.CLR0.B, v.CLR0.A } : null,
                mtx = Has(GXAttribName.GX_VA_PNMTXIDX) ? (int?)v.PNMTXIDX : null
            }).ToList();
            prims.Add(new { type = pg.PrimitiveType.ToString(), verts = vs });
            o += pg.Count;
        }
        return new { flags = p.Flags.ToString(), attrs, prims, bound = p.SingleBoundJOBJ != null };
    }

    public static int Run(string[] a)
    {
        var f = new HSDRawFile(a[1]);
        var m = MenusGeno.FindModel(f, a[2]);
        string outp = null; float[] frames = { 0 };
        for (int i = 3; i < a.Length; i++)
        {
            if (a[i] == "--frames") frames = a[++i].Split(',').Select(s => float.Parse(s, CI)).ToArray();
            else outp = a[i];
        }
        var joints = new List<object>();
        int idx = 0;
        void W(HSD_JOBJ j, HSD_AnimJoint aj, HSD_MatAnimJoint mj, int parent)
        {
            for (; j != null; j = j.Next, aj = aj?.Next, mj = mj?.Next)
            {
                int me = idx++;
                var tracks = new List<object>();
                if (aj?.AOBJ?.FObjDesc != null)
                    foreach (var fd in aj.AOBJ.FObjDesc.List)
                        tracks.Add(new { type = fd.JointTrackType.ToString(), keys = Keys(fd), at = Sample(fd, frames) });
                // T/R/S after animation at each frame: the track's value where one exists, else the rest value
                var sampled = new Dictionary<string, float[]>();
                foreach (var fr in frames)
                {
                    var v = new[] { j.TX, j.TY, j.TZ, j.RX, j.RY, j.RZ, j.SX, j.SY, j.SZ };
                    if (aj?.AOBJ?.FObjDesc != null)
                        foreach (var fd in aj.AOBJ.FObjDesc.List)
                        {
                            int k = fd.JointTrackType switch
                            {
                                JointTrackType.HSD_A_J_TRAX => 0, JointTrackType.HSD_A_J_TRAY => 1, JointTrackType.HSD_A_J_TRAZ => 2,
                                JointTrackType.HSD_A_J_ROTX => 3, JointTrackType.HSD_A_J_ROTY => 4, JointTrackType.HSD_A_J_ROTZ => 5,
                                JointTrackType.HSD_A_J_SCAX => 6, JointTrackType.HSD_A_J_SCAY => 7, JointTrackType.HSD_A_J_SCAZ => 8, _ => -1
                            };
                            if (k >= 0) v[k] = new FOBJ_Player(fd).GetValue(fr);
                        }
                    sampled[fr.ToString(CI)] = v;
                }
                var dobjs = new List<object>();
                var ma = mj?.MaterialAnimation; int di = 0;
                for (var d = j.Dobj; d != null; d = d.Next, ma = ma?.Next, di++)
                {
                    var mo = d.Mobj; var mt = mo?.Material; var pe = mo?.PEDesc;
                    var tobjs = new List<object>(); int ti = 0;
                    for (var t = mo?.Textures; t != null; t = t.Next) tobjs.Add(Tobj(t, ti++));
                    var pobjs = new List<object>();
                    for (var p = d.Pobj; p != null; p = p.Next) pobjs.Add(Pobj(p));
                    object matanim = null;
                    if (ma != null)
                    {
                        var mtr = new List<object>();
                        if (ma.AnimationObject?.FObjDesc != null)
                            foreach (var fd in ma.AnimationObject.FObjDesc.List)
                                mtr.Add(new { type = ((MatTrackType)fd.TrackType).ToString(), keys = Keys(fd), at = Sample(fd, frames) });
                        var tas = new List<object>();
                        for (var ta = ma.TextureAnimation; ta != null; ta = ta.Next)
                            tas.Add(new
                            {
                                texmap = ta.GXTexMapID.ToString(), images = (int)ta.ImageCount, tluts = (int)ta.TlutCount, aobj = Aobj(ta.AnimationObject),
                                tracks = MenusGeno.Tracks(ta).Select(fd => new { type = ((TexTrackType)fd.TrackType).ToString(), keys = Keys(fd), at = Sample(fd, frames) }).ToList()
                            });
                        matanim = new { aobj = Aobj(ma.AnimationObject), tracks = mtr, texanims = tas, render_anim = ma.RenderAnim };
                    }
                    dobjs.Add(new
                    {
                        index = di,
                        render = mo?.RenderFlags.ToString(), render_raw = (uint)(mo?.RenderFlags ?? 0),
                        material = mt == null ? null : new
                        {
                            ambient = Color(mt.AMB_R, mt.AMB_G, mt.AMB_B, mt.AMB_A), diffuse = Color(mt.DIF_R, mt.DIF_G, mt.DIF_B, mt.DIF_A),
                            specular = Color(mt.SPC_R, mt.SPC_G, mt.SPC_B, mt.SPC_A), alpha = mt.Alpha, shininess = mt.Shininess
                        },
                        pe = pe == null ? null : new
                        {
                            flags = pe.Flags.ToString(), blend = pe.BlendMode.ToString(), src = pe.SrcFactor.ToString(), dst = pe.DstFactor.ToString(),
                            logic = pe.BlendOp.ToString(), depth = pe.DepthFunction.ToString(), alpha_ref = new[] { (int)pe.AlphaRef0, pe.AlphaRef1 },
                            alpha_comp = new[] { pe.AlphaComp0.ToString(), pe.AlphaComp1.ToString() }, alpha_op = pe.AlphaOp.ToString(), dst_alpha = (int)pe.DestinationAlpha
                        },
                        tobjs, pobjs, matanim
                    });
                }
                joints.Add(new
                {
                    index = me, parent, flags = j.Flags.ToString(), flags_raw = (uint)j.Flags,
                    rest = new { t = new[] { j.TX, j.TY, j.TZ }, r = new[] { j.RX, j.RY, j.RZ }, s = new[] { j.SX, j.SY, j.SZ } },
                    aobj = Aobj(aj?.AOBJ), tracks, sampled, dobjs
                });
                W(j.Child, aj?.Child, mj?.Child, me);
            }
        }
        W(m.J, m.A, m.M, -1);

        var cams = f.Roots.Where(r => r.Data is HSD_Camera).Select(r =>
        {
            var c = (HSD_Camera)r.Data;
            return (object)new
            {
                name = r.Name, projection = c.ProjectionType.ToString(), flags = (int)c.Flags,
                viewport = new[] { (int)c.ViewportLeft, c.ViewportRight, c.ViewportTop, c.ViewportBottom }, scissor = new[] { c.ProjWidth, c.ProjHeight },
                eye = c.eye == null ? null : new[] { c.eye.V1, c.eye.V2, c.eye.V3 }, target = c.target == null ? null : new[] { c.target.V1, c.target.V2, c.target.V3 },
                roll = c.Roll, near = c.NearClip, far = c.FarClip,
                // the projection's own floats (fov/aspect for a perspective camera, top/bottom/left/right for an ortho one)
                p = Enumerable.Range(0, 4).Where(i => 0x34 + i * 4 <= c._s.Length).Select(i => c._s.GetFloat(0x30 + i * 4)).ToArray()
            };
        }).ToList();
        var fogs = f.Roots.Where(r => r.Data is HSD_FogDesc).Select(r =>
        {
            var fg = (HSD_FogDesc)r.Data;
            return (object)new { name = r.Name, type = fg.Type.ToString(), start = fg.Start, end = fg.End, color = new[] { (int)fg.Color.R, fg.Color.G, fg.Color.B, fg.Color.A }, adj = fg.FogAdjDesc != null };
        }).ToList();
        var lights = new List<object>();
        foreach (var r in f.Roots.Where(r => r.Name.EndsWith("_lights")))
        {
            var arr = new HSDNullPointerArrayAccessor<HSD_Light>(); arr._s = r.Data._s;
            foreach (var l in arr.Array)
            {
                var lo = l?.LightObject; if (lo == null) continue;
                lights.Add(new
                {
                    root = r.Name, flags = lo.Flags.ToString(), color = new[] { (int)lo.ColorR, lo.ColorG, lo.ColorB, lo.ColorAlpha },
                    pos = lo.Position == null ? null : new[] { lo.Position.V1, lo.Position.V2, lo.Position.V3 },
                    interest = lo.Interest == null ? null : new[] { lo.Interest.V1, lo.Interest.V2, lo.Interest.V3 }
                });
            }
        }
        var json = JsonSerializer.Serialize(new { file = Path.GetFileName(a[1]), model = a[2], frames, cameras = cams, fogs, lights, joints },
            new JsonSerializerOptions { WriteIndented = true, NumberHandling = System.Text.Json.Serialization.JsonNumberHandling.AllowNamedFloatingPointLiterals });
        if (outp != null) File.WriteAllText(outp, json); else Console.WriteLine(json);
        return 0;
    }
}
