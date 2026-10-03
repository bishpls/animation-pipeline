// Adding images to HSD texture animations and keying them, shared by css-geno and menus-geno.
using HSDRaw;
using HSDRaw.Common;
using HSDRaw.Common.Animation;
using HSDRaw.GX;
using HSDRaw.Tools;

static class TexKit
{
    public static byte[] Bgra(string path, int w, int h)
    {
        var b = File.ReadAllBytes(path);
        if (b.Length != w * h * 4) throw new Exception($"{path}: expected {w}x{h} BGRA ({w * h * 4} bytes), got {b.Length}");
        return b;
    }

    // an intensity texture (I4/I8): HSDRaw's encoder averages R, G and B
    public static HSD_TOBJ Intensity(string path, int w, int h, GXTexFmt fmt)
    {
        var t = new HSD_TOBJ();
        t.EncodeImageData(Bgra(path, w, h), w, h, fmt, GXTlutFmt.IA8);
        return t;
    }

    // a paletted texture (CI4/CI8) from an image that already has at most 16/256 colours: the palette is exactly its
    // colours (no requantizing), fully transparent pixels share one entry, and the palette is padded to the full size
    public static HSD_TOBJ Indexed(string path, int w, int h, GXTexFmt fmt, GXTlutFmt tf)
    {
        var bgra = Bgra(path, w, h);
        int cap = fmt == GXTexFmt.CI4 ? 16 : 256, th = fmt == GXTexFmt.CI4 ? 8 : 4;
        if (w % 8 != 0 || h % th != 0) throw new Exception($"{path}: {w}x{h} is not whole {8}x{th} tiles");
        var pal = new List<uint>(); var idx = new int[w * h];
        for (int i = 0; i < w * h; i++)
        {
            uint c = BitConverter.ToUInt32(bgra, i * 4);
            if ((c >> 24) == 0) c = 0;
            if (tf == GXTlutFmt.RGB565) c |= 0xFF000000;
            int k = pal.IndexOf(c);
            if (k < 0) { pal.Add(c); k = pal.Count - 1; }
            idx[i] = k;
        }
        if (pal.Count > cap) throw new Exception($"{path}: {pal.Count} colours, {fmt} holds {cap}");
        var data = new List<byte>();
        for (int ty = 0; ty < h; ty += th)
            for (int tx = 0; tx < w; tx += 8)
                for (int y = ty; y < ty + th; y++)
                    for (int x = tx; x < tx + 8; x += fmt == GXTexFmt.CI4 ? 2 : 1)
                        data.Add(fmt == GXTexFmt.CI4 ? (byte)((idx[y * w + x] << 4) | idx[y * w + x + 1]) : (byte)idx[y * w + x]);
        var tl = new byte[cap * 2];
        for (int i = 0; i < pal.Count; i++)
        {
            uint c = pal[i]; int b = (int)(c & 0xFF), g = (int)((c >> 8) & 0xFF), r = (int)((c >> 16) & 0xFF), al = (int)(c >> 24);
            ushort v = tf switch
            {
                GXTlutFmt.RGB5A3 => GXImageConverter.EncodeRGBA3(al, r, g, b),
                GXTlutFmt.RGB565 => (ushort)(((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)),
                _ => throw new Exception($"palette format {tf}")
            };
            tl[i * 2] = (byte)(v >> 8); tl[i * 2 + 1] = (byte)v;
        }
        return new HSD_TOBJ
        {
            ImageData = new HSD_Image { ImageData = data.ToArray(), Width = (short)w, Height = (short)h, Format = fmt },
            TlutData = new HSD_Tlut { TlutData = tl, Format = tf, ColorCount = (short)cap }
        };
    }

    // decoded BGRA of a TOBJ, to check an encode against its source
    public static byte[] Decode(HSD_TOBJ t) => t.GetDecodedImageData();

    public static int MaxError(byte[] a, byte[] b)
    {
        int m = 0;
        for (int i = 0; i < a.Length; i += 4)
        {
            if (a[i + 3] == 0 && b[i + 3] == 0) continue;                 // both transparent: colour doesn't matter
            for (int c = 0; c < 4; c++) m = Math.Max(m, Math.Abs(a[i + c] - b[i + c]));
        }
        return m;
    }

    public static HSD_TexAnim TexAnim(HSD_MatAnimJoint mj, int dobj)
    {
        var mm = mj?.MaterialAnimation;
        for (int i = 0; i < dobj && mm != null; i++) mm = mm.Next;
        var ta = mm?.TextureAnimation;
        if (ta == null || ta.ImageCount == 0) throw new Exception($"no image texture animation on dobj {dobj}");
        return ta;
    }

    public static IEnumerable<HSD_FOBJDesc> Tracks(HSD_TexAnim ta)
    { for (var fd = ta?.AnimationObject?.FObjDesc; fd != null; fd = fd.Next) yield return fd; }

    // Adds images to texture animations once per shared buffer array (the four doors or panels often share one), and
    // keys frames once per shared track, checking that everything sharing a track agrees on the new indices.
    public class Adder
    {
        readonly Dictionary<(HSDStruct, HSDStruct), int> img = new(), tlut = new();
        readonly Dictionary<(HSDStruct, float), float> keyed = new();
        public readonly List<string> Log = new();

        public (int img, int tlut) Add(HSD_TexAnim ta, HSD_TOBJ t)
        {
            var ib = ta.ImageBuffers;
            if (ib.Length != ta.ImageCount) throw new Exception($"image array holds {ib.Length}, count says {ta.ImageCount}");
            if (!img.TryGetValue((ib._s, t.ImageData._s), out var ii))
            {
                ib.Add(new HSD_TexBuffer { Data = t.ImageData });
                ii = ib.Length - 1; img[(ib._s, t.ImageData._s)] = ii;
            }
            ta.ImageBuffers = ib;                                              // refresh this texanim's count
            int ti = -1;
            if (t.TlutData != null)
            {
                var tb = ta.TlutBuffers;
                if (tb == null) throw new Exception("paletted image into a texture animation without palettes");
                if (tb.Length != ta.TlutCount) throw new Exception($"palette array holds {tb.Length}, count says {ta.TlutCount}");
                if (!tlut.TryGetValue((tb._s, t.TlutData._s), out ti))
                {
                    // the widest existing palette (the stage select's first is a 2-colour "locked" placeholder)
                    var t0 = tb.Array.OrderByDescending(x => x.Data.ColorCount).First().Data;
                    if (t0.Format != t.TlutData.Format || t0.ColorCount != t.TlutData.ColorCount)
                        throw new Exception($"palette {t.TlutData.Format}/{t.TlutData.ColorCount} into {t0.Format}/{t0.ColorCount}");
                    t.TlutData.GXTlut = t0.GXTlut;
                    tb.Add(new HSD_TlutBuffer { Data = t.TlutData });
                    ti = tb.Length - 1; tlut[(tb._s, t.TlutData._s)] = ti;
                }
                ta.TlutBuffers = tb;
            }
            return (ii, ti);
        }

        // key FRAMES of the image track to IMG and of the palette track to TLUT; the frame after each keeps what it showed
        public void Key(HSD_TexAnim ta, IEnumerable<float> frames, int imgIdx, int tlutIdx)
        {
            foreach (var fd in Tracks(ta))
            {
                var tt = (TexTrackType)fd.TrackType;
                if (tt != TexTrackType.HSD_A_T_TIMG && tt != TexTrackType.HSD_A_T_TCLT) continue;
                float v = tt == TexTrackType.HSD_A_T_TIMG ? imgIdx : tlutIdx;
                if (v < 0) throw new Exception("palette track but no palette");
                var todo = new List<float>();
                foreach (var f0 in frames)
                {
                    if (keyed.TryGetValue((fd._s, f0), out var had)) { if (had != v) throw new Exception($"shared track keyed {had} and {v} at {f0}"); continue; }
                    keyed[(fd._s, f0)] = v; todo.Add(f0);
                }
                if (todo.Count > 0) KeyTrack(fd, todo, v);
            }
            // a key past the animation's end still plays when requested directly, but keep the end past it like the
            // vanilla frames are (IfAll's emblem animation ends at 120; Geno's frame is 180)
            var ao = ta.AnimationObject; float need = frames.Max() + 2;
            if (ao != null && ao.EndFrame < need) { Log.Add($"end frame {ao.EndFrame} -> {need}"); ao.EndFrame = need; }
        }
    }

    // The GPU reads textures, palettes, display lists and vertex arrays only from 32-byte boundaries. HSDRaw re-saves a
    // loaded file with any block of 0x40 bytes or less on a 4-byte boundary unless it is flagged (a loaded file carries no
    // flags), so once anything earlier in the file changes size, small palettes, tiny images and short display lists land
    // misaligned (css-geno's first MnSlChr.usd had one such display list). This flags every such buffer of every model in
    // the file before a save; projects/geno/menus/gxalign.py checks the result.
    public static int AlignGX(HSDRawFile f)
    {
        var seen = new HashSet<HSDStruct>(); int n = 0;
        void Flag(HSDStruct s) { if (s != null && !s.IsBufferAligned) { s.IsBufferAligned = true; n++; } }
        void Buf0(HSDAccessor a) { if (a != null && a._s.References.TryGetValue(0x00, out var b)) Flag(b); }
        void Pobj(HSD_POBJ p)
        {
            for (; p != null && seen.Add(p._s); p = p.Next)
            {
                var attr = p._s.GetReference<HSDAccessor>(0x08);
                if (attr != null) foreach (var r in attr._s.References) Flag(r.Value);
                Flag(p._s.GetReference<HSDAccessor>(0x10)?._s);
            }
        }
        void Jobj(HSD_JOBJ j)
        {
            for (; j != null && seen.Add(j._s); j = j.Next)
            {
                for (var d = j.Dobj; d != null; d = d.Next)
                {
                    for (var t = d.Mobj?.Textures; t != null; t = t.Next) { Buf0(t.ImageData); Buf0(t.TlutData); }
                    Pobj(d.Pobj);
                }
                Jobj(j.Child);
            }
        }
        void MatJ(HSD_MatAnimJoint m)
        {
            for (; m != null && seen.Add(m._s); m = m.Next)
            {
                for (var ma = m.MaterialAnimation; ma != null; ma = ma.Next)
                    for (var ta = ma.TextureAnimation; ta != null; ta = ta.Next)
                    {
                        foreach (var b in ta.ImageBuffers?.Array ?? new HSD_TexBuffer[0]) Buf0(b.Data);
                        foreach (var b in ta.TlutBuffers?.Array ?? new HSD_TlutBuffer[0]) Buf0(b.Data);
                    }
                MatJ(m.Child);
            }
        }
        foreach (var m in MenusGeno.Models(f)) { Jobj(m.J); MatJ(m.M); }
        foreach (var r in f.Roots)                                   // a scene model's other material-animation sets
        {
            var descs = r.Data is HSD_SOBJ so ? so.JOBJDescs?.Array : (r.Data as HSDNullPointerArrayAccessor<HSD_JOBJDesc>)?.Array;
            foreach (var d in descs ?? new HSD_JOBJDesc[0])
                foreach (var mj in d?.MaterialAnimations?.Array ?? new HSD_MatAnimJoint[0]) MatJ(mj);
        }
        return n;
    }

    public static void KeyTrack(HSD_FOBJDesc fd, IEnumerable<float> frames, float value)
    {
        var keys = fd.GetDecodedKeys();
        foreach (var f0 in frames.OrderBy(x => x))
        {
            float after = MenusGeno.At(keys, f0 + 1);
            bool keepNext = keys.Any(k => k.Frame == f0 + 1);
            keys.RemoveAll(k => k.Frame == f0 || (k.Frame == f0 + 1 && !keepNext));
            keys.Add(new FOBJKey { Frame = f0, Value = value, InterpolationType = GXInterpolationType.HSD_A_OP_CON });
            if (!keepNext) keys.Add(new FOBJKey { Frame = f0 + 1, Value = after, InterpolationType = GXInterpolationType.HSD_A_OP_CON });
            keys.Sort((x, y) => x.Frame.CompareTo(y.Frame));
        }
        fd.SetKeys(keys, fd.TrackType);
    }
}
