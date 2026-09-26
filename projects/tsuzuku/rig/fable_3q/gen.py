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
    # (chosen: base_b_2, kept as src/base.png; keyed to base_keyed.png with rig/fable_seated/key.py)
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
