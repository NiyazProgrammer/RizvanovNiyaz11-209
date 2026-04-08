# -*- coding: utf-8 -*-
"""
Общая обработка HTML корпуса: извлечение текста, токены, леммы (как в tokenize_lemmatize).
Используется tokenize_lemmatize.py, boolean_search.py, tfidf_export.py и vector_search.py.
"""

from __future__ import annotations

import re
from collections import Counter
from html import unescape
from pathlib import Path

from bs4 import BeautifulSoup
from pymorphy3 import MorphAnalyzer

ROOT = Path(__file__).resolve().parent
CORPUS_DIR = ROOT / "corpus"
STOPWORDS_FILE = ROOT / "ru_stopwords.txt"

TOKEN_RE = re.compile(r"[A-Za-zА-Яа-яЁё]+")
URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
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
    """Удаляет script/style/noscript и извлекает видимый текст."""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator=" ")
    return unescape(text)


def count_tokens_in_text(raw: str, stopwords: set[str]) -> Counter[str]:
    """
    Частоты токенов с теми же фильтрами, что для множества уникальных токенов
    (нижний регистр, буквы, без цифр, не стоп-слова, длина >= MIN_TOKEN_LEN).
    """
    raw = URL_RE.sub(" ", raw)
    lowered = raw.lower()
    cnt: Counter[str] = Counter()
    for m in TOKEN_RE.finditer(lowered):
        t = m.group(0)
        if len(t) < MIN_TOKEN_LEN:
            continue
        if any(ch.isdigit() for ch in t):
            continue
        if t in stopwords:
            continue
        cnt[t] += 1
    return cnt


def extract_tokens_from_text(raw: str, stopwords: set[str]) -> set[str]:
    """Уникальные токены (ключи счётчика)."""
    return set(count_tokens_in_text(raw, stopwords).keys())


def lemma_for_token(token: str, morph: MorphAnalyzer) -> str:
    """Русские слова — normal_form pymorphy3; чистая латиница — лемма = токен."""
    if _CYRILLIC_IN_TOKEN.search(token):
        p = morph.parse(token)
        if p:
            return p[0].normal_form
    return token


def lemmas_for_html(html: str, stopwords: set[str], morph: MorphAnalyzer) -> set[str]:
    """Множество лемм одного HTML-документа (те же фильтры, что для корпуса)."""
    text = html_to_text(html)
    tokens = extract_tokens_from_text(text, stopwords)
    return {lemma_for_token(t, morph) for t in tokens}


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
