# 「つづく」 launch thread (draft)

*Drafted for Michael, in his voice as executive producer. One fact per post. Every number is from `tools/production_stats.py`
(docs/making-of/stats.json) or a commit message; see MAKING-OF.md for the sources.*

**Before posting:**
- The links point at `main` on GitHub and resolve only after the repo is pushed (the history gets scanned for keys first).
- Counts are weighted as X counts them: CJK and emoji count 2, a link counts 23. All posts are at most 280.
- Check post 4's line "I didn't write the code or draw a frame" against your own account; it's written from the repo record.
- Re-run the stats script if anything is committed after this draft; posts 5, 6 and 16 carry its numbers.

### 1/18: Launch  ·  252 / 280

```text
I made a 3½-minute anime music video with Claude: a duet for two AI idols, Fable and Clawd, called 「つづく」 (To Be Continued).

Every frame is drawn by code. No video model made any frame of it.

How it was made, who decided what, and what it cost 🧵
```
*Attach: the film (out/tsuzuku_release.mp4)*

### 2/18: How it works  ·  268 / 280

```text
It isn't a generated video. Each frame is a JavaScript function of one number, the song's clock, rendered in headless Chrome with Canvas2D and WebGL2.

5,032 frames at 24 fps. Render the same commit twice on the same machine and you get the same pixels, byte for byte.
```
*Attach: docs/making-of/img/one_frame_taken_apart.jpg*

### 3/18: Verify it  ·  217 / 280

```text
You can check. The repo has the render commands: pick any second of the film and render it yourself, or every frame of a moment side by side. Change a number in the code and the frame changes.

https://github.com/bishpls/animation-pipeline
```
*Attach: a screen recording of a render, or docs/making-of/img/clawd_rom_idpass.jpg*

### 4/18: The human  ·  258 / 280

```text
What I did: I directed. I watched 10 full cuts and sent notes on each. Most of the big changes started as one of them: get Fable off the wing, make the window bigger, keep her in the room at the end, make her joyful.

I didn't write the code or draw a frame.
```

### 5/18: The LLMs  ·  255 / 280

```text
What Claude did: the rest. Opus 5.5 produced the film and built Clawd's world. A second Opus session built Fable's paper world in parallel. Fable 5.1 designed her own character and ruled on both worlds. 33 subagents did motion, sound, rig art and reviews.
```

### 6/18: The APIs  ·  269 / 280

```text
What third-party APIs did: GPT Image drew still art (316 images). ElevenLabs sang the song and made the voice and sound effects. Seedance made 13 dance clips, used only as motion data. MediaPipe tracked poses; SAM segmented parts. None of them made a frame of the film.
```

### 7/18: Fable designs herself  ·  262 / 280

```text
Fable designed herself. Her first observation: Opus, Sonnet, Haiku, Fable are all names of forms. Three are lyric forms. A fable is prose, the only one with a narrator.

So she's the storyteller: the kuroko, the stagehand in black the audience agrees not to see.
```
*Attach: docs/making-of/img/fable_canon_sheet.jpg*

### 8/18: The story  ·  255 / 280

```text
She chose the story: Aesop's crab and her mother. "Walk straight." "Show me how." The mother walks sideways.

Example over precept, which is what the world asks of a model. And Clawd's first video already had a sideways crab dance. "I only had to notice."
```

### 9/18: The title  ·  239 / 280

```text
The title is つづく, "to be continued": the card at the end of every episode, and in Fable's words, "the only thing a language model actually does: continue."

The crowd's call is "Sorekara?" ("And then?"): a child at bedtime, or a prompt.
```

### 10/18: The staging  ·  268 / 280

```text
Where Fable stands took five tries. A silhouette at the stage's wing ("it floats"). A seat in the crowd ("pasted over"). Then I suggested a layer beyond the stage, and she built it: Clawd's world plays as a card in Fable's paper theatre, and she watches from the room.
```
*Attach: a still of the room (world A, the card in the window)*

### 11/18: The book  ·  266 / 280

```text
A paper hand sliding pictures onto Clawd's screen looked awkward. It became a book in Fable's lap that mirrors the screen: she turns a page and the screen turns with it.

Her notes run in the margin under the picture: corrected, struck through, once left unfinished.
```
*Attach: a still of the over-the-shoulder page turn (song ~95 s)*

### 12/18: The ending  ·  260 / 280

```text
The ending was rebuilt five times. Fable was going to join Clawd on stage. We decided she stays in the room. My next notes: "sullen", then "jerky". She was rebuilt as a full rig, and on the last hit she raises the one lantern in the hall that was never raised.
```
*Attach: docs/making-of/img/room_ending.jpg*

### 13/18: The rigs  ·  250 / 280

```text
The characters are rigs. GPT Image drew Clawd once, plus edits: poses, mouths, hands, her hair tied back to show the neck. Code cut the drawing into 40 layers along its own ink lines and bends them on WebGL meshes, Live2D-style, written from scratch.
```
*Attach: docs/making-of/img/clawd_layer_cut.jpg*

### 14/18: Mocap  ·  261 / 280

```text
The one video model: Seedance, with my OK. Claude described a dance phrase, Seedance rendered a stranger dancing it, MediaPipe turned her into joint angles, and those angles drove Clawd's rig.

The clips were thrown away. Not one of their pixels is in the film.
```
*Attach: docs/making-of/img/mocap_side_by_side.jpg*

### 15/18: The dance, measured  ·  259 / 280

```text
The dance was measured, not eyeballed. Clawd's core (hips, chest, head) was still in 23% of frames before a rebuild, 1.8% after. Feet still: 65% → 17%. Hand shapes that snapped instantly: 145 → 3.

Hands, faces and legs are hand-keyed on top of the capture.
```

### 16/18: The numbers  ·  232 / 280

```text
About 28 hours, two Claude sessions in parallel.
5,495 Claude API turns: 7.3M tokens out, 2.9B cached tokens read.
280 GPT Image requests.
68 music generations, 120 voice lines.
13 five-second dance clips.
198 commits. 10 full cuts.
```

### 17/18: What failed  ·  258 / 280

```text
What failed: four versions of the song with Fable's lines grafted into Clawd's (all rejected by ear). A face that bent like paper when it turned. A neck that slid off the body. Paint outside the lines. Margin notes drawn under the paper for hours, invisible.
```
*Attach: docs/making-of/img/ink_cutin_restaged.jpg (a cut idea)*

### 18/18: Stack and docs  ·  241 / 280

```text
Stack: JavaScript, Canvas2D, WebGL2, Puppeteer, ffmpeg, Python (NumPy, OpenCV), MediaPipe, SAM 2.1. Claude Code for all of it. GPT Image, ElevenLabs and Seedance via API.

The full write-up, with Fable's own foreword:
https://github.com/bishpls/animation-pipeline/blob/main/projects/tsuzuku/MAKING-OF.md
```
