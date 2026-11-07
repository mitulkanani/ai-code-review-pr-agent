import re
from collections.abc import Iterable

from app.diff_parser import AddedLine, parse_added_lines
from app.models import ChangedFile, Finding, ReviewCategory, Severity


_RULES: list[tuple[str, ReviewCategory, Severity, re.Pattern[str], str, str, float]] = [
    (
        "SEC001", ReviewCategory.SECURITY, Severity.CRITICAL,
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        "AWS access key appears in the diff",
        "Remove the key, rotate it immediately, and load credentials from a secret manager or environment.", 0.99,
    ),
    (
        "SEC002", ReviewCategory.SECURITY, Severity.CRITICAL,
        re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
        "GitHub token appears in the diff",
        "Revoke the token and replace it with a short-lived, least-privilege credential stored outside source control.", 0.99,
    ),
    (
        "SEC003", ReviewCategory.SECURITY, Severity.HIGH,
        re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
        "Possible model-provider API key in source",
        "Revoke the exposed key and use a secret manager or environment variable.", 0.96,
    ),
    (
        "SEC004", ReviewCategory.SECURITY, Severity.HIGH,
        re.compile(r"(?i)\b(?:password|passwd|api_key|secret|access_token)\s*[:=]\s*['\"][^'\"]{8,}['\"]"),
        "Possible hard-coded credential",
        "Do not commit credentials. Load them at runtime from a secure secret store and rotate any real value.", 0.88,
    ),
    (
        "SEC005", ReviewCategory.SECURITY, Severity.HIGH,
        re.compile(r"\bverify\s*=\s*False\b"),
        "TLS certificate verification is disabled",
        "Keep certificate verification enabled. Configure the correct CA bundle for private certificates instead.", 0.97,
    ),
    (
        "SEC006", ReviewCategory.SECURITY, Severity.HIGH,
        re.compile(r"\bshell\s*=\s*True\b"),
        "Subprocess is invoked through a shell",
        "Prefer an argument list with shell=False. If a shell is unavoidable, strictly validate and quote every input.", 0.90,
    ),
    (
        "BUG001", ReviewCategory.BUG, Severity.HIGH,
        re.compile(r"\beval\s*\("),
        "Dynamic eval of an expression",
        "Avoid evaluating dynamic strings. Parse a constrained format or map inputs to explicit functions.", 0.86,
    ),
    (
        "BUG002", ReviewCategory.BUG, Severity.MEDIUM,
        re.compile(r"\bexcept\s+Exception\s*:\s*pass\b"),
        "An exception is silently ignored",
        "Handle expected exceptions explicitly or log and propagate unexpected failures.", 0.90,
    ),
    (
        "SEC007", ReviewCategory.SECURITY, Severity.HIGH,
        re.compile(r"(?i)f['\"][^'\"]*\b(?:select|insert|update|delete)\b[^'\"]*\{[^}]+\}[^'\"]*['\"]"),
        "Possible SQL string interpolation",
        "Use parameterized queries or the database library's query builder instead of interpolating untrusted values.", 0.83,
    ),
]


def analyze_static(files: Iterable[ChangedFile]) -> list[Finding]:
    findings: list[Finding] = []
    for changed_file in files:
        for added in parse_added_lines(changed_file.patch):
            for rule_id, category, severity, pattern, title, recommendation, confidence in _RULES:
                match = pattern.search(added.text)
                if not match:
                    continue
                # Avoid obvious examples and placeholders for generic credential rules.
                if rule_id == "SEC004":
                    value = match.group(0).lower()
                    if any(marker in value for marker in ("example", "placeholder", "changeme", "your_", "dummy")):
                        continue
                findings.append(
                    Finding(
                        rule_id=rule_id,
                        category=category,
                        severity=severity,
                        title=title,
                        description=f"Added line {added.number} matches rule {rule_id}. Confirm whether this is exploitable in context.",
                        recommendation=recommendation,
                        path=changed_file.path,
                        line=added.number,
                        confidence=confidence,
                        source="static",
                    )
                )
    return findings


def changed_line_index(files: Iterable[ChangedFile]) -> dict[str, set[int]]:
    return {item.path: {line.number for line in parse_added_lines(item.patch)} for item in files}
