import pytest

from app.services.intro import check_intro_message
from app.services.webhooks import verify_github_signature


def test_verify_github_signature_valid() -> None:
    import hashlib
    import hmac

    secret = "test-secret"
    payload = b'{"ref":"refs/heads/main"}'
    sig = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    assert verify_github_signature(payload, sig, secret) is True


def test_verify_github_signature_invalid() -> None:
    assert verify_github_signature(b"{}", "sha256=bad", "secret") is False


@pytest.mark.parametrize(
    "message",
    ["hi", "thanks", "who are you", "help"],
)
def test_intro_still_works(message: str) -> None:
    assert check_intro_message(message) is not None
