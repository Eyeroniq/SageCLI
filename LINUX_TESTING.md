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
Use `--data PATH` (alias `--dataset`) to benchmark another data set, for example
`--data eval/adversarial_v2.jsonl`.

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
