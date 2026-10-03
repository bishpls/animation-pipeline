// stage-build SPEC.json TEMPLATE_GrXx.dat OUT.dat : a stage file from a stage spec (projects/geno/stage/stage_spec.py).
// The template (Battlefield's GrNBa.dat) supplies what the spec doesn't: grGroundParam's camera fields and per-StKind row
// layout (item weights), the map lights (map_head, each gobj's light set), the fighters' lights (map_plit), the stage
// camera descs and ALDYakuAll / itemdata / quake_model_set. Everything the spec gives is written fresh:
//   - coll_data: vertices, lines (engine order, prev at +4 and next at +6, surface / property / material), one line group;
//   - the general points: a joint tree (root = 0, one child per point) and its (index, type) list, as map gobj 0;
//   - map gobjs from the spec's faces: one joint, one DObj per colour, flat-shaded lit material colours (RENDER_DIFFUSE,
//     ambient half the diffuse), rigid PObjs (position + normal), drawn both sides; a gobj may carry its own fog;
//   - grGroundParam: stage scale and one per-StKind row (the stage's music), cloned from the template's VS row.
// Dropped from the template: its models and textures, map_ptcl/map_texg (its particle bank) and yakumono_param.
// Verification is stage-dump on the output (the same numbers as the spec) and the director's grdump in game.
using System.Globalization;
using System.Numerics;
using System.Text.Json;
using HSDRaw;
using HSDRaw.Common;
using HSDRaw.Common.Animation;
using HSDRaw.GX;
using HSDRaw.Melee.Gr;
using HSDRaw.Tools;

static class StageBuild
{
    static float F(JsonElement e) => (float)e.GetDouble();

    static void Colour(HSD_Material mt, byte r, byte g, byte b)
    {
        mt.DIF_R = r; mt.DIF_G = g; mt.DIF_B = b; mt.DIF_A = 255;
        mt.AMB_R = (byte)(r / 2); mt.AMB_G = (byte)(g / 2); mt.AMB_B = (byte)(b / 2); mt.AMB_A = 255;
        mt.SPC_R = mt.SPC_G = mt.SPC_B = 0; mt.SPC_A = 255; mt.Alpha = 1; mt.Shininess = 50;
    }

    static readonly Dictionary<string, HSD_Image> imageCache = new();

    // a spec material: {"texture": "file.bgra" (raw BGRA, relative to the spec), "size": [w, h], "format": "CMP"|"RGB565"|"RGB5A3", "color": [r,g,b]
    // (the diffuse tint; ambient half of it), "ambient": [r,g,b], "wrap": "repeat"|"clamp"}
    static HSD_MOBJ Material(JsonElement m, string name, string specPath, HSD_MOBJ tpl, List<string> log)
    {
        byte[] col = m.TryGetProperty("color", out var c) ? c.EnumerateArray().Select(x => (byte)x.GetInt32()).ToArray() : new byte[] { 255, 255, 255 };
        if (!m.TryGetProperty("texture", out var tp))
        {
            var mo0 = new HSD_MOBJ { RenderFlags = RENDER_MODE.DIFFUSE, Material = new HSD_Material() };
            Colour(mo0.Material, col[0], col[1], col[2]);
            return mo0;
        }
        // a single-texture material built from scratch (ArticleModel.cs's TObj settings): lit by default; "vertex": true is
        // the vanilla stages' own mode (VERTEX, TEX0: unlit, the baked vertex colour times the texture); "alpha": "cut" (an
        // alpha test at 128, depth written) or "blend" (translucent, no depth write) for foliage and branch cards
        bool vtx = m.TryGetProperty("vertex", out var vt) && vt.GetBoolean();
        var alpha = m.TryGetProperty("alpha", out var alp) ? alp.GetString() : null;
        var mo = new HSD_MOBJ { RenderFlags = (vtx ? RENDER_MODE.VERTEX : RENDER_MODE.DIFFUSE) | RENDER_MODE.TEX0, Material = new HSD_Material() };
        Colour(mo.Material, col[0], col[1], col[2]);
        if (vtx) { mo.Material.DIF_R = mo.Material.DIF_G = mo.Material.DIF_B = 255; mo.Material.AMB_R = mo.Material.AMB_G = mo.Material.AMB_B = 255; }
        if (alpha == "blend" || alpha == "add") mo.RenderFlags |= RENDER_MODE.XLU | RENDER_MODE.NO_ZUPDATE;
        if (m.TryGetProperty("alpha_mat", out var amt) && amt.GetBoolean()) mo.RenderFlags |= RENDER_MODE.ALPHA_MAT;   // alpha from the (animated) material
        if (alpha != null)
            mo.PEDesc = new HSD_PEDesc
            {
                Flags = PIXEL_PROCESS_ENABLE.COLOR_UPDATE | PIXEL_PROCESS_ENABLE.COMPARE | (alpha == "cut" ? PIXEL_PROCESS_ENABLE.ZUPDATE : 0),
                AlphaRef0 = (byte)(alpha == "cut" ? 128 : 8), AlphaRef1 = 0,
                BlendMode = alpha == "cut" ? GXBlendMode.GX_NONE : GXBlendMode.GX_BLEND,
                SrcFactor = alpha == "cut" ? GXBlendFactor.GX_BL_ONE : GXBlendFactor.GX_BL_SRCALPHA,
                DstFactor = alpha == "cut" ? GXBlendFactor.GX_BL_ZERO : alpha == "add" ? GXBlendFactor.GX_BL_ONE : GXBlendFactor.GX_BL_INVSRCALPHA,
                BlendOp = GXLogicOp.GX_LO_NOOP, DepthFunction = GXCompareType.LEqual,
                AlphaComp0 = GXCompareType.GEqual, AlphaOp = GXAlphaOp.And, AlphaComp1 = GXCompareType.Always
            };
        mo.Textures = new HSD_TOBJ
        {
            MagFilter = GXTexFilter.GX_LINEAR,
            Flags = TOBJ_FLAGS.COORD_UV | TOBJ_FLAGS.LIGHTMAP_DIFFUSE | TOBJ_FLAGS.COLORMAP_MODULATE | (alpha != null ? TOBJ_FLAGS.ALPHAMAP_MODULATE : 0),
            RepeatS = 1, RepeatT = 1, SX = 1, SY = 1, SZ = 1, GXTexGenSrc = GXTexGenSrc.GX_TG_TEX0, Blending = 1
        };
        if (!vtx && m.TryGetProperty("ambient", out var am)) { var q = am.EnumerateArray().Select(x => (byte)x.GetInt32()).ToArray(); mo.Material.AMB_R = q[0]; mo.Material.AMB_G = q[1]; mo.Material.AMB_B = q[2]; }
        var path = Path.Combine(Path.GetDirectoryName(Path.GetFullPath(specPath)), tp.GetString());
        var fmt = m.TryGetProperty("format", out var ff) ? Enum.Parse<GXTexFmt>(ff.GetString()) : GXTexFmt.CMP;
        var t = mo.Textures; t.Next = null;
        if (!imageCache.TryGetValue(path + fmt, out var img))
        {
            var sz = m.GetProperty("size"); int w = sz[0].GetInt32(), h = sz[1].GetInt32();
            var bgra = TexKit.Bgra(path, w, h);                       // raw BGRA, as the menu art is written
            var tmp = new HSD_TOBJ();
            tmp.EncodeImageData(bgra, w, h, fmt, GXTlutFmt.RGB565);
            img = tmp.ImageData; imageCache[path + fmt] = img;
            log.Add($"  texture {Path.GetFileName(path)} {w}x{h} {fmt} {img.ImageData.Length} bytes");
        }
        t.ImageData = img; t.TlutData = null;
        // "repeat" | "clamp" | "u" (repeat across, clamp down: a strip card, whose top edge would otherwise filter in its
        // bottom row; the treeline's top showed as a dark line)
        var ws = m.TryGetProperty("wrap", out var wr) ? wr.GetString() : "repeat";
        t.WrapS = ws == "clamp" ? GXWrapMode.CLAMP : GXWrapMode.REPEAT;
        t.WrapT = ws == "repeat" ? GXWrapMode.REPEAT : GXWrapMode.CLAMP; t.RepeatS = 1; t.RepeatT = 1; t.SX = 1; t.SY = 1; t.SZ = 1; t.TX = 0; t.TY = 0; t.TZ = 0; t.RX = 0; t.RY = 0; t.RZ = 0;
        return mo;
    }

    // A gobj's animation set 0, as the vanilla stages' backgrounds carry theirs (grAnime_801C8138 attaches set 0 to the
    // model group's root joint and loops it by the set flag at +0x28). spec "anims":
    //   "joints":    {name: [{"type": "TRAX", "keys": [[frame, value], ...], "end": E, "interp": "lin"|"con"|"spl"}]}
    //   "materials": [{"joint": name, "material": m, "tracks": [... "type": "ALPHA" (material) | "TRAU"/"TRAV" (texture)]}]
    // The trees mirror the joints (the root, the mesh joint, its children in order) and each joint's DObjs in order.
    static void Animate(SBM_Map_GOBJ mg, JsonElement an, List<string> jointNames, Dictionary<string, List<string>> dobjOrder, List<string> log)
    {
        static float Fv(JsonElement e) => (float)e.GetDouble();
        HSD_AOBJ Aobj(IEnumerable<JsonElement> tracks, Func<string, byte> type)
        {
            var ts = tracks.ToList(); if (ts.Count == 0) return null;
            var ao = new HSD_AOBJ { EndFrame = ts.Max(t => Fv(t.GetProperty("end"))), Flags = AOBJ_Flags.ANIM_LOOP };
            foreach (var t in ts)
            {
                var ip = t.TryGetProperty("interp", out var ipe) ? ipe.GetString() : "lin";
                var it = ip == "con" ? GXInterpolationType.HSD_A_OP_CON : ip == "spl" ? GXInterpolationType.HSD_A_OP_SPL0 : GXInterpolationType.HSD_A_OP_LIN;
                var keys = t.GetProperty("keys").EnumerateArray().Select(k => new FOBJKey { Frame = Fv(k[0]), Value = Fv(k[1]), InterpolationType = it }).ToList();
                ao.AddTrack(type(t.GetProperty("type").GetString()), keys);
            }
            return ao;
        }
        var ajs = new List<HSD_AnimJoint>(); var mjs = new List<HSD_MatAnimJoint>();
        var jt = an.TryGetProperty("joints", out var jte) ? jte : default;
        var mats = an.TryGetProperty("materials", out var mte) ? mte.EnumerateArray().ToList() : new List<JsonElement>();
        int njt = 0, nmt = 0, ntt = 0;
        foreach (var jn in jointNames)
        {
            var aj = new HSD_AnimJoint();
            if (jt.ValueKind == JsonValueKind.Object && jt.TryGetProperty(jn, out var tr))
            { aj.AOBJ = Aobj(tr.EnumerateArray(), s => (byte)Enum.Parse<JointTrackType>("HSD_A_J_" + s)); njt++; }
            ajs.Add(aj);
            var mj = new HSD_MatAnimJoint();
            foreach (var mk in dobjOrder[jn])
            {
                var ma = new HSD_MatAnim();
                var spec = mats.FirstOrDefault(m => m.GetProperty("material").GetString() == mk && (m.TryGetProperty("joint", out var mjn) ? mjn.GetString() : "mesh") == jn);
                if (spec.ValueKind == JsonValueKind.Object)
                {
                    var tracks = spec.GetProperty("tracks").EnumerateArray().ToList();
                    bool IsTex(JsonElement t) => Enum.TryParse<TexTrackType>("HSD_A_T_" + t.GetProperty("type").GetString(), out _);
                    ma.AnimationObject = Aobj(tracks.Where(t => !IsTex(t)), s => (byte)Enum.Parse<MatTrackType>("HSD_A_M_" + s));
                    var texAo = Aobj(tracks.Where(IsTex), s => (byte)Enum.Parse<TexTrackType>("HSD_A_T_" + s));
                    if (texAo != null) { ma.TextureAnimation = new HSD_TexAnim { GXTexMapID = GXTexMapID.GX_TEXMAP0, AnimationObject = texAo }; ntt++; }
                    if (ma.AnimationObject != null) nmt++;
                }
                if (mj.MaterialAnimation == null) mj.MaterialAnimation = ma; else mj.MaterialAnimation.Add(ma);
            }
            mjs.Add(mj);
        }
        for (int k = 1; k < jointNames.Count; k++) { ajs[0].AddChild(ajs[k]); mjs[0].AddChild(mjs[k]); }
        // the trees mirror the model group's own root: the ground code loads it under a wrapper joint and attaches set 0
        // at the wrapper's child, which is this root (the mesh joint is its child); one level off, a child's animation
        // lands on the mesh joint (the shooting star's scale 0 hid the whole group)
        var ajRoot = new HSD_AnimJoint(); ajRoot.AddChild(ajs[0]);
        var mjRoot = new HSD_MatAnimJoint(); mjRoot.AddChild(mjs[0]);
        mg.JointAnimations = new HSDNullPointerArrayAccessor<HSD_AnimJoint> { Array = new[] { ajRoot } };
        mg.MaterialAnimations = new HSDNullPointerArrayAccessor<HSD_MatAnimJoint> { Array = new[] { mjRoot } };
        mg._s.SetReferenceStruct(0x28, new HSDStruct(new byte[] { 1, 0, 0, 0 }));      // set 0 loops (grAnime_801C8138)
        log.Add($"  anims: {njt} joints, {nmt} material, {ntt} texture tracks sets; set 0 loops");
    }

    public static int Run(string[] a)
    {
        if (a.Length < 4) { Console.Error.WriteLine("usage: stage-build SPEC.json TEMPLATE.dat OUT.dat"); return 2; }
        var spec = JsonDocument.Parse(File.ReadAllText(a[1])).RootElement;
        var f = new HSDRawFile(a[2]);
        HSDAccessor Root(string n) => f.Roots.FirstOrDefault(r => r.Name == n)?.Data;
        var gp = Root("grGroundParam") as SBM_GroundParam;
        var head = Root("map_head") as SBM_Map_Head;
        float scale = F(spec.GetProperty("scale"));
        var log = new List<string>();

        // ---- collision
        var cs = spec.GetProperty("collision");
        var verts = cs.GetProperty("vertices").EnumerateArray().Select(v => new SBM_CollVertex { X = F(v[0]) / scale, Y = F(v[1]) / scale }).ToArray();
        var lines = new List<SBM_CollLine>();
        foreach (var l in cs.GetProperty("lines").EnumerateArray())
        {
            var v = l.GetProperty("v");
            var cl = new SBM_CollLine
            {
                VertexIndex1 = (short)v[0].GetInt32(), VertexIndex2 = (short)v[1].GetInt32(),
                NextLine = (short)l.GetProperty("prev").GetInt32(),          // +4: the engine's prev_id0 (HSDRaw's name is swapped)
                PreviousLine = (short)l.GetProperty("next").GetInt32(),      // +6: next_id0
                NextLineAltGroup = -1, PreviousLineAltGroup = -1,
                CollisionFlag = (CollPhysics)l.GetProperty("surface").GetInt32(),
                Flag = (l.GetProperty("drop").GetBoolean() ? CollProperty.DropThrough : 0) | (l.GetProperty("ledge").GetBoolean() ? CollProperty.LedgeGrab : 0),
                Material = (CollMaterial)l.GetProperty("material").GetInt32(),
            };
            lines.Add(cl);
        }
        var g = cs.GetProperty("group"); var rg = g.GetProperty("ranges"); var bd = g.GetProperty("bounds");
        short S(JsonElement e, int i) => (short)e[i].GetInt32();
        var grp = new SBM_CollLineGroup
        {
            TopLineIndex = S(rg.GetProperty("floor"), 0), TopLineCount = S(rg.GetProperty("floor"), 1),
            BottomLineIndex = S(rg.GetProperty("ceiling"), 0), BottomLineCount = S(rg.GetProperty("ceiling"), 1),
            RightLineIndex = S(rg.GetProperty("right_wall"), 0), RightLineCount = S(rg.GetProperty("right_wall"), 1),
            LeftLineIndex = S(rg.GetProperty("left_wall"), 0), LeftLineCount = S(rg.GetProperty("left_wall"), 1),
            DynamicLineIndex = 0, DynamicLineCount = 0,
            XMin = F(bd[0]) / scale, YMin = F(bd[1]) / scale, XMax = F(bd[2]) / scale, YMax = F(bd[3]) / scale,
            VertexStart = S(g.GetProperty("vertices"), 0), VertexCount = S(g.GetProperty("vertices"), 1),
        };
        var coll = new SBM_Coll_Data();
        coll.Vertices = verts; coll.Links = lines.ToArray(); coll.LineGroups = new[] { grp };
        coll._s.SetInt32(0x04, verts.Length); coll._s.SetInt32(0x0C, lines.Count); coll._s.SetInt32(0x28, 1);
        coll.TopLinksOffset = grp.TopLineIndex; coll.TopLinksCount = grp.TopLineCount;
        coll.BottomLinksOffset = grp.BottomLineIndex; coll.BottomLinksCount = grp.BottomLineCount;
        coll.RightLinksOffset = grp.RightLineIndex; coll.RightLinksCount = grp.RightLineCount;
        coll.LeftLinksOffset = grp.LeftLineIndex; coll.LeftLinksCount = grp.LeftLineCount;
        coll.DynamicLinksOffset = 0; coll.DynamicLinksCount = 0;
        log.Add($"collision: {verts.Length} vertices, {lines.Count} lines (floor {grp.TopLineCount}, ceiling {grp.BottomLineCount}, right {grp.RightLineCount}, left {grp.LeftLineCount})");

        // ---- map gobjs
        var tplGobjs = head.ModelGroups.Array;
        var tplStage = tplGobjs[tplGobjs.Length - 1];               // Battlefield's play plane: its lights and camera
        var gobjs = new List<SBM_Map_GOBJ>();
        var materials = new Dictionary<string, JsonElement>();
        if (spec.TryGetProperty("materials", out var mats)) foreach (var m in mats.EnumerateObject()) materials[m.Name] = m.Value;
        // a textured, lit template material from the template file (DIFFUSE | TEX0, one texture): its TObj settings
        HSD_MOBJ texTemplate = null;
        foreach (var tg in tplGobjs)
        {
            void Find(HSD_JOBJ j) { for (; j != null && texTemplate == null; j = j.Next) { for (var d = j.Dobj; d != null && texTemplate == null; d = d.Next) if (d.Mobj != null && d.Mobj.RenderFlags.HasFlag(RENDER_MODE.DIFFUSE) && d.Mobj.RenderFlags.HasFlag(RENDER_MODE.TEX0) && !d.Mobj.RenderFlags.HasFlag(RENDER_MODE.XLU) && d.Mobj.Textures != null && d.Mobj.Textures.Next == null && d.Mobj.Textures.ImageData?.Format != GXTexFmt.CI8) texTemplate = d.Mobj; Find(j.Child); } }
            Find(tg.RootNode);
        }
        HSD_JOBJ pointsRoot = null;
        SBM_GeneralPointInfo[] pointInfo = null;
        foreach (var go in spec.GetProperty("gobjs").EnumerateArray())
        {
            var kind = go.GetProperty("kind").GetString();
            var mg = new SBM_Map_GOBJ { Camera = tplStage.Camera, Lights = tplStage.Lights };
            if (kind == "points")
            {
                pointsRoot = new HSD_JOBJ { Flags = JOBJ_FLAG.CLASSICAL_SCALING, SX = 1, SY = 1, SZ = 1 };
                var infos = new List<SBM_GeneralPointInfo>(); HSD_JOBJ prev = null; short idx = 1;
                foreach (var p in spec.GetProperty("points").EnumerateArray())
                {
                    var j = new HSD_JOBJ { Flags = JOBJ_FLAG.CLASSICAL_SCALING, SX = 1, SY = 1, SZ = 1, TX = F(p.GetProperty("x")) / scale, TY = F(p.GetProperty("y")) / scale };
                    if (prev == null) pointsRoot.Child = j; else prev.Next = j;
                    prev = j;
                    infos.Add(new SBM_GeneralPointInfo { JOBJIndex = idx++, Type = (PointType)p.GetProperty("type").GetInt32() });
                }
                pointInfo = infos.ToArray();
                mg.RootNode = pointsRoot;
                log.Add($"gobj {gobjs.Count}: {infos.Count} general points");
            }
            else
            {
                var root = new HSD_JOBJ { Flags = JOBJ_FLAG.CLASSICAL_SCALING, SX = 1, SY = 1, SZ = 1 };
                var mesh = new HSD_JOBJ { Flags = JOBJ_FLAG.CLASSICAL_SCALING | JOBJ_FLAG.LIGHTING | JOBJ_FLAG.OPA, SX = 1, SY = 1, SZ = 1 };
                root.Child = mesh;
                // child joints of the mesh joint (a gobj's "joints": [{name, t}]), for parts that move on their own; a face
                // naming one is placed in its space (its translation taken out). "mesh" is the mesh joint itself
                var jointNames = new List<string> { "mesh" };
                var jobjs = new Dictionary<string, HSD_JOBJ> { ["mesh"] = mesh };
                var jointT = new Dictionary<string, GXVector3> { ["mesh"] = new GXVector3(0, 0, 0) };
                if (go.TryGetProperty("joints", out var jlist))
                    foreach (var je in jlist.EnumerateArray())
                    {
                        var nm = je.GetProperty("name").GetString(); var tt = je.GetProperty("t");
                        var cj = new HSD_JOBJ { Flags = JOBJ_FLAG.CLASSICAL_SCALING, SX = 1, SY = 1, SZ = 1, TX = F(tt[0]) / scale, TY = F(tt[1]) / scale, TZ = F(tt[2]) / scale };
                        mesh.AddChild(cj);
                        jointNames.Add(nm); jobjs[nm] = cj; jointT[nm] = new GXVector3(cj.TX, cj.TY, cj.TZ);
                    }
                // one DObj per (joint, material): faces carry per-vertex uv, colours and (when given) normals
                var byMat = new Dictionary<(string j, string k), (List<GX_Vertex> v, bool tex)>();
                int tris = 0;
                foreach (var face in go.GetProperty("faces").EnumerateArray())
                {
                    string key; bool tex = false;
                    if (face.TryGetProperty("material", out var mn)) { key = "m:" + mn.GetString(); tex = materials.ContainsKey(mn.GetString()) && materials[mn.GetString()].TryGetProperty("texture", out _); }
                    else { var c = face.GetProperty("color"); key = $"{c[0].GetInt32()},{c[1].GetInt32()},{c[2].GetInt32()}"; }
                    var jn = face.TryGetProperty("joint", out var fj) ? fj.GetString() : "mesh";
                    var o = jointT[jn];
                    var nv = new GXVector3(0, 1, 0);
                    if (face.TryGetProperty("normal", out var n)) nv = new GXVector3(F(n[0]), F(n[1]), F(n[2]));
                    bool hasUV = face.TryGetProperty("uv", out var uvs), hasN = face.TryGetProperty("normals", out var nrms);
                    bool hasC = face.TryGetProperty("colors", out var cols);     // per-vertex colour, 0-255 (baked light)
                    if (!byMat.TryGetValue((jn, key), out var entry)) byMat[(jn, key)] = entry = (new List<GX_Vertex>(), tex);
                    int ti = 0;
                    foreach (var t in face.GetProperty("tris").EnumerateArray())
                    {
                        int vi = 0;
                        foreach (var p in t.EnumerateArray())
                        {
                            var vx = new GX_Vertex { POS = new GXVector3(F(p[0]) / scale - o.X, F(p[1]) / scale - o.Y, F(p[2]) / scale - o.Z), NRM = nv };
                            if (hasN) { var q = nrms[ti][vi]; vx.NRM = new GXVector3(F(q[0]), F(q[1]), F(q[2])); }
                            if (hasUV) { var q = uvs[ti][vi]; vx.TEX0 = new GXVector2(F(q[0]), F(q[1])); }
                            if (hasC) { var q = cols[ti][vi]; vx.CLR0 = new GXColor4(F(q[0]) / 255f, F(q[1]) / 255f, F(q[2]) / 255f, q.GetArrayLength() > 3 ? F(q[3]) / 255f : 1f); }
                            entry.v.Add(vx); vi++;
                        }
                        tris++; ti++;
                    }
                }
                var dobjOrder = new Dictionary<string, List<string>>();     // joint -> its DObjs' material keys, in order
                foreach (var jn in jointNames) dobjOrder[jn] = new List<string>();
                foreach (var ((jn, key), (list, tex)) in byMat)
                {
                    HSD_MOBJ mo;
                    if (key.StartsWith("m:")) mo = Material(materials[key.Substring(2)], key.Substring(2), a[1], texTemplate, log);
                    else
                    {
                        var rgb = key.Split(',').Select(byte.Parse).ToArray();
                        mo = new HSD_MOBJ { RenderFlags = RENDER_MODE.DIFFUSE, Material = new HSD_Material() };
                        Colour(mo.Material, rgb[0], rgb[1], rgb[2]);
                    }
                    bool vtxMat = key.StartsWith("m:") && materials[key.Substring(2)].TryGetProperty("vertex", out var vv) && vv.GetBoolean();
                    var attrs = vtxMat ? new[] { GXAttribName.GX_VA_POS, GXAttribName.GX_VA_CLR0, GXAttribName.GX_VA_TEX0 }
                              : tex ? new[] { GXAttribName.GX_VA_POS, GXAttribName.GX_VA_NRM, GXAttribName.GX_VA_TEX0 } : new[] { GXAttribName.GX_VA_POS, GXAttribName.GX_VA_NRM };
                    var gen = new POBJ_Generator { CullMode = GenCullMode.None, VertexColorFormat = (GXCompType)GXCompTypeClr.RGBA8 };
                    var po = gen.CreatePOBJsFromTriangleList(list, attrs, null, null);
                    gen.SaveChanges();
                    var d = new HSD_DOBJ { Mobj = mo, Pobj = po };
                    var jj = jobjs[jn];
                    if (jj.Dobj == null) jj.Dobj = d; else jj.Dobj.Add(d);
                    dobjOrder[jn].Add(key.StartsWith("m:") ? key.Substring(2) : key);
                }
                root.UpdateFlags();
                mg.RootNode = root;
                if (go.TryGetProperty("anims", out var an)) Animate(mg, an, jointNames, dobjOrder, log);
                if (go.TryGetProperty("fog", out var fog))
                {
                    var fd = HSDAccessor.DeepClone<HSD_FogDesc>(tplGobjs.First(x => x.Fog != null).Fog);
                    fd.Start = F(fog.GetProperty("start")); fd.End = F(fog.GetProperty("end"));
                    var fc = fog.GetProperty("color");
                    fd.Color = System.Drawing.Color.FromArgb(255, fc[0].GetInt32(), fc[1].GetInt32(), fc[2].GetInt32());
                    mg.Fog = fd;
                }
                log.Add($"gobj {gobjs.Count} ({kind}): {byMat.Count} DObjs, {tris} triangles{(mg.Fog != null ? ", fog" : "")}");
            }
            gobjs.Add(mg);
        }
        head.ModelGroups = new HSDArrayAccessor<SBM_Map_GOBJ> { Array = gobjs.ToArray() };
        var gpts = new SBM_GeneralPoints { JOBJReference = pointsRoot };
        gpts.Points = pointInfo;
        head.GeneralPoints = new HSDArrayAccessor<SBM_GeneralPoints> { Array = new[] { gpts } };

        // ---- grGroundParam
        gp.StageScale = scale;
        var sp = spec.GetProperty("stage_param");
        var vsRow = gp.BGMData.First(b => b.GrKind < 0x21);          // the template's VS row: item weights and layout
        var row = HSDAccessor.DeepClone<SBM_GroundBGM>(vsRow);
        row.GrKind = sp.GetProperty("st_kind").GetInt32();           // HSDRaw's name; the engine's StageParam.stkind
        row.MainMusic = sp.GetProperty("bgm").GetInt32(); row.AltMusic = sp.GetProperty("bgm_alt").GetInt32();
        row.SuddenDeathMainMusic = sp.GetProperty("bgm_sd").GetInt32(); row.SuddenDeathAltMusic = sp.GetProperty("bgm_sd_alt").GetInt32();
        row.SongBehaviorFlag = (short)sp.GetProperty("behaviour").GetInt32(); row.ChanceToPlayAltSong = (short)sp.GetProperty("alt_chance").GetInt32();
        gp.BGMData = new[] { row };
        log.Add($"grGroundParam: scale {scale}, one stage row (StKind 0x{row.GrKind:X}, music {row.MainMusic})");

        // ---- roots
        var coll0 = f.Roots.First(r => r.Name == "coll_data"); coll0.Data = coll;
        var drop = new HashSet<string> { "map_ptcl", "map_texg", "yakumono_param" };
        f.Roots.RemoveAll(r => drop.Contains(r.Name) || r.Name.EndsWith("_image") || r.Name.EndsWith("_tlut") || r.Name.EndsWith("_tlut_desc"));
        f.Save(a[3]);
        foreach (var s in log) Console.WriteLine(s);
        Console.WriteLine($"wrote {a[3]} ({new FileInfo(a[3]).Length} bytes); roots {string.Join(", ", f.Roots.Select(r => r.Name))}");
        return 0;
    }
}
