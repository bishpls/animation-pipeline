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

# ================================================================================================================ the room ending
# (Michael + Fable: she stays in the room through the final chorus, lantern in hand, watching the window.) Every drawing is an edit
# of the hold drawing; build.py pastes back only what changed, so the lantern arm (hold's far arm, forward, the lantern hanging at
# the hip) is the same pixels in every drawing: "the lantern hand holds still throughout"
HOLD = ref('base_room')
KEEP = ("Keep EVERYTHING else exactly as in image 1, pixel for pixel where possible: her far arm held forward with the short "
        "stick and the lit paper lantern hanging from it (same place, same size), her face, the jacket, the skirt, her feet and "
        "geta, the purple floor cushion, the lighting (warm amber light from the lantern on her front, a cool blue rim on her "
        "back), the scale and the position on the canvas. Flat pure green (#00FF00) background, nothing else in the frame. No green "
        "on the character. No shadow on the ground. ")
NEAR = "her near arm (the one nearest to us, hanging relaxed at her side in image 1)"
JOBS['e_down'] = ([HOLD, mine('ref_canon_side_back')],
    "Image 1 is the girl standing in profile facing left, hood up, holding a lit paper lantern on a short stick. Image 2 is her "
    "character sheet (side view and back view, hood down). Redraw image 1 with her hood DOWN: the hood has fallen back and lies "
    "soft and empty on her shoulders and upper back, bunched at the nape of her neck; her head is uncovered, as in image 2: dark "
    "indigo hair with straight-cut bangs and straight side locks, the sides gathered back half-up and tied at the back of her head "
    "with the indigo-teal ribbon in a small bow, its two long tails hanging straight down her back; the rest of the long straight "
    "hair falls down her back to the waist, over the fallen hood. The same face in profile, the same calm expression, eyes looking "
    "left. " + KEEP + DESIGN)
JOBS['e_push1'] = ([HOLD],
    "Edit image 1. Change ONLY " + NEAR + ": she raises that hand to her head and takes hold of the front edge of her hood just "
    "above her forehead, fingertips curled over the rim, about to push the hood back; her elbow is raised forward and up, and the "
    "wide sleeve has slid down her forearm toward the elbow, showing her wrist. The hood is still up. " + KEEP + DESIGN)
JOBS['e_push2'] = ([HOLD],
    "Edit image 1. Change ONLY " + NEAR + " and her hood: with that hand she pushes her hood back off her head. The hood is halfway "
    "off, sliding back: its front rim is now at the top of her head, behind the crown, and her hand is on top of her head pushing "
    "it back, elbow raised. Her dark indigo hair with straight-cut bangs is uncovered at the forehead and the top of her head; the "
    "hood's fabric bunches behind her head. " + KEEP + DESIGN)
JOBS['e_wipe1'] = ([HOLD],
    "Edit image 1. Change ONLY " + NEAR + ": she lifts that hand in front of her body to chest height, forearm level and pointing "
    "forward (to the left of the picture), the elbow bent and close to her side, the hand open and flat with the palm facing "
    "forward and the fingers together, as if about to turn the page of a large book; the wide sleeve hangs down below the "
    "forearm. The hand is above the lantern's stick, not touching it. " + KEEP + DESIGN)
JOBS['e_wipe2'] = ([HOLD],
    "Edit image 1. Change ONLY " + NEAR + ": she sweeps that hand forward toward the left of the picture, as if turning a page "
    "in the air: the arm reaching forward at chest-to-shoulder height, elbow a little bent, the open hand palm facing forward-left, "
    "fingers together, well in front of her body; the wide sleeve swings back and hangs below the arm. A small, contained gesture "
    "(half of a full reach). The arm passes above the lantern's stick, not touching it. " + KEEP + DESIGN)

DOWN = mine('e_down')
KEEPD = KEEP.replace("her face,", "her face, her hair and ribbon, the fallen hood,")
JOBS['e_push3'] = ([DOWN],
    "Edit image 1. Change ONLY " + NEAR + ": she has just pushed her hood back and her hand is still at the back of her head, "
    "resting on her hair just above the ribbon's bow, the elbow raised forward and up beside her face (not covering it), the wide "
    "sleeve slid down toward the elbow. The hood lies fallen on her shoulders exactly as in image 1. " + KEEPD + DESIGN)
JOBS['e_step'] = ([DOWN],
    "Edit image 1. She takes one short step forward, to the LEFT (the direction she faces): her near foot (nearest to us) has just "
    "been set down flat on the floor one geta-length ahead of where it stood; her far foot stays exactly where it was, its heel a "
    "little raised; her body has moved forward to halfway between the two feet, upright and calm, head level. Her arms are exactly "
    "as in image 1 (the far arm holding the lantern stick forward, the lantern hanging from it, the near hand relaxed at her side), "
    "only carried forward with her body. The pleated skirt is pushed forward a little by the front leg. Hood down, hair and ribbon "
    "as in image 1. The same scale, the floor at the same height, the cushion where it is. Flat pure green (#00FF00) background, "
    "nothing else in the frame. No green on the character. No shadow on the ground. " + DESIGN)
JOBS['e_hd_up'] = ([DOWN],
    "Edit image 1. Change ONLY her head: she lifts her chin a little and looks slightly up toward the left, as if watching something "
    "rise in a window: the head tilted back by about six degrees, pivoting at the neck; the hair and ribbon follow the head. The "
    "same face and expression. " + KEEPD + DESIGN)
JOBS['e_hd_dn'] = ([DOWN],
    "Edit image 1. Change ONLY her head: she lowers her chin a little and looks slightly down toward the left: the head tilted "
    "forward by about six degrees, pivoting at the neck; the hair and ribbon follow the head. The same face and expression. "
    + KEEPD + DESIGN)
JOBS['e_hu_up'] = ([HOLD],
    "Edit image 1. Change ONLY her head and hood: she lifts her chin a little and looks slightly up toward the left, as if watching "
    "something rise in a window: the head tilted back by about six degrees, pivoting at the neck; the hood moves with her head. The "
    "same face and expression. " + KEEP + DESIGN)
JOBS['e_turn1'] = ([DOWN, mine('front')],
    "Image 1 is the girl standing in profile facing left, hood down, holding a lit paper lantern on a short stick forward in her "
    "far hand (her right hand). Image 2 is the same girl in another moment, turning toward the viewer: use it only for the body "
    "angle. Redraw image 1 with her turning round toward the viewer, to walk off to the right: her body turned three-quarters "
    "toward the viewer, still facing a little to the left of the picture; her head turned further than her body, almost facing the "
    "viewer, her eyes glancing toward the right of the picture. The lantern stays in her right hand on its short stick, held low "
    "and a little forward at hip height, the lit lantern hanging below it in front of the left side of her skirt. Her other hand "
    "relaxed at her side. Hood down: the hood fallen on her shoulders, hair and ribbon as in image 1; feet together on the same "
    "spot; the pleated skirt swinging a little with the turn. The lantern's warm light lights her from below and in front; a cool "
    "rim on the right side of her figure. The same scale, the floor at the same height, the purple cushion where it is in image 1. "
    "Flat pure green (#00FF00) background, nothing else in the frame. No green on the character. No shadow on the ground. " + DESIGN)

# (e_step v1: the model rescaled her, soles 110 px higher, and set the front geta up on the cushion. The cushion lies just
# upstage of her step line: a step to the left passes in front of its corner, on the floor)
JOBS['e_step'] = ([DOWN],
    "Edit image 1. She takes ONE short step forward, to the LEFT (the direction she faces). Keep her EXACTLY the same size: the "
    "top of her head at the same height as in image 1, and BOTH soles on the same flat floor line as in image 1 (the bottom of the "
    "geta at the same height as in image 1). Her near foot (nearest to us) is set down flat on the floor directly ahead of her "
    "other foot: the heel of the front geta about where the toe of the back geta is, one geta-length forward. The front geta "
    "stands on the floor IN FRONT of the purple cushion's corner (nearer to us than the cushion), never on the cushion. Her far "
    "foot stays exactly where it is in image 1, its heel a little raised. Her body has moved forward to halfway between the two "
    "feet, upright, head level. Her arms are as in image 1 (the far arm holding the lantern stick forward, the lantern hanging, the "
    "near hand relaxed at her side), only carried forward with her body. The pleated skirt is pushed forward a little by the front "
    "leg. Hood down, hair and ribbon as in image 1. The cushion stays exactly where it is. Flat pure green (#00FF00) background, "
    "nothing else in the frame. No green on the character. No shadow on the ground. " + DESIGN)
JOBS['e_turn2'] = ([mine('e_turn1'), mine('turn_r')],
    "Image 1 is the girl turning round toward the viewer, hood down, a lit paper lantern on a short stick in her right hand. Image "
    "2 is the same girl in another moment (use it only for the body angle): three-quarters facing right, about to walk off to the "
    "right. Redraw image 1 one moment later: her body turned three-quarters toward the RIGHT of the picture, her head in profile "
    "facing right, looking right. The lantern stays in her right hand (now the hand nearest to us), held low on its short stick "
    "and carried a little forward, so the lit lantern hangs ahead of her to the right at knee-to-hip height, leading the way. Her "
    "other arm relaxed at her side. Her weight shifting onto her far foot, about to take the first step to the right; the pleated "
    "skirt swinging with the turn; the ribbon and long hair swinging out behind her to the left. Hood down (fallen on her "
    "shoulders), the same face, hair and ribbon as image 1. The lantern's warm light lights her front from below; a cool rim on "
    "her back. The same scale as image 1, the floor at the same height, the purple cushion where it is in image 1. Flat pure green "
    "(#00FF00) background, nothing else in the frame. No green on the character. No shadow on the ground. " + DESIGN)

# ---- the walk-off (200.6): profile facing right, the lantern carried ahead in the near hand, hood down. Identity, lantern and
# light from e_turn2; the leg pose from the room walk's drawings (image 2)
WALKOFF = ("Image 1 is the girl, hood down, carrying a lit paper lantern on a short stick in her right hand. Image 2 is the same girl "
           "walking in another scene: use image 2 ONLY for the legs, feet and body position. Draw the girl of image 1 in profile "
           "facing RIGHT, walking to the right, in the leg pose of image 2. She carries the lantern exactly as in image 1: in her "
           "near hand (her right hand, nearest to us), the arm low and steady, the hand a little forward of her hip holding the "
           "short stick, the lit lantern hanging ahead of her at knee-to-hip height, leading the way. Her far arm swings a little. "
           "Hood down, fallen on her shoulders; her hair, bangs, ribbon bow and long ribbon tails as in image 1, the long hair and "
           "ribbon trailing behind her to the left. The same face. The lantern's warm light lights her front and her skirt from "
           "ahead and below; a cool rim on her back. The same scale as image 1 (the same height from the top of her head to the "
           "soles), the floor at the same height, the purple cushion where it is in image 1. " + DESIGN
           + "Flat pure green (#00FF00) background, nothing else in the frame. No green on the character. No shadow on the ground. ")
JOBS['e_wc1'] = ([mine('e_turn2'), mine('walk_u1')], WALKOFF + "This is the CONTACT drawing: her near leg forward, its geta just "
                 "set down on the floor a short step ahead; her far leg behind, heel raised, the geta tipped onto its front tooth.")
JOBS['e_wp1'] = ([mine('e_turn2'), mine('walk_m1')], WALKOFF + "This is the PASSING drawing: her near leg planted straight under "
                 "her body; her far leg lifted and swinging forward beside it, the geta just off the floor; the skirt nudged forward by "
                 "the swinging knee.")
JOBS['e_wc2'] = ([mine('e_turn2'), mine('walk_u2')], WALKOFF + "This is the other CONTACT drawing: her far leg forward, its geta "
                 "just set down on the floor a short step ahead; her near leg behind, heel raised, the geta tipped onto its front tooth.")

# ---- the deckle edge, not fur (Fable's ruling, commit cd023ef; the director: "the deckle reads as fur"): every room drawing that
# shows a cuff or the jacket's hem, edited directly with one identical prompt so the poses stay registered -> src/k_<name>.png
DECKLE = ("Edit image 1. Change ONLY the trim at the hem of her black jacket and at the openings of her wide sleeves (the cuffs). "
          "Remove the pale, fluffy, fur-like cream band there completely: the black cloth itself simply ends in a thin, irregular, "
          "torn-paper (deckle) edge, like the rough edge of handmade paper, its torn fibres only a slightly lighter value of the same "
          "black cloth (a dark warm grey). No white, no cream, no pale band, no fur. Keep EVERYTHING else exactly as in image 1, pixel "
          "for pixel: her pose, face, hood, hair, ribbon, hands, the lantern and its stick, the skirt, the tabi and geta, the purple "
          "cushion, the lighting, the scale and the position on the canvas. Flat pure green (#00FF00) background.")
for n, src in [('hold', HOLD)] + [(k, mine('e_' + k)) for k in ['push1', 'push2', 'push3', 'wipe1', 'wipe2', 'step', 'turn1', 'turn2', 'wc1', 'wp1', 'wc2']]:
    JOBS['k_' + n] = ([src], DECKLE)

# (the step, again: the cushion lies ahead of her feet and reaches nearer the viewer than they do, so a step along her facing line
# lands on it. She steps toward the window past its near side: the front foot on the floor in front of the cushion's corner)
JOBS['k_step2'] = ([mine('k_step')],
    "Edit image 1. Change ONLY her front foot (the one nearest to us, stepping forward to the left) and the skirt just above it: "
    "move that foot a little toward the viewer and down in the picture, so the geta stands flat on the floor clearly IN FRONT OF "
    "the purple cushion, nearer to us than the cushion's front edge and tassel: the bottom of that geta lower in the picture than "
    "the lowest point of the cushion, by about half the height of a geta. The geta overlaps the cushion's front corner only as "
    "something in front of it; it does not stand on the cushion. Her back foot stays exactly where it is. Keep everything else "
    "exactly as in image 1 (her face, hair, ribbon, the fallen hood, the jacket and its thin torn-paper hem and cuffs, the lantern "
    "and its stick, the cushion, the lighting, the scale and the position). Flat pure green (#00FF00) background. " + DESIGN.replace(
    "a rough cream paper-fibre (deckle) trim at the jacket hem and the cuffs", "a thin, irregular torn-paper edge at the jacket hem and the cuffs, a lighter value of the black cloth, no white"))


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
