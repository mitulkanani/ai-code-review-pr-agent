from app.models import ChangedFile, Severity
from app.rules import analyze_static, changed_line_index


def test_finds_secret_only_on_added_lines() -> None:
    patch = """@@ -1,2 +1,3 @@
 old = 'AKIA1234567890ABCDEF'
+AWS_KEY = 'AKIA1234567890ABCDEF'
 context
"""
    findings = analyze_static([ChangedFile(path="settings.py", patch=patch)])
    assert len(findings) == 1
    assert findings[0].rule_id == "SEC001"
    assert findings[0].severity == Severity.CRITICAL
    assert findings[0].line == 2


def test_detects_shell_true_and_insecure_tls() -> None:
    patch = """@@ -0,0 +1,2 @@
+subprocess.run(command, shell=True)
+requests.get(url, verify=False)
"""
    findings = analyze_static([ChangedFile(path="client.py", patch=patch)])
    assert {finding.rule_id for finding in findings} == {"SEC005", "SEC006"}


def test_placeholder_secret_is_ignored_for_generic_assignment_rule() -> None:
    patch = "@@ -1,0 +1 @@\n+API_KEY = 'your_api_key_here'\n"
    findings = analyze_static([ChangedFile(path="config.py", patch=patch)])
    assert findings == []


def test_changed_line_index_is_per_file() -> None:
    files = [
        ChangedFile(path="a.py", patch="@@ -1,0 +2 @@\n+x=1\n"),
        ChangedFile(path="b.py", patch="@@ -1,0 +8 @@\n+y=2\n"),
    ]
    assert changed_line_index(files) == {"a.py": {2}, "b.py": {8}}
