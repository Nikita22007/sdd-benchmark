# SDD Benchmark — прототип

Ядро независимо выбирает пакет задачи, SDD-подход и харнес. Python 3, без сторонних Python-зависимостей.

```powershell
python benchmark.py --task catalog-search --approach demo --harness demo
python benchmark.py --task catalog-search --approach demo --harness noop
```

Первый запуск проходит тесты, второй демонстрирует ошибку. Результат, рабочая копия и логи сохраняются в `runs/<run_id>/`. Код возврата: 0 — успех, 1 — неуспех прогона, 2 — ошибка конфигурации.

Пакет задачи `tasks/<имя>/` включает `task.json`, исходный `project/`, SDD-контекст `context/`, `request.md` и независимую `evaluation/`. Проверка задаётся массивом аргументов `evaluation_command`. Пакет подхода `approaches/<имя>/` содержит `approach.json`, `instructions.md` и опциональную команду `setup_command`. Пакет харнеса `harnesses/<имя>/` содержит `harness.json` с `command` и `requires_model`; необязательное поле `sandbox` фиксирует границу изоляции, объявленную харнесом. В командах поддерживаются `{python}`, `{task}`, `{approach}`, `{harness}`. Доступны переменные `BENCH_WORKSPACE`, `BENCH_TASK`, `BENCH_CONTEXT`, `BENCH_APPROACH`, `BENCH_PYTHON`.

Харнесы, для которых `requires_model` истинно или не задано, не запускаются без явного `--allow-model`. Этот флаг не ограничивает расход токенов. Демо-харнес детерминирован и не является моделью. Пакет `openspec` и харнес `codex` проверены совместным реальным прогоном: `runs/20261110T083419Z-1fe367ff` (задача `catalog-search`, статус `passed`). Настройка OpenSpec требует установленного CLI `openspec` (`npm i -g @fission-ai/openspec`) и Node.js; команда подготовки выполняет `openspec init --tools codex --language Russian`. JSONL Codex сохраняется в `agent/stdout.bin`.

Если Codex на Windows сообщает `helper_sandbox_lock_failed: lock sandbox bin dir ... SetNamedSecurityInfoW ... failed: 5`, заклинил кэш `%USERPROFILE%\.codex\.sandbox-bin`: после остановки Codex удалите эту пустую папку, и она будет создана заново с корректными правами. Подробности реального прогона, включая ошибки, сохраняются в `runs/<run_id>/`.

Исполнители работают с правами текущего пользователя: закрытые проверки и эталон не копируются в рабочую копию, но сам процесс исполнителя не изолирован на уровне ОС. Лимиты токенов пока не реализованы. Запускайте только доверенные команды.

Доступная телеметрия сохраняется в `telemetry.json`. Для Codex каждая запись `requests[]` соответствует одному ходу: `state` (`started` или `completed`), а `usage` содержит поля с пометкой `reported` или `missing`. Поле `usage_granularity` фиксирует достижимую точность (`turn`), `request_usage` остаётся `missing`, а `sources` указывает происхождение событий и usage. Если адаптера нет или он не отработал, запись содержит `note` с причиной отсутствия данных. Исходный JSONL сохраняется целиком. `result.json` дополнительно фиксирует `phases` и `intent`. В `phases` перечислены шаги `setup`, `agent`, `evaluation`, `telemetry` и `judge` с длительностью и доступной точностью расхода: для `agent` это уровень хода, для остальных шагов расход неизвестен (`usage_note`). Пакет подхода может задать `intent_marker` — маску файла, появление которого означает готовность намерения. Ядро следит за рабочей копией и записывает `intent.ready` и `intent.elapsed_seconds`; для `openspec` маркер — `openspec/changes/*/tasks.md`. Без маркера `intent.source` равен `not configured`.

## Отдельная оценка моделью

Оценка моделью не заменяет независимую проверку и не влияет на `status`: она пишется в `judge.json` и в `result.judge`. Пакет задачи задаёт `evaluation/instructions.md` (что проверять) и `evaluation/reference.md` (эталон). Пакет оценки `judges/<имя>/` содержит `judge.json` с `command` и `requires_model`.

```powershell
python benchmark.py --task catalog-search --approach openspec --harness codex --judge codex --allow-model
python benchmark.py --task catalog-search --approach demo --harness demo --judge stub
```

`judges/codex` вызывает Codex в режиме только чтения и требует `--allow-model`; `judges/stub` детерминирован и служит для проверки конвейера без модели. Оценщик получает `BENCH_WORKSPACE`, `BENCH_TASK`, `BENCH_JUDGE_INSTRUCTIONS`, `BENCH_JUDGE_REFERENCE` и `BENCH_JUDGE_CONFIG`; он выводит один JSON-объект с `score` (0…1), `verdict` и необязательными `criteria`/`notes`. Некорректный ответ сохраняется как `invalid_output` и не скрывает исходный журнал.

## Изоляция исполнителя и закрытых проверок

Рабочая копия всегда создаётся вне пакета задачи, а `evaluation/` и эталон запускаются отдельным процессом из каталога задачи и никогда не копируются в рабочую копию. Каждый прогон записывает в `result.isolation` проверяемые факты: `workspace_outside_task_package`, `evaluation_outside_workspace`, `references_in_workspace` (совпадения по содержимому с файлами `evaluation/`), `env_exposes_task_package` (переменные окружения исполнителя, содержащие путь к пакету задачи) и `harness_sandbox` (граница, объявленная харнесом, например `workspace-write` у Codex). Проверка не полагается на предположения: копия эталона в рабочей копии сразу попадает в `references_in_workspace`.

Ограничение остаётся: исполнитель работает с правами текущего пользователя, скрытость путей не является защитой, а настоящая изоляция требует контейнера или виртуальной машины. Запускайте только доверенные команды.

## Набор сценариев

`tasks/` содержит одиннадцать пакетов: демонстрационную `catalog-search` и десять `quixbugs-*` из набора [QuixBugs](tasks/PROVENANCE.md) (MIT, ревизия `4257f44`): `bitcount`, `bucketsort`, `find_first_in_sorted`, `flatten`, `gcd`, `is_valid_parenthesization`, `kheapsort`, `lcs_length`, `max_sublist_sum`, `next_palindrome`.

Проверки детерминированные: `evaluation/check.py` импортирует модуль исполнителя и прогоняет все случаи из `evaluation/testcases.json`. Сеть, модель и сторонние пакеты не нужны, поэтому набор проверяется целиком за секунды: эталон проходит, версия с дефектом отклоняется. Атрибуция, критерии отбора и правила добавления случаев — в [tasks/PROVENANCE.md](tasks/PROVENANCE.md). Дефектные версии `bitcount` и `find_first_in_sorted` зацикливаются, поэтому такая проверка завершается по общему `--timeout` и даёт исход `TIMEOUT`.

## Контрольные прогоны без модели

Харнес `gold` — не исполнитель: он применяет `evaluation/reference.md` пакета задачи к рабочей копии и служит проверкой самого стенда. Если сценарий отклоняет эталон, ошибочен сценарий или его проверка, а не модель. Харнес `noop` не делает ничего.

Бесплатная серия по всему набору:

```powershell
Get-ChildItem tasks -Directory | ForEach-Object {
  foreach ($h in 'noop','gold') { python benchmark.py --task $_.Name --approach noop --harness $h --timeout 10 }
}
```

Ожидаемый результат: `gold` даёт `PASS` во всех сценариях, `noop` — `FAIL_PRODUCT`, а зацикливающиеся дефектные версии (`bitcount`, `find_first_in_sorted`) — `TIMEOUT`. Токены не расходуются.

## Обвязка как явная часть прогона

Харнес объявляет в `harness.json` режим `install`:

| Режим | Что делает ядро |
|---|---|
| `inherit` (по умолчанию) | использует домашний каталог хоста и честно пишет в манифест `mode: inherit`, `fingerprint: null` |
| `home` | создаёт `runs/<id>/home`, пишет туда объявленные в пакете файлы и указывает `HOME`, `USERPROFILE` и перечисленные переменные на этот каталог |

Отпечаток материализованного каталога попадает в `manifest.install`, поэтому внешняя конфигурация харнеса становится частью идентичности прогона. Детерминированные харнесы (`demo`, `noop`, `gold`) работают в режиме `home`; модельные — в `inherit`, потому что их авторизация живёт в домашнем каталоге пользователя.

Перед запуском окружение вычищается: переменные из списка секретов (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `DEEPSEEK_API_KEY` и подобные) не попадают к исполнителю, если харнес явно не объявил их в `env_keep`. В `manifest.env_scrubbed` сохраняются имена удалённых переменных, без значений.

Проверка изоляции дополнена маркерами оценки: если в рабочую копию попал текст с `pass_rate`, `n_passed`, `judge.json` или похожими, это перечисляется в `result.isolation.grader_markers`.

## Манифест прогона

До запуска исполнителя ядро сохраняет `manifest.json` (и дублирует его в `result.manifest`): `run_id`, задача, подход, харнес, оценщик, `inputs` — отпечаток того, что получил исполнитель (запрос плюс файлы рабочей копии на момент старта), `approach_fingerprint`, `harness_fingerprint`, `judge_fingerprint`, параметры харнеса и версия Python. Отпечатки считает `runmark` из проекта [Harness²](https://github.com/google-research/harness2) (ревизия `6868817`, Apache-2.0), скопированный без изменений в [vendor/harness2](vendor/harness2/PROVENANCE.md). Это позволяет отличить два прогона, у которых совпали имена, но разошлось содержимое подхода или задачи.

## Серия замеров

Каждый прогон получает один терминальный исход в `result.outcome`: `PASS`, `FAIL_PRODUCT`, `FAIL_PROCESS` (пакет подхода задаёт маркер намерения, но он не появился), `TIMEOUT`, `EVAL_ERROR` или `INFRA_ERROR`. Инфраструктурные отказы и таймауты приоритетнее продуктового вердикта, поэтому прерванный прогон не может выглядеть успешным.

Сводка по серии: `python summary.py` (по умолчанию все каталоги `runs/`) или `python summary.py runs/<id> ... --json summary.json`. Отчёт содержит N_started, N_completed, N_graded, N_pass, покрытие оцениванием, медианы времени и токенов и разбивку по подходу, харнесу и задаче. Отсутствующая телеметрия не считается нулевым расходом: такие прогоны исключаются из медиан, а их число видно в `usage.runs_with_complete_usage`.

Проверка парсера без моделей: `python -m unittest discover -s tests`.

## Настройка и адаптеры харнесов

Пакет `harnesses/<имя>/harness.json` определяет команду запуска и необязательную `telemetry_command`. Каждая команда — отдельный процесс; ядро передаёт ей пути через окружение. Адаптер телеметрии получает `BENCH_AGENT_STDOUT`, выводит один JSON-объект на stdout; его ошибки сохраняются в `telemetry/` и не скрывают исходный журнал. Можно добавить новый пакет без изменения ядра.

Параметры конкретного прогона передаются через `--harness-config examples/qwen-config.json`: адаптер получает путь в `BENCH_HARNESS_CONFIG`, а копия параметров сохраняется в результате. Для Qwen Code и Codex поддерживаются `executable`, список `args` и `prompt`. Не помещайте ключи и пароли в этот JSON: файл сохраняется в артефактах; используйте механизмы авторизации самого харнеса. Исполняемые команды и признак модельного запуска задаются в доверенном пакете, а не в параметрах прогона.

Пакет `qwen-code` работает через headless-режим CLI (проверено на Qwen Code 0.27.1): промпт передаётся позиционным аргументом, вывод — `--output-format stream-json`. Режим подтверждений задаётся параметром `approval_mode` (по умолчанию `auto`; значение `none` убирает флаг из команды, если сборка не поддерживает ни `--yolo`, ни `--approval-mode`), а свой список аргументов можно передать через `args`. Авторизация выполняется вне бенчмарка — адаптер её не настраивает и ключи не принимает.

Телеметрия Qwen тоже нормализуется: адаптер читает `stats` итогового события `result` или `usage` отдельных событий и помечает отсутствующие поля как `missing`. Если в потоке есть итоговый `result` с расходом, используется он, чтобы не задвоить сумму. Проверка парсера — без модели, на подставных событиях.
