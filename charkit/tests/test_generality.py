"""charkit.generality: checks named for another character's pieces counted apart from those any character has."""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from charkit import generality  # noqa: E402


def test_buckets_and_share():
    vocab = generality.vocabulary()
    assert {'skirt', 'bow', 'crab'} <= vocab and 'hair' not in vocab and 'face' not in vocab
    qa = {'checks': {'body_front_iou': {'status': 'PASS'}, 'face_width': {'status': 'FAIL'},
                     'piece_skirt_front': {'status': 'WARN'}, 'bow_profile_ribbon': {'status': 'PASS'},
                     'hair_pieces': {'status': 'SKIPPED', 'why': 'ValueError: no families'},
                     'eye_note': {'status': 'INFO'}}}
    T = generality.tally(qa, vocab)
    a, n = T['buckets']['applicable'], T['buckets']['named']
    assert a['PASS'] == 1 and a['FAIL'] == 1 and a['ERROR'] == 1 and a['share'] == round(1 / 3, 4)
    assert n['PASS'] == 1 and n['WARN'] == 1 and n['share'] == 0.5
    assert T['overall']['share'] == 0.4 and 'hair_pieces' in T['parts']


if __name__ == '__main__':
    test_buckets_and_share(); print('ok test_buckets_and_share')
