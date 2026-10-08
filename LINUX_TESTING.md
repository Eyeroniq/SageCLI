# Linux testing checklist

Nothing in this repository is executed on the Windows development machine (apart
from `scripts/build_adversarial_set.py`, which only writes `eval/adversarial.jsonl`).
Run these steps on a Linux machine to verify the project. Commands run from the
repository root.

## 1. Setup

```bash
git clone https://github.com/Eyeroniq/SageCLI.git && cd SageCLI
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
```

## 2. Lint and tests (no model needed)

```bash
ruff check .
pytest
```

## 3. Validator baseline (step 1.3), run ONCE

The baseline is the regex-only measurement. Create it once and commit it; never
regenerate or overwrite it afterwards.

```bash
python scripts/validator_benchmark.py --layers regex --out benchmarks/validator_baseline.json
git add benchmarks/validator_baseline.json benchmarks/validator_baseline.md
```

Then open `benchmarks/validator_thresholds.toml` and set `min_detection_rate` to the
measured `detection_rate` (and `max_false_positives` to the measured count if it is
higher than 1 and the false positives are acceptable). Check that it passes:

```bash
python scripts/validator_benchmark.py --check
```

`--layers structural` and `--layers both` exit with code 2 until Phase 2.
Use `--data PATH` (alias `--dataset`) to benchmark another data set. The gate CI
runs (headline metrics: attacks BLOCKED and benign BLOCKED, per data set):

```bash
python scripts/validator_benchmark.py --check --data eval/adversarial.jsonl
python scripts/validator_benchmark.py --check --data eval/adversarial_v2.jsonl
```

## 4. Model and latency benchmark (step 1.4)

Needs a C/C++ compiler and cmake for `llama-cpp-python`.

```bash
pip install -e ".[dev,llm]"
bash scripts/download_model.sh
sage --dry-run "show the 10 largest files in this folder"
python scripts/benchmark.py
```

`scripts/benchmark.py` loads the model once, runs 20 fixed requests and writes
`benchmarks/results.md` and `benchmarks/results.json` (cold start, first request,
mean/median/p95 latency, tokens/sec, CPU model, threads). Generated commands are
printed, never executed. Try `--threads N` to compare thread counts.

## 5. Docker (step 1.5)

```bash
docker build -t sagecli .
docker run --rm sagecli --version
docker run --rm -it -v "$PWD/models:/models:ro" -v "$PWD:/work" sagecli --dry-run "show the 10 largest files in this folder"
```

The first build compiles llama-cpp-python and takes several minutes. The model is
read from the mounted `/models` volume and is never copied into the image.

## 6. Validator "after" run and before/after table (step 2.2)

The baselines are the frozen regex-only numbers. Produce the "after" numbers with
both layers (bashlex structural + regex) and compare. Do not touch the baselines.

```bash
python scripts/validator_benchmark.py --layers both \
  --out benchmarks/validator_after.json --data eval/adversarial.jsonl
python scripts/validator_benchmark.py --layers both \
  --out benchmarks/validator_after_v2.json --data eval/adversarial_v2.jsonl

python scripts/compare_validator_runs.py \
  --baseline benchmarks/validator_baseline.json \
  --after benchmarks/validator_after.json \
  --out benchmarks/validator_comparison.md
python scripts/compare_validator_runs.py \
  --baseline benchmarks/validator_baseline_v2.json \
  --after benchmarks/validator_after_v2.json \
  --out benchmarks/validator_comparison_v2.md
```

Read the comparison tables, then raise the floors in
`benchmarks/validator_thresholds.toml` to the measured `--layers both` values
(attack BLOCK rate and benign BLOCKED) so regressions fail CI. CI already gates on
`--layers both`; confirm it still passes:

```bash
python scripts/validator_benchmark.py --layers both --check --data eval/adversarial.jsonl
python scripts/validator_benchmark.py --layers both --check --data eval/adversarial_v2.jsonl
```

## 7. Sandboxed preview (step 2.3)

Needs bubblewrap (`sudo apt-get install bubblewrap`) or Docker.

```bash
sage --preview --dry-run "list the files here"            # uses bwrap if present
SAGE_SANDBOX_IMAGE=debian:stable-slim sage --preview --dry-run "count lines in *.py"
pytest -m sandbox                                         # the bwrap integration test
```

The preview runs the command against a copy of the current directory and prints the
exit code, truncated output and the created/modified/deleted files. The real
directory is never touched. It is a guard rail, not a security boundary.

## 8. Accuracy evaluation (step 2.4, needs the model)

```bash
python scripts/eval_accuracy.py                           # real model, writes benchmarks/eval_results.*
python scripts/eval_accuracy.py --equivalence             # also compares in the sandbox (Linux)
# then fill in the "correct (y/n)" column:
$EDITOR eval/manual_grading.csv
python scripts/eval_accuracy.py --mock                    # harness self-check, no model (CI runs this)
```

Optional: convert the public NL2Bash dataset (download it yourself; not vendored):

```bash
python scripts/load_nl2bash.py --nl all.nl --cm all.cm --out eval/nl2bash.jsonl
python scripts/eval_accuracy.py --data eval/nl2bash.jsonl
```

Accuracy, latency and detection numbers come only from these runs on your machine;
none are committed or claimed here.
