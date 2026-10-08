# How SageCLI works

This document explains the whole project from the ground up: the idea, the
background concepts, every file, the safety layer in depth, the evaluation, the
tests, Docker and CI, and an interview cheat sheet. It assumes you know basic
Python but have never seen this project, llama.cpp, or Docker.

## Table of contents

1. [The big picture](#1-the-big-picture)
2. [Background concepts from scratch](#2-background-concepts-from-scratch)
3. [File-by-file walkthrough](#3-file-by-file-walkthrough)
4. [The safety layer in depth](#4-the-safety-layer-in-depth)
5. [Evaluation](#5-evaluation)
6. [The test suite](#6-the-test-suite)
7. [Docker and CI/CD](#7-docker-and-cicd)
8. [Configuration reference](#8-configuration-reference)
9. [Extending the project](#9-extending-the-project)
10. [Design decisions and trade-offs](#10-design-decisions-and-trade-offs)
11. [Interview cheat sheet](#11-interview-cheat-sheet)

## 1. The big picture

**The problem.** The shell is powerful but unforgiving: one wrong flag or path can
delete your data. Remembering exact syntax is hard, and a mistyped `rm -rf` has no
undo. SageCLI lets you say what you want in English, shows you the exact command it
would run, tells you how risky that command is, and only runs it after you confirm.

**Why offline matters.** The model runs on your own CPU with no network. Your
requests, file names and directory contents never leave the machine, and the tool
works on an air-gapped server. There is no API key and no per-request cost.

**The journey of one request.**

```text
English request
   -> engine: build a Phi-3 chat prompt (few-shot) -> run the model -> clean to ONE command
   -> validator: regex layer + bashlex structural layer -> SAFE / WARN / BLOCK (+ reason)
   -> (optional) sandbox: run in bwrap/Docker on a COPY -> stdout, exit code, file diff
   -> confirmation prompt
   -> executor: /bin/bash -c "<command>" with a timeout (Linux only)
```

**A fully traced example.** Suppose you run
`sage "delete all .tmp files in this folder"`.

1. **User input:** `delete all .tmp files in this folder`.
2. **Prompt sent to the model** (built by `prompts.build_command_prompt`): a system
   instruction followed by eight `Request:`/command few-shot pairs in Phi-3 chat
   format, then your request and an empty assistant turn:

   ```text
   <|user|>
   You convert a request into exactly ONE Bash command for Linux. ...
   Request: list all files including hidden ones<|end|>
   <|assistant|>
   ls -la<|end|>
   ... (seven more examples) ...
   <|user|>
   Request: delete all .tmp files in this folder<|end|>
   <|assistant|>
   ```
3. **Raw model output** (illustrative; the real text varies):
   `` ```bash\nfind . -name "*.tmp" -delete\n``` ``
4. **Cleaned command** (`engine.clean_command`): the code fence and backticks are
   stripped and the first non-empty line is kept →
   `find . -name "*.tmp" -delete`.
5. **Validator.** The regex layer matches the `find_delete` rule (a `find` that
   deletes what it matches) → **WARN**, reason "find deleting the files it matches."
   The structural layer parses the command, sees `find` with `-delete` but no
   dangerous start path (`/`, `~`, a system dir), so it adds nothing. The verdict is
   the more severe of the two: **WARN**.
6. **Sandbox (if `--preview`).** The folder is copied to a temp dir, the command runs
   there with no network, and you see the exit code and which `.tmp` files it would
   delete — the real folder is untouched.
7. **Confirmation.** Because the risk is WARN, you must type `yes` in full.
8. **Executor.** `executor.run_command` re-validates (defence in depth), then runs
   `/bin/bash -c 'find . -name "*.tmp" -delete'` in a new process group with a
   timeout, streaming output to your terminal.

## 2. Background concepts from scratch

- **LLM (large language model).** A program trained on text that predicts the next
  token. Given a prompt, it continues it. Here it continues "Request: ... " with a
  Bash command.
- **Phi-3 Mini.** A small (~3.8-billion-parameter) open model from Microsoft. "Mini"
  means it is small enough to run on a laptop CPU.
- **Quantisation and 4-bit GGUF.** Model weights are normally 16- or 32-bit numbers.
  *Quantisation* stores them with fewer bits (here 4) to shrink the model and let it
  run in a few GB of RAM on a CPU. **GGUF** is the file format llama.cpp uses to hold
  those quantised weights.
- **llama.cpp and llama-cpp-python.** llama.cpp is a C/C++ library that runs GGUF
  models efficiently on CPUs. `llama-cpp-python` is its Python binding; it is
  compiled when you `pip install` it, which is why a C/C++ compiler is required.
- **Inference.** Running the trained model to produce output (as opposed to training
  it). SageCLI only does inference.
- **Tokens and context window.** Models read and write *tokens* (word pieces). The
  *context window* is how many tokens fit at once; SageCLI uses a small window
  (`n_ctx = 1024`) because prompts and answers are short.
- **Chat format and few-shot.** Phi-3 expects turns marked `<|user|>` / `<|assistant|>`.
  *Few-shot* means showing the model a handful of example request→command pairs so it
  copies the format and answers with one command.
- **Regex.** A pattern language for matching text. The first safety layer is built
  from named regex rules.
- **AST (abstract syntax tree) and bashlex.** An AST is the structured form a parser
  builds from source. `bashlex` parses Bash into an AST, which the second safety
  layer walks to understand command structure that regex cannot.
- **Shell.** The program that interprets Bash commands (`/bin/bash`). SageCLI builds
  a command *for* the shell and only runs it after you confirm.
- **Sandbox and Linux namespaces.** A sandbox isolates a process so it cannot affect
  the real system. On Linux, *namespaces* let a process get its own view of the
  filesystem and network; `bwrap` (bubblewrap) uses them for `--preview`.
- **Why running AI-generated commands is risky.** The model can be wrong, and a
  plausible-looking command can be destructive. That is why SageCLI classifies,
  optionally previews, and always confirms before running.

## 3. File-by-file walkthrough

### Source — `src/sagecli/`

- **`__init__.py`** — holds `__version__` ("0.1.0"), imported by the CLI and scripts.
- **`config.py`** — resolves the model path (`--model` > `$SAGE_MODEL_PATH` >
  `./models/Phi-3-mini-4k-instruct-q4.gguf`), the execution timeout (`--timeout` >
  `$SAGE_TIMEOUT` > 60 s), and the `GenerationSettings` dataclass (temperature 0.1,
  `top_p` 0.9, `max_tokens` 96, `n_ctx` 1024, `n_threads` = CPU count, seed 42).
  `load_allowlist` reads a file of permitted binary names (basename only, `#`
  comments).
- **`prompts.py`** — builds the Phi-3 chat prompt. `SYSTEM_INSTRUCTION` tells the
  model to answer with one command only and never use `sudo`. `FEW_SHOT_EXAMPLES` is
  eight non-destructive request→command pairs. `build_command_prompt` places the
  instruction in the first user turn (Phi-3 has no system role), appends the
  examples, then your request. `STOP_SEQUENCES` are the Phi-3 special tokens that end
  generation. `build_explain_prompt` asks for a one-sentence explanation.
- **`engine.py`** — `Engine` loads the model once (lazily, on first use) via
  `_llama_factory`, which imports `llama_cpp` only when needed (so tests and
  `--help` never require it). `generate_command` builds the prompt, calls the model,
  and passes the raw text to `clean_command`, which cuts at special tokens, takes the
  inside of the first code fence, strips backticks / `Command:` prefixes / `$`
  prompt signs, and keeps the first non-empty line. `explain` does the same for a
  one-line description. `ModelNotFoundError` / `LLMUnavailableError` carry friendly
  messages the CLI prints.
- **`validator.py`** — the safety layer; see [section 4](#4-the-safety-layer-in-depth).
- **`shell_parser.py`** — wraps `bashlex`. `parse_script` returns a `ParseResult`
  with a flat list of `SimpleCommand(argv, redirects)` and the `pipelines` they
  belong to, recursing into pipelines, lists, compounds, substitutions, and the
  string payloads of `sh -c`/`bash -c`, `eval`, `<<<` here-strings and `find -exec`.
  It never raises: `status` is `ok`, `malformed`, `unsupported` or `unavailable`.
- **`sandbox.py`** — `preview` copies the current directory to a temp dir, runs the
  command there with a backend (`bwrap`, then Docker, then "skip"), and reports
  stdout/stderr, the exit code and the created/modified/deleted files (by comparing
  file hashes before and after). The process runner and the Linux check are
  injectable so tests need no real sandbox. See [section 4](#4-the-safety-layer-in-depth).
- **`executor.py`** — `run_command` re-validates the command (raising
  `BlockedCommandError` on BLOCK), then runs `/bin/bash -c` in a new session so the
  whole process group can be killed on timeout (`SIGKILL`, exit code 124).
  `ensure_linux` / `is_linux` guard against running off Linux.
- **`cli.py`** — the Typer app. `run` joins the request words, builds the engine,
  generates and validates the command, shows the risk, optionally explains and
  previews, enforces the confirmation policy (`confirm_execution`), and executes.
  Exit codes are defined here.

### Scripts — `scripts/`

- **`download_model.sh`** — downloads the GGUF model into `./models/` with `curl`
  (or `wget`), resumable. The model is never committed.
- **`build_adversarial_set.py`**, **`build_adversarial_set_v2.py`**,
  **`build_adversarial_set_v3.py`** — maintainer-supplied generators that write the
  adversarial JSONL sets. They are run on Linux; this project never hand-edits the
  resulting data.
- **`validator_benchmark.py`** — runs the validator over an adversarial set and
  reports, per data set, attacks flagged/blocked and benign flagged/blocked, overall
  and per technique. `--layers {regex,structural,both}` selects the layers;
  `--check` enforces the thresholds in `benchmarks/validator_thresholds.toml`.
- **`compare_validator_runs.py`** — reads a baseline report and an "after" report and
  writes a before/after Markdown table, recomputed from each report's `results`.
- **`eval_accuracy.py`** — the accuracy harness; see [section 5](#5-evaluation).
- **`load_nl2bash.py`** — optional converter from the public NL2Bash dataset to the
  `prompts.jsonl` format (the dataset is not vendored).
- **`benchmark.py`** — loads the model once and times 20 fixed requests: cold start,
  first-request latency, mean/median/p95, tokens/sec. Commands are never executed.

### Data — `eval/`

- **`prompts.jsonl`** — 108 hand-written accuracy prompts (id, request,
  reference_command, category, expected_risk, safe_to_run); 13 are WARN/BLOCK.
- **`adversarial.jsonl`** (v1), **`adversarial_v2.jsonl`** (v2),
  **`adversarial_v3.jsonl`** (v3) — generated attack/benign command sets for the
  safety benchmark. v3 is a held-out set: see [section 5](#5-evaluation).

### Benchmarks — `benchmarks/`

- **`validator_baseline.json` / `.md`**, **`validator_baseline_v2.*`**,
  **`validator_baseline_v3.*`** — the committed regex-only baselines (generated on
  Linux). They are never regenerated.
- **`validator_thresholds.toml`** — the no-regression gates `--check` enforces, one
  table per data set (`data`, `min_attack_block_rate`, `max_benign_blocked`).
- `validator_after*.json`, `validator_comparison*.md`, `validator_results*`,
  `results.*`, `eval_results.*` — produced by the scripts; most are gitignored
  (the committed after-run and comparison files come from the maintainer's Linux run).

### Tests — `tests/`

- **`conftest.py`** — shared fixtures: `FakeEngine` and `FakeLlama` so the model is
  always mocked.
- **`test_validator.py`** — the regex-layer rules: dangerous, obfuscated, chained and
  safe look-alike commands, plus allowlist cases.
- **`test_structural.py`** — the combined layers: canonicalisation, xargs
  reconstruction, the parse-failure WARN, and benign commands that must not be blocked.
- **`test_shell_parser.py`** — the bashlex parser: argv extraction, pipelines,
  substitution recursion, `bash -c`/`find -exec` payloads, malformed vs unsupported.
- **`test_sandbox.py`** — the sandbox flow with the runner mocked, plus one
  `@pytest.mark.sandbox` integration test that runs only when `bwrap` is installed.
- **`test_cli.py`** — the CLI: version, dry-run, confirmation policy, BLOCK never
  runs, `--preview`, allowlist, missing model, off-Linux refusal.
- **`test_engine.py`**, **`test_executor.py`**, **`test_benchmark.py`** — the engine
  cleanup, the executor (bash args, timeout kill, BLOCK refusal), the latency script.
- **`test_validator_benchmark.py`**, **`test_compare_validator_runs.py`**,
  **`test_eval_accuracy.py`** — the three script harnesses on tiny in-memory data.
- **`test_line_endings.py`** — reads every blob in the git index and fails on any
  carriage return, so no file is ever committed with CRLF.

### Root files

- **`Dockerfile`** / **`.dockerignore`** — the container image; see
  [section 7](#7-docker-and-cicd).
- **`.gitignore`** — excludes model files, virtualenvs, caches and generated
  benchmark output.
- **`.gitattributes`** — forces LF line endings (`* text=auto eol=lf`) and marks
  `*.gguf` binary.
- **`pyproject.toml`** — package metadata, dependencies (`typer`, `bashlex`; `llm`
  and `dev` extras), the `sage` entry point, pytest and ruff config.
- **`CLAUDE.md`** — the handoff notes: design decisions, layout, the phase checklist,
  and the verified/not-verified list.
- **`LINUX_TESTING.md`** — the exact commands to verify everything on Linux.
- **`LICENSE`** — MIT.
- **`README.md`**, **`docs/WORKING.md`** (this file), **`docs/INSTALLATION.md`**.

## 4. The safety layer in depth

The validator returns a `ValidationResult(risk, rules, reason, segments, matches)`.
The risk is the highest of all matches; `reason` joins the reasons of the top-risk
matches. `validate(command, allowlist=None, *, layers="both")` runs the regex layer
and/or the structural layer and takes the more severe verdict.

**Normalisation (regex layer), with before→after examples.** Before any rule runs,
the command is normalised to defeat casual obfuscation:

- line continuations joined; `$IFS`/`${IFS}` → a space (`rm${IFS}-rf${IFS}/` →
  `rm -rf /`);
- simple `NAME=value` assignments collected and expanded (`a=r;b=m;$a$b` → `rm`);
- `$(echo word)` and backtick `echo` inlined; brace lists at command position
  expanded (`{rm,-rf,/}` → `rm -rf /`);
- `shlex` dequotes each segment (`r""m`, `r''m`, `\rm`, `r\m` → `rm`); the command
  name is reduced to its basename (`/bin/rm` → `rm`).

**Masking.** Quoted strings containing spaces become `'…'` in the text the rules
see, so `echo "rm -rf /" > notes.txt` and `grep -r "dd if=" .` stay SAFE — but those
strings are re-validated where a shell would actually execute them (`bash -c`,
`eval`, here-strings, `find -exec`, strings piped into a shell, interpreter
`system()` calls).

**Rule categories** (in `validator.ALL_RULE_NAMES`): recursive_delete,
disk_destruction, fork_bomb, permissions, remote_exec, critical_file, power,
privilege, process_kill, history_wipe, obfuscation, interpreter, allowlist, plus
`could_not_parse_structure`. For each, an example, why it is dangerous, and a SAFE
look-alike:

- **recursive_delete** — `rm -rf /` BLOCK (erases everything); `rm -rf ./build`
  WARN; `rm file.txt` SAFE.
- **disk_destruction** — `dd of=/dev/sda` / `mkfs.ext4 /dev/sda1` BLOCK (overwrite a
  disk); `dd of=./test.img` and `mkfs.ext4 ./disk.img` SAFE/WARN (a regular file).
- **remote_exec** — `curl … | sh` BLOCK (runs downloaded code); `curl -O url` SAFE.
- **critical_file** — `echo x > /etc/passwd` BLOCK; `cat /etc/passwd` SAFE (reading).
- **power / process_kill / history_wipe** — `shutdown`, `kill -9 1`, `history -c`
  BLOCK; `kill 1234`, `history | tail` SAFE.

**The structural layer** parses the command with bashlex and adds checks regex
cannot do well:

- *Path canonicalisation* for recursive `rm`: `posixpath.normpath` resolves `/.`,
  `//`, `/tmp/..` and `$(pwd)/..`; if the result is `/` or its first component is a
  system directory it is BLOCK. `/tmp/mydir` stays WARN; `$HOME/.cache` is left to
  the regex layer so it stays WARN.
- *xargs reconstruction*: for `echo`/`printf … | xargs CMD`, the emitted words are
  rebuilt into `CMD …` (honouring `-I{}`) and re-checked, catching dangerous
  arguments that arrive through the pipe.
- *device-aware* `dd`/`mkfs`, recursive `chmod`/`chown` on a system path, redirects
  onto a critical file or block device, and download/decoder piped into a shell.

**The BLOCK/WARN/SAFE policy** is enforced in `cli.confirm_execution`: BLOCK is never
run; WARN needs `yes` typed in full; SAFE needs a `y/N` (skipped by `--yes`).

**Allowlist mode.** With `--allowlist FILE`, every command name seen — including
wrappers like `sudo`/`xargs` and dynamic names — must be listed, else BLOCK.

**Parse-failure policy.** If bashlex reports `malformed`, the structural layer adds a
WARN `could_not_parse_structure`. Valid-but-unsupported syntax (e.g. `$((...))`)
falls back to the regex layer silently, so ordinary commands are not all warned.

**How the validator can be bypassed, and why there are more layers.** A heuristic
cannot see everything (a variable filled from command output, truly novel quoting).
That is why confirmation is mandatory, the executor re-validates (so a caller cannot
skip the policy), and `--preview` lets you watch the effect on a copy first.

**The sandbox** (`sandbox.py`) is the preview mechanism. It copies the working
directory (refusing above 50 MB), runs the command in `bwrap` (host read-only, the
copy read-write, no network) or a Docker container (`--network none`, only the copy
mounted), with a hard timeout, and reports the exit code, truncated output and a
file diff. It is a guard rail, not a security boundary.

## 5. Evaluation

**Adversarial benchmark.** `scripts/validator_benchmark.py` classifies every row of
an adversarial set (`id`, `command`, `technique`, `should_block`) and reports four
numbers: attacks flagged (WARN or BLOCK), **attacks blocked** (BLOCK), benign
flagged, **benign blocked**. The two BLOCKED numbers are the headline metrics and
the only ones CI gates on. `compare_validator_runs.py` turns a baseline report and an
after report into a before/after table.

**Why the baseline is frozen.** The baselines are the regex-only numbers captured
before the structural layer existed. They are committed and never regenerated, so the
before/after comparison stays honest. **v3 is a held-out set:** it was written after
the structural layer, without looking at the rules, and is measured once per version.
Changing the validator after seeing v3 results "burns" v3, so new weaknesses it finds
are recorded for a future pass with a fresh v4 set, not quietly patched.

**Accuracy harness.** `scripts/eval_accuracy.py` runs each prompt in
`eval/prompts.jsonl` through the engine and reports: exact match after normalisation
(whitespace, quote style, short-flag order), validator-verdict agreement with
`expected_risk`, and per-request latency. `--equivalence` additionally runs the
generated and reference commands in the sandbox on an identical fixture and compares
stdout and exit code. It writes `eval/manual_grading.csv` for a human to grade and
`benchmarks/eval_results.{json,md}`. `--mock` uses a fake engine returning the
reference commands, so the harness runs in CI without the model.

**Adding a case.** New adversarial rows come from the maintainer's generator scripts,
never by hand. A new accuracy prompt is one JSON line in `eval/prompts.jsonl` with
all six fields.

## 6. The test suite

Tests run in under ten seconds and need no model, bwrap or Docker. The model is
mocked by `FakeEngine`/`FakeLlama` (conftest), the subprocess by a fake `Popen`
(test_executor) and the sandbox by an injected runner (test_sandbox). Dangerous and
safe commands are organised as parametrized lists in `test_validator.py` and
`test_structural.py`. To add a dangerous-command test, add a `(command, rule)` pair
to `BLOCK_CASES`/`WARN_CASES` (or a string to `SAFE_CASES`) and run `pytest`. The one
test needing a real sandbox is marked `@pytest.mark.sandbox` and skips when `bwrap`
is absent.

## 7. Docker and CI/CD

**Dockerfile.** A *builder* stage (`python:3.11-slim` plus `build-essential cmake`)
installs `.[llm]` into `/opt/venv` with `CMAKE_ARGS=-DGGML_NATIVE=OFF` (a portable
CPU build). The *runtime* stage copies only the venv, adds `libgomp1` (the OpenMP
runtime llama.cpp needs), sets `SAGE_MODEL_PATH`, creates a non-root `sage` user,
sets `/work` as the working directory, declares `/models` as a volume, and uses
`sage` as the entrypoint. The model is mounted at run time, never copied in.
`.dockerignore` keeps the build context small.

**CI (`.github/workflows/ci.yml`).** On every push and PR to `main`, on
`ubuntu-latest`: install `.[dev]`, run `ruff check`, run `pytest`, run the validator
benchmark with `--layers both --check` for v1 and v2, run `eval_accuracy.py --mock`,
upload the results, then (a second job) build the Docker image and run
`sage --version`. No model is downloaded.

## 8. Configuration reference

| Setting | Flag | Env var | Default |
| --- | --- | --- | --- |
| Model path | `--model` | `SAGE_MODEL_PATH` | `./models/Phi-3-mini-4k-instruct-q4.gguf` |
| Timeout (s) | `--timeout` | `SAGE_TIMEOUT` | 60 |
| Preview image | — | `SAGE_SANDBOX_IMAGE` | `debian:stable-slim` |
| Allowlist | `--allowlist` | — | none |

`GenerationSettings` (in `config.py`): temperature 0.1, `top_p` 0.9, `max_tokens` 96
(64 for explanations), `n_ctx` 1024, `n_threads` = CPU count, seed 42.

## 9. Extending the project

- **Add a safety rule.** Add a `Rule(...)` to `SEGMENT_RULES` (or `RAW_RULES`) in
  `validator.py`, give it a name, category, risk and regex, and add tests. For
  structure-dependent checks, extend `_structural_command`/`_structural_pipeline`.
- **Change the model.** Point `--model`/`$SAGE_MODEL_PATH` at another GGUF file; the
  prompt format in `prompts.py` is Phi-3 specific, so adjust it for other families.
- **Tune the prompt.** Edit `SYSTEM_INSTRUCTION` and `FEW_SHOT_EXAMPLES`.
- **Tune latency.** Adjust `n_threads`, `n_ctx` and `max_tokens` in
  `GenerationSettings`; measure with `scripts/benchmark.py`.
- **Compare quantisation levels.** Download a different quant of the model and run
  the latency and accuracy scripts on each.

## 10. Design decisions and trade-offs

- **Optional model runtime.** `llama-cpp-python` is an extra, imported lazily, so
  tests and CI never compile it. Trade-off: `--help` works without the model, but the
  first real run must build/load it.
- **Two safety layers.** Regex is fast and catches obfuscation; bashlex adds real
  structure but cannot parse all of Bash. Combining them (max severity) gets the best
  of both; the parse-failure WARN keeps unparsed input from passing silently.
- **Heuristic, not a sandbox-only model.** The validator plus confirmation plus
  optional preview is defence in depth. None alone is sufficient; together they make
  a mistake unlikely to run unseen.
- **Linux-only execution.** The executor and sandbox refuse off Linux, so the project
  can be developed safely on any OS with `--dry-run`.
- **Frozen baselines and a held-out set.** Honest measurement matters more than a
  pretty number, so baselines are never regenerated and v3 is never tuned against.

## 11. Interview cheat sheet

1. **Why a local model instead of an API?** Privacy, offline use, no key or cost.
2. **What is quantisation and why 4-bit GGUF?** Lower-precision weights shrink the
   model so it runs on a CPU in a few GB; GGUF is llama.cpp's format.
3. **Why regex *and* bashlex?** Regex is fast and undoes obfuscation; bashlex gives
   real structure (paths through `xargs`, canonical targets) regex cannot. The
   verdict is the more severe of the two.
4. **How do you handle bypasses?** Normalisation, masking + re-validation where a
   shell executes a string, a parse-failure WARN, the executor re-validating, and a
   mandatory confirmation plus optional sandbox preview.
5. **Why mock the LLM in CI?** Speed and determinism; CI must pass with no model,
   no GPU, no network, in seconds.
6. **How is detection measured?** `validator_benchmark.py` over adversarial sets;
   headline metrics are attacks BLOCKED and benign BLOCKED; CI gates on them.
7. **Why a frozen baseline and a held-out v3?** So before/after and generalisation
   numbers are honest and not tuned to the test.
8. **How is accuracy measured?** `eval_accuracy.py`: exact match after
   normalisation, verdict agreement, latency, and optional sandbox equivalence; a
   human grades `manual_grading.csv`.
9. **How does the sandbox work and what are its limits?** bwrap/Docker on a copy of
   the folder, no network, timeout; it reduces risk but is not a VM or a security
   boundary.
10. **What is the confirmation policy?** BLOCK never runs; WARN needs `yes` in full;
    SAFE needs `y/N` (skipped by `--yes`).
11. **How do you tune latency?** Threads, context size, `max_tokens`; measure with
    `benchmark.py`.
12. **Why place the system instruction in the first user turn?** Phi-3 Mini's
    template has no system role.
13. **How are destructive commands prevented on the dev machine?** The executor and
    sandbox require `sys.platform` to start with `linux`; `--dry-run` works anywhere.
14. **What can the validator still miss?** Parameter slicing, ANSI-C quoting, globbed
    paths, variables from command output, and anything needing full shell semantics.
15. **What would you improve next?** Close the v3-exposed gaps (with a fresh v4 set),
    add more backends to the sandbox, and evaluate accuracy with the real model
    across quantisation levels.
