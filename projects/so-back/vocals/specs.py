"""What each phrase should be heard as, and its near misses (Whisper forced choice and phoneme CTC)."""
def _spell(ph, marks=('!', '.')):
    return [f' {ph}{m}' for m in marks]
WERE_SO_BACK = dict(
    hits=_spell("We're so back") + _spell("We are so back") + _spell("Were so back") + _spell("We're so back", ('?',)),
    misses=[f' {m}!' for m in ["We're so bad", "We're so black", "Where's the back", "We're so bag", "We so back",
            "Wear so back", "We're sold back", "We're so pack", "We're so tack", "We're so bat", "We're slow back",
            "Where so back", "We're so bang", "We're so back up", "We're so big", "We're so beck", "We're so buck",
            "Winner so back", "We're so dead", "We're so bad!", "Where's the bag", "We're so boss", "We're so bow",
            "We are so bad", "Where'd you go back", "We're so Bach", "We're soap back", "Wear the back", "We're so bay",
            "We're saw back", "We're so duck", "We're so back?"]],
    ipa='w ɪɹ s oʊ b æ k',
    ipa_alts=['w ɪɹ s oʊ b æ d', 'w ɪɹ s oʊ b æ ɡ', 'w ɪɹ s oʊ b æ', 'w ɪɹ s oʊ b ɛ k', 'w ɪɹ s oʊ b ʌ k', 'w ɪɹ s oʊ d æ k',
              'w ɪɹ s oʊ p æ k', 'w ɛɹ s oʊ b æ k', 'w ɪ s oʊ b æ k', 'w ɪɹ s oʊ b eɪ k', 'w ɪɹ s oʊ b ɑː k', 'w ɪɹ s ɔ b æ k',
              'w ɪɹ s oʊ b æ t', 'w ɪɹ s oʊ b ɑː', 'w ɪɹ s oʊ b ɛ', 'w ɪɹ s oʊ m æ k', 'w ɪɹ oʊ b æ k'],
    targets=["were so back", "we are so back", "so back"])
ITS_SO_OVER = dict(
    hits=_spell("It's so over") + _spell("Its so over") + _spell("It's so over", ('?',)),
    misses=[f' {m}!' for m in ["It's over", "It's so ogre", "Is so over", "It's sober", "It's all over", "It's so cover",
            "It's go over", "Just so over", "It's snow over", "It's slow over", "This so over", "Is it over", "It's so old",
            "Yes so over", "Kiss so over", "Its sew over", "It's soul over", "It's so hover", "It's so clover",
            "It's so overdue", "It's over, over", "Is so old", "It's so ova", "Its so ogre", "It's the over", "Tits so over",
            "It's so over?", "Sit so over", "Hits so over", "It so over"]],
    ipa='ɪ t s s oʊ oʊ v ɚ',
    ipa_alts=['ɪ s s oʊ oʊ v ɚ', 'ɪ z s oʊ oʊ v ɚ', 'ɪ t s oʊ v ɚ', 'ɪ t s s oʊ ɡ ɚ', 'ɪ t s s ɔ oʊ v ɚ', 'ɪ t s s oʊ',
              'ð ɪ s s oʊ oʊ v ɚ', 'ɪ t s s oʊ ɔː l oʊ v ɚ', 'ɛ t s s oʊ oʊ v ɚ', 'ɪ t s oʊ oʊ v ɚ', 'j ɛ s s oʊ oʊ v ɚ',
              'ɪ t s s oʊ ʌ v ɚ', 'ɪ t s s ɔː oʊ v ɚ', 'ɪ t s s oʊ oʊ b ɚ'],
    targets=["its so over", "it's so over", "it is so over"])
