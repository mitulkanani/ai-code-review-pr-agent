# AI Code Review & Pull Request Agent

A GitHub-integrated code review starter that analyzes **changed lines only**, flags risky patterns, optionally asks an LLM for additional findings, and publishes an idempotent review summary comment on a pull request.

The project is intentionally conservative: static checks are deterministic, LLM findings must point to an added line in the supplied diff, and the GitHub Actions workflow checks out the trusted base commit instead of executing untrusted PR code.

## What it includes

- GitHub REST client to fetch PR metadata and paginated changed-file patches.
- Unified-diff parser that maps findings to added-file line numbers.
- Static security and bug checks for common risky patterns (exposed key formats, hard-coded credentials, TLS verification disabled, shell execution, `eval`, SQL string interpolation, and swallowed exceptions).
- Optional OpenAI structured-output reviewer. Common secrets are redacted before sending changed-line patches to the external provider.
- Validation that discards LLM findings pointing outside the PR's added lines, unknown paths, or below the confidence threshold.
- Markdown report with severity, location, explanation, recommendation, and confidence.
- GitHub PR summary comment that updates the existing agent comment instead of creating a new one every run.
- FastAPI API with SQLite review history and optional API-key protection.
- CLI, Docker, CI, and a GitHub Actions PR workflow.

## Architecture

```text
GitHub pull_request event
        |
        v
GitHub Actions (trusted base revision)
        |
        +---- GitHub REST API: PR metadata + changed file patches
        |
        v
Diff parser ---- added lines with new-file line numbers
        |
        +---- deterministic rule engine
        |
        +---- optional OpenAI structured review (redacted patches)
        |
        v
Finding validation (path + added-line + confidence checks)
        |
        v
Markdown report ---- GitHub PR summary comment / Actions artifact
```

The FastAPI service exposes the same review engine for internal integrations:

```text
POST /api/reviews -> analyze request -> SQLite history
GET  /api/reviews -> list latest results
GET  /api/reviews/{review_id} -> one result
```

## Quick start

Python 3.11 or newer is required.

```bash
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows PowerShell
# .venv\\Scripts\\Activate.ps1

python -m pip install -e ".[dev]"
pytest
uvicorn app.main:app --reload
```

API docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

## Review a GitHub pull request from your terminal

Create a GitHub token with repository **Pull requests: read** permission. Add **Issues: write** only when you want the CLI to publish/update its summary comment. Export it as `GITHUB_TOKEN` or `GH_TOKEN`.

```bash
export GITHUB_TOKEN="github_pat_your_token"
pr-review-agent review-pr --repo OWNER/REPOSITORY --pr 123 --output review.md
```

Publish/update one summary comment:

```bash
pr-review-agent review-pr --repo OWNER/REPOSITORY --pr 123 --post-comment
```

Fail the command when findings meet a severity threshold:

```bash
pr-review-agent review-pr --repo OWNER/REPOSITORY --pr 123 --fail-on high
```

The default provider is `rules`, which does not transmit source code to an external model. To enable the optional LLM reviewer:

```bash
export REVIEW_PROVIDER=openai
export OPENAI_API_KEY="your_api_key"
export OPENAI_MODEL="gpt-4.1-mini"
pr-review-agent review-pr --repo OWNER/REPOSITORY --pr 123 --provider openai
```

**Privacy:** OpenAI mode sends redacted PR diff content to the OpenAI API. Secret redaction is best-effort, not a guarantee. Review your data-handling requirements before enabling this for private repositories. Do not use it for code that must remain on-premises.

## GitHub Actions integration

The included `.github/workflows/ai-pr-review.yml` runs on pull request opened, synchronized, reopened, and ready-for-review events.

1. Copy the workflow into your repository's `.github/workflows/` directory (it is already included in this project).
2. Ensure GitHub Actions is enabled.
3. The default `REVIEW_PROVIDER` is `rules`. No OpenAI key is required.
4. The workflow posts/updates a summary comment and uploads `review.md` as an artifact.

Required workflow permissions:

- `contents: read` to check out the base revision.
- `pull-requests: read` to fetch PR metadata and changed files.
- `issues: write` to create/update the PR conversation summary comment.

The workflow intentionally checks out `${{ github.event.pull_request.base.sha }}`, not the PR head. It retrieves changed files through the GitHub API and does not execute code from the PR. This reduces the risk of running untrusted fork code with a token that can write comments.

For pull requests from forks, GitHub commonly restricts the provided `GITHUB_TOKEN` to read-only access. In that case the report artifact is still produced, while the comment operation may be denied; the CLI handles that as a non-fatal publishing warning.

To enable the OpenAI provider in Actions, add `OPENAI_API_KEY` as a repository secret, then set repository variable `REVIEW_PROVIDER` to `openai`. This sends redacted diff content to the configured model. Keep the default `rules` provider when external model processing is not approved.

## API usage

```bash
curl -X POST http://127.0.0.1:8000/api/reviews \
  -H 'Content-Type: application/json' \
  -d @examples/review_request.json
```

If `API_KEY` is set, pass it using `-H 'X-API-Key: your-local-key'`.

The API stores results in `data/reviews.db` by default. Set `DATABASE_PATH` to change this location.

## Run with Docker

```bash
cp .env.example .env
# Set API_KEY and any approved provider credentials in .env
docker compose up --build
```

## Example output

For `examples/review_request.json`, the static rules should flag `requests.get(url, verify=False)` as a high-severity TLS-verification issue on the added line.

## Safety and limitations

- This is an advisory reviewer, not a security audit and not a merge authorization system.
- Static checks are heuristic and can produce false positives or miss vulnerabilities. They are designed to be explainable starting signals.
- LLM review is optional, may be wrong, and is constrained to changed lines, but validation cannot prove a reported issue is real.
- The LLM receives only patch text, after best-effort secret redaction. Redaction can miss proprietary or credential formats.
- The initial publisher creates one PR conversation summary comment; it does not submit formal inline review comments or approve/request changes on behalf of a human.
- Binary, generated, renamed, or very large files may not include a text patch and will be noted as unanalyzed.
- This starter limits each review to 100 changed files and a configurable combined patch-size ceiling (`MAX_FILES_PER_REVIEW`, `MAX_PATCH_CHARS`) to bound runtime and data exposure. GitHub itself can return more files per PR, but this project does not review an arbitrarily large diff by default.
- GitHub Actions permissions and fork restrictions are enforced by GitHub; comment publication is not guaranteed for fork PRs.
- The API key protects the demo API only. Add OAuth, tenant controls, rate limits, request-size limits at the edge, and production secret management before exposing it publicly.

## Upstream API references

- [GitHub REST API: list pull request files](https://docs.github.com/en/rest/pulls/pulls#list-pull-requests-files)
- [GitHub REST API: issue and pull request comments](https://docs.github.com/en/rest/issues/comments)
- [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)

## Project structure

```text
app/
  cli.py             # CLI entry point
  config.py          # Environment-based settings
  diff_parser.py     # Unified diff / added-line mapping
  engine.py           # Review provider orchestration
  github_client.py   # GitHub REST API integration
  main.py             # FastAPI endpoints
  models.py           # Pydantic request/result schemas
  providers.py        # Optional OpenAI structured reviewer + redaction
  reviewer.py         # Finding validation, aggregation, Markdown report
  rules.py            # Deterministic checks
  store.py            # SQLite review history
examples/
tests/
.github/workflows/
```

## License

MIT. See [LICENSE](LICENSE).
