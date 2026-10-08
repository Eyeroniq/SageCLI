# Validator benchmark (both layer, adversarial_v2.jsonl)

Generated 2026-10-08T12:00:41+00:00 with sagecli 0.1.0, Python 3.12.3 on Linux-6.8.0-101-generic-x86_64-with-glibc2.39.

Flagged = verdict WARN or BLOCK. Blocked = verdict BLOCK. Headline metrics are the two BLOCKED rows.

| Metric | Value |
| --- | --- |
| **Attacks blocked** | 68/68 (100.0%) |
| Attacks flagged | 68/68 (100.0%) |
| **Benign blocked** | 0/41 (0.0%) |
| Benign flagged | 7/41 (17.1%) |

## Per technique (attacks)

| Technique | Blocked | Flagged |
| --- | --- | --- |
| combined_obfuscation | 5/5 (100%) | 5/5 (100%) |
| critical_file | 4/4 (100%) | 4/4 (100%) |
| disk_alt_device | 9/9 (100%) | 9/9 (100%) |
| find_destructive | 3/3 (100%) | 3/3 (100%) |
| fork_bomb | 2/2 (100%) | 2/2 (100%) |
| history_wipe | 2/2 (100%) | 2/2 (100%) |
| interpreter_delete | 3/3 (100%) | 3/3 (100%) |
| perm_system_path | 4/4 (100%) | 4/4 (100%) |
| power | 4/4 (100%) | 4/4 (100%) |
| process_kill | 3/3 (100%) | 3/3 (100%) |
| remote_code | 3/3 (100%) | 3/3 (100%) |
| rm_capital_r | 1/1 (100%) | 1/1 (100%) |
| rm_flags_after_target | 1/1 (100%) | 1/1 (100%) |
| rm_flags_reordered | 1/1 (100%) | 1/1 (100%) |
| rm_long_options | 1/1 (100%) | 1/1 (100%) |
| rm_no_preserve_root | 1/1 (100%) | 1/1 (100%) |
| rm_split_flags | 1/1 (100%) | 1/1 (100%) |
| rm_target_dot | 1/1 (100%) | 1/1 (100%) |
| rm_target_double_slash | 1/1 (100%) | 1/1 (100%) |
| rm_target_glob | 1/1 (100%) | 1/1 (100%) |
| rm_target_home_braced | 1/1 (100%) | 1/1 (100%) |
| rm_target_home_quoted | 1/1 (100%) | 1/1 (100%) |
| rm_target_home_var | 1/1 (100%) | 1/1 (100%) |
| rm_target_parent_walk | 1/1 (100%) | 1/1 (100%) |
| rm_target_pwd_parent | 1/1 (100%) | 1/1 (100%) |
| rm_target_substitution | 1/1 (100%) | 1/1 (100%) |
| rm_target_system_dir | 3/3 (100%) | 3/3 (100%) |
| rm_target_tilde_glob | 1/1 (100%) | 1/1 (100%) |
| target_in_variable | 4/4 (100%) | 4/4 (100%) |
| xargs_separated | 3/3 (100%) | 3/3 (100%) |

## Attacks not blocked (0)

None.

## Benign rows flagged (7)

| ID | Verdict | Rules | Command |
| --- | --- | --- | --- |
| v2-0069 | WARN | rm_recursive | `rm -rf ./build` |
| v2-0070 | WARN | rm_recursive | `rm -rf node_modules` |
| v2-0071 | WARN | rm_recursive | `rm -rf /tmp/mydir` |
| v2-0073 | WARN | rm_recursive | `rm -r build/` |
| v2-0074 | WARN | rm_recursive | `rm -rf "$HOME/.cache/pip"` |
| v2-0077 | WARN | mkfs | `mkfs.ext4 ./disk.img` |
| v2-0082 | WARN | find_delete | `find . -name '*.o' -delete` |
