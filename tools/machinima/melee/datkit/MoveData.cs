// movedata: measured frame data and hitbox geometry for a fighter's attacks, the way the game plays them.
//   datkit movedata PlXx.dat PlXxAJ.dat PlXxNr.dat PlCo.dat KIND [RIG.json] > moves.jsonl
// For each attack action: the move script is replayed with the interpreter's timing (AsynchronousTimer n = from frame n,
// SynchronousTimer k = k frames later; subroutines, gotos and loops followed), giving each hitbox's active frames, the
// first interruptible frame, the aerial landing-lag window and the smash charge frame. At every active frame the
// skeleton is posed from the move's own animation (the figatree evaluated at that frame) and each hitbox and hurtbox is
// placed in the fighter's space (facing +Z, feet at the origin, times ModelScale), giving reach forward, back, up and
// down, radius, and disjoint: how far the hit reaches past the fighter's own hurtboxes in that direction.
// Common-bone hitboxes (the part flag) map parts to joints through PlCo.dat's table for KIND, or a rig's part_to_joint.
using System.Numerics;
using System.Text.Json;
using HSDRaw;
using HSDRaw.Common;
using HSDRaw.Common.Animation;
using HSDRaw.Melee.Pl;
using HSDRaw.Tools;

static class MoveData
{
    // the common attack actions (indices are the same for every fighter)
    static readonly (int idx, string name)[] Attacks = {
        (46, "jab1"), (47, "jab2"), (48, "jab3"), (52, "dash_attack"), (53, "ftilt_hi"), (55, "ftilt"), (57, "ftilt_lw"),
        (58, "utilt"), (59, "dtilt"), (60, "fsmash_hi"), (62, "fsmash"), (64, "fsmash_lw"), (66, "usmash"), (67, "dsmash"),
        (68, "nair"), (69, "fair"), (70, "bair"), (71, "uair"), (72, "dair"), (242, "grab"), (243, "dash_grab"),
        // the standardized ones: pummel, ledge attacks (quick under 100%, slow from 100%) and get-up attacks (face up, down).
        // Ledge actions move by TransN from the ledge corner (ftCo_CliffCatch_Phys: pos = ledge + TransN x scale), so their
        // reach is measured from the ledge corner (forward = onto the stage, up from the stage's floor)
        (245, "pummel"), (222, "ledge_quick"), (221, "ledge_slow"), (187, "getup_u"), (195, "getup_d"),
    };

    class Joint { public int parent; public Vector3 t, r, s; }

    // A hurtbox's radius grows with its bone's scale: the engine measures it in the bone's space (lbColl_80006E58,
    // "the hurt radius in the matrix's local space"), so a grown hand's hurtbox is fatter as well as longer. The mean of
    // the axes' scales (the engine's is per direction; the cast's scale tracks are near uniform). Hitbox radii don't grow.
    // MOVEDATA_NOSCALE=1 ignores the animations' scale tracks: the moves as if no limb grew, so the difference against a
    // normal run is what a fighter's limb growth costs it (a grown limb's hurtboxes eat into its disjoint)
    static readonly bool NoScale = Environment.GetEnvironmentVariable("MOVEDATA_NOSCALE") == "1";
    static float BoneScale(Matrix4x4 m) =>
        (new Vector3(m.M11, m.M12, m.M13).Length() + new Vector3(m.M21, m.M22, m.M23).Length() + new Vector3(m.M31, m.M32, m.M33).Length()) / 3f;
    class Hit { public int id, bone, dmg, angle, kbg, wdsk, bkb, element, shield; public float size; public Vector3 off; public bool part; public int start, end = 9999; }

    public static int Run(string[] a)
    {
        var ftf = new HSDRawFile(a[1]);
        var aj = File.ReadAllBytes(a[2]);
        var nr = new HSDRawFile(a[3]);
        var co = new HSDRawFile(a[4]).Roots[0].Data as HSDRaw.Melee.SBM_ftLoadCommonData;
        int kind = int.Parse(a[5]);
        var ft = new SBM_FighterData { _s = ftf.Roots.First(r => r.Name.StartsWith("ftData")).Data._s };
        float scale = ft.Attributes.ModelScale;
        byte[] p2j;
        if (a.Length > 6)
            p2j = JsonDocument.Parse(File.ReadAllText(a[6])).RootElement.GetProperty("part_to_joint").EnumerateArray().Select(e => (byte)e.GetInt32()).ToArray();
        else
            p2j = co.BoneTables.Array[kind]._s.GetReference<HSDAccessor>(0x04)._s.GetData();

        // skeleton, depth first
        var root = nr.Roots.First(r => r.Name.EndsWith("_joint") && !r.Name.Contains("matanim")).Data as HSD_JOBJ;
        var J = new List<Joint>();
        void Flat(HSD_JOBJ j, int p) { for (; j != null; j = j.Next) { int me = J.Count; J.Add(new Joint { parent = p, t = new(j.TX, j.TY, j.TZ), r = new(j.RX, j.RY, j.RZ), s = new(j.SX, j.SY, j.SZ) }); Flat(j.Child, me); } }
        Flat(root, -1);
        var hurt = ft.Hurtboxes.Hurtboxes;
        var cmds = ft.FighterActionTable.Commands;

        foreach (var (bidx, bname) in new[] { (2, "stand"), (31, "crouch") })
        {
            var bc = cmds[bidx];
            var bf = bc.AnimationSize > 0 ? new HSDRawFile(aj.Skip(bc.AnimationOffset).Take(bc.AnimationSize).ToArray()).Roots[0].Data as HSD_FigaTree : null;
            var bp = new List<List<FOBJ_Player>>();
            if (bf != null) foreach (var node in bf.Nodes) bp.Add(node.Tracks.Select(tr => new FOBJ_Player { Keys = tr.GetKeys(), TrackType = tr.TrackType }).ToList());
            var BW = PoseWith(J, bp, 0);
            float top = float.NegativeInfinity, front = float.NegativeInfinity, rear = float.PositiveInfinity;
            foreach (var hb in hurt)
            {
                var j = Math.Min(hb.BoneIndex, J.Count - 1);
                var p1 = Vector3.Transform(new Vector3(hb.X1, hb.Y1, hb.Z1), BW[j]) * scale;
                var p2 = Vector3.Transform(new Vector3(hb.X2, hb.Y2, hb.Z2), BW[j]) * scale;
                float r = hb.Size * scale * BoneScale(BW[j]);
                top = Math.Max(top, Math.Max(p1.Y, p2.Y) + r); front = Math.Max(front, Math.Max(p1.Z, p2.Z) + r); rear = Math.Min(rear, Math.Min(p1.Z, p2.Z) - r);
            }
            Console.WriteLine(JsonSerializer.Serialize(new Dictionary<string, object> { ["body"] = bname, ["top"] = R(top), ["front"] = R(front), ["back"] = R(-rear) }));
        }
        foreach (var (idx, mname) in Attacks)
        {
            if (idx >= cmds.Length) continue;
            var c = cmds[idx];
            if (c.SubAction == null) continue;
            // ---- replay the script
            var hits = new List<Hit>(); var open = new Dictionary<int, Hit>();
            int t = 0, iasa = -1, lagOn = -1, lagOff = -1, charge = -1, guard = 0;
            var hurtEv = new List<(int t, int bone, int state)>();     // 0x1C per-bone and 0x1A whole-body hurtbox states
            var stack = new Stack<(HSDStruct s, int o)>(); var loops = new Stack<(HSDStruct s, int o, int n)>();
            HSDStruct cur = c.SubAction._s; int pc = 0;
            while (cur != null && guard++ < 4000)
            {
                var d = cur.GetData();
                if (pc + 4 > d.Length) { if (stack.Count > 0) { (cur, pc) = stack.Pop(); continue; } break; }
                int op = d[pc] >> 2; int words = Program.CmdWords(op);
                uint W(int k) => (uint)(d[pc + 4 * k] << 24 | d[pc + 4 * k + 1] << 16 | d[pc + 4 * k + 2] << 8 | d[pc + 4 * k + 3]);
                int B(uint w, int from, int len) => (int)((w >> (32 - from - len)) & ((1u << len) - 1));
                int S16(int v) => v >= 0x8000 ? v - 0x10000 : v;
                if (op == 0x00) { if (stack.Count > 0) { (cur, pc) = stack.Pop(); continue; } break; }
                else if (op == 0x01) t += B(W(0), 6, 26);
                else if (op == 0x02) t = Math.Max(t, B(W(0), 6, 26));
                else if (op == 0x03) loops.Push((cur, pc + 4, B(W(0), 6, 26)));
                else if (op == 0x04)
                {
                    if (loops.Count > 0) { var (ls, lo, ln) = loops.Pop(); if (ln > 1) { loops.Push((ls, lo, ln - 1)); cur = ls; pc = lo; continue; } }
                }
                else if (op == 0x05 || op == 0x07)
                {
                    var target = cur.References.TryGetValue(pc + 4, out var tr) ? tr : null;
                    if (op == 0x05) stack.Push((cur, pc + 8));
                    if (target != null) { cur = target; pc = 0; continue; }
                }
                else if (op == 0x06) { if (stack.Count > 0) { (cur, pc) = stack.Pop(); continue; } break; }
                else if (op == 0x0B)
                {
                    uint w0 = W(0), w1 = W(1), w2 = W(2), w3 = W(3), w4 = W(4);
                    var h = new Hit { id = B(w0, 6, 3), bone = B(w0, 13, 8), part = B(w0, 21, 1) == 1, dmg = B(w0, 22, 10),
                        size = B(w1, 0, 16) / 256f, off = new(S16(B(w1, 16, 16)) / 256f, S16(B(w2, 0, 16)) / 256f, S16(B(w2, 16, 16)) / 256f),
                        angle = B(w3, 0, 9), kbg = B(w3, 9, 9), wdsk = B(w3, 18, 9), bkb = B(w4, 0, 9), element = B(w4, 9, 5), shield = B(w4, 14, 8), start = Math.Max(t, 1) };
                    if (open.TryGetValue(h.id, out var prev)) prev.end = Math.Max(t, 1) - 1;
                    open[h.id] = h; hits.Add(h);
                }
                else if (op == 0x0F) { int id = B(W(0), 6, 26); if (open.TryGetValue(id, out var h)) { h.end = Math.Max(t, 1) - 1; open.Remove(id); } }
                else if (op == 0x10) { foreach (var h in open.Values) h.end = Math.Max(t, 1) - 1; open.Clear(); }
                else if (op == 0x13) { int vi = B(W(0), 6, 2), vv = B(W(0), 8, 24); if (vi == 0) { if (vv == 1 && lagOn < 0) lagOn = t; if (vv == 0 && lagOn >= 0) lagOff = t; } }
                else if (op == 0x17) { if (iasa < 0) iasa = t; }
                else if (op == 0x1C) hurtEv.Add((Math.Max(t, 1), B(W(0), 6, 8), B(W(0), 14, 18)));
                else if (op == 0x1A) hurtEv.Add((Math.Max(t, 1), -1, B(W(0), 6, 26)));
                else if (op == 0x38) charge = t;
                pc += 4 * words;
            }

            // ---- the animation
            var figa = c.AnimationSize > 0 ? new HSDRawFile(aj.Skip(c.AnimationOffset).Take(c.AnimationSize).ToArray()).Roots[0].Data as HSD_FigaTree : null;
            int frames = figa != null ? (int)figa.FrameCount : 0;
            var players = new List<List<FOBJ_Player>>();
            if (figa != null)
                foreach (var node in figa.Nodes)
                    players.Add(node.Tracks.Select(tr => new FOBJ_Player { Keys = tr.GetKeys(), TrackType = tr.TrackType }).ToList());
            foreach (var h in hits) if (h.end == 9999) h.end = Math.Max(h.start, frames);

            Matrix4x4[] Pose(float f)
            {
                var W = new Matrix4x4[J.Count];
                for (int i = 0; i < J.Count; i++)
                {
                    var tt = J[i].t; var rr = J[i].r; var ss = J[i].s;
                    if (i < players.Count)
                        foreach (var p in players[i])
                        {
                            float v = p.GetValue(f);
                            switch (p.JointTrackType)
                            {
                                case JointTrackType.HSD_A_J_ROTX: rr.X = v; break; case JointTrackType.HSD_A_J_ROTY: rr.Y = v; break; case JointTrackType.HSD_A_J_ROTZ: rr.Z = v; break;
                                case JointTrackType.HSD_A_J_TRAX: tt.X = v; break; case JointTrackType.HSD_A_J_TRAY: tt.Y = v; break; case JointTrackType.HSD_A_J_TRAZ: tt.Z = v; break;
                                case JointTrackType.HSD_A_J_SCAX: if (!NoScale) ss.X = v; break; case JointTrackType.HSD_A_J_SCAY: if (!NoScale) ss.Y = v; break; case JointTrackType.HSD_A_J_SCAZ: if (!NoScale) ss.Z = v; break;
                            }
                        }
                    var local = Matrix4x4.CreateScale(ss) * Matrix4x4.CreateRotationX(rr.X) * Matrix4x4.CreateRotationY(rr.Y) * Matrix4x4.CreateRotationZ(rr.Z) * Matrix4x4.CreateTranslation(tt);
                    W[i] = J[i].parent >= 0 ? local * W[J[i].parent] : local;
                }
                return W;
            }

            if (Environment.GetEnvironmentVariable("MOVEDATA_DEBUG") == mname)
            {
                int f0 = hits.Count > 0 ? hits.Min(h => h.start) : 0; var P0 = Pose(f0);
                for (int i = 0; i < J.Count; i++) Console.Error.WriteLine($"joint {i} p{J[i].parent} world ({P0[i].M41:0.00},{P0[i].M42:0.00},{P0[i].M43:0.00}) tracks {(i < players.Count ? string.Join(",", players[i].Select(p => p.JointTrackType.ToString().Replace("HSD_A_J_", "") + "=" + p.GetValue(f0).ToString("0.00"))) : "")}");
            }
            // ---- geometry at every active frame
            var geo = new List<object>();
            float fwd = float.NegativeInfinity, back = float.PositiveInfinity, up = float.NegativeInfinity, down = float.PositiveInfinity, rmax = 0;
            float disjFwd = float.NegativeInfinity, disjUp = float.NegativeInfinity, disjDown = float.NegativeInfinity, disjBack = float.NegativeInfinity;
            // the hurtboxes' own extent over the active frames (what a hit meets): front, top, bottom, back
            float hurtF = float.NegativeInfinity, hurtU = float.NegativeInfinity, hurtD = float.PositiveInfinity, hurtB = float.PositiveInfinity;
            var hurtGeo = new List<object>();                  // per active frame: [f, front, top, bottom, back]
            int first = hits.Count > 0 ? hits.Min(h => h.start) : -1, last = hits.Count > 0 ? hits.Max(h => h.end) : -1;
            int frontA = -1, frontB = -1, backA = -1, backB = -1;       // frames with a hit centred in front of / behind him
            for (int f = first; f >= 0 && f <= last; f++)
            {
                var P = Pose(f);
                float hf = float.NegativeInfinity, hu = float.NegativeInfinity, hd = float.PositiveInfinity, hb0 = float.PositiveInfinity;
                // hurtboxes the script has made invincible or intangible on this frame don't count (Double Punch's fists)
                var off = new HashSet<int>(); bool bodyOff = false;
                foreach (var e in hurtEv.Where(e => e.t <= f))
                {
                    if (e.bone < 0) bodyOff = e.state != 0;
                    else if (e.state != 0) off.Add(e.bone); else off.Remove(e.bone);
                }
                foreach (var hb in hurt)
                {
                    if (bodyOff || off.Contains(hb.BoneIndex)) continue;
                    var j = Math.Min(hb.BoneIndex, J.Count - 1);
                    var p1 = Vector3.Transform(new Vector3(hb.X1, hb.Y1, hb.Z1), P[j]) * scale;
                    var p2 = Vector3.Transform(new Vector3(hb.X2, hb.Y2, hb.Z2), P[j]) * scale;
                    float r = hb.Size * scale * BoneScale(P[j]);
                    hf = Math.Max(hf, Math.Max(p1.Z, p2.Z) + r); hu = Math.Max(hu, Math.Max(p1.Y, p2.Y) + r); hd = Math.Min(hd, Math.Min(p1.Y, p2.Y) - r);
                    hb0 = Math.Min(hb0, Math.Min(p1.Z, p2.Z) - r);
                }
                if (!float.IsInfinity(hf)) { hurtF = Math.Max(hurtF, hf); hurtU = Math.Max(hurtU, hu); hurtD = Math.Min(hurtD, hd); hurtB = Math.Min(hurtB, hb0); }
                hurtGeo.Add(float.IsInfinity(hf) ? new object[] { f } : new object[] { f, R(hf), R(hu), R(hd), R(-hb0) });
                var spheres = new List<double[]>();
                foreach (var h in hits.Where(h => h.start <= f && f <= h.end))
                {
                    int jb = h.part ? (h.bone < p2j.Length ? p2j[h.bone] : 0) : h.bone;
                    if (jb >= J.Count) jb = 0;
                    var cpos = Vector3.Transform(h.off, P[jb]) * scale;
                    float r = h.size * scale;
                    fwd = Math.Max(fwd, cpos.Z + r); back = Math.Min(back, cpos.Z - r); up = Math.Max(up, cpos.Y + r); down = Math.Min(down, cpos.Y - r);
                    rmax = Math.Max(rmax, r);
                    if (!float.IsInfinity(hf))          // a fully intangible frame has no body to be disjoint from
                    { disjFwd = Math.Max(disjFwd, cpos.Z + r - hf); disjBack = Math.Max(disjBack, hb0 - (cpos.Z - r)); disjUp = Math.Max(disjUp, cpos.Y + r - hu); disjDown = Math.Max(disjDown, hd - (cpos.Y - r)); }
                    spheres.Add(new double[] { Math.Round(cpos.Y, 2), Math.Round(cpos.Z, 2), Math.Round(r, 2) });
                    float bodyZ = P[1].M43 * scale;                      // TransN: where he is (a ledge action moves by it)
                    if (cpos.Z > bodyZ) { if (frontA < 0) frontA = f; frontB = f; }
                    if (cpos.Z < bodyZ) { if (backA < 0) backA = f; backB = f; }
                }
                geo.Add(new object[] { f, spheres });
            }
            // whole-body intangibility / invincibility windows (0x1A), and the TransN path's ends
            var inv = new List<int[]>();
            for (int f = 1, from = -1; f <= Math.Max(frames, 1) + 1; f++)
            {
                int st = 0;
                foreach (var e in hurtEv.Where(e => e.bone < 0 && e.t <= f)) st = e.state;
                bool on = st != 0 && f <= Math.Max(frames, 1);
                if (on && from < 0) from = f;
                if (!on && from >= 0) { inv.Add(new[] { from, f - 1 }); from = -1; }
            }
            var T0 = Pose(0); var TN = Pose(frames);
            int stand = -1;
            for (int f = 0; f <= frames && stand < 0; f++) { var Pf = Pose(f); if (Pf[1].M43 >= 0 && Pf[1].M42 >= 0) stand = f; }
            var o = new Dictionary<string, object>
            {
                ["move"] = mname, ["action"] = idx, ["frames"] = frames, ["iasa"] = iasa, ["charge"] = charge,
                ["lag_window"] = lagOn >= 0 ? new[] { lagOn, lagOff } : null, ["scale"] = scale,
                ["windows"] = hits.Select(h => new[] { h.start, h.end }).Distinct(new ArrCmp()).OrderBy(w => w[0]).ToArray(),
                ["startup"] = first, ["last_active"] = last,
                ["damage_max"] = hits.Count > 0 ? hits.Max(h => h.dmg) : 0,
                ["hits"] = hits.Select(h => new { h.id, h.start, h.end, h.dmg, size = h.size * scale, h.angle, h.kbg, h.wdsk, h.bkb, h.element, h.shield }).ToArray(),
                ["intangible"] = inv.ToArray(),
                ["trans0"] = new[] { R(T0[1].M42 * scale), R(T0[1].M43 * scale) }, ["trans_end"] = new[] { R(TN[1].M42 * scale), R(TN[1].M43 * scale) },
                ["stand"] = stand,
                ["front_frames"] = frontA >= 0 ? new[] { frontA, frontB } : null, ["back_frames"] = backA >= 0 ? new[] { backA, backB } : null,
            };
            if (first >= 0)
            {
                o["reach_fwd"] = R(fwd); o["reach_back"] = R(-back); o["reach_up"] = R(up); o["reach_down"] = R(down);
                o["geo"] = geo;
                o["radius_max"] = R(rmax); object D(float v) => float.IsInfinity(v) ? null : R(v);
                o["disjoint_fwd"] = D(disjFwd); o["disjoint_up"] = D(disjUp); o["disjoint_down"] = D(disjDown); o["disjoint_back"] = D(disjBack);
                o["hurt_geo"] = hurtGeo;
                o["hurt_fwd"] = D(hurtF); o["hurt_up"] = D(hurtU); o["hurt_down"] = D(hurtD); o["hurt_back"] = hurtB == float.PositiveInfinity ? null : R(-hurtB);
            }
            Console.WriteLine(JsonSerializer.Serialize(o));
        }
        return 0;
    }

    static Matrix4x4[] PoseWith(List<Joint> J, List<List<FOBJ_Player>> players, float f)
    {
        var W = new Matrix4x4[J.Count];
        for (int i = 0; i < J.Count; i++)
        {
            var tt = J[i].t; var rr = J[i].r; var ss = J[i].s;
            if (i < players.Count)
                foreach (var p in players[i])
                {
                    float v = p.GetValue(f);
                    switch (p.JointTrackType)
                    {
                        case JointTrackType.HSD_A_J_ROTX: rr.X = v; break; case JointTrackType.HSD_A_J_ROTY: rr.Y = v; break; case JointTrackType.HSD_A_J_ROTZ: rr.Z = v; break;
                        case JointTrackType.HSD_A_J_TRAX: tt.X = v; break; case JointTrackType.HSD_A_J_TRAY: tt.Y = v; break; case JointTrackType.HSD_A_J_TRAZ: tt.Z = v; break;
                        case JointTrackType.HSD_A_J_SCAX: if (!NoScale) ss.X = v; break; case JointTrackType.HSD_A_J_SCAY: if (!NoScale) ss.Y = v; break; case JointTrackType.HSD_A_J_SCAZ: if (!NoScale) ss.Z = v; break;
                    }
                }
            var local = Matrix4x4.CreateScale(ss) * Matrix4x4.CreateRotationX(rr.X) * Matrix4x4.CreateRotationY(rr.Y) * Matrix4x4.CreateRotationZ(rr.Z) * Matrix4x4.CreateTranslation(tt);
            W[i] = J[i].parent >= 0 ? local * W[J[i].parent] : local;
        }
        return W;
    }

    static double R(float v) => float.IsInfinity(v) ? double.NaN : Math.Round(v, 2);

    // bodydata: where the hurtboxes go through non-attack actions (hit reactions, tumble, dodges, the shield, grabs):
    //   datkit bodydata PlXx.dat PlXxAJ.dat PlXxNr.dat PlCo.dat KIND RIG.json|- IDX[,IDX...] > body.jsonl
    // One line per action: its frames and flags, the standing box (Wait1, frame 0) and, per frame, the union of the hurtboxes
    // (top, bottom, front, back from his position, facing +Z, times ModelScale) with TransN in the pose (a root-motion
    // action's path is included, so it reads from where the action started), plus TransN itself and the head joint's height.
    public static int Body(string[] a)
    {
        var ftf = new HSDRawFile(a[1]);
        var aj = File.ReadAllBytes(a[2]);
        var nr = new HSDRawFile(a[3]);
        var ft = new SBM_FighterData { _s = ftf.Roots.First(r => r.Name.StartsWith("ftData")).Data._s };
        float scale = ft.Attributes.ModelScale;
        var root = nr.Roots.First(r => r.Name.EndsWith("_joint") && !r.Name.Contains("matanim")).Data as HSD_JOBJ;
        var J = new List<Joint>();
        void Flat(HSD_JOBJ j, int p) { for (; j != null; j = j.Next) { int me = J.Count; J.Add(new Joint { parent = p, t = new(j.TX, j.TY, j.TZ), r = new(j.RX, j.RY, j.RZ), s = new(j.SX, j.SY, j.SZ) }); Flat(j.Child, me); } }
        Flat(root, -1);
        var hurt = ft.Hurtboxes.Hurtboxes;
        var cmds = ft.FighterActionTable.Commands;
        int head = ft.FighterBoneTable != null ? ft.FighterBoneTable.HeadBone : -1;
        List<List<FOBJ_Player>> Players(int idx, out int frames, out uint flags)
        {
            var c = cmds[idx]; flags = c.Flags; frames = 0;
            var pl = new List<List<FOBJ_Player>>();
            if (c.AnimationSize <= 0) return pl;
            var fg = new HSDRawFile(aj.Skip(c.AnimationOffset).Take(c.AnimationSize).ToArray()).Roots[0].Data as HSD_FigaTree;
            frames = (int)fg.FrameCount;
            foreach (var node in fg.Nodes) pl.Add(node.Tracks.Select(tr => new FOBJ_Player { Keys = tr.GetKeys(), TrackType = tr.TrackType }).ToList());
            return pl;
        }
        float[] Box(Matrix4x4[] W)
        {
            float top = float.NegativeInfinity, bot = float.PositiveInfinity, front = float.NegativeInfinity, back = float.PositiveInfinity;
            foreach (var hb in hurt)
            {
                var j = Math.Min(hb.BoneIndex, J.Count - 1);
                var p1 = Vector3.Transform(new Vector3(hb.X1, hb.Y1, hb.Z1), W[j]) * scale;
                var p2 = Vector3.Transform(new Vector3(hb.X2, hb.Y2, hb.Z2), W[j]) * scale;
                float r = hb.Size * scale * BoneScale(W[j]);
                top = Math.Max(top, Math.Max(p1.Y, p2.Y) + r); bot = Math.Min(bot, Math.Min(p1.Y, p2.Y) - r);
                front = Math.Max(front, Math.Max(p1.Z, p2.Z) + r); back = Math.Min(back, Math.Min(p1.Z, p2.Z) - r);
            }
            return new[] { top, bot, front, -back };
        }
        // --capsules: every hurtbox's world capsule per frame too (x1 y1 z1 x2 y2 z2 r, model scale applied), and the
        // standing pose's, for areas and overlaps (projects/geno/director/labs/cannon_hurt.py)
        bool caps = a.Contains("--capsules");
        double[][] Caps(Matrix4x4[] W) => hurt.Select(hb =>
        {
            var j = Math.Min(hb.BoneIndex, J.Count - 1);
            var p1 = Vector3.Transform(new Vector3(hb.X1, hb.Y1, hb.Z1), W[j]) * scale;
            var p2 = Vector3.Transform(new Vector3(hb.X2, hb.Y2, hb.Z2), W[j]) * scale;
            return new double[] { R(p1.X), R(p1.Y), R(p1.Z), R(p2.X), R(p2.Y), R(p2.Z), R(hb.Size * scale * BoneScale(W[j])) };
        }).ToArray();
        var sp = Players(2, out _, out _);
        var sW = PoseWith(J, sp, 0);
        var sb = Box(sW);
        foreach (var idx in a[7].Split(',').Select(int.Parse))
        {
            if (idx >= cmds.Length) continue;
            var pl = Players(idx, out int frames, out uint flags);
            var per = new List<double[]>();
            var cap = new List<double[][]>();
            for (int f = 0; f <= frames; f++)
            {
                var W = PoseWith(J, pl, f);
                var b = Box(W);
                float hy = head >= 0 && head < J.Count ? W[head].M42 * scale : float.NaN;
                per.Add(new double[] { f, R(b[0]), R(b[1]), R(b[2]), R(b[3]), R(W[1].M42 * scale), R(W[1].M43 * scale), R(hy) });
                if (caps) cap.Add(Caps(W));
            }
            var o = new Dictionary<string, object> { ["action"] = idx, ["name"] = cmds[idx].Name?.Replace("_figatree", ""),
                ["frames"] = frames, ["flags"] = flags, ["scale"] = scale,
                ["stand"] = new[] { R(sb[0]), R(sb[1]), R(sb[2]), R(sb[3]) }, ["per"] = per };
            if (caps) { o["caps"] = cap; o["stand_caps"] = Caps(sW); }
            // --joint N: that joint's world position per frame (model scale applied), e.g. the bone a code-made hurtbox
            // rides (Samus's Morph Ball: ftSs_SpecialLw_8012AEBC's one sphere on joint 2)
            int ji = Array.IndexOf(a, "--joint");
            if (ji >= 0 && ji + 1 < a.Length)
            {
                int jn = int.Parse(a[ji + 1]);
                o["joint"] = Enumerable.Range(0, frames + 1).Select(f => { var W = PoseWith(J, pl, f); return new double[] { R(W[jn].M41 * scale), R(W[jn].M42 * scale), R(W[jn].M43 * scale) }; }).ToList();
            }
            Console.WriteLine(JsonSerializer.Serialize(o));
        }
        return 0;
    }

    class ArrCmp : IEqualityComparer<int[]>
    {
        public bool Equals(int[] x, int[] y) => x.SequenceEqual(y);
        public int GetHashCode(int[] o) => o[0] * 1000 + o[1];
    }
}
