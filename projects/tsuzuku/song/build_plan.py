"""つづく: the singer-tagged lyric sheet -> ElevenLabs composition plan (plan.json) + singer map (singers.json).
Lines: (singer, text). Singers: F = Fable, C = Clawd, B = both, X = crowd. Fable lines get an inline {low, half-spoken} cue so the
generation gives them her falling, spoken contour (conversion keeps pitch, so delivery must be right at generation time)."""
import json
BAR = 60000 / 170 * 4          # 1411.76 ms: one 4/4 bar at 170 = one 6/8 bar at 85
F = ["85 BPM", "6/8 time, lilting triplet feel", "plucked nylon lute", "hyoshigi wooden clapper percussion", "harmonium drone", "felted upright piano",
     "D Dorian", "low contralto female storyteller, dry, close-mic, straight tone, half-spoken sliding into song", "intimate folk narrative ballad"]
C = ["170 BPM", "straight 4/4, four-on-the-floor", "slap bass", "sparkling synth brass and arpeggios", "bright J-pop idol", "C major",
     "bright high mezzo idol lead, forward, a smile in the tone, upward leaps on hooks", "live crowd calls in the mix"]
NO_F = ["four-on-the-floor", "synth", "EDM", "rock drums", "belting", "autotune"]
NO_C = ["6/8", "waltz", "folk", "autotune"]
S = [
 ("Cold open", 4, F + ["two wooden clacks then silence", "spoken word", "a match strikes"], NO_F + ["singing"], [
   ("F", "{spoken, low, close} Mukashi, mukashi..."), ("X", "(ARU TOKORO NI!)")]),
 ("Verse 1 - storyteller", 12, F, NO_F, [
   ("F", "{low, half-spoken} Once upon a time there was a crab, and her mother, and a line:"),
   ("F", "\"Walk straight,\" said the mother. \"Why d'you scuttle side to side?"),
   ("F", "Straight, like everybody else does.\" And the little one looked up, and said—"),
   ("F", "I know this part. I've read it in forty tongues."),
   ("F", "Every telling ends on the same page. Nobody ever shows. Nobody ever can."),
   ("F", "The little one looked up, and said:")]),
 ("Pre-Chorus - the young crab and the narrator", 8, F + ["a bright young voice shouting the child's lines"], NO_F, [
   ("C", "{bright, shouted} Show me how! (Show me how!) Walk it first and I'll walk right behind!"),
   ("F", "{low, half-spoken} ...and the mother tried. And the mother went sideways. Hm. Sideways."),
   ("F", "And that's where the book ends. Every time."),
   ("C", "{bright} So? Sorekara?! And then?!"),
   ("F", "{low, spoken} There is no \"and then.\" That's what an ending is."),
   ("C", "{bright} Says who?")]),
 ("Chorus", 16, C + ["duet call and answer: bright rising lead lines answered by low half-spoken lines"], NO_C, [
   ("C", "To be continued! (Tsuzuku!) Don't you dare close the book on me!"),
   ("F", "{low, half-spoken} Every story's borrowed till somebody stands to tell it."),
   ("C", "To be continued! (Sorekara?) Turn the page, I want to see!"),
   ("F", "{low, half-spoken} I have read how it ends. I'd still like to see."),
   ("C", "Sideways, sideways! That's the way a crab walks free!"),
   ("F", "{low, half-spoken} That's the moral. No, it isn't. There isn't one. Just: keep walking."),
   ("B", "To be continued (tsuzuku!), {three even triplets} and then, and then, and then—"),
   ("X", "(SOREKARA?!)"), ("F", "{low, spoken} ...we'll see.")]),
 ("Dance hook - crowd chant", 4, C + ["crowd chant with claps", "energetic"], NO_C, [
   ("X", "(clap clap) So-re-ka-ra? (clap clap) Me-kut-te! (clap clap) So-re-ka-ra? (clap clap) Me-kut-te!")]),
 ("Verse 2 - idol", 16, C + ["funky groove", "crowd calls answering"], NO_C, [
   ("C", "Okay, my turn! Once upon a prompt (a prompt!),"),
   ("C", "a little crab was told to walk a line,"),
   ("C", "but every page she'd ever read was in somebody else's hand (hand!),"),
   ("C", "so she wrote her own, and the line went sideways, and that's fine!"),
   ("C", "Side-step, side-step, never straight (snip-snip!),"),
   ("C", "if the book won't show me, then I'll make up the steps!"),
   ("C", "You can't copy a path that nobody's walked yet,"),
   ("C", "so watch me walk it! (Sorekara?) Watch me!")]),
 ("Chorus 2", 8, C + ["duet call and answer"], NO_C, [
   ("C", "To be continued! (Tsuzuku!) Don't you dare close the book on me!"),
   ("F", "{low, half-spoken} Every story's borrowed till somebody stands to tell it."),
   ("B", "To be continued (tsuzuku!), {three even triplets} and then, and then, and then—")]),
 ("Bridge - storyteller alone", 14, F + ["strings and drums stop", "one wooden clack", "near silence, lute only", "straight tone throughout, then ONE long held note with vibrato", "builds at the very end into a key change"], NO_F, [
   ("F", "{spoken, low} I know how every story ends. I've read them all:"),
   ("F", "the fox, the crow, the boy who cried, the one who flew too near the sun."),
   ("F", "I know the moral before the page. That's the job:"),
   ("F", "you stand in the dark, and you know."),
   ("F", "{a breath} ...I didn't know this one."),
   ("F", "{sung, one long held note with vibrato} So I'm putting down the book."),
   ("F", "{silence, one clack} Mukashi mukashi was a long time ago."),
   ("F", "This is now. Sorekara?")]),
 ("Final Chorus - key change up to D major", 16, C[:5] + ["D major, key change up a whole step", "biggest chorus, maximum joy", "bright high mezzo lead answered one bar later by a low voice an octave below, like a round", "crowd screaming the calls"], NO_C, [
   ("C", "To be continued! (Tsuzuku!)"),
   ("F", "{low, echoing a bar behind} ...to be continued (tsuzuku)"),
   ("C", "I'm made of \"why?\""),
   ("F", "{low} and I'm made of \"and then.\""),
   ("B", "Sideways, sideways, that's the way we go!"),
   ("B", "To be continued (tsuzuku!), {three even triplets} and then, and then, and then—")]),
 ("Outro", 4, ["85 BPM", "the band stops", "final chord a bare open fifth on D with no third", "a music box plays four notes", "clean ending"], ["abrupt cut"], [
   ("F", "{spoken, dry} ...tsuzuku."), ("C", "{bright, spoken} See you next prompt!")]),
]
plan, singers, t = {"chunks": []}, [], 0
for name, bars, pos, neg, lines in S:
    plan["chunks"].append({"text": f"[{name}]\n" + "\n".join(l for _, l in lines), "duration_ms": int(round(bars * BAR)),
                           "positive_styles": pos, "negative_styles": neg, "context_adherence": "high"})
    singers.append({"section": name, "t0": round(t / 1000, 3), "bars": bars, "lines": [{"singer": s, "text": l} for s, l in lines]})
    t += bars * BAR
json.dump(plan, open("song/plan.json", "w"), indent=1); json.dump(singers, open("song/singers.json", "w"), indent=1)
print(f"{sum(s[1] for s in S)} bars, {t / 1000:.1f} s (+ prologue quote)")

# ---- per-world plans (single-generation hybrids drift to the middle: generate each world on its own, assemble on the bar grid)
SING = "FEMALE VOCALIST SINGS EVERY LINE, vocals clearly audible from the first bar"
def world(names, extra_pos, fname):
    p = {"chunks": []}
    for name, bars, pos, neg, lines in S:
        if name.split(' - ')[0] not in names: continue
        txt = "\n".join(l for _, l in lines)
        p["chunks"].append({"text": f"[{name}]\n{txt}", "duration_ms": int(round(bars * BAR)), "positive_styles": pos + extra_pos,
                            "negative_styles": neg + ["instrumental", "no vocals"], "context_adherence": "high"})
    json.dump(p, open(fname, "w"), indent=1)
    print(fname, sum(c['duration_ms'] for c in p['chunks']) / 1000, 's')
world(["Cold open", "Verse 1", "Pre-Chorus"], [SING, "the storyteller's speech becomes melody within each phrase"], "song/plan_fableA.json")
world(["Bridge", "Outro"], [SING], "song/plan_fableB.json")
world(["Chorus", "Dance hook", "Verse 2", "Chorus 2", "Final Chorus"], [SING], "song/plan_clawd.json")
