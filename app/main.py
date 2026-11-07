import secrets
from uuid import UUID

from fastapi import Depends, FastAPI, Header, HTTPException, Query

from app.config import settings
from app.engine import run_review
from app.models import ApiReviewResponse, HealthResponse, ReviewRequest, ReviewResult
from app.store import ReviewStore

app = FastAPI(
    title="AI Code Review & Pull Request Agent",
    version="0.1.0",
    description="Guarded pull request review using changed-line static checks and optional structured LLM analysis.",
)
store = ReviewStore(settings.database_path)


def verify_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if settings.api_key and not secrets.compare_digest(x_api_key or "", settings.api_key):
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")


@app.get("/health", response_model=HealthResponse, tags=["meta"])
def health() -> HealthResponse:
    return HealthResponse(status="ok", version="0.1.0")


@app.post("/api/reviews", response_model=ApiReviewResponse, dependencies=[Depends(verify_api_key)], tags=["reviews"])
def create_review(payload: ReviewRequest) -> ApiReviewResponse:
    if len(payload.files) > settings.max_files_per_review:
        raise HTTPException(status_code=413, detail="Too many changed files for one review.")
    patch_size = sum(len(item.patch or "") for item in payload.files)
    if patch_size > settings.max_patch_chars:
        raise HTTPException(status_code=413, detail="Combined PR patch exceeds configured size limit.")
    try:
        result = run_review(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Review provider failed: {type(exc).__name__}") from exc
    store.save(result)
    return ApiReviewResponse(review_id=result.review_id, status="completed", result=result)


@app.get("/api/reviews", response_model=list[ReviewResult], dependencies=[Depends(verify_api_key)], tags=["reviews"])
def list_reviews(limit: int = Query(default=20, ge=1, le=100)) -> list[ReviewResult]:
    return store.recent(limit)


@app.get("/api/reviews/{review_id}", response_model=ReviewResult, dependencies=[Depends(verify_api_key)], tags=["reviews"])
def get_review(review_id: UUID) -> ReviewResult:
    result = store.get(review_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Review not found.")
    return result
