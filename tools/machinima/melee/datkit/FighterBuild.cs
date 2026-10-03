// fighter-build: assemble a new fighter's three files from a rig and an animation set (JSON from projects/<film>/rig/).
//   datkit fighter-build RIG.json ANIMS.json TEMPLATE_PlXx.dat PlCo.dat OUTDIR CODE NAME TEMPLATE_KIND
//   -> OUTDIR/Pl{CODE}Nr.dat  the model: the rig's joints (inverse binds set) and one single-bound mesh per colour on the root
//      OUTDIR/Pl{CODE}AJ.dat  the animations: one figatree archive per animation, 0x20-aligned, as the game's AJ files are
//      OUTDIR/Pl{CODE}.dat    the fighter data: ftData{NAME}, the rig's attributes, hurtboxes, engine bones, IK, model parts,
//                             visibility lookups and an action table pointing at the new animations
// The template supplies the parts of the fighter data this rig doesn't author yet (move scripts, articles, sounds, demo
// actions). Hitbox and effect bones in its move scripts are remapped to the new skeleton through the two parts tables, so
// a scripted hit lands on the equivalent body part. Every other bone reference comes from the rig.
using System.Numerics;
using System.Text.Json;
using HSDRaw;
using HSDRaw.Common;
using HSDRaw.Common.Animation;
using HSDRaw.GX;
using HSDRaw.Melee.Pl;
using HSDRaw.Tools;

static class FighterBuild
{
    public static int Run(string[] a)
    {
        var rig = JsonDocument.Parse(File.ReadAllText(a[1])).RootElement;
        var anims = JsonDocument.Parse(File.ReadAllText(a[2])).RootElement;
        string template = a[3], plco = a[4], outDir = a[5], code = a[6], name = a[7];
        int templateKind = int.Parse(a[8]);
        Directory.CreateDirectory(outDir);
        string model = $"Ply{name}5K_Share";

        // the model: the rig's skeleton, and either the rig's blocks or (rig.json "model") a skinned, textured glTF
        List<HSD_JOBJ> J; List<Matrix4x4> W; int nd; GltfModel.Result imp = null; HSD_JOBJ metalRoot = null;
        if (rig.TryGetProperty("model", out var modelSpec) && modelSpec.ValueKind == JsonValueKind.Object)
        {
            (J, W) = BuildSkeleton(rig);
            var names = rig.GetProperty("joints").EnumerateArray().Select(j => j.GetProperty("name").GetString()).ToList();
            var (MJ, MW) = BuildSkeleton(rig);              // the metal model's own copy (the engine maps it onto the main joints)
            var sp = GltfModel.Spec.From(rig, modelSpec, Path.GetDirectoryName(Path.GetFullPath(a[1])));
            string tnr = modelSpec.TryGetProperty("template", out var te) ? te.GetString()
                       : Path.Combine(Path.GetDirectoryName(template)!, Path.GetFileNameWithoutExtension(template) + "Nr.dat");
            imp = GltfModel.Import(sp, new GltfModel.Skel { J = J, W = W, Names = names }, new GltfModel.Skel { J = MJ, W = MW, Names = names }, tnr, template);
            nd = imp.Dobjs.Count; metalRoot = MJ[0];
            File.WriteAllLines(Path.Combine(outDir, $"Pl{code}Nr.import.txt"), imp.Log);
            foreach (var l in imp.Log) Console.WriteLine(l);
        }
        else { var bm = BuildModel(rig); J = bm.J; W = bm.W; nd = bm.nd; }
        var nr = new HSDRawFile();
        var matanim = imp?.MatAnim ?? MatAnimTree(J[0]);
        nr.Roots.Add(new HSDRootNode { Name = model + "_joint", Data = J[0] });
        nr.Roots.Add(new HSDRootNode { Name = model + "_matanim_joint", Data = matanim });
        int aligned = AlignModel(J[0], matanim);
        nr.Save(Path.Combine(outDir, $"Pl{code}Nr.dat"));
        int costumes = 1 + GltfModel.Costumes(rig, imp != null ? modelSpec : default, Path.GetDirectoryName(Path.GetFullPath(a[1])), imp, outDir, code, model,
            Path.Combine(Path.GetDirectoryName(template)!, Path.GetFileNameWithoutExtension(template) + "Nr.dat"), template);

        // ---- animations
        string prefix = anims.GetProperty("prefix").GetString().Replace("PlyGeno5K", $"Ply{name}5K");
        var chunks = new List<(string sym, byte[] data)>();
        var offsets = new Dictionary<string, (int off, int size)>();
        foreach (var an in anims.GetProperty("anims").EnumerateObject())
        {
            string sym = prefix + an.Name + "_figatree";
            var figa = new HSD_FigaTree { Type = 1, FrameCount = an.Value.GetProperty("frames").GetInt32() };
            var nodes = new List<FigaTreeNode>();
            var tracks = an.Value.GetProperty("tracks");
            for (int ji = 0; ji < J.Count; ji++)
            {
                var node = new FigaTreeNode();
                if (tracks.TryGetProperty(ji.ToString(), out var tj))
                {
                    AddTracks(node, tj.GetProperty("r"), new[] { JointTrackType.HSD_A_J_ROTX, JointTrackType.HSD_A_J_ROTY, JointTrackType.HSD_A_J_ROTZ });
                    AddTracks(node, tj.GetProperty("t"), new[] { JointTrackType.HSD_A_J_TRAX, JointTrackType.HSD_A_J_TRAY, JointTrackType.HSD_A_J_TRAZ });
                    // "s": a limb grown on its hit frames (anims.Pose.grow), linear keys as the cast's scale tracks mostly are
                    if (tj.TryGetProperty("s", out var sj)) AddTracks(node, sj, Scale);
                }
                nodes.Add(node);
            }
            figa.Nodes = nodes;
            var af = new HSDRawFile(); af.Roots.Add(new HSDRootNode { Name = sym, Data = figa });
            using var ms = new MemoryStream(); af.Save(ms);
            chunks.Add((sym, ms.ToArray()));
        }
        // anims.json "passthrough": {action: {sym, off, size}}: the template's own animation, copied byte for byte from its AJ file
        // (next to TEMPLATE_PlXx.dat) under its own symbol and flags. The throw victims' animations (PlyTaro, kind 0x21) are
        // keyed to the shared skeleton any fighter can play, not to this fighter's joints. An entry may instead name another
        // AJ file ("file": a cast member's victim animation, under its own symbol), or carry its own keys ("frames", "nodes",
        // "tracks": {node: {"r": [[frame, x, y, z], ...], "t": ...}}, either channel set optional): an animation authored on
        // that shared layout (the engine applies only rotations to its limbs, translations too to TopN..HipN).
        var pass = new Dictionary<string, string>();
        if (anims.TryGetProperty("passthrough", out var pj))
        {
            var tajPath = Path.Combine(Path.GetDirectoryName(template)!, Path.GetFileNameWithoutExtension(template) + "AJ.dat");
            var taj = File.ReadAllBytes(tajPath);
            foreach (var p in pj.EnumerateObject())
            {
                string sym = p.Value.GetProperty("sym").GetString();
                if (p.Value.TryGetProperty("tracks", out var ptr))
                {
                    var figa = new HSD_FigaTree { Type = 1, FrameCount = p.Value.GetProperty("frames").GetInt32() };
                    var nodes = new List<FigaTreeNode>();
                    for (int ni = 0; ni < p.Value.GetProperty("nodes").GetInt32(); ni++)
                    {
                        var node = new FigaTreeNode();
                        if (ptr.TryGetProperty(ni.ToString(), out var tj))
                        {
                            if (tj.TryGetProperty("r", out var rj)) AddTracks(node, rj, new[] { JointTrackType.HSD_A_J_ROTX, JointTrackType.HSD_A_J_ROTY, JointTrackType.HSD_A_J_ROTZ });
                            if (tj.TryGetProperty("t", out var tk)) AddTracks(node, tk, new[] { JointTrackType.HSD_A_J_TRAX, JointTrackType.HSD_A_J_TRAY, JointTrackType.HSD_A_J_TRAZ });
                            if (tj.TryGetProperty("s", out var sk)) AddTracks(node, sk, Scale);
                        }
                        nodes.Add(node);
                    }
                    figa.Nodes = nodes;
                    var af = new HSDRawFile(); af.Roots.Add(new HSDRootNode { Name = sym, Data = figa });
                    using var ms = new MemoryStream(); af.Save(ms);
                    chunks.Add((sym, ms.ToArray()));
                }
                else
                {
                    int off = p.Value.GetProperty("off").GetInt32(), size = p.Value.GetProperty("size").GetInt32();
                    var src = p.Value.TryGetProperty("file", out var fj) ? File.ReadAllBytes(fj.GetString()!) : taj;
                    chunks.Add((sym, src.AsSpan(off, size).ToArray()));
                }
                pass[p.Name] = sym;
            }
            Console.WriteLine($"fighter-build: {pass.Count} template animations passed through ({string.Join(", ", pass.Keys)})");
        }
        using (var aj = new MemoryStream())
        {
            foreach (var (sym, data) in chunks)
            {
                offsets[sym] = ((int)aj.Position, data.Length);
                aj.Write(data);
                while (aj.Position % 0x20 != 0) aj.WriteByte(0xFF);
            }
            File.WriteAllBytes(Path.Combine(outDir, $"Pl{code}AJ.dat"), aj.ToArray());
        }

        // ---- fighter data, from the template
        var ftf = new HSDRawFile(template);
        var root = ftf.Roots.First(r => r.Name.StartsWith("ftData"));
        root.Name = "ftData" + name;
        var ft = new SBM_FighterData { _s = root.Data._s };
        var at = ft.Attributes;
        foreach (var kv in rig.GetProperty("attributes").EnumerateObject())
        {
            var pr = at.GetType().GetProperty(kv.Name) ?? throw new Exception("no attribute " + kv.Name);
            pr.SetValue(at, pr.PropertyType == typeof(int) ? kv.Value.GetInt32()
                : pr.PropertyType.IsEnum ? Enum.ToObject(pr.PropertyType, kv.Value.GetInt32())   // flags (WeightIndependentThrows)
                : (object)(float)kv.Value.GetDouble());
        }
        var bones = rig.GetProperty("bones");
        int B(string k) => bones.GetProperty(k).GetInt32();
        var ml = ft.ModelLookupTables;
        ml.ItemHoldBone = (byte)B("ItemHoldBone"); ml.ShieldBone = (byte)B("ShieldBone"); ml.TopOfHeadBone = (byte)B("TopOfHeadBone");
        ml.LeftFootBone = (byte)B("LeftFootBone"); ml.RightFootBone = (byte)B("RightFootBone");
        if (imp != null) GltfModel.Lookups(ml, imp, costumes);   // high/low/metal DObj groups and the eye slots, from the import
        else
        {
            var all = Enumerable.Range(0, nd).Select(i => (byte)i).ToArray();
            HSDArrayAccessor<SBM_LookupTable> Lookup() =>
                new HSDArrayAccessor<SBM_LookupTable> { Array = new[] { new SBM_LookupTable { Count = 1, LookupEntries = new HSDArrayAccessor<SBM_LookupEntry> { Array = new[] { new SBM_LookupEntry { Count = all.Length, Entries = all } } } } } };
            var vis = new SBM_CostumeLookupTable { HighPoly = Lookup(), LowPoly = Lookup(), MetalPoly = Lookup() };
            ml.CostumeVisibilityLookups = new HSDArrayAccessor<SBM_CostumeLookupTable> { Array = new[] { vis } };
            ml._s.SetInt32(0x00, 1);
            ml._s.SetInt32(0x08, 0); ml._s.SetReference(0x0C, null);             // no material lookups: the blocks have no textures
        }

        var hb = new List<SBM_Hurtbox>();
        foreach (var h in rig.GetProperty("hurtboxes").EnumerateArray())
        {
            var p1 = F3(h.GetProperty("p1")); var p2 = F3(h.GetProperty("p2"));
            hb.Add(new SBM_Hurtbox { BoneIndex = h.GetProperty("bone").GetInt32(), Type = (HurtboxPositionType)h.GetProperty("type").GetInt32(),
                Grabbable = h.GetProperty("grab").GetInt32(), X1 = p1[0], Y1 = p1[1], Z1 = p1[2], X2 = p2[0], Y2 = p2[1], Z2 = p2[2],
                Size = (float)h.GetProperty("size").GetDouble() });
        }
        ft.Hurtboxes.Hurtboxes = hb.ToArray();
        ft.CenterBubble.BoneIndex = B("CenterBubble");
        var ecb = bones.GetProperty("ECB").EnumerateArray().Select(e => e.GetInt32()).ToArray();
        var ec = ft.EnvironmentCollision;
        ec.ECBBone1 = (short)ecb[0]; ec.ECBBone2 = (short)ecb[1]; ec.ECBBone3 = (short)ecb[2]; ec.ECBBone4 = (short)ecb[3]; ec.ECBBone5 = (short)ecb[4]; ec.ECBBone6 = (short)ecb[5];
        if (rig.TryGetProperty("ledge", out var lg))           // the ledge-grab box (model units; the engine scales it by ModelScale)
        {
            ec.LedgeGrabWidth = (float)lg.GetProperty("width").GetDouble(); ec.LedgeGrabYOffset = (float)lg.GetProperty("y").GetDouble();
            ec.LedgeGrabHeight = (float)lg.GetProperty("height").GetDouble();
        }
        var bt = ft.FighterBoneTable;
        bt.HeadBone = (byte)B("HeadBone"); bt.RightArm = (byte)B("RightArm"); bt.LeftLeg = (byte)B("LeftLeg"); bt.RightLeg = (byte)B("RightLeg"); bt.LeftArm = (byte)B("LeftArm");
        var ik = ft.FighterIK; var ikp = rig.GetProperty("ik");
        ik.RLegJ = (byte)B("RLegJ"); ik.LLegJ = (byte)B("LLegJ"); ik.RKneeJ = (byte)B("RKneeJ"); ik.LKneeJ = (byte)B("LKneeJ"); ik.RFootJ = (byte)B("RFootJ"); ik.LFootJ = (byte)B("LFootJ");
        ik.RShoulderJ = (byte)B("RShoulderJ"); ik.LShoulderJ = (byte)B("LShoulderJ"); ik.RArmJ = (byte)B("RArmJ"); ik.LArmJ = (byte)B("LArmJ");
        foreach (var kv in ikp.EnumerateObject()) ik.GetType().GetProperty(kv.Name).SetValue(ik, (float)kv.Value.GetDouble());

        // the shield pose, the metal model (the same blocks) and the hand and cap poses (the scripts' model parts)
        // while shielding the engine poses every joint below TransN from this tree (ftAnim_8006FA58), so it carries the guard
        // pose (anims.json shield_pose: local t and r per joint index); the rest pose left the shield at his feet
        var jidx = J.Select((jo, i) => (jo, i)).ToDictionary(x => x.jo, x => x.i);
        Func<HSD_JOBJ, float[]>? guard = null;
        if (anims.TryGetProperty("shield_pose", out var spj))
            guard = jo => jidx.TryGetValue(jo, out var i) && spj.TryGetProperty(i.ToString(), out var e)
                ? e.EnumerateArray().SelectMany(v => v.EnumerateArray()).Select(x => (float)x.GetDouble()).ToArray() : null;
        ft.ShieldPoseContainer.ShieldPose = SkeletonCopy(J[0], guard);
        ft.MetalModel = metalRoot ?? BuildModel(rig).root;  // a second, independent copy of the meshes
        aligned += AlignModel(ft.MetalModel, null);
        // model parts (the scripts' hand and cap poses): per part, pose k is an animation-joint tree over `count` joints
        // depth-first from its start joint. anims.json "part_poses" (per part, per pose: {joint index: {"r": [x,y,z],
        // "t": [x,y,z]}}, local to the joint's parent) keys those joints, constant, as Mario's are (keys at 0 and 10); a
        // pose without data stays empty, and the script's pose command then leaves the joints to the body animation.
        var parts = new List<SBM_ModelPart>(); int posed = 0;
        var partPoses = anims.TryGetProperty("part_poses", out var ppj) ? ppj.EnumerateArray().ToList() : new List<JsonElement>();
        int pi = 0;
        foreach (var mp in bones.GetProperty("ModelParts").EnumerateArray())
        {
            int st = mp.GetProperty("start").GetInt32(), cnt = mp.GetProperty("count").GetInt32();
            var ents = mp.GetProperty("entries").EnumerateArray().Select(e => (byte)e.GetInt32()).ToArray();
            var part = new SBM_ModelPart { StartingBone = (short)st, Count = (short)ents.Length, Entries = ents };
            int nAnim = st == B("HeadBone") ? 3 : 4;
            var poses = pi < partPoses.Count ? partPoses[pi].EnumerateArray().ToList() : new List<JsonElement>();
            part.Anims = new HSDFixedLengthPointerArrayAccessor<HSD_AnimJoint> { Array = Enumerable.Range(0, nAnim).Select(k => AnimTree(J[st], cnt, st, k < poses.Count ? poses[k] : (JsonElement?)null, ref posed)).ToArray() };
            parts.Add(part); pi++;
        }
        ft.ModelPartAnimations.Array = parts.ToArray();

        // the action table: new animations, flags authored for this kind, template scripts with remapped bones
        var co = new HSDRawFile(plco).Roots[0].Data as HSDRaw.Melee.SBM_ftLoadCommonData;
        var tt = co.BoneTables.Array[templateKind];
        var tj2p = tt._s.GetReference<HSDAccessor>(0x00)._s.GetData();
        var gp2j = rig.GetProperty("part_to_joint").EnumerateArray().Select(e => e.GetInt32()).ToArray();
        int headJ = B("HeadBone");
        int Remap(int tjoint) { int part = tjoint < tj2p.Length ? tj2p[tjoint] : 255; int g = part < gp2j.Length ? gp2j[part] : 255; return g == 255 ? headJ : g; }
        int kindId = 0x22;
        var tab = ft.FighterActionTable;
        var seen = new HashSet<HSDStruct>(); int hits = 0;

        var actNames = anims.GetProperty("actions").EnumerateArray().ToList();
        var (applyRows, animatedSlot) = AnimatedActions(rig);
        var scripts = anims.TryGetProperty("scripts", out var sc) ? sc.EnumerateObject().ToDictionary(p => p.Name, p => p.Value.GetString()) : new();
        int authored = 0;
        var cmds = tab.Commands.ToList();                      // copies of the embedded entries: edit, then assign back
        while (cmds.Count < actNames.Count)                    // a new kind can have more actions than its template
            cmds.Add(new SBM_FighterAction { _s = new HSDStruct(0x18) });
        for (int i = 0; i < cmds.Count; i++)
        {
            var c = cmds[i];
            string an = i < actNames.Count ? actNames[i].GetProperty("name").GetString() : "";
            if (!string.IsNullOrEmpty(an))
            {
                bool passed = pass.TryGetValue(an, out var psym);
                string sym = passed ? psym : prefix + an + "_figatree";
                c.SymbolName = new HSD_String { Value = sym };
                c.AnimationOffset = offsets[sym].off; c._s.SetInt32(0x08, offsets[sym].size);
                uint fl = i < actNames.Count && actNames[i].TryGetProperty("flags", out var fe) ? (uint)fe.GetInt64() : c.Flags;
                c.Flags = passed ? fl : (fl & ~0x3Fu) | (uint)kindId;   // the rig's own action list decides the flags; a passed-through
                                                                         // animation keeps the template's (its kind: 0x21, shared)
                if (animatedSlot.ContainsKey(an)) c.Flags |= 0x08000000u;   // its chains follow a bone apply table row
            }
            if (!string.IsNullOrEmpty(an) && scripts.TryGetValue(an, out var hex))
            {
                c.SubAction = new HSDRaw.Melee.Cmd.SBM_FighterSubactionData { _s = new HSDStruct(Convert.FromHexString(hex)) };
                authored++;
            }
            else if (c.SubAction != null) hits += RemapScript(c.SubAction._s, Remap, seen);
        }
        tab.Commands = cmds.ToArray();
        SilenceTemplateVoices(ft.CommonSoundEffectTable);
        // Geno's own sounds (bank 55): the voice table's slots and the cues his scripts gain (projects/geno/sound/wiring.py)
        if (anims.TryGetProperty("voices", out var vj)) SetVoices(ft.CommonSoundEffectTable, vj);
        int ncues = 0;
        if (anims.TryGetProperty("cues", out var cj))
            for (int i = 0; i < cmds.Count; i++)
            {
                var an = i < actNames.Count ? actNames[i].GetProperty("name").GetString() : null;
                if (string.IsNullOrEmpty(an) || cmds[i].SubAction == null || !cj.TryGetProperty(an, out var list)) continue;
                foreach (var cue in list.EnumerateArray())
                {
                    InsertCue(cmds[i].SubAction._s, cue[0].GetInt32(), Convert.FromHexString(cue[1].GetString()!)); ncues++;
                }
            }
        if (ncues > 0) Console.WriteLine($"fighter-build: {ncues} sound cues inserted");
        // the results screen's poses (the demo table, still Mario's) run their scripts too: the same bone remap and silence
        if (ft.DemoActionTable?.Commands != null)
            foreach (var dc in ft.DemoActionTable.Commands)
                if (dc?.SubAction != null) hits += RemapScript(dc.SubAction._s, Remap, seen);
        // his own results-screen poses, when the animation set has them (DemoBuild.cs: GmRstM{CODE}.dat and demo rows 0-9)
        if (anims.TryGetProperty("demo", out var demoSpec) && ft.DemoActionTable?.Commands != null)
            DemoBuild.Write(ft, demoSpec, J.Count, outDir, prefix);
        int nchains = WritePhysics(ft, rig, applyRows);
        var dyn = ft.FighterActionDynamicBehaviors;         // one per action, plus one
        if (dyn != null && dyn.Length < cmds.Count + 1)
        {
            var arr = dyn.Array.ToList();
            while (arr.Count < cmds.Count + 1) arr.Add(new SBM_DynamicBehavior { _s = new HSDStruct(dyn.Stride) });
            dyn.Array = arr.ToArray();
        }
        for (int i = 0; dyn != null && i < cmds.Count && i < actNames.Count; i++)   // the action's row of the bone apply table
            if (animatedSlot.TryGetValue(actNames[i].GetProperty("name").GetString(), out int slot))
            {
                var e = dyn[i]; e.BoneTableIndex = (byte)slot; dyn[i] = e;             // the indexer hands out a copy
            }
        // anims.json "blend": {action: frames}. Byte 0 of each entry (HSDRaw's "Flags") is the frames the engine blends into
        // that action from the pose before it whenever the caller passes no blend of its own (Fighter_ChangeMotionState:
        // anim_blend 0 falls back to ft_data->x10[anim_id][0]). Every template has 6 on Wait1, the three walks and Run.
        if (dyn != null && anims.TryGetProperty("blend", out var blendj))
        {
            var arr = dyn.Array; int nb = 0;
            for (int i = 0; i < actNames.Count && i < arr.Length; i++)
            {
                var an = actNames[i].GetProperty("name").GetString();
                if (!string.IsNullOrEmpty(an) && blendj.TryGetProperty(an, out var bv)) { arr[i]._s.SetByte(0, (byte)bv.GetInt32()); nb++; }
            }
            dyn.Array = arr;
            Console.WriteLine($"fighter-build: {nb} action blends set");
        }
        // ---- articles (projectiles): copies of donor fighters' articles (model, attributes, state scripts), overridden
        int nart = 0;
        if (anims.TryGetProperty("articles", out var artSpec))
        {
            var list = new List<SBM_Article>();
            var donors = new Dictionary<string, SBM_FighterData>();
            foreach (var ad in artSpec.EnumerateArray())
            {
                string frm = ad.GetProperty("frm").GetString();
                if (!donors.TryGetValue(frm, out var dft))
                {
                    var df = new HSDRawFile(Path.Combine(Path.GetDirectoryName(template)!, frm));
                    donors[frm] = dft = new SBM_FighterData { _s = df.Roots.First(r => r.Name.StartsWith("ftData")).Data._s };
                }
                var art = HSDAccessor.DeepClone<SBM_Article>(dft.Articles.Articles[ad.GetProperty("index").GetInt32()]);
                if (ad.TryGetProperty("state_from", out var sf) && sf.ValueKind == JsonValueKind.Array)
                {   // our states, each a copy of a donor state (its animation and parameters), by index
                    var src = art.ItemState.Array;
                    art.ItemState.Array = sf.EnumerateArray().Select(e => HSDAccessor.DeepClone<SBM_ItemState>(src[e.GetInt32()])).ToArray();
                }
                if (ad.TryGetProperty("hurt_r", out var hr))
                {   // one hurtbox on the item's root, so attacks can hit it (its dmg_received callback decides)
                    var hb0 = new SBM_ItemHurtbox { _s = new HSDStruct(0x20) };
                    hb0.BoneIndex = 0; hb0.Size = (float)hr.GetDouble();
                    art.Hurtboxes = new SBM_HurtboxBank<SBM_ItemHurtbox> { _s = new HSDStruct(8) };
                    art.Hurtboxes.Hurtboxes = new[] { hb0 };
                }
                if (ad.TryGetProperty("ext_size", out var es))
                    art.ParametersExt._s.Resize(Math.Max(art.ParametersExt._s.Length, es.GetInt32()));
                if (ad.TryGetProperty("ext", out var ext))
                    foreach (var kv in ext.EnumerateObject()) art.ParametersExt._s.SetFloat(int.Parse(kv.Name), (float)kv.Value.GetDouble());
                if (ad.TryGetProperty("scripts", out var scr) && scr.ValueKind == JsonValueKind.Array)
                {
                    var states = art.ItemState.Array;
                    int want = scr.GetArrayLength();
                    if (want > states.Length)               // more levels than the donor: clone its last state
                    {
                        var grown = states.ToList();
                        while (grown.Count < want) grown.Add(HSDAccessor.DeepClone<SBM_ItemState>(states[states.Length - 1]));
                        states = grown.ToArray();
                    }
                    int si = 0;
                    foreach (var hx in scr.EnumerateArray())
                    {
                        if (hx.ValueKind == JsonValueKind.String && si < states.Length)
                            states[si].SubactionScript = new HSDRaw.Melee.Cmd.SBM_ItemSubactionData { _s = new HSDStruct(Convert.FromHexString(hx.GetString()!)) };
                        si++;
                    }
                    art.ItemState.Array = states;
                }
                if (ad.TryGetProperty("model", out var msp) && msp.ValueKind == JsonValueKind.Object)
                {   // our own model (ArticleModel.cs): its joints, meshes, textures, and each state's joint animation
                    var mdir = msp.TryGetProperty("dir", out var md) ? md.GetString() : Path.GetDirectoryName(Path.GetFullPath(a[2]))!;
                    var (mroot, manims, msum) = ArticleModel.Build(msp, art, mdir);
                    art.Model.RootModelJoint = mroot;
                    art.Model.BoneCount = ArticleModel.CountJoints(mroot);   // the item's bone table (depth-first), so hitboxes can ride a joint
                    var sts = art.ItemState.Array;
                    for (int k = 0; k < sts.Length && k < manims.Count; k++) { sts[k].AnimJoint = manims[k]; sts[k].MatAnimJoint = null; }
                    art.ItemState.Array = sts;
                    Console.WriteLine($"fighter-build: article {ad.GetProperty("name").GetString()}: own model, {msum}");
                }
                AlignGX(art, new HashSet<HSDStruct>());
                list.Add(art);
            }
            ft.Articles = new SBM_ArticlePointer { Articles = list.ToArray() };
            nart = list.Count;
        }
        ftf.Save(Path.Combine(outDir, $"Pl{code}.dat"));
        Console.WriteLine($"fighter-build: {J.Count} joints, {nd} meshes" + (imp != null ? $" (glTF: high {imp.HighTris} tris, low {imp.LowTris}, {imp.Textures} textures {imp.TexBytes / 1024} KiB, {imp.EyeTobjs.Count} eye slots, metal {imp.Metal.Count})" : "") + $", {aligned} GX buffers aligned, {posed} part-pose joints keyed, {chunks.Count} animations, {cmds.Count} actions, {hb.Count} hurtboxes, {nchains} dynamics chains, {authored} authored scripts, {hits} template script bone refs remapped, {nart} articles -> {outDir}");
        return 0;
    }

    // rig.json dynamics "animated" (rig.py DYN_ANIMATED): {action: [joints left to the animation, per chain]} -> the bone
    // apply table's distinct rows, and each listed action's row
    static (List<int[]> rows, Dictionary<string, int> slot) AnimatedActions(JsonElement rig)
    {
        var rows = new List<int[]>(); var slot = new Dictionary<string, int>();
        if (!rig.TryGetProperty("dynamics", out var dj) || !dj.TryGetProperty("animated", out var aj)) return (rows, slot);
        foreach (var kv in aj.EnumerateObject())
        {
            var row = kv.Value.EnumerateArray().Select(e => e.GetInt32()).ToArray();
            int k = rows.FindIndex(r => r.SequenceEqual(row));
            if (k < 0) { rows.Add(row); k = rows.Count - 1; }
            slot[kv.Name] = k;
        }
        return (rows, slot);
    }

    // the physics chains (rig.json "dynamics", from rig.py DYNAMICS and SPHERES) as the ftData+0x2C group the engine loads at
    // spawn (ftCo_8009CF84) and solves every frame (lb_8001044C): per chain its first joint, its joint count, the follow
    // multiplier, a second multiplier the solver never reads, the gravity, and one 0x3C parameter block per joint; the
    // collision spheres (joint, centre in its frame, radius; ftColl_8007B320 loads at most 11); and the bone apply table, the
    // per-action rows (Marth's cape wraps him in his Guard this way) that an action flagged 0x08000000 picks by its dynamic
    // behaviour byte (ftData+0x10, the second byte)
    static int WritePhysics(SBM_FighterData ft, JsonElement rig, List<int[]> applyRows)
    {
        if (!rig.TryGetProperty("dynamics", out var dj)) return 0;
        var chains = dj.GetProperty("chains").EnumerateArray().ToList();
        var ph = new SBM_PhysicsGroup { _s = new HSDStruct(0x14) };
        var descs = new List<SBM_DynamicDesc>();
        foreach (var c in chains)
        {
            var d = new SBM_DynamicDesc { _s = new HSDStruct(0x18) };
            d.BoneIndex = c.GetProperty("bone").GetInt32();
            d.DragMultiplier = (float)c.GetProperty("follow_mul").GetDouble();
            d.StiffnessMultiplier = (float)c.GetProperty("mul_y").GetDouble();
            d.GravityLengthCompensation = (float)c.GetProperty("gravity").GetDouble();
            var ps = new List<SBM_DynamicParams>();
            foreach (var pj in c.GetProperty("params").EnumerateArray())
            {
                var p = new SBM_DynamicParams { _s = new HSDStruct(0x3C) };
                int k = 0;
                foreach (var v in pj.EnumerateArray()) p._s.SetFloat(4 * k++, (float)v.GetDouble());
                if (k != 15) throw new Exception($"dynamics: a joint's parameter block has {k} floats, not 15");
                ps.Add(p);
            }
            if (ps.Count != c.GetProperty("count").GetInt32()) throw new Exception("dynamics: one parameter block per chain joint");
            d.Parameters = ps.ToArray();                    // also sets the joint count at +0x08
            descs.Add(d);
        }
        ph.DynamicDescCount = descs.Count;
        if (descs.Count > 0) ph.DynamicDesc = new HSDArrayAccessor<SBM_DynamicDesc> { Array = descs.ToArray() };
        var sp = dj.GetProperty("spheres").EnumerateArray().ToList();
        if (sp.Count > 0)
        {   // decomp ftData_x38: joint, centre x y z, radius (HSDRaw's SBM_DynamicHitBubble names the centre Z, Y, X)
            var s = new HSDStruct(0x14 * sp.Count);
            for (int i = 0; i < sp.Count; i++)
            {
                var o = sp[i].GetProperty("offset").EnumerateArray().Select(x => (float)x.GetDouble()).ToArray();
                s.SetInt32(0x14 * i, sp[i].GetProperty("bone").GetInt32());
                s.SetFloat(0x14 * i + 4, o[0]); s.SetFloat(0x14 * i + 8, o[1]); s.SetFloat(0x14 * i + 12, o[2]);
                s.SetFloat(0x14 * i + 16, (float)sp[i].GetProperty("r").GetDouble());
            }
            ph.DynamicHitBubbleCount = sp.Count;
            ph._s.SetReferenceStruct(0x0C, s);
        }
        if (applyRows.Count > 0)
        {   // x10: one pointer per row, each to an int per chain (the engine reads them as ftCo_8009CB40's count: that many
            // leading joints left to the animation; 256 = the whole chain, unsolved)
            var t = new HSDStruct(4 * applyRows.Count);
            for (int k = 0; k < applyRows.Count; k++)
            {
                if (applyRows[k].Length != descs.Count) throw new Exception("dynamics: an animated row needs one count per chain");
                var r = new HSDStruct(4 * descs.Count);
                for (int i = 0; i < descs.Count; i++) r.SetInt32(4 * i, applyRows[k][i]);
                t.SetReferenceStruct(4 * k, r);
            }
            ph._s.SetReferenceStruct(0x10, t);
        }
        ft.Physics = ph;
        return descs.Count;
    }

    // the rig's joints as a JObj tree (depth-first order = index order, which the engine's parts tables assume), with
    // inverse binds; W holds each joint's rest-pose world matrix
    public static (List<HSD_JOBJ> J, List<Matrix4x4> W) BuildSkeleton(JsonElement rig)
    {
            var jr = rig.GetProperty("joints").EnumerateArray().ToList();
            var J = new List<HSD_JOBJ>(); var W = new List<Matrix4x4>();
            foreach (var j in jr)
            {
                var t = F3(j.GetProperty("t")); var r = F3(j.GetProperty("r"));
                // classical scale (JOBJ flag bit 3), as the cast's joints have it (Mario's are 0x9): a scaled joint's matrix is
                // inherited whole, so a grown hand carries its fingers and hitbox offsets. A figatree of type 1 sets it on the
                // joints it animates anyway; this covers the joints it leaves alone
                var jo = new HSD_JOBJ { TX = t[0], TY = t[1], TZ = t[2], RX = r[0], RY = r[1], RZ = r[2], SX = 1, SY = 1, SZ = 1,
                                        Flags = JOBJ_FLAG.CLASSICAL_SCALING };
                int p = j.GetProperty("parent").GetInt32();
                var local = Matrix4x4.CreateRotationX(r[0]) * Matrix4x4.CreateRotationY(r[1]) * Matrix4x4.CreateRotationZ(r[2]) * Matrix4x4.CreateTranslation(t[0], t[1], t[2]);
                W.Add(p >= 0 ? local * W[p] : local);
                if (p >= 0)
                {
                    if (J[p].Child == null) J[p].Child = jo;
                    else { var c = J[p].Child; while (c.Next != null) c = c.Next; c.Next = jo; }
                }
                J.Add(jo);
            }
            for (int i = 0; i < J.Count; i++) { Matrix4x4.Invert(W[i], out var inv); J[i].InverseWorldTransform = Hsd(inv); }
            CheckOrder(J[0], J);
            return (J, W);
    }

    static (HSD_JOBJ root, List<HSD_JOBJ> J, List<Matrix4x4> W, int nd) BuildModel(JsonElement rig)
    {
            var (J, W) = BuildSkeleton(rig);

            // ---- meshes: one DObj per colour, every vertex single-bound to its block's joint (so stored in the joint's frame)
            var gen = new POBJ_Generator { CullMode = GenCullMode.None };
            var attrs = new[] { GXAttribName.GX_VA_PNMTXIDX, GXAttribName.GX_VA_POS, GXAttribName.GX_VA_NRM };
            var byColour = new Dictionary<string, (List<GX_Vertex> v, List<HSD_JOBJ[]> b, List<float[]> w, int[] rgb)>();
            foreach (var bl in rig.GetProperty("blocks").EnumerateArray())
            {
                int ji = bl.GetProperty("joint").GetInt32();
                var rgb = bl.GetProperty("colour").EnumerateArray().Select(e => e.GetInt32()).ToArray();
                string key = string.Join(",", rgb);
                if (!byColour.ContainsKey(key)) byColour[key] = (new(), new(), new(), rgb);
                var g = byColour[key];
                Matrix4x4.Invert(W[ji], out var inv);
                foreach (var tri in bl.GetProperty("tris").EnumerateArray())
                {
                    var p = tri.EnumerateArray().Select(v => Vector3.Transform(new Vector3(F3(v)[0], F3(v)[1], F3(v)[2]), inv)).ToArray();
                    var n = Vector3.Normalize(Vector3.Cross(p[1] - p[0], p[2] - p[0]));
                    if (float.IsNaN(n.X)) continue;
                    foreach (var q in p)
                    {
                        g.v.Add(new GX_Vertex { POS = new GXVector3(q.X, q.Y, q.Z), NRM = new GXVector3(n.X, n.Y, n.Z) });
                        g.b.Add(new[] { J[ji] }); g.w.Add(new[] { 1f });
                    }
                }
            }
            HSD_DOBJ firstD = null, lastD = null; int nd = 0;
            foreach (var g in byColour.Values)
            {
                var mat = new HSD_Material { AMB_R = (byte)(g.rgb[0] / 2), AMB_G = (byte)(g.rgb[1] / 2), AMB_B = (byte)(g.rgb[2] / 2), AMB_A = 255,
                    DIF_R = (byte)g.rgb[0], DIF_G = (byte)g.rgb[1], DIF_B = (byte)g.rgb[2], DIF_A = 255, SPC_R = 255, SPC_G = 255, SPC_B = 255, SPC_A = 255,
                    Alpha = 1, Shininess = 50 };
                var d = new HSD_DOBJ { Mobj = new HSD_MOBJ { RenderFlags = RENDER_MODE.CONSTANT | RENDER_MODE.DIFFUSE | RENDER_MODE.SPECULAR, Material = mat },
                                       Pobj = gen.CreatePOBJsFromTriangleList(g.v, attrs, g.b, g.w) };
                if (firstD == null) firstD = d; else lastD.Next = d;
                lastD = d; nd++;
            }
            gen.SaveChanges();
            J[0].Dobj = firstD;
            J[0].UpdateFlags();
        return (J[0], J, W, nd);
    }

    // The GPU reads display lists and textures only from 32-byte boundaries. HSDRaw writes a data block of 0x40 bytes or
    // less on a 4-byte boundary unless it is flagged, and a loaded file carries no flags (HSDRaw's trim pass sets them, on a
    // trimmed save): the Whirl's cloned 32-byte display lists landed misaligned and the GPU misparsed them every frame
    // ("GFX FIFO: Unknown Opcode"). This flags every mesh buffer and texture reachable from a cloned article, as Trim does.
    static void AlignGX(HSDAccessor a, HashSet<HSDStruct> seen)
    {
        if (a == null || !seen.Add(a._s)) return;
        if (a is HSD_POBJ po)
        {
            var attr = po._s.GetReference<HSDAccessor>(0x08);
            if (attr != null) foreach (var r in attr._s.References) r.Value.IsBufferAligned = true;
            { var dl = po._s.GetReference<HSDAccessor>(0x10); if (dl != null) dl._s.IsBufferAligned = true; }
            if (po.Flags.HasFlag(POBJ_FLAG.ENVELOPE)) { var ev = po._s.GetReference<HSDAccessor>(0x14); if (ev != null) ev._s.IsBufferAligned = true; }
        }
        if ((a is HSD_Image || a is HSD_Tlut) && a._s.References.TryGetValue(0x00, out var buf)) buf.IsBufferAligned = true;
        foreach (var p in a.GetType().GetProperties())
        {
            if (p.GetIndexParameters().Length != 0) continue;
            object v;
            try { v = p.GetValue(a); } catch { continue; }
            if (v is HSDAccessor c && c != a) AlignGX(c, seen);
            else if (v is HSDAccessor[] arr) foreach (var e in arr) AlignGX(e, seen);
        }
    }

    // every display list, vertex array, texture and palette of a model (and its texture animations) on a 32-byte boundary,
    // as TexKit.AlignGX does for a whole file; returns how many buffers it flagged
    public static int AlignModel(HSD_JOBJ root, HSD_MatAnimJoint matanim)
    {
        var seen = new HashSet<HSDStruct>(); int n = 0;
        void Flag(HSDStruct s) { if (s != null && !s.IsBufferAligned) { s.IsBufferAligned = true; n++; } }
        void Buf0(HSDAccessor a) { if (a != null && a._s.References.TryGetValue(0x00, out var b)) Flag(b); }
        void J(HSD_JOBJ j)
        {
            for (; j != null && seen.Add(j._s); j = j.Next)
            {
                for (var d = j.Dobj; d != null; d = d.Next)
                {
                    for (var t = d.Mobj?.Textures; t != null; t = t.Next) { Buf0(t.ImageData); Buf0(t.TlutData); }
                    for (var p = d.Pobj; p != null && seen.Add(p._s); p = p.Next)
                    {
                        var attr = p._s.GetReference<HSDAccessor>(0x08);
                        if (attr != null) foreach (var r in attr._s.References) Flag(r.Value);
                        Flag(p._s.GetReference<HSDAccessor>(0x10)?._s);
                    }
                }
                J(j.Child);
            }
        }
        void M(HSD_MatAnimJoint m)
        {
            for (; m != null && seen.Add(m._s); m = m.Next)
            {
                for (var ma = m.MaterialAnimation; ma != null; ma = ma.Next)
                    for (var ta = ma.TextureAnimation; ta != null; ta = ta.Next)
                    {
                        foreach (var b in ta.ImageBuffers?.Array ?? new HSD_TexBuffer[0]) Buf0(b.Data);
                        foreach (var b in ta.TlutBuffers?.Array ?? new HSD_TlutBuffer[0]) Buf0(b.Data);
                    }
                M(m.Child);
            }
        }
        J(root); M(matanim);
        return n;
    }

    static float[] F3(JsonElement e) => e.EnumerateArray().Select(x => (float)x.GetDouble()).ToArray();

    static HSD_Matrix4x3 Hsd(Matrix4x4 m) => new HSD_Matrix4x3 { M11 = m.M11, M12 = m.M21, M13 = m.M31, M14 = m.M41,
        M21 = m.M12, M22 = m.M22, M23 = m.M32, M24 = m.M42, M31 = m.M13, M32 = m.M23, M33 = m.M33, M34 = m.M43 };

    static void CheckOrder(HSD_JOBJ root, List<HSD_JOBJ> J)
    {
        var order = new List<HSD_JOBJ>();
        void Walk(HSD_JOBJ j) { for (; j != null; j = j.Next) { order.Add(j); Walk(j.Child); } }
        Walk(root);
        for (int i = 0; i < J.Count; i++) if (!ReferenceEquals(order[i]._s, J[i]._s)) throw new Exception($"joint {i} is not in depth-first order");
    }

    public static HSD_MatAnimJoint MatAnimTree(HSD_JOBJ j)
    {
        var m = new HSD_MatAnimJoint();
        if (j.Child != null) m.Child = MatAnimTree(j.Child);
        if (j.Next != null) m.Next = MatAnimTree(j.Next);
        return m;
    }

    // an animation-joint tree mirroring `count` joints in depth-first order from j (its subtree, then its later siblings);
    // node k poses joint start + k (ftAnim_80070904 walks both in step). pose: {joint index: {"r": [...], "t": [...]}}
    static HSD_AnimJoint AnimTree(HSD_JOBJ j, int count, int start, JsonElement? pose, ref int keyed)
    {
        int left = count, idx = start, nk = 0;
        HSD_AnimJoint Build(HSD_JOBJ n)
        {
            if (n == null || left <= 0) return null;
            left--;
            var a = new HSD_AnimJoint { Flags = 1 };     // bit 0: classical scale on the joints it poses, as the cast's (Mario's, Fox's)
            if (pose is JsonElement pj && pj.TryGetProperty(idx.ToString(), out var e))
            {
                var ao = new HSD_AOBJ { EndFrame = 10 };
                void Track(string k, JointTrackType[] types)
                {
                    if (!e.TryGetProperty(k, out var v)) return;
                    var xyz = v.EnumerateArray().Select(x => (float)x.GetDouble()).ToArray();
                    for (int c = 0; c < 3; c++)
                        ao.AddTrack((byte)types[c], new List<FOBJKey> { new FOBJKey { Frame = 0, Value = xyz[c], InterpolationType = GXInterpolationType.HSD_A_OP_CON },
                                                                     new FOBJKey { Frame = 10, Value = xyz[c], InterpolationType = GXInterpolationType.HSD_A_OP_CON } });
                }
                Track("r", new[] { JointTrackType.HSD_A_J_ROTX, JointTrackType.HSD_A_J_ROTY, JointTrackType.HSD_A_J_ROTZ });
                Track("t", new[] { JointTrackType.HSD_A_J_TRAX, JointTrackType.HSD_A_J_TRAY, JointTrackType.HSD_A_J_TRAZ });
                if (ao.FObjDesc != null) { a.AOBJ = ao; nk++; }
            }
            idx++;
            a.Child = Build(n.Child);
            a.Next = Build(n.Next);
            return a;
        }
        var root = Build(j);
        keyed += nk;
        return root;
    }

    static HSD_JOBJ SkeletonCopy(HSD_JOBJ j, Func<HSD_JOBJ, float[]?>? pose = null)
    {
        var c = new HSD_JOBJ { Flags = j.Flags & ~(JOBJ_FLAG.ENVELOPE_MODEL | JOBJ_FLAG.OPA | JOBJ_FLAG.XLU | JOBJ_FLAG.TEXEDGE | JOBJ_FLAG.ROOT_OPA | JOBJ_FLAG.ROOT_XLU | JOBJ_FLAG.ROOT_TEXEDGE),
                               TX = j.TX, TY = j.TY, TZ = j.TZ, RX = j.RX, RY = j.RY, RZ = j.RZ, SX = j.SX, SY = j.SY, SZ = j.SZ };
        var p = pose?.Invoke(j);                          // t xyz, r xyz in the joint's parent frame
        if (p != null) { c.TX = p[0]; c.TY = p[1]; c.TZ = p[2]; c.RX = p[3]; c.RY = p[4]; c.RZ = p[5]; }
        if (j.Child != null) c.Child = SkeletonCopy(j.Child, pose);
        if (j.Next != null) c.Next = SkeletonCopy(j.Next, pose);
        return c;
    }

    static readonly JointTrackType[] Scale = { JointTrackType.HSD_A_J_SCAX, JointTrackType.HSD_A_J_SCAY, JointTrackType.HSD_A_J_SCAZ };

    static void AddTracks(FigaTreeNode node, JsonElement keys, JointTrackType[] types)
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

    // remap bone fields in a move script (and the scripts it calls), in place: CreateHitbox (bits 14..20),
    // GraphicEffect (bits 42..47), SetBoneCollisionState (bits 6..13)
    // Geno is silent in Super Mario RPG: sounds from the template fighter's bank (Mario's, 180000-189999: his jump, dodge,
    // taunt, damage and KO voices, the crowd's "Ma-ri-o!") become 540001, the engine's no-voice id (the voice calls skip it
    // and the others play it at volume 0), in the template's scripts and in the fighter's voice table.
    const int Silent = 540001;
    static bool TemplateBank(int id) => id / 10000 == 18;

    static void SilenceTemplateVoices(SBM_PlayerSFXTable t)
    {
        if (t == null) return;
        foreach (var p in t.GetType().GetProperties())
        {
            if (p.PropertyType == typeof(int) && p.CanWrite && TemplateBank((int)p.GetValue(t)!)) p.SetValue(t, Silent);
            else if (p.GetValue(t) is Int32Table tab && tab.Entries != null)
                tab.Entries = tab.Entries.Select(v => TemplateBank(v) ? Silent : v).ToArray();
        }
    }

    static void SetVoices(SBM_PlayerSFXTable t, JsonElement v)
    {
        if (t == null) return;
        foreach (var kv in v.EnumerateObject())
        {
            var p = t.GetType().GetProperty(kv.Name) ?? throw new Exception("no voice slot " + kv.Name);
            if (kv.Value.ValueKind == JsonValueKind.Array)
            {
                var tab = p.GetValue(t) as Int32Table ?? new Int32Table();
                tab.Entries = kv.Value.EnumerateArray().Select(e => e.GetInt32()).ToArray();
                p.SetValue(t, tab);
            }
            else p.SetValue(t, kv.Value.GetInt32());
        }
    }

    // A sound cue at frame N goes where the script would first wait past N (or before its end or a jump), behind an
    // AsynchronousTimer(N) when the script hasn't reached N yet; a SynchronousTimer it lands in front of becomes the
    // AsynchronousTimer of the same frame, so the template's own commands keep their frames. References (GoTo and
    // subroutine pointers) after the insertion move with it.
    static void InsertCue(HSDStruct s, int frame, byte[] cue)
    {
        var d = s.GetData(); int o = 0, cur = 0, at = -1, syncTarget = -1;
        uint W(int k) => (uint)((d[k] << 24) | (d[k + 1] << 16) | (d[k + 2] << 8) | d[k + 3]);
        while (o < d.Length)
        {
            int op = d[o] >> 2;
            var cmd = HSDRaw.Tools.Melee.ActionCommon.GetMeleeCMDAction((byte)op);
            if (cmd == null || cmd.ByteSize <= 0) break;
            int val = (int)(W(o) & 0x3FFFFFF);
            if (op == 0x02) { if (val > frame) { at = o; break; } cur = val; }
            else if (op == 0x01) { if (cur + val > frame) { at = o; syncTarget = cur + val; break; } cur += val; }
            else if (op == 0x00 || (op >= 0x03 && op <= 0x09)) { at = o; break; }   // the end, loops, jumps
            o += cmd.ByteSize;
        }
        if (at < 0) at = o;
        byte[] Timer(int f) { uint w = (0x02u << 26) | (uint)f; return new[] { (byte)(w >> 24), (byte)(w >> 16), (byte)(w >> 8), (byte)w }; }
        var block = frame > cur ? Timer(frame).Concat(cue).ToArray() : cue;
        var nd = d.Take(at).Concat(block).Concat(d.Skip(at)).ToArray();
        if (syncTarget >= 0) Array.Copy(Timer(syncTarget), 0, nd, at + block.Length, 4);
        var refs = s.References.ToList();
        foreach (var r in refs) s.References.Remove(r.Key);
        s.SetData(nd);
        foreach (var r in refs) s.SetReferenceStruct(r.Key >= at ? r.Key + block.Length : r.Key, r.Value);
    }

    static int RemapScript(HSDStruct s, Func<int, int> remap, HashSet<HSDStruct> seen)
    {
        if (s == null || !seen.Add(s)) return 0;
        var d = s.GetData(); int n = 0, o = 0;
        while (o < d.Length)
        {
            int op = d[o] >> 2;
            var cmd = HSDRaw.Tools.Melee.ActionCommon.GetMeleeCMDAction((byte)op);
            if (cmd == null || cmd.ByteSize <= 0) break;
            if (op == 0x0B) { n++; SetBits(d, o, 14, 7, remap(GetBits(d, o, 14, 7))); }
            // a graphic effect: its bone is bits 6-13 (the decomp's spawn_gfx_0; bits 32-47 are the effect id). With
            // useCommonBoneIDs (bit 14) it is a Fighter_Part every fighter resolves through its own parts table, and 0x8D/0x8E
            // and useUnkBone (bit 16) pick ftData bones, so only a plain joint index (the template's skeleton) is remapped
            // (ftCo_8009F834). This once remapped bits 42-47, the effect id's low bits: the template's effects changed id.
            if (op == 0x0A && GetBits(d, o, 14, 1) == 0 && GetBits(d, o, 16, 1) == 0)
            {
                int gb = GetBits(d, o, 6, 8);
                if (gb != 0x8D && gb != 0x8E) { n++; SetBits(d, o, 6, 8, remap(gb)); }
            }
            if (op == 0x1C) { n++; SetBits(d, o, 6, 8, remap(GetBits(d, o, 6, 8))); }
            if (op == 0x11 && d.Length >= o + 8)                  // a sound from the template's own bank (Mario's voice)
            {
                int id = (d[o + 4] << 24) | (d[o + 5] << 16) | (d[o + 6] << 8) | d[o + 7];
                if (TemplateBank(id)) { d[o + 4] = 0; d[o + 5] = (byte)((Silent >> 16) & 0xFF); d[o + 6] = (byte)((Silent >> 8) & 0xFF); d[o + 7] = (byte)(Silent & 0xFF); }
            }
            if (op == 0) break;
            o += cmd.ByteSize;
        }
        s.SetData(d);
        foreach (var r in s.References.Values) n += RemapScript(r, remap, seen);
        return n;
    }

    static int GetBits(byte[] d, int o, int bit, int len)
    {
        int v = 0;
        for (int i = 0; i < len; i++) { int b = bit + i; v = (v << 1) | ((d[o + b / 8] >> (7 - b % 8)) & 1); }
        return v;
    }

    static void SetBits(byte[] d, int o, int bit, int len, int v)
    {
        for (int i = 0; i < len; i++)
        {
            int b = bit + i, bitv = (v >> (len - 1 - i)) & 1, idx = o + b / 8, sh = 7 - b % 8;
            d[idx] = (byte)((d[idx] & ~(1 << sh)) | (bitv << sh));
        }
    }
}
