"""The measurement steps of checks whose measuring code reaches charkit/code_body.py (charkit.registry; docs/CHARKIT.md).
The motion QA (charkit/sim/motionqa.py) rebuilds the skin's weights with the tree's own code_body.build_body_data
(charkit/sim/motion.py: Scene, through bodyeval's assembly) and poses the skin with them, so the gate's code walk counts
the code body's rig as its measuring code. A step: (check pattern, the commit that changed it, what changed)."""

MEASUREMENT_STEPS = [
    # tool/hands: the measure itself is unchanged (the gate's 2x2, 397ffa1 into 342e88c: the candidate's motion QA on
    # the baseline's geometry reads the baseline's values exactly); the rig it rebuilds now has the hands
    ('motion_*', '5d18d38', "the code body's rig rebuilt with the hands (code_body.build_body_data: the hand template's "
     "parts weighted on the finger bones, the arm's tube cut at the wrist, the joints from the template)"),
    ('motion_*', 'c8c4991', "the code body's arm pose (body.arm: code_body.pose_arm on the arm's chain before its "
     "sections are measured)"),
]
