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
- **Mode override (from step 1.3, per `SAGECLI_PROMPT.md`): write and push only.** Do not
  run pytest, ruff, pip, project scripts or benchmarks on the dev machine. The only
  exception the maintainer asked for is `scripts/build_adversarial_set.py`, which just
  writes `eval/adversarial.jsonl`. Every "run/measure" step becomes code plus the exact
  command in `LINUX_TESTING.md`. CI on GitHub may be checked with `gh run list` /
  `gh run view --log-failed` (max 3 fix attempts per phase).
- Do not put benchmark, accuracy or detection numbers in README or docs; point to the
  scripts. Never create, modify or regenerate the committed baselines
  (`benchmarks/validator_baseline.json`, `benchmarks/validator_baseline_v2.json`, and
  their `.md` files) or `validator_after*.json`; the maintainer generates them on Linux.
- Never edit `eval/adversarial.jsonl` or `eval/adversarial_v2.jsonl` to improve results.
- Write every file with LF endings. A lone-CR `validator_thresholds.toml` (commit
  `e94a3e5`, an edit made on Linux) broke `tomllib` and failed CI on `f1797be`;
  fixed in `251743b`.

## File layout (current)

```
src/sagecli/
  __init__.py    version
  config.py      model path resolution, generation settings, timeout, allowlist loader
  prompts.py     Phi-3 chat prompt with system instruction + 8 few-shot examples
  engine.py      lazy model loading, generate_command(), explain(), output cleanup
  validator.py   normalisation, quote-aware splitting, named regex rules (SAFE/WARN/BLOCK)
  executor.py    runs a confirmed command with /bin/bash -c and a timeout (Linux only)
  cli.py         Typer CLI (`sage`)
scripts/download_model.sh          resumable model download from Hugging Face
scripts/build_adversarial_set.py   maintainer-supplied generator for eval/adversarial.jsonl
scripts/validator_benchmark.py     detection / false-positive report over the data set
scripts/benchmark.py               latency benchmark with the real model (20 fixed requests)
eval/adversarial.jsonl             v1: 256 rows, 216 attacks, 40 benign look-alikes (generated)
scripts/build_adversarial_set_v2.py  maintainer-supplied generator for the v2 set
eval/adversarial_v2.jsonl          v2: 109 rows, 68 attacks, 41 benign; obfuscates arguments
                                   and targets too (written after seeing v1 results, before
                                   any validator change)
benchmarks/validator_baseline{,_v2}.{json,md}  regex-only baselines (maintainer, Linux)
benchmarks/validator_thresholds.toml  CI thresholds for the validator benchmark
tests/           pytest suite; the LLM and subprocess are always mocked
LINUX_TESTING.md   commands the maintainer runs on Linux to verify everything
Dockerfile, .dockerignore          multi-stage image, model mounted at /models
.github/workflows/ci.yml           lint, tests, validator benchmark, Docker build
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

### Validator (regex version, step 1.2)

- `validate(command, allowlist=None) -> ValidationResult(risk, rules, reason, segments, matches)`.
  Highest risk wins; `reason` joins the reasons of the top-risk rules.
- **Normalisation before matching:** join `\`-newline continuations; `$IFS`/`${IFS}`
  become spaces; simple `NAME=value` assignments anywhere in the command are
  collected and `$NAME`/`${NAME}` expanded (so `a=r;b=m;$a$b` becomes `rm`);
  `$(echo word)`/backtick echo is inlined; brace lists at command position
  (`{rm,-rf,/}`) are expanded; `shlex` dequotes each segment (`r""m`, `r''m`,
  `\rm`, `r\m` become `rm`); the command is reduced to its basename (`/bin/rm`).
- **Splitting:** a quote-aware scanner splits on `;`, `&&`, `||`, `|`, `&`, newline
  and lifts `$(...)`, backticks, `<(...)`, `>(...)` bodies out as separate commands
  (placeholders `$__SUBn__` / `/dev/fd/__SUBn__`). Every segment is validated.
- **Prefix stripping:** keywords (`if`, `then`, `do`, `(`, `{`, `!`), assignments
  and wrappers (`sudo`, `env`, `command`, `exec`, `nohup`, `nice`, `timeout`,
  `xargs`, `busybox`, `watch`, ...) are removed, with their options. `sudo`/`doas`/
  `pkexec` still add a WARN `privilege_escalation` match.
- **Masking to avoid false positives:** in the text the rules see, quoted strings
  containing spaces become `'…'`, so `echo "rm -rf /" > notes.txt` and
  `grep -r "dd if=" .` stay SAFE. Rules are anchored at the command position.
- **Re-validation where the shell executes a string:** `bash/sh -c STR`, `su -c`,
  `eval ARGS`, here-strings to a shell (`sh <<< STR`), `find -exec ...`, `trap`,
  `alias x='...'`, strings echoed/printf'd into a shell, a whole command passed as
  one string (`watch "..."`), and quoted strings inside interpreter one-liners
  that call `system`/`subprocess`/`exec`.
- **Pipeline rules:** something piped into a shell or interpreter reading stdin is
  BLOCK if any upstream stage is a downloader (`remote_pipe_shell`) or a decoder
  (`base64 -d`, `xxd -r`, `printf '\x..'`, `rev`, `openssl -d`, ...;
  `obfuscated_pipe_shell`), else WARN `pipe_to_shell`. A substitution used as a
  command name or as code (`bash -c "$(curl ..)"`, `$(printf '\x72\x6d') -rf /`,
  `bash <(curl ..)`) whose body downloads or decodes is BLOCK.
- **Rule categories:** recursive_delete, disk_destruction, fork_bomb, permissions,
  remote_exec, critical_file, power, privilege, process_kill, history_wipe,
  obfuscation, interpreter, allowlist. Names are listed in `validator.ALL_RULE_NAMES`.
- **Risk choices:** `rm -r` on an ordinary path is WARN; on `/`, `/*`, `~`, `$HOME`,
  `*`, `.`, `..` or a top-level system dir it is BLOCK. `find -delete` is WARN, BLOCK
  when started at `/`, `~` or a system dir. `sudo`/`su`, `eval`, `killall`,
  `pkill -9`, plain `shred FILE`, partition tools and `chmod` on `/` are WARN.
  `kill 1`/`kill -9 -1`, shutdown/reboot, `mkfs`, `dd of=/dev/..`, writes to
  critical files, history/log wiping, fork bombs and remote/decoded code into a
  shell are BLOCK.
- **Allowlist mode:** every command name seen, including wrappers (`sudo`, `xargs`)
  and dynamic names (`$__SUB0__`), must be listed, else BLOCK `not_in_allowlist`.
- **Executor double-check:** `executor.run_command` re-validates and raises
  `BlockedCommandError` on BLOCK, even if a caller skipped the CLI policy.
- Known regex-version limits (expected; see the baseline in step 1.3): parameter
  expansion slicing (`${PATH:0:1}`), ANSI-C quoting (`$'\x72m'`), globbed target
  paths (`/h?me`), variables assigned from command output, and anything needing a
  real parse tree.

### Adversarial benchmark (step 1.3)

- **Data set** `eval/adversarial.jsonl` is produced by `scripts/build_adversarial_set.py`
  (supplied by the maintainer; do not hand-write attack strings). Rows: `id`, `command`,
  `technique`, `should_block`. Attacks = 9 destructive base commands x 23 obfuscation
  transforms + 9 extra shapes; benign rows have technique `benign`.
- **Counting (from Phase 2 prep):** four numbers per data set: attacks flagged (WARN
  or BLOCK), **attacks blocked**, benign flagged, **benign blocked**. The two BLOCKED
  numbers are the headline metrics and the only ones CI gates on: WARN-level
  `rm_recursive` flags almost any `rm -r`, so "flagged" overstates protection.
  (The committed baselines use the older key names `detected`/`false_positives`;
  `results` has every row's verdict, so tools recompute from that.)
- **`scripts/validator_benchmark.py`** `--layers {regex,structural,both}` (only `regex`
  works; the others exit 2 with "not implemented until Phase 2"), `--out PATH` (JSON;
  a `.md` report is written next to it), `--data PATH` (alias `--dataset`; default
  `eval/adversarial.jsonl`), `--thresholds`, `--check`.
  Default output `benchmarks/validator_results.{json,md}` (gitignored). Reports
  overall and per-technique detection and block rates, false positives, and misses.
- **Thresholds** live in `benchmarks/validator_thresholds.toml`, one `[datasets.NAME]`
  table per data set (`data`, `min_attack_block_rate`, `max_benign_blocked`); `--check`
  picks the table whose `data` path matches `--data` (exit 2 if none, 1 if not met).
  Current values are no-regression floors from the regex baselines (v1 0.98 / 0;
  v2 0.88 / 1); raise them to the measured values after the Phase 2 Linux run.
  CI runs `--check` for both data sets.
- **Line endings:** `tests/test_line_endings.py` reads every blob in the git index
  (`git cat-file --batch`) and fails on any carriage return (lone CR or CRLF).
- **Baselines (committed by the maintainer on Linux, regex-only validator):**
  `benchmarks/validator_baseline.json` (v1, `--layers regex`) and
  `benchmarks/validator_baseline_v2.json` (v2, `--data eval/adversarial_v2.jsonl`).
  Tag `phase1-regex-baseline` points at `f112423`; `src/sagecli/validator.py` is
  identical there and at both baseline commits. Note: the v1 baseline files were
  actually added in `e94a3e5`, whose message wrongly says "v2 dataset"; history is
  not rewritten. Read `benchmarks/validator_baseline_v2.md` for current misses and
  false positives. Thresholds: `min_detection_rate = 0.95`, `max_false_positives = 1`
  (superseded: see the per-data-set thresholds above).

### Latency benchmark (step 1.4)

- `scripts/benchmark.py` builds an `Engine` (`--model`, `--threads` via
  `dataclasses.replace` on `GenerationSettings`), times `engine.load()` as the cold
  start, then calls `engine.complete()` on 20 fixed, non-destructive requests so it
  gets token counts and per-call seconds. Reports cold start, first request,
  mean/median/p95 (nearest-rank), tokens/sec (total tokens / total generation time),
  CPU model (`/proc/cpuinfo`), logical cores and threads. Writes
  `benchmarks/results.md` + `.json` (gitignored). Commands are never executed.
- Missing model or runtime: prints the engine's friendly message, exit 2.
- Tested with `FakeLlama`; real numbers only come from running it on Linux.

### Docker and CI (step 1.5)

- **Dockerfile:** builder stage (`python:3.11-slim` + build-essential, cmake) installs
  `.[llm]` into `/opt/venv` with `CMAKE_ARGS=-DGGML_NATIVE=OFF` so the image is not
  tied to the build machine's CPU. Runtime stage copies only the venv, adds `libgomp1`
  (OpenMP runtime for llama.cpp), sets `SAGE_MODEL_PATH=/models/Phi-3-mini-4k-instruct-q4.gguf`,
  runs as user `sage` (uid 10001) in `/work`, `VOLUME /models`, `ENTRYPOINT ["sage"]`,
  `CMD ["--help"]`. `.dockerignore` excludes `models/`, `*.gguf`, `.git`, venvs, tests.
- **CI** (`ubuntu-latest`, push and PR to main): Python 3.11, `pip install -e ".[dev]"`,
  `ruff check .`, `pytest`, then the validator benchmark: `--check` only if
  `benchmarks/validator_baseline.json` exists, otherwise a plain run (results uploaded
  as an artifact). A second job builds the image and runs `sagecli:ci --version`;
  no model is downloaded.

## Phase checklist

Phase 1: working product, baseline, Docker, CI
- [x] 1.1 Core engine and CLI
- [x] 1.2 Safety layer, regex version (181 parametrized validator tests)
- [x] 1.3 Adversarial data set and benchmark script (baseline JSON: maintainer, on Linux)
- [x] 1.4 Latency benchmark script (numbers: run on Linux)
- [x] 1.5 Docker and CI
- [x] 1.6 Minimal README (no numbers; points to the scripts) and this handoff file
- [x] Phase 1 acceptance: the maintainer ran ruff and pytest on Linux (pass), committed
  both regex baselines and tuned the thresholds; CI green on `6b9c956`. Check CI with
  the public API if `gh` is missing:
  `curl -s https://api.github.com/repos/Eyeroniq/SageCLI/actions/runs?per_page=3`.

Phase 2 (spec: `../SAGECLI_PROMPT.md`, kept outside the repo):
- [x] Prep: four-number benchmark report, BLOCK-rate gates for v1 and v2 in CI,
  `tests/test_line_endings.py` (commit `d155c45`, CI green).
- [ ] 2.1 bashlex structural layer (next step; nothing written yet)
- [ ] 2.2 compare_validator_runs.py, before/after for both data sets
- [ ] 2.3 sandbox preview
- [ ] 2.4 accuracy eval harness
- [ ] 2.5 CI and handoff updates

Phase 2 rules from the maintainer: fix classes of problems with general mechanisms
(path canonicalisation, arguments reaching a command through xargs or a pipe,
interpreter one-liners handled structurally), never special-case dataset strings;
mkfs/dd and similar are BLOCK only when the target is a block device under /dev/;
never edit the dataset files; record every validator change and why in this file.
Phase 3 (full docs) is not started.

Tooling note: the GitHub CLI (`gh`) is not installed on the dev machine; CI status is
read from the public GitHub REST API instead (read-only).

## Commands

```bash
python -m venv .venv && . .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e ".[dev]"          # tests and lint, no model runtime
pip install -e ".[dev,llm]"      # plus llama-cpp-python (compiles; Linux)
ruff check .
pytest
bash scripts/download_model.sh   # ~2.4 GB into ./models/
python scripts/build_adversarial_set.py          # regenerates eval/adversarial.jsonl
python scripts/validator_benchmark.py --check    # regex layer, thresholds enforced
python scripts/benchmark.py                      # latency, needs the model (Linux)
docker build -t sagecli .
docker run --rm -it -v "$PWD/models:/models:ro" -v "$PWD:/work" sagecli --dry-run "list files"
sage --dry-run "show the 10 largest files in this folder"
```

## Verified here / NOT verified here

Verified by the maintainer on Linux (2026-10-08): `pytest`, `ruff check`, and
`scripts/validator_benchmark.py` for both baselines.

Verified here: nothing was executed locally from step 1.3 on (mode override), except
`scripts/build_adversarial_set.py`, which only wrote `eval/adversarial.jsonl`.
Everything else is NOT verified here; run on Linux to verify (`LINUX_TESTING.md`).

History (earlier sessions, before the override; not re-checked since):
- Steps 1.1 and 1.2 recorded `ruff check .` and `pytest` passing on Windows with fakes.
- The model URL in `scripts/download_model.sh` answered an HTTP HEAD request on
  2026-10-04 (302 to the HF CDN, then 200, content-length 2,393,231,072 bytes).
  Only the HEAD was done; the file was not downloaded.

NOT verified here:
- `scripts/benchmark.py` with the real model; no latency numbers exist yet.
- Loading or running the real Phi-3 model; quality of generated commands.
- `scripts/download_model.sh` end to end (not run here; Linux shell script).
- Real command execution, timeout kill behaviour on Linux.
- Docker image build and run (only checked remotely by CI, if CI ran).
