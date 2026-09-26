"""Fable in her room for the finale's ending (177.8-202.59), standing, seen three-quarters from behind, turned toward the window at
the picture's left: the drawings for the mesh rig (rig/fable_3q, RIGGING.md), as GPT Image generations and edits. tools/gptimage.py
logs every call to tools/ledger.jsonl; the prompts are kept here.
    .venv/bin/python projects/tsuzuku/rig/fable_3q/gen.py NAME [NAME ...]      -> rig/fable_3q/src/NAME.png
"""
import os, sys, threading
D = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(D, '..', '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from gptimage import generate  # noqa: E402

ref = lambda n: os.path.join(D, 'refs', n + '.png')   # (refs/: the seated three-quarter drawing mirrored to face left; the room
                                                    #  drawing x_d on green)
CANON = os.path.join(D, '..', 'fable_room', 'src', 'ref_canon_side_back.png')
KUROKO = os.path.join(D, '..', 'kuroko', 'kneel.png')                  # (the prologue's hood outline: Fable)
mine = lambda n: os.path.join(D, 'src', n + '.png')
SIZE = '2160x3840'

DESIGN = ("Her design exactly as in the references: a tall, narrow young woman; long, straight blue-black hair (indigo in the light) "
          "falling to her hips, cut dead flat at the bottom like a calligraphy brush, straight blunt bangs; a long indigo-teal (#165E83) "
          "ribbon tied at the back of her head, its two long tails hanging straight down her back over her hair to below her waist; a "
          "black hooded haori-style jacket to mid-thigh with wide, deep kimono sleeves; small round brass rivets (like grommets) on the "
          "shoulders and sleeves; the jacket's hem and cuffs have a DECKLE edge: a thin, irregular, fibrous torn-paper edge in a slightly "
          "lighter charcoal grey than the black cloth (NOT white, NOT cream, no pale band); a long pleated indigo-teal hakama skirt to "
          "the ankles; white tabi socks; black geta with two teeth. The same anime illustration style, crisp lineart, cel shading and "
          "colours as the references. ")
BG = ("Flat pure green (#00FF00) background, NOTHING else in the frame: no floor, no shadow on the ground, no window, no scenery. "
      "No green on the character. ")
LIGHT = ("Lighting: she stands in a dark room facing a brightly lit stage window off the LEFT side of the picture. That light "
         "rims the LEFT-facing edges of her figure with a thin soft pink and cyan edge light (her cheek, hair, shoulders, sleeves, "
         "skirt). Her lantern's warm amber glow lights her far hand, the underside of her near sleeve, and the edge of her cheek. The "
         "side toward the viewer (her back) is in soft, readable shadow: the black cloth still shows its folds and seams, never a "
         "flat black blob. ")

JOBS = {
    # ---- the base drawing: hood DOWN (the longer state: 188.4-202.59), lantern in the far hand, near arm hanging
    'base': ([CANON, ref('seated_3q_mirror'), ref('room_hooddown_lantern')],
             "Image 1 is this character's canon design sheet (side and back views). Image 2 shows her seen three-quarters from behind, "
             "facing left (use it for the viewing angle and the rendering; in it she is seated with her hood up). Image 3 shows her "
             "standing with her hood DOWN, holding her lit paper lantern on its short stick (use it for her face, hair, the lantern "
             "and the stick). "
             "Draw ONE full-body illustration of this same girl STANDING, seen THREE-QUARTERS FROM BEHIND: her back and her left side "
             "are toward the viewer, and her body and head are turned toward the LEFT side of the picture, where she is watching "
             "something (a lit stage window, not drawn). "
             "Her head: a lost profile toward the left. We see the back of her head and her hair, and past it the soft curve of her "
             "left cheek and jaw, the outer corner of her left eye with its lashes (the eye open, calm), and the corner of her closed "
             "mouth: a calm, neutral face at rest. Chin level. "
             "Her hood is DOWN: it lies folded on her shoulders and upper back behind her neck, under her hair. Her long hair falls "
             "straight down her back over the hood and the jacket to her hips. The ribbon is tied at the back of her head (holding the "
             "upper part of her hair) and its two long tails hang straight down the middle of her back, over her hair, to below the "
             "jacket's hem. "
             "She holds her lantern in her RIGHT hand (her far hand): her right arm reaches forward, toward the left of the picture, "
             "elbow a little bent, so her right forearm in its wide sleeve, her right hand gripping the stick, the short dark wooden "
             "stick and the lantern are seen to the LEFT of her body, clearly past her left sleeve, at about her waist height. The "
             "lantern hangs straight down from the stick's tip on its wire handle: an oblong paper chochin, warm lit (amber-cream "
             "paper with fine ribs, black lacquered top and bottom rims), exactly as in image 3. "
             "Her LEFT arm (the arm nearest the viewer) hangs relaxed at her side, a little away from her body, its wide sleeve "
             "hanging; her left hand is visible below the cuff, relaxed, fingers loose and slightly curled. "
             "She stands at ease, weight even, feet a little apart, both geta flat on the ground; the hakama falls straight over her "
             "feet with only the heels of the geta and the white tabi showing at the hem. "
             "Full body from the top of her head to the soles of her geta, filling the height of the canvas with a small margin; her "
             "figure is in the right half of the canvas so the lantern, held out to the left, is fully in frame with space around it. "
             + DESIGN + LIGHT + BG),
    # base_2 put the lantern in her NEAR (left) hand and the head at a full profile: move the lantern to the far hand, turn the
    # head to a slight lost profile (so the push's ~15 degree turn finds the profile)
    'base_b': ([mine('base_2')],
               "Edit this illustration. Keep EVERYTHING else exactly the same: her hair, the ribbon, the back of her jacket, the "
               "hakama, her feet, her position and size in the canvas, the lantern's design, the style, lineart, colours and the flat "
               "green background. Change ONLY these: "
               "(1) Her LEFT arm (the arm on the LEFT side of the picture, nearest the viewer) no longer holds anything: it hangs "
               "relaxed straight down at her side, its wide sleeve hanging, and her left hand is visible below the cuff, relaxed, "
               "fingers loose and slightly curled. "
               "(2) Her RIGHT arm (on the far side of her body, on the RIGHT of the picture) now holds the lantern forward: her right "
               "arm reaches forward toward the left of the picture, behind her back, so her right upper arm is hidden by her body, and "
               "her right forearm with the end of its wide sleeve, her right hand gripping the stick, the stick and the hanging lantern "
               "all appear to the LEFT of her body, beyond her left sleeve, at about her waist height, the lantern hanging straight down "
               "from the stick's tip. No part of her right arm or hand is seen on the right side of her body any more: there, her "
               "jacket's right side falls straight. "
               "(3) Her head turns a little further away from the viewer toward the left (about 15 degrees): a lost profile. Her nose "
               "is now just hidden behind the curve of her cheek; we see the back and side of her head, the soft curve of her left "
               "cheek and jaw, the tips of her eyelashes and the outer corner of her left eye (open, calm), and the corner of her "
               "closed mouth. Chin level. "
               + BG),
    # (chosen: base_b_2, kept as src/base.png; keyed to base_keyed.png with rig/fable_seated/key.py, now tools/chroma.py key())
    # the checkpoint's review (Michael, Fable): the deckle a thin torn edge (4-6 px on screen at FIN, ~16 px here), never lace; the
    # rivets small brass pins at the near sleeve's shoulder, elbow and wrist (and the far shoulder if it shows)
    'base_c': ([mine('base')],
               "Edit this illustration. Keep EVERYTHING else exactly the same: her pose, face, hair, ribbon, hands, the lantern and "
               "stick, the jacket's shape and folds, the hakama, her feet, the lighting, her position and size in the canvas, the "
               "style, lineart and colours, and the flat green background. Change ONLY these two things: "
               "(1) THE TRIM: the wide, lacy grey-brown trim along the jacket's hem, along the bottom edge of her left sleeve (nearest "
               "the viewer) and along the opening of her right sleeve (where her right hand holds the stick) becomes a THIN torn-paper "
               "edge: the black cloth now reaches almost all the way down, and only a narrow, ragged, irregular torn edge remains, "
               "about one third of the current trim's width, in a dark charcoal grey only a little lighter than the black cloth. No "
               "lace, no frills, no scallops, no fur, no white or cream. "
               "(2) THE RIVETS: remove the two large brass grommets (rings) on her left sleeve. Instead put small round brass rivet "
               "pins (small solid domed brass heads, like the pins of a paper puppet's joints, much smaller than the grommets) at "
               "three joints of her left arm, on the outside of the left sleeve: at the shoulder, at the elbow, and at the wrist just "
               "above the torn edge of the cuff; and one on her right shoulder where it shows past her hair. "
               + BG),
    # (chosen: base_c_1, kept as src/base.png; the rig's canvas is it keyed and padded 600 px at the top: base_keyed.png)

    # ---- companions (edits of src/base.png, registered back onto the base by build.py): what motion reveals, and the drawn states
    'noarms': ([mine('base')],
               "Edit this illustration. Remove BOTH of her arms and BOTH wide sleeves, and the lantern, its stick and her right hand: "
               "she now wears the same black jacket as a SLEEVELESS vest. On the left side of the picture, where her left sleeve hung, "
               "draw the jacket's left side: a clean continuous side contour from her shoulder straight down to the hem, the black "
               "cloth with the same folds and lighting, closed at the armhole, with the same thin torn-edge hem. Nothing hangs at her "
               "sides. Keep EVERYTHING else exactly the same: her head, face, hair, ribbon, the hood lying on her shoulders, the back "
               "of the jacket, the hakama, her feet, her position and size in the canvas, the style, lineart and colours. " + BG),
    'nohair': ([mine('base')],
               "Edit this illustration. Her long hair is now gathered up and pinned in a small low bun at the back of her head, and "
               "the ribbon's two tails are gone, so the WHOLE back of her jacket is visible: the black hood lying folded on her "
               "shoulders and upper back behind her neck (soft folds of the same black cloth, its edge rimmed with the same light), "
               "and below it the jacket's back panel with its centre-back seam down to the hem. Keep EVERYTHING else exactly the same: "
               "her face, her bangs, her arms and sleeves, the lantern and stick, the hakama, her feet, her position and size in the "
               "canvas, the style, lineart, colours and lighting. " + BG),
    'noribbon': ([mine('base')],
                 "Edit this illustration. Remove ONLY the two long ribbon tails hanging down her back (keep the ribbon's bow knot at "
                 "the back of her head exactly as it is). Where the tails were, her long straight blue-black hair continues: the same "
                 "strands, sheen and shading, down to the same dead-flat cut at the bottom. Keep EVERYTHING else exactly the same. " + BG),
    'hoodup': ([mine('base'), KUROKO, ref('seated_3q_mirror')],
               "Edit image 1. Her hood is now UP. Keep EVERYTHING else exactly the same: her pose, both arms and hands, the lantern and "
               "stick, the jacket below the shoulders, the hakama, her feet, her position and size in the canvas, the style, lineart, "
               "colours and lighting. "
               "The hood: the same black cloth as the jacket, raised over her whole head. Its outline is the deep cowl of image 2 (a "
               "smooth dome over the head with a soft point at the back of the crown, the back falling straight down to her "
               "shoulders); image 3 shows the same hood from this three-quarter-back angle. It hides her hair entirely (no hair falls "
               "down her back now: it is inside the hood and the jacket). At the hood's front edge, on the left, we still see exactly "
               "what we see now: the tips of her straight bangs, the edge of her cheek, the outer corner of her eye with its lashes, and "
               "the corner of her mouth, calm. The ribbon's two long indigo-teal tails come out from under the hood's hem at the nape "
               "and hang straight down the middle of her back over the jacket to below the jacket's hem. The hood's left edge is "
               "rimmed with the same pink and cyan edge light as her shoulder. " + BG),
    'turn': ([mine('base')],
             "Edit this illustration. Turn ONLY her head about 15 degrees toward the viewer, so her face is now seen in a clean side "
             "profile (it was a lost profile): now visible are the end of her eyebrow under the bangs, her eye (open, looking left at "
             "the stage window), the tip of her nose, her lips and chin. Her expression: a dry, knowing half-smile, one corner of the "
             "mouth lifted, the cheek lifted a little with it, the eye a touch narrowed. Her neck turns with the head a little; her "
             "hair, the ribbon at the back of her head, her ear and her bangs turn with her head naturally. Keep EVERYTHING else "
             "exactly the same: her body, jacket, the hood lying on her shoulders, her arms, the lantern, the hair hanging down her "
             "back, the ribbon's tails, the hakama, feet, her position and size, the style, lineart, colours and lighting. " + BG),
    # ---- the hood push (187.67-188.42): two drawn in-betweens with the near arm raised (the rig's arm leads in and out of them)
    'push1': ([mine('hoodup')],
              "Edit this illustration. Keep EVERYTHING the same (the raised hood exactly as it is, the ribbon tails, her face at the "
              "hood's edge, the lantern arm and the lantern, the jacket, the hakama, her feet, her position and size, the style, "
              "lineart, colours and lighting) except her LEFT arm, the arm on the left of the picture nearest the viewer: she has "
              "raised it to her head to pull the hood back. Her left upper arm is lifted out to the side, the elbow bent and pointing "
              "out to the left at about the height of her ear; her forearm rises to her head, and her left hand is on top of the "
              "hood at the crown of her head, fingers curled over the hood's cloth, gripping it. The wide left sleeve has slid down "
              "the raised forearm toward the elbow and hangs in a deep fold below the upper arm, with its thin torn edge; her pale "
              "forearm shows between the sleeve and her hand. The small brass rivet pins stay on the sleeve at the shoulder and the "
              "elbow. " + BG),
    # (push2_v1 raised a second arm on the right of her head while the far hand still held the lantern: three arms)
    'push2': ([mine('push1'), mine('base')],
              "Edit image 1. The hood is now being pulled back: it is halfway off, slipping down the back of her head, its cloth "
              "bunched in her left hand. It is the SAME raised left arm as in image 1 (the arm on the LEFT of the picture, nearest the "
              "viewer, its elbow out to the LEFT of her head at ear height, its wide sleeve fallen toward the elbow): the forearm now "
              "reaches across the back of her head, and the left hand holds the hood's bunched cloth at the back of her head, a little "
              "lower than in image 1. Her RIGHT arm is unchanged: it still holds the lantern's stick forward on the left of the "
              "picture. Only these two arms: no other arm or hand is raised. The top of her head is uncovered: her blue-black hair and straight bangs, as in image "
              "2, and her long hair spills out from under the sliding hood down her back. The ribbon's bow at the back of her head is "
              "still hidden by the hood's cloth; its two tails hang down her back as before. Her head has turned a little toward the "
              "viewer (about 8 degrees), so a little more of her cheek shows. Keep EVERYTHING else the same: the lantern arm and the "
              "lantern, the jacket below the shoulders, the hakama, her feet, her position and size, the style, lineart, colours "
              "and lighting. " + BG),
    # the head's way back from the push's turn (15 degrees toward the viewer, the profile) to the window: an in-between drawing
    'turn_half': ([mine('base'), mine('turn')],
                  "Edit image 1. Turn ONLY her head about 7 degrees toward the viewer: halfway between image 1 (a lost profile) and "
                  "image 2 (a clean side profile): a little more of her cheek shows, the tip of her nose just appears past the cheek's "
                  "curve, the outer corner of her eye and its lashes, and the corner of her mouth lifted in a small dry half-smile. Her "
                  "hair, the ribbon at the back of her head, her ear and her bangs turn with her head naturally (half as far as in "
                  "image 2). Keep EVERYTHING else exactly as in image 1: her body, jacket, the hood lying on her shoulders, her arms, "
                  "the lantern, the hair hanging down her back, the ribbon's tails, the hakama, feet, her position and size, the "
                  "style, lineart, colours and lighting. " + BG),
}


def run(name, n=1):
    refs, prompt = JOBS[name]
    return generate(prompt, mine(name), size=SIZE, quality='high', refs=refs, n=n)


if __name__ == '__main__':
    a = sys.argv[1:]; n = int(a[a.index('--n') + 1]) if '--n' in a else 1
    names = [x for x in a if x in JOBS]
    ts = [threading.Thread(target=run, args=(nm, n)) for nm in names]
    for t in ts: t.start()
    for t in ts: t.join()
