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

import re
import sys
from collections import defaultdict
from html import unescape
from pathlib import Path

from bs4 import BeautifulSoup
from pymorphy3 import MorphAnalyzer

ROOT = Path(__file__).resolve().parent
CORPUS_DIR = ROOT / "corpus"
STOPWORDS_FILE = ROOT / "ru_stopwords.txt"
TOKENS_OUT = ROOT / "tokens.txt"
LEMMAS_OUT = ROOT / "lemmas.txt"

# Слова: кириллица или латиница (статьи Хабра — русский + термины латиницей).
TOKEN_RE = re.compile(r"[A-Za-zА-Яа-яЁё]+")
# Удаление URL до токенизации — меньше «мусора» из href/текста ссылок.
URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
# Минимальная длина токена (однобуквенные обрывки отбрасываем).
MIN_TOKEN_LEN = 2

_CYRILLIC_IN_TOKEN = re.compile(r"[а-яё]")


def load_stopwords(path: Path) -> set[str]:
    """Загружает многострочный список стоп-слов (нижний регистр)."""
    if not path.is_file():
        raise FileNotFoundError(f"Нет файла стоп-слов: {path}")
    out: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip().lower()
        if not line or line.startswith("#"):
            continue
        out.add(line)
    return out


def html_to_text(html: str) -> str:
    """Удаляет script/style/noscript и извлекает видимый текст (разметка не сохраняется)."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator=" ")
    return unescape(text)


def extract_tokens_from_text(raw: str, stopwords: set[str]) -> set[str]:
    """
    Нижний регистр, выделение буквенных токенов, фильтры:
    без цифр, без смеси букв/цифр (регекс только буквы), не стоп-слова, длина >= MIN_TOKEN_LEN.
    """
    raw = URL_RE.sub(" ", raw)
    lowered = raw.lower()
    found: set[str] = set()
    for m in TOKEN_RE.finditer(lowered):
        t = m.group(0)
        if len(t) < MIN_TOKEN_LEN:
            continue
        if any(ch.isdigit() for ch in t):
            continue
        if t in stopwords:
            continue
        found.add(t)
    return found


def lemma_for_token(token: str, morph: MorphAnalyzer) -> str:
    """Русские слова — нормальная форма pymorphy3; чистая латиница — лемма = токен."""
    if _CYRILLIC_IN_TOKEN.search(token):
        p = morph.parse(token)
        if p:
            return p[0].normal_form
    return token


def collect_unique_tokens(stopwords: set[str]) -> set[str]:
    """Обходит corpus/*.txt и возвращает объединённое множество токенов."""
    if not CORPUS_DIR.is_dir():
        raise FileNotFoundError(f"Нет каталога корпуса: {CORPUS_DIR}")
    paths = sorted(CORPUS_DIR.glob("*.txt"))
    if not paths:
        raise FileNotFoundError(f"В {CORPUS_DIR} нет .txt файлов")
    all_tokens: set[str] = set()
    for p in paths:
        html = p.read_text(encoding="utf-8", errors="replace")
        text = html_to_text(html)
        all_tokens |= extract_tokens_from_text(text, stopwords)
    return all_tokens


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
