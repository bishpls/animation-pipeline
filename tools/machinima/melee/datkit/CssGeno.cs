// css-geno: add Geno to the character select screen's data (MnSlChr.usd), leaving every existing joint index unchanged.
//   css-geno IN.usd OUT.usd ICON.bgra CSP0.bgra [CSP1.bgra ...] [--stock STOCK0.bgra [--stock STOCK1.bgra ...]]
// VS menu (MenuModel, 173 joints):
//   - his icon: a copy of Roy's icon joint pair, appended as the menu model's last joints (173 holder, 174 icon; see
//     ICONJOINT_GENO in the decomp), placed static at the bottom row's right-hand cell (24.85, 5.5), with a new face texture;
//   - his portraits: appended to the four doors' portrait texture animation, one per costume, keyed at hud 25 + costume
//     * 30 for every costume row (at least four: a later door picking the same character gets the next costume; with
//     fewer portraits than rows, the last portrait repeats), so no door ever falls through to Ganondorf's costumes;
//   - his emblem: the doors' emblem animation keyed to Mario's mushroom at the same frames.
// 1P menu (SingleMenuModel "regend_menu", 79 joints) and its CPU door (PortraitModel "door"), mncharsel.c:989-1012:
//   - the same icon, appended the same way from that model's own Roy icon: holder 79, icon 80 (ICONJOINT 1P = 0x50);
//   - the player door's portrait (0x2D) and emblem (0x2B), the CPU door's portrait (6) and emblem (4), at the same frames;
//   - with --stock, the five stock icons (0x35-0x39) keyed to his stock icons at the same frames (they were Sheik's), one
//     --stock per costume in the portraits' order (fewer: the last repeats).
// Images arrive as raw BGRA (width x height x 4): the icon face 64x56, portraits 136x188, one per costume, stock 24x24
// (at most 16 colours, transparency allowed).
using HSDRaw;
using HSDRaw.Common;
using HSDRaw.Common.Animation;
using HSDRaw.GX;
using HSDRaw.Tools;

static class CssGeno
{
    const int Hud = 25, Stride = 30, MinRows = 4, RoyHolder = 13, RoyIcon = 14, MarioEmblemImage = 5;
    static readonly int[] Portraits = { 51, 52, 53, 54 }, Emblems = { 46, 47, 48, 49 };
    const int P1Portrait = 0x2D, P1Emblem = 0x2B, CpuPortrait = 6, CpuEmblem = 4;
    static readonly int[] P1Stocks = { 0x35, 0x36, 0x37, 0x38, 0x39 };

    public static int Run(HSDRawFile f, string outPath, string iconPath, string[] args)
    {
        var stockPaths = new List<string>(); var cspPaths = new List<string>();
        for (int i = 0; i < args.Length; i++) { if (args[i] == "--stock") stockPaths.Add(args[++i]); else cspPaths.Add(args[i]); }
        var root = f.Roots.First(r => r.Name == "MnSelectChrDataTable").Data as HSDRaw.Melee.Mn.SBM_SelectChrDataTable;
        var J = Flat(root.MenuModel, root.MenuAnimation, root.MenuMaterialAnimation);
        var R = Flat(root.SingleMenuModel, root.SingleMenuAnimation, root.SingleMenuMaterialAnimation);
        var D = Flat(root.PortraitModel, root.PortraitAnimation, root.PortraitMaterialAnimation);
        if (J.Count != 173 || R.Count != 79 || D.Count != 10)
        { Console.Error.WriteLine($"expected the vanilla 173/79/10-joint menu, 1P menu and door models, found {J.Count}/{R.Count}/{D.Count} (already patched?)"); return 1; }

        var ft = Tobj(iconPath, 64, 56);
        int vsIcon = AddIcon(J, root.MenuModel, root.MenuAnimation, root.MenuMaterialAnimation, ft);
        int p1Icon = AddIcon(R, root.SingleMenuModel, root.SingleMenuAnimation, root.SingleMenuMaterialAnimation, ft);

        // portraits and emblems: every door's texture animations, keyed at each costume row
        var tobjs = cspPaths.Select(p => Tobj(p, 136, 188)).ToArray();
        int rows = Math.Max(MinRows, tobjs.Length);
        var frames = Enumerable.Range(0, rows).Select(c => (float)(Hud + Stride * c)).ToArray();
        var ad = new TexKit.Adder();
        void Portrait(HSD_MatAnimJoint mj, int dobj)
        {
            var ta = TexKit.TexAnim(mj, dobj);
            var added = tobjs.Select(t => ad.Add(ta, t)).ToArray();
            for (int c = 0; c < rows; c++) { var (ii, ti) = added[Math.Min(c, added.Length - 1)]; ad.Key(ta, new[] { frames[c] }, ii, ti); }
        }
        void Emblem(HSD_MatAnimJoint mj, int dobj) => ad.Key(TexKit.TexAnim(mj, dobj), frames, MarioEmblemImage, -1);
        foreach (var ji in Portraits) Portrait(J[ji].M, 0);
        foreach (var ji in Emblems) Emblem(J[ji].M, 1);
        Portrait(R[P1Portrait].M, 0); Emblem(R[P1Emblem].M, 1);
        Portrait(D[CpuPortrait].M, 0); Emblem(D[CpuEmblem].M, 1);
        string stockNote = "";
        if (stockPaths.Count > 0)
        {
            var sts = stockPaths.Select(p => TexKit.Indexed(p, 24, 24, GXTexFmt.CI4, GXTlutFmt.RGB5A3)).ToArray();
            foreach (var ji in P1Stocks)
            {
                var ta = TexKit.TexAnim(R[ji].M, 0);
                var added = sts.Select(st => ad.Add(ta, st)).ToArray();
                for (int c = 0; c < rows; c++) { var (si, sp) = added[Math.Min(c, added.Length - 1)]; ad.Key(ta, new[] { frames[c] }, si, sp); }
                stockNote = $", 1P stock icons images {string.Join(",", added.Select(x => x.img))}";
            }
        }
        foreach (var l in ad.Log) Console.WriteLine("  " + l);
        Console.WriteLine($"css-geno: {TexKit.AlignGX(f)} GPU buffers flagged 32-byte aligned");
        f.Save(outPath);
        Console.WriteLine($"css-geno: VS icon joint {vsIcon} (0x{vsIcon:X}), 1P icon joint {p1Icon} (0x{p1Icon:X}); {tobjs.Length} portrait(s) keyed at {string.Join(",", frames)}{stockNote} -> {outPath}");
        return 0;
    }

    static List<(HSD_JOBJ J, HSD_AnimJoint A, HSD_MatAnimJoint M)> Flat(HSD_JOBJ jo, HSD_AnimJoint an, HSD_MatAnimJoint ma)
        => MenusGeno.Flat(new MenusGeno.Model("", jo, an, ma));

    // Roy's icon (holder + icon) cloned with a new face, appended as the model's last root child; returns the icon's index
    static int AddIcon(List<(HSD_JOBJ J, HSD_AnimJoint A, HSD_MatAnimJoint M)> L, HSD_JOBJ jo, HSD_AnimJoint an, HSD_MatAnimJoint ma, HSD_TOBJ ft)
    {
        var roy = L[RoyIcon].J;
        var icon = new HSD_JOBJ { Flags = roy.Flags, SX = 1, SY = 1, SZ = 1, Dobj = HSDAccessor.DeepClone<HSD_DOBJ>(roy.Dobj) };
        var face = icon.Dobj.Next.Mobj.Textures;               // dobj 0: the tinted stripe card; dobj 1: the face with its name band
        face.ImageData = ft.ImageData; face.TlutData = ft.TlutData;
        var holder = new HSD_JOBJ { Flags = L[RoyHolder].J.Flags, TX = 24.85f, TY = 5.5f, TZ = -1f, SX = 1, SY = 1.25f, SZ = 1, Child = icon };
        var iconMat = new HSD_MatAnimJoint { MaterialAnimation = HSDAccessor.DeepClone<HSD_MatAnim>(L[RoyIcon].M.MaterialAnimation) };
        Append(jo, holder, an, new HSD_AnimJoint { Child = new HSD_AnimJoint() }, ma, new HSD_MatAnimJoint { Child = iconMat });
        return L.Count + 1;
    }

    static HSD_TOBJ Tobj(string path, int w, int h)
    {
        var t = new HSD_TOBJ();
        t.EncodeImageData(TexKit.Bgra(path, w, h), w, h, GXTexFmt.CI8, GXTlutFmt.RGB5A3);
        return t;
    }

    // append a joint (with its animation and material-animation nodes) as the root's last child, padding the parallel
    // animation chains so the new node lines up with its joint
    static void Append(HSD_JOBJ root, HSD_JOBJ j, HSD_AnimJoint aroot, HSD_AnimJoint a, HSD_MatAnimJoint mroot, HSD_MatAnimJoint m)
    {
        int n = 1; var last = root.Child; while (last.Next != null) { last = last.Next; n++; }
        last.Next = j;
        if (aroot.Child == null) aroot.Child = new HSD_AnimJoint();
        var al = aroot.Child; for (int i = 1; i < n; i++) { if (al.Next == null) al.Next = new HSD_AnimJoint(); al = al.Next; }
        al.Next = a;
        if (mroot.Child == null) mroot.Child = new HSD_MatAnimJoint();
        var ml = mroot.Child; for (int i = 1; i < n; i++) { if (ml.Next == null) ml.Next = new HSD_MatAnimJoint(); ml = ml.Next; }
        ml.Next = m;
    }
}
