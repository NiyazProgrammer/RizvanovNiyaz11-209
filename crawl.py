#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Двухфазный краулер корпуса Хабра (курс «Основы информационного поиска»).

Фаза 1: загрузка страниц лент из seed_urls.txt, парсинг ссылок, отбор URL статей,
        дедупликация с сохранением порядка обхода.
Фаза 2: последовательная загрузка HTML статей и запись в corpus/NNN.txt + index.txt.

Требования задания: ≥100 страниц на русском, сырой HTML без очистки разметки,
отдельные .js/.css/картинки по URL не качаются (в документе остаются только теги).

Запуск из корня репозитория:  python crawl.py
См. README.md и DEPLOYMENT.md.
"""

from __future__ import annotations

import random
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

# --- Пути относительно каталога, где лежит скрипт (удобно запускать из любого cwd) ---
ROOT = Path(__file__).resolve().parent
SEED_FILE = ROOT / "seed_urls.txt"
CORPUS_DIR = ROOT / "corpus"
INDEX_FILE = ROOT / "index.txt"

# --- Параметры выкачки ---
MIN_ARTICLES = 100  # минимум уникальных статей по заданию
REQUEST_TIMEOUT = 30
MAX_RETRIES = 4  # повтор при сетевых ошибках и 429/5xx

# User-Agent с пометкой учебного проекта — вежливость к сайту и идентификация трафика.
USER_AGENT = (
    "Mozilla/5.0 (compatible; RizvanovNiyaz11-209/1.0; +edu; Habr corpus crawler)"
)

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": USER_AGENT})

# URL статьи: /ru/articles/<числовой_id> или /ru/articles/<id>-slug/ (не page2, не список).
ARTICLE_PATH = re.compile(r"^/ru/articles/\d+(?:-[\w.-]+)?/?$")
# Легаси-формат постов на Хабре.
POST_PATH = re.compile(r"^/ru/post/\d+/?$")


def canonical_url(url: str) -> str:
    """Приводит URL статьи к виду https://habr.com/.../ с завершающим слэшем (дедуп)."""
    p = urlparse(url)
    path = p.path or "/"
    if not path.endswith("/"):
        path = path + "/"
    return urlunparse(("https", "habr.com", path, "", "", ""))


def is_article_url(url: str) -> bool:
    """True только для страниц статей/постов на habr.com (ru), не для хабов и статики."""
    try:
        p = urlparse(url)
    except ValueError:
        return False
    host = p.netloc.lower()
    if host == "www.habr.com":
        host = "habr.com"
    if host != "habr.com":
        return False
    if p.scheme not in ("http", "https"):
        return False
    path = p.path or ""
    if ARTICLE_PATH.match(path):
        return True
    if POST_PATH.match(path):
        return True
    return False


def fetch(url: str) -> str:
    """
    GET с повторными попытками и экспоненциальной задержкой при перегрузке/ошибках.
    Возвращает тело ответа как str (кодировка из ответа или apparent_encoding).
    """
    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            r = SESSION.get(url, timeout=REQUEST_TIMEOUT)
            if r.status_code in (429, 500, 502, 503, 504):
                wait = 2**attempt + random.uniform(0, 1)
                time.sleep(wait)
                continue
            r.raise_for_status()
            if not r.encoding or r.encoding == "ISO-8859-1":
                r.encoding = r.apparent_encoding or "utf-8"
            return r.text
        except requests.RequestException as e:
            last_err = e
            wait = 2**attempt + random.uniform(0, 1)
            time.sleep(wait)
    raise RuntimeError(f"Failed to fetch {url}: {last_err}")


def collect_article_urls_from_html(html: str, base_url: str) -> list[str]:
    """Из HTML ленты извлекает все href, оставляя только URL статей (порядок как в DOM)."""
    soup = BeautifulSoup(html, "lxml")
    out: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        full = urljoin(base_url, href)
        if is_article_url(full):
            out.append(canonical_url(full))
    return out


def load_seeds() -> list[str]:
    """Читает seed_urls.txt: непустые строки, без комментариев (# в начале)."""
    if not SEED_FILE.is_file():
        raise FileNotFoundError(f"Missing {SEED_FILE}")
    lines = []
    for line in SEED_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            lines.append(line)
    return lines


def phase1_collect_urls(seeds: list[str]) -> list[str]:
    """
    Обходит seed-страницы по порядку, накапливает уникальные URL статей.
    Между запросами к лентам — случайная пауза ~0.5–1.5 с (нагрузка на habr.com).
    """
    seen: set[str] = set()
    ordered: list[str] = []
    for seed in seeds:
        time.sleep(0.5 + random.random())
        html = fetch(seed)
        for u in collect_article_urls_from_html(html, seed):
            if u not in seen:
                seen.add(u)
                ordered.append(u)
        print(f"  seed {seed!r} -> total unique articles: {len(ordered)}", flush=True)
    return ordered


def phase2_download(urls: list[str]) -> None:
    """
    Скачивает каждую статью: сырой HTML в corpus/001.txt …, строки индекса в index.txt.
    Формат index.txt: номер<TAB>URL (одна строка на документ).
    """
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for i, url in enumerate(urls, start=1):
        time.sleep(0.5 + random.random())
        html = fetch(url)
        name = f"{i:03d}.txt"
        path = CORPUS_DIR / name
        path.write_text(html, encoding="utf-8", errors="replace")
        lines.append(f"{i}\t{url}")
        if i % 10 == 0:
            print(f"  downloaded {i}/{len(urls)}", flush=True)
    INDEX_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    """Точка входа: сбор URL, проверка MIN_ARTICLES, выкачка ровно 100 первых в списке."""
    seeds = load_seeds()
    print("Phase 1: collecting article URLs from seed pages…", flush=True)
    urls = phase1_collect_urls(seeds)
    if len(urls) < MIN_ARTICLES:
        print(
            f"ERROR: only {len(urls)} unique article URLs (need >= {MIN_ARTICLES}). "
            "Add more lines to seed_urls.txt (e.g. page8, page9).",
            file=sys.stderr,
            flush=True,
        )
        return 1
    urls = urls[:MIN_ARTICLES]
    print(f"Phase 2: downloading {len(urls)} articles…", flush=True)
    phase2_download(urls)
    print(f"Done. Corpus: {CORPUS_DIR}/, index: {INDEX_FILE}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
