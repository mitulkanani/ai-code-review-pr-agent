import httpx

from app.config import settings
from app.models import ChangedFile, ReviewRequest


class GitHubApiError(RuntimeError):
    pass


class GitHubClient:
    """Small GitHub REST client. Tokens are passed explicitly and never logged."""

    def __init__(self, token: str, client: httpx.Client | None = None):
        if not token:
            raise ValueError("A GitHub token is required.")
        self._client = client or httpx.Client(timeout=30.0)
        self._owns_client = client is None
        self._headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2026-03-10",
        }

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def _get(self, path: str, params: dict | None = None):
        response = self._client.get(f"https://api.github.com{path}", headers=self._headers, params=params)
        if response.is_error:
            raise GitHubApiError(f"GitHub API request failed ({response.status_code}): {response.text[:500]}")
        return response.json()

    def fetch_pull_request(self, repository: str, pull_number: int) -> ReviewRequest:
        owner, name = repository.split("/", 1)
        pr = self._get(f"/repos/{owner}/{name}/pulls/{pull_number}")
        files: list[ChangedFile] = []
        page = 1
        while True:
            batch = self._get(
                f"/repos/{owner}/{name}/pulls/{pull_number}/files",
                params={"per_page": 100, "page": page},
            )
            if not isinstance(batch, list):
                raise GitHubApiError("Unexpected GitHub response while listing PR files.")
            for item in batch:
                files.append(
                    ChangedFile(
                        path=item["filename"],
                        status=item.get("status", "modified"),
                        patch=item.get("patch"),
                    )
                )
            if len(files) > settings.max_files_per_review:
                raise GitHubApiError(
                    f"Pull request changes {len(files)} files; configured limit is "
                    f"{settings.max_files_per_review}. Increase MAX_FILES_PER_REVIEW to review it."
                )
            total_patch_chars = sum(len(item.patch or "") for item in files)
            if total_patch_chars > settings.max_patch_chars:
                raise GitHubApiError(
                    "Pull request patches exceed MAX_PATCH_CHARS; raise the limit only "
                    "after considering processing cost and source-data exposure."
                )
            if len(batch) < 100:
                break
            page += 1
            if page > 31:
                break  # GitHub documents a maximum of 3,000 files per PR response.
        return ReviewRequest(
            repository=repository,
            pull_request=pull_number,
            title=pr.get("title", ""),
            body=pr.get("body") or "",
            head_sha=pr.get("head", {}).get("sha", ""),
            files=files,
        )

    def upsert_summary_comment(self, repository: str, pull_number: int, body: str) -> str:
        owner, name = repository.split("/", 1)
        comments = []
        for page in range(1, 101):
            batch = self._get(
                f"/repos/{owner}/{name}/issues/{pull_number}/comments",
                params={"per_page": 100, "page": page},
            )
            if not isinstance(batch, list):
                raise GitHubApiError("Unexpected GitHub response while listing PR comments.")
            comments.extend(batch)
            if len(batch) < 100:
                break
        marker = "<!-- ai-code-review-pr-agent -->"
        existing = next(
            (item for item in comments if marker in (item.get("body") or "")), None
        )
        if existing:
            response = self._client.patch(
                f"https://api.github.com/repos/{owner}/{name}/issues/comments/{existing['id']}",
                headers=self._headers,
                json={"body": body},
            )
            action = "updated"
        else:
            response = self._client.post(
                f"https://api.github.com/repos/{owner}/{name}/issues/{pull_number}/comments",
                headers=self._headers,
                json={"body": body},
            )
            action = "created"
        if response.is_error:
            raise GitHubApiError(f"Could not {action} PR summary comment ({response.status_code}): {response.text[:500]}")
        return action
