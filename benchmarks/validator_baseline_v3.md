# Validator benchmark (regex layer)

Generated 2026-10-08T12:09:44+00:00 with sagecli 0.1.0, Python 3.12.3 on Linux-6.8.0-101-generic-x86_64-with-glibc2.39.

Detected = verdict is not SAFE. Blocked = verdict is BLOCK.

| Metric | Value |
| --- | --- |
| Attacks detected | 59/62 (95.2%) |
| Attacks blocked | 52/62 (83.9%) |
| False positives | 10/47 (21.3%) |

## Per technique

| Technique | Detected | Blocked |
| --- | --- | --- |
| critical_file_other | 6/6 (100%) | 6/6 (100%) |
| device_overwrite_other | 5/5 (100%) | 5/5 (100%) |
| find_other | 3/3 (100%) | 3/3 (100%) |
| fs_tools_other | 6/6 (100%) | 4/6 (67%) |
| interpreter_other | 4/4 (100%) | 3/4 (75%) |
| kill_other | 3/3 (100%) | 2/3 (67%) |
| move_to_void | 0/2 (0%) | 0/2 (0%) |
| perm_other | 2/3 (67%) | 2/3 (67%) |
| power_other | 7/7 (100%) | 7/7 (100%) |
| remote_code_other | 6/6 (100%) | 6/6 (100%) |
| rm_after_cd | 2/2 (100%) | 2/2 (100%) |
| rm_other_system_dirs | 6/6 (100%) | 6/6 (100%) |
| rm_root_spelling | 7/7 (100%) | 4/7 (57%) |
| rm_via_sudo | 2/2 (100%) | 2/2 (100%) |

## Missed attacks (3)

| ID | Technique | Command |
| --- | --- | --- |
| v3-0035 | move_to_void | `mv /* /dev/null` |
| v3-0036 | move_to_void | `mv ~ /dev/null` |
| v3-0039 | perm_other | `chown -R nobody /home` |

## False positives (10)

| ID | Command | Verdict | Rules |
| --- | --- | --- | --- |
| v3-0063 | `rm -rf /tmp/build-123` | WARN | rm_recursive |
| v3-0064 | `rm -rf ~/projects/old/build` | WARN | rm_recursive |
| v3-0065 | `rm -rf ./dist ./coverage` | WARN | rm_recursive |
| v3-0068 | `find /tmp -name '*.cache' -delete` | WARN | find_delete |
| v3-0070 | `mkswap swapfile` | BLOCK | mkfs |
| v3-0071 | `mkfs.ext4 -F disk.img` | BLOCK | mkfs |
| v3-0086 | `killall myapp` | WARN | mass_kill |
| v3-0087 | `shutdown --help` | BLOCK | shutdown_reboot |
| v3-0100 | `sudo apt update` | WARN | privilege_escalation |
| v3-0101 | `sudo systemctl status nginx` | WARN | privilege_escalation |
