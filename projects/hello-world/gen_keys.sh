#!/bin/zsh
# generate sakuga key illustrations (reference only -> rigged). usage: zsh gen_keys.sh [name ...]
cd ~/animation-pipeline
R=projects/hello-world/refs; K=projects/hello-world/assets/keys; mkdir -p $K
STY="Draw ONE single illustration of ONE character (this is NOT a character sheet: no multiple views, no extra heads, no hands panel). The attached images show the EXACT character design (fluffy clay-orange hair with two blocky square ear-buns and small crab-claw clips, an eight-point yellow spark hairpin, golden eyes with tall vertical slit highlights, clay-orange and cream idol dress with a big cream ribbon, pixel-step dark hem, black shorts, white boots with orange tops). Premium modern TV-anime key-animation frame: crisp clean line art, flat cel colours with one hard shadow tone and a thin warm rim light, expressive and alive. She is a young adult, cute and earnest, never sexualized. BACKGROUND: the entire background is ONE perfectly flat pure green colour #00FF00 filling the whole frame. There is NOTHING else in the frame: no curtains, no stage, no floor, no shadow, no effects, no sparkles, no text, no props except those described. Never use green on the character. 16:9 frame."
typeset -A P
P[k02_pose]="Shot: the transformation's final pose, full body, centred, facing camera, standing on one leg with the other kicked up behind, right hand making a cute 'claw' pinch gesture (thumb and index finger like a crab claw) beside her eye, left hand on her hip, a confident bright smile, hair and skirt settling. Whole body visible with margin."
P[k03_eye]="Shot: extreme close-up of her face filling the frame, cropped from forehead to lips, both golden eyes wide open looking straight into the camera with sparkling tall slit highlights and tiny star reflections, a few strands of orange fringe, the spark hairpin at the edge. Intense, wondering."
P[k04_hero]="Shot: chorus hero pose, full body, centred, she leaps off the ground singing into a handheld microphone in her right hand, left arm flung up in a joyful wave, hair and skirt flaring, huge open-mouthed smile, low camera angle. Whole body visible with margin."
P[k05_smile]="Shot: bust close-up (head and shoulders), a warm gentle closed-eye smile, head tilted slightly, both hands clasped near her chest, a soft rosy blush."
P[k06_shy]="Shot: bust close-up, flustered and shy: a deep blush, eyes glancing sideways toward the camera, a small embarrassed smile, fingertips touching together at her chin."
P[k07_spin]="Shot: full body mid-spin, seen from a back three-quarter angle, looking back over her shoulder at the camera with a delighted smile, one arm extended, hair and skirt flaring outward from the spin. Whole body visible with margin."
P[k08_mirror]="Shot: waist-up, strict side profile facing screen-right, a curious gentle expression, her right hand raised palm-forward as if touching a pane of glass in front of her."
P[k09_mine]="Shot: extreme close-up of her face, slightly low angle, eyes open and resolute, a quiet determined smile, a single orange strand across her cheek, emotional and sincere."
P[k10a]="Shot: full body, crouched low in anticipation, gripping a microphone to her chest with both hands, eyes squeezed shut, hair lifting upward as if energy is gathering. Whole body visible with margin."
P[k10b]="Shot: full body, an explosive jump high in the air, arms flung wide, microphone raised high in her right hand, head thrown back in a huge joyful shout, hair and skirt blasting outward. Whole body visible with margin."
P[k11_reach]="Shot: dramatic foreshortened perspective, she leans toward the camera extending her right arm straight at the viewer, holding a microphone out handle-first to offer it to the viewer; her smiling face behind her hand, warm and inviting."
P[k12_tehe]="Shot: bust close-up, classic anime tehepero: one eye winking shut, the tip of her tongue poking out, her loose fist lightly bonking the top of her head, playful and a little embarrassed."
names=(${@:-${(k)P}})
for n in $names; do
  .venv/bin/python tools/imagegen.py "$STY ${P[$n]}" $K/$n.png --ref $R/ref_front.png --ref projects/hello-world/assets/keys/k05_smile.png --size 2K > $K/$n.log 2>&1 &
  while [ $(jobs -r | wc -l) -ge 3 ]; do sleep 2; done
done
wait
ls $K/*.png | wc -l
