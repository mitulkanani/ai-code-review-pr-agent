from collections import Counter
from typing import Iterable

from app.diff_parser import count_patch_changes
from app.models import (
    ChangedFile,
    FileSummary,
    Finding,
    LLMFinding,
    ReviewRequest,
    ReviewResult,
    ReviewSummary,
    Severity,
)
from app.rules import analyze_static, changed_line_index


_SEVERITY_ORDER = {Severity.CRITICAL: 0, Severity.HIGH: 1, Severity.MEDIUM: 2, Severity.LOW: 3, Severity.INFO: 4}


def validate_llm_findings(candidates: Iterable[LLMFinding], files: list[ChangedFile]) -> list[Finding]:
    """Accept LLM findings only when they point to a real added line in this diff."""
    index = changed_line_index(files)
    paths = {item.path for item in files}
    accepted: list[Finding] = []
    for item in candidates:
        if item.path not in paths or item.line not in index.get(item.path, set()):
            continue
        if item.confidence < 0.65:
            continue
        accepted.append(
            Finding(
                rule_id="LLM-REVIEW",
                category=item.category,
                severity=item.severity,
                title=item.title[:160],
                description=item.description[:2000],
                recommendation=item.recommendation[:1200],
                path=item.path,
                line=item.line,
                confidence=item.confidence,
                source="llm",
            )
        )
    return accepted


def build_result(request: ReviewRequest, provider_name: str, llm_findings: Iterable[LLMFinding] = ()) -> ReviewResult:
    static_findings = analyze_static(request.files)
    findings = static_findings + validate_llm_findings(llm_findings, request.files)

    # Deduplicate same category and location, keeping the highest-confidence finding.
    deduped: dict[tuple[str, int, str], Finding] = {}
    for finding in findings:
        key = (finding.path, finding.line, finding.category.value)
        existing = deduped.get(key)
        if existing is None or finding.confidence > existing.confidence:
            deduped[key] = finding
    findings = sorted(
        deduped.values(),
        key=lambda item: (_SEVERITY_ORDER[item.severity], item.path, item.line),
    )

    file_summaries: list[FileSummary] = []
    analyzed_lines = 0
    for item in request.files:
        additions, deletions, line_count = count_patch_changes(item.patch)
        analyzed_lines += line_count
        file_summaries.append(
            FileSummary(
                path=item.path,
                status=item.status,
                additions=additions,
                deletions=deletions,
                analyzed_added_lines=line_count,
            )
        )

    counts = Counter(finding.severity for finding in findings)
    summary = ReviewSummary(
        total_findings=len(findings),
        critical=counts[Severity.CRITICAL],
        high=counts[Severity.HIGH],
        medium=counts[Severity.MEDIUM],
        low=counts[Severity.LOW],
        info=counts[Severity.INFO],
        changed_files=len(request.files),
        analyzed_added_lines=analyzed_lines,
    )
    notes = [
        "Only added lines with available unified-diff patches were analyzed.",
        "Static checks are heuristic signals; review each finding in its surrounding code context.",
    ]
    if any(item.patch is None for item in request.files):
        notes.append("Some files had no patch in the GitHub API response and could not be analyzed line by line.")
    if provider_name == "openai":
        notes.append("Redacted changed-line diffs were sent to the configured OpenAI model for review.")
    return ReviewResult(
        repository=request.repository,
        pull_request=request.pull_request,
        head_sha=request.head_sha,
        provider=provider_name,
        summary=summary,
        findings=findings,
        files=file_summaries,
        notes=notes,
    )


def render_markdown(result: ReviewResult) -> str:
    s = result.summary
    lines = [
        "<!-- ai-code-review-pr-agent -->",
        "## AI Code Review Summary",
        "",
        f"**Repository:** `{result.repository}` · **PR:** #{result.pull_request}",
        f"**Provider:** `{result.provider}` · **Commit:** `{result.head_sha[:12] or 'not supplied'}`",
        "",
        f"| Findings | Critical | High | Medium | Low | Info | Files | Added lines |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
        f"| {s.total_findings} | {s.critical} | {s.high} | {s.medium} | {s.low} | {s.info} | {s.changed_files} | {s.analyzed_added_lines} |",
        "",
    ]
    if result.findings:
        lines.extend(["### Findings", ""])
        for item in result.findings:
            location = f"`{item.path}:{item.line}`"
            lines.append(f"- **[{item.severity.value.upper()}] {item.title}** — {location}")
            lines.append(f"  - {item.description}")
            if item.recommendation:
                lines.append(f"  - **Suggested fix:** {item.recommendation}")
            lines.append(f"  - Confidence: {item.confidence:.0%} · Source: `{item.source}`")
    else:
        lines.extend(["### Findings", "", "No actionable findings were raised by the configured checks.", ""])
    if result.notes:
        lines.extend(["### Review notes", ""])
        lines.extend([f"- {note}" for note in result.notes])
    lines.extend(["", "<sub>Automated review is advisory, not a security audit or a substitute for tests and human review.</sub>"])
    return "\n".join(lines)
