---
title: SageCLI Safety Checker
emoji: 🛡️
colorFrom: indigo
colorTo: green
sdk: gradio
sdk_version: 4.44.1
app_file: app.py
pinned: false
license: mit
---

# SageCLI Safety Checker (demo)

A one-page web demo of the [SageCLI](https://github.com/Eyeroniq/SageCLI) safety
validator. Type any Bash command and see whether SageCLI classifies it **SAFE**,
**WARN** or **BLOCK**, which rules matched, and why.

It classifies text only — **nothing is ever executed**, and no model is loaded, so it
is safe and light enough to host for free.

## Run it locally

```bash
cd demo
pip install -r requirements.txt
python app.py
```

Then open the URL it prints (default http://127.0.0.1:7860).

## Deploy to a free Hugging Face Space (one-click link for your portfolio)

1. Go to https://huggingface.co/new-space, choose the **Gradio** SDK, name it
   (e.g. `sagecli-safety-checker`), and create it.
2. Upload the three files from this `demo/` folder: `app.py`, `requirements.txt`
   and this `README.md` (the YAML header at the top configures the Space).
3. The Space builds automatically and gives you a public URL like
   `https://huggingface.co/spaces/<you>/sagecli-safety-checker`.
4. Put that URL behind a button on your portfolio, e.g. "▶ Try the safety checker".

The Space pulls the validator straight from the GitHub repo, so it always matches the
shipping tool. Nothing in the demo runs shell commands.
