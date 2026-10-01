"""garments8: register the chosen separated references and the shape truths in Clawd's manifest, laid out as the file
is (charkit.outfit.set_member), numbers read from the refchecks' layerref.json.

    python tools/garments8/register.py            # after the chosen takes are copied into charkit/refs/clawd/gen/
"""
import hashlib, json, os, sys
sys.path.insert(0, os.getcwd())
from charkit import outfit

MP = 'charkit/refs/clawd/manifest.json'
L = 'charkit/out/garments8/layerref/'
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
rd = lambda k: json.load(open(L + k + '/layerref.json'))
LEDGER = 'tools/ledger.jsonl'
APPROVED = ("the coordinator's brief for tool/garments8 (Michael, 2026-10-01: \"Absolutely let the garment round generate "
            "a reference for the blouse / collar / lapel / top in general without the bow\"; paid calls authorized, "
            "~8 at n=2)")


def views(rep, keys):
    return {v: {k: r[k] for k in keys if k in r} for v, r in rep['views'].items()}


top1, top2 = rd('top_layers_1'), rd('top_layers_2')
cg1, cg2 = rd('collar_ghost_1'), rd('collar_ghost_2')
top = {
    "kind": "generated_reference",
    "tracked": True,
    "provenance": {
        "model": "gpt-image-2.5-sunburst", "date": "2026-10-01", "size": "2560x1440", "quality": "high", "n": 2,
        "chosen": "take 1 of 2 by charkit.layerref --kind top (both PASS; take 1's mean iou_dc 0.9814 against 0.9807, "
                  "its V recall 1.0 / 0.998)",
        "inputs": ["bodice_layers"], "prompt": "charkit/refs/clawd/gen/prompts.json", "prompt_key": "top_layers",
        "ledger": LEDGER, "approved": APPROVED, "sha256": sha('charkit/refs/clawd/gen/top_layers.png')},
    "path": "charkit/refs/clawd/gen/top_layers.png",
    "role": "the top WITHOUT the sailor collar and the bow, a separated layer reference (Michael, 2026-10-01: each "
            "covering piece alone and the layer under it without it): bodice_layers (the outfit without the bow) "
            "redrawn in its own layout, A-pose and scale with the collar removed too, and what it covers drawn as worn: "
            "the open orange jacket over the chest fronts, the tops of the shoulders to the puffs' seams and the whole "
            "upper back; its neckline the collar's inner edge (the V in front, round the back of the neck at the band's "
            "height); the cream bodice front below the V's point. The top's shape truth (shape_truth.top)",
    "authority_split": {
        "shape": "the jacket under the collar and the bow: its neckline (the V), its shoulders and its back where the "
                 "collar lies on them, the bodice front under the bow",
        "placement": "body_turnaround: the top, the V and every piece wherever the turnaround shows them",
        "map": "not in the top-level authority map (see base_body_turnaround's)"},
    "refcheck": {
        "command": "python -m charkit.layerref charkit/spec/clawd.json charkit/refs/clawd/gen/top_layers.png --kind top",
        "tolerances": "charkit.layerref.TOL (the bodice kind's, declared before any sheet was measured); calibrated: "
                      "tools/garments8/layercal.py (the turnaround moved 2 px PASS, its torso band widened 6% FAIL)",
        "scale": top1['scale'],
        "views": views(top1, ('shift', 'kept_iou', 'iou_dc', 'recall', 'outside', 'hidden', 'v', 'pass')),
        "take_2": {v: r['iou_dc'] for v, r in top2['views'].items()}},
    "cautions": [
        "a generated reading of what the collar and the bow hide (the jacket's neckline taken as the collar's inner edge: "
        "the collar is sewn to it): checked for consistency only (the kept parts 0.983-0.987; the top and bodice front "
        "against the outfit truth where the turnaround shows them, iou_dc 0.965-0.996, outside under 0.019)",
        "its V's skin reaches z -0.90 in front (the turnaround's visible V -0.71, bodice_layers' -0.88): the V under "
        "the knot is bodice_layers' reading, the same here",
        "its V is drawn 0.068 / 0.055 outside the turnaround's visible V (front / three-quarter, the tolerance 0.10): "
        "the V's width above the bow is the turnaround's"]}

cg = {
    "kind": "generated_reference",
    "tracked": True,
    "provenance": {
        "model": "gpt-image-2.5-sunburst", "date": "2026-10-01", "size": "2560x1440", "quality": "high", "n": 2,
        "chosen": "take 2 of 2 by charkit.layerref --kind collar_ghost (take 2 passes front, three-quarter and back; "
                  "take 1 front and back only: its three-quarter %.3f)" % cg1['views']['three_quarter']['iou_dc'],
        "inputs": ["bodice_layers"], "prompt": "charkit/refs/clawd/gen/prompts.json", "prompt_key": "collar_ghost",
        "ledger": LEDGER, "approved": APPROVED, "sha256": sha('charkit/refs/clawd/gen/collar_ghost.png')},
    "path": "charkit/refs/clawd/gen/collar_ghost.png",
    "role": "the sailor collar ALONE, a separated layer reference (the cover alone): bodice_layers' collar drawn as a "
            "ghost-mannequin sheet (worn over the costume by an invisible person), front / three-quarter / profile / "
            "back left to right, everything else removed: the two flat lapels down to the V's point, the parts over the "
            "shoulders, the low band round the back of the neck (seen through the neck opening in front) and the square "
            "back panel. Registered views: front, three-quarter, back (shape_truth.collar_alone)",
    "authority_split": {
        "shape": "the collar where the hair and the neck hide it (the band round the back of the neck), its whole "
                 "outline alone; the collar's shape where the turnaround shows it in context stays bodice_layers' "
                 "(shape_truth.collar)",
        "placement": "body_turnaround (the sheet keeps neither place nor scale: each view is registered by the fit)",
        "map": "not in the top-level authority map"},
    "refcheck": {
        "command": "python -m charkit.layerref charkit/spec/clawd.json charkit/refs/clawd/gen/collar_ghost.png "
                   "--kind collar_ghost",
        "tolerances": "charkit.layerref.TOL (iou_dc 0.80, outside 0.03, recall 0.85: the bodice kind's); the views "
                      "registered by one joint scale and a shift each; calibrated: tools/garments8/layercal.py",
        "scale": cg2.get('scale'), "scale_spread": cg2.get('scale_spread'),
        "views": views(cg2, ('scale', 'iou_dc', 'recall', 'outside', 'hidden', 'pass')),
        "take_1": {v: r.get('iou_dc') for v, r in cg1['views'].items()}},
    "cautions": [
        "drawn without a body, the collar keeps neither the sheet's place nor its scale (2.3x larger, ~200 px lower): "
        "its sizes and positions are body_turnaround's; each view is placed by the refcheck's fit",
        "its profile FAILs (iou_dc %.3f, outside %.3f: the arc over the shoulder drawn thicker and further back): not "
        "registered" % (cg2['views']['profile']['iou_dc'], cg2['views']['profile']['outside']),
        "its views' own best scales spread %.2f (the three-quarter drawn larger than the front): one joint scale is "
        "fitted" % cg2['scale_spread']]}

masks = {
    "kind": "piece_truth",
    "path": "charkit/refs/clawd/shape_truth.npz",
    "tracked": True,
    "role": "the pieces' shape truths as masks VIEW__NAME on the outfit masks' grids (bodyqa.design_views at the "
            "sheet's 212.5 px/L, outfit_truth's): each `shape_truth` entry's sheet registered by its refcheck "
            "(charkit.layerref) and cut into the layer's pieces by the sheet's own colours, voted by the outfit truth "
            "where the turnaround shows them (layerref.layer_pieces); what the QA compares ours drawn the sheet's way "
            "with (without the entry's `without` pieces)",
    "provenance": {"by": "charkit.layerref.build_truths (tool/garments8, 2026-10-01)",
                   "command": "python -m charkit.layerref truths charkit/spec/clawd.json",
                   "sha256": sha('charkit/refs/clawd/shape_truth.npz') if os.path.exists('charkit/refs/clawd/shape_truth.npz') else None},
    "cautions": ["valid for the grids it records only (outfit_truth's): rebuild it with the command when a sheet, the "
                 "eye spacing or the window changes",
                 "sha256 in provenance, not top-level: a top-level one enters every produced reference's stamp "
                 "(manifest.stamp) and would rebuild the hull, the outfit masks and the hair layers"]}

COVER = ["bow", "bow_tail_L", "bow_tail_R"]
shape_truth = {
    "collar": {"shape": "bodice_layers", "kind": "bodice", "without": COVER,
               "note": "the collar and its lapels without the bow, as worn over the top (Michael, 2026-10-01: the "
                       "lapels without the bow were never defined): bodice_layers' collar"},
    "bodice_panel": {"shape": "bodice_layers", "kind": "bodice", "without": COVER,
                     "note": "the cream bodice front without the bow"},
    "top": {"shape": "top_layers", "kind": "top", "without": ["collar"] + COVER,
            "note": "the jacket without the collar and the bow: its V neckline, shoulders and back"},
    "neck_v": {"shape": "bodice_layers", "kind": "bodice", "class": "skin", "views": ["front", "three_quarter"],
               "without": COVER, "note": "the V's skin without the bow, to its point (z -0.88 in front)"},
    "collar_alone": {"shape": "collar_ghost", "kind": "collar_ghost", "piece": "collar",
                     "views": ["front", "three_quarter", "back"], "alone": True,
                     "note": "the collar alone (the cover alone): ours drawn as its objects only"},
    "bow": {"shape": "body_turnaround",
            "note": "the outermost piece: the turnaround draws it whole in front, three-quarter and profile (its own "
                    "shape truth; nothing to register). bow_closeup and the generated bow ghost fail the ghost refcheck "
                    "(docs/workstreams/garments8.md); bow_closeup stays the bow's construction and lines reference"},
}

if __name__ == '__main__':
    # step 'refs' (the sheets and shape_truth; then `python -m charkit.layerref truths`), step 'masks' (the masks' entry)
    step = sys.argv[1] if len(sys.argv) > 1 else 'refs'
    text = open(MP).read()
    if step == 'masks':
        text = outfit.set_member(text, 'references', 'shape_truth_masks', masks)
        json.loads(text)
        open(MP, 'w').write(text)
        print('registered: shape_truth_masks')
        sys.exit(0)
    for key, val in (('top_layers', top), ('collar_ghost', cg)):
        text = outfit.set_member(text, 'references', key, val)
    # the entries into the manifest's shape_truth (the hair's is pipeline-3d's: kept), laid out as the file is
    if '\n "shape_truth":' in text:
        for k, v in shape_truth.items():
            text = outfit.set_member(text, 'shape_truth', k, v)
    else:
        end = text.rstrip().rfind('}')
        body = json.dumps(shape_truth, indent=1, ensure_ascii=False).replace('\n', '\n ')
        text = text[:end].rstrip() + ',\n "shape_truth": ' + body + '\n}\n'
    assert all(json.loads(text)['shape_truth'][k] == v for k, v in shape_truth.items())
    open(MP, 'w').write(text)
    print('registered: top_layers, collar_ghost, shape_truth_masks, shape_truth', sorted(shape_truth))
