from app.models import ChangedFile, ReviewRequest
from app.reviewer import build_result
from app.store import ReviewStore


def test_review_store_round_trip(tmp_path) -> None:
    store = ReviewStore(str(tmp_path / "reviews.db"))
    request = ReviewRequest(
        repository="owner/repo",
        pull_request=5,
        files=[ChangedFile(path="a.py", patch="@@ -0,0 +1 @@\n+eval(value)\n")],
    )
    result = build_result(request, "rules")
    store.save(result)
    fetched = store.get(result.review_id)
    assert fetched is not None
    assert fetched.review_id == result.review_id
    assert fetched.summary.total_findings == 1
    assert store.recent(5)[0].review_id == result.review_id
