// StageKit: read Melee's stage files (GrXx.dat) the way the engine does, and report them as numbers.
//   stage-dump GrXx.dat [OUT.json] [--anim-frames N]
// Output (JSON): the stage scale and grGroundParam (camera, per-StKind music rows), every map gobj (joint, mesh, texture,
// light, fog, animation counts; its collision links), the general points (spawns, respawns, items, camera range, blast
// zones) in world space, and the collision (vertices, lines with their surface and pass-through/ledge flags, line groups
// with the joint each is bound to). World space is what the engine computes at load:
//   - a map gobj's joints hang under a root scaled by grGroundParam's stage scale (ground.c Ground_801C1A20);
//   - joint indices (general points, collision links) walk the gobj's joint tree depth first from its root = 0, without
//     entering an INSTANCE joint's children (ground.c Ground_801C34AC, mplib.c mpLib_800552B0);
//   - a collision group bound to a joint has its vertices in that joint's space (mpLib_80055E9C: pos = joint mtx x vertex);
//     an unbound group's vertices are world positions times the stage scale (mpLibLoad).
// Joints are evaluated at rest and at frame 0 of the gobj's first joint animation (the engine starts most stage anims
// there); for each animated joint the animation's world-space range over its frames is reported (moving platforms).
// Code-side bindings (a stage's StageData.joints table in the DOL, e.g. Fountain of Dreams') are not in the file: groups
// with no file link are reported unbound, and the in-game GRDUMP (director cue) is the check.
using System.Globalization;
using System.Numerics;
using System.Text.Json;
using HSDRaw;
using HSDRaw.Common;
using HSDRaw.GX;
using HSDRaw.Common.Animation;
using HSDRaw.Melee.Gr;
using HSDRaw.Tools;

static class StageKit
{
    static double R(float v) => Math.Round(v, 4);

    class J
    {
        public HSD_JOBJ Jo; public int Index, Parent; public HSD_AnimJoint Anim;
        public Matrix4x4 Rest, Frame0; public bool Animated; public float[] YRange, XRange;
    }

    // HSD_MkRotationMtx: S, then Rx, Ry, Rz, then T (row-vector System.Numerics order), as ModelSpec.Local
    static Matrix4x4 Local(float tx, float ty, float tz, float rx, float ry, float rz, float sx, float sy, float sz) =>
        Matrix4x4.CreateScale(sx, sy, sz) * Matrix4x4.CreateRotationX(rx) * Matrix4x4.CreateRotationY(ry) *
        Matrix4x4.CreateRotationZ(rz) * Matrix4x4.CreateTranslation(tx, ty, tz);

    static float[] Channels(HSD_JOBJ j) => new[] { j.TX, j.TY, j.TZ, j.RX, j.RY, j.RZ, j.SX, j.SY, j.SZ };

    static readonly Dictionary<JointTrackType, int> Chan = new()
    {
        [JointTrackType.HSD_A_J_TRAX] = 0, [JointTrackType.HSD_A_J_TRAY] = 1, [JointTrackType.HSD_A_J_TRAZ] = 2,
        [JointTrackType.HSD_A_J_ROTX] = 3, [JointTrackType.HSD_A_J_ROTY] = 4, [JointTrackType.HSD_A_J_ROTZ] = 5,
        [JointTrackType.HSD_A_J_SCAX] = 6, [JointTrackType.HSD_A_J_SCAY] = 7, [JointTrackType.HSD_A_J_SCAZ] = 8,
    };

    static List<(int ch, FOBJ_Player p)> Tracks(HSD_AnimJoint a)
    {
        var l = new List<(int, FOBJ_Player)>();
        if (a?.AOBJ?.FObjDesc == null) return l;
        foreach (var fd in a.AOBJ.FObjDesc.List)
            if (Chan.TryGetValue(fd.JointTrackType, out var ch)) l.Add((ch, new FOBJ_Player(fd)));
        return l;
    }

    // the engine's joint order: depth first from the root (0); an INSTANCE joint's children are not entered
    static List<J> Joints(HSD_JOBJ root, HSD_AnimJoint aroot, float scale, int frames)
    {
        var list = new List<J>();
        var top = Matrix4x4.CreateScale(scale);
        float end = aroot?.AOBJ?.EndFrame ?? 0;
        void W(HSD_JOBJ j, HSD_AnimJoint a, int parent, Matrix4x4 pRest, Matrix4x4 pF0, List<Matrix4x4> pFrames)
        {
            for (; j != null; j = j.Next, a = a?.Next)
            {
                var ch = Channels(j);
                var tr = Tracks(a);
                var rest = Local(ch[0], ch[1], ch[2], ch[3], ch[4], ch[5], ch[6], ch[7], ch[8]) * pRest;
                float[] At(float f) { var c = (float[])ch.Clone(); foreach (var (k, p) in tr) c[k] = p.GetValue(f); return c; }
                var c0 = At(0);
                var f0 = Local(c0[0], c0[1], c0[2], c0[3], c0[4], c0[5], c0[6], c0[7], c0[8]) * pF0;
                var me = new J { Jo = j, Index = list.Count, Parent = parent, Anim = a, Rest = rest, Frame0 = f0 };
                me.Animated = tr.Any(t => !t.p.IsConstant);
                List<Matrix4x4> myFrames = null;
                if (pFrames != null || me.Animated)
                {
                    int n = Math.Max(1, Math.Min(frames, (int)Math.Ceiling(end) + 1));
                    myFrames = new List<Matrix4x4>(n);
                    for (int f = 0; f < n; f++)
                    {
                        var c = At(f);
                        myFrames.Add(Local(c[0], c[1], c[2], c[3], c[4], c[5], c[6], c[7], c[8]) * (pFrames != null ? pFrames[f] : pF0));
                    }
                    me.YRange = new[] { myFrames.Min(m => m.M42), myFrames.Max(m => m.M42) };
                    me.XRange = new[] { myFrames.Min(m => m.M41), myFrames.Max(m => m.M41) };
                }
                list.Add(me);
                if (!j.Flags.HasFlag(JOBJ_FLAG.INSTANCE)) W(j.Child, a?.Child, me.Index, rest, f0, myFrames);
            }
        }
        W(root, aroot, -1, top, top, null);
        return list;
    }

    // stage-patch IN.dat OUT.dat [--joint G:J:DX:DY]... [--line L:DX:DY]... : move a map gobj's joint and a collision line's
    // vertices by world units (divided by the stage scale into the file's units), then write the file back through HSDRaw.
    // The feasibility probe for stage-build: collision and visuals edited together, the rest of the file round-tripped.
    public static int Patch(string[] a)
    {
        var f = new HSDRawFile(a[1]);
        var gp = f.Roots.First(r => r.Name == "grGroundParam").Data as SBM_GroundParam;
        var head = f.Roots.First(r => r.Name == "map_head").Data as SBM_Map_Head;
        var coll = f.Roots.First(r => r.Name == "coll_data").Data as SBM_Coll_Data;
        float sc = gp.StageScale;
        var gobjs = head.ModelGroups.Array;
        var verts = coll.Vertices; var lines = coll.Links;
        for (int i = 3; i < a.Length; i++)
        {
            if (a[i] == "--joint")
            {
                var q = a[++i].Split(':'); int g = int.Parse(q[0]), jn = int.Parse(q[1]);
                float dx = float.Parse(q[2], CultureInfo.InvariantCulture), dy = float.Parse(q[3], CultureInfo.InvariantCulture);
                var js = new List<HSD_JOBJ>();
                void W(HSD_JOBJ j) { for (; j != null; j = j.Next) { js.Add(j); if (!j.Flags.HasFlag(JOBJ_FLAG.INSTANCE)) W(j.Child); } }
                W(gobjs[g].RootNode);
                var jo = js[jn];
                Console.WriteLine($"joint {g}:{jn} T ({jo.TX}, {jo.TY}) -> ({jo.TX + dx / sc}, {jo.TY + dy / sc})");
                jo.TX += dx / sc; jo.TY += dy / sc;
            }
            else if (a[i] == "--line")
            {
                var q = a[++i].Split(':'); int l = int.Parse(q[0]);
                float dx = float.Parse(q[1], CultureInfo.InvariantCulture), dy = float.Parse(q[2], CultureInfo.InvariantCulture);
                foreach (var v in new[] { lines[l].VertexIndex1, lines[l].VertexIndex2 })
                {
                    Console.WriteLine($"vertex {v} ({verts[v].X}, {verts[v].Y}) -> ({verts[v].X + dx / sc}, {verts[v].Y + dy / sc})");
                    verts[v].X += dx / sc; verts[v].Y += dy / sc;
                }
                // the line group's bounds follow the vertices
                var groups = coll.LineGroups;
                foreach (var gr in groups)
                    if (lines[l].VertexIndex1 >= gr.VertexStart && lines[l].VertexIndex1 < gr.VertexStart + gr.VertexCount)
                    {
                        gr.XMin = Math.Min(gr.XMin, Math.Min(verts[lines[l].VertexIndex1].X, verts[lines[l].VertexIndex2].X));
                        gr.XMax = Math.Max(gr.XMax, Math.Max(verts[lines[l].VertexIndex1].X, verts[lines[l].VertexIndex2].X));
                        gr.YMin = Math.Min(gr.YMin, Math.Min(verts[lines[l].VertexIndex1].Y, verts[lines[l].VertexIndex2].Y));
                        gr.YMax = Math.Max(gr.YMax, Math.Max(verts[lines[l].VertexIndex1].Y, verts[lines[l].VertexIndex2].Y));
                    }
                coll.LineGroups = groups;
            }
        }
        int nv = coll._s.GetInt32(0x04);
        coll.Vertices = verts;
        coll._s.SetInt32(0x04, nv);                    // the setter writes the (padded) array length; keep the file's count
        f.Save(a[2]);
        Console.WriteLine($"wrote {a[2]} ({new FileInfo(a[2]).Length} bytes; in {new FileInfo(a[1]).Length})");
        return 0;
    }

    // how a model group animates (its animation set 0, which the ground code's grAnime_801C8138 attaches): joint tracks,
    // material colour and alpha tracks, texture tracks (UV scroll, image swaps) with their image counts, end frames and
    // loop flags, and the per-set loop flag the ground code reads at +0x28
    static object AnimCensus(SBM_Map_GOBJ mg)
    {
        var jt = new Dictionary<string, int>(); var mt = new Dictionary<string, int>(); var tt = new Dictionary<string, int>();
        var ends = new SortedSet<float>(); int loops = 0, aobjs = 0, animJoints = 0, matAnims = 0, texAnims = 0, images = 0;
        void Aobj(HSD_AOBJ a, Func<byte, string> name, Dictionary<string, int> hist)
        {
            if (a == null) return;
            aobjs++; ends.Add((float)Math.Round(a.EndFrame, 1)); if (a.Flags.HasFlag(AOBJ_Flags.ANIM_LOOP)) loops++;
            for (var f = a.FObjDesc; f != null; f = f.Next) { var k = name(f.TrackType); hist[k] = hist.GetValueOrDefault(k) + 1; }
        }
        var aj = mg.JointAnimations?.Array; var ma = mg.MaterialAnimations?.Array;
        void J(HSD_AnimJoint j) { for (; j != null; j = j.Next) { if (j.AOBJ != null) { animJoints++; Aobj(j.AOBJ, t => ((JointTrackType)t).ToString().Replace("HSD_A_J_", ""), jt); } J(j.Child); } }
        void M(HSD_MatAnimJoint j)
        {
            for (; j != null; j = j.Next)
            {
                for (var m = j.MaterialAnimation; m != null; m = m.Next)
                {
                    matAnims++; Aobj(m.AnimationObject, t => ((MatTrackType)t).ToString().Replace("HSD_A_M_", ""), mt);
                    for (var x = m.TextureAnimation; x != null; x = x.Next)
                    { texAnims++; images += x.ImageBuffers?.Length ?? 0; Aobj(x.AnimationObject, t => ((TexTrackType)t).ToString().Replace("HSD_A_T_", ""), tt); }
                }
                M(j.Child);
            }
        }
        if (aj != null && aj.Length > 0) J(aj[0]);
        if (ma != null && ma.Length > 0) M(ma[0]);
        var setFlags = mg._s.GetReference<HSDAccessor>(0x28);
        return new { anim_sets = Math.Max(aj?.Length ?? 0, ma?.Length ?? 0), animated_joints = animJoints, joint_tracks = jt, mat_anims = matAnims,
                     material_tracks = mt, tex_anims = texAnims, texture_tracks = tt, swap_images = images, aobjs, looping_aobjs = loops,
                     end_frames = ends.ToArray(), set0_loop_flag = setFlags == null ? (int?)null : setFlags._s.GetByte(0) };
    }

    // triangles drawn by a PObj: lists, strips and fans (and quads) from its display list
    static int Tris(HSD_POBJ po)
    {
        int n = 0;
        try
        {
            foreach (var pr in po.ToDisplayList().Primitives)
            {
                int c = pr.Count;
                switch (pr.PrimitiveType)
                {
                    case GXPrimitiveType.Triangles: n += c / 3; break;
                    case GXPrimitiveType.TriangleStrip: case GXPrimitiveType.TriangleFan: n += Math.Max(0, c - 2); break;
                    case GXPrimitiveType.Quads: n += c / 2; break;
                }
            }
        }
        catch { }
        return n;
    }

    static int Count<T>(T first, Func<T, T> next) where T : class { int n = 0; for (var x = first; x != null; x = next(x)) n++; return n; }

    public static int Dump(string[] a)
    {
        string path = a[1], outp = null; int frames = 2400; bool listJoints = false;
        var codeBind = new Dictionary<int, (int g, int j)>();     // --bind C:G:J,... : a stage's code-side collision bindings
        for (int i = 2; i < a.Length; i++)
        {
            if (a[i] == "--anim-frames") frames = int.Parse(a[++i]);
            else if (a[i] == "--joints") listJoints = true;
            else if (a[i] == "--bind") foreach (var t in a[++i].Split(',')) { var q = t.Split(':').Select(int.Parse).ToArray(); codeBind[q[0]] = (q[1], q[2]); }
            else outp = a[i];
        }
        var f = new HSDRawFile(path);
        HSDAccessor Root(string n) => f.Roots.FirstOrDefault(r => r.Name == n)?.Data;
        var gp = Root("grGroundParam") as SBM_GroundParam;
        var head = Root("map_head") as SBM_Map_Head;
        var coll = Root("coll_data") as SBM_Coll_Data;
        float scale = gp?.StageScale ?? 1f;

        // map gobjs
        var gobjs = head?.ModelGroups?.Array ?? Array.Empty<SBM_Map_GOBJ>();
        var gj = new List<List<J>>();
        var gout = new List<object>();
        for (int g = 0; g < gobjs.Length; g++)
        {
            var mg = gobjs[g];
            var anims = mg.JointAnimations?.Array ?? Array.Empty<HSD_AnimJoint>();
            var js = Joints(mg.RootNode, anims.Length > 0 ? anims[0] : null, scale, frames);
            gj.Add(js);
            int dobjs = 0, tex = 0, tris = 0; long texBytes = 0;
            var seenImg = new HashSet<HSDStruct>();
            var modes = new Dictionary<string, int>();     // render mode + vertex attributes + texture formats -> DObjs
            foreach (var j in js) for (var d = j.Jo.Dobj; d != null; d = d.Next)
            {
                dobjs++;
                var at = d.Pobj == null ? "" : string.Join("+", d.Pobj.ToGXAttributes().Where(x => x.AttributeName != GXAttribName.GX_VA_NULL && x.AttributeName != GXAttribName.GX_VA_PNMTXIDX).Select(x => x.AttributeName.ToString().Replace("GX_VA_", "")));
                var tf = new List<string>(); for (var t = d.Mobj?.Textures; t != null; t = t.Next) tf.Add($"{t.ImageData?.Format}:{t.Flags}");
                var mk = $"{d.Mobj?.RenderFlags} | {at} | {string.Join(",", tf)}";
                modes[mk] = modes.GetValueOrDefault(mk) + 1;
                for (var t = d.Mobj?.Textures; t != null; t = t.Next)
                {
                    tex++;
                    if (t.ImageData != null && seenImg.Add(t.ImageData._s)) texBytes += t.ImageData.ImageData?.Length ?? 0;
                }
                for (var po = d.Pobj; po != null; po = po.Next) tris += Tris(po);
            }
            var links = mg.CollisionLinks?.Array ?? Array.Empty<SBM_Map_GOBJ_CollisionLink>();
            gout.Add(new
            {
                index = g, joints = js.Count, dobjs, textures = tex, triangles = tris, texture_bytes = texBytes, render_modes = modes,
                anim_census = AnimCensus(mg),
                joint_anims = anims.Length, mat_anims = mg.MaterialAnimations?.Array?.Length ?? 0,
                shape_anims = mg.ShapeAnimations?.Array?.Length ?? 0, anim_end = anims.Length > 0 ? R(anims[0].AOBJ?.EndFrame ?? 0) : 0,
                animated_joints = js.Count(j => j.Animated),
                camera = mg.Camera != null, lights = mg.Lights?.Array?.Length ?? 0, fog = mg.Fog != null,
                fog_desc = mg.Fog == null ? null : new { type = mg.Fog.Type.ToString(), start = R(mg.Fog.Start), end = R(mg.Fog.End), color = $"#{mg.Fog.Color.R:X2}{mg.Fog.Color.G:X2}{mg.Fog.Color.B:X2}" },
                coll_links = links.Select(l => new[] { (int)l.CollisionIndex, l.UnknownIndex, l.JOBJIndex }).ToArray(),
                root = js.Count > 0 ? new[] { R(js[0].Rest.M41), R(js[0].Rest.M42), R(js[0].Rest.M43) } : null,
                joint_list = !listJoints ? null : js.Select(j => new
                {
                    i = j.Index, parent = j.Parent, rest = new[] { R(j.Rest.M41), R(j.Rest.M42), R(j.Rest.M43) },
                    frame0 = new[] { R(j.Frame0.M41), R(j.Frame0.M42), R(j.Frame0.M43) }, dobjs = Count(j.Jo.Dobj, d => d.Next),
                    flags = ((uint)j.Jo.Flags).ToString("X"), animated = j.Animated,
                    y_range = j.YRange?.Select(R).ToArray(), x_range = j.XRange?.Select(R).ToArray(),
                }).ToArray(),
            });
        }

        // general points
        var pts = new List<object>();
        foreach (var gpnt in head?.GeneralPoints?.Array ?? Array.Empty<SBM_GeneralPoints>())
        {
            int g = Array.FindIndex(gobjs, m => m.RootNode != null && gpnt.JOBJReference != null && m.RootNode._s == gpnt.JOBJReference._s);
            List<J> js = g >= 0 ? gj[g] : Joints(gpnt.JOBJReference, null, scale, frames);
            // the engine reads the count at +8; HSDRaw's array is sized from the (padded) buffer
            foreach (var p in (gpnt.Points ?? Array.Empty<SBM_GeneralPointInfo>()).Take(gpnt._s.GetInt32(0x08)))
            {
                var j = p.JOBJIndex < js.Count ? js[p.JOBJIndex] : null;
                pts.Add(new
                {
                    type = (int)p.Type, name = p.Type.ToString(), gobj = g, joint = (int)p.JOBJIndex,
                    rest = j == null ? null : new[] { R(j.Rest.M41), R(j.Rest.M42), R(j.Rest.M43) },
                    frame0 = j == null ? null : new[] { R(j.Frame0.M41), R(j.Frame0.M42), R(j.Frame0.M43) },
                    moves = j != null && j.YRange != null && (j.YRange[1] - j.YRange[0] > 0.01 || j.XRange[1] - j.XRange[0] > 0.01),
                });
            }
        }

        // collision
        object collOut = null;
        if (coll != null)
        {
            // the engine reads the count fields (MapCollData vert_count +4, line_count +0xC, joint_count +0x28); HSDRaw's
            // arrays are sized from their buffers, which a rewrite pads to 0x20 (26 vertices read back as 28)
            var verts = (coll.Vertices ?? Array.Empty<SBM_CollVertex>()).Take(coll._s.GetInt32(0x04)).ToArray();
            var lines = (coll.Links ?? Array.Empty<SBM_CollLine>()).Take(coll._s.GetInt32(0x0C)).ToArray();
            var groups = (coll.LineGroups ?? Array.Empty<SBM_CollLineGroup>()).Take(coll._s.GetInt32(0x28)).ToArray();
            // group -> (gobj, joint) from the file's links
            var bind = new Dictionary<int, (int g, int j)>();
            for (int g = 0; g < gobjs.Length; g++)
                foreach (var l in gobjs[g].CollisionLinks?.Array ?? Array.Empty<SBM_Map_GOBJ_CollisionLink>())
                    bind[l.CollisionIndex] = (g, l.JOBJIndex);
            foreach (var kv in codeBind) bind[kv.Key] = kv.Value;
            int GroupOfVertex(int v) { for (int i = 0; i < groups.Length; i++) if (v >= groups[i].VertexStart && v < groups[i].VertexStart + groups[i].VertexCount) return i; return -1; }
            Vector2 World(int v, bool f0)
            {
                int g = GroupOfVertex(v);
                var p = new Vector3(verts[v].X, verts[v].Y, 0);
                if (g >= 0 && bind.TryGetValue(g, out var b) && b.g < gj.Count && b.j < gj[b.g].Count)
                {
                    var w = Vector3.Transform(p, f0 ? gj[b.g][b.j].Frame0 : gj[b.g][b.j].Rest);
                    return new Vector2(w.X, w.Y);
                }
                return new Vector2(p.X * scale, p.Y * scale);
            }
            string Kind(int i)
            {
                if (i >= coll.TopLinksOffset && i < coll.TopLinksOffset + coll.TopLinksCount) return "floor";
                if (i >= coll.BottomLinksOffset && i < coll.BottomLinksOffset + coll.BottomLinksCount) return "ceiling";
                if (i >= coll.RightLinksOffset && i < coll.RightLinksOffset + coll.RightLinksCount) return "right_wall";
                if (i >= coll.LeftLinksOffset && i < coll.LeftLinksOffset + coll.LeftLinksCount) return "left_wall";
                if (i >= coll.DynamicLinksOffset && i < coll.DynamicLinksOffset + coll.DynamicLinksCount) return "dynamic";
                return "?";
            }
            collOut = new
            {
                ranges = new
                {
                    floor = new[] { (int)coll.TopLinksOffset, coll.TopLinksCount }, ceiling = new[] { (int)coll.BottomLinksOffset, coll.BottomLinksCount },
                    right_wall = new[] { (int)coll.RightLinksOffset, coll.RightLinksCount }, left_wall = new[] { (int)coll.LeftLinksOffset, coll.LeftLinksCount },
                    dynamic = new[] { (int)coll.DynamicLinksOffset, coll.DynamicLinksCount },
                },
                vertices = verts.Select((v, i) => { var w = World(i, false); var w0 = World(i, true); return new { i, raw = new[] { R(v.X), R(v.Y) }, rest = new[] { R(w.X), R(w.Y) }, frame0 = new[] { R(w0.X), R(w0.Y) }, group = GroupOfVertex(i) }; }).ToArray(),
                lines = lines.Select((l, i) => new
                {
                    i, kind = Kind(i), v = new[] { (int)l.VertexIndex1, l.VertexIndex2 },
                    // HSDRaw names +4 "NextLine" and +6 "PreviousLine"; the engine's MapLine has prev at +4 and next at +6
                    // (BF: floor line 0's +4 is the left wall that ends at its first vertex), so the engine's names here
                    prev = (int)l.NextLine, next = (int)l.PreviousLine, prev_alt = (int)l.NextLineAltGroup, next_alt = (int)l.PreviousLineAltGroup,
                    surface = l.CollisionFlag.ToString(), surface_bits = (int)l.CollisionFlag,
                    drop_through = l.Flag.HasFlag(CollProperty.DropThrough), ledge = l.Flag.HasFlag(CollProperty.LedgeGrab),
                    prop_bits = (int)l.Flag, material = l.Material.ToString(), group = GroupOfVertex(l.VertexIndex1),
                }).ToArray(),
                groups = groups.Select((g, i) => new
                {
                    i, floor = new[] { (int)g.TopLineIndex, g.TopLineCount }, ceiling = new[] { (int)g.BottomLineIndex, g.BottomLineCount },
                    right_wall = new[] { (int)g.RightLineIndex, g.RightLineCount }, left_wall = new[] { (int)g.LeftLineIndex, g.LeftLineCount },
                    dynamic = new[] { (int)g.DynamicLineIndex, g.DynamicLineCount },
                    bounds = new[] { R(g.XMin), R(g.YMin), R(g.XMax), R(g.YMax) }, vertices = new[] { (int)g.VertexStart, g.VertexCount },
                    bound_to = bind.TryGetValue(i, out var b) ? new[] { b.g, b.j } : null,
                    joint_rest = bind.TryGetValue(i, out b) && b.g < gj.Count && b.j < gj[b.g].Count ? new[] { R(gj[b.g][b.j].Rest.M41), R(gj[b.g][b.j].Rest.M42) } : null,
                    joint_animated = bind.TryGetValue(i, out b) && b.g < gj.Count && b.j < gj[b.g].Count && gj[b.g][b.j].YRange != null,
                    joint_y_range = bind.TryGetValue(i, out b) && b.g < gj.Count && b.j < gj[b.g].Count && gj[b.g][b.j].YRange != null ? gj[b.g][b.j].YRange.Select(R).ToArray() : null,
                    joint_x_range = bind.TryGetValue(i, out b) && b.g < gj.Count && b.j < gj[b.g].Count && gj[b.g][b.j].XRange != null ? gj[b.g][b.j].XRange.Select(R).ToArray() : null,
                }).ToArray(),
            };
        }

        object gpOut = null;
        if (gp != null)
        {
            gpOut = new
            {
                scale = R(gp.StageScale), shadow_alpha = gp.ShadowAlpha, fov = gp.FieldOfView, cam_dist_min = gp.CameraDistanceMin,
                cam_dist_max = gp.CameraDistanceMax, tilt_scale = gp.TiltScale, vertical_rotation = R(gp.VerticalRotation),
                horizontal_rotation = R(gp.HorizontalRotation), fixedness = R(gp.Fixedness), bubble_mult = R(gp.BubbleMultiplier),
                cam_speed_smooth = R(gp.CameraSpeedSmoothness), pause_z = new[] { gp.PauseMinZ, gp.PauseInitialZ, gp.PauseMaxZ },
                pause_angles = new[] { R(gp.PauseMaxAngleUp), R(gp.PauseMaxAngleDown), R(gp.PauseMaxAngleLeft), R(gp.PauseMaxAngleRight) },
                fixed_cam = new[] { R(gp.FixedCamX), R(gp.FixedCamY), R(gp.FixedCamZ), R(gp.FixedFieldOfView), R(gp.FixedVerticalAngle), R(gp.FixedHorizontalAngle) },
                item_freq_scale = gp.UnknownShort0,
                stage_params = gp.BGMData.Select(b => new
                {
                    stkind = b.GrKind, bgm = b.MainMusic, bgm_alt = b.AltMusic, bgm_sd = b.SuddenDeathMainMusic, bgm_sd_alt = b.SuddenDeathAltMusic,
                    behaviour = b.SongBehaviorFlag, alt_chance = b.ChanceToPlayAltSong,
                }).ToArray(),
            };
        }

        var extra = f.Roots.Where(r => !r.Name.EndsWith("_image") && !r.Name.EndsWith("_tlut") && !r.Name.EndsWith("_tlut_desc"))
            .Select(r => new { name = r.Name, type = r.Data?.GetType().Name, bytes = r.Data?._s?.Length ?? 0 }).ToArray();
        int images = f.Roots.Count(r => r.Name.EndsWith("_image"));

        var json = JsonSerializer.Serialize(new
        {
            file = Path.GetFileName(path), bytes = new FileInfo(path).Length, scale = R(scale), roots = extra, image_roots = images,
            ground_param = gpOut, gobjs = gout, points = pts, collision = collOut,
            lights = head?.Lights?.Array?.Length ?? 0, splines = head?.SplineDesc?.Array?.Length ?? 0,
        }, new JsonSerializerOptions { WriteIndented = true });
        if (outp != null) File.WriteAllText(outp, json); else Console.WriteLine(json);
        return 0;
    }
}
