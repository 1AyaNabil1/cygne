"""Collapse near-duplicate short phrases, such as the same goal said twice."""

from __future__ import annotations

import re

from rapidfuzz import fuzz

_WORD = re.compile(r"\w+")
_SUFFIX = re.compile(r"(?:ing|ed|es|s)$")


def _stem(word: str) -> str:
    """A crude stem, enough to match "leads" with "lead" and "needed" with "need"."""
    return _SUFFIX.sub("", word) if len(word) > 4 else word


def _words(text: str) -> frozenset[str]:
    return frozenset(_stem(w) for w in _WORD.findall(text.casefold()))


def _similar(a: frozenset[str], b: frozenset[str], threshold: int) -> bool:
    return fuzz.ratio(" ".join(sorted(a)), " ".join(sorted(b))) >= threshold


def deduplicate(items: list[str], threshold: int = 85) -> list[str]:
    """Merge near-duplicates, keeping the more specific phrase in the earlier one's place.

    "SEO" then "better SEO" keeps "better SEO"; "need more leads" then "more leads
    needed" keeps the first; unrelated phrases are all kept, in order.
    """
    kept: list[tuple[str, frozenset[str]]] = []
    for item in items:
        text = item.strip()
        words = _words(text)
        if not words:
            continue
        for i, (_, other) in enumerate(kept):
            if words <= other or _similar(words, other, threshold):
                break  # adds nothing
            if other < words:
                kept[i] = (text, words)  # same thing, more specific
                break
        else:
            kept.append((text, words))
    return [text for text, _ in kept]
