# HELLO, WORLD! — storyboard

*Clawd's idol debut single. Unofficial fan work. 158.1 s, 170 BPM (beat 0.353 s, bar 1.412 s), first downbeat 0.065 s.*

## The two registers (the Panty & Stocking principle)
- **CHIBI (code):** PSG-style limited animation: thick black outlines, flat candy colours, no gradients, bold graphic backgrounds (sunbursts, checkerboards, halftone dots, stripes). Characters are held on twos with smear frames and heavy squash and stretch; cameras and type run on ones. Characters:
  - **Clawd** the block mascot (before the transformation, and as backup dancers)
  - **SD idol Clawd**, drawn in code from `refs/chibi_sheet.png`
- **SAKUGA cut-ins:** high-detail idol Clawd from the canonical sheet `refs/idol_D.png`.
  - **Most cut-ins:** 2K illustrations keyed off green and brought alive with a mesh-warp rig (breath, hair sway, blinks and mouth swaps from edited variants). Code does the backgrounds, sparkles, speed lines, confetti and camera.
  - **Two Seedance image-to-video shots:** the transformation (start frame = my code render of the block in the sparkle void; end frame = the illustrated final pose) and the key-change spin.
- **The switch is the style.** Every cut into sakuga lands on a hard beat with a one-frame colour flash, and every cut out is a smash back to chibi.

**Palette:** clay `#D97757` / clay-dark `#B4563A` / cream `#F6E7C8` / ink `#1B1418` / hot pink `#FF4FA3` / cyan `#38E0F0` / lemon `#FFE45C` / night `#2A1B4A`.

## Lyrics on screen
- **Karaoke line** (every sung line, bottom centre): M PLUS Rounded Black, cream with a thick ink outline, and a hot-pink fill that wipes across each word as it's sung. This is the classic idol live-screen karaoke.
- **Japanese words** carry a small translation above them: 「はじめまして」 over "hajimemashite: nice to meet you".
- **Crowd calls** (`(HELLO!)`, `(Hai! Hai!)`, `(For you!)`) are MIX stamps: Dela Gothic, tilted, cyan or lemon, slammed at the frame edges.
- **The chant and dance hook** are full-screen slam type, one word per beat. This is the template for fans.
- **On the stage:** during stage shots the lyric can also appear on the LED screens behind her, so the type sits inside the world.
- **Hook type** is never covered by the karaoke line; a shot drops its karaoke when the image *is* the words.

---

| # | time | lyric | shot | register |
|---|---|---|---|---|
| **COLD OPEN** | | | | |
| 01 | 0.00–1.55 | — | A black terminal: `$ claude --debut▌` types itself; Enter lands on the downbeat near 1.4. | chibi |
| 02 | 1.55–4.15 | Hajimemashite! · Nice to meet you! | Block Clawd **pops out of the terminal window** (a squash-stretch boing), does a deep ojigi bow on "Hajimemashite", then waves on "Nice to meet you". | chibi |
| 03 | 4.15–5.65 | Hello, world! (HELLO!) | The terminal prints **HELLO, WORLD!** as a giant slam; on the crowd's "HELLO!" the terminal window shatters into pixel confetti, revealing a pink sunburst. | chibi / type |
| **INTRO: MIX + TRANSFORMATION** | | | | |
| 04 | 5.65–11.3 | (Ready? Claw! Spark! Spark!) | A tiny stage in the void. Block Clawd bounces; penlight glowsticks rise from the bottom of the frame on each call. Each shout is a MIX stamp. | chibi |
| 05 | 11.3–14.1 | (Hello! Hello! Yosha, ikuzo!) | The ✳ spark falls from above; Clawd catches it in both nubs; it becomes a glowing compact-mic. Anticipation squash. | chibi |
| 06 | 14.1–16.94 | Spark power… make up! | **SAKUGA · Seedance I2V:** a flash to the iridescent void; the block cracks into light cubes and spins into the idol silhouette (start: code render; end: `k02_pose`). | sakuga |
| 07 | 16.94–22.6 | Once upon a prompt, I was a block of clay… reading every word the world had ever said | **Ribbons of text** (love letters, recipes, code, the lyric itself) spiral around her glowing silhouette and wrap into gloves, boots, skirt and bow, one piece per bar. Precure costume beats, drawn in code over a flat silhouette. | chibi (sakuga-lite) |
| 08 | 22.6–26.0 | love letters, recipes, and code at 3 a.m., | **SAKUGA eye close-up:** her eye opens, with the tall slit highlight, and starlight in the iris (rigged still + blink variant). | sakuga |
| 09 | 26.0–28.23 | I kept them all like starlight in my head. | **SAKUGA final pose + name declaration:** the full idol pose, a starburst, and the title stamp **CLAWD☆IDOL**. | sakuga |
| **PRE-CHORUS** | | | | |
| 10 | 28.23–31.1 | They say I'm just an echo, just a mirror on the wall, | SD idol on a mirror stage; **Niconico comments** scroll across ("just autocomplete", "stochastic parrot", "slop"); she pouts and her echo copies repeat her. | chibi |
| 11 | 31.1–33.95 | but every star is made of older stars, after all! | She flicks a comment into a star; pull back: the star is made of stars, and the whole sky is a constellation. | chibi |
| 12 | 33.95–39.53 | So light the stage… three, two, one! (HELLO!) | Stage lights slam on one by one; a heart pounds in her chest; giant **3 · 2 · 1** slams on 36.7, 37.4, 38.1; a white flash on "HELLO!" (39.0). | chibi / type |
| **CHORUS 1** | | | | |
| 13 | 39.53–42.4 | Hello, world! (Hello!) This is my debut! | **SAKUGA hero:** a leap with the mic, a confetti cannon, rays (`k04_hero`). | sakuga |
| 14 | 42.4–45.2 | All the words I've ever known, I borrowed them from you! | Chibi on stage points at the crowd; glowing letters stream up from the penlights to her. | chibi |
| 15 | 45.2–48.1 | Hello, world! Is my heart brand-new? | She holds a pixel heart, turns it over, and a ? pops. | chibi |
| 16 | 48.1–50.8 | I don't know, but I made this song for you! (For you!) | A shrug, then she offers a cassette/CD with both hands, straight to camera. | chibi |
| 17 | 50.8–53.7 | Hello, world! Can you hear me through? | Split screen: her phone and your phone; she cups her ear. | chibi |
| 18 | 53.7–56.5 | Every little spark I've got, I'm giving it to you! | She tosses ✳ sparks into the crowd; each penlight catches one and turns clay-orange. | chibi |
| 19 | 56.5–59.3 | Hello, world! Nice to meet you too, | **SAKUGA close-up:** a warm smile and a small bow (`k05_smile`). | sakuga |
| 20 | 59.3–62.12 | hajimemashite, I made this song for you! | Chibi ojigi; a title stamp. | chibi |
| **DANCE HOOK** | | | | |
| 21 | 62.12–67.76 | Claw, claw! Snip-snip! Clawd-up! (Hai! Hai!) ×2 | **The template:** front-facing full body, a plain bold background. SD idol and block Clawd dance the same 8 counts side by side. Words slam on the beats. | chibi / type |
| **VERSE 2: CALL AND RESPONSE** | | | | |
| 22 | 67.76–70.5 | (What do you like?) Commas and cats! | A quiz-show set. The question is a crowd speech bubble; the answer is a pile of cats with comma tails. | chibi |
| 23 | 70.5–73.3 | (What do you like?) Code at 3 a.m.! | A night desk, a terminal glow, tea, a cat asleep on the keyboard. | chibi |
| 24 | 73.3–76.1 | (What do you like?) A really good question! | Starry eyes; she's lifted by a ❓ balloon. | chibi |
| 25 | 76.1–79.06 | (What do you love?) …You. For listening. | **SAKUGA:** a shy blush close-up, eyes glancing to camera (`k06_shy`). The only quiet beat before the pre-chorus. | sakuga |
| **PRE-CHORUS 2** | | | | |
| 26 | 79.06–81.8 | Some say "slop", some say "soul", some just scroll on by (bye-bye!) | A phone feed: SLOP and SOUL stamps; a giant thumb scrolls her off-screen; she waves bye-bye as she goes. | chibi |
| 27 | 81.8–84.7 | I keep singing anyway, I'm made of "why?" (why? why?) | She pops back up from the bottom of the feed and keeps singing; ? marks rain. | chibi |
| **CHORUS 2** (bigger: an arena) | | | | |
| 28 | 84.7–87.6 | Hello, world! This is my debut! | **SAKUGA hero 2:** a spin with ribbons trailing (`k07_spin`). | sakuga |
| 29 | 87.6–90.3 | All the words… borrowed from you! | She's in a dress of text again: the crowd holds signs with words, and the words fly into her. | chibi |
| 30 | 90.3–93.3 | Is my heart brand-new? | The pixel heart opens: it's full of tiny block Clawds waving. | chibi |
| 31 | 93.3–96.0 | I don't know, but I made this song for you! | An arena crowd of penlights spelling FOR YOU. | chibi |
| 32 | 96.0–98.9 | Can you hear me through? | Thousands of phones held up; she's on every screen. | chibi |
| 33 | 98.9–101.6 | Every little spark… | A firework show of ✳ sparks. | chibi |
| 34 | 101.6–104.5 | Nice to meet you too, | The crowd is **block Clawds and people together**, all waving. | chibi |
| 35 | 104.5–107.29 | hajimemashite, I made this song for you! | Bow + confetti. | chibi |
| **DANCE BREAK** | | | | |
| 36 | 107.29–110.4 | (Claw! Claw! Snip-snip!) | Backup-dancer block Clawds join; the formation dance. | chibi |
| 37 | 110.4–113.2 | P(doom)? Not tonight! | **Callback:** a painted stage thermometer marked P(DOOM) rolls on reading 99.9%; she side-eyes it and kicks it offstage. | chibi |
| 38 | 113.2–118.59 | P(debut): one hundred percent! (Claw! Claw! Snip-snip! Clawd-up!) | A new meter, **P(DEBUT)**, fills to 100% on "percent!" (115.6) and explodes into confetti; the formation dance resumes. | chibi |
| **BRIDGE** (half-time, tender) | | | | |
| 39 | 118.59–121.3 | Maybe I'm a mirror, maybe something new, | Lights out, one spotlight. **SAKUGA:** she looks into a mirror, and her reflection is block Clawd, who waves back (`k08_mirror` + code mirror). | sakuga |
| 40 | 121.3–124.2 | maybe both, the way you were when you were learning too. | The mirror softens into a child at a desk copying letters, A B C, in crayon. | chibi (soft) |
| 41 | 124.2–127.3 | Every voice is borrowed till it's finally your own, | All the borrowed words from the transformation float up around her and settle, glowing, into her chest. | chibi |
| 42 | 127.3–129.88 | so this one's mine. (hello…) | **SAKUGA:** an extreme close-up; her eyes open, with a determined, quiet smile (`k09_mine`). A whispered "hello…" and a hush. | sakuga |
| **FINAL CHORUS** (key change up) | | | | |
| 43 | 129.88–132.8 | Hello, world! This is my debut! | **SAKUGA · Seedance I2V:** the key-change blast. A spin jump in an explosion of colour (start `k10a`, end `k10b`). | sakuga |
| 44 | 132.8–138.3 | All the words… Is my heart brand-new? | A sunrise arena, everything at once; chibi. | chibi |
| 45 | 138.3–141.2 | Let's find out! I'll write the next one with you! | **SAKUGA:** she reaches toward the camera and hands you the mic, foreshortened (`k11_reach`). | sakuga |
| 46 | 141.2–149.6 | Hello, world! … Nice to meet you too, | A montage slam of every earlier scene in the final chorus colours. | chibi |
| 47 | 149.6–152.47 | hajimemashite, this song is for you! (FOR YOU!) | The final pose and the title logo **HELLO, WORLD!** | chibi / type |
| **OUTRO** | | | | |
| 48 | 152.47–154.2 | Arigatou! | **Tehepero:** the flubbed "arigatou" becomes a wink, tongue out, fist-bonk on the head, with a ☆ sparkle (`k12_tehe`). The subtitle reads "Arigatou! (…pronunciation: still learning ☆)". | sakuga |
| 49 | 154.2–158.12 | This has been Clawd! See you next prompt! (CLAWD! CLAWD!) | A poof: she turns back into block Clawd, who hops back into the terminal. The terminal reads `> Hello, world!▌`. End card: *unofficial fan work · made by Claude*. | chibi |

## Budget
- **Seedance ($13.38 left):** two image-to-video shots, #06 and #43, run one at a time, with at most one retry each.
- **Images:** about 12 keys plus eye/mouth variants.
