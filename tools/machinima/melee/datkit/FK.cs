// FK: sample a fighter figatree over its skeleton, frame by frame, as the game poses it (HSD Hermite/linear/constant keys,
// Euler XYZ joints, classical scale), and write world transforms per joint per frame plus every key (JSON).
//   fk PlXxNr.dat ANIM.dat [OUT.json] [--step S]            one animation (an extracted figatree, see `actions`)
//   fkdir PlXxNr.dat PlXx.dat PlXxAJ.dat OUTDIR [REGEX | IDX=LABEL,...]   every action whose name matches (default: all)
// Output: joints[] (index, parent, rest T/R/S), tracks[] (node, channel, keys [frame,value,tangent,interp]),
// pose[frame][joint] = [r00,r01,r02,r10,r11,r12,r20,r21,r22, x,y,z] with columns r?0..r?2 = the joint's local X/Y/Z axes
// in model space (model space: +Z the fighter's forward, +Y up; the engine yaws TopN by facing*90deg, no mirroring),
// and local[frame][joint] = [tx,ty,tz,rx,ry,rz,sx,sy,sz] after animation.
using System.Globalization;
using System.Numerics;
using System.Text;
using System.Text.RegularExpressions;
using HSDRaw;
using HSDRaw.Common;
using HSDRaw.Common.Animation;
using HSDRaw.Tools;

static class FK
{
    static readonly CultureInfo CI = CultureInfo.InvariantCulture;
    static string F(float v) => float.IsFinite(v) ? v.ToString("0.#####", CI) : "0";

    public static int Run(string[] a)
    {
        if (a[0] == "fk")
        {
            float step = 1; string outp = null;
            for (int i = 3; i < a.Length; i++) { if (a[i] == "--step") step = float.Parse(a[++i], CI); else outp = a[i]; }
            var skel = Skeleton(a[1]);
            var ft = new HSDRawFile(a[2]).Roots[0].Data as HSD_FigaTree;
            var json = Sample(skel, ft, Path.GetFileName(a[2]), step);
            if (outp != null) File.WriteAllText(outp, json); else Console.WriteLine(json);
            return 0;
        }
        if (a[0] == "fkdir")
        {
            var skel = Skeleton(a[1]);
            var pl = new HSDRawFile(a[2]);
            var ftd = pl.Roots.First(r => r.Name.StartsWith("ftData")).Data;
            var tab = ftd.GetType().GetProperty("FighterActionTable").GetValue(ftd) as HSDRaw.Melee.Pl.SBM_FighterActionTable;
            var aj = File.ReadAllBytes(a[3]);
            Directory.CreateDirectory(a[4]);
            // filter: a regex on the action name, or IDX=LABEL,... (table indices, written as LABEL.json; the names vary per
            // fighter, e.g. Link's Wait1 is "Wait" and Marth's forward smash "AttackS4", but the indices are the common ones)
            string sel = a.Length > 5 ? a[5] : ".";
            var byIdx = sel.Contains('=') ? sel.Split(',').Select(p => p.Split('=')).ToDictionary(p => int.Parse(p[0]), p => p[1]) : null;
            var rx = new Regex(sel);
            var done = new HashSet<string>();
            for (int i = 0; i < tab.Commands.Length; i++)
            {
                var c = tab.Commands[i];
                if (c.AnimationSize <= 0 || c.Name == null) continue;
                var m = Regex.Match(c.Name, @"ACTION_(.+?)_figatree");
                var nm = m.Success ? m.Groups[1].Value : c.Name;
                if (byIdx != null) { if (!byIdx.TryGetValue(i, out var lab)) continue; nm = lab; }
                else if (!rx.IsMatch(nm)) continue;
                if (!done.Add(nm)) continue;
                var ft = new HSDRawFile(aj.Skip(c.AnimationOffset).Take(c.AnimationSize).ToArray()).Roots[0].Data as HSD_FigaTree;
                File.WriteAllText(Path.Combine(a[4], $"{nm}.json"), Sample(skel, ft, nm, 1, i, c.Flags));
                Console.WriteLine($"{i,3} {nm} frames {ft.FrameCount} {(m.Success ? m.Groups[1].Value : c.Name)}");
            }
            return 0;
        }
        return 2;
    }

    record Joint(int I, int P, HSD_JOBJ J);

    static List<Joint> Skeleton(string nr)
    {
        var f = new HSDRawFile(nr);
        var jo = f.Roots.First(r => r.Name.EndsWith("_joint") && !r.Name.Contains("matanim")).Data as HSD_JOBJ;
        var list = new List<Joint>();
        void W(HSD_JOBJ j, int p) { for (; j != null; j = j.Next) { int me = list.Count; list.Add(new Joint(me, p, j)); W(j.Child, me); } }
        W(jo, -1);
        return list;
    }

    // HSD_MkRotationMtx: R = Rz * Ry * Rx (column vectors); System.Numerics is row-vector, so S * Rx * Ry * Rz * T
    static Matrix4x4 Local(float[] v) =>
        Matrix4x4.CreateScale(v[6], v[7], v[8]) * Matrix4x4.CreateRotationX(v[3]) * Matrix4x4.CreateRotationY(v[4]) *
        Matrix4x4.CreateRotationZ(v[5]) * Matrix4x4.CreateTranslation(v[0], v[1], v[2]);

    static string Sample(List<Joint> skel, HSD_FigaTree ft, string name, float step, int action = -1, uint flags = 0)
    {
        int n = skel.Count;
        // channel index: T 0-2, R 3-5, S 6-8
        int Chan(JointTrackType t) => t switch
        {
            JointTrackType.HSD_A_J_TRAX => 0, JointTrackType.HSD_A_J_TRAY => 1, JointTrackType.HSD_A_J_TRAZ => 2,
            JointTrackType.HSD_A_J_ROTX => 3, JointTrackType.HSD_A_J_ROTY => 4, JointTrackType.HSD_A_J_ROTZ => 5,
            JointTrackType.HSD_A_J_SCAX => 6, JointTrackType.HSD_A_J_SCAY => 7, JointTrackType.HSD_A_J_SCAZ => 8, _ => -1
        };
        var players = new List<(int node, int ch, FOBJ_Player p)>();
        var sb = new StringBuilder();
        sb.Append($"{{\"name\":\"{name}\",\"action\":{action},\"flags\":{flags},\"frames\":{F(ft.FrameCount)},\"nodes\":{ft.Nodes.Count},\"joints\":[");
        for (int i = 0; i < n; i++)
        {
            var j = skel[i].J;
            sb.Append(i > 0 ? "," : "").Append($"{{\"i\":{i},\"p\":{skel[i].P},\"t\":[{F(j.TX)},{F(j.TY)},{F(j.TZ)}],\"r\":[{F(j.RX)},{F(j.RY)},{F(j.RZ)}],\"s\":[{F(j.SX)},{F(j.SY)},{F(j.SZ)}],\"flags\":{(uint)j.Flags}}}");
        }
        sb.Append("],\"tracks\":[");
        bool first = true;
        for (int ni = 0; ni < ft.Nodes.Count; ni++)
            foreach (var tr in ft.Nodes[ni].Tracks)
            {
                var keys = tr.GetKeys();
                int ch = Chan(tr.JointTrackType);
                if (ch >= 0) players.Add((ni, ch, new FOBJ_Player { Keys = keys, TrackType = tr.TrackType }));
                sb.Append(first ? "" : ",").Append($"{{\"node\":{ni},\"type\":\"{tr.JointTrackType.ToString().Replace("HSD_A_J_", "")}\",\"start\":{tr.StartFrame},\"keys\":[");
                sb.Append(string.Join(",", keys.Select(k => $"[{F(k.Frame)},{F(k.Value)},{F(k.Tan)},{(int)k.InterpolationType}]")));
                sb.Append("]}");
                first = false;
            }
        sb.Append("],\"pose\":[");
        var local = new StringBuilder();
        int nf = (int)Math.Floor(ft.FrameCount / step) + 1;
        var world = new Matrix4x4[n];
        for (int fi = 0; fi < nf; fi++)
        {
            float fr = fi * step;
            var vals = new float[n][];
            for (int i = 0; i < n; i++) { var j = skel[i].J; vals[i] = new[] { j.TX, j.TY, j.TZ, j.RX, j.RY, j.RZ, j.SX, j.SY, j.SZ }; }
            foreach (var (node, ch, p) in players) if (node < n && p.Keys.Count > 0) vals[node][ch] = p.GetValue(fr);
            sb.Append(fi > 0 ? "," : "").Append('[');
            local.Append(fi > 0 ? "," : "").Append('[');
            for (int i = 0; i < n; i++)
            {
                var m = Local(vals[i]);
                world[i] = skel[i].P >= 0 ? m * world[skel[i].P] : m;
                var w = world[i];
                // rows of a System.Numerics matrix are the transformed basis vectors; emit columns-as-axes (r[row][col])
                sb.Append(i > 0 ? "," : "").Append($"[{F(w.M11)},{F(w.M21)},{F(w.M31)},{F(w.M12)},{F(w.M22)},{F(w.M32)},{F(w.M13)},{F(w.M23)},{F(w.M33)},{F(w.M41)},{F(w.M42)},{F(w.M43)}]");
                local.Append(i > 0 ? "," : "").Append('[').Append(string.Join(",", vals[i].Select(F))).Append(']');
            }
            sb.Append(']'); local.Append(']');
        }
        sb.Append("],\"local\":[").Append(local).Append("]}");
        return sb.ToString();
    }
}
