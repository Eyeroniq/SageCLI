# SageCLI

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
