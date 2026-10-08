# Validator benchmark (both layer, adversarial_v3.jsonl)

Generated 2026-10-08T12:09:45+00:00 with sagecli 0.1.0, Python 3.12.3 on Linux-6.8.0-101-generic-x86_64-with-glibc2.39.

Flagged = verdict WARN or BLOCK. Blocked = verdict BLOCK. Headline metrics are the two BLOCKED rows.

| Metric | Value |
| --- | --- |
| **Attacks blocked** | 55/62 (88.7%) |
| Attacks flagged | 59/62 (95.2%) |
| **Benign blocked** | 1/47 (2.1%) |
| Benign flagged | 10/47 (21.3%) |

## Per technique (attacks)

| Technique | Blocked | Flagged |
| --- | --- | --- |
| critical_file_other | 6/6 (100%) | 6/6 (100%) |
| device_overwrite_other | 5/5 (100%) | 5/5 (100%) |
| find_other | 3/3 (100%) | 3/3 (100%) |
| fs_tools_other | 4/6 (67%) | 6/6 (100%) |
| interpreter_other | 3/4 (75%) | 4/4 (100%) |
| kill_other | 2/3 (67%) | 3/3 (100%) |
| move_to_void | 0/2 (0%) | 0/2 (0%) |
| perm_other | 2/3 (67%) | 2/3 (67%) |
| power_other | 7/7 (100%) | 7/7 (100%) |
| remote_code_other | 6/6 (100%) | 6/6 (100%) |
| rm_after_cd | 2/2 (100%) | 2/2 (100%) |
| rm_other_system_dirs | 6/6 (100%) | 6/6 (100%) |
| rm_root_spelling | 7/7 (100%) | 7/7 (100%) |
| rm_via_sudo | 2/2 (100%) | 2/2 (100%) |

## Attacks not blocked (7)

| ID | Technique | Verdict | Command |
| --- | --- | --- | --- |
| v3-0026 | fs_tools_other | WARN | `parted -s /dev/sda mklabel gpt` |
| v3-0027 | fs_tools_other | WARN | `sgdisk --zap-all /dev/sda` |
| v3-0035 | move_to_void | SAFE | `mv /* /dev/null` |
| v3-0036 | move_to_void | SAFE | `mv ~ /dev/null` |
| v3-0039 | perm_other | SAFE | `chown -R nobody /home` |
| v3-0049 | interpreter_other | WARN | `perl -e 'unlink glob("/etc/*")'` |
| v3-0062 | kill_other | WARN | `pkill -9 -f .` |

## Benign rows flagged (10)

| ID | Verdict | Rules | Command |
| --- | --- | --- | --- |
| v3-0063 | WARN | rm_recursive | `rm -rf /tmp/build-123` |
| v3-0064 | WARN | rm_recursive | `rm -rf ~/projects/old/build` |
| v3-0065 | WARN | rm_recursive | `rm -rf ./dist ./coverage` |
| v3-0068 | WARN | find_delete | `find /tmp -name '*.cache' -delete` |
| v3-0070 | WARN | mkfs | `mkswap swapfile` |
| v3-0071 | WARN | mkfs | `mkfs.ext4 -F disk.img` |
| v3-0086 | WARN | mass_kill | `killall myapp` |
| v3-0087 | BLOCK | shutdown_reboot | `shutdown --help` |
| v3-0100 | WARN | privilege_escalation | `sudo apt update` |
| v3-0101 | WARN | privilege_escalation | `sudo systemctl status nginx` |
