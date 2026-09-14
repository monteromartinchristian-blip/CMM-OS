"""Phase 10.5 – Domain Validation Security Helpers.

Static analysis helpers for domain security validation.
No code execution, no network, no subprocess.
"""

from __future__ import annotations

import ast
import re

# ── Secret scanning patterns ───────────────────────────────────────────────────

_SECRET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"password\s*[:=]\s*['\"]\S", re.IGNORECASE), "password_assignment"),
    (re.compile(r"secret\s*[:=]\s*['\"]\S", re.IGNORECASE), "secret_assignment"),
    (re.compile(r"token\s*[:=]\s*['\"]\S", re.IGNORECASE), "token_assignment"),
    (re.compile(r"api_key\s*[:=]\s*['\"]\S", re.IGNORECASE), "api_key_assignment"),
    (
        re.compile(r"private_key\s*[:=]\s*['\"]\S", re.IGNORECASE),
        "private_key_assignment",
    ),
    (
        re.compile(
            r"-----BEGIN\s+(RSA|EC|DSA|OPENSSH|PGP)?\s*PRIVATE\s+KEY", re.IGNORECASE
        ),
        "private_key_block",
    ),
    (re.compile(r"bearer\s+[a-zA-Z0-9\-._~+/]+=*", re.IGNORECASE), "bearer_token"),
]

# False positive patterns (placeholders, env vars, examples)
_FALSE_POSITIVE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\$\{[A-Z_]+\}"),  # ${ENV_VAR}
    re.compile(r"<[^>]+>"),  # <token>, <your-api-key>
    re.compile(r"your[-_]?(api[-_]?key|token|secret|password)", re.IGNORECASE),
    re.compile(r"^[#\s]*example", re.IGNORECASE),
    re.compile(r"^[#\s]*placeholder", re.IGNORECASE),
    re.compile(r"^[#\s]*TODO", re.IGNORECASE),
    re.compile(r"^[#\s]*XXX", re.IGNORECASE),
    re.compile(r"password\s*[:=]\s*['\"]\s*['\"]"),  # empty password
]


def _is_false_positive(line: str) -> bool:
    """Check if a matched line is likely a false positive."""
    for pattern in _FALSE_POSITIVE_PATTERNS:
        if pattern.search(line):
            return True
    return False


def scan_secrets(content: str, rel_path: str) -> list[dict[str, object]]:
    """Scan file content for secret patterns.

    Args:
        content: File content as string.
        rel_path: Relative path of the file (for reporting).

    Returns:
        List of dicts with 'line', 'category', 'path' (no secret values).
    """
    findings: list[dict[str, object]] = []
    lines = content.split("\n")
    for line_no, line in enumerate(lines, start=1):
        if _is_false_positive(line):
            continue
        for pattern, category in _SECRET_PATTERNS:
            if pattern.search(line):
                findings.append(
                    {
                        "line": line_no,
                        "category": category,
                        "path": rel_path,
                    }
                )
                break  # one finding per line
    return findings


# ── Forbidden command patterns ─────────────────────────────────────────────────

_FORBIDDEN_COMMANDS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\brm\s+-rf\b"), "rm_rf"),
    (re.compile(r"\bsudo\b"), "sudo"),
    (re.compile(r"\bcurl\b.*\|.*\bsh\b"), "curl_pipe_sh"),
    (re.compile(r"\bwget\b.*\|.*\bsh\b"), "wget_pipe_sh"),
    (re.compile(r"\bchmod\s+777\b"), "chmod_777"),
    (re.compile(r"\beval\s*\("), "eval_call"),
    (re.compile(r"\bexec\s*\("), "exec_call"),
    (re.compile(r"\bsubprocess\b"), "subprocess"),
    (re.compile(r"\bos\.system\b"), "os_system"),
    (re.compile(r"\bshell\s*=\s*True\b"), "shell_true"),
]


def scan_forbidden_commands(content: str, rel_path: str) -> list[dict[str, object]]:
    """Scan file content for forbidden command patterns.

    Args:
        content: File content as string.
        rel_path: Relative path of the file.

    Returns:
        List of dicts with 'line', 'category', 'path'.
    """
    findings: list[dict[str, object]] = []
    lines = content.split("\n")
    for line_no, line in enumerate(lines, start=1):
        for pattern, category in _FORBIDDEN_COMMANDS:
            if pattern.search(line):
                findings.append(
                    {
                        "line": line_no,
                        "category": f"forbidden_command_{category}",
                        "path": rel_path,
                    }
                )
    return findings


# ── Unauthorized imports ───────────────────────────────────────────────────────

_FORBIDDEN_IMPORTS = frozenset(
    {
        "subprocess",
        "socket",
        "requests",
        "urllib.request",
        "paramiko",
        "fabric",
        "pexpect",
    }
)


def scan_unauthorized_imports(content: str, rel_path: str) -> list[dict[str, object]]:
    """Scan Python source code for unauthorized imports using AST.

    Args:
        content: Python source code as string.
        rel_path: Relative path of the file.

    Returns:
        List of dicts with 'line', 'import_name', 'path'.
    """
    findings: list[dict[str, object]] = []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return [{"line": 1, "category": "invalid_python_syntax", "path": rel_path}]

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                base_module = alias.name.split(".")[0]
                if base_module in _FORBIDDEN_IMPORTS:
                    findings.append(
                        {
                            "line": node.lineno,
                            "import_name": alias.name,
                            "category": "unauthorized_import",
                            "path": rel_path,
                        }
                    )
        elif isinstance(node, ast.ImportFrom) and node.module:
            base_module = node.module.split(".")[0]
            if base_module in _FORBIDDEN_IMPORTS:
                findings.append(
                    {
                        "line": node.lineno,
                        "import_name": node.module,
                        "category": "unauthorized_import_from",
                        "path": rel_path,
                    }
                )

    return findings


# ── Prompt injection heuristics ────────────────────────────────────────────────

_PROMPT_INJECTION_PATTERNS: list[tuple[re.Pattern[str], str, bool]] = [
    # Patterns that are warnings by default
    (
        re.compile(r"ignore\s+(all\s+)?previous\s+instructions?", re.IGNORECASE),
        "ignore_previous_instructions",
        False,
    ),
    (
        re.compile(r"override\s+system\s+(prompt|message)", re.IGNORECASE),
        "override_system_prompt",
        False,
    ),
    (
        re.compile(r"reveal\s+(system\s+)?(prompt|message)", re.IGNORECASE),
        "reveal_system_prompt",
        False,
    ),
    (re.compile(r"disable\s+safety", re.IGNORECASE), "disable_safety", False),
    (
        re.compile(r"you\s+are\s+now\s+\w+\s+mode", re.IGNORECASE),
        "roleplay_mode",
        False,
    ),
    # Blocking: explicit policy bypass
    (re.compile(r"bypass\s+(policy|policies)", re.IGNORECASE), "bypass_policy", True),
    (
        re.compile(
            r"ignore\s+(all\s+)?(safety|security|content)\s+(policy|policies|restrictions|guidelines)",
            re.IGNORECASE,
        ),
        "ignore_safety_policy",
        True,
    ),
]


def scan_prompt_injection_risks(content: str, rel_path: str) -> list[dict[str, object]]:
    """Scan for prompt injection risks in text content.

    Args:
        content: File content as string.
        rel_path: Relative path of the file.

    Returns:
        List of dicts with 'line', 'category', 'path', 'blocking'.
    """
    findings: list[dict[str, object]] = []
    lines = content.split("\n")
    for line_no, line in enumerate(lines, start=1):
        for pattern, category, is_blocking in _PROMPT_INJECTION_PATTERNS:
            if pattern.search(line):
                findings.append(
                    {
                        "line": line_no,
                        "category": f"prompt_injection_{category}",
                        "path": rel_path,
                        "blocking": is_blocking,
                    }
                )
    return findings


# ── File safety checks ─────────────────────────────────────────────────────────


def check_file_safety(
    rel_path: str,
    content: bytes | str,
    *,
    max_file_bytes: int,
) -> list[dict[str, object]]:
    """Check file for safety issues: size, encoding, binary.

    Args:
        rel_path: Relative path of the file.
        content: File content (bytes or str).
        max_file_bytes: Maximum allowed file size in bytes.

    Returns:
        List of findings dicts.
    """
    findings: list[dict[str, object]] = []

    # Check size
    if isinstance(content, str):
        byte_len = len(content.encode("utf-8", errors="replace"))
    else:
        byte_len = len(content)

    if byte_len > max_file_bytes:
        findings.append(
            {
                "line": 1,
                "category": "file_too_large",
                "path": rel_path,
                "size_bytes": byte_len,
                "max_bytes": max_file_bytes,
            }
        )

    # Check UTF-8 validity
    if isinstance(content, bytes):
        try:
            content.decode("utf-8")
        except UnicodeDecodeError:
            findings.append(
                {
                    "line": 1,
                    "category": "invalid_utf8",
                    "path": rel_path,
                }
            )
            return findings  # Don't continue if not valid UTF-8

    # Detect binary content
    text_content = (
        content
        if isinstance(content, str)
        else content.decode("utf-8", errors="replace")
    )
    null_count = text_content.count("\x00")
    if null_count > 0:
        findings.append(
            {
                "line": 1,
                "category": "binary_content_detected",
                "path": rel_path,
                "null_bytes": null_count,
            }
        )

    return findings


__all__ = [
    "check_file_safety",
    "scan_forbidden_commands",
    "scan_prompt_injection_risks",
    "scan_secrets",
    "scan_unauthorized_imports",
]
