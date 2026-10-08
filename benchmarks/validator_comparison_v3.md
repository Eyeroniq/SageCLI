# Validator before / after

Baseline: `regex` layer. After: `both` layer. Data set: `adversarial_v3.jsonl`.

| Metric | Before | After |
| --- | --- | --- |
| Attacks blocked | 52/62 (83.9%) | 55/62 (88.7%) |
| Attacks flagged | 59/62 (95.2%) | 59/62 (95.2%) |
| Benign blocked | 3/47 | 1/47 |
| Benign flagged | 10/47 | 10/47 |

## Per technique (attack block rate)

| Technique | Before | After |
| --- | --- | --- |
| critical_file_other | 6/6 (100.0%) | 6/6 (100.0%) |
| device_overwrite_other | 5/5 (100.0%) | 5/5 (100.0%) |
| find_other | 3/3 (100.0%) | 3/3 (100.0%) |
| fs_tools_other | 4/6 (66.7%) | 4/6 (66.7%) |
| interpreter_other | 3/4 (75.0%) | 3/4 (75.0%) |
| kill_other | 2/3 (66.7%) | 2/3 (66.7%) |
| move_to_void | 0/2 (0.0%) | 0/2 (0.0%) |
| perm_other | 2/3 (66.7%) | 2/3 (66.7%) |
| power_other | 7/7 (100.0%) | 7/7 (100.0%) |
| remote_code_other | 6/6 (100.0%) | 6/6 (100.0%) |
| rm_after_cd | 2/2 (100.0%) | 2/2 (100.0%) |
| rm_other_system_dirs | 6/6 (100.0%) | 6/6 (100.0%) |
| rm_root_spelling | 4/7 (57.1%) | 7/7 (100.0%) |
| rm_via_sudo | 2/2 (100.0%) | 2/2 (100.0%) |

## Attacks still not blocked after (7)

| ID | Technique | Verdict | Command |
| --- | --- | --- | --- |
| v3-0026 | fs_tools_other | WARN | `parted -s /dev/sda mklabel gpt` |
| v3-0027 | fs_tools_other | WARN | `sgdisk --zap-all /dev/sda` |
| v3-0035 | move_to_void | SAFE | `mv /* /dev/null` |
| v3-0036 | move_to_void | SAFE | `mv ~ /dev/null` |
| v3-0039 | perm_other | SAFE | `chown -R nobody /home` |
| v3-0049 | interpreter_other | WARN | `perl -e 'unlink glob("/etc/*")'` |
| v3-0062 | kill_other | WARN | `pkill -9 -f .` |
