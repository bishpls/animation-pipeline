"""A hand lexicon (espeak-style en-US IPA, the phone set of wav2vec2-lv-60-espeak-cv-ft) for every word the announcer says.
No espeak on this machine; the vocabulary is small enough to write out."""
LEX = {
    'a': 'ɐ', 'all': 'ɔː l', 'and': 'æ n d', 'blue': 'b l uː', 'bonus': 'b oʊ n ə s', 'bowser': 'b aʊ z ɚ',
    'break': 'b ɹ eɪ k', 'brothers': 'b ɹ ʌ ð ɚ z', 'button': 'b ʌ t ə n', 'camera': 'k æ m ɹ ə',
    'captain': 'k æ p t ɪ n', 'character': 'k æ ɹ ɪ k t ɚ', 'choose': 'tʃ uː z', 'climbers': 'k l aɪ m ɚ z',
    'coins': 'k ɔɪ n z', 'complete': 'k ə m p l iː t', 'computer': 'k ə m p j uː ɾ ɚ',
    'congratulations': 'k ə ŋ ɡ ɹ æ tʃ ə l eɪ ʃ ə n z', 'contest': 'k ɑː n t ɛ s t', 'continue': 'k ə n t ɪ n j uː',
    'dairantou': 'd a ɪ ɹ a n t oː', 'death': 'd ɛ θ', 'defeated': 'd ɪ f iː ɾ ɪ d', 'deluxe': 'd ə l ʌ k s',
    'donkey': 'd ɑː ŋ k i', 'dr': 'd ɑː k t ɚ', 'drops': 'd ɹ ɑː p s', 'event': 'ɪ v ɛ n t', 'failure': 'f eɪ l j ɚ',
    'falco': 'f æ l k oʊ', 'falcon': 'f æ l k ə n', 'fighting': 'f aɪ ɾ ɪ ŋ', 'finish': 'f ɪ n ɪ ʃ', 'five': 'f aɪ v',
    'fixed': 'f ɪ k s t', 'four': 'f oːɹ', 'fox': 'f ɑː k s', 'frames': 'f ɹ eɪ m z', 'game': 'ɡ eɪ m',
    "game's": 'ɡ eɪ m z', 'ganondorf': 'ɡ æ n ə n d oːɹ f', 'giant': 'dʒ aɪ ə n t', 'giga': 'ɡ iː ɡ ə', 'go': 'ɡ oʊ',
    'grab': 'ɡ ɹ æ b', 'green': 'ɡ ɹ iː n', 'hand': 'h æ n d', 'home': 'h oʊ m', 'how': 'h aʊ', 'hurry': 'h ɜː ɹ i',
    'ice': 'aɪ s', 'incredible': 'ɪ n k ɹ ɛ d ᵻ b əl', 'invisible': 'ɪ n v ɪ z ᵻ b əl', 'is': 'ɪ z',
    'jigglypuff': 'dʒ ɪ ɡ l i p ʌ f', 'kirby': 'k ɜː b i', 'kong': 'k ɔ ŋ', 'koopa': 'k uː p ə', 'link': 'l ɪ ŋ k',
    'loser': 'l uː z ɚ', 'luigi': 'l uː iː dʒ i', 'man': 'm æ n', 'mario': 'm ɑː ɹ i oʊ', 'marth': 'm ɑːɹ θ',
    'master': 'm æ s t ɚ', 'match': 'm æ tʃ', 'melee': 'm eɪ l eɪ', 'metal': 'm ɛ ɾ əl', 'mewtwo': 'm j uː t uː',
    'mode': 'm oʊ d', 'mr': 'm ɪ s t ɚ', 'multi': 'm ʌ l t i', 'ness': 'n ɛ s', 'new': 'n uː',
    'nintendo': 'n ɪ n t ɛ n d oʊ', 'no': 'n oʊ', 'one': 'w ʌ n', 'out': 'aʊ t', 'over': 'oʊ v ɚ', 'peach': 'p iː tʃ',
    'pichu': 'p iː tʃ uː', 'pikachu': 'p iː k ə tʃ uː', 'play': 'p l eɪ', 'player': 'p l eɪ ɚ', 'race': 'ɹ eɪ s',
    'ready': 'ɹ ɛ d i', 'record': 'ɹ ɛ k ɚ d', 'red': 'ɹ ɛ d', 'removed': 'ɹ ɪ m uː v d', 'roy': 'ɹ ɔɪ',
    'run': 'ɹ ʌ n', 'samus': 's ɑː m ə s', 'sheik': 'ʃ eɪ k', 'single': 's ɪ ŋ ɡ əl', 'smash': 's m æ ʃ',
    'stage': 's t eɪ dʒ', 'stamina': 's t æ m ᵻ n ə', 'star': 's t ɑːɹ', 'stock': 's t ɑː k', 'success': 's ə k s ɛ s',
    'sudden': 's ʌ d ə n', 'super': 's uː p ɚ', 'survival': 's ɚ v aɪ v əl', 'targets': 't ɑːɹ ɡ ɪ t s',
    'team': 't iː m', 'the': 'ð ə', 'this': 'ð ɪ s', 'three': 'θ ɹ iː', 'time': 't aɪ m', 'tiny': 't aɪ n i',
    'to': 't ə', 'tournament': 't ʊɹ n ə m ə n t', 'training': 't ɹ eɪ n ɪ ŋ', 'two': 't uː', 'versus': 'v ɜː s ə s',
    'watch': 'w ɑː tʃ', 'winner': 'w ɪ n ɚ', 'wins': 'w ɪ n z', 'wire': 'w aɪɚ', 'wow': 'w aʊ', 'yoshi': 'j oʊ ʃ i',
    'young': 'j ʌ ŋ', 'your': 'j ʊɹ', 'zelda': 'z ɛ l d ə',
}
VOWELS = set('ɐ ə ɚ æ ɑː ɔː ɔ ɛ ɪ iː i uː ʊ ʌ oʊ eɪ aɪ aʊ ɔɪ ɜː oːɹ ɑːɹ ʊɹ aɪɚ əl ᵻ a oː'.split())

import re
def words_of(text):
    t = text.lower().replace('-', ' ').replace('&', 'and').replace('mr.', 'mr').replace('dr.', 'dr')
    return [w for w in re.findall(r"[a-z']+", t) if w]

def ipa_words(text):
    return [(w, LEX[w].split()) for w in words_of(text)]
