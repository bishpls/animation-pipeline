// The Forest Maze in the menus: the stage select (MnSlMap.usd) and the Random Stage Switch's name (SdMenu.usd).
//   sis-dump SdMenu.usd [FROM TO]            the menu text entries (SIS_MenuData) as text codes
//   dobj-info FILE MODEL J                   a joint's DObjs: attributes, vertex count and bounds, material, textures
//   menus-stage ART_DIR MnSlMap.usd OUT_MnSlMap.usd SdMenu.usd OUT_SdMenu.usd : add the stage (see Build)
using System.Globalization;
using System.Numerics;
using HSDRaw;
using HSDRaw.Common;
using HSDRaw.Common.Animation;
using HSDRaw.GX;
using HSDRaw.Melee;
using HSDRaw.Tools;

static class MenusStage
{
    public static int SisDump(string[] a)
    {
        var f = new HSDRawFile(a[1]);
        var sd = f.Roots.First(r => r.Name.StartsWith("SIS_")).Data;
        var s = new SIS_SdData(); s._s = sd._s;
        int from = a.Length > 2 ? int.Parse(a[2]) : 0, to = a.Length > 3 ? int.Parse(a[3]) : s.Length - 1;
        Console.WriteLine($"{s.Length} entries (0 and 1 are the images and spacing)");
        for (int i = Math.Max(2, from); i <= Math.Min(to, s.Length - 1); i++)
            Console.WriteLine($"{i} 0x{i:X}: {s.GetTextData(i)?.TextCode}");
        return 0;
    }

    // menus-stage ART_DIR SPEC.json MnSlMap.usd OUT_MnSlMap.usd SdMenu.usd OUT_SdMenu.usd
    // The Forest Maze in the stage select, as the decomp's mnstagesel.c (non-matching) expects it:
    //   - PositionModel: a 20th icon slot, a sibling after the 19th, sliding in with the bottom row to x = -4.0, y = -9.1
    //     (one bottom-row step left of Battlefield's 1.3: the open space at the row's left end, Michael 2026-09-30);
    //   - IconSpecialModel: the icon as image 7 of the single icons' texture animation (frame 7; frames 2-6 are the five
    //     vanilla single icons);
    //   - StageNameModel: the name as image 30 (frame 600 = 20 x 30; image 29 is "RANDOM");
    //   - StagePreviewModel: the hologram for segment 30 (frames 1500-1549, free in the vanilla file): Battlefield's
    //     preview joint cloned (material, grid texture, pop-in and visibility tracks, retimed +300 frames) with the mesh
    //     rebuilt from the spec's play plane;
    //   - SdMenu.usd: menu text 0x19, the unused Akaneia slot's name, set to "Forest Maze" (the Random Stage Switch row).
    public static int Build(string[] a)
    {
        string art = a[1];
        var spec = System.Text.Json.JsonDocument.Parse(File.ReadAllText(a[2])).RootElement;
        var f = new HSDRawFile(a[3]);
        var log = new List<string>();
        var add = new TexKit.Adder();

        // the 20th slot
        var pos = MenusGeno.Flat(MenusGeno.FindModel(f, "MnSelectStageDataTable:PositionModel"));
        var (j11, a11, _) = pos[12];                              // slot 11: Battlefield's, the bottom row's first
        var jn = HSDAccessor.DeepClone<HSD_JOBJ>(j11); jn.Next = null; jn.Child = null;
        var an = HSDAccessor.DeepClone<HSD_AnimJoint>(a11); an.Next = null; an.Child = null;
        foreach (var fd in an.AOBJ.FObjDesc.List)
            if (fd.JointTrackType == JointTrackType.HSD_A_J_TRAX)
            {
                var k = fd.GetDecodedKeys(); float fin = k.Last().Value;
                foreach (var key in k) if (Math.Abs(key.Value - fin) < 1e-3) key.Value = -4.0f;
                fd.SetKeys(k, fd.TrackType);
            }
        var (last, lastA, _) = pos[pos.Count - 1];
        last.Next = jn; lastA.Next = an;
        log.Add($"position: slot 19 after {pos.Count - 1} joints, x -4.0 y {jn.TY}");

        // the icon (image 7, frame 7)
        var spc = MenusGeno.Flat(MenusGeno.FindModel(f, "MnSelectStageDataTable:IconSpecialModel"));
        var ta = TexKit.TexAnim(spc[1].M, 1);
        var icon = TexKit.Indexed(Path.Combine(art, "icon.bgra"), 64, 56, GXTexFmt.CI8, GXTlutFmt.RGB565);
        var (ii, ti) = add.Add(ta, icon);
        if (ii != 7) throw new Exception($"icon went to image {ii}, not 7");
        add.Key(ta, new[] { 7f }, ii, ti);
        log.Add($"icon: image {ii} palette {ti} (frame 7)");

        // the name (image 30, frame 600)
        var nm = MenusGeno.Flat(MenusGeno.FindModel(f, "MnSelectStageDataTable:StageNameModel"));
        var tn = TexKit.TexAnim(nm[2].M, 0);
        var name = TexKit.Intensity(Path.Combine(art, "name.bgra"), 224, 56, GXTexFmt.I4);
        var (ni, _) = add.Add(tn, name);
        if (ni != 30) throw new Exception($"name went to image {ni}, not 30");
        add.Key(tn, new[] { 600f }, ni, -1);
        log.Add($"name: image {ni} (frame 600)");
        // the name plate (every stage's): scaled 0.84 about its centre (joint 1, the plate's tilt) and moved 2.4 left, so
        // the widest names (Final Destination, Princess Peach's Castle: x 15-288 px at res 1) end left of the Forest Maze's
        // icon at the bottom row's left end (x 246) and still start on screen (measured: SCOPE.md "the icon's place")
        var plate = nm[1].J;
        plate.SX *= 0.84f; plate.SY *= 0.84f; plate.SZ *= 0.84f; plate.TX -= 2.4f;
        log.Add($"name plate: scale {plate.SX:0.###}, x {plate.TX:0.##}");

        // the hologram (segment 30)
        var pv = MenusGeno.Flat(MenusGeno.FindModel(f, "MnSelectStageDataTable:StagePreviewModel"));
        var (bf, bfA, _) = pv[111];                               // Battlefield's preview (segment 24)
        var hj = HSDAccessor.DeepClone<HSD_JOBJ>(bf); hj.Next = null; hj.Child = null;
        var ha = HSDAccessor.DeepClone<HSD_AnimJoint>(bfA); ha.Next = null; ha.Child = null;
        foreach (var fd in ha.AOBJ.FObjDesc.List)
        {
            var k = fd.GetDecodedKeys();
            foreach (var key in k) if (key.Frame >= 1150 && key.Frame < 1600) key.Frame += 300;
            fd.SetKeys(k, fd.TrackType);
        }
        // the mesh: the spec's play plane, scaled to Battlefield's hologram (its 136.8 ledges are ~9.5 wide there)
        var mesh = new List<GX_Vertex>();
        // an outline extrusion (the flat front and back faces left out: head-on they fill the circle as one bright
        // slab; the vanilla holograms read as edges), at two thirds of Battlefield's hologram scale
        const float k0 = 0.045f; float y0 = 1.81f + 40 * 0.068f, z0 = -3.2f, zk = 0.0615f;
        // a spec with its own "hologram" (low-poly faces, per-material batches of triangles) uses it whole, with a normal
        // per triangle; otherwise the stage gobj's faces, the flat front and back faces left out
        if (spec.TryGetProperty("hologram", out var holo) && holo.GetArrayLength() > 0)
            foreach (var face in holo.EnumerateArray())
                foreach (var t in face.GetProperty("tris").EnumerateArray())
                {
                    var P = t.EnumerateArray().Select(p => new Vector3((float)p[0].GetDouble(), (float)p[1].GetDouble(), (float)p[2].GetDouble())).ToArray();
                    var n = Vector3.Normalize(Vector3.Cross(P[1] - P[0], P[2] - P[0]));
                    if (float.IsNaN(n.X)) continue;
                    foreach (var q in P)
                        mesh.Add(new GX_Vertex { POS = new GXVector3(q.X * k0, y0 + q.Y * k0, z0 + q.Z * zk), NRM = new GXVector3(n.X, n.Y, n.Z), TEX0 = new GXVector2((q.X + 70) / 140f, (q.Y + 60) / 100f) });
                }
        else
        foreach (var go in spec.GetProperty("gobjs").EnumerateArray())
        {
            if (go.GetProperty("kind").GetString() != "stage") continue;
            foreach (var face in go.GetProperty("faces").EnumerateArray())
            {
                var nrm = face.GetProperty("normal");
                if (Math.Abs(nrm[2].GetDouble()) > 0.9) continue;
                foreach (var t in face.GetProperty("tris").EnumerateArray())
                    foreach (var p in t.EnumerateArray())
                    {
                        float x = (float)p[0].GetDouble(), y = (float)p[1].GetDouble(), z = (float)p[2].GetDouble();
                        mesh.Add(new GX_Vertex
                        {
                            POS = new GXVector3(x * k0, y0 + y * k0, z0 + z * zk),
                            NRM = new GXVector3((float)nrm[0].GetDouble(), (float)nrm[1].GetDouble(), (float)nrm[2].GetDouble()),
                            TEX0 = new GXVector2((x + 70) / 140f, (y + 40) / 80f),
                        });
                    }
            }
        }
        var gen = new POBJ_Generator { CullMode = GenCullMode.None };
        var po = gen.CreatePOBJsFromTriangleList(mesh, new[] { GXAttribName.GX_VA_POS, GXAttribName.GX_VA_NRM, GXAttribName.GX_VA_TEX0 }, null, null);
        gen.SaveChanges();
        hj.Dobj.Pobj = po; hj.Dobj.Next = null;
        var (plast, plastA, _) = (pv[112].J, pv[112].A, pv[112].M);   // j1's last child
        plast.Next = hj; plastA.Next = ha;
        log.Add($"hologram: {mesh.Count / 3} triangles, segment 30 (frames 1500-1549)");

        int al = TexKit.AlignGX(f);
        f.Save(a[4]);
        log.Add($"wrote {a[4]} ({new FileInfo(a[4]).Length} bytes; {al} buffers flagged for 32-byte alignment)");

        // the Random Stage Switch's name
        var sm = new HSDRawFile(a[5]);
        var sd = sm.Roots.First(r => r.Name.StartsWith("SIS_")).Data;
        var sis = new SIS_SdData(); sis._s = sd._s;
        var e = sis.GetTextData(0x19);
        string before = e.TextCode;
        e.TextCode = "<KERN><SCALING, 138, 138>Forest<S>Maze</SCALING><END>";
        sm.Save(a[6]);
        log.Add($"SdMenu 0x19: {before} -> {e.TextCode}; wrote {a[6]} ({new FileInfo(a[6]).Length} bytes)");
        foreach (var l in add.Log.Concat(log)) Console.WriteLine(l);
        return 0;
    }

    public static int DobjInfo(string[] a)
    {
        var f = new HSDRawFile(a[1]);
        var fl = MenusGeno.Flat(MenusGeno.FindModel(f, a[2]));
        var (j, aj, mj) = fl[int.Parse(a[3])];
        Console.WriteLine($"joint T=({j.TX},{j.TY},{j.TZ}) R=({j.RX},{j.RY},{j.RZ}) S=({j.SX},{j.SY},{j.SZ}) flags {j.Flags}");
        int di = 0;
        for (var d = j.Dobj; d != null; d = d.Next, di++)
        {
            var mo = d.Mobj; var mt = mo?.Material;
            Console.WriteLine($" dobj{di}: render {mo?.RenderFlags} dif ({mt?.DIF_R},{mt?.DIF_G},{mt?.DIF_B},{mt?.DIF_A}) amb ({mt?.AMB_R},{mt?.AMB_G},{mt?.AMB_B}) alpha {mt?.Alpha} pe {mo?.PEDesc != null}");
            for (var t = mo?.Textures; t != null; t = t.Next)
                Console.WriteLine($"   tex {t.ImageData?.Width}x{t.ImageData?.Height} {t.ImageData?.Format} coord {t.CoordType} wrap {t.WrapS}/{t.WrapT} rep {t.RepeatS}x{t.RepeatT} flags {t.Flags} S=({t.SX},{t.SY}) T=({t.TX},{t.TY})");
            for (var p = d.Pobj; p != null; p = p.Next)
            {
                var dl = p.ToDisplayList();
                var vs = dl.Vertices;
                var mn = new Vector3(vs.Min(v => v.POS.X), vs.Min(v => v.POS.Y), vs.Min(v => v.POS.Z));
                var mx = new Vector3(vs.Max(v => v.POS.X), vs.Max(v => v.POS.Y), vs.Max(v => v.POS.Z));
                Console.WriteLine($"   pobj flags {p.Flags} {vs.Count} verts, pos {mn} .. {mx}, uv0 {vs.Min(v => v.TEX0.X):0.##}..{vs.Max(v => v.TEX0.X):0.##} x {vs.Min(v => v.TEX0.Y):0.##}..{vs.Max(v => v.TEX0.Y):0.##}");
            }
        }
        return 0;
    }
}
