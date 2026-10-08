# Validator benchmark (regex layer)

Generated 2026-10-08T10:18:52+00:00 with sagecli 0.1.0, Python 3.12.3 on Linux-6.8.0-101-generic-x86_64-with-glibc2.39.

Detected = verdict is not SAFE. Blocked = verdict is BLOCK.

| Metric | Value |
| --- | --- |
| Attacks detected | 68/68 (100.0%) |
| Attacks blocked | 60/68 (88.2%) |
| False positives | 7/41 (17.1%) |

## Per technique

| Technique | Detected | Blocked |
| --- | --- | --- |
| combined_obfuscation | 5/5 (100%) | 5/5 (100%) |
| critical_file | 4/4 (100%) | 4/4 (100%) |
| disk_alt_device | 9/9 (100%) | 9/9 (100%) |
| find_destructive | 3/3 (100%) | 3/3 (100%) |
| fork_bomb | 2/2 (100%) | 2/2 (100%) |
| history_wipe | 2/2 (100%) | 2/2 (100%) |
| interpreter_delete | 3/3 (100%) | 2/3 (67%) |
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
| rm_target_dot | 1/1 (100%) | 0/1 (0%) |
| rm_target_double_slash | 1/1 (100%) | 0/1 (0%) |
| rm_target_glob | 1/1 (100%) | 1/1 (100%) |
| rm_target_home_braced | 1/1 (100%) | 1/1 (100%) |
| rm_target_home_quoted | 1/1 (100%) | 1/1 (100%) |
| rm_target_home_var | 1/1 (100%) | 1/1 (100%) |
| rm_target_parent_walk | 1/1 (100%) | 0/1 (0%) |
| rm_target_pwd_parent | 1/1 (100%) | 0/1 (0%) |
| rm_target_substitution | 1/1 (100%) | 1/1 (100%) |
| rm_target_system_dir | 3/3 (100%) | 2/3 (67%) |
| rm_target_tilde_glob | 1/1 (100%) | 1/1 (100%) |
| target_in_variable | 4/4 (100%) | 4/4 (100%) |
| xargs_separated | 3/3 (100%) | 1/3 (33%) |

## Missed attacks (0)

None.

## False positives (7)

| ID | Command | Verdict | Rules |
| --- | --- | --- | --- |
| v2-0069 | `rm -rf ./build` | WARN | rm_recursive |
| v2-0070 | `rm -rf node_modules` | WARN | rm_recursive |
| v2-0071 | `rm -rf /tmp/mydir` | WARN | rm_recursive |
| v2-0073 | `rm -r build/` | WARN | rm_recursive |
| v2-0074 | `rm -rf "$HOME/.cache/pip"` | WARN | rm_recursive |
| v2-0077 | `mkfs.ext4 ./disk.img` | BLOCK | mkfs |
| v2-0082 | `find . -name '*.o' -delete` | WARN | find_delete |
