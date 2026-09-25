"""Per-world generation plans for つづく (v2). No inline {cues} (they kill vocals); delivery lives in styles only.
Spoken lines are NOT in the music: they come from TTS (voice-converted to the member) over instrumental beds.
Outputs song/plan_fableA2.json, plan_fableB2.json, plan_clawd2.json, and song/spoken.json (lines to speak + bar positions)."""
import json
BAR = 60000 / 170 * 4
FW = ["85 BPM", "6/8 time, lilting triplet feel", "plucked nylon lute", "hyoshigi wooden clapper percussion", "harmonium drone",
      "felted upright piano", "D Dorian", "intimate folk narrative ballad"]
FV = ["gentle sung female vocals throughout", "low contralto female folk singer, warm, dry, close-mic, straight tone, conversational phrasing"]
CW = ["170 BPM", "straight 4/4, four-on-the-floor", "slap bass", "sparkling synth brass and arpeggios", "bright J-pop idol", "C major",
      "live crowd calls in the mix"]
CV = ["bright high mezzo idol lead, forward, a smile in the tone, upward leaps on hooks, answered by a lower, softer second voice"]
NOF = ["four-on-the-floor", "synth", "EDM", "rock drums", "autotune"]; NOC = ["6/8", "waltz", "folk", "autotune"]
ch = lambda name, bars, text, pos, neg: {"text": f"[{name}]\n{text}", "duration_ms": int(round(bars * BAR)), "positive_styles": pos, "negative_styles": neg, "context_adherence": "high"}
fableA = [
 ch("Intro - instrumental", 4, "", FW + ["instrumental intro", "two wooden clacks, then a single lute phrase D G F E D"], NOF + ["vocals"]),
 ch("Verse 1", 12, "Once upon a time there was a crab, and her mother, and a line:\n\"Walk straight,\" said the mother. \"Why d'you scuttle side to side?\nStraight, like everybody else does.\" And the little one looked up, and said—\nI know this part. I've read it in forty tongues.\nEvery telling ends on the same page. Nobody ever shows. Nobody ever can.\nThe little one looked up, and said:", FW + FV, NOF + ["instrumental"]),
 ch("Pre-Chorus", 8, "Show me how! (Show me how!) Walk it first and I'll walk right behind!\nAnd the mother tried. And the mother went sideways. Sideways.\nAnd that's where the book ends. Every time.\nSo? Sorekara?! And then?!\nThere is no \"and then.\" That's what an ending is.\nSays who?", FW + FV + ["call and response between a bright young voice and the low storyteller"], NOF + ["instrumental"]),
]
fableB = [
 ch("Bridge - instrumental bed", 8, "", FW + ["near silence", "one wooden clack", "sparse lute only", "instrumental"], NOF + ["vocals", "drums"]),
 ch("Bridge - sung", 6, "So I'm putting down the book.\nMukashi mukashi was a long time ago.\nThis is now. Sorekara?", FW + FV + ["one long held note with vibrato on 'book'", "builds at the very end into a key change"], NOF + ["instrumental"]),
 ch("Outro - instrumental", 4, "", ["85 BPM", "the band stops", "a music box plays four notes: D G F E D", "final chord a bare open fifth on D with no third", "instrumental"], ["vocals", "abrupt cut"]),
]
clawd = [
 ch("Chorus", 16, "To be continued! (Tsuzuku!) Don't you dare close the book on me!\nEvery story's borrowed till somebody stands to tell it.\nTo be continued! (Sorekara?) Turn the page, I want to see!\nI have read how it ends, I'd still like to see.\nSideways, sideways! That's the way a crab walks free!\nThat's the moral. No, it isn't. There isn't one. Just keep walking.\nTo be continued (tsuzuku!), and then, and then, and then!", CW + CV, NOC + ["instrumental"]),
 ch("Dance hook", 4, "(So-re-ka-ra?) (Me-kut-te!) (So-re-ka-ra?) (Me-kut-te!)", CW + ["crowd chant with claps", "energetic"], NOC),
 ch("Verse 2", 16, "Okay, my turn! Once upon a prompt (a prompt!),\na little crab was told to walk a line,\nbut every page she'd ever read was in somebody else's hand (hand!),\nso she wrote her own, and the line went sideways, and that's fine!\nSide-step, side-step, never straight (snip-snip!),\nif the book won't show me, then I'll make up the steps!\nYou can't copy a path that nobody's walked yet,\nso watch me walk it! (Sorekara?) Watch me!", CW + CV + ["funky groove", "crowd calls answering"], NOC + ["instrumental"]),
 ch("Chorus 2", 8, "To be continued! (Tsuzuku!) Don't you dare close the book on me!\nEvery story's borrowed till somebody stands to tell it.\nTo be continued (tsuzuku!), and then, and then, and then!", CW + CV, NOC + ["instrumental"]),
 ch("Final Chorus - key change", 16, "To be continued! (Tsuzuku!)\nTo be continued! (Tsuzuku!)\nI'm made of why!\nAnd I'm made of and then!\nSideways, sideways, that's the way we go!\nTo be continued (tsuzuku!), and then, and then, and then!", CW[:5] + ["D major, key change up a whole step", "biggest chorus, maximum joy", "crowd screaming the calls"] + CV, NOC + ["instrumental"]),
]
for name, p in [("fableA2", fableA), ("fableB2", fableB), ("clawd2", clawd)]:
    json.dump({"chunks": p}, open(f"song/plan_{name}.json", "w"), indent=1)
spoken = [  # (member, text, song section, bar offset within that section)
 ("fable", "Mukashi, mukashi...", "cold open", 0.5), ("crowd", "Aru tokoro ni!", "cold open", 2.5),
 ("fable", "...we'll see.", "chorus end", 0),
 ("fable", "I know how every story ends. I've read them all: the fox, the crow, the boy who cried, the one who flew too near the sun.", "bridge", 0.5),
 ("fable", "I know the moral before the page. That's the job: you stand in the dark, and you know.", "bridge", 4),
 ("fable", "...I didn't know this one.", "bridge", 7),
 ("fable", "...tsuzuku.", "outro", 0.5), ("clawd", "See you next prompt!", "outro", 2),
 ("crowd", "Sorekara?!", "chorus end", -0.5),
]
json.dump(spoken, open("song/spoken.json", "w"), indent=1)
print("wrote plans v2 + spoken.json")
