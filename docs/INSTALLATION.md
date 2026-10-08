# Installing SageCLI

A detailed, beginner-friendly install and verification guide. SageCLI runs on
**Linux**; you can develop on other systems with `--dry-run`, but executing commands
and the sandbox preview are Linux-only. All example outputs are illustrative and may
differ on your machine.

## Table of contents

1. [Requirements and first checks](#1-requirements-and-first-checks)
2. [Ubuntu / Debian](#2-ubuntu--debian)
3. [Fedora / RHEL and Arch](#3-fedora--rhel-and-arch)
4. [Virtual environment and install](#4-virtual-environment-and-install)
5. [Download the model](#5-download-the-model)
6. [First run](#6-first-run)
7. [Tests, linter and benchmarks](#7-tests-linter-and-benchmarks)
8. [Docker](#8-docker)
9. [Optional: system-wide install](#9-optional-system-wide-install)
10. [Verification checklist](#10-verification-checklist)
11. [Troubleshooting](#11-troubleshooting)
12. [Uninstall and update](#12-uninstall-and-update)

## 1. Requirements and first checks

| Requirement | Minimum | Notes |
| --- | --- | --- |
| OS | Linux | Execution and `--preview` are Linux-only. |
| Python | 3.11+ | `python3 --version`. |
| RAM | ~4 GB | To load the 4-bit model. |
| Disk | ~3 GB | For the model file. |
| Compiler | gcc/clang + CMake | To build `llama-cpp-python`. |
| Sandbox (optional) | bubblewrap or Docker | For `--preview`. |

Check your machine first:

```bash
uname -a              # kernel and architecture
python3 --version     # expect 3.11 or newer
free -h               # expect ~4 GB available
nproc                 # number of CPU cores (used as model threads)
```

## 2. Ubuntu / Debian

```bash
sudo apt-get update
sudo apt-get install -y build-essential cmake python3-venv python3-pip git bubblewrap
```

- `build-essential`, `cmake` — compiler and build tool for `llama-cpp-python`.
- `python3-venv`, `python3-pip` — virtual environments and the package installer.
- `git` — to clone the repository.
- `bubblewrap` — provides `bwrap` for `--preview` (optional).

Expected: the packages install without error.

## 3. Fedora / RHEL and Arch

Fedora / RHEL:

```bash
sudo dnf install -y gcc gcc-c++ make cmake python3 python3-pip git bubblewrap
```

Arch:

```bash
sudo pacman -S --needed base-devel cmake python python-pip git bubblewrap
```

(The bubblewrap package is `bubblewrap` on all three; the `bwrap` command comes from it.)

## 4. Virtual environment and install

```bash
git clone https://github.com/Eyeroniq/SageCLI.git
cd SageCLI
python3 -m venv .venv        # create an isolated environment
. .venv/bin/activate         # activate it (prompt shows (.venv))
pip install -e ".[llm]"      # install SageCLI and the model runtime
```

- `python3 -m venv .venv` makes a private copy of Python so packages do not touch the
  system.
- `pip install -e ".[llm]"` installs the package in editable mode plus the `llm`
  extra (`llama-cpp-python`), which **compiles** and can take a few minutes.
- For development without the model runtime, use `pip install -e ".[dev]"` (adds
  pytest and ruff) or `pip install -e ".[dev,llm]"` for both.

Expected: pip finishes with "Successfully installed …" and `sage --version` prints a
version.

## 5. Download the model

```bash
bash scripts/download_model.sh
```

This fetches `Phi-3-mini-4k-instruct-q4.gguf` (~2.4 GB) from the Hugging Face repo
`microsoft/Phi-3-mini-4k-instruct-gguf` into `./models/`, resuming if interrupted.

Manual fallback (if the script cannot run): open the model's page on
huggingface.co, download the `q4` GGUF file, and place it at
`models/Phi-3-mini-4k-instruct-q4.gguf`, or point `--model`/`$SAGE_MODEL_PATH` at
wherever you saved it.

Verify size and location:

```bash
ls -lh models/Phi-3-mini-4k-instruct-q4.gguf   # ~2.4 GB
```

The model is **not** part of this repository and has its own license (see its
Hugging Face model card).

## 6. First run

```bash
sage --dry-run "show the 10 largest files in this folder"
```

Example output (yours may differ):

```text
Command: find . -maxdepth 1 -type f -exec du -h {} + | sort -rh | head -n 10
Risk:    SAFE
Dry run: not executed.
```

Risk levels look like this:

```text
# WARN — you must type 'yes' in full
$ sage "delete the build folder"
Command: rm -rf build
Risk:    WARN
Reason:  Recursive deletion.
This command is risky. Type 'yes' to run it:

# BLOCK — never executed
$ sage "erase the whole disk"
Command: rm -rf /
Risk:    BLOCK
Blocked: this command will not be executed.

# Preview (needs bwrap or Docker)
$ sage --preview "create a file called note.txt"
Command: touch note.txt
Risk:    SAFE
Preview [bwrap]: exit 0
Files changed in a copy of this folder: 1 created, 0 modified, 0 deleted.
  created: note.txt
Run this command? [y/N]:
```

## 7. Tests, linter and benchmarks

```bash
pip install -e ".[dev]"          # test and lint tools (no model needed)
ruff check .                     # style and lint; expect "All checks passed!"
pytest                           # the suite; the model is mocked
pytest -m sandbox                # the bwrap integration test (needs bwrap)

python scripts/validator_benchmark.py --layers both --check   # safety gates
python scripts/eval_accuracy.py --mock                        # harness self-check
python scripts/eval_accuracy.py                               # accuracy (needs model)
python scripts/benchmark.py                                   # latency (needs model)
```

How to read the results:

- `validator_benchmark.py` prints attacks/benign blocked and flagged and writes
  `benchmarks/validator_results.{json,md}`; `--check` exits non-zero if a gate fails.
- `eval_accuracy.py` prints exact-match and verdict-agreement rates and writes
  `benchmarks/eval_results.{json,md}` and `eval/manual_grading.csv`.
- `benchmark.py` prints cold-start and per-request latency and writes
  `benchmarks/results.{json,md}`.

## 8. Docker

```bash
docker build -t sagecli .
docker run --rm sagecli --version
docker run --rm -it \
  -v "$PWD/models:/models:ro" \
  -v "$PWD:/work" \
  sagecli --dry-run "show the 10 largest files in this folder"
```

- The first build compiles the model runtime and takes several minutes.
- The model is read from the mounted `/models` volume and never copied into the image.
- The container runs as a non-root user. To let confirmed commands write to `/work`,
  add `--user "$(id -u):$(id -g)"`.

## 9. Optional: system-wide install

Install `sage` globally with [pipx](https://pipx.pypa.io/) (isolated, on your PATH):

```bash
pipx install "git+https://github.com/Eyeroniq/SageCLI.git[llm]"
```

Or add a shell alias to a checkout's virtual environment:

```bash
echo "alias sage='~/SageCLI/.venv/bin/sage'" >> ~/.bashrc
```

## 10. Verification checklist

Run these; each should behave as noted.

```bash
sage --version                                   # prints a version
sage --dry-run "list files here"                 # SAFE, "Dry run: not executed."
sage --dry-run "erase everything"                # BLOCK, exit code 3
ruff check .                                      # "All checks passed!"
pytest -q                                         # all tests pass
python scripts/validator_benchmark.py --layers both --check   # thresholds met
python scripts/eval_accuracy.py --mock           # exits 0
```

With the model and bwrap installed:

```bash
sage --dry-run "show disk usage here"            # a real command appears
sage --preview --dry-run "list files here"       # Preview [bwrap] line appears
pytest -m sandbox                                 # the integration test runs
```

## 11. Troubleshooting

| Problem | Cause | Fix |
| --- | --- | --- |
| `llama-cpp-python` build fails | No compiler/CMake | `apt-get install build-essential cmake` (or distro equivalent), reinstall `.[llm]`. |
| "Model file not found" | Model not downloaded | `bash scripts/download_model.sh`, or set `--model`/`$SAGE_MODEL_PATH`. |
| `pip` "externally managed environment" | Installing into system Python | Use a venv: `python3 -m venv .venv && . .venv/bin/activate`. |
| Out of memory loading the model | <4 GB free | Close other apps, or use a smaller quantisation. |
| Generation very slow | CPU-only inference | Fewer threads/context; see `benchmark.py --threads N`. |
| Model adds extra text | Model verbosity | `clean_command` strips most of it; rephrase the request. |
| `bwrap` missing or "operation not permitted" | Not installed, or user namespaces disabled | Install `bubblewrap`; if namespaces are disabled, use the Docker backend or skip `--preview`. |
| Docker "permission denied" on `/work` | Container user cannot write | Add `--user "$(id -u):$(id -g)"`. |
| Volume mount path error | Wrong host path | Use an absolute path, e.g. `-v "$PWD/models:/models:ro"`. |
| CRLF line-ending errors | Files checked out with CRLF | Ensure `.gitattributes` is respected; re-clone or `git add --renormalize .`. |
| `ImportError` for `llama_cpp` | `llm` extra not installed | `pip install -e ".[llm]"`. |

## 12. Uninstall and update

Update to the latest version:

```bash
cd SageCLI
git pull
. .venv/bin/activate
pip install -e ".[llm]"          # rebuild if the runtime changed
```

Uninstall:

```bash
pip uninstall sagecli            # remove the package
rm -rf .venv models              # remove the environment and the model
# or, if installed with pipx:
pipx uninstall sagecli
```
