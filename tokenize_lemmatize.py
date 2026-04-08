#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Токенизация корпуса (HTML из corpus/) и группировка токенов по леммам.

Выход:
  tokens.txt   — уникальные токены, по одному на строку (UTF-8).
  lemmas.txt   — строки: <лемма> <токен1> <токен2> ... (леммы и токены отсортированы).

Запуск из корня репозитория:  python tokenize_lemmatize.py
"""

from __future__ import annotations

import sys
from collections import defaultdict

from pymorphy3 import MorphAnalyzer

from corpus_text import (
    ROOT,
    collect_unique_tokens,
    lemma_for_token,
    load_stopwords,
)

STOPWORDS_FILE = ROOT / "ru_stopwords.txt"
TOKENS_OUT = ROOT / "tokens.txt"
LEMMAS_OUT = ROOT / "lemmas.txt"


def build_lemma_groups(tokens: set[str], morph: MorphAnalyzer) -> dict[str, set[str]]:
    """lemma -> множество поверхностных форм (токенов)."""
    groups: dict[str, set[str]] = defaultdict(set)
    for t in tokens:
        lem = lemma_for_token(t, morph)
        groups[lem].add(t)
    return groups


def main() -> int:
    stopwords = load_stopwords(STOPWORDS_FILE)
    print("Сбор токенов из corpus/…", flush=True)
    tokens = collect_unique_tokens(stopwords)
    print(f"  уникальных токенов после фильтров: {len(tokens)}", flush=True)

    morph = MorphAnalyzer()
    groups = build_lemma_groups(tokens, morph)
    print(f"  уникальных лемм: {len(groups)}", flush=True)

    sorted_tokens = sorted(tokens)
    TOKENS_OUT.write_text("\n".join(sorted_tokens) + "\n", encoding="utf-8")

    lemma_lines: list[str] = []
    for lemma in sorted(groups):
        forms = " ".join(sorted(groups[lemma]))
        lemma_lines.append(f"{lemma} {forms}")
    LEMMAS_OUT.write_text("\n".join(lemma_lines) + "\n", encoding="utf-8")

    print(f"Записано: {TOKENS_OUT}", flush=True)
    print(f"Записано: {LEMMAS_OUT}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        raise SystemExit(1)
