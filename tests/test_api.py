from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_review_api_analyzes_patch_and_returns_findings() -> None:
    response = client.post(
        "/api/reviews",
        json={
            "repository": "owner/repo",
            "pull_request": 7,
            "head_sha": "123abc",
            "files": [{"path": "client.py", "patch": "@@ -1,0 +1 @@\n+requests.get(url, verify=False)\n"}],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["result"]["findings"][0]["rule_id"] == "SEC005"


def test_review_api_rejects_absolute_and_parent_paths() -> None:
    for path in ("/etc/passwd", "../secret.py", "folder/../secret.py"):
        response = client.post(
            "/api/reviews",
            json={"repository": "owner/repo", "pull_request": 1, "files": [{"path": path, "patch": "@@ -0,0 +1 @@\n+x=1"}]},
        )
        assert response.status_code == 422


def test_api_rejects_extra_request_fields() -> None:
    response = client.post(
        "/api/reviews",
        json={"repository": "owner/repo", "pull_request": 1, "files": [{"path": "a.py", "patch": "@@ -0,0 +1 @@\n+x=1"}], "extra": "no"},
    )
    assert response.status_code == 422
