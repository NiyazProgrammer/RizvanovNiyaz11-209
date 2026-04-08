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

Общие функции обработки текста: [`corpus_text.py`](corpus_text.py) (используются `tokenize_lemmatize.py` и `boolean_search.py`).

## Инвертированный индекс и булев поиск

После заполнения [`corpus/`](corpus/):

```bash
python boolean_search.py build    # создать inverted_index.json
python boolean_search.py          # интерактивный ввод запроса (строка не хардкодится)
python boolean_search.py -q "(python AND код) OR telegram"
```

- **Индекс:** [`inverted_index.json`](inverted_index.json) — лемма → списки `doc_id` (те же правила нормализации, что при токенизации).
- **Операторы:** `AND`, `OR`, `NOT` (без учёта регистра), скобки. **Приоритеты:** `NOT` сильнее `AND`, `AND` сильнее `OR` (т.е. `a OR b AND c` читается как `a OR (b AND c)`).
- **Вывод:** `doc_id` и URL из [`index.txt`](index.txt).

Код: [`boolean_search.py`](boolean_search.py).

## TF-IDF по документам (термины и леммы)

Нужны [`tokens.txt`](tokens.txt) и [`lemmas.txt`](lemmas.txt) (сначала `python tokenize_lemmatize.py`), каталог [`corpus/`](corpus/).

```bash
python tfidf_export.py
python tfidf_export.py --sparse   # только ненулевой tf в документе (меньше строк)
```

- **Выход:** каталоги [`tfidf_terms/`](tfidf_terms/) и [`tfidf_lemmas/`](tfidf_lemmas/) — по файлу `NNN.txt` на документ `corpus/NNN.txt`.
- **Строка:** `<термин или лемма><пробел><idf><пробел><tf-idf>` (UTF-8, фиксированный порядок как в `tokens.txt` / строках `lemmas.txt`).

**Формулы** (натуральный логарифм): \(|d|\) — сумма частот отфильтрованных токенов в документе;  
\(\text{tf}_{\text{терм}} = \text{count}(t,d)/|d|\);  
\(\text{tf}_{\text{лемма}} = \sum_{w \in \text{формы леммы}} \text{count}(w,d) / |d|\);  
\(\text{idf} = \ln\frac{N+1}{\text{df}+1}\); **tf-idf** = tf × idf.  
\(N\) — число документов; **df** — в скольких документах встречается термин / лемма (сумма частот форм > 0).

Код: [`tfidf_export.py`](tfidf_export.py); частоты токенов — [`count_tokens_in_text`](corpus_text.py) в [`corpus_text.py`](corpus_text.py).

Папки `tfidf_*` в [`.gitignore`](.gitignore) — при сдаче сгенерируйте локально или добавьте в коммит принудительно.

## Зависимости

См. [`requirements.txt`](requirements.txt): `requests`, `beautifulsoup4`, `lxml`, `pymorphy3`, `pymorphy3-dicts-ru`.
