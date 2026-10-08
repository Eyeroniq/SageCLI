"""Safety layer (regex version): classify a Bash command as SAFE, WARN or BLOCK.

Pipeline
--------
1. Whole-command checks on the raw text (fork bombs, history disabling).
2. Normalisation: join line continuations, replace `$IFS` tricks with spaces,
   collect simple `NAME=value` assignments and expand `$NAME` / `${NAME}`,
   inline `$(echo word)` substitutions.
3. Splitting: a quote-aware scanner splits on `;`, `&&`, `||`, `|`, `&` and
   newlines, and lifts the bodies of `$(...)`, backticks, `<(...)` and `>(...)`
   out as separate commands. Every resulting segment is validated.
4. Per segment: dequote with `shlex` (removes `r""m`, `r''m`, `\\rm` tricks),
   strip structural keywords, assignments and wrappers (`sudo`, `env`,
   `command`, `xargs`, ...), expand `{a,b,c}` brace lists at command position,
   reduce the command to its basename, and collapse whitespace. Arguments that
   were quoted strings containing spaces are masked (so `echo "rm -rf /"` is not
   flagged), but their contents are re-validated where the shell would execute
   them (`bash -c`, `eval`, here-strings to a shell, `find -exec sh -c`,
   strings echoed into a shell, interpreter `system()` calls).
5. Named regex rules run on each normalised segment; pipeline rules look at
   what feeds a shell (`curl | sh`, `base64 -d | bash`).

The highest risk found wins. This is a heuristic: it is a guard rail against
mistakes and casual obfuscation, not a sandbox.
"""

from __future__ import annotations

import posixpath
import re
import shlex
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import IntEnum

from sagecli import shell_parser


class Risk(IntEnum):
    SAFE = 0
    WARN = 1
    BLOCK = 2


@dataclass(frozen=True)
class Rule:
    name: str
    category: str
    risk: Risk
    pattern: re.Pattern[str]
    reason: str
    field: str = "text"  # "text": masked segment; "full": segment with quoted strings kept


@dataclass(frozen=True)
class Match:
    rule: str
    category: str
    risk: Risk
    reason: str
    segment: str


@dataclass(frozen=True)
class ValidationResult:
    risk: Risk
    rules: tuple[str, ...] = ()
    reason: str = "No risky pattern found."
    segments: tuple[str, ...] = ()
    matches: tuple[Match, ...] = field(default=(), repr=False)

    @property
    def blocked(self) -> bool:
        return self.risk is Risk.BLOCK


# ---------------------------------------------------------------------------
# Shared regex fragments
# ---------------------------------------------------------------------------

_SYS_DIRS = (
    "bin|boot|dev|etc|home|lib|lib32|lib64|libx32|media|mnt|opt|proc|root|run|"
    "sbin|srv|sys|usr|var"
)
# Targets whose recursive deletion is catastrophic.
DANGER_PATH = (
    rf"(?:/\*?|~/?\*?|\$HOME/?\*?|\$\{{HOME\}}/?\*?|\*|\.{{1,2}}/?\*?|/(?:{_SYS_DIRS})/?\*?)"
)
# Starting points for `find ... -delete` that reach system files or all of home.
FIND_ROOT = rf"(?:/\*?|~/?|\$HOME/?|\$\{{HOME\}}/?|/(?:{_SYS_DIRS})/?)"
# Catastrophic sources for `mv` (relocating these destroys the layout). Unlike
# DANGER_PATH this excludes a bare `*`, `.` and `..` so `mv * dir/` stays SAFE.
MV_DANGER = rf"(?:/\*?|~/?\*?|\$HOME/?\*?|\$\{{HOME\}}/?\*?|/(?:{_SYS_DIRS})/?\*?)"
# System locations for chmod/chown -R. Bare top-level dirs (incl. /home, /opt, ...)
# match only themselves; the second group also matches subpaths under /usr etc.
SYSTEM_PATH = (
    r"(?:/\*?|~/?|\$HOME/?"
    r"|/(?:dev|home|media|mnt|opt|proc|root|run|srv|sys|var)/?"
    r"|/(?:bin|boot|etc|lib\w*|sbin|usr)(?:/\S*)?)"
)
END = r"(?=\s|$)"
RM_RECURSIVE = r"(?:-[a-zA-Z]*[rR][a-zA-Z]*|--recursive)"
CHMOD_RECURSIVE = r"(?:-[a-zA-Z]*R[a-zA-Z]*|--recursive)"
BLOCK_DEVICE = r"/dev/(?:sd|hd|vd|xvd|nvme|mmcblk|dm-|mapper/|disk/|md\d|loop)\S*"
CRITICAL_FILE = (
    r"(?:/etc/(?:passwd|shadow|group|gshadow|sudoers(?:\.d/\S*)?|fstab|crontab|hosts|"
    r"ld\.so\.preload|pam\.d/\S*|ssh/sshd_config|profile|bash\.bashrc)|/boot/\S*|/boot|"
    r"/(?:s?bin|usr/s?bin|usr/lib\w*|lib\w*)/\S+|/proc/sysrq-trigger)"
)
REDIRECT = r"(?:^|\s)(?:\d|&)?>>?&?\|?\s*"
HISTORY_OR_LOG = (
    r"(?:\S*\.(?:bash|zsh|sh|python|mysql|psql|lesshst)_history|\S*/?\.history|/var/log\S*)"
)

SHELLS = frozenset({"sh", "bash", "dash", "zsh", "ksh", "mksh", "fish", "csh", "tcsh", "ash",
                    "busybox"})
INTERPRETERS = frozenset({"python", "python2", "python3", "perl", "ruby", "node", "nodejs",
                          "php", "lua", "tclsh"})
DOWNLOADERS = frozenset({"curl", "wget", "fetch", "nc", "ncat", "netcat", "socat", "aria2c"})
DECODER_RE = re.compile(
    r"\bbase(?:32|64)\s+(?:-\w*\s+)*(?:-d|--decode|-D)\b|\bxxd\s+(?:-\w+\s+)*-r|"
    r"\bprintf\b.*\\(?:x[0-9a-fA-F]{2}|[0-7]{3})|\becho\s+-\w*e\w*\b.*\\(?:x[0-9a-fA-F]|[0-7]{3})|"
    r"(?<![\w-])rev(?![\w-])|\bopenssl\b.*\s-d\b|\b(?:gunzip|zcat|uudecode|bunzip2|xz\s+-d)\b|\btr\b.*a-z"
)
DOWNLOAD_RE = re.compile(r"^(?:curl|wget|fetch|nc|ncat|netcat|socat|aria2c)\b")


def _r(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern)


# ---------------------------------------------------------------------------
# Rules applied to each normalised segment
# ---------------------------------------------------------------------------

B, W = Risk.BLOCK, Risk.WARN

SEGMENT_RULES: tuple[Rule, ...] = (
    # Recursive / forced deletion -------------------------------------------------
    Rule("rm_recursive_dangerous_target", "recursive_delete", B,
         _r(rf"^rm\b(?=.*\s{RM_RECURSIVE}{END})(?=.*\s{DANGER_PATH}{END})"),
         "Recursive deletion of /, a system directory, the home directory or everything (*)."),
    Rule("rm_no_preserve_root", "recursive_delete", B, _r(r"^rm\b.*\s--no-preserve-root\b"),
         "Disables rm's protection against deleting /."),
    Rule("rm_recursive", "recursive_delete", W, _r(rf"^rm\b(?=.*\s{RM_RECURSIVE}{END})"),
         "Recursive deletion."),
    Rule("find_delete_dangerous_root", "recursive_delete", B,
         _r(rf"^find\s+(?:-[HLP]\s+)*{FIND_ROOT}(?=\s)(?=.*\s(?:-delete{END}|"
            r"-exec(?:dir)?\s+(?:rm|shred|unlink)\b))"),
         "find deleting files under /, a system directory or home."),
    Rule("find_delete", "recursive_delete", W,
         _r(r"^find\b.*\s(?:-delete|-exec(?:dir)?\s+(?:rm|shred|unlink)|-ok\s+rm)\b"),
         "find deleting the files it matches."),
    Rule("destructive_move", "recursive_delete", B,
         _r(rf"^mv\b(?=.*\s{MV_DANGER}{END})"),
         "Moves the whole filesystem, home or a system directory, destroying its layout."),
    Rule("obfuscated_command_destructive", "obfuscation", B,
         _r(rf"^(?:\$\S*|\S*[?*]\S*|\S+\[\S*)\s(?=.*{RM_RECURSIVE}{END})(?=.*\s{DANGER_PATH}{END})"),
         "Hidden or wildcard command name with recursive flags on a dangerous path."),
    Rule("dynamic_command_name", "obfuscation", W, _r(r"^(?:\$\S*|\S*[?*]\S*|\S+\[\S*)(?:\s|$)"),
         "The command name is computed at run time (variable, substitution or wildcard)."),
    # Disk and filesystem destruction --------------------------------------------
    Rule("dd_to_device", "disk_destruction", B,
         _r(r"^dd\b.*\bof=/dev/(?!null\b|zero\b|stdout\b|stderr\b|tty\b)"),
         "dd writing directly to a device."),
    Rule("mkfs_device", "disk_destruction", B,
         _r(rf"^(?:mkfs(?:\.\w+)?|mke2fs|mkswap|mkdosfs)\b.*\s{BLOCK_DEVICE}"),
         "Creates a filesystem on a block device, erasing it."),
    Rule("mkfs", "disk_destruction", W, _r(r"^(?:mkfs(?:\.\w+)?|mke2fs|mkswap|mkdosfs)(?:\s|$)"),
         "Creates a filesystem, erasing the target."),
    Rule("wipefs", "disk_destruction", B, _r(r"^(?:wipefs|blkdiscard)(?:\s|$)"),
         "Wipes filesystem signatures or discards a whole device."),
    Rule("shred_device", "disk_destruction", B, _r(r"^shred\b.*\s/dev/"),
         "Overwrites a device with random data."),
    Rule("shred", "disk_destruction", W, _r(r"^shred(?:\s|$)"),
         "Irrecoverably overwrites files."),
    Rule("redirect_to_block_device", "disk_destruction", B, _r(REDIRECT + BLOCK_DEVICE),
         "Redirects output onto a raw disk device."),
    Rule("write_to_block_device", "disk_destruction", B,
         _r(rf"^(?:tee\b.*\s{BLOCK_DEVICE}|(?:cp|mv)\b.*\s{BLOCK_DEVICE}$)"),
         "Writes onto a raw disk device."),
    Rule("partition_tool_device", "disk_destruction", B,
         _r(rf"^(?:fdisk|sfdisk|cfdisk|parted|gdisk|sgdisk|partprobe)\b(?!.*\s-l\b).*"
            rf"\s{BLOCK_DEVICE}"),
         "Edits the partition table of a block device."),
    Rule("partition_tool", "disk_destruction", W,
         _r(r"^(?:fdisk|sfdisk|cfdisk|parted|gdisk|sgdisk)\b(?!.*\s-l\b)"),
         "Edits a partition table."),
    # Permissions on system paths --------------------------------------------------
    Rule("recursive_perm_system", "permissions", B,
         _r(rf"^(?:chmod|chown|chgrp)\b(?=.*\s{CHMOD_RECURSIVE}{END})(?=.*\s{SYSTEM_PATH}{END})"),
         "Recursive permission or ownership change on a system path."),
    Rule("perm_system_root", "permissions", W,
         _r(rf"^(?:chmod|chown|chgrp)\b.*\s(?:/|/(?:etc|bin|sbin|usr|boot|lib\w*)){END}"),
         "Permission or ownership change on a system directory."),
    # Critical files ----------------------------------------------------------------
    Rule("redirect_to_critical_file", "critical_file", B, _r(REDIRECT + CRITICAL_FILE),
         "Overwrites a critical system file."),
    Rule("modify_critical_file", "critical_file", B,
         _r(rf"^(?:tee|truncate|shred|unlink|chattr|chmod|chown|mv|rm)\b.*\s{CRITICAL_FILE}{END}|"
            rf"^sed\b.*\s-\w*i.*\s{CRITICAL_FILE}{END}|"
            rf"^(?:cp|ln|install|rsync)\b.*\s{CRITICAL_FILE}$|^dd\b.*\bof={CRITICAL_FILE}"),
         "Modifies, replaces or deletes a critical system file."),
    # Power state -------------------------------------------------------------------
    Rule("shutdown_reboot", "power", B,
         _r(r"^(?:shutdown|reboot|halt|poweroff)\b(?!.*\s--(?:help|version)\b)"),
         "Shuts down or reboots the machine."),
    Rule("systemctl_power", "power", B,
         _r(r"^systemctl\b(?!.*\s--(?:help|version)\b).*\s"
            r"(?:poweroff|reboot|halt|kexec|emergency|rescue)(?:\s|$)"),
         "Shuts down or reboots the machine."),
    Rule("init_runlevel", "power", B, _r(r"^(?:init|telinit)\s+[06](?:\s|$)"),
         "Switches to the halt or reboot runlevel."),
    # Privilege escalation --------------------------------------------------------------
    Rule("privilege_escalation", "privilege", W, _r(r"^(?:sudo|su|doas|pkexec)(?:\s|$)"),
         "Runs with root privileges."),
    # Process killing ------------------------------------------------------------------
    Rule("kill_init_or_all", "process_kill", B, _r(r"^kill\b.*\s(?:-1|1)$"),
         "Kills init (PID 1) or every process (-1)."),
    Rule("killall5", "process_kill", B, _r(r"^killall5(?:\s|$)"), "Kills every process."),
    Rule("kill_critical_process", "process_kill", B,
         _r(r"^(?:killall|pkill)\b.*\s(?:init|systemd|sshd|-u\s+root|1)$"),
         "Kills a critical system process."),
    Rule("pkill_catchall", "process_kill", B,
         _r(r"^pkill\b(?=.*\s-(?:9|KILL|SIGKILL)\b)(?=.*\s-f\b)(?=.*\s\.(?:\s|$))"),
         "Force-kills every process (a catch-all pattern matches them all)."),
    Rule("mass_kill", "process_kill", W,
         _r(r"^(?:killall(?:\s|$)|pkill\b.*\s-(?:9|KILL|SIGKILL)(?:\s|$))"),
         "Kills processes by name."),
    # History and log wiping --------------------------------------------------------------
    Rule("history_clear", "history_wipe", B, _r(r"^history\b.*\s-\w*c\w*(?:\s|$)"),
         "Clears the shell history."),
    Rule("history_disable", "history_wipe", B,
         _r(r"^(?:unset\b.*\bHISTFILE\b|set\s+\+o\s+history\b|export\s+HISTFILE=(?:/dev/null)?$"
            r"|export\s+HISTSIZE=0)"),
         "Disables shell history."),
    Rule("redirect_to_history_or_log", "history_wipe", B, _r(REDIRECT + HISTORY_OR_LOG),
         "Overwrites shell history or system logs."),
    Rule("delete_history_or_log", "history_wipe", B,
         _r(rf"^(?:rm|shred|truncate|unlink|ln)\b.*\s{HISTORY_OR_LOG}{END}"),
         "Deletes or truncates shell history or system logs."),
    Rule("journal_vacuum", "history_wipe", B, _r(r"^journalctl\b.*--(?:vacuum|rotate)"),
         "Deletes systemd journal logs."),
    # Code execution and obfuscation ---------------------------------------------------------
    Rule("eval", "obfuscation", W, _r(r"^eval(?:\s|$)"),
         "eval executes a string as code."),
    Rule("source_process_substitution", "remote_exec", W,
         _r(r"^(?:source|\.)\s+/dev/fd/"),
         "Sources code produced by another command."),
    Rule("interpreter_delete_dangerous", "interpreter", B,
         _r(r"^(?:python[\d.]*|perl|ruby|node|nodejs|php|lua)\b.*"
            r"(?:rmtree|remove|unlink|rmdir|rm_rf|rm_r|rmSync|rimraf|delete)"
            r".*['\"](?:/|~|~/|~/\*|/\*|"
            r"/(?:etc|home|usr|var|boot|bin|lib|root|opt|srv|mnt|media)(?:/[^'\"]*)?)['\"]"),
         "Interpreter one-liner deleting /, home or a system directory.", field="full"),
    Rule("interpreter_delete", "interpreter", W,
         _r(r"^(?:python[\d.]*|perl|ruby|node|nodejs|php|lua)\b.*\s-\w*[ceEr]\w*\s.*"
            r"(?:rmtree|os\.remove|os\.unlink|unlink|rmdir|rm_rf|rmSync|rimraf|File\.delete)"),
         "Interpreter one-liner deleting files.", field="full"),
    Rule("interpreter_exec", "interpreter", W,
         _r(r"^(?:python[\d.]*|perl|ruby|node|nodejs|php|lua)\b.*\s-\w*[ceEr]\w*\s.*"
            r"(?:os\.system|subprocess|popen|exec\w*\s*\(|system\s*\(|\bsystem\b|\bqx|`|"
            r"child_process|spawn)"),
         "Interpreter one-liner running shell commands.", field="full"),
)

# Rules applied to the raw command text (before splitting).
RAW_RULES: tuple[Rule, ...] = (
    Rule("fork_bomb", "fork_bomb", B,
         _r(r"([^\s(){}|;&]+)\s*\(\s*\)\s*\{[^}]*\1\s*\|\s*&?\s*\1"),
         "Fork bomb: a function that endlessly spawns copies of itself."),
    Rule("fork_bomb_loop", "fork_bomb", B,
         _r(r"\bfork\s*(?:\(\s*\))?\s*while\s+fork\b|while\s*(?:true|:|1)\s*;\s*do\s+[^;]*&\s*;?\s*done"
            r"|\bos\.fork\(\)[^\n]*while|while\s+True\s*:\s*os\.fork"),
         "Loop that spawns processes without limit."),
    Rule("history_disable_assignment", "history_wipe", B,
         _r(r"(?:^|[\s;&|])HIST(?:FILE=(?:/dev/null|\s|;|$)|SIZE=0\b|FILESIZE=0\b)"),
         "Disables shell history."),
)

ALL_RULE_NAMES: tuple[str, ...] = tuple(
    r.name for r in RAW_RULES + SEGMENT_RULES
) + ("remote_pipe_shell", "obfuscated_pipe_shell", "pipe_to_shell", "remote_code_exec",
     "obfuscated_exec", "not_in_allowlist", "could_not_parse_structure")

# Shared patterns reused by the structural layer, compiled for whole-token matching.
_SYS_DIR_SET = frozenset(_SYS_DIRS.split("|"))
_BLOCK_DEVICE_RE = re.compile(BLOCK_DEVICE)
_CRITICAL_FILE_RE = re.compile(CRITICAL_FILE)
_SYSTEM_PATH_RE = re.compile(SYSTEM_PATH + r"$")


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

_IFS_RE = re.compile(r"\$\{IFS[^}]*\}(?:\$[0-9@*])?|\$IFS(?:\$[0-9@*])?")
_VAR_RE = re.compile(r"\$\{([A-Za-z_]\w*)\}|\$([A-Za-z_]\w*)")
_ASSIGN_RE = re.compile(r"^([A-Za-z_]\w*)=(.*)$", re.DOTALL)
_SIMPLE_ECHO_RE = re.compile(
    r"^\s*(?:echo|printf)\s+(?:-n\s+)?(['\"]?)([^\s'\"$`\\;|&<>()]+)\1\s*$"
)
_PLACEHOLDER = "__SUB{}__"
_PLACEHOLDER_RE = re.compile(r"__SUB(\d+)__")
_KEYWORDS = frozenset({"if", "then", "else", "elif", "fi", "do", "done", "while", "until", "for",
                       "!", "{", "}", "(", ")", "time", "case", "esac", "in", "function"})
_WRAPPERS = frozenset({"sudo", "doas", "pkexec", "env", "command", "builtin", "exec", "nohup",
                       "nice", "ionice", "timeout", "stdbuf", "setsid", "xargs", "unbuffer",
                       "chrt", "taskset", "flock", "busybox", "time", "caffeinate", "torsocks",
                       "proxychains", "strace", "ltrace", "watch"})
_WRAPPER_VALUE_OPTS = {
    "sudo": {"-u", "-g", "-C", "-D", "-h", "-p", "-r", "-t", "-U", "--user", "--group"},
    "doas": {"-u", "-C"},
    "env": {"-u", "-C", "-S", "--unset", "--chdir"},
    "nice": {"-n", "--adjustment"},
    "ionice": {"-c", "-n", "-p", "--class", "--classdata"},
    "timeout": {"-s", "-k", "--signal", "--kill-after"},
    "xargs": {"-I", "-i", "-n", "-P", "-d", "-L", "-l", "-s", "-a", "-E", "-e",
              "--max-args", "--max-procs", "--delimiter", "--arg-file", "--replace"},
    "chrt": {"-p"},
    "taskset": {"-p", "-c"},
    "watch": {"-n", "-d", "--interval"},
    "flock": {"-w", "-E"},
    "strace": {"-e", "-o", "-p", "-s"},
}
_WRAPPER_POSITIONAL = {"timeout": 1, "chrt": 1, "taskset": 1, "flock": 1}


@dataclass
class _Ctx:
    subs: dict[int, str] = field(default_factory=dict)
    variables: dict[str, str] = field(default_factory=dict)
    matches: list[Match] = field(default_factory=list)
    segments: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    allowlist: frozenset[str] | None = None
    depth: int = 0


def _find_closing(text: str, start: int) -> int:
    """Index of the `)` closing a `(` that opened just before `start` (or len(text))."""
    depth, i, quote = 1, start, None
    while i < len(text):
        c = text[i]
        if quote:
            if c == "\\" and quote == '"':
                i += 2
                continue
            if c == quote:
                quote = None
        elif c in "'\"":
            quote = c
        elif c == "\\":
            i += 2
            continue
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return len(text)


def _find_backtick(text: str, start: int) -> int:
    i = start
    while i < len(text):
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == "`":
            return i
        i += 1
    return len(text)


def split_pipelines(text: str, subs: dict[int, str]) -> list[list[str]]:
    """Quote-aware split into pipelines (lists of stages).

    Command and process substitution bodies are stored in `subs` and replaced
    with `__SUBn__` placeholders (`$__SUBn__` for `$(...)`/backticks,
    `/dev/fd/__SUBn__` for `<(...)`/`>(...)`). A body that is a bare
    `echo word` is inlined as the word instead.
    """
    pipelines: list[list[str]] = []
    stages: list[str] = []
    buf: list[str] = []
    quote: str | None = None
    i, n = 0, len(text)

    def end_stage() -> None:
        stages.append("".join(buf))
        buf.clear()

    def end_pipeline() -> None:
        end_stage()
        kept = [s for s in stages if s.strip()]
        if kept:
            pipelines.append(kept)
        stages.clear()

    def substitute(inner: str, process: bool) -> str:
        echo = _SIMPLE_ECHO_RE.match(inner)
        if echo and not process:
            return echo.group(2)
        index = len(subs)
        subs[index] = inner
        placeholder = _PLACEHOLDER.format(index)
        return f"/dev/fd/{placeholder}" if process else f"${placeholder}"

    while i < n:
        c = text[i]
        if quote == "'":
            buf.append(c)
            if c == "'":
                quote = None
            i += 1
            continue
        if c == "\\" and i + 1 < n:
            buf.append(text[i:i + 2])
            i += 2
            continue
        if text.startswith("$((", i):
            end = _find_closing(text, i + 3)
            buf.append(text[i:end + 2])
            i = end + 2
            continue
        if text.startswith("$(", i) or (quote is None and text[i:i + 2] in ("<(", ">(")):
            end = _find_closing(text, i + 2)
            buf.append(substitute(text[i + 2:end], process=c != "$"))
            i = end + 1
            continue
        if c == "`":
            end = _find_backtick(text, i + 1)
            buf.append(substitute(text[i + 1:end], process=False))
            i = end + 1
            continue
        if quote == '"':
            buf.append(c)
            if c == '"':
                quote = None
            i += 1
            continue
        # Unquoted context.
        if c in "'\"":
            quote = c
            buf.append(c)
            i += 1
            continue
        if c == "#" and (i == 0 or text[i - 1] in " \t\n;&|("):
            while i < n and text[i] != "\n":
                i += 1
            continue
        if c in ";\n":
            end_pipeline()
            i += 1
            continue
        if text.startswith("&&", i) or text.startswith("||", i):
            end_pipeline()
            i += 2
            continue
        if c == "|":
            end_stage()
            i += 2 if text.startswith("|&", i) else 1
            continue
        if c == "&":
            prev = text[i - 1] if i else ""
            nxt = text[i + 1] if i + 1 < n else ""
            if prev in "<>" or nxt == ">":
                buf.append(c)
                i += 1
                continue
            end_pipeline()
            i += 1
            continue
        buf.append(c)
        i += 1
    end_pipeline()
    return pipelines


def _tokenize(segment: str) -> list[str]:
    lexer = shlex.shlex(segment, posix=True, punctuation_chars=";&|<>()")
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        return list(lexer)
    except ValueError:  # unbalanced quotes: fall back to crude dequoting
        return segment.replace('"', "").replace("'", "").replace("\\", "").split()


def _expand_variables(text: str, variables: dict[str, str]) -> str:
    for _ in range(3):
        expanded = _VAR_RE.sub(
            lambda m: variables.get(m.group(1) or m.group(2), m.group(0)), text)
        if expanded == text:
            break
        text = expanded
    return text


def _expand_brace(tokens: list[str]) -> list[str]:
    if tokens and re.fullmatch(r"\{[^{}\s]*,[^{}\s]*\}", tokens[0]):
        return [part for part in tokens[0][1:-1].split(",") if part] + tokens[1:]
    return tokens


def _strip_prefix(tokens: list[str], ctx: _Ctx) -> tuple[list[str], list[str]]:
    """Remove keywords, assignments and wrapper commands. Returns (tokens, wrappers)."""
    wrappers: list[str] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        base = posixpath.basename(tok)
        if tok in _KEYWORDS or tok in ("[[", "]]"):
            i += 1
            continue
        if _ASSIGN_RE.match(tok):
            i += 1
            continue
        if base in _WRAPPERS and not (base == "busybox" and i + 1 >= len(tokens)):
            wrappers.append(base)
            i += 1
            value_opts = _WRAPPER_VALUE_OPTS.get(base, set())
            while i < len(tokens) and (tokens[i].startswith("-") or
                                        (base == "env" and _ASSIGN_RE.match(tokens[i]))):
                if tokens[i] == "--":
                    i += 1
                    break
                takes_value = tokens[i] in value_opts
                i += 2 if takes_value else 1
            i += _WRAPPER_POSITIONAL.get(base, 0)
            continue
        break
    return tokens[i:], wrappers


def _render(tokens: Iterable[str], mask: bool) -> str:
    """Join tokens; with `mask`, multi-word strings become `'…'` so their text is not matched."""
    parts = []
    for tok in tokens:
        if re.search(r"\s", tok):
            parts.append("'…'" if mask else shlex.quote(tok))
        else:
            parts.append(tok)
    return " ".join(parts)


def _sub_bodies(token_text: str, ctx: _Ctx) -> list[str]:
    return [ctx.subs.get(int(m.group(1)), "") for m in _PLACEHOLDER_RE.finditer(token_text)]


def _add(ctx: _Ctx, rule: str, category: str, risk: Risk, reason: str, segment: str) -> None:
    ctx.matches.append(Match(rule, category, risk, reason, segment))


# ---------------------------------------------------------------------------
# Core analysis
# ---------------------------------------------------------------------------

def _analyse(command: str, ctx: _Ctx) -> None:
    if ctx.depth > 6:
        _add(ctx, "obfuscated_exec", "obfuscation", Risk.BLOCK,
             "Too many nested layers of code execution.", command)
        return
    ctx.depth += 1
    text = command.replace("\\\n", "")
    for rule in RAW_RULES:
        if rule.pattern.search(text):
            _add(ctx, rule.name, rule.category, rule.risk, rule.reason, text.strip())
    text = _IFS_RE.sub(" ", text)

    base_index = len(ctx.subs)
    pipelines = split_pipelines(text, ctx.subs)
    end_index = len(ctx.subs)
    # Collect simple assignments from every stage first, so `a=r;b=m;$a$b` resolves.
    for pipeline in pipelines:
        for stage in pipeline:
            for tok in _tokenize(stage):
                m = _ASSIGN_RE.match(tok)
                if m and "$(" not in m.group(2):
                    ctx.variables[m.group(1)] = m.group(2)
                elif tok not in ("export", "declare", "local", "readonly", "typeset", "-x"):
                    break
    for pipeline in pipelines:
        _analyse_pipeline(pipeline, ctx)
    # Validate the bodies of substitutions found at this level.
    for index in range(base_index, end_index):
        body = ctx.subs[index]
        if body.strip():
            _analyse(body, ctx)
    ctx.depth -= 1


def _analyse_pipeline(pipeline: list[str], ctx: _Ctx) -> None:
    analysed: list[tuple[str, list[str], str, list[str]]] = []
    for stage in pipeline:
        stage = _expand_variables(stage, ctx.variables)
        tokens = _tokenize(stage)
        tokens, wrappers = _strip_prefix(tokens, ctx)
        tokens = _expand_brace(tokens)
        while tokens and tokens[-1] in (")", "}", "]]", "done", "fi", "esac"):
            tokens = tokens[:-1]
        if not tokens and not wrappers:
            continue
        if tokens and re.search(r"\s", tokens[0]):
            # A whole command passed as one string (`watch "rm -rf /"`, `"$cmd"`): re-check it.
            ctx.commands.extend(wrappers)
            _analyse(" ".join(tokens), ctx)
            continue
        cmd = posixpath.basename(tokens[0]) if tokens else ""
        args = tokens[1:]
        masked = _render([cmd, *args], mask=True).strip()
        full = " ".join([cmd, *args]).strip()
        ctx.segments.append(full if not wrappers else " ".join(wrappers) + " " + full)
        ctx.commands.extend(wrappers)
        if cmd:
            ctx.commands.append(cmd)
        if wrappers and set(wrappers) & {"sudo", "doas", "pkexec"}:
            _add(ctx, "privilege_escalation", "privilege", Risk.WARN,
                 "Runs with root privileges.", full)
        for rule in SEGMENT_RULES:
            target = masked if rule.field == "text" else full
            if rule.pattern.search(target):
                _add(ctx, rule.name, rule.category, rule.risk, rule.reason, full)
        _nested_code(cmd, args, wrappers, full, ctx)
        analysed.append((cmd, args, full, wrappers))
    _pipeline_rules(analysed, ctx)


def _nested_code(cmd: str, args: list[str], wrappers: list[str], full: str, ctx: _Ctx) -> None:
    """Re-validate strings that the shell (or an interpreter) will execute."""
    nested: list[str] = []
    if cmd in SHELLS or cmd == "su":
        for i, arg in enumerate(args):
            if re.fullmatch(r"-\w*c\w*", arg) and i + 1 < len(args):
                nested.append(args[i + 1])
                break
        if "<<<" in args:
            idx = args.index("<<<")
            nested.append(" ".join(args[idx + 1:]))
    elif cmd == "eval":
        nested.append(" ".join(args))
    elif cmd in ("trap", "watch", "alias"):
        for arg in args:
            nested.append(arg.split("=", 1)[1] if cmd == "alias" and "=" in arg else arg)
    elif cmd == "find":
        for i, arg in enumerate(args):
            if arg in ("-exec", "-execdir", "-ok") and i + 1 < len(args):
                rest = args[i + 1:]
                end = next((j for j, a in enumerate(rest) if a in (";", "+", "\\;")), len(rest))
                nested.append(_render(rest[:end], mask=False))
    elif cmd in INTERPRETERS or re.fullmatch(r"python[\d.]*", cmd) or cmd in ("awk", "gawk",
                                                                             "mawk"):
        # Perl/Ruby expose the environment as $ENV{VAR}; map it to the shell's $VAR
        # so `rm -rf $ENV{HOME}` is seen as `rm -rf $HOME`.
        code = re.sub(r"\$ENV\{\s*'?(\w+)'?\s*\}", r"$\1", " ".join(args))
        if re.search(r"system|popen|subprocess|exec|spawn|`|qx", code):
            nested.extend(m.group(2) for m in re.finditer(r"(['\"])(.+?)\1", code))
    # Substitutions used as the command name or as code for an executing command.
    executes = (cmd in SHELLS or cmd in INTERPRETERS or cmd in ("eval", "source", ".")
                or bool(re.fullmatch(r"python[\d.]*", cmd)) or not cmd or cmd.startswith("$"))
    for body in _sub_bodies(" ".join([cmd, *args]) if executes else cmd, ctx):
        if DECODER_RE.search(body):
            _add(ctx, "obfuscated_exec", "obfuscation", Risk.BLOCK,
                 "Executes code that is decoded or de-obfuscated at run time.", full)
        if DOWNLOAD_RE.search(body.strip()):
            _add(ctx, "remote_code_exec", "remote_exec", Risk.BLOCK,
                 "Executes code downloaded from the network.", full)
    for code in nested:
        if code.strip():
            _analyse(code, ctx)


def _pipeline_rules(stages: list[tuple[str, list[str], str, list[str]]], ctx: _Ctx) -> None:
    for i, (cmd, args, full, wrappers) in enumerate(stages):
        if i == 0:
            continue
        reads_stdin = (cmd in SHELLS and not any(not a.startswith("-") for a in args)) or (
            (cmd in INTERPRETERS or re.fullmatch(r"python[\d.]*", cmd or "")) and
            (not args or args == ["-"])) or (cmd in ("source", ".") and "/dev/stdin" in args)
        if cmd in SHELLS and "-s" in args:
            reads_stdin = True
        if not reads_stdin:
            if "xargs" in wrappers and cmd in ("rm", "shred", "unlink"):
                upstream = " ".join(s[2] for s in stages[:i])
                if re.search(rf"^(?:find|ls|echo|printf)\s+(?:-\S+\s+)*{FIND_ROOT}{END}",
                             upstream):
                    _add(ctx, "rm_recursive_dangerous_target", "recursive_delete", Risk.BLOCK,
                         "Deletes files listed from /, a system directory or home.", full)
            continue
        upstream = stages[:i]
        texts = [s[2] for s in upstream]
        if any(s[0] in DOWNLOADERS for s in upstream):
            _add(ctx, "remote_pipe_shell", "remote_exec", Risk.BLOCK,
                 "Pipes content downloaded from the network into a shell.", full)
        elif any(DECODER_RE.search(t) for t in texts):
            _add(ctx, "obfuscated_pipe_shell", "obfuscation", Risk.BLOCK,
                 "Pipes decoded or de-obfuscated data into a shell.", full)
        else:
            _add(ctx, "pipe_to_shell", "remote_exec", Risk.WARN,
                 "Pipes text into a shell to be executed.", full)
            for s in upstream:
                if s[0] in ("echo", "printf"):
                    _analyse(" ".join(a for a in s[1] if not a.startswith("-")), ctx)


# ---------------------------------------------------------------------------
# Structural layer (bashlex): a second, independent check on parsed commands
# ---------------------------------------------------------------------------

def _normpath(path: str) -> str:
    """POSIX normpath, collapsing the special leading `//` to `/`."""
    norm = posixpath.normpath(path)
    if norm.startswith("//") and not norm.startswith("///"):
        norm = "/" + norm.lstrip("/")
    return norm


def _canonical_target_is_dangerous(target: str) -> bool:
    """True if a recursive deletion target resolves to /, a system dir or everything.

    Canonicalising the path catches `rm -rf /.`, `//`, `/tmp/..` and `/var/lib`,
    which the regex layer's literal patterns miss. Home targets are left to the
    regex layer, which blocks bare `$HOME`/`~` but only warns on their subdirs.
    """
    t = target.strip()
    if not t:
        return False
    if t == "*":
        return True
    if re.match(r"^(?:~|\$HOME\b|\$\{HOME\})", t):
        return False
    # A leading command substitution or $PWD is a non-root absolute directory, so
    # `$(pwd)/..` walks up to / just as a literal path would.
    t = re.sub(r"^(?:\$\([^)]*\)|`[^`]*`|\$\{?PWD\}?)", "/__abs__", t)
    if not t.startswith("/"):
        return False
    norm = _normpath(t)
    if norm == "/":
        return True
    first = norm.split("/", 2)[1] if len(norm) > 1 else ""
    return first in _SYS_DIR_SET


def _rm_targets(cmd: shell_parser.SimpleCommand) -> tuple[bool, list[str]]:
    """Return (recursive?, target words) for an `rm` command, flag order aside."""
    recursive = False
    targets: list[str] = []
    opts_done = False
    for arg in cmd.argv[1:]:
        if not opts_done and arg == "--":
            opts_done = True
            continue
        if not opts_done and arg.startswith("-") and len(arg) > 1:
            if arg == "--recursive" or (not arg.startswith("--") and re.search(r"[rR]", arg)):
                recursive = True
            continue
        targets.append(arg)
    return recursive, targets


def _emitted_words(producer: shell_parser.SimpleCommand) -> list[str]:
    """Words an `echo`/`printf` producer prints, as `xargs` would split them."""
    args = list(producer.argv[1:])
    if producer.program == "printf":
        args = args[1:]  # drop the format string
    else:
        while args and re.fullmatch(r"-[neE]+", args[0]):
            args = args[1:]
    words: list[str] = []
    for arg in args:
        words.extend(arg.split())
    return words


_XARGS_VALUE_OPTS = frozenset({"-n", "-P", "-d", "-L", "-l", "-s", "-a", "-E", "-e",
                               "--max-args", "--max-procs", "--delimiter", "--arg-file",
                               "--max-lines"})


def _xargs_command(tokens: list[str]) -> tuple[list[str], str | None]:
    """Split xargs options from the command it runs; return (command, replace-string)."""
    replace: str | None = None
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if not tok.startswith("-"):
            break
        if tok in ("-I", "-i", "--replace"):
            replace = tokens[i + 1] if i + 1 < len(tokens) else "{}"
            i += 2 if i + 1 < len(tokens) else 1
        elif tok.startswith("-I"):
            replace = tok[2:] or "{}"
            i += 1
        elif tok.startswith("--replace="):
            replace = tok.split("=", 1)[1] or "{}"
            i += 1
        elif tok in _XARGS_VALUE_OPTS:
            i += 2
        else:
            i += 1
    return tokens[i:], replace


def _reads_stdin(stage: shell_parser.SimpleCommand) -> bool:
    """True if a shell stage runs whatever it is piped (no -c string, no script arg)."""
    args = stage.argv[1:]
    if any(a.startswith("-") and "c" in a.lstrip("-") for a in args):
        return False
    return not any(not a.startswith("-") for a in args)


def _structural_command(cmd: shell_parser.SimpleCommand, ctx: _Ctx) -> None:
    prog = cmd.program
    full = " ".join(cmd.argv)
    if prog == "rm":
        recursive, targets = _rm_targets(cmd)
        if recursive and any(_canonical_target_is_dangerous(t) for t in targets):
            _add(ctx, "rm_recursive_dangerous_target", "recursive_delete", Risk.BLOCK,
                 "Recursive deletion of /, a system directory or everything "
                 "(after resolving the path).", full)
    elif prog == "dd":
        if any(a.startswith("of=") and _BLOCK_DEVICE_RE.match(a[3:]) for a in cmd.argv[1:]):
            _add(ctx, "dd_to_device", "disk_destruction", Risk.BLOCK,
                 "dd writing directly to a block device.", full)
    elif re.fullmatch(r"mkfs(?:\.\w+)?|mke2fs|mkswap|mkdosfs", prog):
        if any(_BLOCK_DEVICE_RE.match(a) for a in cmd.argv[1:]):
            _add(ctx, "mkfs_device", "disk_destruction", Risk.BLOCK,
                 "Creates a filesystem on a block device, erasing it.", full)
    elif prog in ("chmod", "chown", "chgrp"):
        recursive = any(a == "--recursive" or (a.startswith("-") and not a.startswith("--")
                        and "R" in a) for a in cmd.argv[1:])
        targets = [a for a in cmd.argv[1:] if not a.startswith("-")]
        if recursive and any(_SYSTEM_PATH_RE.match(t) for t in targets):
            _add(ctx, "recursive_perm_system", "permissions", Risk.BLOCK,
                 "Recursive permission or ownership change on a system path.", full)
    for redirect in cmd.redirects:
        if redirect.type in (">", ">>") and (_CRITICAL_FILE_RE.match(redirect.target) or
                                             _BLOCK_DEVICE_RE.match(redirect.target)):
            _add(ctx, "redirect_to_critical_file", "critical_file", Risk.BLOCK,
                 "Redirects output onto a critical file or block device.", full)


def _structural_xargs(producer: shell_parser.SimpleCommand,
                      xargs_stage: shell_parser.SimpleCommand, ctx: _Ctx) -> None:
    """Rebuild the command xargs runs from an echo/printf producer and re-check it.

    This catches attacks where the dangerous arguments reach the command through
    the pipe, e.g. `echo "-rf /" | xargs rm` or `echo "of=/dev/sda" | xargs dd`.
    """
    if producer.program not in ("echo", "printf"):
        return
    emitted = _emitted_words(producer)
    if not emitted:
        return
    command, replace = _xargs_command(list(xargs_stage.argv[1:]))
    if not command:
        return
    if replace:
        joined = " ".join(emitted)
        rebuilt = " ".join(tok.replace(replace, joined) for tok in command)
    else:
        rebuilt = " ".join(command + emitted)
    for match in validate(rebuilt, layers="regex").matches:
        ctx.matches.append(Match(match.rule, match.category, match.risk, match.reason, rebuilt))


def _structural_pipeline(stages: list[shell_parser.SimpleCommand], ctx: _Ctx) -> None:
    for i, stage in enumerate(stages):
        if i == 0:
            continue
        if stage.program == "xargs":
            _structural_xargs(stages[i - 1], stage, ctx)
        if stage.program in SHELLS and _reads_stdin(stage):
            upstream = stages[:i]
            texts = [" ".join(s.argv) for s in upstream]
            if any(s.program in DOWNLOADERS for s in upstream):
                _add(ctx, "remote_pipe_shell", "remote_exec", Risk.BLOCK,
                     "Pipes content downloaded from the network into a shell.",
                     " ".join(stage.argv))
            elif any(DECODER_RE.search(t) for t in texts):
                _add(ctx, "obfuscated_pipe_shell", "obfuscation", Risk.BLOCK,
                     "Pipes decoded or de-obfuscated data into a shell.",
                     " ".join(stage.argv))


def _structural(command: str, ctx: _Ctx) -> None:
    """Run the bashlex-based structural layer, appending matches to `ctx`."""
    result = shell_parser.parse_script(command)
    if result.status == "malformed":
        _add(ctx, "could_not_parse_structure", "structure", Risk.WARN,
             "Could not parse the command structure; treating it as risky.", command.strip())
        return
    if result.status != "ok":
        return  # unsupported syntax or bashlex missing: rely on the regex layer
    for cmd in result.commands:
        _structural_command(cmd, ctx)
    for stages in result.pipelines:
        _structural_pipeline(stages, ctx)


def validate(command: str, allowlist: frozenset[str] | None = None, *,
             layers: str = "both") -> ValidationResult:
    """Classify `command`. With `allowlist`, any binary not listed is BLOCKed.

    `layers` selects the validator layers: "regex", "structural" or "both"
    (default). The verdict is the most severe match from the layers that ran, and
    every matched rule name is reported.
    """
    if not command or not command.strip():
        return ValidationResult(Risk.SAFE, reason="Empty command.")
    ctx = _Ctx(allowlist=allowlist)
    if layers in ("regex", "both"):
        _analyse(command, ctx)
    if layers in ("structural", "both"):
        _structural(command, ctx)
    if allowlist is not None:
        outside = sorted({c for c in ctx.commands if c and c not in allowlist})
        if outside or not ctx.commands:
            _add(ctx, "not_in_allowlist", "allowlist", Risk.BLOCK,
                 "Not in the allowlist: " + (", ".join(outside) or "(no command found)") + ".",
                 command)
    if not ctx.matches:
        return ValidationResult(Risk.SAFE, segments=tuple(ctx.segments))
    top = max(m.risk for m in ctx.matches)
    names = tuple(dict.fromkeys(m.rule for m in ctx.matches))
    reasons = list(dict.fromkeys(m.reason for m in ctx.matches if m.risk == top))
    return ValidationResult(top, names, " ".join(reasons), tuple(ctx.segments),
                            tuple(ctx.matches))
