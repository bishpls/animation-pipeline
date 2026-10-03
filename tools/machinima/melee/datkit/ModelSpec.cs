// ModelSpec: measure and export a fighter's costume model (PlXxNr.dat and friends).
//   meshstats PlXxNr.dat [--ft PlXx.dat] [--co PlCo.dat --kind N | --rig RIG.json] one JSON object: joints, DObjs, PObjs, triangles,
//                                                                          envelopes, materials, textures, texture animations
//   export    PlXxNr.dat OUT.gltf [--ft PlXx.dat] [--lod high|low|all] [--dobjs 0-36,53]   (or PlXx.dat OUT.gltf --metal)
//                                                                          rest-pose glTF (skinned, every UV set, textures as
//                                                                          PNG) plus OUT.melee.json: each material's texture
//                                                                          layers as Melee blends them (tools/.../art/meltex.py)
// Vertices are placed the way HSDRawViewer's exporter does (IO/ModelExporter.cs): rigid meshes by their joint's world matrix,
// single-weight envelopes by that joint, multi-weight envelopes are stored in bind (model) space.
using System.Numerics;
using System.Text.Json;
using HSDRaw;
using HSDRaw.Common;
using HSDRaw.Common.Animation;
using HSDRaw.GX;

static class ModelSpec
{
    public class Vtx
    {
        public Vector3 P, N; public bool HasN;
        public Vector2[] UV = new Vector2[8]; public int UVMask;
        public Vector4 C = Vector4.One; public bool HasC;
        public List<(int j, float w)> W = new();
    }
    public class Tri { public Vtx A, B, C; }
    public class PInfo { public int Index, Flags, Prims, DLVerts, Tris, Degenerate, Envelopes; public string Kind; public List<Tri> T = new(); public int[] EnvHist = new int[9]; public int[] VInf = new int[9]; public string Attrs; }
    public class DInfo { public int Index, Joint; public HSD_DOBJ D; public List<PInfo> P = new(); }

    public class Model
    {
        public HSD_JOBJ Root; public List<HSD_JOBJ> J = new(); public List<int> Parent = new(); public List<Matrix4x4> World = new();
        public Dictionary<HSDStruct, int> ByS = new(ReferenceEqualityComparer.Instance);   // accessors are rebuilt per read: key on the struct
        public bool Has(HSD_JOBJ j) => j != null && ByS.ContainsKey(j._s);
        public int Of(HSD_JOBJ j) => ByS[j._s];
        public List<DInfo> D = new(); public HSD_MatAnimJoint MatAnim; public string RootName;
    }

    public static Matrix4x4 Local(HSD_JOBJ j) =>
        Matrix4x4.CreateScale(j.SX, j.SY, j.SZ) * Matrix4x4.CreateRotationX(j.RX) * Matrix4x4.CreateRotationY(j.RY) *
        Matrix4x4.CreateRotationZ(j.RZ) * Matrix4x4.CreateTranslation(j.TX, j.TY, j.TZ);

    public static Model Load(string path, bool metal = false)
    {
        var f = new HSDRawFile(path);
        Model m;
        if (metal)
        {   // a fighter data file's metal model (ftData+0x5C): its DObjs ride the costume's joints in the game
            var fr = f.Roots.First(x => x.Name.StartsWith("ftData"));
            m = new Model { Root = new HSDRaw.Melee.Pl.SBM_FighterData { _s = fr.Data._s }.MetalModel, RootName = fr.Name + ".MetalModel" };
        }
        else
        {
            var r = f.Roots.FirstOrDefault(x => x.Data is HSD_JOBJ);
            if (r == null && f.Roots.FirstOrDefault(x => x.Name.StartsWith("ftDataKirbyCopy")) is HSDRootNode kh)
            {   // a Kirby copy hat (PlKbCpXx.dat): a KirbyHatStruct, its joint at +0, the parts desc at +4 (HatLods reads it)
                m = new Model { Root = kh.Data._s.GetReference<HSD_JOBJ>(0x00), RootName = kh.Name + ".hat_joint" };
            }
            else m = new Model { Root = r.Data as HSD_JOBJ, RootName = r.Name };
            m.MatAnim = f.Roots.FirstOrDefault(x => x.Data is HSD_MatAnimJoint)?.Data as HSD_MatAnimJoint;
        }
        void W(HSD_JOBJ j, Matrix4x4 parent, int pi)
        {
            for (; j != null; j = j.Next)
            {
                var w = Local(j) * parent; int me = m.J.Count;
                m.J.Add(j); m.Parent.Add(pi); m.World.Add(w); m.ByS[j._s] = me;
                W(j.Child, w, me);
            }
        }
        W(m.Root, Matrix4x4.Identity, -1);
        int di = 0;
        for (int ji = 0; ji < m.J.Count; ji++)
            for (var d = m.J[ji].Dobj; d != null; d = d.Next)
                m.D.Add(Decode(m, ji, d, di++));
        return m;
    }

    static DInfo Decode(Model m, int ji, HSD_DOBJ dobj, int di)
    {
        var di_ = new DInfo { Index = di, Joint = ji, D = dobj };
        var parent = m.J[ji]; var parentT = m.World[ji];
        int pi = 0;
        for (var po = dobj.Pobj; po != null; po = po.Next, pi++)
        {
            var info = new PInfo { Index = pi, Flags = (int)po.Flags };
            GX_DisplayList dl; GX_Attribute[] attrs;
            try { attrs = po.ToGXAttributes(); dl = po.ToDisplayList(); } catch { di_.P.Add(info); continue; }
            info.Attrs = string.Join(",", attrs.Where(a => a.AttributeName != GXAttribName.GX_VA_NULL).Select(a => a.AttributeName.ToString().Replace("GX_VA_", "") + ":" + a.AttributeType.ToString().Replace("GX_", "") + (a.AttributeName == GXAttribName.GX_VA_POS || a.AttributeName == GXAttribName.GX_VA_TEX0 || a.AttributeName == GXAttribName.GX_VA_NRM ? "/" + a.CompType + (a.Scale > 0 ? "<<" + a.Scale : "") : "")));
            bool hasEnv = po.HasAttribute(GXAttribName.GX_VA_PNMTXIDX);
            var env = po.EnvelopeWeights; var sb = po.SingleBoundJOBJ;
            info.Kind = po.Flags.HasFlag(POBJ_FLAG.SHAPEANIM) ? "shape" : env != null ? "envelope" : sb != null ? "singlebind" : "rigid";
            info.Envelopes = env?.Length ?? 0;
            if (env != null) foreach (var e in env) info.EnvHist[Math.Min(8, e.EnvelopeCount)]++;
            var sbT = m.Has(sb) ? m.World[m.Of(sb)] : Matrix4x4.Identity;
            bool skel = parent.Flags.HasFlag(JOBJ_FLAG.SKELETON) || parent.Flags.HasFlag(JOBJ_FLAG.SKELETON_ROOT) || po.Flags.HasFlag(POBJ_FLAG.UNKNOWN2);
            int off = 0;
            foreach (var prim in dl.Primitives)
            {
                info.Prims++; info.DLVerts += prim.Count;
                var vs = new List<Vtx>();
                for (int k = 0; k < prim.Count; k++)
                {
                    var g = dl.Vertices[off + k];
                    var v = new Vtx();
                    var single = Matrix4x4.Identity;
                    if (hasEnv)
                    {
                        if (po.Flags.HasFlag(POBJ_FLAG.UNKNOWN2))
                        {
                            int en = g.PNMTXIDX / 3; int bj = ji;
                            if (en == 1 && m.Parent[ji] >= 0) bj = m.Parent[ji];
                            v.W.Add((bj, 1)); single = m.World[bj];
                        }
                        else if (env != null && g.PNMTXIDX / 3 < env.Length)
                        {
                            var e = env[g.PNMTXIDX / 3];
                            for (int w = 0; w < e.EnvelopeCount; w++)
                            {
                                var jj = e.GetJOBJAt(w); int idx = m.Has(jj) ? m.Of(jj) : 0;
                                v.W.Add((idx, e.GetWeightAt(w)));
                            }
                            if (e.EnvelopeCount > 0 && e.GetWeightAt(0) == 1 && m.Has(e.GetJOBJAt(0)))
                                single = m.World[m.Of(e.GetJOBJAt(0))];
                            else single = parentT;
                        }
                    }
                    else if (m.Has(sb)) v.W.Add((m.Of(sb), 1));
                    else v.W.Add((ji, 1));
                    var p = new Vector3(g.POS.X, g.POS.Y, g.POS.Z);
                    var n = new Vector3(g.NRM.X, g.NRM.Y, g.NRM.Z);
                    if (!po.Flags.HasFlag(POBJ_FLAG.SHAPESET_AVERAGE) && !hasEnv) { p = Vector3.Transform(p, parentT); n = Vector3.TransformNormal(n, parentT); }
                    if (skel) { p = Vector3.Transform(p, single); n = Vector3.TransformNormal(n, single); }
                    p = Vector3.Transform(p, sbT); n = Vector3.TransformNormal(n, sbT);
                    v.P = p;
                    foreach (var a in attrs)
                    {
                        switch (a.AttributeName)
                        {
                            case GXAttribName.GX_VA_NRM: v.N = n.LengthSquared() > 0 ? Vector3.Normalize(n) : n; v.HasN = true; break;
                            case GXAttribName.GX_VA_CLR0: v.C = new Vector4(g.CLR0.R, g.CLR0.G, g.CLR0.B, g.CLR0.A); v.HasC = true; break;
                            case GXAttribName.GX_VA_TEX0: v.UV[0] = new Vector2(g.TEX0.X, g.TEX0.Y); v.UVMask |= 1; break;
                            case GXAttribName.GX_VA_TEX1: v.UV[1] = new Vector2(g.TEX1.X, g.TEX1.Y); v.UVMask |= 2; break;
                            case GXAttribName.GX_VA_TEX2: v.UV[2] = new Vector2(g.TEX2.X, g.TEX2.Y); v.UVMask |= 4; break;
                            case GXAttribName.GX_VA_TEX3: v.UV[3] = new Vector2(g.TEX3.X, g.TEX3.Y); v.UVMask |= 8; break;
                        }
                    }
                    info.VInf[Math.Min(8, v.W.Count)]++;
                    vs.Add(v);
                }
                off += prim.Count;
                void Add(Vtx a, Vtx b, Vtx c)
                {
                    if (a.P == b.P || b.P == c.P || a.P == c.P) { info.Degenerate++; return; }
                    info.T.Add(new Tri { A = a, B = b, C = c }); info.Tris++;
                }
                switch (prim.PrimitiveType)
                {
                    case GXPrimitiveType.Triangles: for (int k = 0; k + 2 < vs.Count; k += 3) Add(vs[k], vs[k + 1], vs[k + 2]); break;
                    case GXPrimitiveType.TriangleStrip:
                        for (int k = 0; k + 2 < vs.Count; k++) { if ((k & 1) == 0) Add(vs[k], vs[k + 1], vs[k + 2]); else Add(vs[k + 1], vs[k], vs[k + 2]); }
                        break;
                    case GXPrimitiveType.TriangleFan: for (int k = 1; k + 1 < vs.Count; k++) Add(vs[0], vs[k], vs[k + 1]); break;
                    case GXPrimitiveType.Quads: for (int k = 0; k + 3 < vs.Count; k += 4) { Add(vs[k], vs[k + 1], vs[k + 2]); Add(vs[k], vs[k + 2], vs[k + 3]); } break;
                }
            }
            di_.P.Add(info);
        }
        return di_;
    }

    // ---- lookups (PlXx.dat ModelLookupTables): costume 0's high/low/metal DObj lists
    public static (HashSet<int> hi, HashSet<int> lo, int groups) Lookups(string ftPath)
    {
        var f = new HSDRawFile(ftPath);
        var ft = f.Roots.First(r => r.Name.StartsWith("ftData")).Data;
        var ml = ft.GetType().GetProperty("ModelLookupTables").GetValue(ft) as HSDRaw.Melee.Pl.SBM_PlayerModelLookupTables;
        var hi = new HashSet<int>(); var lo = new HashSet<int>();
        var c0 = ml.CostumeVisibilityLookups[0];
        void Fill(HSDArrayAccessor<HSDRaw.Melee.Pl.SBM_LookupTable> t, HashSet<int> s)
        {
            if (t == null) return;
            foreach (var lt in t.Array) foreach (var e in lt.LookupEntries?.Array ?? new HSDRaw.Melee.Pl.SBM_LookupEntry[0]) foreach (var b in e.Entries ?? new byte[0]) s.Add(b);
        }
        Fill(c0.HighPoly, hi); Fill(c0.LowPoly, lo);
        return (hi, lo, ml.VisibilityLookupLength);
    }

    // a Kirby copy hat's visibility row (KirbyHatStruct +4 FtPartsDesc: model_num, then four FtPartsVisLookup* for
    // [0] normal, [1] low detail, [2] normal again, [3] none; each is model_num groups of options of DObj indices)
    public static (HashSet<int> hi, HashSet<int> lo, int groups) HatLods(string path)
    {
        var s = new HSDRawFile(path).Roots.First(x => x.Name.StartsWith("ftDataKirbyCopy")).Data._s;
        int n = s.GetInt32(0x04); var row = s.GetReference<HSDAccessor>(0x08)?._s;
        HashSet<int> Row(int k)
        {
            var set = new HashSet<int>(); var t = row?.GetReference<HSDAccessor>(4 * k)?._s; if (t == null) return set;
            for (int g = 0; g < n; g++)
            {
                int nopt = t.GetInt32(8 * g); var opts = t.GetReference<HSDAccessor>(8 * g + 4)?._s;
                for (int o = 0; o < nopt && opts != null; o++)
                {
                    int cnt = opts.GetInt32(8 * o); var b = opts.GetReference<HSDAccessor>(8 * o + 4)?._s;
                    for (int i = 0; i < cnt && b != null; i++) set.Add(b.GetByte(i));
                }
            }
            return set;
        }
        return (Row(0), Row(1), n);
    }

    // group -> option -> DObj indices, for costume 0's high (which=0) or low (1) table
    public static List<List<List<int>>> Groups(string ftPath, int which)
    {
        var ft = new HSDRawFile(ftPath).Roots.First(r => r.Name.StartsWith("ftData")).Data;
        var ml = ft.GetType().GetProperty("ModelLookupTables").GetValue(ft) as HSDRaw.Melee.Pl.SBM_PlayerModelLookupTables;
        var c0 = ml.CostumeVisibilityLookups[0]; var t = which == 0 ? c0.HighPoly : c0.LowPoly;
        if (t == null) return new();
        return t.Array.Select(lt => (lt.LookupEntries?.Array ?? new HSDRaw.Melee.Pl.SBM_LookupEntry[0]).Select(e => (e.Entries ?? new byte[0]).Select(b => (int)b).ToList()).ToList()).ToList();
    }

    // ftData+0x2C: the dynamics chains (capes, hair, tails): start bone, chain length, drag/stiffness; plus collision bubbles
    public static object Dynamics(string ftPath)
    {
        var fd = new HSDRawFile(ftPath).Roots.First(r => r.Data is HSDRaw.Melee.Pl.SBM_FighterData).Data as HSDRaw.Melee.Pl.SBM_FighterData;
        var ph = fd.Physics; if (ph == null) return null;
        var descs = ph.DynamicDesc?.Array ?? new HSDRaw.Melee.Pl.SBM_DynamicDesc[0];
        return new Dictionary<string, object>
        {
            ["chains"] = descs.Take(ph.DynamicDescCount).Select(d => new Dictionary<string, object> { ["bone"] = d.BoneIndex, ["n"] = d._s.GetInt32(0x08), ["drag"] = d.DragMultiplier, ["stiff"] = d.StiffnessMultiplier, ["gravlen"] = d.GravityLengthCompensation,
                ["params"] = (d.Parameters ?? new HSDRaw.Melee.Pl.SBM_DynamicParams[0]).Select(q => new[] { q.FollowDamping, q.Stiffness }).ToList() }).ToList(),
            ["bubbles"] = (ph.Hitbubbles?.Array ?? new HSDRaw.Melee.Pl.SBM_DynamicHitBubble[0]).Take(ph.DynamicHitBubbleCount).Select(b => new Dictionary<string, object> { ["bone"] = b.BoneIndex, ["size"] = b.Size }).ToList(),
        };
    }

    public static string TexKey(HSD_TOBJ t)
    {
        var d = t.ImageData?.ImageData; if (d == null) return null;
        var h = System.Security.Cryptography.SHA1.HashData(d.Concat(t.TlutData?.TlutData ?? new byte[0]).ToArray());
        return Convert.ToHexString(h).Substring(0, 10).ToLower();
    }
    static string CoordName(HSD_TOBJ t) => ((int)t.Flags & 0xF) switch { 0 => "uv", 1 => "reflection", 2 => "highlight", 3 => "shadow", 4 => "toon", 5 => "gradation", var x => x.ToString() };
    static string ColorMap(HSD_TOBJ t) => (((int)t.Flags >> 16) & 0xF) switch { 0 => "none", 1 => "alpha_mask", 2 => "rgb_mask", 3 => "blend", 4 => "modulate", 5 => "replace", 6 => "pass", 7 => "add", 8 => "sub", var x => x.ToString() };
    static string AlphaMap(HSD_TOBJ t) => (((int)t.Flags >> 20) & 0xF) switch { 0 => "none", 1 => "alpha_mask", 2 => "blend", 3 => "modulate", 4 => "replace", 5 => "pass", 6 => "add", 7 => "sub", var x => x.ToString() };
    static List<string> Lightmaps(HSD_TOBJ t)
    {
        var l = new List<string>();
        if (t.DiffuseLightmap) l.Add("diffuse"); if (t.SpecularLightmap) l.Add("specular"); if (t.AmbientLightmap) l.Add("ambient");
        if (t.ExtLightmap) l.Add("ext"); if (t.ShadowLightmap) l.Add("shadow"); if (t.BumpMap) l.Add("bump");
        return l;
    }
    static int UVChan(HSD_TOBJ t) { int s = (int)t.GXTexGenSrc; return s >= 4 && s <= 11 ? s - 4 : s >= 13 && s <= 19 ? s - 13 : 0; }
    static int TexBytes(HSD_TOBJ t) => (t.ImageData?.ImageData?.Length ?? 0) + (t.TlutData?.TlutData?.Length ?? 0);

    public static Dictionary<string, object> TexInfo(HSD_TOBJ t) => new()
    {
        ["key"] = TexKey(t), ["w"] = t.ImageData?.Width ?? 0, ["h"] = t.ImageData?.Height ?? 0, ["fmt"] = t.ImageData?.Format.ToString(),
        ["tlut"] = t.TlutData != null ? $"{t.TlutData.Format}x{t.TlutData.ColorCount}" : null, ["bytes"] = TexBytes(t),
        ["mip"] = t.ImageData?.MipMap ?? 0, ["coord"] = CoordName(t), ["lightmaps"] = Lightmaps(t), ["colormap"] = ColorMap(t), ["alphamap"] = AlphaMap(t),
        ["blend"] = t.Blending, ["uv"] = UVChan(t), ["src"] = t.GXTexGenSrc.ToString(), ["wrap"] = new[] { t.WrapS.ToString(), t.WrapT.ToString() },
        ["repeat"] = new[] { (int)t.RepeatS, (int)t.RepeatT }, ["scale"] = new[] { t.SX, t.SY }, ["rot"] = new[] { t.RX, t.RY, t.RZ }, ["trans"] = new[] { t.TX, t.TY },
        ["texmap"] = t.TexMapID.ToString(), ["mag"] = t.MagFilter.ToString(), ["tev"] = t.TEV != null,
    };

    public static Dictionary<string, object> MatInfo(HSD_MOBJ mo)
    {
        var mt = mo?.Material; var pe = mo?.PEDesc;
        var rf = mo == null ? 0u : (uint)mo.RenderFlags;
        var flags = new List<string>();
        if (mo != null) foreach (RENDER_MODE v in Enum.GetValues(typeof(RENDER_MODE))) if (v != RENDER_MODE.ALPHA_BOTH && v != RENDER_MODE.ALPHA_VTX && ((uint)v & rf) == (uint)v && (uint)v != 0) flags.Add(v.ToString());
        return new()
        {
            ["render"] = $"{rf:X8}", ["flags"] = flags,
            ["amb"] = mt == null ? null : new[] { mt.AMB_R, mt.AMB_G, mt.AMB_B, mt.AMB_A }.Select(x => (int)x).ToArray(),
            ["dif"] = mt == null ? null : new[] { mt.DIF_R, mt.DIF_G, mt.DIF_B, mt.DIF_A }.Select(x => (int)x).ToArray(),
            ["spc"] = mt == null ? null : new[] { mt.SPC_R, mt.SPC_G, mt.SPC_B, mt.SPC_A }.Select(x => (int)x).ToArray(),
            ["alpha"] = mt?.Alpha ?? 1, ["shininess"] = mt?.Shininess ?? 0,
            ["pe"] = pe == null ? null : new Dictionary<string, object> { ["flags"] = pe.Flags.ToString(), ["blend"] = pe.BlendMode.ToString(), ["src"] = pe.SrcFactor.ToString(), ["dst"] = pe.DstFactor.ToString(), ["acmp0"] = pe.AlphaComp0.ToString(), ["aref0"] = (int)pe.AlphaRef0, ["aop"] = pe.AlphaOp.ToString(), ["acmp1"] = pe.AlphaComp1.ToString(), ["aref1"] = (int)pe.AlphaRef1, ["z"] = pe.DepthFunction.ToString() },
            ["tex"] = mo?.Textures?.List.Select(TexInfo).ToList() ?? new(),
        };
    }

    // the texture animations: matanim tree parallel to joints, one HSD_MatAnim per DObj
    public static List<Dictionary<string, object>> TexAnims(Model m, string outDir = null)
    {
        var res = new List<Dictionary<string, object>>();
        if (m.MatAnim == null) return res;
        var flat = new List<HSD_MatAnimJoint>();
        void F(HSD_MatAnimJoint j) { for (; j != null; j = j.Next) { flat.Add(j); F(j.Child); } }
        F(m.MatAnim);
        int di = 0;
        for (int ji = 0; ji < m.J.Count; ji++)
        {
            var mj = ji < flat.Count ? flat[ji] : null;
            var ma = mj?.MaterialAnimation;
            for (var d = m.J[ji].Dobj; d != null; d = d.Next, di++, ma = ma?.Next)
            {
                int ti = 0;
                for (var ta = ma?.TextureAnimation; ta != null; ta = ta.Next, ti++)
                {
                    var imgs = ta.ImageBuffers?.Array; var tls = ta.TlutBuffers?.Array;
                    var frames = new List<string>(); var sizes = new List<string>(); var keys = new List<string>(); int bytes = 0;
                    for (int ii = 0; imgs != null && ii < imgs.Length; ii++)
                    {
                        var im = imgs[ii].Data; if (im == null) continue;
                        var tl = tls != null && tls.Length > 0 ? tls[Math.Min(ii, tls.Length - 1)].Data : null;
                        sizes.Add($"{im.Width}x{im.Height} {im.Format}" + (tl != null ? $"/{tl.Format}x{tl.ColorCount}" : "")); bytes += im.ImageData?.Length ?? 0;
                        keys.Add(Convert.ToHexString(System.Security.Cryptography.SHA1.HashData(im.ImageData ?? new byte[0])).Substring(0, 10).ToLower());
                        if (outDir != null)
                        {
                            var rgba = tl != null ? HSDRaw.Tools.GXImageConverter.DecodeTPL(im.Format, im.Width, im.Height, im.ImageData, tl.Format, tl.ColorCount, tl.TlutData)
                                                  : HSDRaw.Tools.GXImageConverter.DecodeTPL(im.Format, im.Width, im.Height, im.ImageData);
                            var name = $"texanim_d{di}_t{ti}_{ii:D2}.png"; Png.Write(Path.Combine(outDir, name), rgba, im.Width, im.Height); frames.Add(name);
                        }
                    }
                    foreach (var tl in tls ?? new HSD_TlutBuffer[0]) bytes += tl.Data?.TlutData?.Length ?? 0;
                    res.Add(new() { ["dobj"] = di, ["joint"] = ji, ["texmap"] = ta.GXTexMapID.ToString(), ["images"] = imgs?.Length ?? 0, ["tluts"] = tls?.Length ?? 0, ["sizes"] = sizes.Distinct().ToList(), ["keys"] = keys, ["bytes"] = bytes, ["files"] = frames });
                }
            }
        }
        return res;
    }

    static string Arg(string[] a, string k) { int i = Array.IndexOf(a, k); return i >= 0 && i + 1 < a.Length ? a[i + 1] : null; }
    static HashSet<int> Ranges(string s) => s.Split(',').SelectMany(p => { var q = p.Split('-'); int a0 = int.Parse(q[0]), a1 = q.Length > 1 ? int.Parse(q[1]) : a0; return Enumerable.Range(a0, a1 - a0 + 1); }).ToHashSet();

    public static int Stats(string[] a)
    {
        var m = Load(a[1]);
        HashSet<int> hi = null, lo = null; int groups = 0;
        if (Arg(a, "--ft") != null) (hi, lo, groups) = Lookups(Arg(a, "--ft"));
        else if (m.RootName.EndsWith(".hat_joint")) (hi, lo, groups) = HatLods(a[1]);
        byte[] j2p = null;
        if (Arg(a, "--rig") != null)       // a new fighter (e.g. Geno, kind 34): its parts table is in the decomp, not PlCo
        {
            var rj = System.Text.Json.JsonDocument.Parse(File.ReadAllText(Arg(a, "--rig"))).RootElement;
            j2p = rj.GetProperty("joint_to_part").EnumerateArray().Select(e => (byte)e.GetInt32()).ToArray();
        }
        else if (Arg(a, "--co") != null)
        {
            var co = new HSDRawFile(Arg(a, "--co")).Roots[0].Data as HSDRaw.Melee.SBM_ftLoadCommonData;
            int kind = int.Parse(Arg(a, "--kind"));
            if (kind >= co.BoneTables.Length)
            {
                Console.Error.WriteLine($"meshstats: PlCo has parts tables for kinds 0-{co.BoneTables.Length - 1}; kind {kind} is a new fighter, pass --rig RIG.json");
                return 1;
            }
            var bt = co.BoneTables.Array[kind];
            j2p = bt._s.GetReference<HSDAccessor>(0x00)?._s.GetData();
        }
        var joints = new List<object>();
        for (int i = 0; i < m.J.Count; i++)
        {
            var w = m.World[i]; var j = m.J[i];
            joints.Add(new Dictionary<string, object> { ["i"] = i, ["p"] = m.Parent[i], ["part"] = j2p != null && i < j2p.Length ? j2p[i] : -1, ["x"] = w.M41, ["y"] = w.M42, ["z"] = w.M43, ["flags"] = (uint)j.Flags, ["dobjs"] = j.Dobj?.List.Count ?? 0 });
        }
        var dobjs = new List<object>();
        foreach (var d in m.D)
        {
            // per-triangle: dominant joint, world area, texel area of the base colour texture
            var mo = d.D.Mobj; var baseTex = mo?.Textures?.List.FirstOrDefault(t => ((int)t.Flags & 0xF) == 0 && t.ImageData != null);
            var byJoint = new Dictionary<int, double[]>();   // joint -> [tris, area, texelArea, texturedArea, min xyz, max xyz]
            var pos = new HashSet<(int, int, int)>();
            float ymin = 1e9f, ymax = -1e9f;
            foreach (var p in d.P) foreach (var t in p.T)
            {
                foreach (var v in new[] { t.A, t.B, t.C }) { pos.Add(((int)MathF.Round(v.P.X * 1000), (int)MathF.Round(v.P.Y * 1000), (int)MathF.Round(v.P.Z * 1000))); ymin = MathF.Min(ymin, v.P.Y); ymax = MathF.Max(ymax, v.P.Y); }
                var jw = new Dictionary<int, float>();
                foreach (var v in new[] { t.A, t.B, t.C }) foreach (var (jj, ww) in v.W) jw[jj] = jw.GetValueOrDefault(jj) + ww;
                int dom = jw.OrderByDescending(kv => kv.Value).First().Key;
                double area = Vector3.Cross(t.B.P - t.A.P, t.C.P - t.A.P).Length() / 2;
                double tarea = 0; bool has = false;
                if (baseTex != null)
                {
                    int ch = UVChan(baseTex);
                    if ((t.A.UVMask & (1 << ch)) != 0)
                    {
                        float sx = baseTex.ImageData.Width * Math.Max((int)baseTex.RepeatS, 1) / (baseTex.SX == 0 ? 1 : baseTex.SX);
                        float sy = baseTex.ImageData.Height * Math.Max((int)baseTex.RepeatT, 1) / (baseTex.SY == 0 ? 1 : baseTex.SY);
                        var ua = t.A.UV[ch] * new Vector2(sx, sy); var ub = t.B.UV[ch] * new Vector2(sx, sy); var uc = t.C.UV[ch] * new Vector2(sx, sy);
                        tarea = Math.Abs((ub.X - ua.X) * (uc.Y - ua.Y) - (uc.X - ua.X) * (ub.Y - ua.Y)) / 2; has = true;
                    }
                }
                if (!byJoint.TryGetValue(dom, out var acc)) { byJoint[dom] = acc = new double[10]; for (int q = 4; q < 7; q++) { acc[q] = 1e9; acc[q + 3] = -1e9; } }
                acc[0]++; acc[1] += area; if (has) { acc[2] += tarea; acc[3] += area; }
                foreach (var v in new[] { t.A, t.B, t.C }) { acc[4] = Math.Min(acc[4], v.P.X); acc[5] = Math.Min(acc[5], v.P.Y); acc[6] = Math.Min(acc[6], v.P.Z); acc[7] = Math.Max(acc[7], v.P.X); acc[8] = Math.Max(acc[8], v.P.Y); acc[9] = Math.Max(acc[9], v.P.Z); }
            }
            dobjs.Add(new Dictionary<string, object>
            {
                ["i"] = d.Index, ["joint"] = d.Joint, ["lod"] = hi == null ? "?" : hi.Contains(d.Index) ? "high" : lo.Contains(d.Index) ? "low" : "shared",
                ["class"] = d.D.ClassName, ["uniquePos"] = pos.Count, ["ymin"] = ymin, ["ymax"] = ymax,
                ["tris"] = d.P.Sum(p => p.Tris), ["degenerate"] = d.P.Sum(p => p.Degenerate), ["dlverts"] = d.P.Sum(p => p.DLVerts), ["prims"] = d.P.Sum(p => p.Prims),
                ["pobjs"] = d.P.Select(p => new Dictionary<string, object> { ["kind"] = p.Kind, ["flags"] = $"{p.Flags:X}", ["tris"] = p.Tris, ["dlverts"] = p.DLVerts, ["prims"] = p.Prims, ["envelopes"] = p.Envelopes, ["envhist"] = p.EnvHist, ["vinf"] = p.VInf, ["attrs"] = p.Attrs }).ToList(),
                ["byJoint"] = byJoint.ToDictionary(kv => kv.Key.ToString(), kv => kv.Value),
                ["mat"] = MatInfo(mo),
            });
        }
        var outObj = new Dictionary<string, object>
        {
            ["file"] = Path.GetFileName(a[1]), ["root"] = m.RootName, ["joints"] = joints, ["dobjs"] = dobjs, ["groups"] = groups,
            ["high"] = hi?.OrderBy(x => x).ToList(), ["low"] = lo?.OrderBy(x => x).ToList(),
            ["highGroups"] = Arg(a, "--ft") == null ? null : Groups(Arg(a, "--ft"), 0), ["lowGroups"] = Arg(a, "--ft") == null ? null : Groups(Arg(a, "--ft"), 1),
            ["dynamics"] = Arg(a, "--ft") == null ? null : Dynamics(Arg(a, "--ft")), ["texanims"] = TexAnims(m, Arg(a, "--texdir")),
        };
        if (Arg(a, "--texdir") != null)
        {   // every distinct texture as PNG, named by key
            foreach (var d in m.D) foreach (var t in d.D.Mobj?.Textures?.List ?? new List<HSD_TOBJ>())
            {
                var k = TexKey(t); if (k == null) continue; var fn = Path.Combine(Arg(a, "--texdir"), $"tex_{k}.png");
                if (!File.Exists(fn)) { var rgba = t.GetDecodedImageData(); if (rgba != null) Png.Write(fn, rgba, t.ImageData.Width, t.ImageData.Height); }
            }
        }
        Console.WriteLine(JsonSerializer.Serialize(outObj, new JsonSerializerOptions { WriteIndented = false }));
        return 0;
    }

    // ---- glTF export -----------------------------------------------------------------------------------------------------
    public static int Export(string[] a)
    {
        var m = Load(a[1], a.Contains("--metal")); var outPath = a[2];
        var dir = Path.GetDirectoryName(Path.GetFullPath(outPath)); Directory.CreateDirectory(dir);
        var stem = Path.GetFileNameWithoutExtension(outPath);
        HashSet<int> want = null;
        if (Arg(a, "--dobjs") != null) want = Ranges(Arg(a, "--dobjs"));
        else if (Arg(a, "--ft") != null)
        {
            // the model as shown by default: option 0 of every group of the high (or low) table, plus DObjs in neither table
            var (hi, lo, _) = Lookups(Arg(a, "--ft")); var lod = Arg(a, "--lod") ?? "high";
            var groups = Groups(Arg(a, "--ft"), lod == "low" ? 1 : 0);
            want = m.D.Select(d => d.Index).Where(i => lod == "all" || (!hi.Contains(i) && !lo.Contains(i))).ToHashSet();
            if (lod != "all") foreach (var g in groups) if (g.Count > 0) want.UnionWith(g[0]);
        }
        // orientation: GX strips' winding versus stored normals, measured over the model; flip if most faces point inward
        double agree = 0;
        foreach (var d in m.D) foreach (var p in d.P) foreach (var t in p.T)
            if (t.A.HasN) { var fn = Vector3.Cross(t.B.P - t.A.P, t.C.P - t.A.P); agree += Math.Sign(Vector3.Dot(fn, t.A.N + t.B.N + t.C.N)); }
        bool flip = agree < 0;

        var bin = new MemoryStream();
        var bufferViews = new List<object>(); var accessors = new List<object>();
        int View(byte[] data, int? target)
        {
            while (bin.Length % 4 != 0) bin.WriteByte(0);
            int off = (int)bin.Length; bin.Write(data);
            var bv = new Dictionary<string, object> { ["buffer"] = 0, ["byteOffset"] = off, ["byteLength"] = data.Length };
            if (target != null) bv["target"] = target.Value;
            bufferViews.Add(bv); return bufferViews.Count - 1;
        }
        int Acc(byte[] data, int comp, int count, string type, int? target, float[] min = null, float[] max = null, bool norm = false)
        {
            var ac = new Dictionary<string, object> { ["bufferView"] = View(data, target), ["componentType"] = comp, ["count"] = count, ["type"] = type };
            if (min != null) { ac["min"] = min; ac["max"] = max; }
            if (norm) ac["normalized"] = true;
            accessors.Add(ac); return accessors.Count - 1;
        }
        byte[] F(IEnumerable<float> fs) { var l = fs.ToArray(); var b = new byte[l.Length * 4]; Buffer.BlockCopy(l, 0, b, 0, b.Length); return b; }

        // nodes: joints first (index = joint index), then one mesh node
        var nodes = new List<Dictionary<string, object>>();
        for (int i = 0; i < m.J.Count; i++)
        {
            var j = m.J[i];
            Matrix4x4.Decompose(Local(j), out var s, out var q, out var t);
            var nd = new Dictionary<string, object> { ["name"] = $"J{i:D2}", ["translation"] = new[] { t.X, t.Y, t.Z }, ["rotation"] = new[] { q.X, q.Y, q.Z, q.W }, ["scale"] = new[] { s.X, s.Y, s.Z } };
            var ch = new List<int>(); for (int k = 0; k < m.J.Count; k++) if (m.Parent[k] == i) ch.Add(k);
            if (ch.Count > 0) nd["children"] = ch;
            nodes.Add(nd);
        }
        var ibm = new List<float>();
        for (int i = 0; i < m.J.Count; i++)
        {
            Matrix4x4.Invert(m.World[i], out var inv);
            // glTF is column-major with column vectors; System.Numerics is row-vector, so its row-major layout is glTF's column-major
            ibm.AddRange(new[] { inv.M11, inv.M12, inv.M13, inv.M14, inv.M21, inv.M22, inv.M23, inv.M24, inv.M31, inv.M32, inv.M33, inv.M34, inv.M41, inv.M42, inv.M43, inv.M44 });
        }
        int ibmAcc = Acc(F(ibm), 5126, m.J.Count, "MAT4", null);

        // materials, textures
        var images = new List<object>(); var textures = new List<object>(); var samplers = new List<object>(); var materials = new List<object>();
        var imgIdx = new Dictionary<string, int>(); var sampIdx = new Dictionary<string, int>();
        var sidecar = new List<object>();
        int Wrap(GXWrapMode w) => w == GXWrapMode.REPEAT ? 10497 : w == GXWrapMode.MIRROR ? 33648 : 33071;
        int TexIndex(HSD_TOBJ t)
        {
            var k = TexKey(t);
            if (!imgIdx.TryGetValue(k, out var ii))
            {
                var fn = $"{stem}_tex_{k}.png";
                var rgba = t.GetDecodedImageData(); Png.Write(Path.Combine(dir, fn), rgba, t.ImageData.Width, t.ImageData.Height);
                images.Add(new Dictionary<string, object> { ["uri"] = fn, ["name"] = k }); ii = images.Count - 1; imgIdx[k] = ii;
            }
            var sk = $"{Wrap(t.WrapS)}/{Wrap(t.WrapT)}";
            if (!sampIdx.TryGetValue(sk, out var si)) { samplers.Add(new Dictionary<string, object> { ["wrapS"] = Wrap(t.WrapS), ["wrapT"] = Wrap(t.WrapT), ["magFilter"] = 9729, ["minFilter"] = 9987 }); si = samplers.Count - 1; sampIdx[sk] = si; }
            textures.Add(new Dictionary<string, object> { ["source"] = ii, ["sampler"] = si }); return textures.Count - 1;
        }
        // Melee's texture matrix: uv' = (inverse(S R T) * uv) * repeat
        (float[] off, float[] sc, float rot) UVXf(HSD_TOBJ t)
        {
            float sx = (t.SX == 0 ? 1 : t.SX), sy = (t.SY == 0 ? 1 : t.SY);
            float rs = Math.Max((int)t.RepeatS, 1), rt = Math.Max((int)t.RepeatT, 1);
            return (new[] { -t.TX / sx * rs, -t.TY / sy * rt }, new[] { rs / sx, rt / sy }, 0);
        }

        var prims = new List<object>();
        int mi = 0;
        var matOfMobj = new Dictionary<HSDStruct, int>(ReferenceEqualityComparer.Instance);
        foreach (var d in m.D)
        {
            if (want != null && !want.Contains(d.Index)) continue;
            var tris = d.P.SelectMany(p => p.T).ToList();
            if (tris.Count == 0) continue;
            var mo = d.D.Mobj;
            if (!matOfMobj.TryGetValue(mo._s, out var matIndex))
            {
                var mat = new Dictionary<string, object> { ["name"] = $"{stem}_M{mi++:D2}_d{d.Index}" };
                var mt = mo.Material; var rf = mo.RenderFlags;
                var dif = mt == null ? new float[] { 1, 1, 1, 1 } : new float[] { mt.DIF_R / 255f, mt.DIF_G / 255f, mt.DIF_B / 255f, mt.Alpha };
                var pbr = new Dictionary<string, object> { ["metallicFactor"] = 0f, ["roughnessFactor"] = 0.85f };
                var layers = mo.Textures?.List.Where(t => t.ImageData != null).ToList() ?? new();
                var baseT = layers.FirstOrDefault(t => ((int)t.Flags & 0xF) == 0 && t.DiffuseLightmap && (((int)t.Flags >> 16) & 0xF) is 4 or 5)
                         ?? layers.FirstOrDefault(t => ((int)t.Flags & 0xF) == 0 && t.DiffuseLightmap);
                if (baseT != null)
                {
                    var ti = new Dictionary<string, object> { ["index"] = TexIndex(baseT), ["texCoord"] = UVChan(baseT) };
                    var (o, s, _) = UVXf(baseT);
                    if (o[0] != 0 || o[1] != 0 || s[0] != 1 || s[1] != 1) ti["extensions"] = new Dictionary<string, object> { ["KHR_texture_transform"] = new Dictionary<string, object> { ["offset"] = o, ["scale"] = s, ["texCoord"] = UVChan(baseT) } };
                    pbr["baseColorTexture"] = ti;
                    if ((((int)baseT.Flags >> 16) & 0xF) == 5) dif = new float[] { 1, 1, 1, dif[3] };
                }
                pbr["baseColorFactor"] = dif;
                mat["pbrMetallicRoughness"] = pbr;
                bool xlu = rf.HasFlag(RENDER_MODE.XLU) || (mt != null && mt.Alpha < 0.999f);
                var pe = mo.PEDesc;
                if (xlu) mat["alphaMode"] = "BLEND";
                else if (layers.Any(t => (((int)t.Flags >> 20) & 0xF) != 0) || (pe != null && pe.AlphaComp0 is GXCompareType.Greater or GXCompareType.GEqual)) { mat["alphaMode"] = "MASK"; mat["alphaCutoff"] = 0.5f; }
                // HSD's cull bits are relative to GX winding; the cast sets CULLFRONT on single-sided meshes. After the flip above
                // (faces agree with their normals) glTF's back-face culling is the equivalent; neither bit = double-sided.
                if ((d.P.Select(p => p.Flags).Aggregate(0, (x, y) => x | y) & ((int)POBJ_FLAG.CULLBACK | (int)POBJ_FLAG.CULLFRONT)) == 0) mat["doubleSided"] = true;
                materials.Add(mat); matIndex = materials.Count - 1; matOfMobj[mo._s] = matIndex;
                var mi_ = MatInfo(mo); mi_["gltf"] = matIndex; mi_["name"] = mat["name"];
                mi_["layers"] = layers.Select(t => new Dictionary<string, object> { ["png"] = $"{stem}_tex_{TexKey(t)}.png", ["info"] = TexInfo(t), ["xf"] = UVXf(t) is var x ? new { off = x.off, sc = x.sc } : null }).ToList();
                foreach (var t in layers) TexIndex(t);   // write every layer's PNG
                sidecar.Add(mi_);
            }
            // vertices: dedupe on every attribute
            var map = new Dictionary<string, int>(); var P = new List<Vector3>(); var N = new List<Vector3>(); var C = new List<Vector4>();
            var UV = Enumerable.Range(0, 4).Select(_ => new List<Vector2>()).ToArray();
            var JW = new List<(int[] j, float[] w)>(); var idx = new List<int>();
            int uvMask = tris.Aggregate(0, (x, t) => x | t.A.UVMask); bool hasC = tris.Any(t => t.A.HasC);
            foreach (var t in tris)
            {
                var order = flip ? new[] { t.A, t.C, t.B } : new[] { t.A, t.B, t.C };
                foreach (var v in order)
                {
                    var top = v.W.OrderByDescending(x => x.w).Take(4).ToList(); float sum = top.Sum(x => x.w); if (sum <= 0) sum = 1;
                    var js = new int[4]; var ws = new float[4]; for (int k = 0; k < top.Count; k++) { js[k] = top[k].j; ws[k] = top[k].w / sum; }
                    var key = $"{v.P.X:R},{v.P.Y:R},{v.P.Z:R},{v.N.X:R},{v.N.Y:R},{v.N.Z:R},{v.UV[0].X:R},{v.UV[0].Y:R},{v.UV[1].X:R},{v.UV[1].Y:R},{v.UV[2].X:R},{v.UV[2].Y:R},{v.C},{string.Join(":", js)},{string.Join(":", ws)}";
                    if (!map.TryGetValue(key, out var vi))
                    {
                        vi = P.Count; map[key] = vi; P.Add(v.P); N.Add(v.HasN ? v.N : Vector3.UnitY); C.Add(v.C / 255f);
                        for (int k = 0; k < 4; k++) UV[k].Add(v.UV[k]); JW.Add((js, ws));
                    }
                    idx.Add(vi);
                }
            }
            var attrs = new Dictionary<string, object>();
            var mn = new float[] { P.Min(p => p.X), P.Min(p => p.Y), P.Min(p => p.Z) }; var mx = new float[] { P.Max(p => p.X), P.Max(p => p.Y), P.Max(p => p.Z) };
            attrs["POSITION"] = Acc(F(P.SelectMany(p => new[] { p.X, p.Y, p.Z })), 5126, P.Count, "VEC3", 34962, mn, mx);
            attrs["NORMAL"] = Acc(F(N.SelectMany(p => new[] { p.X, p.Y, p.Z })), 5126, N.Count, "VEC3", 34962);
            for (int k = 0; k < 4; k++) if ((uvMask & (1 << k)) != 0) attrs[$"TEXCOORD_{k}"] = Acc(F(UV[k].SelectMany(p => new[] { p.X, p.Y })), 5126, P.Count, "VEC2", 34962);
            if (hasC) attrs["COLOR_0"] = Acc(F(C.SelectMany(p => new[] { p.X, p.Y, p.Z, p.W })), 5126, P.Count, "VEC4", 34962);
            var jb = new byte[JW.Count * 8]; for (int k = 0; k < JW.Count; k++) for (int q = 0; q < 4; q++) { jb[k * 8 + q * 2] = (byte)JW[k].j[q]; jb[k * 8 + q * 2 + 1] = (byte)(JW[k].j[q] >> 8); }
            attrs["JOINTS_0"] = Acc(jb, 5123, JW.Count, "VEC4", 34962);
            attrs["WEIGHTS_0"] = Acc(F(JW.SelectMany(x => x.w)), 5126, JW.Count, "VEC4", 34962);
            var ib = new byte[idx.Count * 4]; Buffer.BlockCopy(idx.ToArray(), 0, ib, 0, ib.Length);
            int ia = Acc(ib, 5125, idx.Count, "SCALAR", 34963);
            prims.Add(new Dictionary<string, object> { ["attributes"] = attrs, ["indices"] = ia, ["material"] = matIndex, ["extras"] = new Dictionary<string, object> { ["dobj"] = d.Index, ["joint"] = d.Joint } });
        }
        int meshNode = nodes.Count;
        nodes.Add(new Dictionary<string, object> { ["name"] = stem, ["mesh"] = 0, ["skin"] = 0 });
        var gl = new Dictionary<string, object>
        {
            ["asset"] = new Dictionary<string, object> { ["version"] = "2.0", ["generator"] = "datkit export (animation-pipeline)" },
            ["extensionsUsed"] = new[] { "KHR_texture_transform" },
            ["scene"] = 0, ["scenes"] = new[] { new Dictionary<string, object> { ["nodes"] = new[] { 0, meshNode } } },
            ["nodes"] = nodes, ["meshes"] = new[] { new Dictionary<string, object> { ["name"] = stem, ["primitives"] = prims } },
            ["skins"] = new[] { new Dictionary<string, object> { ["joints"] = Enumerable.Range(0, m.J.Count).ToArray(), ["inverseBindMatrices"] = ibmAcc, ["skeleton"] = 0 } },
            ["materials"] = materials, ["textures"] = textures, ["images"] = images, ["samplers"] = samplers,
            ["accessors"] = accessors, ["bufferViews"] = bufferViews,
            ["buffers"] = new[] { new Dictionary<string, object> { ["uri"] = stem + ".bin", ["byteLength"] = (int)bin.Length } },
        };
        File.WriteAllBytes(Path.Combine(dir, stem + ".bin"), bin.ToArray());
        File.WriteAllText(outPath, JsonSerializer.Serialize(gl));
        File.WriteAllText(Path.Combine(dir, stem + ".melee.json"), JsonSerializer.Serialize(new Dictionary<string, object> { ["flipped"] = flip, ["materials"] = sidecar, ["texanims"] = TexAnims(m) }, new JsonSerializerOptions { WriteIndented = true }));
        Console.WriteLine($"{outPath}: {prims.Count} primitives, {materials.Count} materials, {images.Count} images, {m.J.Count} joints, flip={flip}");
        return 0;
    }
}
