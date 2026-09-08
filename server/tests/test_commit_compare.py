from app.services.commit_compare import (
    compare_commits,
    format_commit_compare_block,
    normalize_path,
)


def test_normalize_path() -> None:
    assert normalize_path("./api/server.py") == "api/server.py"
    assert normalize_path("api//server.py") == "api/server.py"


def test_spec_example_19_and_1_with_one_shared() -> None:
    """89da7fb (19 files) vs 1a57fa1 (1 file) with api/server.py shared."""
    only_a_files = [
        "api/bridge_client.py",
        "api/config_store.py",
        "api/live_sync.py",
        "api/server.py",
        "api/trading_session.py",
        "backtest/engine.py",
        "config/accounts.yaml",
        "core/daily_targets.py",
        "core/multi_account/account_runner.py",
        "core/multi_timeframe.py",
        "core/position_manager.py",
        "core/signal_generator.py",
        "core/signal_generator_h4.py",
        "data/live_prices.py",
        "data/mt5_bars.py",
        "tests/test_mt5_bars.py",
        "tests/test_position_manager.py",
        "tests/test_signal_generator.py",
        "tests/test_trade_modes.py",
    ]
    detail_a = {
        "sha": "89da7fb",
        "short_sha": "89da7fb",
        "title": "AUto config",
        "date": "2026-07-22",
        "file_count": 19,
        "files": [{"filename": f} for f in only_a_files],
        "all_filenames": only_a_files,
    }
    detail_b = {
        "sha": "1a57fa1",
        "short_sha": "1a57fa1",
        "title": "auto trade settings and fixes to broken pipeline2",
        "date": "2026-07-03",
        "file_count": 1,
        "files": [{"filename": "api/server.py", "patch": "+added line"}],
        "all_filenames": ["api/server.py"],
        "has_diff": True,
    }

    result = compare_commits(detail_a, detail_b)
    assert result["valid"] is True
    counts = result["counts"]
    assert counts["total_a"] == 19
    assert counts["total_b"] == 1
    assert counts["overlap"] == 1
    assert counts["only_a"] == 18
    assert counts["only_b"] == 0
    assert "api/server.py" in result["overlap"]
    assert "api/server.py" not in result["only_a"]
    assert counts["only_a"] + counts["overlap"] == counts["total_a"]
    assert counts["only_b"] + counts["overlap"] == counts["total_b"]

    block = format_commit_compare_block(detail_a, detail_b)
    assert "Only in Commit A (unique to A, NOT including shared): 18" in block
    assert "Changed in both commits (shared): 1" in block
    assert "api/server.py" in block
    assert "only in A (19 total)" not in block.lower()


def test_format_commit_compare_block_two_disjoint_sets() -> None:
    detail_a = {
        "short_sha": "abc1234",
        "title": "commit A",
        "date": "2026-07-22",
        "file_count": 2,
        "files": [{"filename": "shared.py"}, {"filename": "only_a.py"}],
        "all_filenames": ["shared.py", "only_a.py"],
    }
    detail_b = {
        "short_sha": "def5678",
        "title": "commit B",
        "date": "2026-07-03",
        "file_count": 2,
        "files": [{"filename": "shared.py"}, {"filename": "only_b.py"}],
        "all_filenames": ["shared.py", "only_b.py"],
    }
    block = format_commit_compare_block(detail_a, detail_b)
    assert "FILES CHANGED IN BOTH" in block
    assert "FILES ONLY IN COMMIT A" in block
    assert "FILES ONLY IN COMMIT B" in block
    assert "only_a.py" in block
    assert "only_b.py" in block


def test_incomplete_file_list_fails_validation() -> None:
    detail_a = {
        "short_sha": "abc1234",
        "title": "A",
        "file_count": 5,
        "files": [{"filename": "a.py"}],
        "all_filenames": ["a.py"],
    }
    detail_b = {
        "short_sha": "def5678",
        "title": "B",
        "file_count": 1,
        "files": [{"filename": "b.py"}],
        "all_filenames": ["b.py"],
    }
    result = compare_commits(detail_a, detail_b)
    assert result["valid"] is False
    assert any("incomplete" in e.lower() for e in result["validation_errors"])
