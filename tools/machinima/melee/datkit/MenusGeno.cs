// Menu models in any HSD file, and Geno's menu art outside the character select screen.
//   mscan FILE [FRAMES]                 every model's texture animations: images, tracks, what each frame shows
//   mdump FILE MODEL OUTDIR J1,J2,...   those joints' textures and texture-animation images as PNG, with their keys
// MODEL names a model the way mscan prints it: ROOT#i (a scene's or a model list's i-th model), ROOT:Field (a data
// table's model), or BASE (a BASE_joint root with its BASE_animjoint and BASE_matanim_joint).
using HSDRaw;
using HSDRaw.Common;
using HSDRaw.Common.Animation;
using HSDRaw.GX;
using HSDRaw.Tools;

static partial class MenusGeno
{
    public record Model(string Name, HSD_JOBJ J, HSD_AnimJoint A, HSD_MatAnimJoint M);

    public static IEnumerable<Model> Models(HSDRawFile f)
    {
        foreach (var r in f.Roots)
        {
            switch (r.Data)
            {
                case HSD_SOBJ s:
                    if (s.JOBJDescs != null)
                        for (int i = 0; i < s.JOBJDescs.Length; i++) yield return Desc($"{r.Name}#{i}", s.JOBJDescs[i]);
                    break;
                case HSDNullPointerArrayAccessor<HSD_JOBJDesc> arr:
                    for (int i = 0; i < arr.Length; i++) yield return Desc($"{r.Name}#{i}", arr[i]);
                    break;
                case HSD_JOBJ j when r.Name.EndsWith("_joint") && !r.Name.EndsWith("anim_joint"):
                    var b = r.Name[..^6];
                    yield return new Model(b, j, f.Roots.FirstOrDefault(x => x.Name == b + "_animjoint")?.Data as HSD_AnimJoint,
                                           f.Roots.FirstOrDefault(x => x.Name == b + "_matanim_joint")?.Data as HSD_MatAnimJoint);
                    break;
                default:
                    if (r.Data == null) break;
                    foreach (var p in r.Data.GetType().GetProperties().Where(p => p.PropertyType == typeof(HSD_JOBJ) && p.Name.EndsWith("Model")))
                    {
                        var stem = p.Name[..^5];
                        var jo = p.GetValue(r.Data) as HSD_JOBJ; if (jo == null) continue;
                        // the tables name their animations stem+Animation/MaterialAnimation or stem+AnimJoint/MatAnimJoint (the SSS)
                        object Get(params string[] ns) => ns.Select(n => r.Data.GetType().GetProperty(stem + n)?.GetValue(r.Data)).FirstOrDefault(v => v != null);
                        yield return new Model($"{r.Name}:{p.Name}", jo, Get("Animation", "AnimJoint") as HSD_AnimJoint,
                            Get("MaterialAnimation", "MatAnimJoint") as HSD_MatAnimJoint);
                    }
                    break;
            }
        }
    }

    static Model Desc(string name, HSD_JOBJDesc d) =>
        new Model(name, d?.RootJoint, d?.JointAnimations?.Length > 0 ? d.JointAnimations[0] : null,
                  d?.MaterialAnimations?.Length > 0 ? d.MaterialAnimations[0] : null);

    public static Model FindModel(HSDRawFile f, string name) =>
        Models(f).FirstOrDefault(m => m.Name == name) ?? throw new Exception($"no model {name}");

    // depth-first joints with their parallel animation nodes (the order lb_80011E24 counts in)
    public static List<(HSD_JOBJ J, HSD_AnimJoint A, HSD_MatAnimJoint M)> Flat(Model m)
    {
        var o = new List<(HSD_JOBJ, HSD_AnimJoint, HSD_MatAnimJoint)>();
        void W(HSD_JOBJ j, HSD_AnimJoint a, HSD_MatAnimJoint mj)
        { for (; j != null; j = j.Next, a = a?.Next, mj = mj?.Next) { o.Add((j, a, mj)); W(j.Child, a?.Child, mj?.Child); } }
        W(m.J, m.A, m.M);
        return o;
    }

    // the value a constant-stepped track holds at a frame (the last key at or before it)
    public static float At(List<FOBJKey> keys, float fr)
    {
        FOBJKey best = null;
        foreach (var k in keys) if (k.Frame <= fr && (best == null || k.Frame >= best.Frame)) best = k;
        return best?.Value ?? float.NaN;
    }

    public static IEnumerable<HSD_FOBJDesc> Tracks(HSD_TexAnim ta)
    { for (var fd = ta?.AnimationObject?.FObjDesc; fd != null; fd = fd.Next) yield return fd; }

    public static int Scan(string[] a)
    {
        var f = new HSDRawFile(a[1]);
        var frames = (a.Length > 2 ? a[2] : "0,24,25,55,85,115,180").Split(',').Select(float.Parse).ToArray();
        foreach (var m in Models(f))
        {
            var fl = Flat(m);
            Console.WriteLine($"== {m.Name}: {fl.Count} joints");
            for (int ji = 0; ji < fl.Count; ji++)
            {
                int mi = 0;
                for (var mm = fl[ji].M?.MaterialAnimation; mm != null; mm = mm.Next, mi++)
                {
                    int ti = 0;
                    for (var ta = mm.TextureAnimation; ta != null; ta = ta.Next, ti++)
                    {
                        if (ta.ImageCount == 0) continue;
                        var im = ta.ImageBuffers?.Array?.FirstOrDefault()?.Data;
                        var tr = string.Join(" ", Tracks(ta).Select(fd =>
                        {
                            var k = fd.GetDecodedKeys();
                            return $"{(TexTrackType)fd.TrackType}[{k.Count}k ..{(k.Count > 0 ? k.Max(x => x.Frame) : 0)}: " +
                                   string.Join(",", frames.Select(fr => $"{fr}>{At(k, fr)}")) + "]";
                        }));
                        Console.WriteLine($"  j{ji} (0x{ji:X}) dobj{mi} ta{ti}: {ta.ImageCount} img {im?.Width}x{im?.Height} {im?.Format}, {ta.TlutCount} tlut  {tr}");
                    }
                }
            }
        }
        return 0;
    }

    // mframes FILE MODEL OUTDIR J[:DOBJ],... FRAMES : the image (with the palette its palette track picks) each frame of
    // those joints' texture animations shows, as OUTDIR/jJ_dD_fFRAME.png: what the game draws at that frame
    public static int Frames(string[] a)
    {
        var f = new HSDRawFile(a[1]);
        var fl = Flat(FindModel(f, a[2])); var outDir = a[3];
        Directory.CreateDirectory(outDir);
        var frames = a[5].Split(',').Select(float.Parse).ToArray();
        foreach (var spec in a[4].Split(','))
        {
            var p = spec.Split(':');
            int ji = p[0].StartsWith("0x") ? Convert.ToInt32(p[0], 16) : int.Parse(p[0]), di = p.Length > 1 ? int.Parse(p[1]) : 0;
            var ta = TexKit.TexAnim(fl[ji].M, di);
            var ti = Tracks(ta).FirstOrDefault(t => t.TrackType == (byte)TexTrackType.HSD_A_T_TIMG)?.GetDecodedKeys();
            var tc = Tracks(ta).FirstOrDefault(t => t.TrackType == (byte)TexTrackType.HSD_A_T_TCLT)?.GetDecodedKeys();
            foreach (var fr in frames)
            {
                int ii = (int)At(ti, fr), pi = tc != null ? (int)At(tc, fr) : -1;
                var im = ta.ImageBuffers[ii].Data; var tl = pi >= 0 ? ta.TlutBuffers[pi].Data : null;
                var rgba = tl != null ? GXImageConverter.DecodeTPL(im.Format, im.Width, im.Height, im.ImageData, tl.Format, tl.ColorCount, tl.TlutData)
                                      : GXImageConverter.DecodeTPL(im.Format, im.Width, im.Height, im.ImageData);
                Png.Write(Path.Combine(outDir, $"j{ji}_d{di}_f{fr:000}.png"), rgba, im.Width, im.Height);
                Console.WriteLine($"j{ji} dobj{di} frame {fr}: image {ii}{(pi >= 0 ? $" palette {pi}" : "")} {im.Width}x{im.Height} {im.Format}");
            }
        }
        return 0;
    }

    public static int Dump(string[] a)
    {
        var f = new HSDRawFile(a[1]);
        var m = FindModel(f, a[2]); var outDir = a[3];
        Directory.CreateDirectory(outDir);
        var fl = Flat(m);
        var want = a.Length > 4 ? a[4].Split(',').Select(s => s.StartsWith("0x") ? Convert.ToInt32(s, 16) : int.Parse(s)).ToList() : Enumerable.Range(0, fl.Count).ToList();
        foreach (var ji in want)
        {
            var (j, aj, mj) = fl[ji];
            int di = 0;
            for (var dob = j.Dobj; dob != null; dob = dob.Next, di++)
            {
                int ti = 0;
                for (var t = dob.Mobj?.Textures; t != null; t = t.Next, ti++)
                {
                    var rgba = t.GetDecodedImageData();
                    if (rgba != null) Png.Write(Path.Combine(outDir, $"j{ji}_d{di}_t{ti}.png"), rgba, t.ImageData.Width, t.ImageData.Height);
                    Console.WriteLine($"j{ji} dobj{di} tex{ti} {t.ImageData?.Width}x{t.ImageData?.Height} {t.ImageData?.Format} tlut={t.TlutData?.Format}/{t.TlutData?.ColorCount} flags={t.Flags} render={dob.Mobj.RenderFlags}");
                }
            }
            if (aj?.AOBJ?.FObjDesc != null)
                foreach (var fo in aj.AOBJ.FObjDesc.List)
                    Console.WriteLine($"j{ji} joint track {fo.JointTrackType}: " + string.Join(" ", fo.GetDecodedKeys().Take(60).Select(k => $"{k.Frame}:{k.Value:0.###}")));
            int mi = 0;
            for (var mm = mj?.MaterialAnimation; mm != null; mm = mm.Next, mi++)
            {
                int ti = 0;
                for (var ta = mm.TextureAnimation; ta != null; ta = ta.Next, ti++)
                {
                    var imgs = ta.ImageBuffers?.Array; var tls = ta.TlutBuffers?.Array;
                    Console.WriteLine($"j{ji} matanim{mi} texanim{ti} texmap={ta.GXTexMapID} images={imgs?.Length ?? 0}/{ta.ImageCount} tluts={tls?.Length ?? 0}/{ta.TlutCount} aobj end={ta.AnimationObject?.EndFrame} flags={ta.AnimationObject?.Flags}");
                    foreach (var fo in Tracks(ta))
                        Console.WriteLine($"   track {(TexTrackType)fo.TrackType}: " + string.Join(" ", fo.GetDecodedKeys().Select(k => $"{k.Frame}:{k.Value}{(k.InterpolationType == GXInterpolationType.HSD_A_OP_CON ? "" : "/" + k.InterpolationType.ToString().Replace("HSD_A_OP_", ""))}")));
                    for (int ii = 0; imgs != null && ii < imgs.Length; ii++)
                    {
                        var im = imgs[ii].Data; var tl = tls != null && tls.Length > 0 ? tls[Math.Min(ii, tls.Length - 1)].Data : null;
                        var rgba = tl != null ? GXImageConverter.DecodeTPL(im.Format, im.Width, im.Height, im.ImageData, tl.Format, tl.ColorCount, tl.TlutData)
                                              : GXImageConverter.DecodeTPL(im.Format, im.Width, im.Height, im.ImageData);
                        Png.Write(Path.Combine(outDir, $"j{ji}_m{mi}_ta{ti}_{ii:D3}.png"), rgba, im.Width, im.Height);
                    }
                    if (tls != null && tls.Length > 0) Console.WriteLine($"   tlut0 {tls[0].Data.Format} {tls[0].Data.ColorCount} colours");
                }
                if (mm.AnimationObject?.FObjDesc != null)
                    foreach (var fo in mm.AnimationObject.FObjDesc.List)
                        Console.WriteLine($"   material track {fo.MatTrackType}: " + string.Join(" ", fo.GetDecodedKeys().Take(40).Select(k => $"{k.Frame}:{k.Value:0.###}")));
            }
        }
        return 0;
    }
}


// menus-geno SRC OUT ART : Geno's art in the results screen (GmRst.usd), the VS Records faces (MnMaAll.usd) and the
// in-match HUD (IfAll.usd). SRC holds the vanilla files, OUT gets the patched ones, ART holds the raw BGRA images
// (stock_0.bgra, stock_1.bgra, ... one 24x24 stock icon per costume, or a single stock.bgra; face 64x32, banner 256x28,
// label 120x24). His frame in these animations is gm_80168B34's 180 + costume (the stock icons; at least four costume
// frames are keyed, the last icon repeating) and, in the Records faces, his SELKIND 25. Every file is refused unless it
// is the vanilla layout.
static partial class MenusGeno
{
    const int MarioEmblem = 5;                                   // the mushroom, in every 13/16-image emblem set
    static readonly float[] Rst = { 180 };
    const int RstFrame = 180, MinCostumeFrames = 4;

    // one stock icon per costume row (180 + costume): stock_0.bgra, stock_1.bgra, ... or a single stock.bgra for all
    static List<HSD_TOBJ> Stocks(string art)
    {
        var paths = Enumerable.Range(0, 16).Select(c => Path.Combine(art, $"stock_{c}.bgra")).TakeWhile(File.Exists).ToList();
        if (paths.Count == 0) paths.Add(Path.Combine(art, "stock.bgra"));
        return paths.Select(p => TexKit.Indexed(p, 24, 24, GXTexFmt.CI4, GXTlutFmt.RGB5A3)).ToList();
    }

    // key 180 + costume to each costume's stock icon in one texture animation; returns the images added
    static string KeyStocks(TexKit.Adder ad, HSD_TexAnim ta, List<HSD_TOBJ> stocks)
    {
        var added = stocks.Select(t => ad.Add(ta, t)).ToArray();
        for (int c = 0; c < Math.Max(MinCostumeFrames, added.Length); c++)
        { var (si, st) = added[Math.Min(c, added.Length - 1)]; ad.Key(ta, new float[] { RstFrame + c }, si, st); }
        return $"images {string.Join(",", added.Select(x => x.img))} @{RstFrame}-{RstFrame + Math.Max(MinCostumeFrames, added.Length) - 1}";
    }

    public static int Run(string[] a)
    {
        if (a.Length < 4) { Console.Error.WriteLine("usage: menus-geno SRC OUT ART"); return 2; }
        string src = a[1], outDir = a[2], art = a[3];
        Directory.CreateDirectory(outDir);
        string A(string n) => Path.Combine(art, n);
        var stocks = Stocks(art); var stock = stocks[0];
        Console.WriteLine($"  {stocks.Count} stock icon(s), one per costume");
        var face = TexKit.Indexed(A("face.bgra"), 64, 32, GXTexFmt.CI8, GXTlutFmt.RGB565);
        var banner = TexKit.Intensity(A("banner.bgra"), 256, 28, GXTexFmt.I4);
        var label = TexKit.Intensity(A("label.bgra"), 120, 24, GXTexFmt.I4);
        foreach (var (n, t, w, h) in new[] { (File.Exists(A("stock_0.bgra")) ? "stock_0" : "stock", stock, 24, 24), ("face", face, 64, 32), ("banner", banner, 256, 28), ("label", label, 120, 24) })
        {
            var want = TexKit.Bgra(A(n + ".bgra"), w, h);
            if (n == "banner" || n == "label")                    // I4 holds intensity in 4 bits and shows it as alpha too
                for (int i = 0; i < want.Length; i += 4) { int v = (want[i] + want[i + 1] + want[i + 2]) / 3 / 17 * 17; want[i] = want[i + 1] = want[i + 2] = want[i + 3] = (byte)v; }
            Console.WriteLine($"  {n}: {t.ImageData.Format} {w}x{h}{(t.TlutData != null ? $" + {t.TlutData.Format}/{t.TlutData.ColorCount}" : "")}, max channel error after encoding {TexKit.MaxError(want, TexKit.Decode(t))}");
        }

        // ---- results screen: the winner banner, and each panel's stock icon, name label and emblem
        {
            var f = new HSDRawFile(Path.Combine(src, "GmRst.usd"));
            var J = Flat(FindModel(f, "pnlsce#0"));
            if (J.Count != 115 || TexKit.TexAnim(J[0x0A].M, 1).ImageCount != 30) { Console.Error.WriteLine("GmRst.usd: not the vanilla results panel (already patched?)"); return 1; }
            var ad = new TexKit.Adder();
            var ta = TexKit.TexAnim(J[0x0A].M, 1);                  // the winner banner's name, dobj 1 (gmresultplayer.c)
            var (bi, _) = ad.Add(ta, banner); ad.Key(ta, Rst, bi, -1);
            Console.WriteLine($"GmRst.usd: banner j0x0A dobj1 image {bi} @180");
            foreach (var j in new[] { 0x19, 0x1A, 0x1B, 0x1C })      // jobjs[7]: the stock icon, frame 180 + costume
            {
                ta = TexKit.TexAnim(J[j].M, 1);
                Console.WriteLine($"  stock j0x{j:X} dobj1 {KeyStocks(ad, ta, stocks)}");
            }
            foreach (var j in new[] { 0x21, 0x29, 0x31, 0x39 })      // jobjs[5]: the name label
            {
                ta = TexKit.TexAnim(J[j].M, 0); var (li, _) = ad.Add(ta, label); ad.Key(ta, Rst, li, -1);
                Console.WriteLine($"  label j0x{j:X} dobj0 image {li} @180");
            }
            foreach (var j in new[] { 0x42, 0x43, 0x44, 0x45 })      // jobjs[0]: the series emblem
            {
                ta = TexKit.TexAnim(J[j].M, 0); ad.Key(ta, Rst, MarioEmblem, -1);
                Console.WriteLine($"  emblem j0x{j:X} dobj0 -> image {MarioEmblem} @180");
            }
            Console.WriteLine($"  {TexKit.AlignGX(f)} GPU buffers flagged 32-byte aligned");
            f.Save(Path.Combine(outDir, "GmRst.usd"));
        }

        // ---- Data > VS Records: the row and column faces, keyed by SELKIND
        {
            var f = new HSDRawFile(Path.Combine(src, "MnMaAll.usd"));
            var J = Flat(FindModel(f, "MenMainFaceB_Top"));
            var ta = TexKit.TexAnim(J[2].M, 0);
            if (J.Count != 3 || ta.ImageCount != 25) { Console.Error.WriteLine("MnMaAll.usd: not the vanilla faces (already patched?)"); return 1; }
            var ad = new TexKit.Adder();
            var (fi, ft) = ad.Add(ta, face); ad.Key(ta, new float[] { 25 }, fi, ft);
            Console.WriteLine($"MnMaAll.usd: MenMainFaceB_Top j2 image {fi} palette {ft} @25");
            Console.WriteLine($"  {TexKit.AlignGX(f)} GPU buffers flagged 32-byte aligned");
            f.Save(Path.Combine(outDir, "MnMaAll.usd"));
        }

        // ---- in-match HUD: the stock icons (ifstock.c, 180 + costume) and the emblem behind the percent (ifstatus.c, 180.5)
        {
            var f = new HSDRawFile(Path.Combine(src, "IfAll.usd"));
            var S = Flat(FindModel(f, "Stc_scemdls#0"));
            var M = Flat(FindModel(f, "DmgMrk_scene_models#0"));
            if (S.Count != 17 || TexKit.TexAnim(S[1].M, 0).ImageCount != 130 || TexKit.TexAnim(M[1].M, 0).ImageCount != 16)
            { Console.Error.WriteLine("IfAll.usd: not the vanilla HUD (already patched?)"); return 1; }
            var ad = new TexKit.Adder();
            for (int j = 1; j <= 7; j++)
            {
                var ta = TexKit.TexAnim(S[j].M, 0);
                Console.WriteLine($"IfAll.usd: Stc_scemdls#0 j{j} {KeyStocks(ad, ta, stocks)}");
            }
            ad.Key(TexKit.TexAnim(M[1].M, 0), Rst, MarioEmblem, -1);
            Console.WriteLine($"  DmgMrk_scene_models#0 j1 -> image {MarioEmblem} @180");
            foreach (var l in ad.Log) Console.WriteLine("  " + l);
            Console.WriteLine($"  {TexKit.AlignGX(f)} GPU buffers flagged 32-byte aligned");
            f.Save(Path.Combine(outDir, "IfAll.usd"));
        }
        return 0;
    }
}
