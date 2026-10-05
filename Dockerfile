# SageCLI container image. The model is NOT in the image: mount it at /models.
#
#   docker build -t sagecli .
#   docker run --rm -it \
#     -v "$PWD/models:/models:ro" \
#     -v "$PWD:/work" \
#     sagecli --dry-run "show the 10 largest files in this folder"

# ---- builder: compilers live only here ----
FROM python:3.11-slim AS builder

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential cmake \
    && rm -rf /var/lib/apt/lists/*

# Portable CPU build: do not tune llama.cpp for the build machine's CPU only.
ENV CMAKE_ARGS="-DGGML_NATIVE=OFF" \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /src
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install ".[llm]"

# ---- runtime: no compilers ----
FROM python:3.11-slim

# libgomp1: OpenMP runtime used by the compiled llama.cpp library.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH" \
    SAGE_MODEL_PATH="/models/Phi-3-mini-4k-instruct-q4.gguf" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN useradd --create-home --uid 10001 sage
USER sage
WORKDIR /work
VOLUME ["/models"]

ENTRYPOINT ["sage"]
CMD ["--help"]
