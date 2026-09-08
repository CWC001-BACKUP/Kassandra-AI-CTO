from app.services.github_activity import (
    format_activity_for_llm,
    format_deployments_block,
    format_workflow_runs_block,
)
from app.services.repo_context import (
    is_activity_overview_question,
    is_ci_question,
    is_deployment_question,
)


def test_deployment_question_detected() -> None:
    assert is_deployment_question("show me deployment logs")
    assert is_deployment_question("what was deployed to production?")


def test_ci_question_detected() -> None:
    assert is_ci_question("why did the build fail?")
    assert is_ci_question("show me github actions logs")


def test_activity_overview_detected() -> None:
    assert is_activity_overview_question("what's going on in this repo?")


def test_format_deployments_block() -> None:
    deployments = [
        {
            "environment": "production",
            "ref": "main",
            "sha": "abc1234",
            "creator": "alice",
            "time": "2h ago",
            "latest_status": {"state": "success", "description": "Deployed"},
        }
    ]
    text = format_deployments_block(deployments)
    assert "production" in text
    assert "success" in text


def test_format_activity_for_llm_includes_ci() -> None:
    activity = {
        "workflows": [{"name": "CI"}],
        "workflow_runs": [
            {
                "name": "CI",
                "branch": "main",
                "conclusion": "failure",
                "time": "1h ago",
                "actor": "bob",
                "head_sha": "deadbeef",
            }
        ],
        "failed_runs": [],
        "deployments": [],
        "releases": [],
        "branches": [{"name": "main", "sha": "abc", "protected": False}],
        "tags": [],
        "events": [],
        "environments": [],
    }
    text = format_activity_for_llm(activity)
    assert "CI/CD runs" in text
    assert "failure" in text
    assert "Branches" in text
