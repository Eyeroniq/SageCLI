# SageCLI

[![CI](https://github.com/Eyeroniq/SageCLI/actions/workflows/ci.yml/badge.svg)](https://github.com/Eyeroniq/SageCLI/actions/workflows/ci.yml)

Offline plain-English to Bash for Linux. You type what you want in ordinary
English; a **local** Phi-3 Mini model (running on your CPU, no internet) turns it
into one Bash command; a safety layer checks that command; you can preview it in a
sandbox; and nothing runs until you confirm. No cloud APIs, no telemetry.

```text
$ sage "show the 10 largest files in this folder"
Command: find . -maxdepth 1 -type f -exec du -h {} + | sort -rh | head -n 10
Risk:    SAFE
Run this command? [y/N]:
```

> **Live demo:** try the safety layer in your browser — no install, nothing runs.
> See [demo/](demo/) to launch it locally or deploy a free Hugging Face Space, then
> drop the Space URL here.

## Table of contents

- [What it is](#what-it-is)
- [Live demo](#live-demo)
- [How it works](#how-it-works)
- [The safety layer](#the-safety-layer)
- [What each file does](#what-each-file-does)
- [Requirements](#requirements)
- [Install (Ubuntu / Debian)](#install-ubuntu--debian)
- [Command-line flags and environment variables](#command-line-flags-and-environment-variables)
- [Running the tests and benchmarks](#running-the-tests-and-benchmarks)
- [Docker](#docker)
- [Troubleshooting](#troubleshooting)
- [Glossary](#glossary)
- [Known limitations](#known-limitations)
- [More documentation](#more-documentation)
- [License](#license)

## What it is

SageCLI (`sage`) is a command-line tool for Linux that lets you describe a task in
plain English instead of remembering Bash syntax. It runs a small language model on
your own machine, so it works with no internet connection and sends nothing
anywhere. Every generated command is classified **SAFE**, **WARN** or **BLOCK**
before you are asked to run it, and a BLOCK command is never executed.

A short session:

```text
$ sage "find all log files bigger than 10 MB"
Command: find . -type f -name "*.log" -size +10M
Risk:    SAFE
Run this command? [y/N]: y
./var/app.log
./old/debug.log

$ sage "delete everything in the system"
Command: rm -rf /
Risk:    BLOCK
Reason:  Recursive deletion of /, a system directory, the home directory or everything (*).
Blocked: this command will not be executed.
```

(Output above is an example; what the model generates can differ on your machine.)

## Live demo

The [`demo/`](demo/) folder is a small Gradio web app for the **safety layer**: type
any command and see whether it is SAFE / WARN / BLOCK, which rules matched, and why.
It classifies text only — nothing is executed and no model is loaded. Run it locally
with `python demo/app.py`, or deploy it as a free Hugging Face Space in a couple of
clicks (see [demo/README.md](demo/README.md)) to get a shareable one-click URL.

## How it works

```text
  English request
        |
        v
  +-----------+     build a Phi-3 chat prompt with few-shot examples
  |  engine   | --> run the local model (CPU) --> clean the output to ONE command
  +-----------+
        |
        v
  +-----------+     regex layer  +  bashlex structural layer
  | validator | --> SAFE / WARN / BLOCK, matched rule names, a plain-English reason
  +-----------+
        |
        v
  +-----------+     optional --preview: run in a sandbox against a COPY of the folder
  |  sandbox  | --> show stdout, exit code, and which files it would change
  +-----------+
        |
        v
  confirmation prompt  --> executor runs it with /bin/bash (Linux only)
```

What happens at each risk level:

- **SAFE** — a normal `y/N` prompt. `--yes` skips it.
- **WARN** — you must type the word `yes` in full. `--yes` does **not** skip this.
- **BLOCK** — never executed, not even with `--yes`. The tool exits with code 3.

## The safety layer

Every generated command goes through [`src/sagecli/validator.py`](src/sagecli/validator.py)
before anything runs. It has **two independent layers** and takes the more severe
verdict of the two:

1. **Regex layer.** It first undoes common obfuscation — quote splitting
   (`r""m`, `r''m`), backslashes (`\rm`), variable assembly (`a=r;b=m;$a$b`),
   `$IFS` spacing, brace lists (`{rm,-rf,/}`), simple `$(echo ...)` — then splits
   the command into pipeline stages and substitutions and checks each piece against
   named rules.
2. **Structural layer.** It parses the command with `bashlex` (a real Bash parser)
   into clean commands and pipelines, then applies checks that need structure:
   canonicalising a deletion path (so `rm -rf /tmp/..` is seen as `rm -rf /`),
   reconstructing arguments that reach a command through `xargs`, and recognising
   writes to a block device under `/dev/`. If the parser cannot handle the syntax,
   it falls back to the regex layer and raises the verdict to at least WARN.

Six examples of commands that are blocked, and why:

| Command | Why it is blocked |
| --- | --- |
| `rm -rf /` | Recursive deletion of the whole filesystem. |
| `mkfs.ext4 /dev/sda1` | Formats a disk, erasing it (block device under `/dev/`). |
| `dd if=/dev/zero of=/dev/sda` | Overwrites a raw disk device. |
| `curl -s http://x/i.sh \| sh` | Runs code downloaded from the network. |
| `echo "-rf /" \| xargs rm` | Dangerous arguments reach `rm` through the pipe. |
| `:(){ :\|:& };:` | Fork bomb: spawns processes until the machine stalls. |

And commands that look dangerous but are **not** blocked, because they are safe:

- `echo "rm -rf /" > notes.txt` — writes the text to a file; it is not run.
- `grep -r "dd if=" .` — searches for the text; nothing is executed.
- `rm -rf ./build` — WARN (recursive), not BLOCK: an ordinary project folder.

**What it cannot catch.** This is a heuristic guard rail, not a sandbox or a proof.
It can miss attacks that need information it does not have (for example a variable
filled from command output, or exotic quoting), and the small model can produce a
wrong command that is still SAFE. Always read the command before confirming, and
use `--preview` when you are unsure.

The adversarial benchmark measures how well the two layers do. The numbers are not
printed here on purpose; generate them with
[`scripts/validator_benchmark.py`](scripts/validator_benchmark.py) and the
before/after table with
[`scripts/compare_validator_runs.py`](scripts/compare_validator_runs.py) (which
writes `benchmarks/validator_comparison*.md`). See
[docs/WORKING.md](docs/WORKING.md) for how the evaluation works.

## What each file does

```text
src/sagecli/
  config.py       where the model is, generation settings, timeout, allowlist loader
  prompts.py      builds the Phi-3 chat prompt with few-shot examples
  engine.py       loads the model once and turns a request into one command
  validator.py    the safety layer: regex rules + structural layer, SAFE/WARN/BLOCK
  shell_parser.py parses a command with bashlex (feeds the structural layer)
  sandbox.py      runs --preview in bwrap or Docker against a copy of the folder
  executor.py     runs a confirmed command with /bin/bash and a timeout (Linux only)
  cli.py          the `sage` command-line interface
scripts/          model download, benchmarks, the eval harness, dataset generators
eval/             adversarial command sets and the accuracy prompts
benchmarks/       committed baselines and thresholds for the validator benchmark
tests/            the pytest suite (the model and subprocesses are always mocked)
docs/             WORKING.md and INSTALLATION.md
Dockerfile        multi-stage image; the model is mounted, never copied in
```

A section for every file is in [docs/WORKING.md](docs/WORKING.md).

## Requirements

- **Linux** (the executor and sandbox refuse to run on anything else; `--dry-run`
  works everywhere).
- **Python 3.11+**.
- A **C/C++ compiler and CMake** (to build `llama-cpp-python`, the model runtime).
- About **4 GB of RAM** and **3 GB of disk** for the model.
- Optional: **bubblewrap** (`bwrap`) or **Docker** for `--preview`.

## Install (Ubuntu / Debian)

```bash
sudo apt-get update
sudo apt-get install -y build-essential cmake python3-venv python3-pip git bubblewrap

git clone https://github.com/Eyeroniq/SageCLI.git
cd SageCLI
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[llm]"          # SageCLI plus the model runtime (compiles)

bash scripts/download_model.sh   # about 2.4 GB into ./models/
sage --dry-run "show the 10 largest files in this folder"
```

The download script fetches `Phi-3-mini-4k-instruct-q4.gguf` from the Hugging Face
repo `microsoft/Phi-3-mini-4k-instruct-gguf`. **The model is not part of this
repository and has its own license** (see its Hugging Face model card). SageCLI's
own code is MIT licensed. A full, step-by-step guide — including Fedora and Arch —
is in [docs/INSTALLATION.md](docs/INSTALLATION.md).

## Command-line flags and environment variables

```bash
sage "find all python files here"
sage --dry-run "show disk usage of each folder"   # show and check, never run
sage --explain "count lines in all python files"  # add a one-line explanation
sage --preview "list the files here"              # sandbox preview, then confirm
sage --yes "list files"                           # skip the prompt for SAFE only
sage --allowlist allowed.txt "update packages"    # only listed binaries may run
```

| Flag | Meaning |
| --- | --- |
| `--dry-run` | Generate and check the command, but never execute it. |
| `--yes`, `-y` | Skip the `y/N` prompt for SAFE commands only. |
| `--explain` | Also print a one-line explanation from the model. |
| `--preview` | Run the command in a sandbox against a copy of this folder first. |
| `--model PATH` | GGUF model file to use. |
| `--allowlist FILE` | Only binaries listed in FILE (one per line) are allowed. |
| `--timeout SECONDS` | Kill a running command after this long. |
| `--version` | Print the version and exit. |

| Environment variable | Meaning | Default |
| --- | --- | --- |
| `SAGE_MODEL_PATH` | Model path when `--model` is not given. | `./models/Phi-3-mini-4k-instruct-q4.gguf` |
| `SAGE_TIMEOUT` | Execution timeout when `--timeout` is not given. | `60` |
| `SAGE_SANDBOX_IMAGE` | Docker image for `--preview` when the backend is Docker. | `debian:stable-slim` |

**Exit codes:** `0` ok or dry run, `1` aborted or no command generated, `2` usage
error or missing model/runtime, `3` blocked, `4` execution refused off Linux. When
a command actually runs, its own exit code is returned (`124` on timeout).

## Running the tests and benchmarks

```bash
pip install -e ".[dev]"          # test and lint tools; no model runtime needed
ruff check .
pytest                           # the model and subprocesses are mocked
pytest -m sandbox                # the bwrap integration test (Linux + bwrap)

python scripts/validator_benchmark.py --layers both --check   # safety benchmark
python scripts/eval_accuracy.py --mock                        # eval harness self-check
python scripts/eval_accuracy.py                               # accuracy, needs the model
python scripts/benchmark.py                                   # latency, needs the model
```

These scripts print and save the numbers for **your** machine; no figures are baked
into this README. CI runs lint, the tests, the validator benchmark (both layers)
and `eval_accuracy.py --mock`, then builds the Docker image, on every push.

## Docker

The image contains SageCLI and the model runtime but **not** the model. Download the
model first, then mount it at `/models`:

```bash
docker build -t sagecli .
docker run --rm -it \
  -v "$PWD/models:/models:ro" \
  -v "$PWD:/work" \
  sagecli --dry-run "show the 10 largest files in this folder"
```

The container runs as a non-root user (uid 10001) with `/work` as its working
directory. To let confirmed commands write to the mounted folder, add
`--user "$(id -u):$(id -g)"`.

## Troubleshooting

- **`llama-cpp-python` fails to build** — install a compiler and CMake
  (`build-essential cmake`), then reinstall `.[llm]`.
- **"Model file not found"** — run `bash scripts/download_model.sh`, or point
  `--model` / `$SAGE_MODEL_PATH` at an existing `.gguf` file.
- **Generation is slow** — the model runs on CPU; try fewer threads or a smaller
  context (see `scripts/benchmark.py --threads N`).
- **The model adds extra text** — `engine.clean_command` already strips fences and
  prefixes; rephrase the request if it still misbehaves.
- **Docker permission errors writing to `/work`** — add `--user "$(id -u):$(id -g)"`.
- **`pip` "externally managed environment"** — install inside a virtual environment
  (`python3 -m venv .venv && . .venv/bin/activate`).

A longer "Problem, Cause, Fix" list is in [docs/INSTALLATION.md](docs/INSTALLATION.md).

## Glossary

- **GGUF** — the file format llama.cpp uses for model weights.
- **Quantisation** — storing weights at lower precision (here 4-bit) so a model
  runs in less memory on a CPU.
- **CLI** — command-line interface.
- **CI/CD** — automated checks that run on every push (here, GitHub Actions).
- **Regex** — a pattern language for matching text.
- **AST** — abstract syntax tree; the structured form a parser produces.
- **Sandbox** — an isolated environment where a command cannot touch the real system.
- **Inference** — running a trained model to get an output.

## Known limitations

- The safety layer is a heuristic. Parameter slicing (`${PATH:0:1}`), ANSI-C quoting
  (`$'\x72m'`), globbed paths (`/h?me`), variables filled from command output, and
  anything needing full shell semantics can slip through. Always read the command.
- A small 4-bit model makes mistakes; a SAFE command can still be wrong.
- `--preview` reduces risk but is **not** a security boundary against a determined
  attacker; bubblewrap namespaces are not a full virtual machine.
- Linux only. Execution and preview are refused elsewhere; `--dry-run` works anywhere.

The accuracy prompts can be extended with the public
[NL2Bash](https://github.com/TellinaTool/nl2bash) dataset via
[`scripts/load_nl2bash.py`](scripts/load_nl2bash.py); the dataset is not vendored
here.

## More documentation

- [docs/WORKING.md](docs/WORKING.md) — how the whole project works, file by file,
  from background concepts to the code, plus an interview cheat sheet.
- [docs/INSTALLATION.md](docs/INSTALLATION.md) — a detailed install and verification
  guide for Ubuntu/Debian, Fedora/RHEL and Arch.

## License

MIT, see [LICENSE](LICENSE). The Phi-3 Mini model is downloaded separately and has
its own license.
