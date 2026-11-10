# Набор сценариев задачи

Пакеты `tasks/quixbugs-*` собраны из набора **QuixBugs** (James Koppel), MIT — полный текст в [QUIXBUGS_LICENSE.txt](QUIXBUGS_LICENSE.txt).

- Источник: <https://github.com/jkoppel/QuixBugs>
- Ревизия: `4257f44b0ff1181dedaedee6a447e133219fcebf`
- Взято: `python_programs/<имя>.py` (версия с дефектом), `correct_python_programs/<имя>.py` (эталон), `json_testcases/<имя>.json` (случаи, по одному JSON на строку)

## Почему эти десять

Отобраны случаи, которые проверяются только стандартной библиотекой, не требуют вспомогательных модулей (`node.py` и подобных) и имеют машинные случаи в `json_testcases`: `bitcount`, `bucketsort`, `find_first_in_sorted`, `flatten`, `gcd`, `is_valid_parenthesization`, `kheapsort`, `lcs_length`, `max_sublist_sum`, `next_palindrome`.

## Устройство пакета

| Файл | Содержимое |
|---|---|
| `project/<имя>.py` | исходная версия с дефектом (исполнитель видит только её) |
| `context/<имя>.md` | краткий контекст модуля |
| `request.md` | запрос на русском, без подсказки решения |
| `evaluation/check.py` | детерминированная проверка: импортирует модуль исполнителя и прогоняет все случаи |
| `evaluation/testcases.json` | случаи из QuixBugs, по одному JSON на строку |
| `evaluation/reference.md` | эталонная реализация для оценщика |
| `evaluation/instructions.md` | инструкции оценщику |
| `task.json` | имя задачи и команда проверки |

Проверка не использует модель, сеть и сторонние пакеты. Генераторы (`flatten`, `kheapsort`) материализуются перед сравнением.

## Известные особенности

- Дефектные версии `bitcount` и `find_first_in_sorted` зацикливаются на части случаев. Проверка таких решений завершается по общему `--timeout` и даёт исход `TIMEOUT`; эталонные версии проходят быстро.
- Тексты `request.md` и `context/*.md` написаны для бенчмарка и не являются частью QuixBugs.

## Добавление новых случаев

Скопировать три файла из QuixBugs по той же схеме и сгенерировать `check.py` с подставленным именем модуля. Случаи QuixBugs считать эталоном поведения: правки в них не вносить.
