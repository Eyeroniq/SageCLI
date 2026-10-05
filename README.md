# SageCLI

[![CI](https://github.com/Eyeroniq/SageCLI/actions/workflows/ci.yml/badge.svg)](https://github.com/Eyeroniq/SageCLI/actions/workflows/ci.yml)

Offline plain-English to Bash for Linux. A local Phi-3 Mini model turns your
request into one Bash command, a safety layer checks it, and nothing runs until
you confirm.

Work in progress. See `CLAUDE.md` for the build status.

## Regex-only baseline

`eval/adversarial.jsonl` holds obfuscated attack commands and benign look-alikes.
`scripts/validator_benchmark.py` reports how many attacks the validator flags
(overall and per technique), its false-positive rate, and the misses. The first
measurement uses the regex layer only and is kept as
`benchmarks/validator_baseline.json`. Missed attacks are expected at this stage.
Run the script to get the numbers (see `LINUX_TESTING.md`).

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
