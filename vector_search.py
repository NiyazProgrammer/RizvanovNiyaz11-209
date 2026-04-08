#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Векторный поиск по TF-IDF: документы — разреженные векторы из tfidf_terms/NNN.txt,
запрос — tf-idf с теми же idf; ранжирование по косинусной близости.

Зависимости: python tokenize_lemmatize.py && python tfidf_export.py

Вес запроса для терма t: tf_q(t) * idf(t), где tf_q(t) = count(t) / |q|,
|q| — сумма частот токенов запроса после фильтров (как в corpus_text).

Запуск:
  python vector_search.py
  python vector_search.py -q "python машинное обучение" --top 15
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

from corpus_text import ROOT, STOPWORDS_FILE, count_tokens_in_text, load_stopwords

INDEX_FILE = ROOT / "index.txt"
TOKENS_FILE = ROOT / "tokens.txt"
TERMS_DIR = ROOT / "tfidf_terms"


def load_doc_urls() -> dict[int, str]:
    """doc_id -> URL из index.txt."""
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


def parse_tfidf_line(line: str) -> tuple[str, float, float]:
    """Строка 'термин idf tf-idf' (термин без пробелов)."""
    line = line.strip()
    if not line:
        raise ValueError("empty line")
    term, idf_s, tfidf_s = line.rsplit(" ", 2)
    return term, float(idf_s), float(tfidf_s)


def load_tfidf_index() -> tuple[list[tuple[int, dict[str, float], float]], dict[str, float]]:
    """
    Загружает все tfidf_terms/NNN.txt.
    Возвращает: список (doc_id, {term: tfidf}, ||d||), и словарь idf[term]
    (idf одинаков для терма во всех файлах).
    """
    if not TERMS_DIR.is_dir():
        raise FileNotFoundError(
            f"Нет каталога {TERMS_DIR}. Выполните: python tfidf_export.py"
        )
    paths = sorted(TERMS_DIR.glob("*.txt"))
    if not paths:
        raise FileNotFoundError(f"В {TERMS_DIR} нет .txt файлов")

    idf_by_term: dict[str, float] = {}
    docs: list[tuple[int, dict[str, float], float]] = []

    for p in paths:
        doc_id = int(p.stem)
        weights: dict[str, float] = {}
        for raw in p.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            term, idf_v, tfidf_v = parse_tfidf_line(raw)
            idf_by_term[term] = idf_v
            if abs(tfidf_v) > 1e-18:
                weights[term] = tfidf_v
        norm_d = math.sqrt(sum(w * w for w in weights.values()))
        docs.append((doc_id, weights, norm_d))

    return docs, idf_by_term


def query_weights(
    query: str,
    stopwords: set[str],
    idf_by_term: dict[str, float],
) -> tuple[dict[str, float], float]:
    """
    Вектор запроса: w(t) = tf_q(t) * idf(t), только термы из словаря idf.
    Возвращает (weights, ||q||).
    """
    c = count_tokens_in_text(query, stopwords)
    total = sum(c.values())
    if total <= 0:
        return {}, 0.0
    wq: dict[str, float] = {}
    for t, cnt in c.items():
        if t not in idf_by_term:
            continue
        tf_q = cnt / total
        wq[t] = tf_q * idf_by_term[t]
    norm_q = math.sqrt(sum(v * v for v in wq.values()))
    return wq, norm_q


def cosine_scores(
    q_weights: dict[str, float],
    norm_q: float,
    docs: list[tuple[int, dict[str, float], float]],
) -> list[tuple[int, float]]:
    """Список (doc_id, cosine_similarity), без сортировки."""
    if norm_q <= 0:
        return [(d[0], 0.0) for d in docs]
    scores: list[tuple[int, float]] = []
    for doc_id, dvec, norm_d in docs:
        if norm_d <= 0:
            scores.append((doc_id, 0.0))
            continue
        dot = 0.0
        for t, qw in q_weights.items():
            if t in dvec:
                dot += qw * dvec[t]
        sim = dot / (norm_q * norm_d)
        scores.append((doc_id, sim))
    return scores


def print_results(
    ranked: list[tuple[int, float]],
    urls: dict[int, str],
    top: int,
) -> None:
    for rank, (doc_id, score) in enumerate(ranked[:top], start=1):
        u = urls.get(doc_id, "")
        if u:
            print(f"{rank}\t{doc_id}\t{score:.6f}\t{u}")
        else:
            print(f"{rank}\t{doc_id}\t{score:.6f}")


def run_search(
    query: str,
    docs: list[tuple[int, dict[str, float], float]],
    idf_by_term: dict[str, float],
    stopwords: set[str],
    urls: dict[int, str],
    top: int,
) -> None:
    q_w, norm_q = query_weights(query, stopwords, idf_by_term)
    if not q_w or norm_q <= 0.0:
        print(
            "Нет весов запроса: пустой текст, только стоп-слова или слова вне словаря tokens.txt.",
            flush=True,
        )
        return
    scores = cosine_scores(q_w, norm_q, docs)
    ranked = sorted(scores, key=lambda x: (-x[1], x[0]))
    print_results(ranked, urls, top)
    print(f"Показано до {top} из {len(docs)} документов.", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Векторный поиск (косинус) по TF-IDF из tfidf_terms/."
    )
    parser.add_argument("-q", "--query", type=str, default=None, help="Один запрос")
    parser.add_argument(
        "--top",
        type=int,
        default=10,
        help="Число документов в выдаче (по умолчанию 10)",
    )
    args = parser.parse_args()

    if not TOKENS_FILE.is_file():
        print(
            f"Нет {TOKENS_FILE}. Сначала: python tokenize_lemmatize.py",
            file=sys.stderr,
        )
        return 1

    try:
        docs, idf_by_term = load_tfidf_index()
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 1

    stopwords = load_stopwords(STOPWORDS_FILE)
    urls = load_doc_urls()

    if args.query is not None:
        run_search(args.query, docs, idf_by_term, stopwords, urls, args.top)
        return 0

    print("Векторный поиск по TF-IDF (косинус). Пустая строка или quit — выход.")
    while True:
        try:
            line = input("query> ").strip()
        except EOFError:
            print()
            break
        if not line or line.lower() in ("quit", "exit", "q"):
            break
        run_search(line, docs, idf_by_term, stopwords, urls, args.top)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        raise SystemExit(1)
