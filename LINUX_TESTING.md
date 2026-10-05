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
