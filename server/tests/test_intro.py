import pytest

from app.services.intro import IntroIntent, check_intro_message


@pytest.mark.parametrize(
    ("message", "intent"),
    [
        ("hi", IntroIntent.GREETING),
        ("Hello there!", IntroIntent.GREETING),
        ("Hey!", IntroIntent.GREETING),
        ("good morning", IntroIntent.GREETING),
        ("thanks!", IntroIntent.THANKS),
        ("thank you so much", IntroIntent.THANKS),
        ("appreciate it", IntroIntent.THANKS),
        ("bye", IntroIntent.FAREWELL),
        ("goodbye", IntroIntent.FAREWELL),
        ("how are you", IntroIntent.HOW_ARE_YOU),
        ("who are you", IntroIntent.WHO_ARE_YOU),
        ("help", IntroIntent.HELP),
        ("what can you do", IntroIntent.WHO_ARE_YOU),
    ],
)
def test_intro_messages_detected(message: str, intent: IntroIntent) -> None:
    match = check_intro_message(message)
    assert match is not None
    assert match.intent == intent
    assert len(match.response) > 10


def test_intro_uses_user_name() -> None:
    match = check_intro_message("hello", user_name="Ada")
    assert match is not None
    assert "Ada" in match.response


def test_continuation_with_greeting_not_intro() -> None:
    match = check_intro_message(
        "hi, lets continue from where we left off in the last conversation"
    )
    assert match is None


def test_engineering_question_not_intro() -> None:
    match = check_intro_message("Why did we choose PostgreSQL for the payments service?")
    assert match is None


def test_long_message_not_intro() -> None:
    match = check_intro_message("hi " + "there " * 20)
    assert match is None
