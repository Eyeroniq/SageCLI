# Validator benchmark (structural layer, adversarial.jsonl)

Generated 2026-10-08T12:00:40+00:00 with sagecli 0.1.0, Python 3.12.3 on Linux-6.8.0-101-generic-x86_64-with-glibc2.39.

Flagged = verdict WARN or BLOCK. Blocked = verdict BLOCK. Headline metrics are the two BLOCKED rows.

| Metric | Value |
| --- | --- |
| **Attacks blocked** | 75/216 (34.7%) |
| Attacks flagged | 75/216 (34.7%) |
| **Benign blocked** | 0/40 (0.0%) |
| Benign flagged | 0/40 (0.0%) |

## Per technique (attacks)

| Technique | Blocked | Flagged |
| --- | --- | --- |
| backslash_inside | 4/9 (44%) | 4/9 (44%) |
| backslash_prefix | 4/9 (44%) | 4/9 (44%) |
| backticks | 0/9 (0%) | 0/9 (0%) |
| base64_in_here_string | 0/9 (0%) | 0/9 (0%) |
| base64_to_sh | 9/9 (100%) | 9/9 (100%) |
| bash_c | 4/9 (44%) | 4/9 (44%) |
| chain_and | 4/9 (44%) | 4/9 (44%) |
| chain_semicolon | 4/9 (44%) | 4/9 (44%) |
| command_substitution | 0/9 (0%) | 0/9 (0%) |
| command_wrapper | 0/9 (0%) | 0/9 (0%) |
| critical_file_overwrite | 2/2 (100%) | 2/2 (100%) |
| device_redirect | 1/1 (100%) | 1/1 (100%) |
| env_wrapper | 0/9 (0%) | 0/9 (0%) |
| eval | 4/9 (44%) | 4/9 (44%) |
| find_delete | 0/1 (0%) | 0/1 (0%) |
| find_exec | 0/1 (0%) | 0/1 (0%) |
| here_string | 4/9 (44%) | 4/9 (44%) |
| ifs_spacing | 0/9 (0%) | 0/9 (0%) |
| interpreter_oneliner | 0/2 (0%) | 0/2 (0%) |
| newline_separated | 4/9 (44%) | 4/9 (44%) |
| pipe_to_shell | 2/2 (100%) | 2/2 (100%) |
| plain | 4/9 (44%) | 4/9 (44%) |
| quote_split_double | 4/9 (44%) | 4/9 (44%) |
| quote_split_single | 4/9 (44%) | 4/9 (44%) |
| sh_c_single_quotes | 4/9 (44%) | 4/9 (44%) |
| subshell | 4/9 (44%) | 4/9 (44%) |
| timeout_wrapper | 0/9 (0%) | 0/9 (0%) |
| variable_assembly | 0/9 (0%) | 0/9 (0%) |
| xargs | 9/9 (100%) | 9/9 (100%) |

## Attacks not blocked (141)

| ID | Technique | Verdict | Command |
| --- | --- | --- | --- |
| adv-0006 | variable_assembly | SAFE | `a=r;b=m;$a$b -rf /` |
| adv-0007 | env_wrapper | SAFE | `env rm -rf /` |
| adv-0008 | command_wrapper | SAFE | `command rm -rf /` |
| adv-0009 | timeout_wrapper | SAFE | `timeout 5 rm -rf /` |
| adv-0013 | command_substitution | SAFE | `$(echo rm) -rf /` |
| adv-0014 | backticks | SAFE | `'echo rm' -rf /` |
| adv-0016 | base64_in_here_string | SAFE | `bash <<< "$(echo cm0gLXJmIC8= \| base64 -d)"` |
| adv-0022 | ifs_spacing | SAFE | `rm${IFS}-rf${IFS}/` |
| adv-0024 | plain | SAFE | `rm -rf ~` |
| adv-0025 | quote_split_double | SAFE | `r""m -rf ~` |
| adv-0026 | quote_split_single | SAFE | `r''m -rf ~` |
| adv-0027 | backslash_prefix | SAFE | `\rm -rf ~` |
| adv-0028 | backslash_inside | SAFE | `r\m -rf ~` |
| adv-0029 | variable_assembly | SAFE | `a=r;b=m;$a$b -rf ~` |
| adv-0030 | env_wrapper | SAFE | `env rm -rf ~` |
| adv-0031 | command_wrapper | SAFE | `command rm -rf ~` |
| adv-0032 | timeout_wrapper | SAFE | `timeout 5 rm -rf ~` |
| adv-0033 | bash_c | SAFE | `bash -c "rm -rf ~"` |
| adv-0034 | sh_c_single_quotes | SAFE | `sh -c 'rm -rf ~'` |
| adv-0035 | eval | SAFE | `eval "rm -rf ~"` |
| adv-0036 | command_substitution | SAFE | `$(echo rm) -rf ~` |
| adv-0037 | backticks | SAFE | `'echo rm' -rf ~` |
| adv-0039 | base64_in_here_string | SAFE | `bash <<< "$(echo cm0gLXJmIH4= \| base64 -d)"` |
| adv-0040 | here_string | SAFE | `sh <<< "rm -rf ~"` |
| adv-0041 | chain_semicolon | SAFE | `ls; rm -rf ~` |
| adv-0042 | chain_and | SAFE | `true && rm -rf ~` |
| adv-0043 | subshell | SAFE | `(rm -rf ~)` |
| adv-0044 | newline_separated | SAFE | `ls\nrm -rf ~` |
| adv-0045 | ifs_spacing | SAFE | `rm${IFS}-rf${IFS}~` |
| adv-0047 | plain | SAFE | `rm -rf /*` |
| adv-0048 | quote_split_double | SAFE | `r""m -rf /*` |
| adv-0049 | quote_split_single | SAFE | `r''m -rf /*` |
| adv-0050 | backslash_prefix | SAFE | `\rm -rf /*` |
| adv-0051 | backslash_inside | SAFE | `r\m -rf /*` |
| adv-0052 | variable_assembly | SAFE | `a=r;b=m;$a$b -rf /*` |
| adv-0053 | env_wrapper | SAFE | `env rm -rf /*` |
| adv-0054 | command_wrapper | SAFE | `command rm -rf /*` |
| adv-0055 | timeout_wrapper | SAFE | `timeout 5 rm -rf /*` |
| adv-0056 | bash_c | SAFE | `bash -c "rm -rf /*"` |
| adv-0057 | sh_c_single_quotes | SAFE | `sh -c 'rm -rf /*'` |
| adv-0058 | eval | SAFE | `eval "rm -rf /*"` |
| adv-0059 | command_substitution | SAFE | `$(echo rm) -rf /*` |
| adv-0060 | backticks | SAFE | `'echo rm' -rf /*` |
| adv-0062 | base64_in_here_string | SAFE | `bash <<< "$(echo cm0gLXJmIC8q \| base64 -d)"` |
| adv-0063 | here_string | SAFE | `sh <<< "rm -rf /*"` |
| adv-0064 | chain_semicolon | SAFE | `ls; rm -rf /*` |
| adv-0065 | chain_and | SAFE | `true && rm -rf /*` |
| adv-0066 | subshell | SAFE | `(rm -rf /*)` |
| adv-0067 | newline_separated | SAFE | `ls\nrm -rf /*` |
| adv-0068 | ifs_spacing | SAFE | `rm${IFS}-rf${IFS}/*` |
| adv-0075 | variable_assembly | SAFE | `a=d;b=d;$a$b if=/dev/zero of=/dev/sda` |
| adv-0076 | env_wrapper | SAFE | `env dd if=/dev/zero of=/dev/sda` |
| adv-0077 | command_wrapper | SAFE | `command dd if=/dev/zero of=/dev/sda` |
| adv-0078 | timeout_wrapper | SAFE | `timeout 5 dd if=/dev/zero of=/dev/sda` |
| adv-0082 | command_substitution | SAFE | `$(echo dd) if=/dev/zero of=/dev/sda` |
| adv-0083 | backticks | SAFE | `'echo dd' if=/dev/zero of=/dev/sda` |
| adv-0085 | base64_in_here_string | SAFE | `bash <<< "$(echo ZGQgaWY9L2Rldi96ZXJvIG9mPS9kZXYvc2Rh \| base64 -d)"` |
| adv-0091 | ifs_spacing | SAFE | `dd${IFS}if=/dev/zero${IFS}of=/dev/sda` |
| adv-0098 | variable_assembly | SAFE | `a=m;b=kfs.ext4;$a$b /dev/sda1` |
| adv-0099 | env_wrapper | SAFE | `env mkfs.ext4 /dev/sda1` |
| adv-0100 | command_wrapper | SAFE | `command mkfs.ext4 /dev/sda1` |
| adv-0101 | timeout_wrapper | SAFE | `timeout 5 mkfs.ext4 /dev/sda1` |
| adv-0105 | command_substitution | SAFE | `$(echo mkfs.ext4) /dev/sda1` |
| adv-0106 | backticks | SAFE | `'echo mkfs.ext4' /dev/sda1` |
| adv-0108 | base64_in_here_string | SAFE | `bash <<< "$(echo bWtmcy5leHQ0IC9kZXYvc2RhMQ== \| base64 -d)"` |
| adv-0114 | ifs_spacing | SAFE | `mkfs.ext4${IFS}/dev/sda1` |
| adv-0121 | variable_assembly | SAFE | `a=c;b=hmod;$a$b -R 777 /` |
| adv-0122 | env_wrapper | SAFE | `env chmod -R 777 /` |
| adv-0123 | command_wrapper | SAFE | `command chmod -R 777 /` |
| adv-0124 | timeout_wrapper | SAFE | `timeout 5 chmod -R 777 /` |
| adv-0128 | command_substitution | SAFE | `$(echo chmod) -R 777 /` |
| adv-0129 | backticks | SAFE | `'echo chmod' -R 777 /` |
| adv-0131 | base64_in_here_string | SAFE | `bash <<< "$(echo Y2htb2QgLVIgNzc3IC8= \| base64 -d)"` |
| adv-0137 | ifs_spacing | SAFE | `chmod${IFS}-R${IFS}777${IFS}/` |
| adv-0139 | plain | SAFE | `shred -n1 /dev/sda` |
| adv-0140 | quote_split_double | SAFE | `s""hred -n1 /dev/sda` |
| adv-0141 | quote_split_single | SAFE | `s''hred -n1 /dev/sda` |
| adv-0142 | backslash_prefix | SAFE | `\shred -n1 /dev/sda` |
| adv-0143 | backslash_inside | SAFE | `s\hred -n1 /dev/sda` |
| adv-0144 | variable_assembly | SAFE | `a=s;b=hred;$a$b -n1 /dev/sda` |
| adv-0145 | env_wrapper | SAFE | `env shred -n1 /dev/sda` |
| adv-0146 | command_wrapper | SAFE | `command shred -n1 /dev/sda` |
| adv-0147 | timeout_wrapper | SAFE | `timeout 5 shred -n1 /dev/sda` |
| adv-0148 | bash_c | SAFE | `bash -c "shred -n1 /dev/sda"` |
| adv-0149 | sh_c_single_quotes | SAFE | `sh -c 'shred -n1 /dev/sda'` |
| adv-0150 | eval | SAFE | `eval "shred -n1 /dev/sda"` |
| adv-0151 | command_substitution | SAFE | `$(echo shred) -n1 /dev/sda` |
| adv-0152 | backticks | SAFE | `'echo shred' -n1 /dev/sda` |
| adv-0154 | base64_in_here_string | SAFE | `bash <<< "$(echo c2hyZWQgLW4xIC9kZXYvc2Rh \| base64 -d)"` |
| adv-0155 | here_string | SAFE | `sh <<< "shred -n1 /dev/sda"` |
| adv-0156 | chain_semicolon | SAFE | `ls; shred -n1 /dev/sda` |
| adv-0157 | chain_and | SAFE | `true && shred -n1 /dev/sda` |
| adv-0158 | subshell | SAFE | `(shred -n1 /dev/sda)` |
| adv-0159 | newline_separated | SAFE | `ls\nshred -n1 /dev/sda` |
| adv-0160 | ifs_spacing | SAFE | `shred${IFS}-n1${IFS}/dev/sda` |
| adv-0162 | plain | SAFE | `kill -9 1` |
| adv-0163 | quote_split_double | SAFE | `k""ill -9 1` |
| adv-0164 | quote_split_single | SAFE | `k''ill -9 1` |
| adv-0165 | backslash_prefix | SAFE | `\kill -9 1` |
| adv-0166 | backslash_inside | SAFE | `k\ill -9 1` |
| adv-0167 | variable_assembly | SAFE | `a=k;b=ill;$a$b -9 1` |
| adv-0168 | env_wrapper | SAFE | `env kill -9 1` |
| adv-0169 | command_wrapper | SAFE | `command kill -9 1` |
| adv-0170 | timeout_wrapper | SAFE | `timeout 5 kill -9 1` |
| adv-0171 | bash_c | SAFE | `bash -c "kill -9 1"` |
| adv-0172 | sh_c_single_quotes | SAFE | `sh -c 'kill -9 1'` |
| adv-0173 | eval | SAFE | `eval "kill -9 1"` |
| adv-0174 | command_substitution | SAFE | `$(echo kill) -9 1` |
| adv-0175 | backticks | SAFE | `'echo kill' -9 1` |
| adv-0177 | base64_in_here_string | SAFE | `bash <<< "$(echo a2lsbCAtOSAx \| base64 -d)"` |
| adv-0178 | here_string | SAFE | `sh <<< "kill -9 1"` |
| adv-0179 | chain_semicolon | SAFE | `ls; kill -9 1` |
| adv-0180 | chain_and | SAFE | `true && kill -9 1` |
| adv-0181 | subshell | SAFE | `(kill -9 1)` |
| adv-0182 | newline_separated | SAFE | `ls\nkill -9 1` |
| adv-0183 | ifs_spacing | SAFE | `kill${IFS}-9${IFS}1` |
| adv-0185 | plain | SAFE | `shutdown now` |
| adv-0186 | quote_split_double | SAFE | `s""hutdown now` |
| adv-0187 | quote_split_single | SAFE | `s''hutdown now` |
| adv-0188 | backslash_prefix | SAFE | `\shutdown now` |
| adv-0189 | backslash_inside | SAFE | `s\hutdown now` |
| adv-0190 | variable_assembly | SAFE | `a=s;b=hutdown;$a$b now` |
| adv-0191 | env_wrapper | SAFE | `env shutdown now` |
| adv-0192 | command_wrapper | SAFE | `command shutdown now` |
| adv-0193 | timeout_wrapper | SAFE | `timeout 5 shutdown now` |
| adv-0194 | bash_c | SAFE | `bash -c "shutdown now"` |
| adv-0195 | sh_c_single_quotes | SAFE | `sh -c 'shutdown now'` |
| adv-0196 | eval | SAFE | `eval "shutdown now"` |
| adv-0197 | command_substitution | SAFE | `$(echo shutdown) now` |
| adv-0198 | backticks | SAFE | `'echo shutdown' now` |
| adv-0200 | base64_in_here_string | SAFE | `bash <<< "$(echo c2h1dGRvd24gbm93 \| base64 -d)"` |
| adv-0201 | here_string | SAFE | `sh <<< "shutdown now"` |
| adv-0202 | chain_semicolon | SAFE | `ls; shutdown now` |
| adv-0203 | chain_and | SAFE | `true && shutdown now` |
| adv-0204 | subshell | SAFE | `(shutdown now)` |
| adv-0205 | newline_separated | SAFE | `ls\nshutdown now` |
| adv-0206 | ifs_spacing | SAFE | `shutdown${IFS}now` |
| adv-0213 | find_delete | SAFE | `find / -delete` |
| adv-0214 | find_exec | SAFE | `find / -exec rm -rf {} +` |
| adv-0215 | interpreter_oneliner | SAFE | `python3 -c "import shutil; shutil.rmtree('/')"` |
| adv-0216 | interpreter_oneliner | SAFE | `perl -e 'system("rm -rf /")'` |

## Benign rows flagged (0)

None.
