#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TF-IDF по каждому документу корпуса (задание 1) и словарям задания 2.

Термины: tokens.txt (порядок строк сохраняется).
Леммы: lemmas.txt — строка «лемма форма1 форма2 …»; TF леммы = сумма частот форм / |d|.

Формулы (натуральный логарифм):
  |d| = сумма частот всех отфильтрованных токенов в документе.
  tf(термин, d) = count(термин, d) / |d|,  |d| = 0 => tf = 0.
  tf(лемма, d) = (сумма count(форма, d) по формам из lemmas.txt) / |d|.
  df — число документов, где величина > 0.
  idf = ln((N + 1) / (df + 1)).
  tf-idf = tf * idf.

Выход (UTF-8, пробел как разделитель):
  tfidf_terms/NNN.txt — строки: термин idf tf-idf
  tfidf_lemmas/NNN.txt — строки: лемма idf tf-idf

Перед запуском: python tokenize_lemmatize.py (нужны tokens.txt и lemmas.txt).

Запуск:
  python tfidf_export.py
  python tfidf_export.py --sparse   # только строки с tf > 0 в данном документе
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

from corpus_text import (
    CORPUS_DIR,
    ROOT,
    STOPWORDS_FILE,
    count_tokens_in_text,
    html_to_text,
    load_stopwords,
)

TOKENS_FILE = ROOT / "tokens.txt"
LEMMAS_FILE = ROOT / "lemmas.txt"
TERMS_OUT_DIR = ROOT / "tfidf_terms"
LEMMAS_OUT_DIR = ROOT / "tfidf_lemmas"


def idf_smoothed(df: int, n_docs: int) -> float:
    """Сглаженный IDF: ln((N + 1) / (df + 1))."""
    return math.log((n_docs + 1) / (df + 1))


def load_terms_ordered(path: Path) -> list[str]:
    terms: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        t = line.strip()
        if t:
            terms.append(t)
    return terms


def load_lemma_rows_ordered(path: Path) -> list[tuple[str, frozenset[str]]]:
    """
    Порядок строк lemmas.txt: (лемма, множество поверхностных форм из строки).
    Первая лексема строки — лемма, остальные — токены-формы.
    """
    rows: list[tuple[str, frozenset[str]]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if not parts:
            continue
        lemma = parts[0]
        # Формы из строки; если только лемма — считаем вхождения токена, совпадающего с леммой.
        forms = frozenset(parts[1:]) if len(parts) > 1 else frozenset([lemma])
        rows.append((lemma, forms))
    return rows


def collect_document_counters(stopwords: set[str]) -> tuple[list[Path], list]:
    paths = sorted(CORPUS_DIR.glob("*.txt"))
    if not paths:
        raise FileNotFoundError(f"В {CORPUS_DIR} нет .txt файлов")
    counters: list = []
    for p in paths:
        html = p.read_text(encoding="utf-8", errors="replace")
        text = html_to_text(html)
        counters.append(count_tokens_in_text(text, stopwords))
    return paths, counters


def compute_df_terms(terms: list[str], counters: list) -> dict[str, int]:
    df: dict[str, int] = {}
    for t in terms:
        df[t] = sum(1 for c in counters if c[t] > 0)
    return df


def compute_df_lemmas(
    rows: list[tuple[str, frozenset[str]]], counters: list
) -> dict[str, int]:
    df: dict[str, int] = {}
    for lemma, forms in rows:
        def doc_has_lemma(c) -> bool:
            return sum(c.get(w, 0) for w in forms) > 0

        df[lemma] = sum(1 for c in counters if doc_has_lemma(c))
    return df


def lemma_tf(counter, forms: frozenset[str], doc_total: int) -> float:
    if doc_total <= 0:
        return 0.0
    s = sum(counter.get(w, 0) for w in forms)
    return s / doc_total


def write_doc_terms_file(
    path_out: Path,
    terms: list[str],
    idf_by_term: dict[str, float],
    counter,
    doc_total: int,
    sparse: bool,
) -> None:
    lines: list[str] = []
    for t in terms:
        idf_t = idf_by_term[t]
        tf_t = (counter[t] / doc_total) if doc_total > 0 else 0.0
        if sparse and tf_t == 0.0:
            continue
        tfidf = tf_t * idf_t
        lines.append(f"{t} {idf_t:.10f} {tfidf:.10f}")
    path_out.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def write_doc_lemmas_file(
    path_out: Path,
    rows: list[tuple[str, frozenset[str]]],
    idf_by_lemma: dict[str, float],
    counter,
    doc_total: int,
    sparse: bool,
) -> None:
    lines: list[str] = []
    for lemma, forms in rows:
        idf_l = idf_by_lemma[lemma]
        tf_l = lemma_tf(counter, forms, doc_total)
        if sparse and tf_l == 0.0:
            continue
        tfidf = tf_l * idf_l
        lines.append(f"{lemma} {idf_l:.10f} {tfidf:.10f}")
    path_out.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Экспорт TF-IDF по документам.")
    parser.add_argument(
        "--sparse",
        action="store_true",
        help="Писать только термины/леммы с ненулевым tf в данном документе",
    )
    args = parser.parse_args()

    if not TOKENS_FILE.is_file():
        print(f"Нет {TOKENS_FILE}. Запустите: python tokenize_lemmatize.py", file=sys.stderr)
        return 1
    if not LEMMAS_FILE.is_file():
        print(f"Нет {LEMMAS_FILE}. Запустите: python tokenize_lemmatize.py", file=sys.stderr)
        return 1

    stopwords = load_stopwords(STOPWORDS_FILE)
    terms = load_terms_ordered(TOKENS_FILE)
    lemma_rows = load_lemma_rows_ordered(LEMMAS_FILE)

    print("Чтение корпуса и подсчёт частот…", flush=True)
    paths, counters = collect_document_counters(stopwords)
    n_docs = len(paths)
    print(f"  документов: {n_docs}", flush=True)

    print("DF / IDF для терминов…", flush=True)
    df_terms = compute_df_terms(terms, counters)
    idf_terms = {t: idf_smoothed(df_terms[t], n_docs) for t in terms}

    print("DF / IDF для лемм…", flush=True)
    df_lemmas = compute_df_lemmas(lemma_rows, counters)
    idf_lemmas = {lem: idf_smoothed(df_lemmas[lem], n_docs) for lem, _ in lemma_rows}

    TERMS_OUT_DIR.mkdir(parents=True, exist_ok=True)
    LEMMAS_OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Запись tfidf_terms/ и tfidf_lemmas/…", flush=True)
    for p, c in zip(paths, counters, strict=True):
        stem = p.stem
        doc_total = sum(c.values())
        write_doc_terms_file(
            TERMS_OUT_DIR / f"{stem}.txt",
            terms,
            idf_terms,
            c,
            doc_total,
            args.sparse,
        )
        write_doc_lemmas_file(
            LEMMAS_OUT_DIR / f"{stem}.txt",
            lemma_rows,
            idf_lemmas,
            c,
            doc_total,
            args.sparse,
        )

    mode = "sparse" if args.sparse else "полный словарь"
    print(f"Готово ({mode}). {TERMS_OUT_DIR}/, {LEMMAS_OUT_DIR}/", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        raise SystemExit(1)
