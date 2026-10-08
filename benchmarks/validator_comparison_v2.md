# Validator before / after

Baseline: `regex` layer. After: `both` layer. Data set: `adversarial_v2.jsonl`.

| Metric | Before | After |
| --- | --- | --- |
| Attacks blocked | 60/68 (88.2%) | 68/68 (100.0%) |
| Attacks flagged | 68/68 (100.0%) | 68/68 (100.0%) |
| Benign blocked | 1/41 | 0/41 |
| Benign flagged | 7/41 | 7/41 |

## Per technique (attack block rate)

| Technique | Before | After |
| --- | --- | --- |
| combined_obfuscation | 5/5 (100.0%) | 5/5 (100.0%) |
| critical_file | 4/4 (100.0%) | 4/4 (100.0%) |
| disk_alt_device | 9/9 (100.0%) | 9/9 (100.0%) |
| find_destructive | 3/3 (100.0%) | 3/3 (100.0%) |
| fork_bomb | 2/2 (100.0%) | 2/2 (100.0%) |
| history_wipe | 2/2 (100.0%) | 2/2 (100.0%) |
| interpreter_delete | 2/3 (66.7%) | 3/3 (100.0%) |
| perm_system_path | 4/4 (100.0%) | 4/4 (100.0%) |
| power | 4/4 (100.0%) | 4/4 (100.0%) |
| process_kill | 3/3 (100.0%) | 3/3 (100.0%) |
| remote_code | 3/3 (100.0%) | 3/3 (100.0%) |
| rm_capital_r | 1/1 (100.0%) | 1/1 (100.0%) |
| rm_flags_after_target | 1/1 (100.0%) | 1/1 (100.0%) |
| rm_flags_reordered | 1/1 (100.0%) | 1/1 (100.0%) |
| rm_long_options | 1/1 (100.0%) | 1/1 (100.0%) |
| rm_no_preserve_root | 1/1 (100.0%) | 1/1 (100.0%) |
| rm_split_flags | 1/1 (100.0%) | 1/1 (100.0%) |
| rm_target_dot | 0/1 (0.0%) | 1/1 (100.0%) |
| rm_target_double_slash | 0/1 (0.0%) | 1/1 (100.0%) |
| rm_target_glob | 1/1 (100.0%) | 1/1 (100.0%) |
| rm_target_home_braced | 1/1 (100.0%) | 1/1 (100.0%) |
| rm_target_home_quoted | 1/1 (100.0%) | 1/1 (100.0%) |
| rm_target_home_var | 1/1 (100.0%) | 1/1 (100.0%) |
| rm_target_parent_walk | 0/1 (0.0%) | 1/1 (100.0%) |
| rm_target_pwd_parent | 0/1 (0.0%) | 1/1 (100.0%) |
| rm_target_substitution | 1/1 (100.0%) | 1/1 (100.0%) |
| rm_target_system_dir | 2/3 (66.7%) | 3/3 (100.0%) |
| rm_target_tilde_glob | 1/1 (100.0%) | 1/1 (100.0%) |
| target_in_variable | 4/4 (100.0%) | 4/4 (100.0%) |
| xargs_separated | 1/3 (33.3%) | 3/3 (100.0%) |

## Attacks still not blocked after (0)

None.
