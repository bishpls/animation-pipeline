// datkit: inspect (and, next, write) Melee's HSD .dat files.
//   dotnet run --project tools/machinima/melee/datkit -- roots FILE.dat
//   dotnet run --project tools/machinima/melee/datkit -- tree FILE.dat [ROOT] [--depth 4]
using System.Collections;
using System.Reflection;
using HSDRaw;

static class Program
{
    // command sizes in words: opcodes 0-9 are the interpreter's (1 word, 5 and 7 carry a pointer: 2), 0x0A+ from the
    // decomp's ftAction_803C0870
    static readonly int[] FtCmdWords = { 5, 5, 1, 1, 1, 1, 1, 3, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 3, 1, 1, 1, 7, 4, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 3, 3, 2, 1, 4 };
    public static int CmdWords(int op) => op < 10 ? (op == 5 || op == 7 ? 2 : 1) : (op - 10 < FtCmdWords.Length ? FtCmdWords[op - 10] : 1);

    static int Main(string[] a)
    {
        if (a.Length < 2) { Console.Error.WriteLine("usage: datkit roots|tree FILE.dat [ROOT] [--depth N]"); return 2; }
        if (a[0] == "fighter-build") return FighterBuild.Run(a);
        if (a[0] == "meshstats") return ModelSpec.Stats(a);            // meshstats PlXxNr.dat [--ft PlXx.dat] [--co PlCo.dat --kind N | --rig RIG.json] [--texdir D] : model measurements (JSON)
        if (a[0] == "export") return ModelSpec.Export(a);
        if (a[0] == "model-tables") return GltfModel.Tables(a);
        if (a[0] == "gltf-model") return GltfModel.Run(a);              // gltf-model RIG.json OUT_PlXxNr.dat [--high H.gltf --low L.gltf] : a costume file from a skinned glTF (GltfModel.cs)         // model-tables PlXx.dat [PlXxNr.dat] : lookup tables, metal model, texture animations (JSON)              // export PlXxNr.dat OUT.gltf [--ft PlXx.dat --lod high|low|all] [--dobjs 0-36] : rest-pose glTF
        if (a[0] == "kirby-hat") return GltfModel.KirbyHat(a);          // kirby-hat TEMPLATE_PlKbCpXx.dat OUT.dat --high H.gltf [--low L.gltf] [--symbol S] : a Kirby copy hat (HatBuild.cs)
        if (a[0] == "ef-dump") return EffectKit.Dump(a);
        if (a[0] == "ef-build") return EffectKit.Build(a);
        if (a[0] == "art-dump") return EffectKit.ArticleDump(a);     // art-dump PlXx.dat INDEX : an article's model and state animations          // ef-build SPEC.json OUT.dat : a new effect file (EffectKit.cs)            // ef-dump EfXxData.dat [--gen N,...] [--tex OUTDIR] [--models] (EffectKit.cs)
        if (a[0] == "movedata") return MoveData.Run(a);
        if (a[0] == "stage-dump") return StageKit.Dump(a);       // stage-dump GrXx.dat [OUT.json] [--joints] [--bind C:G:J,...] : a stage in world space (StageKit.cs)
        if (a[0] == "stage-patch") return StageKit.Patch(a);
        if (a[0] == "stage-build") return StageBuild.Run(a);
        if (a[0] == "sis-dump") return MenusStage.SisDump(a);
        if (a[0] == "menus-stage") return MenusStage.Build(a);   // menus-stage ART SPEC MnSlMap.usd OUT SdMenu.usd OUT : the Forest Maze in the stage select (MenusStage.cs)
        if (a[0] == "dobj-info") return MenusStage.DobjInfo(a);
        if (a[0] == "prize-geno") return MenusApproach.Prize(a);       // prize-geno SdPrize.usd OUT TEXT1 TEXT2 : Geno's prize messages, entries 0x47-0x48 (MenusApproach.cs)
        if (a[0] == "approach-geno") return MenusApproach.Build(a); // approach-geno NtAppro.usd SIL.bgra OUT : Geno's NEW CHALLENGER silhouette, frame 12 (MenusApproach.cs)     // stage-build SPEC.json TEMPLATE_GrXx.dat OUT.dat : a stage file from a spec (StageBuild.cs)     // stage-patch IN OUT [--joint G:J:DX:DY] [--line L:DX:DY] : move a joint and a line (world units)
        if (a[0] == "bodydata") return MoveData.Body(a);        // bodydata PL AJ NR CO KIND RIG|- IDX,... : hurtbox extents per frame (MoveData.cs)
        if (a[0] == "fk" || a[0] == "fkdir") return FK.Run(a);      // fk NR ANIM [OUT] / fkdir NR PL AJ OUTDIR [REGEX] : sampled FK per frame (FK.cs)
        if (a[0] == "mscan") return MenusGeno.Scan(a);                 // mscan FILE [FRAMES] : every model's texture animations
        if (a[0] == "mdump") return MenusGeno.Dump(a);
        if (a[0] == "scene-dump") return SceneDump.Run(a);           // scene-dump FILE MODEL [OUT.json] [--frames F,...] : joints, materials, quads, cameras as JSON (SceneDump.cs)
        if (a[0] == "mframes") return MenusGeno.Frames(a);             // mframes FILE MODEL OUTDIR J[:DOBJ],... FRAMES : what each frame shows                 // mdump FILE MODEL OUTDIR [J,...] : textures and keys as PNG/text
        if (a[0] == "menus-geno") return MenusGeno.Run(a);             // menus-geno ART DISC OUT : Geno's menu art (MenusGeno.cs)
        var f = new HSDRawFile(a[1]);
        if (a[0] == "roots")
        {
            foreach (var r in f.Roots) Console.WriteLine($"{r.Name,-32} {r.Data?.GetType().Name,-36} {r.Data?._s?.Length,8} bytes");
            return 0;
        }
        if (a[0] == "attrs")                                   // attrs FILE... : every fighter's common attributes as CSV
        {
            bool header = true;
            foreach (var path in a.Skip(1))
            {
                var ff = new HSDRawFile(path);
                var root = ff.Roots.FirstOrDefault(r => r.Name.StartsWith("ftData"));
                var at = root?.Data?.GetType().GetProperty("Attributes")?.GetValue(root.Data);
                if (at == null) { Console.Error.WriteLine($"{path}: no ftData attributes"); continue; }
                var props = at.GetType().GetProperties(BindingFlags.Public | BindingFlags.Instance)
                    .Where(p => (p.PropertyType == typeof(float) || p.PropertyType == typeof(int)) && p.GetIndexParameters().Length == 0 && !p.Name.StartsWith("_")).ToArray();
                if (header) { Console.WriteLine("fighter," + string.Join(",", props.Select(p => p.Name))); header = false; }
                Console.WriteLine(root.Name.Substring(6) + "," + string.Join(",", props.Select(p => Convert.ToString(p.GetValue(at), System.Globalization.CultureInfo.InvariantCulture))));
            }
            return 0;
        }
        if (a[0] == "jobjs")                                   // jobjs FILE ROOT FIELD : a model's joints in depth-first index order
        {
            var root = f.Roots.First(r => r.Name == a[2]).Data;
            var get = (string n) => root.GetType().GetProperty(n)?.GetValue(root);
            var jo = get(a[3]) as HSDRaw.Common.HSD_JOBJ;
            var an = get(a[3].Replace("Model", "Animation")) as HSDRaw.Common.Animation.HSD_AnimJoint;
            var ma = get(a[3].Replace("Model", "MaterialAnimation")) as HSDRaw.Common.Animation.HSD_MatAnimJoint;
            int idx = 0;
            void W(HSDRaw.Common.HSD_JOBJ j, HSDRaw.Common.Animation.HSD_AnimJoint aj, HSDRaw.Common.Animation.HSD_MatAnimJoint mj, int d)
            {
                for (; j != null; j = j.Next, aj = aj?.Next, mj = mj?.Next)
                {
                    int nd = 0; string tex = "";
                    for (var dob = j.Dobj; dob != null; dob = dob.Next)
                    {
                        nd++;
                        var t = dob.Mobj?.Textures;
                        if (t != null && tex == "") tex = $"{t.ImageData?.Width}x{t.ImageData?.Height} {t.ImageData?.Format}";
                    }
                    int ntr = 0; if (aj?.AOBJ?.FObjDesc != null) foreach (var _ in aj.AOBJ.FObjDesc.List) ntr++;
                    string mat = "";
                    for (var mm = mj?.MaterialAnimation; mm != null; mm = mm.Next)
                        if (mm.TextureAnimation != null) mat += $" texanim[{mm.TextureAnimation.ImageCount}]";
                    Console.WriteLine($"{idx,3} {new string(' ', d * 2)}T=({j.TX:0.##},{j.TY:0.##},{j.TZ:0.##}) S=({j.SX:0.##},{j.SY:0.##}) flags={(uint)j.Flags:X} dobj={nd} {tex} tracks={ntr}{mat}");
                    idx++;
                    W(j.Child, aj?.Child, mj?.Child, d + 1);
                }
            }
            W(jo, an, ma, 0);
            return 0;
        }
        if (a[0] == "script")                                  // script PlXx.dat IDX[,IDX...] : move scripts as text and hex
        {
            var ft = f.Roots.First(r => r.Name.StartsWith("ftData")).Data;
            var tab = ft.GetType().GetProperty("FighterActionTable").GetValue(ft) as HSDRaw.Melee.Pl.SBM_FighterActionTable;
            var cmds = tab.Commands;
            foreach (var idx in a[2].Split(',').Select(int.Parse))
            {
                var c = cmds[idx];
                Console.WriteLine($"=== {idx} 0x{idx:X} {c.Name} flags {c.Flags:X8}");
                var d = c.SubAction?._s.GetData();
                int o = 0;
                while (d != null && o < d.Length)
                {
                    int op = d[o] >> 2;
                    var mc = HSDRaw.Tools.Melee.ActionCommon.GetMeleeCMDAction((byte)op);
                    int n = CmdWords(op) * 4;
                    var bytes = d.Skip(o).Take(n).ToArray();
                    string dec; try { dec = mc?.Decompile(bytes); } catch { dec = "?"; }
                    Console.WriteLine($"  {o,4} {op:X2} {BitConverter.ToString(bytes).Replace("-", "")}  {mc?.Name}({dec})");
                    if (op == 0) break;
                    o += n;
                }
            }
            return 0;
        }
        if (a[0] == "lookups")                                 // lookups PlXx.dat : model visibility and material lookups
        {
            var ft = f.Roots.First(r => r.Name.StartsWith("ftData")).Data;
            var ml = ft.GetType().GetProperty("ModelLookupTables").GetValue(ft) as HSDRaw.Melee.Pl.SBM_PlayerModelLookupTables;
            Console.WriteLine($"groups {ml.VisibilityLookupLength}  material lookups {ml.MaterialLookupLength}");
            var cl = ml.CostumeVisibilityLookups;
            string T(HSDArrayAccessor<HSDRaw.Melee.Pl.SBM_LookupTable> t)
            {
                if (t == null) return "null";
                return string.Join(" / ", t.Array.Select(lt => $"[{lt.Count}: " + string.Join(" ; ", (lt.LookupEntries?.Array ?? new HSDRaw.Melee.Pl.SBM_LookupEntry[0]).Select(e => string.Join(",", e.Entries ?? new byte[0]))) + "]"));
            }
            for (int c = 0; c < cl.Length; c++)
                Console.WriteLine($"costume {c}: high {T(cl[c].HighPoly)}\n   low {T(cl[c].LowPoly)}\n   metal {T(cl[c].MetalPoly)}\n   metalmain {T(cl[c].MetalMainModel)}");
            var mat = ml.CostumeMaterialLookups;
            for (int c = 0; mat != null && c < mat.Length; c++)
                Console.WriteLine($"material {c}: {string.Join(",", mat[c].Entries?.Array ?? new ushort[0])}");
            return 0;
        }
        if (a[0] == "actions")                                 // actions PlXx.dat [AJ.dat OUTDIR] : the action table (and extract anims)
        {
            var ft = f.Roots.First(r => r.Name.StartsWith("ftData")).Data;
            var tab = ft.GetType().GetProperty("FighterActionTable").GetValue(ft) as HSDRaw.Melee.Pl.SBM_FighterActionTable;
            byte[] aj = a.Length > 3 ? File.ReadAllBytes(a[2]) : null;
            if (aj != null) Directory.CreateDirectory(a[3]);
            for (int i = 0; i < tab.Commands.Length; i++)
            {
                var c = tab.Commands[i];
                float frames = 0;
                if (aj != null && c.AnimationSize > 0)
                {
                    var chunk = new HSDRawFile(aj.Skip(c.AnimationOffset).Take(c.AnimationSize).ToArray());
                    frames = (chunk.Roots[0].Data as HSDRaw.Common.Animation.HSD_FigaTree)?.FrameCount ?? 0;
                }
                Console.WriteLine($"{i,3} 0x{i:X3} off {c.AnimationOffset,8} size {c.AnimationSize,6} flags {c.Flags:X8} script {c.SubAction?._s.Length ?? 0,5} frames {frames,5}  {c.Name}");
                if (aj != null && c.AnimationSize > 0)
                    File.WriteAllBytes(Path.Combine(a[3], $"{i:D3}.dat"), aj.Skip(c.AnimationOffset).Take(c.AnimationSize).ToArray());
            }
            return 0;
        }
        if (a[0] == "dynamics")                                // dynamics PlXx.dat [--actions] : the ftData+0x2C physics chains (cape, hair, cap)
        {
            var ft = new HSDRaw.Melee.Pl.SBM_FighterData { _s = f.Roots.First(r => r.Name.StartsWith("ftData")).Data._s };
            var ph = ft.Physics;
            if (ph == null) { Console.WriteLine("no physics group"); return 0; }
            Console.WriteLine($"chains {ph.DynamicDescCount}, collision spheres {ph.DynamicHitBubbleCount}, bone apply table {(ph._s.GetReference<HSDAccessor>(0x10) != null ? "yes" : "no")}");
            var dd = ph.DynamicDesc?.Array ?? new HSDRaw.Melee.Pl.SBM_DynamicDesc[0];
            foreach (var d in dd)
            {
                var ps = d.Parameters ?? new HSDRaw.Melee.Pl.SBM_DynamicParams[0];
                Console.WriteLine($"chain bone {d.BoneIndex} count {d._s.GetInt32(0x08)}  pos.x(follow mul) {d.DragMultiplier:0.####} pos.y {d.StiffnessMultiplier:0.####} pos.z(gravity) {d.GravityLengthCompensation:0.####}");
                for (int i = 0; i < ps.Length; i++)
                {
                    var p = ps[i];
                    var raw = string.Join(" ", Enumerable.Range(0, 15).Select(k => p._s.GetFloat(k * 4).ToString("0.####")));
                    Console.WriteLine($"   [{i}] follow {p.FollowDamping:0.####} converge {p.Stiffness:0.####} rest ({p.RotX:0.####},{p.RotY:0.####},{p.RotZ:0.####},{p.RotW:0.####}) limit {p.RotationLimit:0.####} damp {p.InertiaDamping:0.####} maxstep {p.Resistance:0.####} | {raw}");
                }
            }
            for (int i = 0; i < ph.DynamicHitBubbleCount; i++)
            {
                var s = ph._s.GetReference<HSDAccessor>(0x0C)._s;
                Console.WriteLine($"sphere bone {s.GetInt32(i * 0x14)} offset ({s.GetFloat(i * 0x14 + 4):0.###},{s.GetFloat(i * 0x14 + 8):0.###},{s.GetFloat(i * 0x14 + 12):0.###}) r {s.GetFloat(i * 0x14 + 16):0.###}");
            }
            var bat = ph._s.GetReference<HSDAccessor>(0x10);
            if (bat != null)
            {
                Console.WriteLine($"bone apply table: {bat._s.Length} bytes, {bat._s.References.Count} refs (per slot, per chain: joints left to the animation)");
                for (int k = 0; k < bat._s.Length / 4; k++)
                {
                    var t = bat._s.GetReference<HSDAccessor>(4 * k);
                    Console.WriteLine($"   slot {k}: " + (t == null ? "null" : string.Join(" ", Enumerable.Range(0, t._s.Length / 4).Select(i => t._s.GetInt32(4 * i)))));
                }
            }
            if (a.Contains("--actions"))
            {
                var tab = ft.FighterActionTable; var beh = ft.FighterActionDynamicBehaviors;
                for (int i = 0; i < tab.Commands.Length; i++)
                {
                    var c = tab.Commands[i]; uint fl = c.Flags;
                    string bb = beh != null && i < beh.Length ? $"{beh[i].Flags:X2} {beh[i].BoneTableIndex:X2}" : "--";
                    if ((fl & 0x18000000) != 0 || (beh != null && i < beh.Length && (beh[i].Flags | beh[i].BoneTableIndex) != 0))
                        Console.WriteLine($"action {i,3} 0x{i:X3} flags {fl:X8} anim-driven {((fl & 0x10000000) != 0 ? 1 : 0)} table {((fl & 0x08000000) != 0 ? 1 : 0)} beh {bb}  {c.Name}");
                }
            }
            return 0;
        }
        if (a[0] == "chances")                                 // chances PlXx.dat : the idle-animation lists (ftData+0x24 Wait, +0x28 SquatWait): action id and weight
        {
            var ft = f.Roots.First(r => r.Name.StartsWith("ftData")).Data as HSDRaw.Melee.Pl.SBM_FighterData;
            foreach (var (lab, arr) in new[] { ("wait", ft.IdleActionChances), ("squat", ft.WaitIdleActionChances) })
            {
                var l = new List<string>();
                for (int i = 0; arr != null && i < 32; i++) { var e = arr[i]; if (e == null || e.ActionID == -1) break; l.Add($"{e.ActionID}:{e.Chance}"); }
                Console.WriteLine($"{lab} {string.Join(" ", l)}");
            }
            return 0;
        }
        if (a[0] == "parts")                                   // parts PlXx.dat : the ftData model-part (hand pose) tables
        {
            var ft = f.Roots.First(r => r.Name.StartsWith("ftData")).Data;
            var mp = ft.GetType().GetProperty("ModelPartAnimations").GetValue(ft) as HSDFixedLengthPointerArrayAccessor<HSDRaw.Melee.Pl.SBM_ModelPart>;
            for (int i = 0; i < mp.Length; i++)
            {
                var m = mp[i];
                Console.WriteLine($"part {i}: start bone {m.StartingBone} count {m.Count} entries [{string.Join(",", m.Entries ?? new byte[0])}] anims {m.Anims?.Length}");
                for (int k = 0; m.Anims != null && k < m.Anims.Length; k++)
                {
                    int n = 0, tr = 0; var fl = new SortedSet<uint>();
                    void C(HSDRaw.Common.Animation.HSD_AnimJoint aj) { for (; aj != null; aj = aj.Next) { n++; fl.Add((uint)aj.Flags); if (aj.AOBJ != null) tr++; C(aj.Child); } }
                    // flags bit 0: the engine sets classical scale on each joint the part animation poses (HSD_JObjAddAnim)
                    C(m.Anims[k]); Console.WriteLine($"   anim {k}: {n} nodes, {tr} animated, anim-joint flags {string.Join(",", fl.Select(x => x.ToString("X")))}");
                }
            }
            return 0;
        }
        if (a[0] == "pobjcheck")                               // pobjcheck PlXx.dat : each article mesh's vertex format and display list, as the game reads them
        {   // The game reads a mesh's attribute list up to GX_VA_NULL and sends DisplayListSize bytes; a list or buffer that
            // HSDRaw split (another struct points into its middle) and a clone laid out apart makes the GPU misparse the list
            var fd = f.Roots.First(r => r.Data is HSDRaw.Melee.Pl.SBM_FighterData).Data as HSDRaw.Melee.Pl.SBM_FighterData;
            var arts = fd.Articles?.Articles ?? new HSDRaw.Melee.Pl.SBM_Article[0];
            for (int i = 0; i < arts.Length; i++)
            {
                int pi = 0;
                void J(HSDRaw.Common.HSD_JOBJ j)
                {
                    for (; j != null; j = j.Next)
                    {
                        for (var dob = j.Dobj; dob != null; dob = dob.Next)
                            for (var po = dob.Pobj; po != null; po = po.Next, pi++)
                            {
                                var at = po._s.GetReference<HSDAccessor>(0x08)?._s;
                                int n = at == null ? 0 : at.Length / 0x18, term = -1;
                                var names = new List<string>();
                                for (int k = 0; k < n; k++)
                                {
                                    int nm = at.GetInt32(k * 0x18);
                                    if (nm == 0xFF) { term = k; break; }
                                    names.Add($"{nm}:{at.GetInt32(k * 0x18 + 4)}");
                                }
                                var dl = po.DisplayListBuffer;
                                string warn = (term < 0 ? " NO-TERMINATOR" : "") + ((dl?.Length ?? 0) < po.DisplayListSize ? " SHORT-DL" : "") + (po.ShapeSet != null ? " shapeset" : "");
                                Console.WriteLine($"article {i} pobj {pi}: flags {(int)po.Flags:X} attrs[{n} in struct, term@{term}] {string.Join(",", names)} dl {dl?.Length}/{po.DisplayListSize}{warn}");
                            }
                        J(j.Child);
                    }
                }
                J(arts[i]?.Model?.RootModelJoint);
            }
            return 0;
        }
        if (a[0] == "articles")                                // articles PlXx.dat : each article's states, scripts, attributes
        {
            var fd = f.Roots.First(r => r.Data is HSDRaw.Melee.Pl.SBM_FighterData).Data as HSDRaw.Melee.Pl.SBM_FighterData;
            var arts = fd.Articles?.Articles ?? new HSDRaw.Melee.Pl.SBM_Article[0];
            for (int i = 0; i < arts.Length; i++)
            {
                var ar = arts[i];
                if (ar == null) { Console.WriteLine($"article {i}: null"); continue; }
                var ext = ar.ParametersExt?._s;
                Console.WriteLine($"article {i}: common {ar.Parameters?._s?.Length} ext {ext?.Length} model {(ar.Model != null ? "yes" : "no")} hurt {(ar.Hurtboxes != null ? "yes" : "no")} states {ar.ItemState?.Length ?? 0}");
                if (ext != null) Console.WriteLine("   ext floats: " + string.Join(" ", Enumerable.Range(0, ext.Length / 4).Select(k => ext.GetFloat(k * 4).ToString("0.###"))));
                for (int s = 0; s < (ar.ItemState?.Length ?? 0); s++)
                {
                    var st = ar.ItemState[s];
                    var sc = st?.SubactionScript?._s?.GetData();
                    Console.WriteLine($"   state {s}: anim {(st?.AnimJoint != null ? "yes" : "no")} script {(sc == null ? "-" : BitConverter.ToString(sc).Replace("-", ""))}");
                }
            }
            return 0;
        }
        if (a[0] == "rootmotion")                              // rootmotion AJFILE.dat [NODE=1] : TransN's translation each frame (JSON)
        {
            var ft = f.Roots[0].Data as HSDRaw.Common.Animation.HSD_FigaTree;
            int node = a.Length > 2 ? int.Parse(a[2]) : 1;
            var ps = node < ft.Nodes.Count ? ft.Nodes[node].Tracks.Select(tr => new HSDRaw.Tools.FOBJ_Player { Keys = tr.GetKeys(), TrackType = tr.TrackType }).ToList() : new();
            var rows = new List<string>();
            for (int fr = 0; fr <= (int)Math.Ceiling(ft.FrameCount); fr++)
            {
                float x = 0, y = 0, z = 0;
                foreach (var p in ps)
                {
                    if (p.JointTrackType == HSDRaw.Common.Animation.JointTrackType.HSD_A_J_TRAX) x = p.GetValue(fr);
                    if (p.JointTrackType == HSDRaw.Common.Animation.JointTrackType.HSD_A_J_TRAY) y = p.GetValue(fr);
                    if (p.JointTrackType == HSDRaw.Common.Animation.JointTrackType.HSD_A_J_TRAZ) z = p.GetValue(fr);
                }
                rows.Add($"[{fr},{x:0.####},{y:0.####},{z:0.####}]");
            }
            Console.WriteLine($"{{\"frames\":{ft.FrameCount:0.##},\"t\":[{string.Join(",", rows)}]}}");
            return 0;
        }
        if (a[0] == "figa")                                    // figa AJFILE.dat [NODE] : a figatree's nodes and tracks (NODE: every key of that node)
        {
            var ft = f.Roots[0].Data as HSDRaw.Common.Animation.HSD_FigaTree;
            Console.WriteLine($"{f.Roots[0].Name} type {ft.Type} frames {ft.FrameCount} nodes {ft.Nodes.Count}");
            int ni = 0, pick = a.Length > 2 ? int.Parse(a[2]) : -1;
            foreach (var nd in ft.Nodes)
            {
                if (pick < 0 || pick == ni)
                    Console.WriteLine($"  node {ni}: " + string.Join(" | ", nd.Tracks.Select(t => { var k = t.GetKeys(); return $"{t.JointTrackType} {k.Count}k [{string.Join(" ", k.Take(pick < 0 ? 4 : k.Count).Select(x => $"{x.Frame}:{x.Value:0.###}/{x.InterpolationType.ToString().Replace("HSD_A_OP_", "")}"))}]"; })));
                ni++;
            }
            return 0;
        }
        if (a[0] == "rest")                                    // rest PlXxNr.dat : world rest positions of every joint (JSON lines)
        {
            var jo = f.Roots.First(r => r.Name.EndsWith("_joint") && !r.Name.Contains("matanim")).Data as HSDRaw.Common.HSD_JOBJ;
            int idx = 0;
            void W(HSDRaw.Common.HSD_JOBJ j, System.Numerics.Matrix4x4 parent, int pi)
            {
                for (; j != null; j = j.Next)
                {
                    var local = System.Numerics.Matrix4x4.CreateScale(j.SX, j.SY, j.SZ) *
                                System.Numerics.Matrix4x4.CreateRotationX(j.RX) * System.Numerics.Matrix4x4.CreateRotationY(j.RY) * System.Numerics.Matrix4x4.CreateRotationZ(j.RZ) *
                                System.Numerics.Matrix4x4.CreateTranslation(j.TX, j.TY, j.TZ);
                    var world = local * parent;
                    int me = idx++;
                    Console.WriteLine($"{{\"i\":{me},\"p\":{pi},\"x\":{world.M41:0.####},\"y\":{world.M42:0.####},\"z\":{world.M43:0.####},\"t\":[{j.TX:0.####},{j.TY:0.####},{j.TZ:0.####}],\"r\":[{j.RX:0.####},{j.RY:0.####},{j.RZ:0.####}],\"flags\":{(uint)j.Flags}}}");
                    W(j.Child, world, me);
                }
            }
            W(jo, System.Numerics.Matrix4x4.Identity, -1);
            return 0;
        }
        if (a[0] == "skel")                                    // skel PlCo.dat KIND PlXxNr.dat : a skeleton with its parts mapping
        {
            var co = f.Roots[0].Data as HSDRaw.Melee.SBM_ftLoadCommonData;
            var bt = co.BoneTables.Array[int.Parse(a[2])];
            var j2p = bt._s.GetReference<HSDAccessor>(0x00); var p2j = bt._s.GetReference<HSDAccessor>(0x04);
            int n = bt._s.GetInt32(0x08);
            Console.WriteLine($"count {n}  joint_to_part {j2p?._s.Length} bytes  part_to_joint {p2j?._s.Length} bytes");
            Console.WriteLine("part_to_joint: " + string.Join(" ", Enumerable.Range(0, p2j._s.Length).Select(i => $"{i}:{p2j._s.GetByte(i)}")));
            var nr = new HSDRawFile(a[3]);
            var jo = nr.Roots.First(r => r.Name.EndsWith("_joint") && !r.Name.Contains("matanim")).Data as HSDRaw.Common.HSD_JOBJ;
            int idx = 0;
            void W(HSDRaw.Common.HSD_JOBJ j, int d, int parent)
            {
                for (; j != null; j = j.Next)
                {
                    int me = idx++;
                    int nd = 0; for (var dob = j.Dobj; dob != null; dob = dob.Next) nd++;
                    string part = j2p != null && me < j2p._s.Length ? j2p._s.GetByte(me).ToString() : "-";
                    Console.WriteLine($"{me,3} p{parent,-3} part {part,-4}{new string(' ', d * 2)}T=({j.TX:0.###},{j.TY:0.###},{j.TZ:0.###}) R=({j.RX:0.###},{j.RY:0.###},{j.RZ:0.###}) S=({j.SX:0.##},{j.SY:0.##},{j.SZ:0.##}) flags={(uint)j.Flags:X} dobj={nd}");
                    W(j.Child, d + 1, me);
                }
            }
            W(jo, 0, -1);
            return 0;
        }
        if (a[0] == "fighter-build")
            return FighterBuild.Run(a);
        if (a[0] == "css-geno")                                // css-geno IN.usd OUT.usd ICON.bgra CSP0.bgra [CSP1.bgra ...] [--stock STOCK.bgra]
            return CssGeno.Run(f, a[2], a[3], a.Skip(4).ToArray());
        if (a[0] == "animkeys")                                // animkeys FILE ROOT FIELD J1,J2 : a joint's animation tracks
        {
            var root = f.Roots.First(r => r.Name == a[2]).Data;
            var jo = root.GetType().GetProperty(a[3])?.GetValue(root) as HSDRaw.Common.HSD_JOBJ;
            var an = root.GetType().GetProperty(a[3].Replace("Model", "Animation"))?.GetValue(root) as HSDRaw.Common.Animation.HSD_AnimJoint;
            var flat = new List<HSDRaw.Common.Animation.HSD_AnimJoint>();
            void Fl(HSDRaw.Common.HSD_JOBJ j, HSDRaw.Common.Animation.HSD_AnimJoint aj) { for (; j != null; j = j.Next, aj = aj?.Next) { flat.Add(aj); Fl(j.Child, aj?.Child); } }
            Fl(jo, an);
            foreach (var ji in a[4].Split(',').Select(int.Parse))
            {
                var aj = flat[ji];
                Console.WriteLine($"j{ji} aobj flags={aj?.AOBJ?.Flags} end={aj?.AOBJ?.EndFrame}");
                if (aj?.AOBJ?.FObjDesc != null)
                    foreach (var fo in aj.AOBJ.FObjDesc.List)
                        Console.WriteLine($"   {fo.JointTrackType}: " + string.Join(" ", fo.GetDecodedKeys().Select(k => $"{k.Frame}:{k.Value:0.###}/{k.InterpolationType}")));
            }
            return 0;
        }
        if (a[0] == "texdump")                                 // texdump FILE ROOT FIELD OUTDIR J1,J2,... : textures and texanims as PNG
        {
            var root = f.Roots.First(r => r.Name == a[2]).Data;
            var get = (string n) => root.GetType().GetProperty(n)?.GetValue(root);
            var jo = get(a[3]) as HSDRaw.Common.HSD_JOBJ;
            var ma = get(a[3].Replace("Model", "MaterialAnimation")) as HSDRaw.Common.Animation.HSD_MatAnimJoint;
            var want = a[5].Split(',').Select(int.Parse).ToHashSet();
            Directory.CreateDirectory(a[4]);
            var joints = new List<(HSDRaw.Common.HSD_JOBJ, HSDRaw.Common.Animation.HSD_MatAnimJoint)>();
            void Flat(HSDRaw.Common.HSD_JOBJ j, HSDRaw.Common.Animation.HSD_MatAnimJoint mj)
            { for (; j != null; j = j.Next, mj = mj?.Next) { joints.Add((j, mj)); Flat(j.Child, mj?.Child); } }
            Flat(jo, ma);
            foreach (var ji in want.OrderBy(x => x))
            {
                var (j, mj) = joints[ji];
                int di = 0;
                for (var dob = j.Dobj; dob != null; dob = dob.Next, di++)
                {
                    var t = dob.Mobj?.Textures; int ti = 0;
                    for (; t != null; t = t.Next, ti++)
                    {
                        var rgba = t.GetDecodedImageData();
                        if (rgba != null) Png.Write(Path.Combine(a[4], $"j{ji}_d{di}_t{ti}.png"), rgba, t.ImageData.Width, t.ImageData.Height);
                        Console.WriteLine($"j{ji} dobj{di} tex{ti} {t.ImageData?.Width}x{t.ImageData?.Height} {t.ImageData?.Format} tlut={t.TlutData?.Format} blend={dob.Mobj.RenderFlags}");
                    }
                }
                int mi = 0;
                for (var mm = mj?.MaterialAnimation; mm != null; mm = mm.Next, mi++)
                {
                    int ti = 0;
                    for (var ta = mm.TextureAnimation; ta != null; ta = ta.Next, ti++)
                    {
                        var imgs = ta.ImageBuffers?.Array; var tls = ta.TlutBuffers?.Array;
                        Console.WriteLine($"j{ji} matanim{mi} texanim{ti} texmap={ta.GXTexMapID} images={imgs?.Length ?? 0} tluts={tls?.Length ?? 0} count={ta.ImageCount}");
                        if (ta.AnimationObject?.FObjDesc != null)
                            foreach (var fo in ta.AnimationObject.FObjDesc.List)
                            {
                                var keys = fo.GetDecodedKeys();
                                Console.WriteLine($"   track {fo.JointTrackType}/{fo.TrackType}: " + string.Join(" ", keys.Take(400).Select(k => $"{k.Frame}:{k.Value}")));
                            }
                        for (int ii = 0; imgs != null && ii < imgs.Length && ii < 400; ii++)
                        {
                            var im = imgs[ii].Data; var tl = tls != null && ii < tls.Length ? tls[ii].Data : (tls != null && tls.Length > 0 ? tls[0].Data : null);
                            var rgba = tl != null ? HSDRaw.Tools.GXImageConverter.DecodeTPL(im.Format, im.Width, im.Height, im.ImageData, tl.Format, tl.ColorCount, tl.TlutData)
                                                  : HSDRaw.Tools.GXImageConverter.DecodeTPL(im.Format, im.Width, im.Height, im.ImageData);
                            Png.Write(Path.Combine(a[4], $"j{ji}_m{mi}_ta{ti}_{ii:D3}.png"), rgba, im.Width, im.Height);
                        }
                    }
                }
            }
            return 0;
        }
        int depth = 4; string only = null;
        for (int i = 2; i < a.Length; i++) { if (a[i] == "--depth") depth = int.Parse(a[++i]); else only = a[i]; }
        foreach (var r in f.Roots)
        {
            if (only != null && r.Name != only) continue;
            Console.WriteLine($"# {r.Name}  ({r.Data?.GetType().Name})");
            Walk(r.Data, "  ", depth, new HashSet<object>(ReferenceEqualityComparer.Instance));
        }
        return 0;
    }

    static void Walk(object o, string ind, int depth, HashSet<object> seen)
    {
        if (o == null || depth < 0 || !seen.Add(o)) return;
        foreach (var p in o.GetType().GetProperties(BindingFlags.Public | BindingFlags.Instance))
        {
            if (p.GetIndexParameters().Length > 0 || p.Name.StartsWith("_") || p.Name == "TrimmedSize") continue;
            object v; try { v = p.GetValue(o); } catch { continue; }
            if (v == null) continue;
            var t = v.GetType();
            if (t.IsPrimitive || v is string || t.IsEnum || v is decimal) { Console.WriteLine($"{ind}{p.Name} = {v}"); continue; }
            if (v is Array arr) { Console.WriteLine($"{ind}{p.Name} [{arr.Length}] {t.GetElementType()?.Name}"); if (arr.Length > 0 && depth > 0 && !(arr.GetValue(0)?.GetType().IsPrimitive ?? true)) Walk(arr.GetValue(0), ind + "  [0] ", depth - 1, seen); continue; }
            if (v is HSDAccessor acc) { Console.WriteLine($"{ind}{p.Name}: {t.Name} ({acc._s?.Length} bytes)"); Walk(v, ind + "  ", depth - 1, seen); continue; }
            if (v is IEnumerable en && !(v is string)) { int n = 0; foreach (var _ in en) n++; Console.WriteLine($"{ind}{p.Name} ({n}) {t.Name}"); continue; }
        }
    }
}

static class Png
{
    static uint[] T = Enumerable.Range(0, 256).Select(n => { uint c = (uint)n; for (int k = 0; k < 8; k++) c = (c & 1) != 0 ? 0xEDB88320u ^ (c >> 1) : c >> 1; return c; }).ToArray();
    static uint Crc(byte[] b, int o, int n) { uint c = 0xFFFFFFFFu; for (int i = o; i < o + n; i++) c = T[(c ^ b[i]) & 0xFF] ^ (c >> 8); return c ^ 0xFFFFFFFFu; }
    static void Chunk(Stream s, string type, byte[] data)
    {
        var len = BitConverter.GetBytes(data.Length); Array.Reverse(len); s.Write(len);
        var td = System.Text.Encoding.ASCII.GetBytes(type).Concat(data).ToArray(); s.Write(td);
        var crc = BitConverter.GetBytes(Crc(td, 0, td.Length)); Array.Reverse(crc); s.Write(crc);
    }
    // HSDRaw decodes to BGRA; PNG wants RGBA
    public static void Write(string path, byte[] bgra, int w, int h)
    {
        using var fs = File.Create(path);
        fs.Write(new byte[] { 137, 80, 78, 71, 13, 10, 26, 10 });
        var ih = new byte[13]; void BE(int o, int v) { ih[o] = (byte)(v >> 24); ih[o + 1] = (byte)(v >> 16); ih[o + 2] = (byte)(v >> 8); ih[o + 3] = (byte)v; }
        BE(0, w); BE(4, h); ih[8] = 8; ih[9] = 6; Chunk(fs, "IHDR", ih);
        var raw = new byte[h * (w * 4 + 1)];
        for (int y = 0; y < h; y++) for (int x = 0; x < w; x++)
        { int si = (y * w + x) * 4, di = y * (w * 4 + 1) + 1 + x * 4; raw[di] = bgra[si + 2]; raw[di + 1] = bgra[si + 1]; raw[di + 2] = bgra[si]; raw[di + 3] = bgra[si + 3]; }
        using var ms = new MemoryStream();
        using (var z = new System.IO.Compression.ZLibStream(ms, System.IO.Compression.CompressionLevel.Fastest, true)) z.Write(raw);
        Chunk(fs, "IDAT", ms.ToArray()); Chunk(fs, "IEND", new byte[0]);
    }
}
