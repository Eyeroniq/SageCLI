# SageCLI

[![CI](https://github.com/Eyeroniq/SageCLI/actions/workflows/ci.yml/badge.svg)](https://github.com/Eyeroniq/SageCLI/actions/workflows/ci.yml)

Offline plain-English to Bash for Linux. A local Phi-3 Mini model turns your
request into one Bash command, a safety layer checks it, and nothing runs until
you confirm. No internet, cloud APIs or telemetry at runtime.

```text
$ sage "show the 10 largest files in this folder"
```

SageCLI prints the generated command and its risk level (SAFE, WARN or BLOCK),
then asks before running it. This is the minimal Phase 1 README; a full guide
comes later.

## Quick install (Linux)

You need Python 3.11+, a C/C++ compiler and cmake (to build `llama-cpp-python`),
about 4 GB of RAM and about 3 GB of disk.

```bash
git clone https://github.com/Eyeroniq/SageCLI.git && cd SageCLI
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[llm]"
bash scripts/download_model.sh
```

The download script fetches `Phi-3-mini-4k-instruct-q4.gguf` (about 2.4 GB) from the
Hugging Face repo `microsoft/Phi-3-mini-4k-instruct-gguf` into `./models/`. The model
is downloaded separately and is not part of this repository; it has its own license
(see its Hugging Face model card). SageCLI's code is MIT licensed.

## Usage

```bash
sage "find all .log files bigger than 10 MB"
sage --dry-run "show disk usage of each folder here"   # show and check, never run
sage --explain "count lines in all python files"
```

| Flag | Meaning |
| --- | --- |
| `--dry-run` | Show the command and its risk, never execute. |
| `--yes`, `-y` | Skip the y/N prompt for SAFE commands only. |
| `--explain` | Add a one-line explanation from the model. |
| `--model PATH` | GGUF model file (default `$SAGE_MODEL_PATH`, then `./models/Phi-3-mini-4k-instruct-q4.gguf`). |
| `--allowlist FILE` | Only binaries listed in FILE (one per line) are allowed; anything else is blocked. |
| `--timeout SECONDS` | Kill the command after this long (default `$SAGE_TIMEOUT` or 60). |
| `--version` | Print the version. |

Exit codes: 0 ok or dry run, 1 aborted or no command generated, 2 usage error or
missing model/runtime, 3 blocked, 4 execution refused off Linux. When a command
runs, its own exit code is returned (124 on timeout).

## Safety summary

Every generated command goes through `src/sagecli/validator.py` before anything
runs. It undoes common obfuscation (quote splitting like `r""m`, backslashes,
variable assembly, `$IFS`, brace lists, simple `$(echo ...)`), splits chains,
pipelines and substitutions, and checks every piece against named rules:
recursive deletion, disk and filesystem destruction, fork bombs, recursive
permission changes on system paths, remote or decoded code piped into a shell,
overwriting critical files, shutdown/reboot, privilege escalation, killing init,
wiping history or logs, `eval` and interpreter one-liners.

- **BLOCK** is never executed, not even with `--yes`.
- **WARN** runs only if you type `yes` in full.
- **SAFE** asks a normal y/N question (skipped by `--yes`).

The executor re-checks the command and refuses BLOCK, and refuses to run anything
when the platform is not Linux.

## Regex-only baseline

`eval/adversarial.jsonl` holds obfuscated attack commands and benign look-alikes.
`scripts/validator_benchmark.py` reports how many attacks the validator flags
(overall and per technique), its false-positive rate, and the misses. The first
measurement uses the regex layer only and is kept as
`benchmarks/validator_baseline.json`. Missed attacks are expected at this stage.
Run the script to get the numbers (see `LINUX_TESTING.md`).

## Latency

`scripts/benchmark.py` loads the model once, runs 20 fixed requests and reports
cold start, mean/median/p95 latency and tokens per second for your machine. Run
the script to get your numbers.

## Docker

The image contains SageCLI and llama-cpp-python but not the model. Download the
model first (`bash scripts/download_model.sh`), then mount it at `/models`:

```bash
docker build -t sagecli .
docker run --rm -it -v "$PWD/models:/models:ro" -v "$PWD:/work" sagecli --dry-run "show the 10 largest files in this folder"
```

The container runs as a non-root user (uid 10001) with `/work` as its working
directory. If confirmed commands need to write to the mounted folder, add
`--user "$(id -u):$(id -g)"`.

## Development

```bash
pip install -e ".[dev]"     # no model runtime needed
ruff check .
pytest                      # the model and subprocesses are mocked
```

`LINUX_TESTING.md` lists every command to verify the project on Linux.

## Limitations

- The safety layer is pattern based. It cannot catch everything: parameter
  slicing (`${PATH:0:1}`), ANSI-C quoting (`$'\x72m'`), globbed paths (`/h?me`),
  variables filled from command output, and anything that needs a real parse of
  the shell grammar can slip through. Always read the command before confirming.
- A small 4-bit model makes mistakes; generated commands can be wrong even when
  they are SAFE.
- Linux only. Execution is refused on other platforms; `--dry-run` works anywhere.

## License

MIT, see `LICENSE`. The Phi-3 Mini model is downloaded separately under its own license.
