"""Spelling for sign legends read from CAD library faces.

Library drawings carry misspellings (CROSWALK, NIGHTTIM, QUTLET). A word is corrected only when it is not
an English word and exactly one traffic word lies within one edit of it (two for words of seven letters
or more). Traffic words come from the official sign legends and the MUTCD text published on the site, so
place and business names, which have no near traffic word, are left as drawn.
"""
from collections import Counter
from functools import lru_cache
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parent.parent


@lru_cache(None)
def vocabulary():
    words = Counter()
    for s in json.loads((ROOT / 'data/signs/signs.json').read_text()):
        for k in ('caption', 'legend_ocr', 'name', 'descriptor'):
            for t in re.findall(r"[A-Za-z]+", s.get(k) or ''):
                words[t.upper()] += 5
    for f in (ROOT / 'src/content/docs').glob('ca-mutcd/**/*.md'):
        for t in re.findall(r"[A-Za-z]{3,}", f.read_text(errors='ignore')):
            words[t.upper()] += 1
    return {w: n for w, n in words.items() if n >= 3}


def is_word(w):
    from wordfreq import zipf_frequency
    return zipf_frequency(w.lower(), 'en') >= 1.5 or w.upper() in vocabulary()


def edits1(w):
    letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    splits = [(w[:i], w[i:]) for i in range(len(w) + 1)]
    return ({a + b[1:] for a, b in splits if b} | {a + b[1] + b[0] + b[2:] for a, b in splits if len(b) > 1} |
            {a + c + b[1:] for a, b in splits if b for c in letters} | {a + c + b for a, b in splits for c in letters})


def correct_word(w):
    if len(w) < 4 or not w.isalpha() or not w.isupper() or is_word(w):
        return w
    vocab = vocabulary()
    near = {c for c in edits1(w) if c in vocab}
    if not near and len(w) >= 7:
        near = {c2 for c in edits1(w) for c2 in edits1(c) if c2 in vocab}
    if len(near) == 1:
        return near.pop()
    if len(near) > 1:
        ranked = sorted(near, key=lambda c: -vocab[c])
        if vocab[ranked[0]] >= 4 * vocab[ranked[1]]:
            return ranked[0]
    return w


def correct(text):
    """Corrected legend line, and the corrections made."""
    out, made = [], []
    for tok in re.split(r'(\W+)', text):
        fixed = correct_word(tok) if tok.isalpha() else tok
        if fixed != tok:
            made.append((tok, fixed))
        out.append(fixed)
    return ''.join(out), made
