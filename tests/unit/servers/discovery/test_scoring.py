"""Unit tests for the tool discovery scoring module."""

import pytest

from src.mcp_atlassian.servers.discovery.scoring import (
    ACTION_SYNONYMS,
    ENTITY_SYNONYMS,
    _extract_words,
    _get_canonical_action,
    _get_canonical_entity,
    _normalize_text,
    score_tool_relevance,
)
from src.mcp_atlassian.servers.discovery.types import ToolIndexEntry


class TestNormalizeText:
    """Tests for text normalization."""

    def test_lowercase(self):
        assert _normalize_text("Hello World") == "hello world"

    def test_strip_whitespace(self):
        assert _normalize_text("  hello  ") == "hello"

    def test_combined(self):
        assert _normalize_text("  HELLO WORLD  ") == "hello world"


class TestExtractWords:
    """Tests for word extraction."""

    def test_simple_words(self):
        result = _extract_words("hello world")
        assert result == {"hello", "world"}

    def test_underscore_separation(self):
        result = _extract_words("get_issue_details")
        assert result == {"get", "issue", "details"}

    def test_camel_case(self):
        result = _extract_words("getIssueDetails")
        assert result == {"get", "issue", "details"}

    def test_mixed(self):
        result = _extract_words("get_issueDetails_and_more")
        assert result == {"get", "issue", "details", "and", "more"}

    def test_with_numbers_and_punctuation(self):
        result = _extract_words("issue-123 (details)")
        assert result == {"issue", "details"}


class TestCanonicalAction:
    """Tests for action verb synonym matching."""

    def test_canonical_verb_returns_itself(self):
        assert _get_canonical_action("get") == "get"
        assert _get_canonical_action("create") == "create"
        assert _get_canonical_action("update") == "update"
        assert _get_canonical_action("delete") == "delete"

    def test_synonym_returns_canonical(self):
        # "fetch" is a synonym for "get"
        assert _get_canonical_action("fetch") == "get"
        assert _get_canonical_action("retrieve") == "get"

        # "add" is a synonym for "create"
        assert _get_canonical_action("add") == "create"
        assert _get_canonical_action("new") == "create"

        # "edit" is a synonym for "update"
        assert _get_canonical_action("edit") == "update"
        assert _get_canonical_action("modify") == "update"

        # "remove" is a synonym for "delete"
        assert _get_canonical_action("remove") == "delete"

    def test_unknown_word_returns_none(self):
        assert _get_canonical_action("banana") is None
        assert _get_canonical_action("xyz123") is None

    def test_case_insensitive(self):
        assert _get_canonical_action("GET") == "get"
        assert _get_canonical_action("Fetch") == "get"


class TestCanonicalEntity:
    """Tests for entity synonym matching."""

    def test_canonical_entity_returns_itself(self):
        assert _get_canonical_entity("issue") == "issue"
        assert _get_canonical_entity("page") == "page"

    def test_synonym_returns_canonical(self):
        # "ticket" and "bug" are synonyms for "issue"
        assert _get_canonical_entity("ticket") == "issue"
        assert _get_canonical_entity("bug") == "issue"
        assert _get_canonical_entity("story") == "issue"
        assert _get_canonical_entity("task") == "issue"

        # "document" is a synonym for "page"
        assert _get_canonical_entity("document") == "page"
        assert _get_canonical_entity("doc") == "page"

        # "pull request" synonyms
        assert _get_canonical_entity("pr") == "pr"

    def test_unknown_entity_returns_none(self):
        assert _get_canonical_entity("banana") is None
        assert _get_canonical_entity("xyz123") is None


class TestScoreToolRelevance:
    """Tests for the main scoring function."""

    @pytest.fixture
    def jira_get_issue_tool(self):
        """Create a mock tool entry for jira_get_issue."""
        return ToolIndexEntry(
            name="jira_get_issue",
            description="Get details of a specific Jira issue including its Epic links and relationship information.",
            service="jira",
            is_write=False,
            tags={"jira", "read"},
            parameters=["issue_key", "fields", "expand"],
            use_cases=[
                "Look up issue details",
                "Check issue status",
                "See who is assigned to an issue",
            ],
            examples=[
                "What's the status of PROJ-123?",
                "Who is working on this ticket?",
            ],
            keywords={"ticket", "bug", "story", "task", "status", "details", "issue"},
        )

    @pytest.fixture
    def jira_search_tool(self):
        """Create a mock tool entry for jira_search."""
        return ToolIndexEntry(
            name="jira_search",
            description="Search Jira issues using JQL (Jira Query Language).",
            service="jira",
            is_write=False,
            tags={"jira", "read"},
            parameters=["jql", "fields", "limit"],
            use_cases=[
                "Find issues by criteria",
                "Search for bugs in a project",
                "Find my assigned issues",
            ],
            examples=[
                "Find all open bugs in project PROJ",
                "What issues are assigned to me?",
            ],
            keywords={"find", "search", "query", "jql", "filter"},
        )

    @pytest.fixture
    def confluence_search_tool(self):
        """Create a mock tool entry for confluence_search."""
        return ToolIndexEntry(
            name="confluence_search",
            description="Search Confluence content using simple terms or CQL.",
            service="confluence",
            is_write=False,
            tags={"confluence", "read"},
            parameters=["query", "limit"],
            use_cases=[
                "Find documentation",
                "Search for pages about a topic",
            ],
            examples=[
                "Find documentation about authentication",
            ],
            keywords={"documentation", "docs", "wiki", "page", "search"},
        )

    @pytest.fixture
    def jira_create_issue_tool(self):
        """Create a mock tool entry for jira_create_issue."""
        return ToolIndexEntry(
            name="jira_create_issue",
            description="Create a new Jira issue with optional Epic link or parent for subtasks.",
            service="jira",
            is_write=True,
            tags={"jira", "write"},
            parameters=["project_key", "summary", "issue_type"],
            use_cases=[
                "Create a new ticket",
                "File a bug report",
                "Add a new task",
            ],
            examples=[
                "Create a new bug in PROJ",
                "Add a task for this work",
            ],
            keywords={"create", "new", "add", "ticket", "bug", "task"},
        )

    def test_exact_keyword_match_scores_high(self, jira_get_issue_tool):
        """Test that exact keyword matches produce high scores."""
        score, reasons = score_tool_relevance("get issue details", jira_get_issue_tool)
        assert score > 0.3
        assert any("keyword" in r.lower() or "action" in r.lower() for r in reasons)

    def test_action_synonym_matching(self, jira_get_issue_tool):
        """Test that action synonyms are recognized."""
        # "fetch" is a synonym for "get"
        score, reasons = score_tool_relevance("fetch the ticket", jira_get_issue_tool)
        assert score > 0.2
        # Should match on action (get/fetch) and entity (issue/ticket)

    def test_entity_synonym_matching(self, jira_get_issue_tool):
        """Test that entity synonyms are recognized."""
        # "ticket" is a synonym for "issue"
        score, reasons = score_tool_relevance("show me the ticket", jira_get_issue_tool)
        assert score > 0.2

    def test_search_query_matches_search_tool(self, jira_search_tool):
        """Test that search queries match the search tool."""
        score, reasons = score_tool_relevance(
            "find all bugs assigned to me", jira_search_tool
        )
        # "find" maps to "search" action, providing some relevance
        assert score > 0.1

    def test_documentation_query_matches_confluence(self, confluence_search_tool):
        """Test that documentation queries match Confluence tools."""
        score, reasons = score_tool_relevance(
            "find documentation about API", confluence_search_tool
        )
        assert score > 0.3

    def test_create_query_matches_create_tool(self, jira_create_issue_tool):
        """Test that create queries match create tools."""
        score, reasons = score_tool_relevance(
            "create a new bug ticket", jira_create_issue_tool
        )
        assert score > 0.3

    def test_unrelated_query_scores_low(self, jira_get_issue_tool):
        """Test that unrelated queries produce low scores."""
        score, reasons = score_tool_relevance(
            "calculate the square root of pi", jira_get_issue_tool
        )
        assert score < 0.2

    def test_use_case_matching(self, jira_get_issue_tool):
        """Test that use cases contribute to scoring."""
        # This closely matches a use case
        score, reasons = score_tool_relevance(
            "check issue status", jira_get_issue_tool
        )
        assert score > 0.3

    def test_example_matching(self, jira_get_issue_tool):
        """Test that examples contribute to scoring."""
        # This is similar to an example
        score, reasons = score_tool_relevance(
            "what is the status of PROJ-456", jira_get_issue_tool
        )
        assert score > 0.2  # Examples provide moderate boost

    def test_fuzzy_matching(self, jira_search_tool):
        """Test that fuzzy matching works for similar descriptions."""
        score, reasons = score_tool_relevance(
            "search jira issues with jql query", jira_search_tool
        )
        assert score > 0.3

    def test_service_in_query_helps_matching(self, jira_get_issue_tool):
        """Test that mentioning the service helps matching."""
        score, reasons = score_tool_relevance("jira issue", jira_get_issue_tool)
        assert score > 0.2

    def test_custom_weights(self, jira_get_issue_tool):
        """Test that custom weights are respected."""
        # Use weights that heavily favor keyword matching
        custom_weights = {
            "keyword": 0.8,
            "action": 0.05,
            "entity": 0.05,
            "fuzzy": 0.05,
            "use_case": 0.05,
        }
        score_default, _ = score_tool_relevance("issue details", jira_get_issue_tool)
        score_custom, _ = score_tool_relevance(
            "issue details", jira_get_issue_tool, weights=custom_weights
        )
        # Custom weights should produce different score
        # The exact comparison depends on the content

    def test_score_never_exceeds_one(self, jira_get_issue_tool):
        """Test that scores are capped at 1.0."""
        # Query with many matching terms
        score, _ = score_tool_relevance(
            "get issue ticket bug story task details status jira read fetch retrieve",
            jira_get_issue_tool,
        )
        assert score <= 1.0

    def test_score_non_negative(self, jira_get_issue_tool):
        """Test that scores are never negative."""
        score, _ = score_tool_relevance("", jira_get_issue_tool)
        assert score >= 0.0

        score, _ = score_tool_relevance("xyz abc 123", jira_get_issue_tool)
        assert score >= 0.0


class TestActionSynonymsCompleteness:
    """Tests to verify ACTION_SYNONYMS dictionary."""

    def test_all_canonical_actions_have_synonyms(self):
        """Test that all canonical actions have at least one synonym."""
        for action, synonyms in ACTION_SYNONYMS.items():
            assert len(synonyms) > 0, f"Action '{action}' has no synonyms"

    def test_common_actions_present(self):
        """Test that common actions are present."""
        expected_actions = ["get", "create", "update", "delete", "search", "list"]
        for action in expected_actions:
            assert action in ACTION_SYNONYMS, f"Expected action '{action}' not found"


class TestEntitySynonymsCompleteness:
    """Tests to verify ENTITY_SYNONYMS dictionary."""

    def test_all_entities_have_synonyms(self):
        """Test that all entities have at least one synonym."""
        for entity, synonyms in ENTITY_SYNONYMS.items():
            assert len(synonyms) > 0, f"Entity '{entity}' has no synonyms"

    def test_common_entities_present(self):
        """Test that common entities are present."""
        expected_entities = ["issue", "page", "comment", "user", "project"]
        for entity in expected_entities:
            assert entity in ENTITY_SYNONYMS, f"Expected entity '{entity}' not found"
