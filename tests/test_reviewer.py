from app.models import ChangedFile, LLMFinding, ReviewCategory, ReviewRequest, Severity
from app.reviewer import build_result, render_markdown, validate_llm_findings


def sample_request() -> ReviewRequest:
    return ReviewRequest(
        repository="example/project",
        pull_request=12,
        title="Add helper",
        head_sha="abcdef1234567890",
        files=[ChangedFile(path="app.py", patch="@@ -1,0 +1,2 @@\n+eval(user_input)\n+print('ok')\n")],
    )


def test_llm_findings_must_reference_added_lines_and_have_confidence() -> None:
    candidates = [
        LLMFinding(category=ReviewCategory.BUG, severity=Severity.HIGH, title="Unsafe eval", description="User input is evaluated directly.", recommendation="Use a parser.", path="app.py", line=1, confidence=0.9),
        LLMFinding(category=ReviewCategory.BUG, severity=Severity.HIGH, title="Not changed", description="Not a changed line issue.", recommendation="Ignore.", path="app.py", line=99, confidence=0.99),
        LLMFinding(category=ReviewCategory.BUG, severity=Severity.LOW, title="Weak signal", description="Confidence too low.", recommendation="Review.", path="app.py", line=2, confidence=0.4),
    ]
    accepted = validate_llm_findings(candidates, sample_request().files)
    assert len(accepted) == 1
    assert accepted[0].line == 1


def test_review_result_has_counts_and_markdown() -> None:
    result = build_result(sample_request(), provider_name="rules")
    assert result.summary.total_findings == 1
    assert result.summary.high == 1
    report = render_markdown(result)
    assert "<!-- ai-code-review-pr-agent -->" in report
    assert "app.py:1" in report
    assert "Suggested fix" in report


def test_rule_and_llm_duplicate_at_same_location_are_deduplicated() -> None:
    request = ReviewRequest(
        repository="example/project", pull_request=13,
        files=[ChangedFile(path="app.py", patch="@@ -1,0 +1 @@\n+eval(value)\n")],
    )
    llm = LLMFinding(category=ReviewCategory.BUG, severity=Severity.HIGH, title="Eval call", description="The eval call may execute attacker-controlled input.", recommendation="Avoid eval.", path="app.py", line=1, confidence=0.99)
    result = build_result(request, "openai", [llm])
    assert result.summary.total_findings == 1
    assert result.findings[0].confidence == 0.99
