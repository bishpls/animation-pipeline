// An article (projectile) model from a spec, replacing the donor's: our own joints, meshes, materials, textures and the
// states' joint animations. projects/geno/fx/beam_model.py writes the spec; fighter-build calls this for an article with
// a "model" entry (projects/geno/rig/articles.py).
//
// spec = { "joints": [ { "parent": -1, "t": [x,y,z], "r": [x,y,z], "s": [x,y,z], "flags": ["VBILLBOARD"] }, ... ]
//                                                                                                  (depth-first order)
//          "meshes": [ { "joint": 1, "tris": [[x,y,z, r,g,b,a (0-1), u,v], ...] (a triangle list),
//                        "blend": "add" | "xlu", "alpha": 1.0, "texture": "flare.png" | null, "tex_fmt": "IA8" } ],
//          "states": [ { "tracks": [ { "joint": 2, "track": "ROTX", "keys": [[frame, value], ...], "end": 30,
//                                      "loop": true } ] }, ... ] }                                 (one per article state)
// Materials copy the donor laser's two setups (Falco's article 0): its outer shells' additive blend (src alpha, one) and
// its core's plain translucency, both unlit vertex colour. A textured mesh modulates the vertex colour by the texture.
using System.Text.Json;
using HSDRaw;
using HSDRaw.Common;
using HSDRaw.Common.Animation;
using HSDRaw.GX;
using HSDRaw.Melee.Pl;
using HSDRaw.Tools;

static class ArticleModel
{
    public static int CountJoints(HSD_JOBJ j) { int n = 0; for (; j != null; j = j.Next) n += 1 + CountJoints(j.Child); return n; }

    public static (HSD_JOBJ root, List<HSD_AnimJoint> anims, string summary) Build(JsonElement spec, SBM_Article donor, string baseDir)
    {
        // the two material setups, as Falco's laser has them: an additive glow (the PE blends src alpha onto one) and a
        // plain translucent layer; both unlit vertex colour, no depth writes
        HSD_MOBJ Mat(bool additive)
        {
            var m = new HSD_MOBJ
            {
                RenderFlags = RENDER_MODE.VERTEX | RENDER_MODE.NO_ZUPDATE | RENDER_MODE.XLU,
                Material = new HSD_Material { AMB_R = 128, AMB_G = 128, AMB_B = 128, AMB_A = 255, DIF_R = 255, DIF_G = 255, DIF_B = 255, DIF_A = 255, Alpha = 1f }
            };
            if (additive)
                m.PEDesc = new HSD_PEDesc
                {
                    Flags = PIXEL_PROCESS_ENABLE.COLOR_UPDATE | PIXEL_PROCESS_ENABLE.BEFORE_TEX | PIXEL_PROCESS_ENABLE.COMPARE,
                    BlendMode = GXBlendMode.GX_BLEND, SrcFactor = GXBlendFactor.GX_BL_SRCALPHA, DstFactor = GXBlendFactor.GX_BL_ONE,
                    BlendOp = GXLogicOp.GX_LO_NOOP, DepthFunction = GXCompareType.LEqual, AlphaComp0 = GXCompareType.Always,
                    AlphaOp = GXAlphaOp.And, AlphaComp1 = GXCompareType.Always
                };
            return m;
        }

        var js = spec.GetProperty("joints").EnumerateArray().ToList();
        var J = new List<HSD_JOBJ>();
        foreach (var je in js)
        {
            var j = new HSD_JOBJ { Flags = JOBJ_FLAG.CLASSICAL_SCALING };
            float[] V(string k, float d) => je.TryGetProperty(k, out var v) ? v.EnumerateArray().Select(e => (float)e.GetDouble()).ToArray() : new[] { d, d, d };
            var t = V("t", 0); var r = V("r", 0); var s = V("s", 1);
            j.TX = t[0]; j.TY = t[1]; j.TZ = t[2]; j.RX = r[0]; j.RY = r[1]; j.RZ = r[2]; j.SX = s[0]; j.SY = s[1]; j.SZ = s[2];
            int p = je.GetProperty("parent").GetInt32();
            if (p >= 0) J[p].AddChild(j);
            J.Add(j);
        }

        int nm = 0, nv = 0, ntex = 0;
        var texCache = new Dictionary<string, HSD_TOBJ>();          // one encoded image per (file, format), shared by its meshes
        foreach (var me in spec.GetProperty("meshes").EnumerateArray())
        {
            var tex = me.TryGetProperty("texture", out var tv) && tv.ValueKind == JsonValueKind.String ? tv.GetString() : null;
            var verts = new List<GX_Vertex>();
            foreach (var tr in me.GetProperty("tris").EnumerateArray())
            {
                var f = tr.EnumerateArray().Select(e => (float)e.GetDouble()).ToArray();
                var v = new GX_Vertex { POS = new GXVector3(f[0], f[1], f[2]), CLR0 = new GXColor4(f[3], f[4], f[5], f[6]) };
                if (f.Length >= 9) v.TEX0 = new GXVector2(f[7], f[8]);
                verts.Add(v);
            }
            var attrs = new List<GXAttribName> { GXAttribName.GX_VA_POS, GXAttribName.GX_VA_CLR0 };
            if (tex != null) attrs.Add(GXAttribName.GX_VA_TEX0);
            var gen = new POBJ_Generator { CullMode = GenCullMode.None, VertexColorFormat = (GXCompType)GXCompTypeClr.RGBA8 };
            var po = gen.CreatePOBJsFromTriangleList(verts, attrs.ToArray(), null, null);
            gen.SaveChanges();
            var add = me.GetProperty("blend").GetString() == "add";
            var mo = Mat(add);
            mo.Material.Alpha = me.TryGetProperty("alpha", out var al) ? (float)al.GetDouble() : 1f;
            mo.Material.DIF_R = mo.Material.DIF_G = mo.Material.DIF_B = mo.Material.DIF_A = 255;
            if (tex != null)
            {
                var fmt = Enum.Parse<GXTexFmt>(me.TryGetProperty("tex_fmt", out var tf) ? tf.GetString() : "IA8");
                var key = tex + "|" + fmt;
                if (texCache.TryGetValue(key, out var shared))
                {
                    var tcopy = HSDAccessor.DeepClone<HSD_TOBJ>(shared);   // its own TOBJ (flags, chain), the same image and palette
                    tcopy.ImageData = shared.ImageData; tcopy.TlutData = shared.TlutData;
                    mo.Textures = tcopy; mo.RenderFlags |= RENDER_MODE.TEX0;
                    var dob2 = new HSD_DOBJ { Mobj = mo, Pobj = po };
                    var jj2 = J[me.GetProperty("joint").GetInt32()];
                    if (jj2.Dobj == null) jj2.Dobj = dob2; else jj2.Dobj.Add(dob2);
                    nm++; nv += verts.Count;
                    continue;
                }
                var (w, h, rgba) = PngRead.Decode(File.ReadAllBytes(Path.Combine(baseDir, tex)));
                var bgra = new byte[w * h * 4];
                for (int i = 0; i < w * h; i++) { bgra[i * 4] = rgba[i * 4 + 2]; bgra[i * 4 + 1] = rgba[i * 4 + 1]; bgra[i * 4 + 2] = rgba[i * 4]; bgra[i * 4 + 3] = rgba[i * 4 + 3]; }
                var to = new HSD_TOBJ
                {
                    MagFilter = GXTexFilter.GX_LINEAR,
                    Flags = TOBJ_FLAGS.COORD_UV | TOBJ_FLAGS.LIGHTMAP_DIFFUSE | TOBJ_FLAGS.COLORMAP_MODULATE | TOBJ_FLAGS.ALPHAMAP_MODULATE,
                    RepeatS = 1, RepeatT = 1, WrapS = GXWrapMode.CLAMP, WrapT = GXWrapMode.CLAMP,
                    SX = 1, SY = 1, SZ = 1, GXTexGenSrc = GXTexGenSrc.GX_TG_TEX0, Blending = 1
                };
                to.EncodeImageData(bgra, w, h, fmt, GXTlutFmt.RGB5A3);
                texCache[key] = to;
                mo.Textures = to;
                mo.RenderFlags |= RENDER_MODE.TEX0;
                ntex++;
            }
            var dob = new HSD_DOBJ { Mobj = mo, Pobj = po };
            var jj = J[me.GetProperty("joint").GetInt32()];
            if (jj.Dobj == null) jj.Dobj = dob; else jj.Dobj.Add(dob);
            jj.Flags |= JOBJ_FLAG.XLU;
            nm++; nv += verts.Count;
        }
        // as the laser's: translucent joints (no alpha-test pass). Every joint with a translucent mesh at or below it is
        // marked ROOT_XLU: the renderer only descends into a subtree in the translucent pass when it is (the Whirl's disc,
        // two joints down under its tilt, didn't draw without it)
        var js2 = spec.GetProperty("joints").EnumerateArray().Select(e => e.GetProperty("parent").GetInt32()).ToList();
        var holds = J.Select(j => j.Dobj != null).ToArray();
        for (int i = J.Count - 1; i > 0; i--) if (holds[i] && js2[i] >= 0) holds[js2[i]] = true;   // children follow parents
        for (int i = 0; i < J.Count; i++)
        {
            J[i].Flags = JOBJ_FLAG.CLASSICAL_SCALING | (J[i].Dobj != null ? JOBJ_FLAG.XLU : 0) | (holds[i] ? JOBJ_FLAG.ROOT_XLU : 0);
            if (js[i].TryGetProperty("flags", out var jf))     // e.g. ["VBILLBOARD"]: a joint that turns to face the camera
                foreach (var fl in jf.EnumerateArray()) J[i].Flags |= Enum.Parse<JOBJ_FLAG>(fl.GetString());
        }
        FighterBuild.AlignModel(J[0], null);

        // the states' joint animations: one AnimJoint tree per state, mirroring the joints
        var anims = new List<HSD_AnimJoint>();
        if (spec.TryGetProperty("states", out var ss))
            foreach (var st in ss.EnumerateArray())
            {
                var A = J.Select(_ => new HSD_AnimJoint()).ToList();
                for (int i = 1; i < js.Count; i++) A[js[i].GetProperty("parent").GetInt32()].AddChild(A[i]);
                foreach (var tr in st.GetProperty("tracks").EnumerateArray())
                {
                    var a = A[tr.GetProperty("joint").GetInt32()];
                    if (a.AOBJ == null)
                        a.AOBJ = new HSD_AOBJ { EndFrame = (float)tr.GetProperty("end").GetDouble(), Flags = tr.TryGetProperty("loop", out var lp) && lp.GetBoolean() ? AOBJ_Flags.ANIM_LOOP : 0 };
                    var keys = tr.GetProperty("keys").EnumerateArray().Select(k => new FOBJKey
                    { Frame = (float)k[0].GetDouble(), Value = (float)k[1].GetDouble(), InterpolationType = GXInterpolationType.HSD_A_OP_LIN }).ToList();
                    a.AOBJ.AddTrack((byte)Enum.Parse<JointTrackType>("HSD_A_J_" + tr.GetProperty("track").GetString()), keys);
                }
                anims.Add(A[0]);
            }
        return (J[0], anims, $"{J.Count} joints, {nm} meshes, {nv} verts, {ntex} textures, {anims.Count} state animations");
    }
}
