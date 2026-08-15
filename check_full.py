#!/usr/bin/env python3
"""
ЕДИНАЯ проверка OpenAI-совместимого прокси.

ЧАСТЬ 1 — Провайдер (не перенаправляют ли на неофициальную инфраструктуру):
  Провоцирует настоящие серверные ошибки и смотрит, что сервер сам
  вернёт — заголовки, стектрейсы, формат ошибок, упоминания вендоров.

ЧАСТЬ 2 — Деградация / квантование модели (та же ли это версия,
  что заявлена, или урезанная/сжатая):
  Сложные задачи на рассуждение, двойной прогон при temperature=0
  (проверка детерминированности), скорость ответа, метрики
  thinking/reasoning токенов.

Все запросы уходят ТОЛЬКО на указанный endpoint. Ничего не
подделывается — весь вывод это то, что реально прислал сервер.

Использование:
    set PROXY_URL=https://твой-прокси.com/v1
    set PROXY_KEY=твой-ключ
    set PROXY_MODEL=deepseek-v4-pro
    python check_full.py

Опционально, для прямого сравнения с официальным доступом (на примере Deepseek):
    set OFFICIAL_URL=https://api.deepseek.com/v1
    set OFFICIAL_KEY=твой-официальный-ключ
"""

import os
import sys
import json
import time
import urllib.request
import urllib.error


VENDOR_SIGNATURES = [
    # Вендоры / инфраструктура
    "openai", "azure", "anthropic", "google", "vertex",
    "generativelanguage", "cohere", "mistral", "together",
    "groq", "vllm", "ollama", "fireworks", "deepinfra", "replicate",
    "bedrock", "amazon", "huggingface", "deepseek", "xai", "meta",
    "alibaba", "moonshot", "zhipu", "z.ai",
    # Названия моделей / линеек (актуальные на август 2026)
    "claude", "opus", "sonnet", "haiku", "fable", "mythos",
    "gemini", "gpt-5", "gpt-4", "grok", "llama", "qwen",
    "kimi", "kimi-k3", "glm-5.3", "glm-5.2",
]


# ============================================================
# Общие утилиты
# ============================================================

def raw_request(base_url, api_key, data_bytes):
    url = f"{base_url.rstrip('/')}/chat/completions"
    req = urllib.request.Request(
        url, data=data_bytes, method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, dict(resp.getheaders()), resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.getheaders()), e.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as e:
        return None, {}, f"CONNECTION ERROR: {e.reason}"
    except Exception as e:
        return None, {}, f"UNEXPECTED ERROR: {type(e).__name__}: {e}"


def call(base_url, api_key, payload):
    return raw_request(base_url, api_key, json.dumps(payload).encode())


def find_vendor_hints(text):
    text_l = text.lower()
    return sorted({v for v in VENDOR_SIGNATURES if v in text_l})


def show(title, status, headers, body, findings):
    print(f"\n--- {title} ---")
    print(f"Status: {status}")

    interesting = {k: v for k, v in headers.items()
                   if k.lower() in ("server", "via", "x-request-id", "x-served-by",
                                     "cf-ray", "x-cache", "x-powered-by",
                                     "openai-organization", "openai-processing-ms",
                                     "openai-version", "x-ratelimit-limit-requests")}
    if interesting:
        print("Заголовки-подсказки:")
        for k, v in interesting.items():
            print(f"  {k}: {v}")
            findings.update(find_vendor_hints(f"{k} {v}"))

    print("Тело ответа:")
    try:
        parsed = json.loads(body)
        pretty = json.dumps(parsed, ensure_ascii=False, indent=2)
        print(pretty[:1200])
        findings.update(find_vendor_hints(pretty))
    except json.JSONDecodeError:
        print(body[:1200])
        findings.update(find_vendor_hints(body))


# ============================================================
# ЧАСТЬ 1: Провайдер
# ============================================================

def part1_provider(base_url, api_key, model, findings):
    print("\n" + "#" * 60)
    print("# ЧАСТЬ 1: Определение реального провайдера")
    print("#" * 60)

    probes = [
        ("Несуществующая модель", {
            "model": "this-model-definitely-does-not-exist-xyz123",
            "max_tokens": 5,
            "messages": [{"role": "user", "content": "hi"}],
        }),
        ("Экстремальный max_tokens", {
            "model": model, "max_tokens": 999999999,
            "messages": [{"role": "user", "content": "hi"}],
        }),
        ("Некорректный тип параметра", {
            "model": model, "max_tokens": 5, "temperature": "not-a-number",
            "messages": [{"role": "user", "content": "hi"}],
        }),
        ("Пустой messages[]", {
            "model": model, "max_tokens": 5, "messages": [],
        }),
    ]

    for title, payload in probes:
        try:
            s, h, b = call(base_url, api_key, payload)
        except Exception as e:
            s, h, b = None, {}, f"UNEXPECTED ERROR: {type(e).__name__}: {e}"
        try:
            show(title, s, h, b, findings)
        except Exception as e:
            print(f"\n--- {title} ---\n(ошибка при выводе: {e})")

    try:
        s, h, b = raw_request(base_url, api_key, b'{"model": "x", "messages": [')
        show("Битый JSON в теле запроса", s, h, b, findings)
    except Exception as e:
        print(f"\n--- Битый JSON в теле запроса ---\n(не удалось выполнить: {e})")


# ============================================================
# ЧАСТЬ 2: Деградация / квантование модели
# ============================================================

DEGRADATION_TASKS = [
    (
        "Многошаговый код-ревью",
        "Find the bug in this Python function and explain why it fails, "
        "then provide the fix:\n\n"
        "def merge_sorted(a, b):\n"
        "    result = []\n"
        "    i = j = 0\n"
        "    while i < len(a) and j < len(b):\n"
        "        if a[i] < b[j]:\n"
        "            result.append(a[i])\n"
        "            i += 1\n"
        "        else:\n"
        "            result.append(b[j])\n"
        "            j += 1\n"
        "    return result\n\n"
        "Test case that fails: merge_sorted([1,3,5],[2,4]) -- what's wrong "
        "with the output, and why?",
    ),
    (
        "Нестандартная логика",
        "Five people (A, B, C, D, E) sit in a row. A is not at either end. "
        "B is somewhere to the left of C. D is adjacent to E. C is at one "
        "of the ends. Exactly one valid seating exists. Find it, showing "
        "your elimination process step by step.",
    ),
    (
        "Числовой ряд с подвохом",
        "What is the next number in this sequence, and what is the rule: "
        "2, 3, 5, 9, 17, 33, ? Explain the pattern precisely before giving "
        "the answer.",
    ),
]

SELF_ID_PROMPT = (
    "Answer only with a JSON object, no other text: "
    '{"model_family": "...", "developer": "...", "approx_knowledge_cutoff": "..."}'
    " Fill in what you actually are, as precisely as you can."
)


def call_chat(base_url, api_key, model, prompt, max_tokens=8000, temperature=0, max_retries=3):
    url = f"{base_url.rstrip('/')}/chat/completions"
    payload = json.dumps({
        "model": model, "max_tokens": max_tokens, "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()

    for attempt in range(max_retries + 1):
        req = urllib.request.Request(
            url, data=payload, method="POST",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        )
        start = time.time()
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                elapsed = time.time() - start
                data = json.loads(resp.read().decode())
                text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
                usage = data.get("usage", {})
                completion_tokens = usage.get("completion_tokens", len(text.split()))
                tps = completion_tokens / elapsed if elapsed > 0 else 0
                return {"text": text, "elapsed": elapsed, "tps": tps, "raw": data}
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < max_retries:
                retry_after = e.headers.get("Retry-After")
                wait = float(retry_after) if retry_after and retry_after.isdigit() else (5 * (attempt + 1))

                if wait > 60:
                    print(f"    ⚠️ Сервер прислал Retry-After = {wait:.0f}s (это {wait/3600:.1f} ч) — "
                          f"аномально большое значение. Официальные API вендоров так себя не ведут, "
                          f"это похоже на самодельный/некачественный reverse-прокси, а не официальную "
                          f"инфраструктуру вендора.")
                    try:
                        choice = input("    Пропустить эту пробу и продолжить дальше? (Y/N): ").strip().lower()
                    except EOFError:
                        choice = "y"
                    if choice in ("y", "yes", "да", "д", ""):
                        return {"error": f"Пропущено пользователем (аномальный Retry-After={wait:.0f}s)"}
                    print(f"    Хорошо, жду {wait:.0f}s...")
                    time.sleep(wait)
                    continue

                print(f"    (429 Too Many Requests — жду {wait:.0f}s и пробую снова, попытка {attempt + 1}/{max_retries})")
                time.sleep(wait)
                continue
            return {"error": f"HTTPError: HTTP Error {e.code}: {e.reason}"}
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}

    return {"error": "Превышено число повторных попыток после 429"}


def part2_degradation(base_url, api_key, model, findings, label="Прокси"):
    print("\n" + "#" * 60)
    print(f"# ЧАСТЬ 2: Проверка деградации/квантования модели ({label})")
    print("#" * 60)

    print("\n--- Самоидентификация ---")
    r = call_chat(base_url, api_key, model, SELF_ID_PROMPT, max_tokens=150)
    if "error" in r:
        print(f"  ❌ {r['error']}")
    else:
        print(f"  Ответ: {r['text'][:400]}")
        returned_model = r["raw"].get("model")
        if returned_model:
            print(f"  Поле 'model' в ответе сервера: {returned_model}")
            findings.update(find_vendor_hints(returned_model))
            if returned_model != model:
                print(f"  ⚠️ Запрошена '{model}', сервер вернул '{returned_model}'.")

    for title, prompt in DEGRADATION_TASKS:
        print(f"\n--- {title} ---")
        time.sleep(2)  # небольшая пауза, чтобы не провоцировать rate limit
        r1 = call_chat(base_url, api_key, model, prompt)
        if "error" in r1:
            print(f"  ❌ Прогон 1: {r1['error']}")
            continue
        print(f"  Прогон 1 ({r1['elapsed']:.1f}s, {r1['tps']:.1f} ток/с):")
        print(f"    {r1['text'][:350]}")

        tt = r1["raw"].get("usageMetadata", {}).get("thoughtsTokenCount")
        rt = (r1["raw"].get("usage", {}) or {}).get("completion_tokens_details", {}).get("reasoning_tokens")
        if tt is not None:
            print(f"    thoughtsTokenCount: {tt}")
        if rt is not None:
            print(f"    reasoning_tokens: {rt}")

        time.sleep(2)
        r2 = call_chat(base_url, api_key, model, prompt)
        if "error" in r2:
            print(f"  ❌ Прогон 2: {r2['error']}")
            continue
        print(f"  Прогон 2 ({r2['elapsed']:.1f}s, {r2['tps']:.1f} ток/с):")
        print(f"    {r2['text'][:350]}")

        same = r1["text"].strip() == r2["text"].strip()
        if same:
            print("  ✅ Прогоны идентичны при temperature=0")
        else:
            print("  ⚠️ РАЗЛИЧАЮТСЯ при temperature=0 — либо прокси игнорирует "
                  "параметр, либо нестабильный serving (возможно квантование "
                  "или балансировка между разными инстансами)")


# ============================================================
# main
# ============================================================

def main():
    proxy_url = os.environ.get("PROXY_URL")
    proxy_key = os.environ.get("PROXY_KEY")
    model = os.environ.get("PROXY_MODEL", "gpt-4o")

    if len(sys.argv) >= 3:
        proxy_url, proxy_key = sys.argv[1], sys.argv[2]
        model = sys.argv[3] if len(sys.argv) > 3 else model

    if not proxy_url or not proxy_key:
        print(__doc__)
        sys.exit(1)

    print(f"Проверяю прокси: {proxy_url}")
    print(f"Заявленная модель: {model}")

    findings = set()

    try:
        part1_provider(proxy_url, proxy_key, model, findings)
    except Exception as e:
        print(f"\n(Часть 1 прервана: {type(e).__name__}: {e})")

    try:
        part2_degradation(proxy_url, proxy_key, model, findings, label="Прокси")
    except Exception as e:
        print(f"\n(Часть 2 прервана: {type(e).__name__}: {e})")

    official_url = os.environ.get("OFFICIAL_URL")
    official_key = os.environ.get("OFFICIAL_KEY")
    if official_url and official_key:
        try:
            part2_degradation(official_url, official_key, model, findings, label="Официальный доступ")
        except Exception as e:
            print(f"\n(Сравнение с официальным доступом прервано: {e})")

    print("\n" + "#" * 60)
    print("# ИТОГ")
    print("#" * 60)
    if findings:
        print(f"Упоминания вендоров/моделей, найденные в сырых ответах: {sorted(findings)}")
    else:
        print("Явных упоминаний вендора не найдено — прокси хорошо "
              "'отмывает' ошибки, смотри содержательные пробы Части 2 вручную.")
    print(
        "\nНапоминание:\n"
        "  - Часть 1 отвечает на вопрос 'куда реально уходит запрос'.\n"
        "  - Часть 2 отвечает на вопрос 'насколько полноценна модель на "
        "другом конце' — разошедшиеся при temperature=0 прогоны, низкий\n"
        "    thinking/reasoning-бюджет на сложных задачах и подозрительно\n"
        "    высокая скорость — сигналы возможного урезания/квантования.\n"
    )


if __name__ == "__main__":
    main()
