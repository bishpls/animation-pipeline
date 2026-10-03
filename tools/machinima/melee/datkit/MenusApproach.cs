// Geno on the NEW CHALLENGER screen (NtAppro.usd): his silhouette as the challenger panel's 12th image; and on the
// prize screen after it (SdPrize.usd): his two messages.
//   approach-geno NtAppro.usd SIL.bgra OUT_NtAppro.usd : add the image and key it at frame 12 (see Build)
//   prize-geno SdPrize.usd OUT_SdPrize.usd TEXT1 TEXT2  : the messages in the unused entries 0x47 and 0x48 (see Prize)
// The screen (gm/gmapproach.c) loads ScNtcApproach_scene_data, and every frame asks the challenger panel's texture
// animation (model 0, joint 12, dobj 0) for one frame and stops it there: frame 1 + the image index for the eleven
// unlockable characters (Game & Watch 1 ... Ganondorf 11), frame 0 for anyone else (the whitelist turns them into
// Ganondorf first). The vanilla image track is 0:0 1:0 2:1 ... 11:10 300:10 over eleven 96x160 I4 images. The decomp's
// non-matching gmapproach.c sends Geno (CKind 0x22) to frame 12, so this appends image 11 and keys 12 -> 11 (13 keeps 10,
// as the frames after the vanilla ones do).
using HSDRaw;
using HSDRaw.GX;
using HSDRaw.Melee;

static class MenusApproach
{
    const string Model = "ScNtcApproach_scene_data#0";
    const int Joint = 12, W = 96, H = 160, Frame = 12;

    public static int Build(string[] a)
    {
        if (a.Length < 4) { Console.Error.WriteLine("usage: approach-geno NtAppro.usd SIL.bgra OUT_NtAppro.usd"); return 2; }
        var f = new HSDRawFile(a[1]);
        var fl = MenusGeno.Flat(MenusGeno.FindModel(f, Model));
        var ta = TexKit.TexAnim(fl[Joint].M, 0);
        // refuse anything but the vanilla layout (eleven 96x160 I4 images, frame 12 unkeyed)
        var ib = ta.ImageBuffers.Array;
        if (ta.ImageCount != 11 || ib.Any(b => b.Data.Width != W || b.Data.Height != H || b.Data.Format != GXTexFmt.I4))
            throw new Exception($"not the vanilla challenger panel: {ta.ImageCount} images");
        foreach (var fd in TexKit.Tracks(ta))
            if (fd.GetDecodedKeys().Any(k => k.Frame == Frame)) throw new Exception($"frame {Frame} is already keyed");

        var sil = TexKit.Intensity(a[2], W, H, GXTexFmt.I4);
        // the source is already 16 levels (silhouette.py writes level x 17): the encode must be exact
        var src = TexKit.Bgra(a[2], W, H);
        var dec = TexKit.Decode(sil);
        int err = 0;
        for (int i = 0; i < W * H * 4; i += 4) err = Math.Max(err, Math.Abs(src[i] - dec[i]));
        if (err != 0) throw new Exception($"I4 encode is off by {err}: the source isn't 16 levels");

        var add = new TexKit.Adder();
        var (ii, _) = add.Add(ta, sil);
        if (ii != 11) throw new Exception($"silhouette went to image {ii}, not 11");
        add.Key(ta, new[] { (float)Frame }, ii, -1);
        int al = TexKit.AlignGX(f);
        f.Save(a[3]);
        foreach (var l in add.Log) Console.WriteLine(l);
        var keys = string.Join(" ", TexKit.Tracks(ta).First().GetDecodedKeys().Select(k => $"{k.Frame}:{k.Value}"));
        Console.WriteLine($"silhouette: image {ii} (frame {Frame}); image track {keys}");
        Console.WriteLine($"wrote {a[3]} ({new FileInfo(a[3]).Length} bytes; {al} buffers flagged for 32-byte alignment)");
        return 0;
    }

    // prize-geno SdPrize.usd OUT TEXT1 TEXT2: the decomp's non-matching ifprize.c shows Geno's two messages (IFPRIZE_GENO,
    // IFPRIZE_GENO_MOD) from SIS entries 0x47 and 0x48, which no prize uses (the trophy messages compose in 0x41-0x44 and
    // 0x4A; 0x47-0x49 are empty in the vanilla file). TEXT is plain text, "|" breaking the line (two lines, as every
    // vanilla message), set in the vanilla messages' own code: kerned, white.
    public static int Prize(string[] a)
    {
        if (a.Length < 5) { Console.Error.WriteLine("usage: prize-geno SdPrize.usd OUT_SdPrize.usd TEXT1 TEXT2"); return 2; }
        var sm = new HSDRawFile(a[1]);
        var sd = sm.Roots.First(r => r.Name.StartsWith("SIS_")).Data;
        var sis = new SIS_SdData(); sis._s = sd._s;
        const string Empty = "<KERN><COLOR, 255, 255, 255><END>";
        for (int k = 0; k < 2; k++)
        {
            int idx = 0x47 + k;
            var e = sis.GetTextData(idx);
            if (e.TextCode != Empty) throw new Exception($"entry 0x{idx:X} isn't the vanilla empty entry: {e.TextCode}");
            e.TextCode = "<KERN><COLOR, 255, 255, 255>" + string.Join("<BR>", a[3 + k].Split('|').Select(l => l.Trim().Replace(" ", "<S>"))) + "<END>";
            Console.WriteLine($"0x{idx:X}: {e.TextCode}");
        }
        sm.Save(a[2]);
        Console.WriteLine($"wrote {a[2]} ({new FileInfo(a[2]).Length} bytes)");
        return 0;
    }
}
