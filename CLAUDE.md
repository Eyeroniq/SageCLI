# CLAUDE.md: SageCLI handoff notes

Read this first when resuming work. It records design decisions, layout, the
phase checklist, exact commands, and what was or was not verified.

## What SageCLI is

An offline Linux CLI: `sage "show the 10 largest files here"`. A local Phi-3 Mini
(4-bit GGUF, CPU, llama-cpp-python) produces ONE Bash command, a safety layer
classifies it (SAFE / WARN / BLOCK), and it runs only after confirmation.
No network, cloud APIs or telemetry at runtime.

## Environment facts

- Development happens on native Windows; the code TARGETS LINUX ONLY.
- The real model, Docker, bwrap and the latency/accuracy benchmarks cannot be
  run on the dev machine. Never claim they were.
- Never execute generated or dangerous commands on the dev machine. The executor
  refuses unless `sys.platform` starts with `linux`; `--dry-run` works everywhere.
- All files use LF (`.gitattributes`). Python 3.11+.

## File layout (current)

```
src/sagecli/
  __init__.py    version
  config.py      model path resolution, generation settings, timeout, allowlist loader
  prompts.py     Phi-3 chat prompt with system instruction + 8 few-shot examples
  engine.py      lazy model loading, generate_command(), explain(), output cleanup
  validator.py   risk classification (SAFE/WARN/BLOCK)
  executor.py    runs a confirmed command with /bin/bash -c and a timeout (Linux only)
  cli.py         Typer CLI (`sage`)
scripts/download_model.sh   resumable model download from Hugging Face
tests/           pytest suite; the LLM and subprocess are always mocked
```

## Design decisions

- **Optional model runtime.** `llama-cpp-python` is in the `llm` extra and imported
  lazily inside `engine._llama_factory`, so tests, CI, `--version` and `--help`
  never need it compiled.
- **Engine.** Loaded once per process on first use (`Engine.load`). Settings:
  temperature 0.1, top_p 0.9, max_tokens 96 (64 for explanations), n_ctx 1024,
  n_threads = `os.cpu_count()`, fixed seed 42. Stop sequences are the Phi-3 special
  tokens.
- **Prompt.** Phi-3 Mini's original template has no system role, so the short
  system instruction is placed in the first user turn, followed by 8 few-shot
  request/command pairs (all non-destructive). Format:
  `<|user|>\n...<|end|>\n<|assistant|>\n...<|end|>\n`.
- **Output cleanup.** `clean_command` cuts at special tokens, takes the inside of
  the first code fence if any, strips backticks, `Command:`/`bash:` prefixes and
  `$ ` prompt signs, and keeps the first non-empty line. A one-line pipeline or
  `a && b` is kept as-is ("one command" means one line).
- **Model path.** `--model` > `$SAGE_MODEL_PATH` > `./models/Phi-3-mini-4k-instruct-q4.gguf`.
  Missing file gives a message pointing to `scripts/download_model.sh`.
- **Confirmation policy.** BLOCK is never executed, not even with `--yes`.
  WARN needs the user to type `yes` in full (`--yes` does not skip it).
  SAFE needs y/N, skipped by `--yes`. `--allowlist FILE` blocks any binary not listed.
- **Exit codes.** 0 ok/dry-run, 1 aborted or empty generation, 2 usage error or
  missing model/runtime, 3 blocked, 4 execution refused off Linux. When a command
  runs, its own exit code is returned (124 on timeout).
- **Executor.** `/bin/bash -c CMD` in a new session (process group); on timeout the
  whole group gets SIGKILL. Default timeout 60 s (`--timeout` / `$SAGE_TIMEOUT`).
  Output streams directly to the terminal.
- **Platform guard.** `executor.ensure_linux()` raises before any subprocess is
  created; the CLI checks `is_linux()` before prompting so the user is not asked
  to confirm something that cannot run.
- **Multi-word requests.** `sage list all files` (unquoted) is joined into one request.

## Phase checklist

Phase 1: working product, baseline, Docker, CI
- [x] 1.1 Core engine and CLI
- [ ] 1.2 Safety layer, regex version (+100 parametrized tests)
- [ ] 1.3 Adversarial benchmark and regex-only baseline
- [ ] 1.4 Latency benchmark script
- [ ] 1.5 Docker and CI
- [ ] 1.6 Minimal README and this handoff file complete; CI green

Phase 2 and Phase 3: not started (their specs were not included in the build prompt
received so far).

## Commands

```bash
python -m venv .venv && . .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e ".[dev]"          # tests and lint, no model runtime
pip install -e ".[dev,llm]"      # plus llama-cpp-python (compiles; Linux)
ruff check .
pytest
bash scripts/download_model.sh   # ~2.4 GB into ./models/
sage --dry-run "show the 10 largest files in this folder"
```

## Verified here / NOT verified here

Verified here (Windows dev machine, model mocked):
- `ruff check .` and `pytest` pass (engine, CLI and executor with fakes).
- The model URL in `scripts/download_model.sh` answered an HTTP HEAD request on
  2026-10-04 (302 to the HF CDN, then 200, content-length 2,393,231,072 bytes).
  Only the HEAD was done; the file was not downloaded.

NOT verified here:
- Loading or running the real Phi-3 model; quality of generated commands.
- `scripts/download_model.sh` end to end (not run here; Linux shell script).
- Real command execution, timeout kill behaviour on Linux.
