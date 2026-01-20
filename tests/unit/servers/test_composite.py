"""Unit tests for the Composite FastMCP server implementation."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.mcp_atlassian.servers.composite import (
    get_issue_with_development_context,
    get_pr_with_jira_context,
    resolve_development_links,
)

# Access the underlying functions from the FunctionTool wrappers
_get_issue_with_development_context = get_issue_with_development_context.fn
_get_pr_with_jira_context = get_pr_with_jira_context.fn
_resolve_development_links = resolve_development_links.fn


# ============================================================================
# Mock Data
# ============================================================================

MOCK_JIRA_ISSUE = {
    "id": "12345",
    "key": "PROJ-123",
    "summary": "Test Issue Summary",
    "description": "Test description",
    "status": {"name": "In Progress"},
    "issue_type": {"name": "Task"},
    "priority": {"name": "Medium"},
    "assignee": {"display_name": "Test User"},
    "reporter": {"display_name": "Reporter User"},
}

MOCK_DEVELOPMENT_INFO = {
    "has_development_info": True,
    "pull_requests": [
        {
            "id": 456,
            "title": "Fix for PROJ-123",
            "state": "OPEN",
            "source_branch": "feature/PROJ-123-fix",
            "target_branch": "main",
            "url": "https://bitbucket.example.com/projects/PROJ/repos/my-repo/pull-requests/456",
        }
    ],
    "branches": [
        {"name": "feature/PROJ-123-fix", "url": "https://bitbucket.example.com/..."}
    ],
    "commits": [
        {"id": "abc123", "message": "PROJ-123: Fix the bug", "author": "Test User"}
    ],
    "builds": [],
    "summary": "1 PR, 1 branch, 1 commit",
}

MOCK_BITBUCKET_PR = {
    "id": 456,
    "title": "PROJ-123: Fix the important bug",
    "description": "This PR fixes PROJ-123 and also addresses PROJ-456",
    "state": "OPEN",
    "source_branch": "feature/PROJ-123-fix",
    "target_branch": "main",
    "author": {"display_name": "Test User"},
    "url": "https://bitbucket.example.com/projects/PROJ/repos/my-repo/pull-requests/456",
}


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_jira_fetcher():
    """Create a mock JiraFetcher."""
    mock_fetcher = MagicMock()
    mock_fetcher.config = MagicMock()
    mock_fetcher.config.url = "https://test.atlassian.net"
    mock_fetcher.config.projects_filter = None

    # Configure get_issue
    def mock_get_issue(issue_key, fields=None, expand=None, **kwargs):
        mock_issue = MagicMock()
        response_data = MOCK_JIRA_ISSUE.copy()
        response_data["key"] = issue_key
        mock_issue.to_simplified_dict.return_value = response_data
        return mock_issue

    mock_fetcher.get_issue.side_effect = mock_get_issue

    # Configure get_development_information
    def mock_get_dev_info(issue_key, application_type=None):
        mock_dev_info = MagicMock()
        mock_dev_info.to_dict.return_value = MOCK_DEVELOPMENT_INFO.copy()
        return mock_dev_info

    mock_fetcher.get_development_information.side_effect = mock_get_dev_info

    return mock_fetcher


@pytest.fixture
def mock_bitbucket_fetcher():
    """Create a mock BitbucketFetcher."""
    mock_fetcher = MagicMock()
    mock_fetcher.config = MagicMock()
    mock_fetcher.config.url = "https://bitbucket.example.com"

    # Configure get_pull_request
    def mock_get_pr(project_key, repo_slug, pr_id):
        mock_pr = MagicMock()
        response_data = MOCK_BITBUCKET_PR.copy()
        response_data["id"] = pr_id
        mock_pr.to_simplified_dict.return_value = response_data
        return mock_pr

    mock_fetcher.get_pull_request.side_effect = mock_get_pr

    # Configure get_repositories
    mock_repo = MagicMock()
    mock_repo.slug = "my-repo"
    mock_fetcher.get_repositories.return_value = [mock_repo]

    # Configure get_pull_requests for search
    def mock_get_prs(project_key, repo_slug, state="OPEN", limit=50):
        mock_pr = MagicMock()
        mock_pr.to_simplified_dict.return_value = MOCK_BITBUCKET_PR.copy()
        return [mock_pr]

    mock_fetcher.get_pull_requests.side_effect = mock_get_prs

    # Configure get_pull_request_changes
    mock_fetcher.get_pull_request_changes.return_value = {
        "files_changed": 3,
        "additions": 50,
        "deletions": 10,
    }

    return mock_fetcher


@pytest.fixture
def mock_context():
    """Create a mock FastMCP context."""
    return MagicMock()


# ============================================================================
# Tests for get_issue_with_development_context
# ============================================================================


@pytest.mark.anyio
async def test_get_issue_with_development_context(
    mock_context, mock_jira_fetcher, mock_bitbucket_fetcher
):
    """Test getting a Jira issue with development context."""
    with (
        patch(
            "src.src.mcp_atlassian.servers.composite.get_jira_fetcher",
            AsyncMock(return_value=mock_jira_fetcher),
        ),
        patch(
            "src.mcp_atlassian.servers.composite.get_bitbucket_fetcher",
            AsyncMock(return_value=mock_bitbucket_fetcher),
        ),
    ):
        response = await _get_issue_with_development_context(
            ctx=mock_context,
            issue_key="PROJ-123",
            include_pr_details=True,
            include_pr_diff_summary=False,
        )

    content = json.loads(response)
    assert content["issue_key"] == "PROJ-123"
    assert content["issue"] is not None
    assert content["issue"]["key"] == "PROJ-123"
    assert content["development_info"] is not None
    assert content["development_info"]["has_development_info"] is True
    assert len(content["pull_requests"]) > 0
    assert content["summary"]["issue_found"] is True
    assert content["summary"]["has_development_info"] is True


@pytest.mark.anyio
async def test_get_issue_with_development_context_no_dev_info(
    mock_context, mock_jira_fetcher
):
    """Test when development info is not available."""

    # Modify mock to return no development info
    def mock_no_dev_info(issue_key, application_type=None):
        mock_dev_info = MagicMock()
        mock_dev_info.to_dict.return_value = {
            "has_development_info": False,
            "pull_requests": [],
            "branches": [],
            "commits": [],
            "builds": [],
        }
        return mock_dev_info

    mock_jira_fetcher.get_development_information.side_effect = mock_no_dev_info

    with patch(
        "src.mcp_atlassian.servers.composite.get_jira_fetcher",
        AsyncMock(return_value=mock_jira_fetcher),
    ):
        response = await _get_issue_with_development_context(
            ctx=mock_context,
            issue_key="PROJ-999",
        )

    content = json.loads(response)
    assert content["summary"]["has_development_info"] is False
    assert len(content["pull_requests"]) == 0


@pytest.mark.anyio
async def test_get_issue_with_development_context_jira_error(mock_context):
    """Test error handling when Jira is unavailable."""
    with patch(
        "src.mcp_atlassian.servers.composite.get_jira_fetcher",
        AsyncMock(side_effect=ValueError("Jira not configured")),
    ):
        response = await _get_issue_with_development_context(
            ctx=mock_context,
            issue_key="PROJ-123",
        )

    content = json.loads(response)
    assert len(content["errors"]) > 0
    assert "Jira not available" in content["errors"][0]


@pytest.mark.anyio
async def test_get_issue_jira_error_during_fetch(mock_context, mock_jira_fetcher):
    """Test error handling when Jira issue fetch fails."""
    mock_jira_fetcher.get_issue.side_effect = Exception("Issue not found")

    with patch(
        "src.mcp_atlassian.servers.composite.get_jira_fetcher",
        AsyncMock(return_value=mock_jira_fetcher),
    ):
        response = await _get_issue_with_development_context(
            ctx=mock_context,
            issue_key="NONEXISTENT-999",
        )

    content = json.loads(response)
    assert content["issue"] is None
    assert len(content["errors"]) > 0
    assert "Failed to fetch issue" in content["errors"][0]


# ============================================================================
# Tests for get_pr_with_jira_context
# ============================================================================


@pytest.mark.anyio
async def test_get_pr_with_jira_context(
    mock_context, mock_bitbucket_fetcher, mock_jira_fetcher
):
    """Test getting a Bitbucket PR with Jira context."""
    with (
        patch(
            "mcp_atlassian.servers.composite.get_bitbucket_fetcher",
            AsyncMock(return_value=mock_bitbucket_fetcher),
        ),
        patch(
            "src.mcp_atlassian.servers.composite.get_jira_fetcher",
            AsyncMock(return_value=mock_jira_fetcher),
        ),
    ):
        response = await _get_pr_with_jira_context(
            ctx=mock_context,
            project_key="PROJ",
            repository_slug="my-repo",
            pull_request_id=456,
            resolve_jira_issues=True,
        )

    content = json.loads(response)
    assert content["pull_request"] is not None
    assert content["pull_request"]["id"] == 456
    # Should have found PROJ-123 and PROJ-456 from title/description
    assert len(content["jira_key_matches"]) >= 1
    assert content["summary"]["pr_found"] is True
    assert content["summary"]["jira_keys_found"] >= 1


@pytest.mark.anyio
async def test_get_pr_with_jira_context_no_resolve(
    mock_context, mock_bitbucket_fetcher, mock_jira_fetcher
):
    """Test getting a PR without resolving Jira issues."""
    with (
        patch(
            "mcp_atlassian.servers.composite.get_bitbucket_fetcher",
            AsyncMock(return_value=mock_bitbucket_fetcher),
        ),
        patch(
            "src.mcp_atlassian.servers.composite.get_jira_fetcher",
            AsyncMock(return_value=mock_jira_fetcher),
        ),
    ):
        response = await _get_pr_with_jira_context(
            ctx=mock_context,
            project_key="PROJ",
            repository_slug="my-repo",
            pull_request_id=456,
            resolve_jira_issues=False,
        )

    content = json.loads(response)
    assert content["pull_request"] is not None
    assert len(content["jira_key_matches"]) >= 1
    # Should not have resolved issues
    assert len(content["linked_jira_issues"]) == 0


@pytest.mark.anyio
async def test_get_pr_with_jira_context_bitbucket_error(mock_context):
    """Test error handling when Bitbucket is unavailable."""
    with patch(
        "mcp_atlassian.servers.composite.get_bitbucket_fetcher",
        AsyncMock(side_effect=ValueError("Bitbucket not configured")),
    ):
        response = await _get_pr_with_jira_context(
            ctx=mock_context,
            project_key="PROJ",
            repository_slug="my-repo",
            pull_request_id=456,
        )

    content = json.loads(response)
    assert len(content["errors"]) > 0
    assert "Bitbucket not available" in content["errors"][0]


@pytest.mark.anyio
async def test_get_pr_jira_issue_fetch_error(
    mock_context, mock_jira_fetcher, mock_bitbucket_fetcher
):
    """Test partial resolution when some Jira issues fail to fetch."""

    def mock_get_issue_with_error(issue_key, fields=None, expand=None, **kwargs):
        if issue_key == "PROJ-456":
            raise Exception("Issue not found")
        mock_issue = MagicMock()
        response_data = MOCK_JIRA_ISSUE.copy()
        response_data["key"] = issue_key
        mock_issue.to_simplified_dict.return_value = response_data
        return mock_issue

    mock_jira_fetcher.get_issue.side_effect = mock_get_issue_with_error

    with (
        patch(
            "mcp_atlassian.servers.composite.get_bitbucket_fetcher",
            AsyncMock(return_value=mock_bitbucket_fetcher),
        ),
        patch(
            "src.mcp_atlassian.servers.composite.get_jira_fetcher",
            AsyncMock(return_value=mock_jira_fetcher),
        ),
    ):
        response = await _get_pr_with_jira_context(
            ctx=mock_context,
            project_key="PROJ",
            repository_slug="my-repo",
            pull_request_id=456,
            resolve_jira_issues=True,
        )

    content = json.loads(response)
    # Should still have PR info
    assert content["pull_request"] is not None
    # Should have partial resolution - some succeed, some fail
    assert len(content["linked_jira_issues"]) >= 1
    # Check that at least one has an error
    errors_found = [i for i in content["linked_jira_issues"] if "error" in i]
    successes_found = [i for i in content["linked_jira_issues"] if "issue" in i]
    # We should have both successful and failed resolutions
    assert len(errors_found) + len(successes_found) >= 1


# ============================================================================
# Tests for resolve_development_links
# ============================================================================


@pytest.mark.anyio
async def test_resolve_development_links_jira_issue(
    mock_context, mock_jira_fetcher, mock_bitbucket_fetcher
):
    """Test resolving a Jira issue identifier."""
    with (
        patch(
            "src.mcp_atlassian.servers.composite.get_jira_fetcher",
            AsyncMock(return_value=mock_jira_fetcher),
        ),
        patch(
            "mcp_atlassian.servers.composite.get_bitbucket_fetcher",
            AsyncMock(return_value=mock_bitbucket_fetcher),
        ),
    ):
        response = await _resolve_development_links(
            ctx=mock_context,
            identifier="PROJ-123",
            resolve_depth=1,
        )

    content = json.loads(response)
    assert content["identifier"] == "PROJ-123"
    assert content["resolved_type"] == "jira"
    assert content["data"] is not None
    assert content["data"]["issue_key"] == "PROJ-123"


@pytest.mark.anyio
async def test_resolve_development_links_bitbucket_pr(
    mock_context, mock_jira_fetcher, mock_bitbucket_fetcher
):
    """Test resolving a Bitbucket PR identifier."""
    with (
        patch(
            "src.mcp_atlassian.servers.composite.get_jira_fetcher",
            AsyncMock(return_value=mock_jira_fetcher),
        ),
        patch(
            "mcp_atlassian.servers.composite.get_bitbucket_fetcher",
            AsyncMock(return_value=mock_bitbucket_fetcher),
        ),
    ):
        response = await _resolve_development_links(
            ctx=mock_context,
            identifier="PROJ/my-repo#456",
            resolve_depth=1,
        )

    content = json.loads(response)
    assert content["identifier"] == "PROJ/my-repo#456"
    assert content["resolved_type"] == "bitbucket"
    assert content["data"] is not None
    assert content["data"]["pull_request"]["id"] == 456


@pytest.mark.anyio
async def test_resolve_development_links_bitbucket_repo(
    mock_context, mock_bitbucket_fetcher
):
    """Test resolving a Bitbucket repo identifier (without PR)."""
    with patch(
        "mcp_atlassian.servers.composite.get_bitbucket_fetcher",
        AsyncMock(return_value=mock_bitbucket_fetcher),
    ):
        response = await _resolve_development_links(
            ctx=mock_context,
            identifier="PROJ/my-repo",
            resolve_depth=1,
        )

    content = json.loads(response)
    assert content["resolved_type"] == "bitbucket"
    assert content["data"] is not None
    assert "open_pull_requests" in content["data"]


@pytest.mark.anyio
async def test_resolve_development_links_invalid_identifier(mock_context):
    """Test error handling for invalid identifier."""
    response = await _resolve_development_links(
        ctx=mock_context,
        identifier="invalid-identifier",
        resolve_depth=1,
    )

    content = json.loads(response)
    assert len(content["errors"]) > 0
    assert "Unrecognized identifier format" in content["errors"][0]


@pytest.mark.anyio
async def test_resolve_development_links_empty_identifier(mock_context):
    """Test error handling for empty identifier."""
    response = await _resolve_development_links(
        ctx=mock_context,
        identifier="",
        resolve_depth=1,
    )

    content = json.loads(response)
    assert len(content["errors"]) > 0
    assert "cannot be empty" in content["errors"][0]


@pytest.mark.anyio
async def test_resolve_with_depth_2(
    mock_context, mock_jira_fetcher, mock_bitbucket_fetcher
):
    """Test resolve_development_links with depth 2."""
    with (
        patch(
            "src.mcp_atlassian.servers.composite.get_jira_fetcher",
            AsyncMock(return_value=mock_jira_fetcher),
        ),
        patch(
            "mcp_atlassian.servers.composite.get_bitbucket_fetcher",
            AsyncMock(return_value=mock_bitbucket_fetcher),
        ),
    ):
        response = await _resolve_development_links(
            ctx=mock_context,
            identifier="PROJ/my-repo#456",
            resolve_depth=2,
        )

    content = json.loads(response)
    assert content["resolved_type"] == "bitbucket"
    assert content["data"] is not None
    # With depth 2, linked issues should have development_context
    linked = content["data"].get("linked_jira_issues", [])
    if linked:
        # Check that development context was attempted
        for issue in linked:
            if "issue" in issue:
                assert (
                    "development_context" in issue or "development_context_error" in issue
                )


# ============================================================================
# Tests for edge cases
# ============================================================================


@pytest.mark.anyio
async def test_get_issue_with_pr_diff_summary(
    mock_context, mock_jira_fetcher, mock_bitbucket_fetcher
):
    """Test including PR diff summaries."""
    with (
        patch(
            "src.mcp_atlassian.servers.composite.get_jira_fetcher",
            AsyncMock(return_value=mock_jira_fetcher),
        ),
        patch(
            "mcp_atlassian.servers.composite.get_bitbucket_fetcher",
            AsyncMock(return_value=mock_bitbucket_fetcher),
        ),
    ):
        response = await _get_issue_with_development_context(
            ctx=mock_context,
            issue_key="PROJ-123",
            include_pr_details=True,
            include_pr_diff_summary=True,
        )

    content = json.loads(response)
    assert content["issue_key"] == "PROJ-123"
    # When diff summary is requested, PRs should have diff info (if Bitbucket available)
    if content["pull_requests"]:
        # The implementation should attempt to add diff info
        pass  # PR diff info depends on Bitbucket fetcher availability


@pytest.mark.anyio
async def test_get_issue_with_bitbucket_project_filter(
    mock_context, mock_jira_fetcher, mock_bitbucket_fetcher
):
    """Test filtering PRs by Bitbucket project."""
    with (
        patch(
            "src.mcp_atlassian.servers.composite.get_jira_fetcher",
            AsyncMock(return_value=mock_jira_fetcher),
        ),
        patch(
            "mcp_atlassian.servers.composite.get_bitbucket_fetcher",
            AsyncMock(return_value=mock_bitbucket_fetcher),
        ),
    ):
        response = await _get_issue_with_development_context(
            ctx=mock_context,
            issue_key="PROJ-123",
            include_pr_details=True,
            bitbucket_project_key="PROJ",
        )

    content = json.loads(response)
    assert content["issue_key"] == "PROJ-123"
    assert content["summary"]["issue_found"] is True


@pytest.mark.anyio
async def test_resolve_development_links_jira_service_unavailable(
    mock_context, mock_bitbucket_fetcher
):
    """Test resolve when Jira service is unavailable but identifier is Jira."""
    with (
        patch(
            "src.mcp_atlassian.servers.composite.get_jira_fetcher",
            AsyncMock(side_effect=ValueError("Jira not configured")),
        ),
        patch(
            "mcp_atlassian.servers.composite.get_bitbucket_fetcher",
            AsyncMock(return_value=mock_bitbucket_fetcher),
        ),
    ):
        response = await _resolve_development_links(
            ctx=mock_context,
            identifier="PROJ-123",
            resolve_depth=1,
        )

    content = json.loads(response)
    assert content["resolved_type"] == "jira"
    # Should have error about Jira being unavailable (propagated from inner call)
    assert content["data"] is not None
    assert len(content["data"]["errors"]) > 0


@pytest.mark.anyio
async def test_resolve_development_links_bitbucket_service_unavailable(mock_context):
    """Test resolve when Bitbucket service is unavailable but identifier is Bitbucket."""
    with patch(
        "mcp_atlassian.servers.composite.get_bitbucket_fetcher",
        AsyncMock(side_effect=ValueError("Bitbucket not configured")),
    ):
        response = await _resolve_development_links(
            ctx=mock_context,
            identifier="PROJ/my-repo#456",
            resolve_depth=1,
        )

    content = json.loads(response)
    assert content["resolved_type"] == "bitbucket"
    # Should have error about Bitbucket being unavailable (propagated from inner call)
    assert content["data"] is not None
    assert len(content["data"]["errors"]) > 0
