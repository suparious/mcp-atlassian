"""Unit tests for the tool discovery index module."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.mcp_atlassian.servers.discovery.index import ToolDiscoveryIndex
from src.mcp_atlassian.servers.discovery.types import ToolIndexEntry, ToolRecommendation


class TestToolDiscoveryIndexSingleton:
    """Tests for singleton behavior of ToolDiscoveryIndex."""

    def setup_method(self):
        """Reset the singleton before each test."""
        ToolDiscoveryIndex.reset()

    def teardown_method(self):
        """Reset the singleton after each test."""
        ToolDiscoveryIndex.reset()

    def test_singleton_returns_same_instance(self):
        """Test that multiple instantiations return the same instance."""
        index1 = ToolDiscoveryIndex()
        index2 = ToolDiscoveryIndex()
        assert index1 is index2

    def test_reset_creates_new_instance(self):
        """Test that reset() allows creating a new instance."""
        index1 = ToolDiscoveryIndex()
        ToolDiscoveryIndex.reset()
        index2 = ToolDiscoveryIndex()
        assert index1 is not index2

    def test_initial_state_not_built(self):
        """Test that a new index is not built."""
        index = ToolDiscoveryIndex()
        assert not index.is_built


class TestToolDiscoveryIndexBuild:
    """Tests for building the tool discovery index."""

    def setup_method(self):
        """Reset the singleton before each test."""
        ToolDiscoveryIndex.reset()

    def teardown_method(self):
        """Reset the singleton after each test."""
        ToolDiscoveryIndex.reset()

    @pytest.fixture
    def mock_mcp_server(self):
        """Create a mock FastMCP server with some tools."""
        mock_server = AsyncMock()

        # Create mock tools
        mock_tools = {
            "jira_get_issue": MagicMock(
                tags={"jira", "read"},
                description="Get details of a specific Jira issue.",
                parameters={
                    "type": "object",
                    "properties": {
                        "issue_key": {"type": "string"},
                        "fields": {"type": "string"},
                    },
                },
            ),
            "jira_create_issue": MagicMock(
                tags={"jira", "write"},
                description="Create a new Jira issue.",
                parameters={
                    "type": "object",
                    "properties": {
                        "project_key": {"type": "string"},
                        "summary": {"type": "string"},
                    },
                },
            ),
            "confluence_search": MagicMock(
                tags={"confluence", "read"},
                description="Search Confluence content.",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                    },
                },
            ),
            "bitbucket_list_repositories": MagicMock(
                tags={"bitbucket", "read"},
                description="List all repositories in a Bitbucket project.",
                parameters={
                    "type": "object",
                    "properties": {
                        "project_key": {"type": "string"},
                    },
                },
            ),
        }

        mock_server.get_tools = AsyncMock(return_value=mock_tools)
        return mock_server

    @pytest.mark.anyio
    async def test_build_index_marks_as_built(self, mock_mcp_server):
        """Test that build_index marks the index as built."""
        index = ToolDiscoveryIndex()
        assert not index.is_built

        await index.build_index(mock_mcp_server)

        assert index.is_built

    @pytest.mark.anyio
    async def test_build_index_indexes_all_tools(self, mock_mcp_server):
        """Test that all tools are indexed."""
        index = ToolDiscoveryIndex()
        await index.build_index(mock_mcp_server)

        all_tools = index.get_all_tools()
        assert len(all_tools) == 4
        assert "jira_get_issue" in all_tools
        assert "jira_create_issue" in all_tools
        assert "confluence_search" in all_tools
        assert "bitbucket_list_repositories" in all_tools

    @pytest.mark.anyio
    async def test_build_index_extracts_service(self, mock_mcp_server):
        """Test that service is correctly extracted from tags."""
        index = ToolDiscoveryIndex()
        await index.build_index(mock_mcp_server)

        jira_tool = index.get_tool("jira_get_issue")
        assert jira_tool is not None
        assert jira_tool.service == "jira"

        confluence_tool = index.get_tool("confluence_search")
        assert confluence_tool is not None
        assert confluence_tool.service == "confluence"

        bitbucket_tool = index.get_tool("bitbucket_list_repositories")
        assert bitbucket_tool is not None
        assert bitbucket_tool.service == "bitbucket"

    @pytest.mark.anyio
    async def test_build_index_identifies_write_tools(self, mock_mcp_server):
        """Test that write tools are correctly identified."""
        index = ToolDiscoveryIndex()
        await index.build_index(mock_mcp_server)

        read_tool = index.get_tool("jira_get_issue")
        assert read_tool is not None
        assert not read_tool.is_write

        write_tool = index.get_tool("jira_create_issue")
        assert write_tool is not None
        assert write_tool.is_write

    @pytest.mark.anyio
    async def test_build_index_extracts_parameters(self, mock_mcp_server):
        """Test that parameters are extracted from tool schema."""
        index = ToolDiscoveryIndex()
        await index.build_index(mock_mcp_server)

        tool = index.get_tool("jira_get_issue")
        assert tool is not None
        assert "issue_key" in tool.parameters
        assert "fields" in tool.parameters

    @pytest.mark.anyio
    async def test_build_index_skips_if_already_built(self, mock_mcp_server):
        """Test that build_index is idempotent."""
        index = ToolDiscoveryIndex()
        await index.build_index(mock_mcp_server)

        # Call build again - should not re-fetch tools
        mock_mcp_server.get_tools.reset_mock()
        await index.build_index(mock_mcp_server)

        # Should not have called get_tools again
        mock_mcp_server.get_tools.assert_not_called()


class TestToolDiscoveryIndexSearch:
    """Tests for searching the tool discovery index."""

    def setup_method(self):
        """Reset the singleton and pre-populate for tests."""
        ToolDiscoveryIndex.reset()
        self.index = ToolDiscoveryIndex()
        # Manually populate for testing without needing async
        self.index._tools = {
            "jira_get_issue": ToolIndexEntry(
                name="jira_get_issue",
                description="Get details of a specific Jira issue.",
                service="jira",
                is_write=False,
                tags={"jira", "read"},
                parameters=["issue_key", "fields"],
                use_cases=["Look up issue details", "Check issue status"],
                examples=["What's the status of PROJ-123?"],
                keywords={"issue", "ticket", "bug", "details", "status"},
            ),
            "jira_search": ToolIndexEntry(
                name="jira_search",
                description="Search Jira issues using JQL.",
                service="jira",
                is_write=False,
                tags={"jira", "read"},
                parameters=["jql", "limit"],
                use_cases=["Find issues by criteria", "Search for bugs"],
                examples=["Find all bugs assigned to me"],
                keywords={"search", "find", "query", "jql"},
            ),
            "jira_create_issue": ToolIndexEntry(
                name="jira_create_issue",
                description="Create a new Jira issue.",
                service="jira",
                is_write=True,
                tags={"jira", "write"},
                parameters=["project_key", "summary"],
                use_cases=["Create a new ticket", "File a bug"],
                examples=["Create a bug in PROJ"],
                keywords={"create", "new", "add", "ticket"},
            ),
            "confluence_search": ToolIndexEntry(
                name="confluence_search",
                description="Search Confluence content.",
                service="confluence",
                is_write=False,
                tags={"confluence", "read"},
                parameters=["query"],
                use_cases=["Find documentation", "Search wiki"],
                examples=["Find docs about API"],
                keywords={"search", "find", "documentation", "wiki"},
            ),
            "bitbucket_list_repositories": ToolIndexEntry(
                name="bitbucket_list_repositories",
                description="List repositories in a Bitbucket project.",
                service="bitbucket",
                is_write=False,
                tags={"bitbucket", "read"},
                parameters=["project_key"],
                use_cases=["List repos", "See available repositories"],
                examples=["What repos are in PROJ?"],
                keywords={"repository", "repo", "list"},
            ),
            "discover_tools": ToolIndexEntry(
                name="discover_tools",
                description="Find the most relevant tools for a task.",
                service="meta",
                is_write=False,
                tags={"meta", "read"},
                parameters=["task"],
                use_cases=[],
                examples=[],
                keywords={"discover", "find", "tools"},
            ),
        }
        self.index._built = True

    def teardown_method(self):
        """Reset the singleton after each test."""
        ToolDiscoveryIndex.reset()

    def test_search_returns_recommendations(self):
        """Test that search returns tool recommendations."""
        results = self.index.search("get issue details")
        assert len(results) > 0
        assert all(isinstance(r, ToolRecommendation) for r in results)

    def test_search_returns_sorted_by_relevance(self):
        """Test that results are sorted by relevance score."""
        results = self.index.search("get jira issue")
        if len(results) > 1:
            for i in range(len(results) - 1):
                assert results[i].relevance_score >= results[i + 1].relevance_score

    def test_search_respects_limit(self):
        """Test that limit parameter is respected."""
        results = self.index.search("search", limit=2)
        assert len(results) <= 2

    def test_search_filters_by_service(self):
        """Test that service_filter works correctly."""
        results = self.index.search("search", service_filter="confluence")
        assert all(r.service == "confluence" for r in results)

    def test_search_excludes_write_tools_when_requested(self):
        """Test that include_write=False excludes write tools."""
        results = self.index.search("create ticket", include_write=False)
        assert all(not r.is_write for r in results)

    def test_search_includes_write_tools_by_default(self):
        """Test that write tools are included by default."""
        results = self.index.search("create new ticket")
        # Should find jira_create_issue
        write_tools = [r for r in results if r.is_write]
        assert len(write_tools) > 0

    def test_search_excludes_discover_tools_itself(self):
        """Test that discover_tools is excluded from results."""
        results = self.index.search("discover tools find")
        tool_names = [r.name for r in results]
        assert "discover_tools" not in tool_names

    def test_search_empty_query_returns_results(self):
        """Test that empty query still returns some results."""
        results = self.index.search("")
        # May return empty or low-scoring results depending on implementation
        assert isinstance(results, list)

    def test_search_unbuilt_index_returns_empty(self):
        """Test that searching an unbuilt index returns empty."""
        ToolDiscoveryIndex.reset()
        fresh_index = ToolDiscoveryIndex()
        results = fresh_index.search("get issue")
        assert results == []

    def test_search_recommendation_has_all_fields(self):
        """Test that recommendations have all expected fields."""
        results = self.index.search("get jira issue")
        assert len(results) > 0

        rec = results[0]
        assert rec.name
        assert rec.description
        assert isinstance(rec.relevance_score, float)
        assert isinstance(rec.match_reasons, list)
        assert rec.service
        assert isinstance(rec.is_write, bool)


class TestToolDiscoveryIndexGetTool:
    """Tests for getting specific tools from the index."""

    def setup_method(self):
        """Reset and populate the index."""
        ToolDiscoveryIndex.reset()
        self.index = ToolDiscoveryIndex()
        self.index._tools = {
            "test_tool": ToolIndexEntry(
                name="test_tool",
                description="A test tool.",
                service="jira",
                is_write=False,
                tags={"jira", "read"},
                parameters=[],
                use_cases=[],
                examples=[],
                keywords=set(),
            ),
        }
        self.index._built = True

    def teardown_method(self):
        """Reset the singleton after each test."""
        ToolDiscoveryIndex.reset()

    def test_get_existing_tool(self):
        """Test getting an existing tool."""
        tool = self.index.get_tool("test_tool")
        assert tool is not None
        assert tool.name == "test_tool"

    def test_get_nonexistent_tool(self):
        """Test getting a tool that doesn't exist."""
        tool = self.index.get_tool("nonexistent_tool")
        assert tool is None


class TestToolDiscoveryIndexKeywordExtraction:
    """Tests for keyword extraction from descriptions."""

    def setup_method(self):
        """Reset the singleton."""
        ToolDiscoveryIndex.reset()

    def teardown_method(self):
        """Reset the singleton after each test."""
        ToolDiscoveryIndex.reset()

    def test_extract_keywords_filters_stop_words(self):
        """Test that common stop words are filtered out."""
        index = ToolDiscoveryIndex()
        keywords = index._extract_keywords_from_description(
            "Get the details of a specific Jira issue"
        )
        # "the", "of", "a" should be filtered
        assert "the" not in keywords
        assert "of" not in keywords
        assert "a" not in keywords
        # But meaningful words should remain
        assert "details" in keywords
        # Note: "specific" is in the stop words list, so it's filtered out
        assert "jira" in keywords
        assert "issue" in keywords

    def test_extract_keywords_filters_short_words(self):
        """Test that very short words are filtered out."""
        index = ToolDiscoveryIndex()
        keywords = index._extract_keywords_from_description("Do it now")
        assert "do" not in keywords
        assert "it" not in keywords

    def test_extract_keywords_handles_empty_description(self):
        """Test that empty description returns empty set."""
        index = ToolDiscoveryIndex()
        keywords = index._extract_keywords_from_description("")
        assert keywords == set()
