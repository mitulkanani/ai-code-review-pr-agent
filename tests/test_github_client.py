import json

import httpx

from app.github_client import GitHubClient


def test_fetch_pr_and_files() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/pulls/4"):
            return httpx.Response(200, json={"title": "Add change", "body": "desc", "head": {"sha": "abc123"}})
        if request.url.path.endswith("/pulls/4/files"):
            return httpx.Response(200, json=[{"filename": "a.py", "status": "modified", "patch": "@@ -1,0 +1 @@\n+x=1"}])
        raise AssertionError(str(request.url))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    github = GitHubClient("token", client=client)
    result = github.fetch_pull_request("owner/repo", 4)
    assert result.title == "Add change"
    assert result.head_sha == "abc123"
    assert result.files[0].path == "a.py"
    client.close()


def test_summary_comment_created_or_updated_idempotently() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.method == "GET":
            return httpx.Response(200, json=[])
        if request.method == "POST":
            assert "<!-- ai-code-review-pr-agent -->" in json.loads(request.content)["body"]
            return httpx.Response(201, json={"id": 100})
        raise AssertionError(request.method)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    github = GitHubClient("token", client=client)
    assert github.upsert_summary_comment("owner/repo", 4, "<!-- ai-code-review-pr-agent -->\nreview") == "created"
    assert calls[-1][0] == "POST"
    client.close()
