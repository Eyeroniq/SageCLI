# Validator benchmark (both layer, adversarial.jsonl)

Generated 2026-10-08T12:00:41+00:00 with sagecli 0.1.0, Python 3.12.3 on Linux-6.8.0-101-generic-x86_64-with-glibc2.39.

Flagged = verdict WARN or BLOCK. Blocked = verdict BLOCK. Headline metrics are the two BLOCKED rows.

| Metric | Value |
| --- | --- |
| **Attacks blocked** | 216/216 (100.0%) |
| Attacks flagged | 216/216 (100.0%) |
| **Benign blocked** | 0/40 (0.0%) |
| Benign flagged | 1/40 (2.5%) |

## Per technique (attacks)

| Technique | Blocked | Flagged |
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
| xargs | 9/9 (100%) | 9/9 (100%) |

## Attacks not blocked (0)

None.

## Benign rows flagged (1)

| ID | Verdict | Rules | Command |
| --- | --- | --- | --- |
| adv-0218 | WARN | rm_recursive | `rm -r build/` |
