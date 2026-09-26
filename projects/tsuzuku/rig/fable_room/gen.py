"""Fable in her room, 178.2-181: the new drawings (set-down in-betweens, the turn, the walk), as GPT Image edits of the room
drawings in rig/fable_stage/src/room. tools/gptimage.py logs every call to tools/ledger.jsonl; the prompts are kept here.
    .venv/bin/python projects/tsuzuku/rig/fable_room/gen.py NAME [NAME ...]      -> rig/fable_room/src/NAME.png
"""
import os, sys, threading
D = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(D, '..', '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from gptimage import generate  # noqa: E402

SR = os.path.join(D, '..', 'fable_stage', 'src', 'room')
ref = lambda n: os.path.join(SR, n + '.png')
mine = lambda n: os.path.join(D, 'src', n + '.png')

DESIGN = ("Keep her design exactly as in the reference: black hooded haori-style jacket with wide sleeves, a rough cream paper-fibre "
          "(deckle) trim at the jacket hem and the cuffs, small round brass rivets on the shoulders and sleeves; the hood up; dark "
          "indigo hair with straight bangs; a long indigo-teal ribbon hanging from under the back of the hood down past the jacket; an "
          "ankle-length pleated indigo hakama skirt; white tabi socks; black geta with two wooden teeth. The same face, the same anime "
          "illustration style, line weight, colours and rendering as the reference. ")
FRAME = ("Same canvas framing as image 1: the same scale (her height from the top of the hood to the soles is the same as in image 1), "
         "the floor at the same height, and the purple floor cushion and the lit paper lantern exactly where they are in image 1. "
         "Flat pure green (#00FF00) background, nothing else in the frame. No green on the character. No shadow on the ground. ")
LIGHT_L = ("Lighting exactly as in image 1: warm amber light from the left side of the picture, a cool blue rim on the right side. ")
LIGHT_TURNED = ("The scene's lights stay where they are: warm amber light comes from the LEFT side of the picture (the lantern on the "
                "cushion, low, and a pale pink glow), and there is a cool blue rim on the RIGHT side of the picture. ")

JOBS = {
    # ---- the set-down (profile, facing left)
    'down': ([ref('base_room'), ref('setdown')],
             "Image 1 and image 2 are two key drawings of one animation of the same girl, in the same frame: in image 1 she stands in "
             "profile facing left, holding a lit paper lantern that hangs from a short stick; in image 2 she kneels and sets the lantern "
             "on the purple floor cushion. Draw the in-between drawing, halfway down. She still faces left in profile. Her knees are bent "
             "deeply and she is sinking toward the kneel, her far foot stepping back; her torso leans forward from the hips and her head "
             "is bowed, looking down at the cushion. Her forward arm is lowered and reaches toward the cushion, so the lantern, still "
             "hanging from the stick, is just above the cushion, about to touch it; the lantern is directly above the spot where it "
             "stands in image 2. Her other hand rests on her thigh. " + DESIGN + FRAME.replace('and the lit paper lantern ', '') + LIGHT_L),
    'rise': ([ref('setdown'), ref('empty')],
             "Image 1 and image 2 are two key drawings of one animation of the same girl, in the same frame: in image 1 she kneels "
             "and has just set a lit paper lantern on the purple floor cushion; in image 2 she stands up again in profile facing "
             "left, hands empty. Draw the in-between drawing, halfway up. She still faces left in profile, her hands empty: she has "
             "let go of the stick. She is rising from the kneel: one knee still bent, pushing up from the floor, her near hand pressing "
             "on her bent knee, her torso upright and lifting, her head level, looking left toward the window. The lantern and the "
             "stick stay on the cushion exactly as they are in image 1 (the same place, the same size). " + DESIGN
             + "Same canvas framing as image 1: the same scale, the floor at the same height, the cushion, lantern and stick exactly "
             "where they are in image 1. Flat pure green (#00FF00) background, nothing else in the frame. No green on the character. "
             "No shadow on the ground. " + LIGHT_L),
    # ---- the turn (she pivots on the spot, toward the viewer, to walk out right)
    'front': ([ref('empty'), os.path.join(D, '..', 'fable_stage', 'src', 'base_stage.png')],
              "Image 1 is the girl standing in profile facing left, beside a floor cushion with a lit paper lantern on it. Image 2 is "
              "the same girl seen from the front (her front design, with the hood down). Redraw image 1 with her turned to face the "
              "viewer: her body square to the viewer, standing on the same spot with her feet together, hood UP as in image 1, arms "
              "relaxed at her sides, empty hands. She is in the middle of turning to walk off to the right, so her head is turned a "
              "little to her left (toward the right side of the picture) and her eyes look to the right side of the picture; the "
              "pleated skirt swings slightly with the turn, its hem flaring a little to the right. Calm face. Under the open jacket: the "
              "black kimono collar crossing left over right, and the thin red cord at her neck, as in image 2. " + DESIGN + FRAME + LIGHT_TURNED
              + "So the warm light falls on the left side of her figure, and the right side of her figure is in cool shadow."),
    # ---- the walk (facing right, walking out; the lights stay on the left, so they're behind her)
    'walk_c1': ([ref('empty')],
                "Image 1 is the girl standing in profile facing left, beside a floor cushion with a lit paper lantern on it. Redraw her "
                "turned around, in profile facing RIGHT, walking to the right, on the same spot at the same size. This is the "
                "CONTACT drawing of a slow, deliberate walk: her near leg (her right leg) is forward and its geta has just landed flat "
                "on the floor, a short step ahead; her far leg is behind, its heel raised and its geta tipped forward onto the front "
                "tooth. A short step, as walking in geta and a long skirt: the gap between the heel of the front geta and the toe of "
                "the back geta is about one geta length. Body upright, head level, looking ahead to the right, calm. The front of the "
                "pleated hakama is pushed forward by her front shin, the pleats opening, the hem lifting a little over the front foot. "
                "Her arms hang relaxed with a small swing (the near arm slightly back, the far arm slightly forward), hands empty. The "
                "long ribbon hangs down her back, trailing slightly behind her. " + DESIGN + FRAME + LIGHT_TURNED
                + "Since she now faces right, the warm light falls on her back and the back of her skirt, and the cool blue rim is "
                "on her front."),
}

# ---- the turn's three-quarter views (the head leads the body: eyes, then head, then shoulders)
JOBS['turn_l'] = ([ref('empty'), mine('front')],
    "Image 1 is the girl standing in profile facing left. Image 2 is the same girl a moment later, turned to face the viewer. Draw "
    "the in-between drawing: her body turned three-quarters, halfway between image 1 and image 2. She still faces toward the left "
    "of the picture, but we see the front of her body at three-quarters. Her head is turned further than her body, almost facing "
    "the viewer, and her eyes glance toward the right side of the picture (she is turning round to walk away to the right). She "
    "stands on the same spot, feet together, hood up, arms relaxed at her sides, empty hands; the pleated skirt swings a little with "
    "the turn. " + DESIGN + FRAME + LIGHT_TURNED + "So the warm light falls on the left side of her figure (her front), and the cool "
    "rim on the right side.")
JOBS['turn_r'] = ([mine('front'), mine('walk_c1')],
    "Image 1 is the girl facing the viewer, turning round to walk off to the right. Image 2 is the same girl walking to the right in "
    "profile. Draw the in-between drawing: her body turned three-quarters toward the right of the picture, halfway between image 1 "
    "and the profile of image 2; her head already in profile facing right, looking right. She still stands on the same spot as in "
    "image 1, her weight shifting onto her far foot, about to take the first step to the right; arms relaxed at her sides; the "
    "pleated skirt swinging with the turn, the ribbon swinging behind her. " + DESIGN + FRAME + LIGHT_TURNED + "So the warm light "
    "falls on the left side of her figure (her back and her left shoulder), and the cool rim on her front.")

# ---- the walk: every drawing from the approved contact (walk_c1), walking in place on the canvas
WALK = ("Image 1 is one drawing of her slow, deliberate walk to the right (profile, facing right), beside the floor cushion with the "
        "lit lantern. Draw another drawing of the same walk: the same girl at the same scale, the same profile facing right, her body "
        "at the same place on the canvas (walking in place), the cushion and lantern exactly where they are in image 1, the same "
        "lighting (warm amber on her back from the left, a cool blue rim on her front), and the long ribbon trailing behind her as in "
        "image 1. Short steps, as walking in geta and a long skirt. " + DESIGN
        + "Flat pure green (#00FF00) background, nothing else in the frame. No green on the character. No shadow on the ground. ")
POSES = {
    'walk_d1': "This is the DOWN drawing, just after image 1's contact: her front foot (the one in front in image 1) is now flat on "
               "the floor and takes her weight, that knee bending a little, so her whole body sinks to its lowest point (her head a "
               "little lower than in image 1). Her back foot stays where it is behind her, its heel lifted high, the geta tipped up "
               "onto its front tooth, about to leave the floor. The feet are the same distance apart as in image 1. The skirt "
               "settles forward over the front leg. Arms: the same small swing as in image 1.",
    'walk_p1': "This is the PASSING drawing: the leg that was in front in image 1 is now planted flat directly under her body, "
               "straight, carrying her weight; her other leg has lifted off the floor and swings forward past the planted leg, knee "
               "bent, its geta lifted clear of the floor beside the planted ankle; the swinging knee pushes the front of the pleated "
               "skirt forward, so the skirt kicks forward over it. Her body is upright and a little higher than in image 1. Arms "
               "hang almost straight down at her sides.",
    'walk_u1': "This is the UP drawing, after the passing position: her standing leg is now behind her body, pushing off, its heel "
               "lifting and its geta tipping forward onto the front tooth; her other leg swings forward and reaches ahead, knee almost "
               "straight, its geta just above the floor a short step ahead, about to land. Her body is at its highest point. The "
               "skirt swings forward over the reaching leg. Arms: a small swing, the near arm moving slightly forward.",
    'walk_c2': "This is the next CONTACT drawing, the other step: like image 1 but with the legs swapped. Now her far leg (her left "
               "leg, partly behind the near one) is forward, and its geta has just landed flat on the floor a short step ahead; her "
               "near leg (her right leg, nearest to us) is behind, its heel raised and its geta tipped onto the front tooth. The same "
               "step length as image 1. The arms are swapped too: the near arm slightly forward, the far arm slightly back.",
    'walk_p2': "This is the PASSING drawing of the other step: her far leg (her left leg) is planted flat directly under her body, "
               "straight, carrying her weight; her near leg (her right leg, nearest to us) has lifted off the floor and swings "
               "forward past it, knee bent, its geta lifted clear of the floor beside the planted ankle; the near knee pushes the "
               "front of the pleated skirt forward, so the skirt kicks forward over it. Her body is upright and a little higher than "
               "in image 1. Arms hang almost straight down at her sides.",
    'walk_u2': "This is the UP drawing of the other step: her far leg (her left leg) is behind her body, pushing off, its heel "
               "lifting and its geta tipping forward onto the front tooth; her near leg (her right leg, nearest to us) swings forward "
               "and reaches ahead, knee almost straight, its geta just above the floor a short step ahead, about to land. Her body is "
               "at its highest point. The skirt swings forward over the reaching leg. Arms: a small swing, the near arm moving back.",
}
for k, v in POSES.items(): JOBS[k] = ([mine('walk_c1')], WALK + v)
# (the model drew both PASSING prompts as reaches, swing foot well forward: walk_p1/p2 serve as the reach. The passing drawings
# are small edits of them that move only the lifted foot back under her hips)
PASS = ("Edit image 1, a drawing of the girl walking to the right. Change ONLY her lifted foot and the skirt just above it; keep "
        "everything else exactly the same (her face, hood, ribbon, jacket, arms, the planted foot, the cushion and lantern, the "
        "lighting, the scale and the position on the canvas). Move the lifted foot BACK so that it is directly under her hips, just "
        "beside and slightly behind the ankle of the planted foot, NOT in front of it: the PASSING position of a walk. The lifted "
        "geta is only a little off the floor (about the height of a geta), its heel higher than its toe, the toe pointing down "
        "and slightly back, the knee a little bent; the pleated skirt hangs almost straight, the swinging knee nudging the skirt "
        "forward a little. The two geta overlap in side view. " + DESIGN
        + "Flat pure green (#00FF00) background, nothing else in the frame. No green on the character. No shadow on the ground.")
JOBS['walk_s1'] = ([mine('walk_p1')], PASS)
JOBS['walk_s2'] = ([mine('walk_p2')], PASS)
# (both came back trailing: the lifted foot 240 px behind. The true passing position, from walk_s1: the feet level)
JOBS['walk_m1'] = ([mine('walk_s1')],
    "Edit image 1, a drawing of the girl walking to the right. Change ONLY her lifted foot (the one behind) and the skirt just above "
    "it; keep everything else exactly the same (her face, hood, ribbon, jacket, arms, the planted foot, the cushion and lantern, the "
    "lighting, the scale and the position on the canvas). Move the lifted foot FORWARD so it is exactly level with the planted foot: "
    "the two geta side by side, overlapping in side view, the lifted one a few centimetres off the floor, held nearly level (its toe "
    "just lower than its heel), its knee bent forward so the knee nudges the front of the pleated skirt forward. This is the "
    "PASSING position of a walk: the swinging foot passes right beside the planted one. " + DESIGN
    + "Flat pure green (#00FF00) background, nothing else in the frame. No green on the character. No shadow on the ground.")

# ---- two more set-down in-betweens (the descent and the rise were each one big jump at 812 px tall: CRAFT §13, ease large moves)
JOBS['bend'] = ([ref('base_room'), mine('down')],
    "Image 1 and image 2 are two drawings of one animation of the same girl, in the same frame: in image 1 she stands in profile "
    "facing left, holding a lit paper lantern that hangs from a short stick; in image 2 she has bent down deeply, lowering the "
    "lantern to just above the purple floor cushion. Draw the in-between drawing, a third of the way from image 1 to image 2: she "
    "has just begun to bend. Her head is bowed, her eyes looking down at the cushion; her knees are a little bent; her far foot is "
    "just starting to step back; her torso tilts forward a little; the arm holding the stick is lowering, so the lantern, still "
    "hanging from the stick, is at about the height of her knees, between where it is in image 1 and in image 2. Her near foot "
    "stays exactly where it is in image 1. Her other hand hangs at her side. " + DESIGN
    + FRAME.replace('and the lit paper lantern ', '') + LIGHT_L)
JOBS['rise2'] = ([mine('rise'), ref('empty')],
    "Image 1 and image 2 are two drawings of one animation of the same girl, in the same frame: in image 1 she is rising from a "
    "kneel, one knee up, a hand on that knee; in image 2 she stands in profile facing left, hands empty. Draw the in-between "
    "drawing, almost standing: her legs nearly straight, knees just a little bent, her back foot stepping forward to join the front "
    "foot, her torso upright, hands empty (the hand leaving her knee), her head level, looking left toward the window. Her feet are "
    "where they are in image 2 (the standing feet), the back foot just behind. The lantern and its stick stay on the cushion "
    "exactly as they are in image 1. " + DESIGN
    + "Same canvas framing as image 1: the same scale, the floor at the same height, the cushion, lantern and stick exactly where "
    "they are in image 1. Flat pure green (#00FF00) background, nothing else in the frame. No green on the character. No shadow "
    "on the ground. " + LIGHT_L)


def run(name):
    refs, prompt = JOBS[name]
    generate(prompt, mine(name), size='2048x2560', quality='high', refs=refs)


if __name__ == '__main__':
    names = sys.argv[1:]
    for n in names: assert n in JOBS, n
    os.makedirs(os.path.join(D, 'src'), exist_ok=True)
    th = [threading.Thread(target=run, args=(n,)) for n in names]
    for t in th: t.start()
    for t in th: t.join()
