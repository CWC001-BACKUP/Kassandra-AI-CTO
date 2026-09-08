from app.services.github import _parse_link_last_page


def test_parse_link_last_page() -> None:
    link = (
        '<https://api.github.com/repos/o/r/commits?per_page=100&page=2>; rel="next", '
        '<https://api.github.com/repos/o/r/commits?per_page=100&page=5>; rel="last"'
    )
    assert _parse_link_last_page(link) == 5


def test_parse_link_last_page_missing() -> None:
    assert _parse_link_last_page("") is None
