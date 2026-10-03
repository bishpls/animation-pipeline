// Melee's effect files (EfXxData.dat): read them, and build new ones.
//   ef-dump FILE.dat [--gen N,...] [--tex OUTDIR] [--models]
//       the root table (effXxxDataTable): the particle bank (version, first id, generators with their header fields and
//       decoded command lists), the texture bank (groups: format, size, frames; --tex writes every frame as PNG) and the
//       model effects (lifetime, joints, animations, particle joints)
//   ef-build SPEC.json OUT.dat
//       a new effect file from a spec (projects/geno/fx/efge.py writes it): textures (PNG frames per group, encoded to a
//       GX format), generators (header fields plus a command list as hex), and model effects cloned from another file
//
// The layout (decomp src/melee/ef/efasync.c, sysdolphin particle.c; HSDRaw SBM_EffectTable):
//   root "eff<Name>DataTable" = { +0 particle bank*, +4 texture bank*, +8 model effects[n] (0x14 each) }
//   particle bank = { u16 version (0x42), u16 0, s32 first id, s32 count, s32 offset[count], generators... }: offsets are
//     from the bank's start, and the game adds the base in place (psInitDataBankLocate); generator id N is
//     ptclref[bank][N], so a bank's ids run from its first id (file index * 1000)
//   texture bank = { s32 count, s32 offset[count], groups... }: each group { s32 frames, s32 GXTexFmt, s32 GXTlutFmt,
//     s32 w, s32 h, s32 ?, s32 image offset[frames] (+ palette offset[frames]) , data }, offsets from the bank's start
//   model effect = { f32 lifetime, JOBJ*, AnimJoint*, MatAnimJoint*, ShapeAnimJoint* } (EF_EffectDesc), index id % 1000
using System.Text.Json;
using HSDRaw;
using HSDRaw.Common;
using HSDRaw.Common.Animation;
using HSDRaw.GX;
using HSDRaw.Melee.Ef;
using HSDRaw.Tools;

static class EffectKit
{
    static string Arg(string[] a, string k) { int i = Array.IndexOf(a, k); return i >= 0 && i + 1 < a.Length ? a[i + 1] : null; }

    static SBM_EffectTable Table(HSDRawFile f, out string name)
    {
        var r = f.Roots.First(x => x.Name.StartsWith("eff") && x.Name.EndsWith("DataTable"));
        name = r.Name;
        return new SBM_EffectTable { _s = r.Data._s };
    }

    public static string Ops(byte[] code)
    {
        try
        {
            return string.Join(" ", ParticleEncoding.DecodeParticleOpCodes(code).Select(t =>
                t.Item1 == 0 ? $"w{t.Item2[0]}" :
                t.Item1 == 0x40 ? $"tex{t.Item2[0]}" :
                $"{t.Item1:X2}(" + string.Join(",", t.Item2.Select(o => o is float fl ? fl.ToString("0.###") : o.ToString())) + ")"));
        }
        catch (Exception e) { return "?? " + e.Message + " " + Convert.ToHexString(code.Take(48).ToArray()); }
    }

    public static int Dump(string[] a)
    {
        var f = new HSDRawFile(a[1]);
        var t = Table(f, out var rootName);
        var only = Arg(a, "--gen")?.Split(',').Select(int.Parse).ToHashSet();
        Console.WriteLine($"{rootName}: {t._s.Length} bytes");
        var pg = t.Particles;
        if (pg != null)
        {
            Console.WriteLine($"particle bank: version 0x{(ushort)pg.Unknown1:X} ({pg.Unknown2}), first id {pg.EffectIDStart}, {pg.GeneratorCount} generators, {pg._s.Length} bytes");
            var gens = pg.Generators;
            for (int i = 0; i < gens.Length; i++)
            {
                int id = pg.EffectIDStart + i;
                if (only != null && !only.Contains(id) && !only.Contains(i)) continue;
                var g = gens[i];
                if (g == null || g._s == null || g._s.Length < 0x3C) { Console.WriteLine($"  [{i}] id {id}: (empty)"); continue; }
                Console.WriteLine($"  [{i}] id {id}: {g.TypeShape} flags=0x{(int)g.Flags & 0xFFFF:X} texg {g.TexGroup} genlife {g.GenLife} life {g.Life} kind=0x{(uint)g.Kind:X8} ({g.Kind})");
                Console.WriteLine($"       grav {g.Gravity:0.###} fric {g.Friction:0.###} v ({g.VX:0.###},{g.VY:0.###},{g.VZ:0.###}) radius {g.Radius:0.###} angle {g.Angle:0.###} random {g.Random:0.###} size {g.Size:0.###} params ({g.Param1:0.###},{g.Param2:0.###},{g.Param3:0.###})");
                Console.WriteLine($"       cmd[{g.TrackData.Length}]: {Ops(g.TrackData)}");
            }
        }
        var tb = t.TextureGraphics;
        if (tb != null)
        {
            var imgs = tb.ParticleImages;
            Console.WriteLine($"texture bank: {imgs.Length} groups, {tb._s.Length} bytes");
            var outDir = Arg(a, "--tex");
            if (outDir != null) Directory.CreateDirectory(outDir);
            for (int i = 0; i < imgs.Length; i++)
            {
                var g = imgs[i];
                Console.WriteLine($"  texg {i}: {g.ImageCount} x {g.Width}x{g.Height} {g.ImageFormat} tlut {g.PaletteFormat} ({g._s.Length} bytes) hdr+14={g._s.GetInt32(0x14)}");
                if (outDir != null)
                {
                    try
                    {
                        var frames = g.GetRGBAImageData();
                        for (int k = 0; k < frames.Count; k++) Png.Write(Path.Combine(outDir, $"texg{i:D2}_{k:D2}.png"), frames[k], g.Width, g.Height);
                    }
                    catch (Exception e) { Console.WriteLine($"    (decode failed: {e.Message})"); }
                }
            }
        }
        var models = t.Models;
        Console.WriteLine($"model effects: {models.Length}");
        if (a.Contains("--models"))
            for (int i = 0; i < models.Length; i++)
            {
                var m = models[i];
                if (m.RootJoint == null) { Console.WriteLine($"  [{i}] (none) life {m.FrameCount}"); continue; }
                int nj = 0, nd = 0, np = 0; var tex = new HashSet<string>();
                void W(HSD_JOBJ j) { for (; j != null; j = j.Next) { nj++; if (j.Flags.HasFlag(JOBJ_FLAG.PTCL)) np++; for (var d = j.Dobj; d != null; d = d.Next) { nd++; for (var tt = d.Mobj?.Textures; tt != null; tt = tt.Next) if (tt.ImageData != null) tex.Add($"{tt.ImageData.Width}x{tt.ImageData.Height} {tt.ImageData.Format}"); } W(j.Child); } }
                W(m.RootJoint);
                Console.WriteLine($"  [{i}] life {m.FrameCount} joints {nj} dobjs {nd} ptcl-joints {np} anim {(m.JointAnim != null ? "j" : "-")}{(m.MaterialAnim != null ? "m" : "-")}{(m.ShapeAnim != null ? "s" : "-")} tex [{string.Join("; ", tex)}]");
            }
        return 0;
    }

    // ---- ef-build SPEC.json OUT.dat
    // SPEC: { "root": "effGenoDataTable", "bank": 22, "first_id": 22000,
    //         "textures": [ { "fmt": "IA8", "frames": ["a.png", ...] } ],                 (PNG paths relative to the spec)
    //         "generators": [ { "type": 0, "flags": 0, "texg": 0, "genlife": 1, "life": 30, "kind": 1024,
    //                           "grav": 0, "fric": 1, "v": [0,0,1], "radius": 0, "angle": 0, "random": -1, "size": 4,
    //                           "params": [0,0,0], "cmd": "hex" } ],
    //         "models": [ { "file": "EfXxData.dat", "index": 3 } ] }                     (model effects cloned; optional)
    public static int Build(string[] a)
    {
        var specPath = a[1];
        var outPath = a[2];
        var dir = Path.GetDirectoryName(Path.GetFullPath(specPath))!;
        var spec = JsonDocument.Parse(File.ReadAllText(specPath)).RootElement;
        int bank = spec.GetProperty("bank").GetInt32();
        int first = spec.TryGetProperty("first_id", out var fi) ? fi.GetInt32() : bank * 1000;

        // textures: one group per entry, every frame the same size and format
        var groups = new List<HSD_TexGraphic>();
        foreach (var tg in spec.GetProperty("textures").EnumerateArray())
        {
            var fmt = Enum.Parse<GXTexFmt>(tg.GetProperty("fmt").GetString());
            var tobjs = new List<HSD_TOBJ>();
            int w0 = 0, h0 = 0;
            foreach (var fr in tg.GetProperty("frames").EnumerateArray())
            {
                var path = Path.Combine(dir, fr.GetString());
                var (iw, ih, rgba) = PngRead.Decode(File.ReadAllBytes(path));
                if (w0 == 0) { w0 = iw; h0 = ih; }
                if (iw != w0 || ih != h0) throw new Exception($"{path}: {iw}x{ih}, the group's frames are {w0}x{h0}");
                var bgra = new byte[iw * ih * 4];
                for (int i = 0; i < iw * ih; i++)
                {   // PngRead gives RGBA; HSDRaw encodes BGRA
                    bgra[i * 4 + 0] = rgba[i * 4 + 2]; bgra[i * 4 + 1] = rgba[i * 4 + 1];
                    bgra[i * 4 + 2] = rgba[i * 4 + 0]; bgra[i * 4 + 3] = rgba[i * 4 + 3];
                }
                var t = new HSD_TOBJ();
                t.EncodeImageData(bgra, iw, ih, fmt, GXTlutFmt.RGB5A3);
                tobjs.Add(t);
            }
            var g = new HSD_TexGraphic { _s = new HSDStruct(0x18) };
            g.SetFromTOBJs(tobjs.ToArray());
            groups.Add(g);
        }
        var tb = new HSD_TEXGraphicBank { _s = new HSDStruct(4) };
        tb.ParticleImages = groups.ToArray();
        tb._s.IsBufferAligned = true;

        // generators: the header fields, then the command list
        var gens = new List<HSD_ParticleGenerator>();
        foreach (var gs in spec.GetProperty("generators").EnumerateArray())
        {
            var g = new HSD_ParticleGenerator();
            g.New();
            float F(string k, float d = 0) => gs.TryGetProperty(k, out var v) ? (float)v.GetDouble() : d;
            int I(string k, int d = 0) => gs.TryGetProperty(k, out var v) ? v.GetInt32() : d;
            g._s.SetInt16(0x00, (short)(I("type") & 0xF | I("flags") & ~0xF));
            g.TexGroup = (short)I("texg");
            g.GenLife = (short)I("genlife", 1);
            g.Life = (short)I("life", 30);
            g._s.SetInt32(0x08, (int)(gs.TryGetProperty("kind", out var kv) ? kv.GetInt64() : 0));
            g.Gravity = F("grav"); g.Friction = F("fric", 1);
            var v = gs.TryGetProperty("v", out var vv) ? vv.EnumerateArray().Select(e => (float)e.GetDouble()).ToArray() : new float[3];
            g.VX = v[0]; g.VY = v[1]; g.VZ = v[2];
            g.Radius = F("radius"); g.Angle = F("angle"); g.Random = F("random", -1); g.Size = F("size", 1);
            var pr = gs.TryGetProperty("params", out var pv) ? pv.EnumerateArray().Select(e => (float)e.GetDouble()).ToArray() : new float[3];
            g.Param1 = pr[0]; g.Param2 = pr[1]; g.Param3 = pr[2];
            g.TrackData = Convert.FromHexString(gs.GetProperty("cmd").GetString());
            gens.Add(g);
        }
        var pg = new HSD_ParticleGroup { _s = new HSDStruct(0x0C) };
        pg.Unknown1 = 0x42;              // the bank format every vanilla effect file uses
        pg.Unknown2 = (short)bank;       // vanilla files carry their slot here (the game doesn't read it)
        pg.EffectIDStart = first;
        pg.Generators = gens.ToArray();

        // model effects: cloned from other effect files (their joints, animations, textures)
        var models = new List<SBM_EffectModel>();
        if (spec.TryGetProperty("models", out var ms))
            foreach (var m in ms.EnumerateArray())
            {
                var src = new HSDRawFile(Path.Combine(dir, m.GetProperty("file").GetString()));
                var st = Table(src, out _);
                var mm = HSDAccessor.DeepClone<SBM_EffectModel>(st.Models[m.GetProperty("index").GetInt32()]);
                if (m.TryGetProperty("life", out var lf)) mm.FrameCount = (float)lf.GetDouble();
                FighterBuildAlign(mm);
                models.Add(mm);
            }

        var table = new SBM_EffectTable { _s = new HSDStruct(0x08 + 0x14 * models.Count) };
        table.Particles = pg;
        table.TextureGraphics = tb;
        if (models.Count > 0) table.Models = models.ToArray();
        var f = new HSDRawFile();
        f.Roots.Add(new HSDRootNode { Name = spec.GetProperty("root").GetString(), Data = table });
        f.Save(outPath);
        Console.WriteLine($"ef-build: {gens.Count} generators (ids {first}-{first + gens.Count - 1}), {groups.Count} texture groups ({tb._s.Length} bytes), {models.Count} model effects -> {outPath} ({new FileInfo(outPath).Length} bytes)");
        return 0;
    }

    // every display list, vertex buffer and texture of a cloned model effect on a 32-byte boundary (as fighter-build's
    // AlignGX does for cloned articles: a loaded file carries no alignment flags)
    static void FighterBuildAlign(SBM_EffectModel m)
    {
        if (m.RootJoint != null) FighterBuild.AlignModel(m.RootJoint, m.MaterialAnim);
    }

    // ---- art-dump PlXx.dat INDEX : an article's model (joints, meshes, materials, blending, textures) and its states'
    // joint and material animations
    public static int ArticleDump(string[] a)
    {
        var f = new HSDRawFile(a[1]);
        var ft = new HSDRaw.Melee.Pl.SBM_FighterData { _s = f.Roots.First(r => r.Name.StartsWith("ftData")).Data._s };
        var art = ft.Articles.Articles[int.Parse(a[2])];
        var m = art.Model;
        if (art.ParametersExt != null) Console.WriteLine("  ext floats: " + string.Join(" ", Enumerable.Range(0, art.ParametersExt._s.Length / 4).Select(i => $"+{i * 4:X}={art.ParametersExt._s.GetFloat(i * 4):0.###}")));
        Console.WriteLine($"article {a[2]}: model bones {m?.BoneCount} attach {m?.BoneAttachID} bits 0x{m?.BitField:X}; ext {art.ParametersExt?._s.Length} bytes; {art.ItemState?.Array.Length} states");
        int idx = 0;
        void J(HSD_JOBJ j, int d)
        {
            for (; j != null; j = j.Next)
            {
                Console.WriteLine($"  j{idx++} {new string(' ', d * 2)}flags=0x{(uint)j.Flags:X} T=({j.TX:0.##},{j.TY:0.##},{j.TZ:0.##}) R=({j.RX:0.##},{j.RY:0.##},{j.RZ:0.##}) S=({j.SX:0.##},{j.SY:0.##},{j.SZ:0.##})");
                int di = 0;
                for (var dob = j.Dobj; dob != null; dob = dob.Next, di++)
                {
                    int nv = 0, np = 0;
                    for (var po = dob.Pobj; po != null; po = po.Next) { np++; try { nv += po.ToDisplayList().Vertices.Count; } catch { } }
                    var mo = dob.Mobj; var mt = mo?.Material; var pe = mo?.PEDesc;
                    Console.WriteLine($"    {new string(' ', d * 2)}d{di}: {np} pobj {nv} verts; render={mo?.RenderFlags}; dif=({mt?.DIF_R},{mt?.DIF_G},{mt?.DIF_B},{mt?.DIF_A}) amb=({mt?.AMB_R},{mt?.AMB_G},{mt?.AMB_B}) alpha={mt?.Alpha:0.##}" +
                        (pe != null ? $" PE flags={pe.Flags} ref0={pe.AlphaRef0} ref1={pe.AlphaRef1} dst={pe.DestinationAlpha} blend={pe.BlendMode} src={pe.SrcFactor} dstf={pe.DstFactor} logic={pe.BlendOp} z={pe.DepthFunction} acomp={pe.AlphaComp0}/{pe.AlphaOp}/{pe.AlphaComp1}" : " PE -"));
                    if (a.Contains("--verts"))
                        for (var po = dob.Pobj; po != null; po = po.Next)
                        {
                            var dl = po.ToDisplayList();
                            Console.WriteLine($"      attrs: {string.Join(",", po.ToGXAttributes().Select(x => x.AttributeName + ":" + x.AttributeType))}; prims {string.Join(",", dl.Primitives.Select(pr => pr.PrimitiveType + "x" + pr.Count))}");
                            foreach (var v in dl.Vertices)
                                Console.WriteLine($"        p=({v.POS.X:0.###},{v.POS.Y:0.###},{v.POS.Z:0.###}) c=({v.CLR0.R:0.##},{v.CLR0.G:0.##},{v.CLR0.B:0.##},{v.CLR0.A:0.##})");
                        }
                    for (var t = mo?.Textures; t != null; t = t.Next)
                        Console.WriteLine($"      {new string(' ', d * 2)}tex {t.ImageData?.Width}x{t.ImageData?.Height} {t.ImageData?.Format} flags={t.Flags} colorop={t.ColorOperation} alphaop={t.AlphaOperation} coord={t.CoordType} wrap={t.WrapS}/{t.WrapT} rep={t.RepeatS}/{t.RepeatT} blend={t.Blending:0.##}" + (t.TEV != null ? " TEV" : ""));
                }
                J(j.Child, d + 1);
            }
        }
        J(m?.RootModelJoint, 0);
        var st = art.ItemState?.Array ?? new HSDRaw.Melee.Pl.SBM_ItemState[0];
        for (int i = 0; i < st.Length; i++)
        {
            int ntr = 0, nm = 0;
            void AJ(HSD_AnimJoint aj) { for (; aj != null; aj = aj.Next) { if (aj.AOBJ?.FObjDesc != null) foreach (var fo in aj.AOBJ.FObjDesc.List) { ntr++; Console.WriteLine($"    state {i} joint track {fo.JointTrackType} end {aj.AOBJ.EndFrame}"); } AJ(aj.Child); } }
            void MJ(HSD_MatAnimJoint mj) { for (; mj != null; mj = mj.Next) { for (var ma = mj.MaterialAnimation; ma != null; ma = ma.Next) { nm++; if (ma.AnimationObject?.FObjDesc != null) foreach (var fo in ma.AnimationObject.FObjDesc.List) Console.WriteLine($"    state {i} material track {fo.TrackType} end {ma.AnimationObject.EndFrame}"); for (var ta = ma.TextureAnimation; ta != null; ta = ta.Next) Console.WriteLine($"    state {i} texture anim images {ta.ImageCount}"); } MJ(mj.Child); } }
            Console.WriteLine($"  state {i}: anim {(st[i].AnimJoint != null ? "joint" : "-")} {(st[i].MatAnimJoint != null ? "material" : "-")} script {st[i].SubactionScript?._s.Length} bytes");
            if (st[i].SubactionScript != null) Console.WriteLine("    script " + Convert.ToHexString(st[i].SubactionScript._s.GetData()));
            AJ(st[i].AnimJoint); MJ(st[i].MatAnimJoint);
        }
        return 0;
    }
}

