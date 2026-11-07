import json

import httpx

from app.models import ChangedFile
from app.providers import OpenAIReviewProvider, redact_secrets


def test_redact_secrets_before_external_review() -> None:
    source = "token = 'ghp_abcdefghijklmnopqrstuvwxyz1234567890'\npassword = 'super-secret-value'"
    redacted = redact_secrets(source)
    assert "ghp_abcdefghijklmnopqrstuvwxyz" not in redacted
    assert "super-secret-value" not in redacted
    assert "[REDACTED_SECRET]" in redacted


def test_openai_provider_parses_structured_output_and_sends_redacted_patch() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen["body"] = body
        output = {
            "findings": [
                {
                    "category": "security",
                    "severity": "high",
                    "title": "Possible exposed credential",
                    "description": "A credential-like value is present in the changed line.",
                    "recommendation": "Rotate and move it to a secret store.",
                    "path": "settings.py",
                    "line": 1,
                    "confidence": 0.9,
                }
            ]
        }
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(output)}}]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenAIReviewProvider("test-key", client=client)
    result = provider.review([ChangedFile(path="settings.py", patch="@@ -1,0 +1 @@\n+api_key = 'sk-abcdefghijklmnopqrstuvwxyz1234'\n")])
    assert len(result) == 1
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in json.dumps(seen["body"])
    assert seen["body"]["response_format"]["type"] == "json_schema"
    client.close()
