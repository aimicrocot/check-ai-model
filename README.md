# Testing an OpenAI-compatible proxy, provider, and quantization

A diagnostic script for OpenAI-compatible API proxies. It answers two questions:

1. **Where does the request actually go?** (Part 1 — Provider Detection)
2. **Is the model on the other end the real, full-quality version, or a degraded/quantized one?** (Part 2 — Degradation Check)

No responses are faked or guessed — everything printed is exactly what the target endpoint returned.

## Why

Many "AI proxy" resellers advertise access to a specific model (e.g. a particular Claude, GPT, or Gemini version) while actually routing requests through unofficial infrastructure, cheaper backend models, or quantized/throttled variants. This script provokes real server errors and edge cases to surface identifying information the proxy operator didn't intend to leak (stack traces, vendor-specific error formats, response headers), and separately probes whether the model's actual behavior (determinism, reasoning depth, latency) matches what a full, official model should produce.

## How it works

### Part 1 — Provider fingerprinting

Sends a series of malformed/edge-case requests designed to trigger raw backend errors rather than a clean handled response:

- A nonexistent model name
- An absurdly large `max_tokens`
- A wrong parameter type (e.g. `temperature` as a string)
- An empty `messages[]` array
- Deliberately broken JSON in the request body

The script inspects the resulting status codes, response headers (`Server`, `Via`, `X-Powered-By`, `X-Request-Id`, etc.), and response bodies for stack traces, vendor-specific error schemas, and documentation links, then scans all of it for known vendor/model name signatures (OpenAI, Google/Vertex, Anthropic, AWS Bedrock, DeepSeek, and many others — see `VENDOR_SIGNATURES` in the script).

### Part 2 — Model degradation / quantization check

- **Self-identification**: asks the model to describe itself as JSON, and compares the `model` field in the raw API response against the model name you requested.
- **Reasoning tasks**: three prompts (a code-review bug hunt, a constraint-satisfaction logic puzzle, and a pattern-completion sequence) are each run **twice** at `temperature=0`.
  - If the two runs differ, that's a signal the proxy is either ignoring the `temperature` parameter or routing you to different backend instances/quantization levels.
  - Response speed (tokens/sec) and thinking/reasoning token counts (`thoughtsTokenCount` / `reasoning_tokens`, when the backend exposes them) are also logged as secondary signals of a cut-down model.
- If a `429` response includes an abnormally large `Retry-After` (the script flags anything over 60s), it warns that this doesn't match how official vendor APIs behave and asks whether to skip that probe.

Optionally, if you provide `OFFICIAL URL` / `OFFICIAL KEY`, Part 2 is run a second time against the official API for direct comparison.

### Summary

At the end, the script prints every vendor/model keyword found anywhere in the raw responses across both parts — this is your best evidence of what's actually running behind the proxy.

## Usage

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
run check_full_for_python.py
```

### Optional: compare against the official API (CMD)

```bash
export OFFICIAL_URL=https://api.deepseek.com/v1
export OFFICIAL_KEY=your-official-key
python check_full.py
```

When set, Part 2 runs against both the proxy and the official endpoint, so you can compare determinism, speed, and reasoning depth side by side.

## Reading the output

- **Part 1** tells you *where the request really goes* — look for vendor names, internal file paths, or documentation URLs leaking through error messages.
- **Part 2** tells you *how intact the model is* — divergent outputs at `temperature=0`, a low/missing reasoning-token budget on hard tasks, or suspiciously high tokens/sec are all signs of possible truncation, quantization, or a cheaper substitute model.
- No vendor keywords found doesn't mean the proxy is legitimate — it may just mean the proxy sanitizes its errors well. In that case, rely on the Part 2 signals instead.

## Requirements

- Python 3, standard library only (`urllib`, `json`, `os`, `sys`, `time`) — no external dependencies.

## Notes

- All requests are sent only to the endpoint(s) you configure.
- The empty-`messages[]` and malformed-JSON probes are expected to fail — that's the point; the *shape* of the failure is the signal.
- Some proxies rate-limit aggressively; the script has built-in retry/backoff logic for `429` responses, with a manual override if `Retry-After` looks abnormal.
