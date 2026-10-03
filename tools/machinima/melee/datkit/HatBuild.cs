// HatBuild: a Kirby copy hat (PlKbCpXx.dat) from glTF meshes, on a vanilla hat file as the template.
//   kirby-hat TEMPLATE_PlKbCpXx.dat OUT.dat --high H.gltf [--low L.gltf] [--symbol ftDataKirbyCopyGeno]
// The root is a KirbyHatStruct (decomp ft/types.h): +0 the hat joint, +4 FtPartsDesc (model_num, then a row of four
// FtPartsVisLookup*: [0] normal, [1] low detail, [2] normal again, [3] none), +0xC five dynamics pointers (kept from the
// template: NULL on Mario's and Luigi's caps). The template's joint is kept (its translate (0, 5.62, 0) and flags); the
// game draws it with the matrix of Kirby's joint 6, so hat-file space is Kirby's rest model space.
// The glTF meshes are read in that space (unskinned; glTF +Y up, +Z Kirby's front) and become rigid DObjs on the joint,
// one per primitive, high then low, each with a clone of the template's own cap material (DIFFUSE+TEX0, one CMP layer
// blended at 1 over a diffuse lightmap) and the cast's cull bit unless the material is double-sided.
using System.Numerics;
using HSDRaw;
using HSDRaw.Common;
using HSDRaw.GX;
using HSDRaw.Melee.Pl;

static partial class GltfModel
{
    public static int KirbyHat(string[] a)
    {
        string Arg(string k) { int i = Array.IndexOf(a, k); return i >= 0 && i + 1 < a.Length ? a[i + 1] : null; }
        var tplPath = a[1]; var outPath = a[2];
        var symbol = Arg("--symbol") ?? "ftDataKirbyCopyGeno";
        var f = new HSDRawFile(tplPath);
        var root = f.Roots.First(r => r.Name.StartsWith("ftDataKirbyCopy"));
        var hs = root.Data._s;
        var joint = hs.GetReference<HSD_JOBJ>(0x00);
        if (joint.Child != null || joint.Next != null) throw new Exception($"{tplPath}: the template's hat has more than one joint (use Mario's or Luigi's cap)");
        // the template's material: the first single-layer CMP UV material, clamped
        HSD_MOBJ tplM = null;
        for (var d = joint.Dobj; d != null && tplM == null; d = d.Next)
        {
            var t = d.Mobj?.Textures;
            if (t != null && t.Next == null && t.ImageData?.Format == GXTexFmt.CMP && ((int)t.Flags & 0xF) == 0 && t.WrapS == GXWrapMode.CLAMP) tplM = d.Mobj;
        }
        if (tplM == null) throw new Exception($"{tplPath}: no single-layer CMP material to copy");
        POBJ_FLAG bits = (POBJ_FLAG)((int)joint.Dobj.Pobj.Flags & 0xF);

        var W = ModelSpec.Local(joint);
        var sk = new Skel { J = new() { joint }, W = new() { W }, Names = new() { "J00" } };
        var sp = new Spec { WeightStep = 0.05f, MaxRebind = 1e9f };
        var tc = new TexCache(); var log = new List<string>();
        var dobjs = new List<HSD_DOBJ>(); var lists = new Dictionary<string, List<int>> { ["high"] = new(), ["low"] = new() };
        var tris = new Dictionary<string, int> { ["high"] = 0, ["low"] = 0 };
        foreach (var (lod, path) in new[] { ("high", Arg("--high")), ("low", Arg("--low")) })
        {
            if (path == null) continue;
            var g = Gltf.Load(path);
            foreach (var p in ReadPrims(g, sk, sp, log, lod))
            {
                var m = HSDAccessor.DeepClone<HSD_MOBJ>(tplM);
                bool cull = !(p.HasMat && p.MatJ.TryGetProperty("doubleSided", out var ds) && ds.GetBoolean());
                bool tex = p.HasMat && p.MatJ.TryGetProperty("pbrMetallicRoughness", out var pbr) && pbr.TryGetProperty("baseColorTexture", out var bt0);
                int set = 0;
                if (tex)
                {
                    var bt = p.MatJ.GetProperty("pbrMetallicRoughness").GetProperty("baseColorTexture");
                    set = bt.TryGetProperty("texCoord", out var tce) ? tce.GetInt32() : 0;
                    int ti = bt.GetProperty("index").GetInt32();
                    var im = GltfImage(g, ti, tc);
                    var (img, _) = Encode(im.rgba, im.w, im.h, GXTexFmt.CMP, GXTlutFmt.RGB565, tc, g.ImageName(g.El("textures", ti).GetProperty("source").GetInt32()));
                    var t = m.Textures; t.ImageData = img; t.TlutData = null;
                    bool unit = p.Tri.All(i => p.UV[set][i].X >= -1e-3f && p.UV[set][i].X <= 1.001f && p.UV[set][i].Y >= -1e-3f && p.UV[set][i].Y <= 1.001f);
                    t.WrapS = Wrap(g, bt, unit, "wrapS"); t.WrapT = Wrap(g, bt, unit, "wrapT"); t.RepeatS = 1; t.RepeatT = 1;
                }
                else throw new Exception($"{p.Name}: untextured (every hat mesh carries a texture, as the vanilla caps do)");
                var d = new HSD_DOBJ { Mobj = m };
                d.Pobj = Polygons(new[] { (p, p.Tri.ToArray()) }, sk, cull, true, false, set, set, false, bits, out int nt, rigid: true);
                lists[lod].Add(dobjs.Count); dobjs.Add(d); tris[lod] += nt;
                log.Add($"  d{dobjs.Count - 1,-3} {lod} {p.Name,-20} {p.MatName,-12} {nt,4} tris {d.Pobj.List.Count} pobj{(cull ? "" : " 2-sided")}");
            }
        }
        if (dobjs.Count == 0) throw new Exception("no meshes");
        if (dobjs.Count > 32) throw new Exception($"{dobjs.Count} DObjs: the engine holds 32 per hat (ftParts_80075650)");
        if (lists["low"].Count == 0) lists["low"] = lists["high"];
        for (int i = 0; i < dobjs.Count; i++) dobjs[i].Next = i + 1 < dobjs.Count ? dobjs[i + 1] : null;
        joint.Dobj = dobjs[0];

        // the visibility row: model_num 1 (one group), one option each
        SBM_LookupTable Table(List<int> l) => new SBM_LookupTable { LookupEntries = new HSDArrayAccessor<SBM_LookupEntry> { Array = new[] { new SBM_LookupEntry { Entries = l.Select(i => (byte)i).ToArray() } } } };
        var hi = new HSDArrayAccessor<SBM_LookupTable> { Array = new[] { Table(lists["high"]) } };
        var lo = new HSDArrayAccessor<SBM_LookupTable> { Array = new[] { Table(lists["low"]) } };
        var row = new HSDAccessor(); row._s = new HSDStruct(0x10);
        row._s.SetReference(0x00, hi); row._s.SetReference(0x04, lo); row._s.SetReference(0x08, hi);
        hs.SetInt32(0x04, 1); hs.SetReference(0x08, row);
        // +0xC: five dynamics pointers, NULL (the caps' file struct is 0x18 long; Luigi's +0xC points at data of his own,
        // which only his copy's code reads). Written out in full so the C struct's 0x20 bytes are all ours.
        if (hs.Length < 0x20) hs.Resize(0x20);
        for (int o = 0x0C; o < 0x20; o += 4) { hs.SetReference(o, null); hs.SetInt32(o, 0); }
        root.Name = symbol;
        int aligned = FighterBuild.AlignModel(joint, null);
        Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(outPath)));
        f.Save(outPath);
        foreach (var l in log) Console.WriteLine(l);
        foreach (var l in tc.Log) Console.WriteLine(l);
        Console.WriteLine($"kirby-hat: {symbol}: {dobjs.Count} DObjs (normal {lists["high"].Count}: {tris["high"]} tris; low {(Arg("--low") != null ? lists["low"].Count : 0)}: {tris["low"]} tris), " +
                          $"{tc.Map.Count} textures {tc.Bytes} bytes, {aligned} GX buffers aligned, {new FileInfo(outPath).Length} bytes -> {outPath}");
        return 0;
    }
}
