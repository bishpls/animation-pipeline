// GltfModel: import a skinned, textured glTF as a Melee fighter's costume meshes (the inverse of ModelSpec's export).
//   gltf-model RIG.json OUT_PlXxNr.dat [--high H.gltf] [--low L.gltf] [--eyes] [--template-nr PlMrNr.dat] [--template-ft PlMr.dat] [--name Geno]
//                                                       a costume file alone, from the rig's skeleton and the glTF's meshes
//   model-tables PlXx.dat [PlXxNr.dat] [--poses]        a fighter's lookup tables, metal model, material lookups, texture
//                                                       animations and model-part poses, as JSON (the cast's templates)
// fighter-build calls Import() when rig.json names a model ("model": {"high": ..., "low": ..., "eyes": [...]}).
//
// Conventions (measured on the cast, ~/games/melee/work/art/spec/SPEC.md; ModelSpec.cs reads them back):
//  - the skeleton is the rig's; glTF joints are matched by name: the rig's joint names, or "J%02d", an index into the
//    skeleton the glTF was skinned to (rig.json "jnames", else the rig's own order). A glTF joint the rig lacks passes
//    its weight to its nearest matched ancestor (reported).
//  - each vertex keeps the glTF's rest-pose shape and moves by its joints' position differences from the rig (weighted);
//    bone orientations (Blender's head/tail/roll) are ignored. Single-weight vertices are stored in their joint's frame,
//    multi-weight ones in bind (model) space; every DObj hangs on the root joint, as the cast's do.
//  - one DObj per glTF primitive, one MObj each, cloned from the template's (Mario's): DIFFUSE+TEX0, diffuse = ambient
//    (179,179,179), white specular, shininess 50; TObj UV + diffuse lightmap + REPLACE, the template's TEV. A material
//    that asks for a sheen adds SPECULAR; a specular map becomes a second, specular-lightmap layer on TEX1.
//  - GX front faces are clockwise: glTF's counter-clockwise triangles are reversed, and a single-sided material gets
//    the cast's cull bit (HSDRaw's CULLFRONT = the decomp's POBJ_CULLBACK); doubleSided gets none.
//  - textures: CMP; CI8 with an RGB565 palette for eyes (padded to whole tiles, as Mario's 190x190 are); a masked or
//    blended material's alpha through an RGB5A3 palette (or RGB5A3). Override per material: extras {"melee": {"format": "CI8"}}.
using System.Numerics;
using System.Text.Json;
using System.Text.RegularExpressions;
using HSDRaw;
using HSDRaw.Common;
using HSDRaw.Common.Animation;
using HSDRaw.GX;
using HSDRaw.Melee.Pl;
using HSDRaw.Tools;

static partial class GltfModel
{
    // ---- what to import (rig.json "model") -------------------------------------------------------------------------
    public class Spec
    {
        public string High, Low;                       // glTF paths
        public List<string> JNames;                    // the skeleton "J%02d" names index (default: the rig's own order)
        public Dictionary<string, (int slot, List<string> frames)> Eyes = new();   // material name -> eye slot, frame PNGs
        public float WeightStep = 0.05f;               // skin weights snap to multiples of this (the cast's are 0.05s)
        public float MaxRebind = 1.0f;                 // a glTF joint farther than this from the rig's is an error (a name mix-up)

        public static Spec From(JsonElement rig, JsonElement m, string baseDir)
        {
            string P(string s) => s == null ? null : Path.GetFullPath(Path.Combine(baseDir, s.StartsWith("~/") ? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), s[2..]) : s));
            var sp = new Spec { High = P(m.GetProperty("high").GetString()), Low = m.TryGetProperty("low", out var lo) && lo.ValueKind == JsonValueKind.String ? P(lo.GetString()) : null };
            JsonElement jn;
            if (m.TryGetProperty("jnames", out jn) || rig.TryGetProperty("jnames", out jn)) sp.JNames = jn.EnumerateArray().Select(e => e.GetString()).ToList();
            if (m.TryGetProperty("weight_step", out var ws)) sp.WeightStep = (float)ws.GetDouble();
            if (m.TryGetProperty("max_rebind", out var mr)) sp.MaxRebind = (float)mr.GetDouble();
            if (m.TryGetProperty("eyes", out var ey))
            {
                int slot = 0;
                foreach (var e in ey.EnumerateArray())
                {
                    var dir = Path.GetDirectoryName(sp.High);
                    var frames = e.TryGetProperty("frames", out var fr) ? fr.EnumerateArray().Select(f => Path.GetFullPath(Path.Combine(dir, f.GetString()))).ToList() : new List<string>();
                    sp.Eyes[e.GetProperty("material").GetString()] = (e.TryGetProperty("slot", out var sl) ? sl.GetInt32() : slot, frames);
                    slot++;
                }
            }
            return sp;
        }
    }

    public class Skel { public List<HSD_JOBJ> J; public List<Matrix4x4> W; public List<string> Names; }

    public class Result
    {
        public List<HSD_DOBJ> Dobjs = new();                              // the main model's DObjs on the root joint, in order
        public List<List<List<int>>> High = new(), Low = new();           // visibility groups -> options -> DObj indices
        public HSD_MatAnimJoint MatAnim;                                  // the costume's material-animation tree
        public List<int> EyeTobjs = new();                                // material lookups: the TObj index of each eye slot
        public List<HSD_DOBJ> Metal = new();                              // the metal model's DObjs (on its own skeleton)
        public List<List<int>> MetalBody = new();                         // the metal DObjs per body option (group 0)
        public List<string> Log = new();
        public int HighTris, LowTris, HighPobjs, LowPobjs, TexBytes, Textures;
    }

    // ---- templates: the cast's material, texture and polygon setup, copied from a costume file (Mario's) ------------
    class Templates
    {
        public HSD_MOBJ Base, Plain, Metal;        // DIFFUSE+TEX0 with one UV/diffuse/REPLACE CMP layer; untextured; metal
        public HSD_TOBJ BaseTex, EyeTex, SpecTex;  // base colour layer; the CI8 eye layer; the specular-map layer (TEX1)
        public HSD_TexAnim EyeAnim;                // an eye's texture animation (image + palette tracks)
        public POBJ_FLAG PobjBits;                 // the low flag bits the cast's envelope PObjs carry (0x0001)

        public static Templates Load(string nrPath, string ftPath)
        {
            var t = new Templates();
            var m = ModelSpec.Load(nrPath);
            bool IsUV(HSD_TOBJ x) => ((int)x.Flags & 0xF) == 0;
            int ColorOp(HSD_TOBJ x) => ((int)x.Flags >> 16) & 0xF;
            foreach (var d in m.D)
            {
                var mo = d.D.Mobj; if (mo == null) continue;
                var tex = mo.Textures?.List ?? new List<HSD_TOBJ>();
                if (t.Base == null && (uint)mo.RenderFlags == 0x14 && tex.Count == 1 && tex[0].ImageData?.Format == GXTexFmt.CMP && IsUV(tex[0]) && tex[0].DiffuseLightmap && ColorOp(tex[0]) == 5)
                { t.Base = mo; t.BaseTex = tex[0]; }
                if (t.EyeTex == null && tex.Count == 1 && tex[0].ImageData?.Format == GXTexFmt.CI8 && IsUV(tex[0]) && tex[0].DiffuseLightmap) t.EyeTex = tex[0];
                if (t.SpecTex == null) t.SpecTex = tex.Skip(1).FirstOrDefault(x => x.SpecularLightmap && IsUV(x));
                if (t.Plain == null && tex.Count == 0) t.Plain = mo;
                foreach (var p in d.P) if (t.PobjBits == 0 && (p.Flags & (int)POBJ_FLAG.ENVELOPE) != 0) t.PobjBits = (POBJ_FLAG)(p.Flags & 0xF);
            }
            if (t.Base == null) throw new Exception($"{nrPath}: no DIFFUSE+TEX0 CMP material to copy");
            t.EyeTex ??= t.BaseTex; t.SpecTex ??= t.BaseTex;
            if (t.Plain == null) { t.Plain = HSDAccessor.DeepClone<HSD_MOBJ>(t.Base); t.Plain.Textures = null; t.Plain.RenderFlags = RENDER_MODE.DIFFUSE; }
            // the eye texture animation: the first image-swapping texanim on a CI8 layer
            var flat = new List<HSD_MatAnimJoint>();
            void F(HSD_MatAnimJoint j) { for (; j != null; j = j.Next) { flat.Add(j); F(j.Child); } }
            F(m.MatAnim);
            for (int ji = 0; ji < m.J.Count && t.EyeAnim == null; ji++)
            {
                var ma = ji < flat.Count ? flat[ji].MaterialAnimation : null;
                for (var d = m.J[ji].Dobj; d != null && t.EyeAnim == null; d = d.Next, ma = ma?.Next)
                    for (var ta = ma?.TextureAnimation; ta != null; ta = ta.Next)
                        if (ta.ImageCount > 1) { t.EyeAnim = ta; break; }
            }
            if (ftPath != null && File.Exists(ftPath))
            {
                var ft = new HSDRawFile(ftPath).Roots.First(r => r.Name.StartsWith("ftData")).Data as SBM_FighterData;
                void W(HSD_JOBJ j) { for (; j != null && t.Metal == null; j = j.Next) { if (j.Dobj?.Mobj != null) t.Metal = j.Dobj.Mobj; W(j.Child); } }
                W(ft?.MetalModel);
            }
            return t;
        }
    }

    // ---- glTF --------------------------------------------------------------------------------------------------------
    public class Gltf
    {
        public JsonElement R; public string Dir, File_; public List<byte[]> Buf = new();
        public int[] Parent; public Matrix4x4[] World; public string[] Name;

        public static Gltf Load(string path)
        {
            var g = new Gltf { File_ = path, Dir = Path.GetDirectoryName(Path.GetFullPath(path)) };
            var bytes = File.ReadAllBytes(path); byte[] bin = null;
            if (bytes.Length >= 12 && BitConverter.ToUInt32(bytes, 0) == 0x46546C67)            // .glb: JSON chunk + BIN chunk
            {
                string json = null;
                for (int off = 12; off + 8 <= bytes.Length;)
                {
                    int len = BitConverter.ToInt32(bytes, off); uint type = BitConverter.ToUInt32(bytes, off + 4);
                    if (type == 0x4E4F534A) json = System.Text.Encoding.UTF8.GetString(bytes, off + 8, len);
                    else if (type == 0x004E4942) bin = bytes.AsSpan(off + 8, len).ToArray();
                    off += 8 + len;
                }
                g.R = JsonDocument.Parse(json).RootElement;
            }
            else g.R = JsonDocument.Parse(bytes).RootElement;
            foreach (var b in g.Arr("buffers")) g.Buf.Add(b.TryGetProperty("uri", out var u) ? g.ReadUri(u.GetString()) : bin);
            int n = g.Count("nodes");
            g.Parent = Enumerable.Repeat(-1, n).ToArray(); g.World = new Matrix4x4[n]; g.Name = new string[n];
            var local = new Matrix4x4[n];
            for (int i = 0; i < n; i++)
            {
                var nd = g.El("nodes", i);
                g.Name[i] = nd.TryGetProperty("name", out var nm) ? nm.GetString() : $"node{i}";
                if (nd.TryGetProperty("children", out var ch)) foreach (var c in ch.EnumerateArray()) g.Parent[c.GetInt32()] = i;
                local[i] = LocalOf(nd);
            }
            var done = new bool[n];
            Matrix4x4 Wd(int i) { if (!done[i]) { g.World[i] = g.Parent[i] >= 0 ? local[i] * Wd(g.Parent[i]) : local[i]; done[i] = true; } return g.World[i]; }
            for (int i = 0; i < n; i++) Wd(i);
            return g;
        }

        byte[] ReadUri(string uri) => uri.StartsWith("data:") ? Convert.FromBase64String(uri[(uri.IndexOf(',') + 1)..])
                                                              : File.ReadAllBytes(Path.Combine(Dir, Uri.UnescapeDataString(uri)));
        public IEnumerable<JsonElement> Arr(string k) => R.TryGetProperty(k, out var e) ? e.EnumerateArray() : Enumerable.Empty<JsonElement>();
        public int Count(string k) => R.TryGetProperty(k, out var e) ? e.GetArrayLength() : 0;
        public JsonElement El(string k, int i) => R.GetProperty(k)[i];

        static float[] Fl(JsonElement e) => e.EnumerateArray().Select(x => (float)x.GetDouble()).ToArray();
        // System.Numerics is row-vector (v * M); glTF's column-major arrays read in order give exactly that form
        public static Matrix4x4 M16(float[] f, int o = 0) => new Matrix4x4(f[o], f[o + 1], f[o + 2], f[o + 3], f[o + 4], f[o + 5], f[o + 6], f[o + 7], f[o + 8], f[o + 9], f[o + 10], f[o + 11], f[o + 12], f[o + 13], f[o + 14], f[o + 15]);
        static Matrix4x4 LocalOf(JsonElement nd)
        {
            if (nd.TryGetProperty("matrix", out var m)) return M16(Fl(m));
            var t = nd.TryGetProperty("translation", out var te) ? Fl(te) : new float[] { 0, 0, 0 };
            var r = nd.TryGetProperty("rotation", out var re) ? Fl(re) : new float[] { 0, 0, 0, 1 };
            var s = nd.TryGetProperty("scale", out var se) ? Fl(se) : new float[] { 1, 1, 1 };
            return Matrix4x4.CreateScale(s[0], s[1], s[2]) * Matrix4x4.CreateFromQuaternion(new Quaternion(r[0], r[1], r[2], r[3])) * Matrix4x4.CreateTranslation(t[0], t[1], t[2]);
        }

        public float[][] Read(int ai)
        {
            var a = El("accessors", ai);
            if (a.TryGetProperty("sparse", out _)) throw new Exception($"accessor {ai}: sparse accessors are not supported");
            int count = a.GetProperty("count").GetInt32(), comp = a.GetProperty("componentType").GetInt32();
            int nc = a.GetProperty("type").GetString() switch { "SCALAR" => 1, "VEC2" => 2, "VEC3" => 3, "VEC4" => 4, "MAT2" => 4, "MAT3" => 9, "MAT4" => 16, var t => throw new Exception("accessor type " + t) };
            bool norm = a.TryGetProperty("normalized", out var ne) && ne.GetBoolean();
            int cs = comp switch { 5120 or 5121 => 1, 5122 or 5123 => 2, 5125 or 5126 => 4, _ => throw new Exception("component type " + comp) };
            var res = new float[count][];
            if (!a.TryGetProperty("bufferView", out var bve)) { for (int i = 0; i < count; i++) res[i] = new float[nc]; return res; }
            var bv = El("bufferViews", bve.GetInt32()); var buf = Buf[bv.GetProperty("buffer").GetInt32()];
            int off = (bv.TryGetProperty("byteOffset", out var bo) ? bo.GetInt32() : 0) + (a.TryGetProperty("byteOffset", out var ao) ? ao.GetInt32() : 0);
            int stride = bv.TryGetProperty("byteStride", out var st) ? st.GetInt32() : nc * cs;
            for (int i = 0; i < count; i++)
            {
                var v = new float[nc]; int p = off + i * stride;
                for (int c = 0; c < nc; c++, p += cs)
                    v[c] = comp switch
                    {
                        5126 => BitConverter.ToSingle(buf, p),
                        5121 => norm ? buf[p] / 255f : buf[p],
                        5120 => norm ? Math.Max((sbyte)buf[p] / 127f, -1) : (sbyte)buf[p],
                        5123 => norm ? BitConverter.ToUInt16(buf, p) / 65535f : BitConverter.ToUInt16(buf, p),
                        5122 => norm ? Math.Max(BitConverter.ToInt16(buf, p) / 32767f, -1) : BitConverter.ToInt16(buf, p),
                        _ => BitConverter.ToUInt32(buf, p),
                    };
                res[i] = v;
            }
            return res;
        }

        public byte[] ImageBytes(int ii)
        {
            var im = El("images", ii);
            if (im.TryGetProperty("uri", out var u)) return ReadUri(u.GetString());
            var bv = El("bufferViews", im.GetProperty("bufferView").GetInt32()); var buf = Buf[bv.GetProperty("buffer").GetInt32()];
            return buf.AsSpan(bv.TryGetProperty("byteOffset", out var bo) ? bo.GetInt32() : 0, bv.GetProperty("byteLength").GetInt32()).ToArray();
        }
        public string ImageName(int ii)
        {
            var im = El("images", ii);
            return im.TryGetProperty("name", out var n) ? n.GetString() : im.TryGetProperty("uri", out var u) && !u.GetString().StartsWith("data:") ? Path.GetFileNameWithoutExtension(u.GetString()) : $"image{ii}";
        }
    }

    // ---- one glTF primitive, re-bound to the rig: model-space positions and normals, influences in rig joints ---------
    class Prim
    {
        public string Name; public int Mat = -1; public JsonElement MatJ; public bool HasMat;
        public List<Vector3> P = new(), N = new(); public List<Vector2>[] UV = { new(), new(), new(), new() }; public int UVMask;
        public List<(int j, float w)[]> Inf = new();
        public List<int> Tri = new();                  // corner vertex indices, GX order (clockwise)
        public int Group, Option, Degenerate;
        public string MatName => HasMat && MatJ.TryGetProperty("name", out var n) ? n.GetString() : $"material{Mat}";
    }

    static JsonElement? Melee(JsonElement e) => e.ValueKind == JsonValueKind.Object && e.TryGetProperty("extras", out var x) && x.ValueKind == JsonValueKind.Object && x.TryGetProperty("melee", out var m) ? m : null;

    static List<Prim> ReadPrims(Gltf g, Skel sk, Spec sp, List<string> log, string lod)
    {
        var rigIndex = new Dictionary<string, int>(); for (int i = 0; i < sk.Names.Count; i++) rigIndex[sk.Names[i]] = i;
        var jn = sp.JNames ?? sk.Names;
        var inv = sk.W.Select(w => { Matrix4x4.Invert(w, out var iw); return iw; }).ToList();
        string Named(string n)
        {
            if (rigIndex.ContainsKey(n)) return n;
            var mm = Regex.Match(n, @"^J(\d+)$");
            return mm.Success && int.Parse(mm.Groups[1].Value) < jn.Count && rigIndex.ContainsKey(jn[int.Parse(mm.Groups[1].Value)]) ? jn[int.Parse(mm.Groups[1].Value)] : null;
        }
        int Map(int node) => Named(g.Name[node]) is string s ? rigIndex[s] : -1;
        // the nearest ancestor node that maps to a rig joint
        int Anc(int node) { for (int a = g.Parent[node]; a >= 0; a = g.Parent[a]) if (Map(a) >= 0) return a; return -1; }

        // per skin: mesh space -> glTF world at bind (M), and per glTF joint its rig joint and how far the rig's joint sits
        // from the glTF's bind position. A vertex keeps the modeller's rest shape and moves only by its joints' position
        // differences (weighted): bone orientations (Blender's head/tail/roll) never rotate the mesh.
        var skins = new List<(int[] rig, Vector3[] off, Matrix4x4 M)>();
        var unmapped = new SortedDictionary<string, string>(); double maxDev = 0, maxRot = 0, posed = 0; string devJ = "";
        foreach (var s in g.Arr("skins"))
        {
            var joints = s.GetProperty("joints").EnumerateArray().Select(e => e.GetInt32()).ToArray();
            float[][] ibm = s.TryGetProperty("inverseBindMatrices", out var ib) ? g.Read(ib.GetInt32()) : null;
            var IBM = Enumerable.Range(0, joints.Length).Select(k => ibm != null ? Gltf.M16(ibm[k]) : Matrix4x4.Identity).ToArray();
            // at rest, IBM * joint world is the same mesh -> world matrix for every joint; if not, the file was saved posed
            var D = Enumerable.Range(0, joints.Length).Select(k => IBM[k] * g.World[joints[k]]).ToArray();
            int root = 0; for (int k = 0; k < joints.Length; k++) if (!joints.Contains(g.Parent[joints[k]])) { root = k; break; }
            var M = D[root];
            foreach (var d in D) posed = Math.Max(posed, MaxAbs(d - M));
            var rig = new int[joints.Length]; var off = new Vector3[joints.Length];
            for (int k = 0; k < joints.Length; k++)
            {
                Matrix4x4.Invert(IBM[k], out var b); var bind = b * M;      // the joint's bind matrix in glTF world
                int node = joints[k], r = Map(node);
                if (r >= 0)
                {
                    rig[k] = r; off[k] = sk.W[r].Translation - bind.Translation;
                    if (off[k].Length() > maxDev) { maxDev = off[k].Length(); devJ = $"{g.Name[node]}->{sk.Names[r]}"; }
                    maxRot = Math.Max(maxRot, Angle(bind, sk.W[r]));
                }
                else
                {   // a joint the rig lacks: its weight goes to its nearest matched ancestor, which moves it as it moves
                    int a = Anc(node); int ra = a >= 0 ? Map(a) : 0;
                    rig[k] = ra; off[k] = sk.W[ra].Translation - (a >= 0 ? g.World[a].Translation : Vector3.Zero);
                    unmapped[g.Name[node]] = sk.Names[ra];
                }
            }
            skins.Add((rig, off, M));
        }
        log.Add($"{lod}: {Path.GetFileName(g.File_)}: {g.Count("skins")} skin(s); bind pose vs rig rest: max {maxDev:0.####} units ({devJ}), bone orientations differ by up to {maxRot:0.#} deg (ignored)");
        if (unmapped.Count > 0) log.Add($"{lod}: glTF joints the rig lacks (weights passed to the ancestor; add them to rig.py JOINTS): " + string.Join(", ", unmapped.Select(kv => $"{kv.Key}->{kv.Value}")));
        if (maxDev > sp.MaxRebind) throw new Exception($"{lod}: the glTF's joint {devJ} sits {maxDev:0.###} units from the rig's: a joint-name mix-up? (J%02d names resolve through rig.json \"jnames\"; model.max_rebind raises the limit)");
        if (maxDev > 0.05) log.Add($"{lod}: WARNING: the glTF skeleton differs from the rig by {maxDev:0.###} units at {devJ}: vertices move with their joints to the rig's rest pose (check jnames if J%02d names were remapped)");
        if (posed > 1e-3) log.Add($"{lod}: WARNING: the skeleton was saved posed away from its bind pose (by up to {posed:0.###}): the bind pose is used; export in rest pose");

        var prims = new List<Prim>(); int nNoNormal = 0, nMany = 0, nRigid = 0;
        for (int ni = 0; ni < g.Count("nodes"); ni++)
        {
            var node = g.El("nodes", ni);
            if (!node.TryGetProperty("mesh", out var mi)) continue;
            var mesh = g.El("meshes", mi.GetInt32());
            int skin = node.TryGetProperty("skin", out var sknode) ? sknode.GetInt32() : -1;
            // an unskinned mesh rides its nearest matched ancestor joint (Blender's bone parenting), else the root
            int rigidA = Map(ni) >= 0 ? ni : Anc(ni);
            Matrix4x4 rigidM = g.World[ni]; var rigidOff = rigidA >= 0 ? sk.W[Map(rigidA)].Translation - g.World[rigidA].Translation : Vector3.Zero;
            int pi = 0;
            foreach (var pr in mesh.GetProperty("primitives").EnumerateArray())
            {
                var p = new Prim { Name = (mesh.TryGetProperty("name", out var mn) ? mn.GetString() : g.Name[ni]) + (mesh.GetProperty("primitives").GetArrayLength() > 1 ? $".{pi}" : "") };
                pi++;
                int mode = pr.TryGetProperty("mode", out var md) ? md.GetInt32() : 4;
                if (mode < 4) { log.Add($"{lod}: {p.Name}: primitive mode {mode} (points/lines) skipped"); continue; }
                if (pr.TryGetProperty("material", out var mt)) { p.Mat = mt.GetInt32(); p.MatJ = g.El("materials", p.Mat); p.HasMat = true; }
                foreach (var src in new[] { Melee(node), Melee(mesh), Melee(pr), p.HasMat ? Melee(p.MatJ) : null })
                    if (src is JsonElement x) { if (x.TryGetProperty("group", out var gg)) p.Group = gg.GetInt32(); if (x.TryGetProperty("option", out var oo)) p.Option = oo.GetInt32(); }
                var at = pr.GetProperty("attributes");
                var pos = g.Read(at.GetProperty("POSITION").GetInt32());
                var nrm = at.TryGetProperty("NORMAL", out var na) ? g.Read(na.GetInt32()) : null;
                var uvs = new float[4][][];
                for (int k = 0; k < 4; k++) if (at.TryGetProperty($"TEXCOORD_{k}", out var ta)) { uvs[k] = g.Read(ta.GetInt32()); p.UVMask |= 1 << k; }
                var js = new List<float[][]>(); var ws = new List<float[][]>();
                for (int k = 0; at.TryGetProperty($"JOINTS_{k}", out var ja) && at.TryGetProperty($"WEIGHTS_{k}", out var wa); k++) { js.Add(g.Read(ja.GetInt32())); ws.Add(g.Read(wa.GetInt32())); }
                int nv = pos.Length;
                var idx = pr.TryGetProperty("indices", out var ie) ? g.Read(ie.GetInt32()).Select(v => (int)v[0]).ToArray() : Enumerable.Range(0, nv).ToArray();
                var tris = new List<(int, int, int)>();
                if (mode == 4) for (int k = 0; k + 2 < idx.Length; k += 3) tris.Add((idx[k], idx[k + 1], idx[k + 2]));
                else if (mode == 5) for (int k = 0; k + 2 < idx.Length; k++) tris.Add((k & 1) == 0 ? (idx[k], idx[k + 1], idx[k + 2]) : (idx[k + 1], idx[k], idx[k + 2]));
                else if (mode == 6) for (int k = 1; k + 1 < idx.Length; k++) tris.Add((idx[0], idx[k], idx[k + 1]));
                if (nrm == null)
                {   // smooth normals from the faces (area weighted, by position)
                    nNoNormal++; nrm = new float[nv][]; var acc = new Dictionary<(float, float, float), Vector3>();
                    Vector3 V(int i) => new(pos[i][0], pos[i][1], pos[i][2]);
                    foreach (var (a, b, c) in tris) { var fn = Vector3.Cross(V(b) - V(a), V(c) - V(a)); foreach (var i in new[] { a, b, c }) { var key = (pos[i][0], pos[i][1], pos[i][2]); acc[key] = acc.GetValueOrDefault(key) + fn; } }
                    for (int i = 0; i < nv; i++) { var s = acc.GetValueOrDefault((pos[i][0], pos[i][1], pos[i][2])); s = s.LengthSquared() > 0 ? Vector3.Normalize(s) : Vector3.UnitY; nrm[i] = new[] { s.X, s.Y, s.Z }; }
                }
                // UV transforms on the textures this material uses are baked into their UV sets
                var xf = new Matrix3x2?[4];
                if (p.HasMat) foreach (var ti in TexRefs(p.MatJ))
                    if (ti.TryGetProperty("extensions", out var ex) && ex.TryGetProperty("KHR_texture_transform", out var tt))
                    {
                        int tc = tt.TryGetProperty("texCoord", out var tce) ? tce.GetInt32() : ti.TryGetProperty("texCoord", out var tc0) ? tc0.GetInt32() : 0;
                        var off = tt.TryGetProperty("offset", out var oe) ? oe.EnumerateArray().Select(e => (float)e.GetDouble()).ToArray() : new float[] { 0, 0 };
                        var sc = tt.TryGetProperty("scale", out var se) ? se.EnumerateArray().Select(e => (float)e.GetDouble()).ToArray() : new float[] { 1, 1 };
                        float rot = tt.TryGetProperty("rotation", out var re) ? (float)re.GetDouble() : 0;
                        // glTF: uv' = T * R * S * uv, with R rotating by -rotation in these (v down) coordinates
                        xf[tc] = Matrix3x2.CreateScale(sc[0], sc[1]) * new Matrix3x2(MathF.Cos(rot), -MathF.Sin(rot), MathF.Sin(rot), MathF.Cos(rot), 0, 0) * Matrix3x2.CreateTranslation(off[0], off[1]);
                    }
                // vertices
                var sE = skin >= 0 ? skins[skin] : default;
                for (int v = 0; v < nv; v++)
                {
                    var pv = new Vector3(pos[v][0], pos[v][1], pos[v][2]); var nvv = new Vector3(nrm[v][0], nrm[v][1], nrm[v][2]);
                    Vector3 P = Vector3.Zero, N = Vector3.Zero; var inf = new Dictionary<int, float>(); float wsum = 0;
                    if (skin >= 0 && js.Count > 0)
                    {
                        for (int s = 0; s < js.Count; s++)
                            for (int c = 0; c < 4; c++)
                            {
                                float w = ws[s][v][c]; if (w <= 0) continue;
                                int k = (int)js[s][v][c];
                                P += w * (Vector3.Transform(pv, sE.M) + sE.off[k]); N += w * Vector3.TransformNormal(nvv, sE.M); wsum += w;
                                inf[sE.rig[k]] = inf.GetValueOrDefault(sE.rig[k]) + w;
                            }
                    }
                    if (wsum <= 0)
                    {   // unweighted: rigid on the mesh's ancestor joint (or the root)
                        if (skin >= 0) nRigid++;
                        P = Vector3.Transform(pv, skin >= 0 ? sE.M : rigidM) + rigidOff; N = Vector3.TransformNormal(nvv, skin >= 0 ? sE.M : rigidM); wsum = 1;
                        inf.Clear(); inf[rigidA >= 0 ? Map(rigidA) : 0] = 1;
                    }
                    P /= wsum; N = N.LengthSquared() > 0 ? Vector3.Normalize(N) : Vector3.UnitY;
                    // influences: drop the negligible, keep at most 4 (the cast has at most 3), snap to the weight step
                    var l = inf.Where(kv => kv.Value / wsum >= sp.WeightStep / 2).OrderByDescending(kv => kv.Value).Select(kv => (j: kv.Key, w: kv.Value / wsum)).ToList();
                    if (l.Count == 0) l.Add((inf.OrderByDescending(kv => kv.Value).First().Key, 1f));
                    if (l.Count > 3) nMany++;
                    if (l.Count > 4) l = l.Take(4).ToList();
                    float tot = l.Sum(x => x.w);
                    var q = l.Select(x => (x.j, w: MathF.Round(x.w / tot / sp.WeightStep) * sp.WeightStep)).Where(x => x.w > 0).ToList();
                    if (q.Count == 0) q.Add((l[0].j, 1f));
                    float rest = q.Skip(1).Sum(x => x.w); q[0] = (q[0].j, 1f - rest);   // the largest takes the rounding
                    if (q[0].w <= 0) q = new() { (l[0].j, 1f) };
                    p.P.Add(P); p.N.Add(N); p.Inf.Add(q.ToArray());
                    for (int k = 0; k < 4; k++)
                    {
                        var uv = uvs[k] != null ? new Vector2(uvs[k][v][0], uvs[k][v][1]) : Vector2.Zero;
                        if (xf[k] is Matrix3x2 m) uv = Vector2.Transform(uv, m);
                        p.UV[k].Add(uv);
                    }
                }
                foreach (var (a, b, c) in tris)
                {
                    if (Vector3.Cross(p.P[b] - p.P[a], p.P[c] - p.P[a]).LengthSquared() < 1e-14f) { p.Degenerate++; continue; }
                    p.Tri.Add(a); p.Tri.Add(c); p.Tri.Add(b);     // glTF's counter-clockwise front faces -> GX's clockwise
                }
                if (p.Tri.Count > 0) prims.Add(p);
            }
        }
        if (nNoNormal > 0) log.Add($"{lod}: {nNoNormal} primitive(s) without normals: smooth normals computed");
        if (nMany > 0) log.Add($"{lod}: WARNING: {nMany} vertices with more than 3 influences (the cast has at most 3; kept the largest 4)");
        if (nRigid > 0) log.Add($"{lod}: {nRigid} skinned vertices with no weight: bound to the mesh's joint");
        return prims;
    }

    static double MaxAbs(Matrix4x4 m) => new[] { m.M11, m.M12, m.M13, m.M14, m.M21, m.M22, m.M23, m.M24, m.M31, m.M32, m.M33, m.M34, m.M41, m.M42, m.M43, m.M44 }.Max(x => Math.Abs((double)x));
    static double Angle(Matrix4x4 a, Matrix4x4 b)
    {   // the rotation between two frames' orientations, in degrees
        Matrix4x4.Decompose(a, out _, out var qa, out _); Matrix4x4.Decompose(b, out _, out var qb, out _);
        return 2 * Math.Acos(Math.Min(1, Math.Abs(Quaternion.Dot(Quaternion.Normalize(qa), Quaternion.Normalize(qb))))) * 180 / Math.PI;
    }

    static IEnumerable<JsonElement> TexRefs(JsonElement mat)
    {
        if (mat.TryGetProperty("pbrMetallicRoughness", out var pbr) && pbr.TryGetProperty("baseColorTexture", out var bt)) yield return bt;
        if (mat.TryGetProperty("extensions", out var ex) && ex.TryGetProperty("KHR_materials_specular", out var ks))
        {
            if (ks.TryGetProperty("specularColorTexture", out var sct)) yield return sct;
            else if (ks.TryGetProperty("specularTexture", out var st)) yield return st;
        }
    }

    // ---- textures ----------------------------------------------------------------------------------------------------
    class TexCache
    {
        public Dictionary<string, (HSD_Image img, HSD_Tlut tl)> Map = new();
        public Dictionary<(int, string), (int w, int h, byte[] rgba)> Decoded = new();
        public int Bytes; public List<string> Log = new();
    }

    static (int w, int h, byte[] rgba) GltfImage(Gltf g, int texIndex, TexCache tc)
    {
        int src = g.El("textures", texIndex).GetProperty("source").GetInt32();
        var key = (src, g.File_);
        if (!tc.Decoded.TryGetValue(key, out var im)) tc.Decoded[key] = im = PngRead.Decode(g.ImageBytes(src));
        return im;
    }

    static bool HasAlpha(byte[] rgba) { for (int i = 3; i < rgba.Length; i += 4) if (rgba[i] < 250) return true; return false; }

    // the cast's formats: CMP for colour, CI8 (RGB565 palette) for eyes, alpha through an RGB5A3 palette (or RGB5A3)
    static (GXTexFmt, GXTlutFmt) ChooseFormat(byte[] rgba, int w, int h, bool eye, bool alpha, string forced)
    {
        if (forced != null)
        {
            var f = Enum.Parse<GXTexFmt>(forced, true);
            return (f, alpha ? GXTlutFmt.RGB5A3 : GXTlutFmt.RGB565);
        }
        if (alpha && HasAlpha(rgba)) return (Colours(rgba, GXTlutFmt.RGB5A3) <= 256 ? GXTexFmt.CI8 : GXTexFmt.RGB5A3, GXTlutFmt.RGB5A3);
        if (eye) return (GXTexFmt.CI8, GXTlutFmt.RGB565);
        return (GXTexFmt.CMP, GXTlutFmt.RGB565);
    }

    static ushort Pal16(byte r, byte g, byte b, byte a, GXTlutFmt tf) => tf switch
    {
        GXTlutFmt.RGB5A3 => GXImageConverter.EncodeRGBA3(a, r, g, b),
        GXTlutFmt.RGB565 => (ushort)(((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)),
        _ => throw new Exception($"palette format {tf}")
    };
    static int Colours(byte[] rgba, GXTlutFmt tf) { var s = new HashSet<ushort>(); for (int i = 0; i < rgba.Length; i += 4) s.Add(Pal16(rgba[i], rgba[i + 1], rgba[i + 2], rgba[i + 3], tf)); return s.Count; }

    // a paletted image (tiles 8x4 for CI8, 8x8 for CI4, padded like the cast's 190x190 eyes): the palette is exactly the
    // image's colours when they fit (no dithering), else a quantized palette mapped to the nearest entry
    static (byte[] data, byte[] pal) Indexed(byte[] rgba, int w, int h, GXTexFmt fmt, GXTlutFmt tf)
    {
        int cap = fmt == GXTexFmt.CI4 ? 16 : 256, th = fmt == GXTexFmt.CI4 ? 8 : 4;
        var idx = new int[w * h]; var pal = new List<ushort>(); var at = new Dictionary<ushort, int>();
        for (int i = 0; i < w * h; i++)
        {
            var c = Pal16(rgba[i * 4], rgba[i * 4 + 1], rgba[i * 4 + 2], rgba[i * 4 + 3], tf);
            if (!at.TryGetValue(c, out var k)) { k = pal.Count; pal.Add(c); at[c] = k; }
            idx[i] = k;
        }
        if (pal.Count > cap)
        {
            var exq = new ExoQuantSharp.ExoQuant();
            if (tf == GXTlutFmt.RGB565) exq.NoTransparency();
            exq.Feed(rgba); exq.QuantizeEx(cap, true); exq.GetPalette(out var pp, cap); exq.MapImage(w * h, rgba, out var mapped);
            pal = Enumerable.Range(0, cap).Select(i => Pal16(pp[i * 4], pp[i * 4 + 1], pp[i * 4 + 2], pp[i * 4 + 3], tf)).ToList();
            for (int i = 0; i < w * h; i++) idx[i] = mapped[i];
        }
        int pw = (w + 7) / 8 * 8, ph = (h + th - 1) / th * th;
        var data = new List<byte>();
        for (int ty = 0; ty < ph; ty += th)
            for (int tx = 0; tx < pw; tx += 8)
                for (int y = ty; y < ty + th; y++)
                    for (int x = tx; x < tx + 8; x += fmt == GXTexFmt.CI4 ? 2 : 1)
                    {
                        int I(int xx) => xx < w && y < h ? idx[y * w + xx] : 0;
                        data.Add(fmt == GXTexFmt.CI4 ? (byte)((I(x) << 4) | I(x + 1)) : (byte)I(x));
                    }
        var tl = new byte[cap * 2];
        for (int i = 0; i < pal.Count; i++) { tl[i * 2] = (byte)(pal[i] >> 8); tl[i * 2 + 1] = (byte)pal[i]; }
        return (data.ToArray(), tl);
    }

    static byte[] Swap(byte[] a) { var b = (byte[])a.Clone(); for (int i = 0; i < b.Length; i += 4) (b[i], b[i + 2]) = (b[i + 2], b[i]); return b; }   // RGBA <-> BGRA

    static (HSD_Image img, HSD_Tlut tl) Encode(byte[] rgba, int w, int h, GXTexFmt fmt, GXTlutFmt tf, TexCache tc, string name)
    {
        var key = Convert.ToHexString(System.Security.Cryptography.SHA1.HashData(rgba)) + $"/{w}x{h}/{fmt}/{tf}";
        if (tc.Map.TryGetValue(key, out var hit)) return hit;
        if (w > 1024 || h > 1024) throw new Exception($"{name}: {w}x{h} is over GX's 1024 limit");
        byte[] data, pal = null;
        if (fmt == GXTexFmt.CI8 || fmt == GXTexFmt.CI4) (data, pal) = Indexed(rgba, w, h, fmt, tf);
        else data = GXImageConverter.EncodeImage(Swap(rgba), w, h, fmt, tf, out _);   // HSDRaw's encoders take BGRA
        var img = new HSD_Image { ImageData = data, Width = (short)w, Height = (short)h, Format = fmt };
        HSD_Tlut tl = pal == null ? null : new HSD_Tlut { TlutData = pal, Format = tf, ColorCount = (short)(pal.Length / 2) };
        var back = pal != null ? GXImageConverter.DecodeTPL(fmt, w, h, data, tf, pal.Length / 2, pal) : GXImageConverter.DecodeTPL(fmt, w, h, data);
        int err = TexKit.MaxError(Swap(rgba), back);
        tc.Bytes += data.Length + (pal?.Length ?? 0);
        tc.Log.Add($"  {name}: {w}x{h} {fmt}{(tl != null ? "/" + tf : "")} {data.Length + (pal?.Length ?? 0)} bytes, max channel error {err}" +
                   ((w & (w - 1)) != 0 || (h & (h - 1)) != 0 ? " (not a power of two)" : "") + (w > 256 || h > 256 ? " (over the cast's 256)" : ""));
        return tc.Map[key] = (img, tl);
    }

    // ---- materials ---------------------------------------------------------------------------------------------------
    class MatOut { public HSD_MOBJ M; public bool Cull, UV0, UV1; public int Tex0Set, Tex1Set; public HSD_TexAnim EyeAnim; public int EyeSlot = -1; }

    static bool Sheen(JsonElement mat)
    {
        if (Melee(mat) is JsonElement x && x.TryGetProperty("specular", out var s)) return s.ValueKind == JsonValueKind.True;
        if (mat.TryGetProperty("extensions", out var ex))
        {
            if (ex.TryGetProperty("KHR_materials_sheen", out _) || ex.TryGetProperty("KHR_materials_clearcoat", out _)) return true;
            if (ex.TryGetProperty("KHR_materials_specular", out var ks))
            {
                float f = ks.TryGetProperty("specularFactor", out var sf) ? (float)sf.GetDouble() : 1;
                var col = ks.TryGetProperty("specularColorFactor", out var cf) ? cf.EnumerateArray().Select(e => (float)e.GetDouble()).ToArray() : new float[] { 1, 1, 1 };
                if (f > 0 && col.Any(c => c > 0) && f * col.Max() > 0.5f) return true;
            }
        }
        if (mat.TryGetProperty("pbrMetallicRoughness", out var pbr))
        {
            float metal = pbr.TryGetProperty("metallicFactor", out var mf) ? (float)mf.GetDouble() : 1;
            float rough = pbr.TryGetProperty("roughnessFactor", out var rf) ? (float)rf.GetDouble() : 1;
            if (metal >= 0.5f || rough <= 0.35f) return true;
        }
        return false;
    }

    static GXWrapMode Wrap(Gltf g, JsonElement texInfo, bool inUnit, string st)
    {
        if (inUnit) return GXWrapMode.CLAMP;                 // the cast clamps 0-1 UVs (89% of layers)
        var tex = g.El("textures", texInfo.GetProperty("index").GetInt32());
        int mode = 10497;
        if (tex.TryGetProperty("sampler", out var si)) { var s = g.El("samplers", si.GetInt32()); if (s.TryGetProperty(st, out var m)) mode = m.GetInt32(); }
        return mode == 33648 ? GXWrapMode.MIRROR : mode == 33071 ? GXWrapMode.CLAMP : GXWrapMode.REPEAT;
    }

    static MatOut Material(Gltf g, Prim p, Templates tpl, TexCache tc, Spec sp, List<string> log, bool allowEyes)
    {
        var o = new MatOut { Cull = true };
        var mat = p.HasMat ? p.MatJ : default;
        var mx = p.HasMat ? Melee(mat) : null;
        if (p.HasMat && mat.TryGetProperty("doubleSided", out var ds) && ds.GetBoolean()) o.Cull = false;
        var baseCol = new float[] { 1, 1, 1, 1 };
        JsonElement pbr = default, bt = default; bool hasTex = false;
        if (p.HasMat && mat.TryGetProperty("pbrMetallicRoughness", out pbr))
        {
            if (pbr.TryGetProperty("baseColorFactor", out var bf)) baseCol = bf.EnumerateArray().Select(e => (float)e.GetDouble()).ToArray();
            hasTex = pbr.TryGetProperty("baseColorTexture", out bt);
        }
        string alphaMode = p.HasMat && mat.TryGetProperty("alphaMode", out var am) ? am.GetString() : "OPAQUE";
        bool alpha = alphaMode != "OPAQUE";
        bool sheen = p.HasMat && Sheen(mat);
        string forced = mx is JsonElement x0 && x0.TryGetProperty("format", out var fe) ? fe.GetString() : null;
        // eyes: rig.json model.eyes names the material, or the material's extras carry {"melee": {"eye": slot, "frames": [...]}}
        List<string> frames = null;
        if (allowEyes && sp.Eyes.TryGetValue(p.MatName, out var eyeSpec)) { o.EyeSlot = eyeSpec.slot; frames = eyeSpec.frames; }
        else if (allowEyes && mx is JsonElement x1 && x1.TryGetProperty("eye", out var es))
        {
            o.EyeSlot = es.GetInt32();
            frames = x1.TryGetProperty("frames", out var fr) ? fr.EnumerateArray().Select(f => Path.GetFullPath(Path.Combine(g.Dir, f.GetString()))).ToList() : new();
        }
        bool eye = o.EyeSlot >= 0 || Regex.IsMatch(p.MatName, "eye(?!brow|lash|lid)", RegexOptions.IgnoreCase);

        HSD_MOBJ m;
        bool UVIn(int set) => p.Tri.All(i => p.UV[set][i].X >= -1e-3f && p.UV[set][i].X <= 1.001f && p.UV[set][i].Y >= -1e-3f && p.UV[set][i].Y <= 1.001f);
        if (hasTex || (frames != null && frames.Count > 0))
        {
            m = HSDAccessor.DeepClone<HSD_MOBJ>(tpl.Base);
            int set = hasTex && bt.TryGetProperty("texCoord", out var tce) ? tce.GetInt32() : 0;
            if ((p.UVMask & (1 << set)) == 0) throw new Exception($"{p.Name}: material {p.MatName} textures TEXCOORD_{set}, which the primitive lacks");
            o.UV0 = true; o.Tex0Set = set;
            (int w, int h, byte[] rgba) im;
            string nm;
            if (hasTex) { im = GltfImage(g, bt.GetProperty("index").GetInt32(), tc); nm = g.ImageName(g.El("textures", bt.GetProperty("index").GetInt32()).GetProperty("source").GetInt32()); }
            else { im = PngRead.Decode(File.ReadAllBytes(frames[0])); nm = Path.GetFileNameWithoutExtension(frames[0]); }
            var rgba = im.rgba;
            if (baseCol.Take(3).Any(c => MathF.Abs(c - 1) > 1e-3f))
            {   // REPLACE drops the material colour, so a tinted texture carries its tint (the alpha factor is the MObj's)
                rgba = (byte[])rgba.Clone();
                for (int i = 0; i < rgba.Length; i += 4) for (int c = 0; c < 3; c++) rgba[i + c] = (byte)Math.Clamp(MathF.Round(rgba[i + c] * baseCol[c]), 0, 255);
            }
            var (fmt, tf) = ChooseFormat(rgba, im.w, im.h, eye, alpha, forced);
            var (img, tl) = Encode(rgba, im.w, im.h, fmt, tf, tc, nm);
            var t = HSDAccessor.DeepClone<HSD_TOBJ>(fmt == GXTexFmt.CI8 && o.EyeSlot >= 0 ? tpl.EyeTex : tpl.BaseTex);
            t.Next = null; t.ImageData = img; t.TlutData = tl;
            bool unit = UVIn(set);
            t.WrapS = hasTex ? Wrap(g, bt, unit, "wrapS") : GXWrapMode.CLAMP; t.WrapT = hasTex ? Wrap(g, bt, unit, "wrapT") : GXWrapMode.CLAMP;
            t.RepeatS = 1; t.RepeatT = 1;
            if (alpha && HasAlpha(rgba)) t.AlphaOperation = ALPHAMAP.REPLACE;
            m.Textures = t;
            // the specular map: a second, specular-lightmap layer on TEX1 (Mario's lacquered parts)
            JsonElement? spec = null;
            if (p.HasMat) foreach (var r in TexRefs(mat).Skip(1)) spec = r;
            if (spec is JsonElement sj)
            {
                int s1 = sj.TryGetProperty("texCoord", out var s1e) ? s1e.GetInt32() : 0;
                var si = GltfImage(g, sj.GetProperty("index").GetInt32(), tc);
                var (simg, stl) = Encode(si.rgba, si.w, si.h, GXTexFmt.CMP, GXTlutFmt.RGB565, tc, g.ImageName(g.El("textures", sj.GetProperty("index").GetInt32()).GetProperty("source").GetInt32()));
                var t1 = HSDAccessor.DeepClone<HSD_TOBJ>(tpl.SpecTex); t1.Next = null; t1.ImageData = simg; t1.TlutData = stl;
                t1.WrapS = Wrap(g, sj, UVIn(s1), "wrapS"); t1.WrapT = Wrap(g, sj, UVIn(s1), "wrapT");
                t.Next = t1; o.UV1 = true; o.Tex1Set = s1; sheen = true;
                m.RenderFlags |= RENDER_MODE.TEX1;
            }
            // the eye's frames: a texture animation swapping image and palette, keyed frame k -> image k (Mario's)
            if (o.EyeSlot >= 0)
            {
                if (fmt != GXTexFmt.CI8) log.Add($"eye {p.MatName}: {fmt}, not CI8 (the cast's eyes are CI8)");
                var imgs = new List<HSD_Image>(); var tls = new List<HSD_Tlut>();
                if (frames.Count == 0) frames = null;
                foreach (var fpath in frames ?? new List<string>())
                {
                    var fi = PngRead.Decode(File.ReadAllBytes(fpath));
                    if (fi.w != im.w || fi.h != im.h) throw new Exception($"eye frame {fpath}: {fi.w}x{fi.h}, the eye texture is {im.w}x{im.h}");
                    var (fimg, ftl) = Encode(fi.rgba, fi.w, fi.h, fmt, tf, tc, Path.GetFileNameWithoutExtension(fpath));
                    imgs.Add(fimg); tls.Add(ftl);
                }
                if (imgs.Count == 0) { imgs.Add(img); tls.Add(tl); }
                else { t.ImageData = imgs[0]; t.TlutData = tls[0]; }
                if (tpl.EyeAnim == null) throw new Exception("the template has no eye texture animation to copy");
                var ta = HSDAccessor.DeepClone<HSD_TexAnim>(tpl.EyeAnim); ta.Next = null;
                ta.GXTexMapID = t.TexMapID;
                ta.ImageBuffers = new HSDArrayAccessor<HSD_TexBuffer> { Array = imgs.Select(i => new HSD_TexBuffer { Data = i }).ToArray() };
                ta.TlutBuffers = tls[0] == null ? null : new HSDArrayAccessor<HSD_TlutBuffer> { Array = tls.Select(i => new HSD_TlutBuffer { Data = i }).ToArray() };
                float end = Math.Max(ta.AnimationObject.EndFrame, imgs.Count);
                for (var fd = ta.AnimationObject.FObjDesc; fd != null; fd = fd.Next)
                {
                    var tt = (TexTrackType)fd.TrackType;
                    if (tt != TexTrackType.HSD_A_T_TIMG && tt != TexTrackType.HSD_A_T_TCLT) continue;
                    var keys = Enumerable.Range(0, imgs.Count).Select(k => new FOBJKey { Frame = k, Value = k, InterpolationType = GXInterpolationType.HSD_A_OP_CON }).ToList();
                    keys.Add(new FOBJKey { Frame = end, Value = imgs.Count - 1, InterpolationType = GXInterpolationType.HSD_A_OP_CON });
                    fd.SetKeys(keys, fd.TrackType);
                }
                ta.AnimationObject.EndFrame = end;
                if (tls[0] == null)
                {   // an unpaletted eye: drop the palette track
                    HSD_FOBJDesc prev = null;
                    for (var fd = ta.AnimationObject.FObjDesc; fd != null; fd = fd.Next)
                        if ((TexTrackType)fd.TrackType == TexTrackType.HSD_A_T_TCLT) { if (prev == null) ta.AnimationObject.FObjDesc = fd.Next; else prev.Next = fd.Next; }
                        else prev = fd;
                }
                o.EyeAnim = ta;
            }
        }
        else
        {   // untextured: the colour lives in the material (diffuse, ambient at half, as the blocks were)
            m = HSDAccessor.DeepClone<HSD_MOBJ>(tpl.Plain);
            m.Textures = null;
            var mt = m.Material;
            byte B(float v) => (byte)Math.Clamp(MathF.Round(v * 255), 0, 255);
            mt.DIF_R = B(baseCol[0]); mt.DIF_G = B(baseCol[1]); mt.DIF_B = B(baseCol[2]); mt.DIF_A = 255;
            mt.AMB_R = (byte)(mt.DIF_R / 2); mt.AMB_G = (byte)(mt.DIF_G / 2); mt.AMB_B = (byte)(mt.DIF_B / 2); mt.AMB_A = 255;
            m.RenderFlags = RENDER_MODE.DIFFUSE;
        }
        // sheen: the cast's Phong highlight at shininess 50, white unless the material names its colour: extras
        // {"melee": {"specular_color": [r, g, b]}} (0-255; Mario's shoes are (102,102,102)), else KHR_materials_specular's
        // specularColorFactor x specularFactor (0-1)
        if (sheen)
        {
            m.RenderFlags |= RENDER_MODE.SPECULAR; var mt = m.Material; mt.SPC_A = 255; mt.Shininess = 50;
            byte[] spc = { 255, 255, 255 };
            if (mx is JsonElement xs && xs.TryGetProperty("specular_color", out var sc))
                spc = sc.EnumerateArray().Take(3).Select(v => (byte)Math.Clamp(Math.Round(v.GetDouble()), 0, 255)).ToArray();
            else if (p.HasMat && mat.TryGetProperty("extensions", out var sx) && sx.TryGetProperty("KHR_materials_specular", out var ks) && ks.TryGetProperty("specularColorFactor", out var cf))
            {
                double f = ks.TryGetProperty("specularFactor", out var sf) ? sf.GetDouble() : 1;
                spc = cf.EnumerateArray().Take(3).Select(v => (byte)Math.Clamp(Math.Round(v.GetDouble() * f * 255), 0, 255)).ToArray();
            }
            mt.SPC_R = spc[0]; mt.SPC_G = spc[1]; mt.SPC_B = spc[2];
            if (spc[0] != 255 || spc[1] != 255 || spc[2] != 255) log.Add($"  {p.MatName}: specular colour {spc[0]},{spc[1]},{spc[2]}");
        }
        else m.RenderFlags &= ~RENDER_MODE.SPECULAR;
        if (alpha)
        {
            m.Material.Alpha = baseCol[3];
            m.RenderFlags |= RENDER_MODE.XLU;
            if (alphaMode == "BLEND") m.RenderFlags |= RENDER_MODE.NO_ZUPDATE;
        }
        o.M = m;
        return o;
    }

    // ---- polygons ----------------------------------------------------------------------------------------------------
    // One DObj's PObjs through HSDRaw's generator (strips, split at 10 envelopes). Values are pre-snapped to the grids the
    // cast uses, so the compressor picks their formats instead of floats: positions s16 with as many fraction bits as
    // the DObj's extent allows (10-11 on a fighter), normals s8 with 6, UVs s16 with 13.
    // rigid: no matrix index or envelopes; every vertex is stored in the frame of its (single) joint and drawn with that
    // joint's matrix, as the Kirby copy hats are (HatBuild.cs)
    static HSD_POBJ Polygons(IEnumerable<(Prim p, int[] tris)> src, Skel sk, bool cull, bool uv0, bool uv1, int set0, int set1, bool metal, POBJ_FLAG bits, out int nTris, bool rigid = false)
    {
        var attrs = rigid ? new List<GXAttribName>() : new List<GXAttribName> { GXAttribName.GX_VA_PNMTXIDX };
        if (metal) { attrs.Add(GXAttribName.GX_VA_TEX0MTXIDX); attrs.Add(GXAttribName.GX_VA_TEX1MTXIDX); }
        attrs.Add(GXAttribName.GX_VA_POS); attrs.Add(GXAttribName.GX_VA_NRM);
        if (uv0) attrs.Add(GXAttribName.GX_VA_TEX0);
        if (uv1) attrs.Add(GXAttribName.GX_VA_TEX1);
        var inv = sk.W.Select(w => { Matrix4x4.Invert(w, out var iw); return iw; }).ToList();
        var P = new List<Vector3>(); var N = new List<Vector3>(); var U0 = new List<Vector2>(); var U1 = new List<Vector2>();
        var bones = new List<HSD_JOBJ[]>(); var weights = new List<float[]>();
        foreach (var (p, tris) in src)
            foreach (var v in tris)
            {
                var inf = p.Inf[v];
                if (inf.Length == 1)
                {   // single-weight: stored in its joint's frame
                    var iw = inv[inf[0].j];
                    P.Add(Vector3.Transform(p.P[v], iw)); N.Add(Vector3.Normalize(Vector3.TransformNormal(p.N[v], iw)));
                }
                else { P.Add(p.P[v]); N.Add(p.N[v]); }      // multi-weight: bind (model) space
                U0.Add(p.UV[set0][v]); U1.Add(p.UV[set1][v]);
                bones.Add(inf.Select(x => sk.J[x.j]).ToArray()); weights.Add(inf.Select(x => x.w).ToArray());
            }
        nTris = P.Count / 3;
        float maxAbs = P.Count == 0 ? 1 : P.Max(q => MathF.Max(MathF.Abs(q.X), MathF.Max(MathF.Abs(q.Y), MathF.Abs(q.Z))));
        int sh = 15; while (sh > 0 && maxAbs * (1 << sh) > 32767) sh--;
        float Snap(float x, int s) => MathF.Round(x * (1 << s)) / (1 << s);
        var verts = new List<GX_Vertex>();
        for (int i = 0; i < P.Count; i++)
        {
            var n = N[i]; if (float.IsNaN(n.X)) n = Vector3.UnitY;
            verts.Add(new GX_Vertex
            {
                POS = new GXVector3(Snap(P[i].X, sh), Snap(P[i].Y, sh), Snap(P[i].Z, sh)),
                NRM = new GXVector3(Snap(n.X, 6), Snap(n.Y, 6), Snap(n.Z, 6)),
                TEX0 = new GXVector2(Snap(U0[i].X, 13), Snap(U0[i].Y, 13)),
                TEX1 = new GXVector2(Snap(U1[i].X, 13), Snap(U1[i].Y, 13)),
            });
        }
        var gen = new POBJ_Generator { CullMode = cull ? GenCullMode.Front : GenCullMode.None };
        var input = verts.ToList();
        if (rigid && bones.Any(b => b.Length != 1 || b[0] != bones[0][0])) throw new Exception("a rigid mesh must ride one joint");
        var po = gen.CreatePOBJsFromTriangleList(verts, attrs.ToArray(), rigid ? null : bones, rigid ? null : weights);
        gen.SaveChanges();
        for (var q = po; q != null; q = q.Next) q.Flags |= bits;
        // HSDRaw dedupes vertex values by a 32-bit structural hash: a collision would silently snap one value to another.
        // Every input value must come back out of the buffers, and nothing else.
        var want = new HashSet<(float, float, float, float, float, float, float, float)>(); var got = new HashSet<(float, float, float, float, float, float, float, float)>();
        foreach (var v in input) want.Add((v.POS.X, v.POS.Y, v.POS.Z, v.NRM.X, v.NRM.Y, v.NRM.Z, uv0 ? v.TEX0.X : 0, uv0 ? v.TEX0.Y : 0));
        for (var q = po; q != null; q = q.Next)
            foreach (var v in q.ToDisplayList().Vertices) got.Add((v.POS.X, v.POS.Y, v.POS.Z, v.NRM.X, v.NRM.Y, v.NRM.Z, uv0 ? v.TEX0.X : 0, uv0 ? v.TEX0.Y : 0));
        if (!want.SetEquals(got)) throw new Exception($"vertex buffers differ from their input ({want.Except(got).Count()} values lost): a hash collision in HSDRaw's POBJ_Generator");
        return po;
    }

    // ---- the import ----------------------------------------------------------------------------------------------------
    // The costume's meshes from the glTF(s) onto the rig's skeleton (sk, already built: joints with inverse binds), the
    // metal model's onto a second copy of it (metalSk, or null for none). Returns the DObjs (hung on sk's root), the
    // visibility groups, the material animation tree and the eye slots' TObj indices.
    public static Result Import(Spec sp, Skel sk, Skel metalSk, string templateNr, string templateFt)
    {
        var res = new Result(); var tc = new TexCache();
        var tpl = Templates.Load(templateNr, templateFt);
        res.Log.Add($"template: {Path.GetFileName(templateNr)} (PObj bits 0x{(int)tpl.PobjBits:X}, eye texanim {(tpl.EyeAnim != null ? "yes" : "no")}, metal material {(tpl.Metal != null ? "yes" : "no")})");
        var eyes = new List<(int slot, HSD_DOBJ d)>(); var eyeAnims = new Dictionary<HSD_DOBJ, HSD_TexAnim>();
        List<Prim> highPrims = null;
        foreach (var (lod, path) in new[] { ("high", sp.High), ("low", sp.Low) })
        {
            if (path == null) continue;
            var g = Gltf.Load(path);
            var prims = ReadPrims(g, sk, sp, res.Log, lod);
            if (lod == "high") highPrims = prims;
            var groups = lod == "high" ? res.High : res.Low;
            int tris = 0, pobjs = 0;
            foreach (var p in prims)
            {
                var mo = Material(g, p, tpl, tc, sp, res.Log, lod == "high");
                var d = new HSD_DOBJ { Mobj = mo.M };
                d.Pobj = Polygons(new[] { (p, p.Tri.ToArray()) }, sk, mo.Cull, mo.UV0, mo.UV1, mo.Tex0Set, mo.Tex1Set, false, tpl.PobjBits, out int nt);
                tris += nt; pobjs += d.Pobj.List.Count;
                int di = res.Dobjs.Count; res.Dobjs.Add(d);
                while (groups.Count <= p.Group) groups.Add(new());
                while (groups[p.Group].Count <= p.Option) groups[p.Group].Add(new());
                groups[p.Group][p.Option].Add(di);
                if (mo.EyeAnim != null) { eyes.Add((mo.EyeSlot, d)); eyeAnims[d] = mo.EyeAnim; }
                var inf = p.Inf.Select(x => x.Length).GroupBy(x => x).OrderBy(x => x.Key).Select(x => $"{x.Key}:{x.Count()}");
                res.Log.Add($"  d{di,-3} {lod} {p.Name,-28} {p.MatName,-20} {nt,5} tris {d.Pobj.List.Count} pobj  render {(uint)mo.M.RenderFlags:X2}{(mo.Cull ? "" : " 2-sided")}{(mo.EyeSlot >= 0 ? $" eye{mo.EyeSlot}" : "")}  influences {string.Join(" ", inf)}" + (p.Degenerate > 0 ? $"  ({p.Degenerate} degenerate dropped)" : "") + (p.Group != 0 || p.Option != 0 ? $"  group {p.Group} option {p.Option}" : ""));
            }
            if (lod == "high") { res.HighTris = tris; res.HighPobjs = pobjs; } else { res.LowTris = tris; res.LowPobjs = pobjs; }
            res.Log.Add($"{lod}: {prims.Count} DObjs, {tris} triangles, {pobjs} PObjs");
        }
        if (sp.Low == null) res.Low = res.High.Select(gr => gr.Select(o => o.ToList()).ToList()).ToList();   // no low model: the magnifier draws the high one
        // the engine reads every visibility table (high, low, metal) for every group (ftParts_80074B6C loops model_num):
        // a low model without the high one's variants gets empty groups (Link's metal table has them too)
        while (res.Low.Count < res.High.Count) res.Low.Add(new());
        if (res.Dobjs.Count > 124) throw new Exception($"{res.Dobjs.Count} DObjs: the engine holds 124 per fighter (ftparts.c)");
        if (res.High.Count > 11) throw new Exception($"{res.High.Count} visibility groups: the engine holds 11");
        for (int i = 0; i < res.Dobjs.Count; i++) res.Dobjs[i].Next = i + 1 < res.Dobjs.Count ? res.Dobjs[i + 1] : null;
        sk.J[0].Dobj = res.Dobjs.Count > 0 ? res.Dobjs[0] : null;
        RootFlags(sk.J[0]);

        // eyes: the material animation (one MatAnim per root DObj up to the last eye) and the material lookup, whose
        // entries count TObjs across the DObj list in order (ftParts_80075240)
        res.MatAnim = FighterBuild.MatAnimTree(sk.J[0]);
        if (eyes.Count > 0)
        {
            int last = eyes.Max(e => res.Dobjs.IndexOf(e.d));
            HSD_MatAnim first = null, prev = null;
            for (int i = 0; i <= last; i++)
            {
                var ma = new HSD_MatAnim();
                if (eyeAnims.TryGetValue(res.Dobjs[i], out var ta)) ma.TextureAnimation = ta;
                if (first == null) first = ma; else prev.Next = ma;
                prev = ma;
            }
            res.MatAnim.MaterialAnimation = first;
            var tobjBase = new List<int>(); int acc = 0;
            foreach (var d in res.Dobjs) { tobjBase.Add(acc); acc += d.Mobj?.Textures?.List.Count ?? 0; }
            // slots in declared order; one eye material on several DObjs (one mirrored set for both eyes) takes the next ones
            var slots = eyes.Select((e, i) => (e.slot, e.d, i)).OrderBy(e => e.slot).ThenBy(e => e.i).Select(e => (e.slot, e.d)).ToList();
            if (slots.Select(e => e.slot).Distinct().Count() != slots.Count) { res.Log.Add("eyes: a material on several DObjs: slots " + string.Join(",", slots.Select(e => e.slot)) + " -> 0.." + (slots.Count - 1)); slots = slots.Select((e, i) => (i, e.d)).ToList(); }
            if (slots.Select((e, i) => e.slot != i).Any(x => x)) throw new Exception("eye slots must run 0, 1, ...: " + string.Join(",", slots.Select(e => e.slot)));
            res.EyeTobjs = slots.Select(e => tobjBase[res.Dobjs.IndexOf(e.d)]).ToList();
            res.Log.Add($"eyes: {slots.Count} slot(s), TObj indices {string.Join(",", res.EyeTobjs)}, {eyeAnims.Values.First().ImageCount} frames");
        }

        // the metal model: the high model once more on the metal skeleton, merged into one DObj per cull mode (the engine
        // appends these to the main joints and holds 32), with the template's metal material (reflection-mapped). Always
        // built: in the metal state the engine hides the costume and draws only this.
        if (metalSk != null && highPrims != null)
        {
            if (tpl.Metal == null) res.Log.Add("metal: the template has no metal model; a plain grey material stands in");
            // one metal model per body option (group 0): option 0 is the default model (every group's option 0), a later
            // option a whole-body alternate (Geno Flash's cannon, as Samus's Morph Ball) shown in its place, so a metal
            // fighter keeps its shape when a script swaps the body. Hand variants (weapon forms, spare copies) are left out
            var bodyOptions = highPrims.Where(p => p.Group == 0).Select(p => p.Option).Distinct().OrderBy(o => o).ToList();
            foreach (var opt in bodyOptions)
            {
                var ids = new List<int>();
                foreach (var cull in new[] { true, false })
                {
                    var part = new List<(Prim, int[])>();
                    foreach (var p in highPrims)
                    {
                        if (opt == 0 ? p.Option != 0 : (p.Group != 0 || p.Option != opt)) continue;
                        bool c = !(p.HasMat && p.MatJ.TryGetProperty("doubleSided", out var ds) && ds.GetBoolean());
                        if (c == cull) part.Add((p, p.Tri.ToArray()));
                    }
                    if (part.Count == 0) continue;
                    var d = new HSD_DOBJ { Mobj = HSDAccessor.DeepClone<HSD_MOBJ>(tpl.Metal ?? tpl.Plain) };
                    d.Pobj = Polygons(part, metalSk, cull, false, false, 0, 0, true, tpl.PobjBits, out _);
                    ids.Add(res.Metal.Count); res.Metal.Add(d);
                }
                while (res.MetalBody.Count < opt) res.MetalBody.Add(new());
                res.MetalBody.Add(ids);
            }
            for (int i = 0; i < res.Metal.Count; i++) res.Metal[i].Next = i + 1 < res.Metal.Count ? res.Metal[i + 1] : null;
            metalSk.J[0].Dobj = res.Metal.FirstOrDefault();
            RootFlags(metalSk.J[0]);
            res.Log.Add($"metal: {res.Metal.Count} DObjs, {res.Metal.Sum(d => d.Pobj.List.Count)} PObjs, body options {JsonSerializer.Serialize(res.MetalBody)}");
        }
        res.TexBytes = tc.Bytes; res.Textures = tc.Map.Count;
        res.Log.Add($"textures: {tc.Map.Count} images, {tc.Bytes / 1024.0:0.0} KiB");
        res.Log.AddRange(tc.Log);
        return res;
    }

    // HSDRaw's flags, plus what the cast's root joint carries besides (Mario's 0x1005018E): texgen and root-opaque
    static void RootFlags(HSD_JOBJ root)
    {
        root.UpdateFlags();
        bool tex = false, opa = false;
        for (var d = root.Dobj; d != null; d = d.Next) { tex |= d.Mobj?.Textures != null; opa |= !d.Mobj.RenderFlags.HasFlag(RENDER_MODE.XLU); }
        if (tex) root.Flags |= JOBJ_FLAG.TEXGEN;
        if (opa) root.Flags |= JOBJ_FLAG.ROOT_OPA;
    }


    // ---- costumes: rig.json model "costumes": [{"code": "Re", "dir": DIR}, ...], each DIR a copy of the model's folder
    // (its glTFs and eye frames linked, some textures recoloured: projects/geno/model/costumes.py). Each is imported
    // exactly as costume 0 was and saved as OUTDIR/Pl{CODE}{Re}.dat under the vanilla symbols (PlyMario5KYe_Share_joint),
    // and must come out with the same DObjs, visibility groups and eye slots: the fighter data's tables index them for
    // every costume. Returns how many were written. Costume files an earlier build left in OUTDIR are removed first (a
    // blocky-rig build has one costume, and its fighter data one costume row: installing a stale PlGeRe.dat beside it
    // would let the game offer a costume whose tables aren't there).
    public static int Costumes(JsonElement rig, JsonElement modelSpec, string baseDir, Result first, string outDir, string code,
                               string model, string templateNr, string templateFt)
    {
        foreach (var old in Directory.GetFiles(outDir, $"Pl{code}??.dat"))
        {
            var cc = Path.GetFileNameWithoutExtension(old)[^2..];
            if (cc != "Nr" && cc != "AJ" && char.IsUpper(cc[0]) && char.IsLower(cc[1])) File.Delete(old);
        }
        if (first == null || modelSpec.ValueKind != JsonValueKind.Object || !modelSpec.TryGetProperty("costumes", out var cj) || cj.ValueKind != JsonValueKind.Array) return 0;
        if (modelSpec.TryGetProperty("template", out var te)) templateNr = te.GetString();
        var names = rig.GetProperty("joints").EnumerateArray().Select(j => j.GetProperty("name").GetString()).ToList();
        var sig = Signature(first);
        int n = 0;
        foreach (var c in cj.EnumerateArray())
        {
            string cc = c.GetProperty("code").GetString(), dir = Path.GetFullPath(c.GetProperty("dir").GetString());
            var sp = Spec.From(rig, modelSpec, baseDir);
            string src = Path.GetDirectoryName(sp.High);
            string Move(string p) => p == null ? null : Path.Combine(dir, Path.GetRelativePath(src, p));
            sp.High = Move(sp.High); sp.Low = Move(sp.Low);
            sp.Eyes = sp.Eyes.ToDictionary(kv => kv.Key, kv => (kv.Value.slot, kv.Value.frames.Select(Move).ToList()));
            var (J, W) = FighterBuild.BuildSkeleton(rig);
            var res = Import(sp, new Skel { J = J, W = W, Names = names }, null, templateNr, templateFt);
            var s2 = Signature(res);
            if (s2 != sig) throw new Exception($"costume {cc}: its model differs from costume 0's ({s2} against {sig}); a costume may change textures only");
            var f = new HSDRawFile();
            f.Roots.Add(new HSDRootNode { Name = model.Replace("5K_Share", $"5K{cc}_Share") + "_joint", Data = J[0] });
            f.Roots.Add(new HSDRootNode { Name = model.Replace("5K_Share", $"5K{cc}_Share") + "_matanim_joint", Data = res.MatAnim });
            FighterBuild.AlignModel(J[0], res.MatAnim);
            f.Save(Path.Combine(outDir, $"Pl{code}{cc}.dat"));
            Console.WriteLine($"costume {cc}: {res.Dobjs.Count} DObjs, {res.Textures} textures ({res.TexBytes / 1024.0:0.0} KiB) -> Pl{code}{cc}.dat");
            n++;
        }
        return n;
    }

    // what the fighter data's tables depend on: DObj count, the visibility groups and the eye slots' TObj indices
    static string Signature(Result r) =>
        $"{r.Dobjs.Count} dobjs {JsonSerializer.Serialize(r.High)} {JsonSerializer.Serialize(r.Low)} eyes {JsonSerializer.Serialize(r.EyeTobjs)}";

    // the fighter data's visibility tables (high, low, metal) and material lookups (the eye slots), one row per costume:
    // the engine indexes both by costume id (ftParts_8007487C, ftAnim_80070200), and every costume has the same meshes
    public static void Lookups(SBM_PlayerModelLookupTables ml, Result r, int costumes = 1)
    {
        HSDArrayAccessor<SBM_LookupTable> T(List<List<List<int>>> groups) => new HSDArrayAccessor<SBM_LookupTable>
        {
            Array = groups.Select(gr => new SBM_LookupTable { LookupEntries = new HSDArrayAccessor<SBM_LookupEntry> { Array = gr.Select(o => new SBM_LookupEntry { Entries = o.Select(i => (byte)i).ToArray() }).ToArray() } }).ToArray()
        };
        // the metal table: group 0's options are the metal models per body option (the default, and any whole-body
        // alternate); the hand groups are empty, as the metal model is the default hands
        var metal = new List<List<List<int>>> { r.MetalBody.Count > 0 ? r.MetalBody : new() { Enumerable.Range(0, r.Metal.Count).ToList() } };
        while (metal.Count < r.High.Count) metal.Add(new());      // one row per group, as every table needs
        var high = T(r.High); var low = T(r.Low); var met = r.Metal.Count > 0 ? T(metal) : null;
        ml.CostumeVisibilityLookups = new HSDArrayAccessor<SBM_CostumeLookupTable>
        { Array = Enumerable.Range(0, costumes).Select(_ => { var v = new SBM_CostumeLookupTable { HighPoly = high, LowPoly = low }; if (met != null) v.MetalPoly = met; return v; }).ToArray() };
        ml._s.SetInt32(0x00, r.High.Count);
        if (r.EyeTobjs.Count > 0)
        {
            var ents = new HSDUShortArray(); ents.Array = r.EyeTobjs.Select(i => (ushort)i).ToArray();
            ml._s.SetInt32(0x08, r.EyeTobjs.Count);
            ml.CostumeMaterialLookups = new HSDArrayAccessor<SBM_CostumeMaterialLookup>
            { Array = Enumerable.Range(0, costumes).Select(_ => new SBM_CostumeMaterialLookup { Entries = ents }).ToArray() };
        }
        else { ml._s.SetInt32(0x08, 0); ml._s.SetReference(0x0C, null); }
    }

    // ---- gltf-model: a costume file alone (no fighter data), for checking an import -------------------------------------
    //   gltf-model RIG.json OUT_PlXxNr.dat [--high H.gltf] [--low L.gltf] [--eyes] [--template-nr PlMrNr.dat] [--template-ft PlMr.dat] [--name Geno]
    //   (rig.json's "model" supplies what the flags don't; --high drops its low model and, unless --eyes, its eye list)
    public static int Run(string[] a)
    {
        string Arg(string k) { int i = Array.IndexOf(a, k); return i >= 0 && i + 1 < a.Length ? a[i + 1] : null; }
        var rigPath = a[1]; var outPath = a[2];
        var rig = JsonDocument.Parse(File.ReadAllText(rigPath)).RootElement;
        var disc = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), "games/melee/disc/files");
        var nr = Arg("--template-nr") ?? Path.Combine(disc, "PlMrNr.dat"); var ftp = Arg("--template-ft") ?? Path.Combine(disc, "PlMr.dat");
        // rig.json's "model" (eyes, jnames, ...), with --high/--low in place of its files
        var o = rig.TryGetProperty("model", out var me) ? JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(me.GetRawText()) : new();
        if (Arg("--high") != null) { o["high"] = JsonSerializer.SerializeToElement(Path.GetFullPath(Arg("--high"))); o.Remove("low"); }
        if (Arg("--low") != null) o["low"] = JsonSerializer.SerializeToElement(Path.GetFullPath(Arg("--low")));
        if (Arg("--high") != null && !a.Contains("--eyes")) o.Remove("eyes");
        var sp = Spec.From(rig, JsonSerializer.SerializeToElement(o), Path.GetDirectoryName(Path.GetFullPath(rigPath)));
        var (J, W) = FighterBuild.BuildSkeleton(rig);
        var names = rig.GetProperty("joints").EnumerateArray().Select(j => j.GetProperty("name").GetString()).ToList();
        var res = Import(sp, new Skel { J = J, W = W, Names = names }, null, nr, ftp);
        string model = $"Ply{Arg("--name") ?? "Geno"}5K_Share";
        var f = new HSDRawFile();
        f.Roots.Add(new HSDRootNode { Name = model + "_joint", Data = J[0] });
        f.Roots.Add(new HSDRootNode { Name = model + "_matanim_joint", Data = res.MatAnim });
        int flagged = FighterBuild.AlignModel(J[0], res.MatAnim);
        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(outPath)));
        f.Save(outPath);
        foreach (var l in res.Log) Console.WriteLine(l);
        Console.WriteLine($"gltf-model: {J.Count} joints, {res.Dobjs.Count} DObjs (high {res.HighTris} tris, low {res.LowTris}), {flagged} GX buffers aligned -> {outPath}");
        Console.WriteLine("lookups: high " + JsonSerializer.Serialize(res.High) + " low " + JsonSerializer.Serialize(res.Low) + " eyes " + JsonSerializer.Serialize(res.EyeTobjs));
        return 0;
    }

    public static int Tables(string[] a)
    {
        var ft = new HSDRawFile(a[1]).Roots.First(r => r.Name.StartsWith("ftData")).Data as SBM_FighterData;
        var ml = ft.ModelLookupTables;
        List<List<List<int>>> Tab(HSDArrayAccessor<SBM_LookupTable> t) => t?.Array.Select(lt => (lt.LookupEntries?.Array ?? new SBM_LookupEntry[0]).Select(e => (e.Entries ?? new byte[0]).Select(b => (int)b).ToList()).ToList()).ToList();
        var costumes = new List<object>();
        foreach (var c in ml.CostumeVisibilityLookups?.Array ?? new SBM_CostumeLookupTable[0])
            costumes.Add(new Dictionary<string, object> { ["high"] = Tab(c.HighPoly), ["low"] = Tab(c.LowPoly), ["metal"] = Tab(c.MetalPoly), ["metalMain"] = Tab(c.MetalMainModel) });
        var mats = new List<object>();
        foreach (var c in ml.CostumeMaterialLookups?.Array ?? new SBM_CostumeMaterialLookup[0])
            mats.Add(c.Entries?.Array.Select(x => (int)x).ToList());
        int metalD = 0; var metalJ = 0;
        void Walk(HSD_JOBJ j) { for (; j != null; j = j.Next) { metalJ++; for (var d = j.Dobj; d != null; d = d.Next) metalD++; Walk(j.Child); } }
        Walk(ft.MetalModel);
        var metalMats = new List<string>();
        void WalkM(HSD_JOBJ j) { for (; j != null; j = j.Next) { for (var d = j.Dobj; d != null; d = d.Next) metalMats.Add($"{(uint)d.Mobj.RenderFlags:X}:{d.Mobj.Textures?.List.Count ?? 0}"); WalkM(j.Child); } }
        WalkM(ft.MetalModel);
        var metalAttrs = new HashSet<string>();
        void WalkA(HSD_JOBJ j) { for (; j != null; j = j.Next) { for (var d = j.Dobj; d != null; d = d.Next) for (var p = d.Pobj; p != null; p = p.Next) metalAttrs.Add($"{(int)p.Flags:X}/" + string.Join(",", p.ToGXAttributes().Where(x => x.AttributeName != GXAttribName.GX_VA_NULL).Select(x => x.AttributeName.ToString().Replace("GX_VA_", "")))); WalkA(j.Child); } }
        WalkA(ft.MetalModel);
        // model parts: per pose, each keyed joint (depth-first from the start joint) and its first key per track
        object Pose(HSD_AnimJoint aj, int start)
        {
            var keyed = new List<string>(); int i = start;
            void W(HSD_AnimJoint n) { for (; n != null; n = n.Next) { int me = i++;
                var tr = new List<string>();
                for (var fd = n.AOBJ?.FObjDesc; fd != null; fd = fd.Next) { var k = fd.GetDecodedKeys(); tr.Add($"{fd.JointTrackType.ToString().Replace("HSD_A_J_", "")}={k[0].Value:0.##}" + (k.Count > 1 ? $"..{k[^1].Value:0.##}/{k.Count}" : "")); }
                if (tr.Count > 0) keyed.Add($"j{me}: " + string.Join(" ", tr) + (keyed.Count == 0 ? $" [aobj flags {(uint)n.AOBJ.Flags:X} end {n.AOBJ.EndFrame} keys@{string.Join(",", n.AOBJ.FObjDesc.GetDecodedKeys().Select(k => k.Frame + ":" + k.InterpolationType.ToString().Replace("HSD_A_OP_", "")))} ajflags {n.Flags:X}]" : ""));
                W(n.Child); } }
            W(aj);
            var fl = new List<string>(); void F2(HSD_AnimJoint n) { for (; n != null; n = n.Next) { fl.Add($"{n.Flags:X}{(n.AOBJ != null ? "*" : "")}"); F2(n.Child); } } F2(aj);
            keyed.Add("ajflags " + string.Join(",", fl));
            return keyed;
        }
        var parts = (ft.ModelPartAnimations?.Array ?? new SBM_ModelPart[0]).Select(p => new Dictionary<string, object> { ["start"] = p.StartingBone, ["count"] = p.Count, ["entries"] = p.Entries?.Select(b => (int)b).ToList(), ["anims"] = p.Anims?.Length ?? 0,
            ["poses"] = a.Contains("--poses") ? (p.Anims?.Array ?? new HSD_AnimJoint[0]).Select(x => Pose(x, p.StartingBone)).ToList() : null }).ToList();
        var o = new Dictionary<string, object>
        {
            ["groups"] = ml.VisibilityLookupLength, ["costumes"] = costumes, ["materialLookupLength"] = ml.MaterialLookupLength, ["materialLookups"] = mats,
            ["metalJoints"] = metalJ, ["metalDobjs"] = metalD, ["metalMats"] = string.Join(" ", metalMats), ["metalPobjs"] = metalAttrs.ToList(), ["metalRootFlags"] = ft.MetalModel == null ? null : $"{(uint)ft.MetalModel.Flags:X}", ["modelParts"] = parts,
        };
        if (a.Length > 2 && !a[2].StartsWith("--"))
        {   // the texture animations: which DObj, how many frames, and the image/palette index per frame
            var m = ModelSpec.Load(a[2]);
            var ta = new List<object>();
            var flat = new List<HSD_MatAnimJoint>();
            void F(HSD_MatAnimJoint j) { for (; j != null; j = j.Next) { flat.Add(j); F(j.Child); } }
            F(m.MatAnim);
            int di = 0, ti0 = 0;
            for (int ji = 0; ji < m.J.Count; ji++)
            {
                var ma = ji < flat.Count ? flat[ji].MaterialAnimation : null;
                for (var d = m.J[ji].Dobj; d != null; d = d.Next, di++, ma = ma?.Next)
                {
                    int ntex = d.Mobj?.Textures?.List.Count ?? 0;
                    for (var t = ma?.TextureAnimation; t != null; t = t.Next)
                    {
                        var tracks = new Dictionary<string, object>();
                        for (var fd = t.AnimationObject?.FObjDesc; fd != null; fd = fd.Next)
                            tracks[((TexTrackType)fd.TrackType).ToString()] = fd.GetDecodedKeys().Select(k => new[] { k.Frame, k.Value, (float)k.InterpolationType }).ToList();
                        ta.Add(new Dictionary<string, object> { ["dobj"] = di, ["tobjBase"] = ti0, ["texmap"] = t.GXTexMapID.ToString(), ["images"] = t.ImageCount, ["tluts"] = t.TlutCount,
                            ["end"] = t.AnimationObject?.EndFrame, ["aflags"] = t.AnimationObject == null ? null : $"{(uint)t.AnimationObject.Flags:X}", ["tracks"] = tracks });
                    }
                    ti0 += ntex;
                }
            }
            o["texanims"] = ta;
            o["tobjs"] = ti0;
        }
        Console.WriteLine(JsonSerializer.Serialize(o, new JsonSerializerOptions { WriteIndented = true }));
        return 0;
    }
}

// A PNG decoder (non-interlaced; greyscale, RGB, palette, grey+alpha, RGBA; 1-16 bits): images as RGBA8, top row first.
static class PngRead
{
    static int BE(byte[] b, int o) => (b[o] << 24) | (b[o + 1] << 16) | (b[o + 2] << 8) | b[o + 3];
    static int Paeth(int a, int b, int c) { int p = a + b - c, pa = Math.Abs(p - a), pb = Math.Abs(p - b), pc = Math.Abs(p - c); return pa <= pb && pa <= pc ? a : pb <= pc ? b : c; }

    public static (int w, int h, byte[] rgba) Decode(byte[] f)
    {
        if (f.Length < 8 || f[0] != 0x89 || f[1] != (byte)'P' || f[2] != (byte)'N' || f[3] != (byte)'G')
            throw new Exception(f.Length > 2 && f[0] == 0xFF && f[1] == 0xD8 ? "a JPEG texture: export textures as PNG" : "not a PNG image");
        int w = 0, h = 0, depth = 0, ct = 0, il = 0; byte[] plte = null, trns = null; var idat = new MemoryStream();
        for (int o = 8; o + 8 <= f.Length;)
        {
            int len = BE(f, o); string type = System.Text.Encoding.ASCII.GetString(f, o + 4, 4); int d = o + 8;
            if (type == "IHDR") { w = BE(f, d); h = BE(f, d + 4); depth = f[d + 8]; ct = f[d + 9]; il = f[d + 12]; }
            else if (type == "PLTE") plte = f[d..(d + len)];
            else if (type == "tRNS") trns = f[d..(d + len)];
            else if (type == "IDAT") idat.Write(f, d, len);
            else if (type == "IEND") break;
            o = d + len + 4;
        }
        if (il != 0) throw new Exception("an interlaced PNG: save it without interlacing");
        int ch = ct switch { 0 => 1, 2 => 3, 3 => 1, 4 => 2, 6 => 4, _ => throw new Exception("PNG colour type " + ct) };
        int bits = ch * depth, bpp = Math.Max(1, bits / 8), row = (w * bits + 7) / 8;
        idat.Position = 0;
        byte[] raw;
        using (var z = new System.IO.Compression.ZLibStream(idat, System.IO.Compression.CompressionMode.Decompress)) using (var ms = new MemoryStream()) { z.CopyTo(ms); raw = ms.ToArray(); }
        var cur = new byte[row]; var prev = new byte[row]; var outp = new byte[w * h * 4];
        int maxv = (1 << depth) - 1;
        for (int y = 0; y < h; y++)
        {
            int ft = raw[y * (row + 1)];
            Array.Copy(raw, y * (row + 1) + 1, cur, 0, row);
            for (int i = 0; i < row; i++)
            {
                int a = i >= bpp ? cur[i - bpp] : 0, b = prev[i], c = i >= bpp ? prev[i - bpp] : 0;
                cur[i] = (byte)(cur[i] + ft switch { 0 => 0, 1 => a, 2 => b, 3 => (a + b) / 2, 4 => Paeth(a, b, c), _ => throw new Exception("PNG filter " + ft) });
            }
            int S(int x, int k)            // sample k of pixel x, scaled to 0-255 (palette: the raw index)
            {
                if (depth == 8) return cur[x * ch + k];
                if (depth == 16) return cur[(x * ch + k) * 2];
                int bit = (x * ch + k) * depth, v = (cur[bit / 8] >> (8 - depth - bit % 8)) & maxv;
                return ct == 3 ? v : v * 255 / maxv;
            }
            for (int x = 0; x < w; x++)
            {
                int o = (y * w + x) * 4; byte r, g, bb, al = 255;
                switch (ct)
                {
                    case 0: r = g = bb = (byte)S(x, 0); if (trns != null && trns.Length >= 2 && S(x, 0) == (depth == 16 ? trns[0] : trns[1] * 255 / Math.Max(1, maxv))) al = 0; break;
                    case 2: r = (byte)S(x, 0); g = (byte)S(x, 1); bb = (byte)S(x, 2); if (trns != null && trns.Length >= 6 && r == trns[1] && g == trns[3] && bb == trns[5]) al = 0; break;
                    case 3: { int i = S(x, 0); r = plte[i * 3]; g = plte[i * 3 + 1]; bb = plte[i * 3 + 2]; if (trns != null && i < trns.Length) al = trns[i]; break; }
                    case 4: r = g = bb = (byte)S(x, 0); al = (byte)S(x, 1); break;
                    default: r = (byte)S(x, 0); g = (byte)S(x, 1); bb = (byte)S(x, 2); al = (byte)S(x, 3); break;
                }
                outp[o] = r; outp[o + 1] = g; outp[o + 2] = bb; outp[o + 3] = al;
            }
            (prev, cur) = (cur, prev);
        }
        return (w, h, outp);
    }
}
