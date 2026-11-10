# SDD Benchmark — прототип

Ядро независимо выбирает пакет задачи, SDD-подход и харнес. Python 3, без сторонних Python-зависимостей.

```powershell
python benchmark.py --task catalog-search --approach demo --harness demo
python benchmark.py --task catalog-search --approach demo --harness noop
```

Первый запуск проходит тесты, второй демонстрирует ошибку. Результат, рабочая копия и логи сохраняются в `runs/<run_id>/`. Код возврата: 0 — успех, 1 — неуспех прогона, 2 — ошибка конфигурации.

Пакет задачи `tasks/<имя>/` включает `task.json`, исходный `project/`, SDD-контекст `context/`, `request.md` и независимую `evaluation/`. Проверка задаётся массивом аргументов `evaluation_command`. Пакет подхода `approaches/<имя>/` содержит `approach.json`, `instructions.md` и опциональную команду `setup_command`. Пакет харнеса `harnesses/<имя>/` содержит `harness.json` с `command` и `requires_model`. В командах поддерживаются `{python}`, `{task}`, `{approach}`, `{harness}`. Доступны переменные `BENCH_WORKSPACE`, `BENCH_TASK`, `BENCH_CONTEXT`, `BENCH_APPROACH`, `BENCH_PYTHON`.

Харнесы, для которых `requires_model` истинно или не задано, не запускаются без явного `--allow-model`. Этот флаг не ограничивает расход токенов. Демо-харнес детерминирован и не является моделью. Доступен пакет `openspec` и харнес `codex`, но их совместная работа пока не подтверждена: Windows-песочница Codex вернула ошибку доступа. Настройка OpenSpec требует Node.js, npx и доступа к npm. JSONL Codex сохраняется в `agent/stdout.bin`.

Исполнители работают с правами текущего пользователя: рабочая копия не защищает закрытые тесты от доступа или изменения. Полноценная изоляция, лимиты токенов и модель-проверяльщик ещё не реализованы. Запускайте только доверенные команды.
