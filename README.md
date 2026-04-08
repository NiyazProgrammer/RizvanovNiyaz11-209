# Основы информационного поиска

ФИО: Ризванов Нияз  
Группа: 11-209

## Задание: корпус страниц Хабра

- **Код:** [`crawl.py`](crawl.py) — краулер (сбор URL с лент → выкачка HTML).
- **Вход:** [`seed_urls.txt`](seed_urls.txt) — URL страниц лент (`/ru/articles/`, `page2`, …; при необходимости добавлены `page8`–`page10`, чтобы набрать ≥100 уникальных статей).
- **Выход:** каталог [`corpus/`](corpus/) (`001.txt` … `100.txt`, **сырой HTML без очистки**), в корне [`index.txt`](index.txt) — строки `номер<TAB>URL`.

Подробные шаги установки, проверки результата **без запуска** и заметки по коммитам: **[`DEPLOYMENT.md`](DEPLOYMENT.md)**.

## Быстрый запуск

```bash
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python crawl.py
```

Запускать из корня репозитория (там же лежат `seed_urls.txt`, `crawl.py`).

## Без запуска кода

1. Откройте [`index.txt`](index.txt) — должно быть **100** строк, формат `число<TAB>https://habr.com/ru/...`.
2. Откройте [`corpus/001.txt`](corpus/001.txt) — это HTML-страница статьи (не «чистый текст»).
3. Номер в индексе `N` соответствует файлу `corpus/NNN.txt` с ведущими нулями (например, `7` → `007.txt`).

Если в репозитории нет папки `corpus/` (не закоммичена из‑за размера), проверка по инструкции в [`DEPLOYMENT.md`](DEPLOYMENT.md) — либо один раз выполнить команды из раздела «Установка и запуск».

## Токенизация и лемматизация

После того как заполнен каталог [`corpus/`](corpus/):

```bash
pip install -r requirements.txt
python tokenize_lemmatize.py
```

- **Вход:** все `corpus/*.txt` (HTML), стоп-слова — [`ru_stopwords.txt`](ru_stopwords.txt).
- **Выход:**
  - [`tokens.txt`](tokens.txt) — уникальные токены, **одна строка = один токен** (нижний регистр, без чисел, союзов/предлогов из стоп-листа и «мусора» с цифрами).
  - [`lemmas.txt`](lemmas.txt) — строки вида `лемма токен1 токен2 …` (леммы и токены в группе отсортированы по алфавиту).

Логика: из HTML удаляются `script`/`style`/`noscript`, текст токенизируется; русские слова лемматизируются через **pymorphy3**, чисто латинские токены (термины) — лемма совпадает с токеном.

## Зависимости

См. [`requirements.txt`](requirements.txt): `requests`, `beautifulsoup4`, `lxml`, `pymorphy3`, `pymorphy3-dicts-ru`.
