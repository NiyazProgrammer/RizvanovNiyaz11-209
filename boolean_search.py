#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Инвертированный индекс по corpus/ (леммы) и булев поиск: AND, OR, NOT, скобки.

Приоритеты операторов: NOT > AND > OR (как в типичной булевой логике).
Пример:  a OR b AND c  ==  a OR (b AND c)

Сборка индекса:  python boolean_search.py build
Поиск:         python boolean_search.py -q '(слово1 AND слово2) OR слово3'
Интерактивно:  python boolean_search.py
(ввод строки запроса; пустая строка или quit — выход)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from pymorphy3 import MorphAnalyzer

from corpus_text import (
    CORPUS_DIR,
    ROOT,
    STOPWORDS_FILE,
    TOKEN_RE,
    lemma_for_token,
    lemmas_for_html,
    load_stopwords,
)

INDEX_FILE = ROOT / "index.txt"
INVERTED_INDEX_FILE = ROOT / "inverted_index.json"


# --- индекс ---


def build_inverted_index() -> dict:
    """Строит индекс по corpus/*.txt; возвращает сериализуемый dict."""
    stopwords = load_stopwords(STOPWORDS_FILE)
    morph = MorphAnalyzer()
    postings: dict[str, set[int]] = defaultdict(set)
    doc_ids: list[int] = []

    paths = sorted(CORPUS_DIR.glob("*.txt"))
    if not paths:
        raise FileNotFoundError(f"В {CORPUS_DIR} нет .txt файлов")

    for p in paths:
        doc_id = int(p.stem)
        doc_ids.append(doc_id)
        html = p.read_text(encoding="utf-8", errors="replace")
        for lem in lemmas_for_html(html, stopwords, morph):
            postings[lem].add(doc_id)

    return {
        "num_docs": len(doc_ids),
        "doc_ids": sorted(doc_ids),
        "postings": {t: sorted(ids) for t, ids in sorted(postings.items())},
    }


def save_index(data: dict) -> None:
    INVERTED_INDEX_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Индекс записан: {INVERTED_INDEX_FILE}", flush=True)


def load_index() -> tuple[dict[str, set[int]], set[int]]:
    """postings (лемма -> множество doc_id), universe — все doc_id."""
    if not INVERTED_INDEX_FILE.is_file():
        raise FileNotFoundError(
            f"Нет файла {INVERTED_INDEX_FILE}. Сначала выполните: python boolean_search.py build"
        )
    raw = json.loads(INVERTED_INDEX_FILE.read_text(encoding="utf-8"))
    universe = set(raw["doc_ids"])
    postings = {k: set(v) for k, v in raw["postings"].items()}
    return postings, universe


def load_doc_urls() -> dict[int, str]:
    """doc_id -> URL из index.txt (строка k соответствует документу k)."""
    if not INDEX_FILE.is_file():
        return {}
    out: dict[int, str] = {}
    for line in INDEX_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or "\t" not in line:
            continue
        num_s, url = line.split("\t", 1)
        try:
            out[int(num_s.strip())] = url.strip()
        except ValueError:
            continue
    return out


# --- лексер запроса ---


def lex_query(s: str) -> list[tuple[str, str | None]]:
    """
    Список токенов: ('LP',), ('RP',), ('AND',), ('OR',), ('NOT',), ('WORD', 'слово').
    """
    tokens: list[tuple[str, str | None]] = []
    i = 0
    n = len(s)

    def kw_at(pos: int, kw: str) -> bool:
        L = len(kw)
        if pos + L > n:
            return False
        if s[pos : pos + L].lower() != kw:
            return False
        if pos + L < n and s[pos + L].isalnum():
            return False
        return True

    while i < n:
        c = s[i]
        if c.isspace():
            i += 1
            continue
        if c == "(":
            tokens.append(("LP", None))
            i += 1
            continue
        if c == ")":
            tokens.append(("RP", None))
            i += 1
            continue
        if kw_at(i, "and"):
            tokens.append(("AND", None))
            i += 3
            continue
        if kw_at(i, "or"):
            tokens.append(("OR", None))
            i += 2
            continue
        if kw_at(i, "not"):
            tokens.append(("NOT", None))
            i += 3
            continue
        m = TOKEN_RE.match(s, i)
        if not m:
            raise ValueError(f"Неожиданный символ в позиции {i}: {s[i]!r}")
        word = m.group(0).lower()
        tokens.append(("WORD", word))
        i = m.end()

    return tokens


# --- парсер и вычисление ---


class BooleanParser:
    """
    Грамматика (приоритет NOT > AND > OR):
      expr     ::= or_expr
      or_expr  ::= and_expr ( OR and_expr )*
      and_expr ::= not_expr ( AND not_expr )*
      not_expr ::= NOT not_expr | primary
      primary  ::= '(' expr ')' | WORD
    """

    def __init__(
        self,
        tokens: list[tuple[str, str | None]],
        universe: set[int],
        postings: dict[str, set[int]],
        morph: MorphAnalyzer,
    ) -> None:
        self.toks = tokens
        self.i = 0
        self.universe = universe
        self.postings = postings
        self.morph = morph

    def peek(self) -> str | None:
        if self.i >= len(self.toks):
            return None
        return self.toks[self.i][0]

    def term_set(self, surface: str) -> set[int]:
        lem = lemma_for_token(surface, self.morph)
        return set(self.postings.get(lem, ()))

    def parse(self) -> set[int]:
        if not self.toks:
            return set()
        result = self.parse_or()
        if self.peek() is not None:
            raise ValueError("Лишние токены после конца выражения")
        return result

    def parse_or(self) -> set[int]:
        left = self.parse_and()
        while self.peek() == "OR":
            self.i += 1
            right = self.parse_and()
            left = left | right
        return left

    def parse_and(self) -> set[int]:
        left = self.parse_not()
        while self.peek() == "AND":
            self.i += 1
            right = self.parse_not()
            left = left & right
        return left

    def parse_not(self) -> set[int]:
        if self.peek() == "NOT":
            self.i += 1
            inner = self.parse_not()
            return self.universe - inner
        return self.parse_primary()

    def parse_primary(self) -> set[int]:
        t = self.peek()
        if t == "LP":
            self.i += 1
            inner = self.parse_or()
            if self.peek() != "RP":
                raise ValueError("Ожидалась закрывающая скобка ')'")
            self.i += 1
            return inner
        if t == "WORD":
            w = self.toks[self.i][1]
            assert w is not None
            self.i += 1
            return self.term_set(w)
        raise ValueError(f"Ожидался термин или '(', получено: {t}")


def search_query(
    query: str,
    postings: dict[str, set[int]],
    universe: set[int],
    morph: MorphAnalyzer,
) -> set[int]:
    q = query.strip()
    if not q:
        return set()
    tokens = lex_query(q)
    parser = BooleanParser(tokens, universe, postings, morph)
    return parser.parse()


def print_results(doc_ids: set[int], urls: dict[int, str]) -> None:
    for did in sorted(doc_ids):
        u = urls.get(did, "")
        if u:
            print(f"{did}\t{u}")
        else:
            print(did)


def cmd_build() -> int:
    data = build_inverted_index()
    save_index(data)
    print(f"Документов: {data['num_docs']}, терминов в индексе: {len(data['postings'])}")
    return 0


def cmd_search_loop(
    postings: dict[str, set[int]],
    universe: set[int],
    morph: MorphAnalyzer,
    urls: dict[int, str],
    single_query: str | None,
) -> int:
    if single_query is not None:
        try:
            hits = search_query(single_query, postings, universe, morph)
        except (ValueError, AssertionError) as e:
            print(f"Ошибка запроса: {e}", file=sys.stderr)
            return 1
        print_results(hits, urls)
        print(f"Найдено документов: {len(hits)}")
        return 0

    print("Булев поиск (AND / OR / NOT, скобки). Пустая строка или quit — выход.")
    print("Приоритеты: NOT > AND > OR. Пример: (a AND b) OR c OR NOT d")
    while True:
        try:
            line = input("query> ").strip()
        except EOFError:
            print()
            break
        if not line or line.lower() in ("quit", "exit", "q"):
            break
        try:
            hits = search_query(line, postings, universe, morph)
        except (ValueError, AssertionError) as e:
            print(f"Ошибка: {e}")
            continue
        print_results(hits, urls)
        print(f"Найдено: {len(hits)}")

    return 0


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "build":
        try:
            return cmd_build()
        except FileNotFoundError as e:
            print(e, file=sys.stderr)
            return 1

    parser = argparse.ArgumentParser(
        description="Булев поиск по inverted_index.json (см. подкоманду build)."
    )
    parser.add_argument(
        "-q",
        "--query",
        type=str,
        default=None,
        help="Один запрос без интерактивного режима",
    )
    args = parser.parse_args(sys.argv[1:])

    try:
        postings, universe = load_index()
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 1

    morph = MorphAnalyzer()
    urls = load_doc_urls()
    return cmd_search_loop(postings, universe, morph, urls, args.query)


if __name__ == "__main__":
    raise SystemExit(main())
