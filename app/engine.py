from app.config import settings
from app.models import ReviewRequest, ReviewResult
from app.providers import OpenAIReviewProvider
from app.reviewer import build_result


def run_review(request: ReviewRequest, provider_name: str | None = None) -> ReviewResult:
    selected = (provider_name or settings.review_provider or "rules").lower()
    if selected == "rules":
        return build_result(request, provider_name="rules")
    if selected == "openai":
        provider = OpenAIReviewProvider(settings.openai_api_key, settings.openai_model)
        try:
            llm_findings = provider.review(request.files)
        finally:
            provider.close()
        return build_result(request, provider_name="openai", llm_findings=llm_findings)
    raise ValueError("Unsupported review provider. Choose 'rules' or 'openai'.")
