from app.services.llm import is_llm_configured
from app.config import Settings


def test_is_llm_configured_false_when_missing() -> None:
    settings = Settings(
        llm_api_key="",
        llm_base_url="",
        llm_model="",
    )
    assert is_llm_configured(settings) is False


def test_is_llm_configured_true_when_set() -> None:
    settings = Settings(
        llm_api_key="sk-test",
        llm_base_url="https://api.openai.com/v1",
        llm_model="gpt-4o-mini",
    )
    assert is_llm_configured(settings) is True
