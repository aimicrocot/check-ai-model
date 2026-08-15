## English Guide

<details>

### Testing an OpenAI-compatible proxy, provider, and quantization

A diagnostic script for OpenAI-compatible API proxies. It answers two questions:

1. **Where does the request actually go?** (Part 1 — Provider Detection)
2. **Is the model on the other end the real, full-quality version, or a degraded/quantized one?** (Part 2 — Degradation Check)

No responses are faked or guessed — everything printed is exactly what the target endpoint returned.

### Why

Many "AI proxy" resellers advertise access to a specific model (e.g. a particular Claude, GPT, or Gemini version) while actually routing requests through unofficial infrastructure, cheaper backend models, or quantized/throttled variants. This script provokes real server errors and edge cases to surface identifying information the proxy operator didn't intend to leak (stack traces, vendor-specific error formats, response headers), and separately probes whether the model's actual behavior (determinism, reasoning depth, latency) matches what a full, official model should produce.

### How it works

#### Part 1 — Provider fingerprinting

Sends a series of malformed/edge-case requests designed to trigger raw backend errors rather than a clean handled response:

- A nonexistent model name
- An absurdly large `max_tokens`
- A wrong parameter type (e.g. `temperature` as a string)
- An empty `messages[]` array
- Deliberately broken JSON in the request body

The script inspects the resulting status codes, response headers (`Server`, `Via`, `X-Powered-By`, `X-Request-Id`, etc.), and response bodies for stack traces, vendor-specific error schemas, and documentation links, then scans all of it for known vendor/model name signatures (OpenAI, Google/Vertex, Anthropic, AWS Bedrock, DeepSeek, and many others — see `VENDOR_SIGNATURES` in the script).

#### Part 2 — Model degradation / quantization check

- **Self-identification**: asks the model to describe itself as JSON, and compares the `model` field in the raw API response against the model name you requested.
- **Reasoning tasks**: three prompts (a code-review bug hunt, a constraint-satisfaction logic puzzle, and a pattern-completion sequence) are each run **twice** at `temperature=0`.
  - If the two runs differ, that's a signal the proxy is either ignoring the `temperature` parameter or routing you to different backend instances/quantization levels.
  - Response speed (tokens/sec) and thinking/reasoning token counts (`thoughtsTokenCount` / `reasoning_tokens`, when the backend exposes them) are also logged as secondary signals of a cut-down model.
- If a `429` response includes an abnormally large `Retry-After` (the script flags anything over 60s), it warns that this doesn't match how official vendor APIs behave and asks whether to skip that probe.

Optionally, if you provide `OFFICIAL URL` / `OFFICIAL KEY`, Part 2 is run a second time against the official API for direct comparison.

#### Summary

At the end, the script prints every vendor/model keyword found anywhere in the raw responses across both parts — this is your best evidence of what's actually running behind the proxy.

### Usage

Use CMD:

1. Download `check_full.py`
2. Open your `CMD`
3. Navigate to the file folder
4. Pass the arguments directly

```bash
python check_full.py https://your-proxy.com/v1 your-proxy-key deepseek-v4-pro
```

Or put `check_full.py` and `run_check.bat` to the same folder: 

```bash
run run_check.bat
```

Or make sure `Python 3` is installed and added to your `PATH`:

```bash
run check_full.py 
```

##### Optional: compare against the official API (CMD)

```bash
export OFFICIAL_URL=https://api.deepseek.com/v1
export OFFICIAL_KEY=your-official-key
python check_full.py
```

When set, Part 2 runs against both the proxy and the official endpoint, so you can compare determinism, speed, and reasoning depth side by side.

### Reading the output

- **Part 1** tells you *where the request really goes* — look for vendor names, internal file paths, or documentation URLs leaking through error messages.
- **Part 2** tells you *how intact the model is* — divergent outputs at `temperature=0`, a low/missing reasoning-token budget on hard tasks, or suspiciously high tokens/sec are all signs of possible truncation, quantization, or a cheaper substitute model.
- No vendor keywords found doesn't mean the proxy is legitimate — it may just mean the proxy sanitizes its errors well. In that case, rely on the Part 2 signals instead.

### Requirements

- Python 3, standard library only (`urllib`, `json`, `os`, `sys`, `time`) — no external dependencies.

### Notes

- All requests are sent only to the endpoint(s) you configure.
- The empty-`messages[]` and malformed-JSON probes are expected to fail — that's the point; the *shape* of the failure is the signal.
- Some proxies rate-limit aggressively; the script has built-in retry/backoff logic for `429` responses, with a manual override if `Retry-After` looks abnormal.

</details>

### Тестирование OpenAI-совместимого прокси, провайдера и квантования

Диагностический скрипт для OpenAI-совместимых API-прокси. Он отвечает на два вопроса:

1. **Куда на самом деле уходит запрос?** (Часть 1 — Определение провайдера)
2. **Является ли модель на том конце оригинальной полноценной версией или урезанной/квантованной?** (Часть 2 — Проверка на деградацию)

Никакие ответы не подделываются и не угадываются — всё, что выводится на экран, в точности соответствует ответу целевого эндпоинта.

### Зачем это нужно

Многие реселлеры «AI-прокси» заявляют о предоставлении доступа к конкретной модели (например, к определённым версиям Claude, GPT или Gemini), но на самом деле перенаправляют запросы через неофициальную инфраструктуру, более дешёвые модели или квантованные/ограниченные варианты. Этот скрипт провоцирует реальные ошибки сервера и граничные случаи, чтобы извлечь идентификационную информацию, которую оператор прокси не планировал раскрывать (стек-трейсы, специфичные для вендоров форматы ошибок, заголовки ответов). Отдельно он проверяет, соответствует ли реальное поведение модели (детерминированность, глубина рассуждений, задержка) тому, что должна выдавать полноценная официальная модель.

### Как это работает

#### Часть 1 — Определение вендора (fingerprinting)

Отправляет серию некорректных или крайних запросов, предназначенных для вызова необработанных ошибок бэкенда, а не чистого обработанного ответа:

* Несуществующее имя модели
* Абсурдно большое значение `max_tokens`
* Неверный тип параметра (например, `temperature` в виде строки)
* Пустой массив `messages[]`
* Намеренно повреждённый JSON в теле запроса

Скрипт анализирует полученные коды ответов, заголовки (`Server`, `Via`, `X-Powered-By`, `X-Request-Id` и т. д.) и тела ответов на наличие стек-трейсов, схем ошибок конкретных вендоров и ссылок на документацию, а затем сканирует всё это на предмет сигнатур известных вендоров и моделей (OpenAI, Google/Vertex, Anthropic, AWS Bedrock, DeepSeek и многих других — см. `VENDOR_SIGNATURES` в скрипте).

#### Часть 2 — Проверка на деградацию / квантование модели

* **Самоидентификация**: просит модель описать себя в формате JSON и сравнивает поле `model` в сыром ответе API с запрошенным именем модели.
* **Задачи на рассуждение**: три промпта (поиск багов при ревью кода, логическая puzzle-задача с ограничениями и продолжение последовательности) запускаются **дважды** с параметром `temperature=0`.
* Если результаты двух запусков различаются, это признак того, что прокси либо игнорирует параметр `temperature`, либо перенаправляет запросы на разные бэкенд-инстансы или уровни квантования.
* Скорость ответа (токенов/сек) и количество токенов рассуждений/размышлений (`thoughtsTokenCount` / `reasoning_tokens`, если бэкенд их возвращает) также логируются как косвенные признаки урезанной модели.


* Если ответ с кодом `429` содержит аномально большой заголовок `Retry-After` (скрипт отмечает всё, что больше 60 секунд), система предупреждает, что это не соответствует behavior официальных API вендоров, и спрашивает, стоит ли пропустить эту проверку.

Опционально, если указать `OFFICIAL URL` / `OFFICIAL KEY`, Часть 2 будет выполнена повторно через официальный API для прямого сравнения.

#### Итог

В конце скрипт выводит все ключевые слова вендоров/моделей, найденные в сырых ответах в обеих частях — это главное доказательство того, что на самом деле работает за прокси.

### Использование

Использование через CMD:

1. Скачайте `check_full.py`
2. Откройте командную строку `CMD`
3. Перейдите в папку с файлом
4. Передайте аргументы напрямую

```bash
python check_full.py https://your-proxy.com/v1 your-proxy-key deepseek-v4-pro

```

Или поместите `check_full.py` и `run_check.bat` в одну папку:

```bash
run run_check.bat

```

Или убедитесь, что `Python 3` установлен и добавлен в `PATH`:

```bash
run check_full.py 

```

### Опционально: сравнение с официальным API (CMD)

```bash
export OFFICIAL_URL=https://api.deepseek.com/v1
export OFFICIAL_KEY=your-official-key
python check_full.py

```

При установке этих переменных Часть 2 выполняется как для прокси, так и для официального эндпоинта, позволяя напрямую сравнить детерминированность, скорость и глубину рассуждений.

#### Расшифровка результатов

* **Часть 1** показывает, *куда на самом деле уходит запрос* — ищите названия вендоров, внутренние пути к файлам или URL-адреса документации, утекающие через сообщения об ошибках.
* **Часть 2** показывает, *насколько модель сохранила свое качество* — разница в ответах при `temperature=0`, низкий или отсутствующий лимит токенов рассуждений на сложных задачах или подозрительно высокая скорость (токенов/сек) — все это признаки возможной урезки, квантования или подмены на более дешевую модель.
* Отсутствие ключевых слов вендоров не означает, что прокси легален — это может лишь указывать на качественную очистку ошибок. В таком случае опирайтесь на сигналы из Части 2.

### Требования

* Python 3, только стандартная библиотека (`urllib`, `json`, `os`, `sys`, `time`) — никаких внешних зависимостей.

### Примечания

* Все запросы отправляются только на настроенные вами эндпоинты.
* Проверки с пустым `messages[]` и некорректным JSON гарантированно приведут к ошибке — в этом и смысл: сама *структура* ошибки служит сигналом.
* Некоторые прокси агрессивно ограничивают количество запросов (rate limit); в скрипт встроена логика повторных попыток с экспоненциальной задержкой для ответов `429` с возможностью ручного пропуска, если значение `Retry-After` выглядит аномально большим.

