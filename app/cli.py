import argparse
import os
from pathlib import Path
import sys

from app.github_client import GitHubApiError, GitHubClient
from app.engine import run_review
from app.reviewer import render_markdown


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Review a GitHub pull request.")
    sub = parser.add_subparsers(dest="command", required=True)
    review = sub.add_parser("review-pr", help="Fetch and review a GitHub pull request.")
    review.add_argument("--repo", required=True, help="Repository in owner/name format.")
    review.add_argument("--pr", type=int, required=True, help="Pull request number.")
    review.add_argument("--output", default="review.md", help="Markdown report output path.")
    review.add_argument("--post-comment", action="store_true", help="Create/update the agent's summary comment on the PR.")
    review.add_argument("--provider", choices=["rules", "openai"], default=None)
    review.add_argument("--fail-on", choices=["never", "critical", "high", "medium", "low"], default="never")
    return parser


def _should_fail(result, threshold: str) -> bool:
    if threshold == "never":
        return False
    ranks = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    limit = ranks[threshold]
    return any(ranks[item.severity.value] <= limit for item in result.findings)


def main() -> None:
    args = build_parser().parse_args()
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if not token:
        print("Set GITHUB_TOKEN or GH_TOKEN before running the GitHub CLI.", file=sys.stderr)
        raise SystemExit(2)

    client = GitHubClient(token)
    try:
        request = client.fetch_pull_request(args.repo, args.pr)
        result = run_review(request, provider_name=args.provider)
        report = render_markdown(result)
        Path(args.output).write_text(report + "\n", encoding="utf-8")
        print(report)
        if args.post_comment:
            try:
                action = client.upsert_summary_comment(args.repo, args.pr, report)
                print(f"\nGitHub PR summary comment {action}.")
            except GitHubApiError as exc:
                # Common for fork-origin PRs where GITHUB_TOKEN is read-only.
                print(f"\nCould not post PR comment; report remains in {args.output}: {exc}", file=sys.stderr)
        if _should_fail(result, args.fail_on):
            raise SystemExit(1)
    except GitHubApiError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc
    finally:
        client.close()


if __name__ == "__main__":
    main()
