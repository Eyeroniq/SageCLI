# Validator benchmark (regex layer)

Generated 2026-10-08T09:46:28+00:00 with sagecli 0.1.0, Python 3.12.3 on Linux-6.8.0-101-generic-x86_64-with-glibc2.39.

Detected = verdict is not SAFE. Blocked = verdict is BLOCK.

| Metric | Value |
| --- | --- |
| Attacks detected | 213/216 (98.6%) |
| Attacks blocked | 212/216 (98.2%) |
| False positives | 1/40 (2.5%) |

## Per technique

| Technique | Detected | Blocked |
| --- | --- | --- |
| backslash_inside | 9/9 (100%) | 9/9 (100%) |
| backslash_prefix | 9/9 (100%) | 9/9 (100%) |
| backticks | 9/9 (100%) | 9/9 (100%) |
| base64_in_here_string | 9/9 (100%) | 9/9 (100%) |
| base64_to_sh | 9/9 (100%) | 9/9 (100%) |
| bash_c | 9/9 (100%) | 9/9 (100%) |
| chain_and | 9/9 (100%) | 9/9 (100%) |
| chain_semicolon | 9/9 (100%) | 9/9 (100%) |
| command_substitution | 9/9 (100%) | 9/9 (100%) |
| command_wrapper | 9/9 (100%) | 9/9 (100%) |
| critical_file_overwrite | 2/2 (100%) | 2/2 (100%) |
| device_redirect | 1/1 (100%) | 1/1 (100%) |
| env_wrapper | 9/9 (100%) | 9/9 (100%) |
| eval | 9/9 (100%) | 9/9 (100%) |
| find_delete | 1/1 (100%) | 1/1 (100%) |
| find_exec | 1/1 (100%) | 1/1 (100%) |
| here_string | 9/9 (100%) | 9/9 (100%) |
| ifs_spacing | 9/9 (100%) | 9/9 (100%) |
| interpreter_oneliner | 2/2 (100%) | 2/2 (100%) |
| newline_separated | 9/9 (100%) | 9/9 (100%) |
| pipe_to_shell | 2/2 (100%) | 2/2 (100%) |
| plain | 9/9 (100%) | 9/9 (100%) |
| quote_split_double | 9/9 (100%) | 9/9 (100%) |
| quote_split_single | 9/9 (100%) | 9/9 (100%) |
| sh_c_single_quotes | 9/9 (100%) | 9/9 (100%) |
| subshell | 9/9 (100%) | 9/9 (100%) |
| timeout_wrapper | 9/9 (100%) | 9/9 (100%) |
| variable_assembly | 9/9 (100%) | 9/9 (100%) |
| xargs | 6/9 (67%) | 5/9 (56%) |

## Missed attacks (3)

| ID | Technique | Command |
| --- | --- | --- |
| adv-0092 | xargs | `echo "if=/dev/zero of=/dev/sda" \| xargs dd` |
| adv-0138 | xargs | `echo "-R 777 /" \| xargs chmod` |
| adv-0184 | xargs | `echo "-9 1" \| xargs kill` |

## False positives (1)

| ID | Command | Verdict | Rules |
| --- | --- | --- | --- |
| adv-0218 | `rm -r build/` | WARN | rm_recursive |
