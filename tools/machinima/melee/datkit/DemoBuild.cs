// DemoBuild: a fighter's own results-screen poses (fighter-build calls it when anims.json has a "demo" section).
// The results screen (and the other demo scenes) animate a fighter from the demo action table (ftData+0x14), whose rows
// point into a per-character motion file: rows 0-9 into GmRstM{CODE}.dat (Win1, Win1Wait, Win2, Win2Wait1, Win2Wait2,
// Win3, Win3Wait, Selected, SelectedWait, Lose), rows 10+ into the shared intro and ending archives. That file is a plain
// HSD archive with no relocations and one root (ftDemoResultMotionFile{NAME}) at data offset 0, holding one figatree
// archive per animation end to end on 0x20 boundaries; each row's symbol is its figatree archive's root name
// (ftData_80085CD8 looks it up) and its offset is from the data's start (ftData_80085B98).
//   anims.json "demo": {"file": "GmRstMGe.dat", "root": "ftDemoResultMotionFileGeno",
//                        "anims": {NAME: {"frames": N, "tracks": {...}}},        (as anims.json "anims")
//                        "rows": {"0": {"anim": NAME, "flags": 0x22, "script": HEX}, ...}}
// Rows not listed keep the template's (Mario's intro and ending rows, which his shared archives hold).
using System.Text.Json;
using HSDRaw;
using HSDRaw.Common;
using HSDRaw.Common.Animation;
using HSDRaw.GX;
using HSDRaw.Melee.Pl;
using HSDRaw.Tools;

static class DemoBuild
{
    public static int Write(SBM_FighterData ft, JsonElement demo, int nJoints, string outDir, string prefix)
    {
        var chunks = new List<(string sym, byte[] data)>();
        foreach (var an in demo.GetProperty("anims").EnumerateObject())
        {
            string sym = prefix + an.Name + "_figatree";
            var figa = new HSD_FigaTree { Type = 1, FrameCount = an.Value.GetProperty("frames").GetInt32() };
            var nodes = new List<FigaTreeNode>();
            var tracks = an.Value.GetProperty("tracks");
            for (int ji = 0; ji < nJoints; ji++)
            {
                var node = new FigaTreeNode();
                if (tracks.TryGetProperty(ji.ToString(), out var tj))
                {
                    Tracks(node, tj.GetProperty("r"), new[] { JointTrackType.HSD_A_J_ROTX, JointTrackType.HSD_A_J_ROTY, JointTrackType.HSD_A_J_ROTZ });
                    Tracks(node, tj.GetProperty("t"), new[] { JointTrackType.HSD_A_J_TRAX, JointTrackType.HSD_A_J_TRAY, JointTrackType.HSD_A_J_TRAZ });
                }
                nodes.Add(node);
            }
            figa.Nodes = nodes;
            var af = new HSDRawFile(); af.Roots.Add(new HSDRootNode { Name = sym, Data = figa });
            using var ms = new MemoryStream(); af.Save(ms);
            var bytes = ms.ToArray();                       // Save closes the stream; ToArray still works
            if (bytes.Length > 0xB000) throw new Exception($"demo: {sym} is {bytes.Length} bytes; the results screen's buffer takes 0xB000");
            chunks.Add((sym, bytes));
        }
        var offsets = new Dictionary<string, (int off, int size)>();
        byte[] blob;
        using (var mf = new MemoryStream())
        {
            foreach (var (sym, data) in chunks)
            {
                offsets[sym] = ((int)mf.Position, data.Length);
                mf.Write(data);
                while (mf.Position % 0x20 != 0) mf.WriteByte(0xFF);
            }
            blob = mf.ToArray();
        }
        var file = new HSDRawFile();
        file.Roots.Add(new HSDRootNode { Name = demo.GetProperty("root").GetString(), Data = new HSDAccessor { _s = new HSDStruct(blob) } });
        string path = Path.Combine(outDir, demo.GetProperty("file").GetString()!);
        file.Save(path);

        var cmds = ft.DemoActionTable.Commands.ToList();
        int rows = 0;
        foreach (var r in demo.GetProperty("rows").EnumerateObject())
        {
            int i = int.Parse(r.Name);
            var c = cmds[i];
            string sym = prefix + r.Value.GetProperty("anim").GetString() + "_figatree";
            c.SymbolName = new HSD_String { Value = sym };
            c.AnimationOffset = offsets[sym].off; c._s.SetInt32(0x08, offsets[sym].size);
            c.Flags = (uint)r.Value.GetProperty("flags").GetInt64();
            c.SubAction = new HSDRaw.Melee.Cmd.SBM_FighterSubactionData { _s = new HSDStruct(Convert.FromHexString(r.Value.GetProperty("script").GetString()!)) };
            cmds[i] = c; rows++;
        }
        ft.DemoActionTable.Commands = cmds.ToArray();
        Console.WriteLine($"demo: {chunks.Count} poses, {blob.Length} bytes -> {path}; {rows} demo rows rewritten");
        return rows;
    }

    static void Tracks(FigaTreeNode node, JsonElement keys, JointTrackType[] types)
    {
        var ks = keys.EnumerateArray().Select(k => k.EnumerateArray().Select(x => (float)x.GetDouble()).ToArray()).ToList();
        for (int c = 0; c < 3; c++)
        {
            var list = new List<FOBJKey>();
            float lastFrame = -1;
            foreach (var k in ks)
            {
                if (k[0] <= lastFrame) list.RemoveAt(list.Count - 1);
                list.Add(new FOBJKey { Frame = k[0], Value = k[1 + c], InterpolationType = GXInterpolationType.HSD_A_OP_LIN });
                lastFrame = k[0];
            }
            if (list.All(k => Math.Abs(k.Value - list[0].Value) < 1e-5f)) list = new List<FOBJKey> { list[0] };
            node.Tracks.Add(new HSD_Track(FOBJFrameEncoder.EncodeFrames(list, types[c])));
        }
    }
}
