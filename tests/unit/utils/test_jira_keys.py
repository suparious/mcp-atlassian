"""Unit tests for Jira key extraction utilities."""

import pytest

from mcp_atlassian.utils.jira_keys import (
    JIRA_KEY_PATTERN,
    DevelopmentIdentifier,
    JiraKeyMatch,
    extract_jira_keys,
    get_jira_keys_from_text,
    parse_development_identifier,
)


class TestJiraKeyPattern:
    """Tests for the JIRA_KEY_PATTERN regex."""

    @pytest.mark.parametrize(
        "key",
        [
            "PROJ-123",
            "ABC-1",
            "TEAM_NAME-9999",
            "AB-1",  # Minimum 2 chars for project key
            "TEST123-456",
            "MY_PROJECT-1",
            "X1-99",
        ],
    )
    def test_valid_jira_keys_match(self, key: str):
        """Test that valid Jira keys are matched."""
        match = JIRA_KEY_PATTERN.match(key)
        assert match is not None
        assert match.group(1) == key

    @pytest.mark.parametrize(
        "invalid_key",
        [
            "proj-123",  # lowercase
            "123-456",  # starts with number
            "_PROJ-123",  # starts with underscore
            "PROJ123",  # no hyphen
            "PROJ-",  # no number after hyphen
            "-123",  # no project key
            "PROJ-ABC",  # letters after hyphen
        ],
    )
    def test_invalid_jira_keys_no_match(self, invalid_key: str):
        """Test that invalid keys don't match."""
        match = JIRA_KEY_PATTERN.match(invalid_key)
        assert match is None

    def test_findall_multiple_keys_in_text(self):
        """Test finding multiple keys in a text."""
        text = "Fix for PROJ-123 and TEST-456. Also see ABC-1."
        matches = JIRA_KEY_PATTERN.findall(text)
        assert matches == ["PROJ-123", "TEST-456", "ABC-1"]

    def test_word_boundary_matching(self):
        """Test that keys are matched at word boundaries."""
        text = "The issue PROJ-123 is related to NOTAPROJ-999abc"
        matches = JIRA_KEY_PATTERN.findall(text)
        # NOTAPROJ-999 should not match because it's followed by 'abc'
        assert "PROJ-123" in matches


class TestExtractJiraKeys:
    """Tests for the extract_jira_keys function."""

    def test_extract_from_title_highest_confidence(self):
        """Test that keys in title have confidence 1.0."""
        matches = extract_jira_keys(title="PROJ-123: Fix the bug")
        assert len(matches) == 1
        assert matches[0].key == "PROJ-123"
        assert matches[0].source == "title"
        assert matches[0].confidence == 1.0

    def test_extract_from_branch_high_confidence(self):
        """Test that keys in branch have confidence 0.9."""
        matches = extract_jira_keys(branch_name="feature/PROJ-123-fix-bug")
        assert len(matches) == 1
        assert matches[0].key == "PROJ-123"
        assert matches[0].source == "branch"
        assert matches[0].confidence == 0.9

    def test_extract_from_description_lower_confidence(self):
        """Test that keys in description have confidence 0.7."""
        matches = extract_jira_keys(description="Related to PROJ-123")
        assert len(matches) == 1
        assert matches[0].key == "PROJ-123"
        assert matches[0].source == "description"
        assert matches[0].confidence == 0.7

    def test_deduplication_keeps_highest_confidence(self):
        """Test that same key from multiple sources keeps highest confidence."""
        matches = extract_jira_keys(
            title="PROJ-123: Fix bug",
            description="This fixes PROJ-123",
            branch_name="feature/PROJ-123",
        )
        assert len(matches) == 1
        assert matches[0].key == "PROJ-123"
        assert matches[0].source == "title"
        assert matches[0].confidence == 1.0

    def test_multiple_different_keys_sorted_by_confidence(self):
        """Test multiple keys from different sources are sorted by confidence."""
        matches = extract_jira_keys(
            title="PROJ-100",
            description="Also fixes ABC-200 and DEF-300",
            branch_name="feature/XYZ-400",
        )
        # Should be sorted by confidence, then by key
        assert len(matches) == 4
        assert matches[0].key == "PROJ-100"  # title, 1.0
        assert matches[0].confidence == 1.0
        assert matches[1].key == "XYZ-400"  # branch, 0.9
        assert matches[1].confidence == 0.9
        # Description keys (0.7) sorted alphabetically
        assert matches[2].confidence == 0.7
        assert matches[3].confidence == 0.7

    def test_empty_inputs(self):
        """Test with all empty/None inputs."""
        matches = extract_jira_keys(title=None, description=None, branch_name=None)
        assert matches == []

    def test_no_keys_found(self):
        """Test when no Jira keys are present."""
        matches = extract_jira_keys(
            title="Just a regular title",
            description="No issues here",
            branch_name="feature/some-feature",
        )
        assert matches == []

    def test_case_insensitivity(self):
        """Test that lowercase keys in input are converted to uppercase."""
        matches = extract_jira_keys(title="proj-123: fix bug")
        assert len(matches) == 1
        assert matches[0].key == "PROJ-123"

    def test_branch_with_slashes(self):
        """Test branch names with multiple slashes."""
        matches = extract_jira_keys(branch_name="feature/team/PROJ-123-description")
        assert len(matches) == 1
        assert matches[0].key == "PROJ-123"


class TestParseDevelopmentIdentifier:
    """Tests for the parse_development_identifier function."""

    def test_parse_jira_issue_simple(self):
        """Test parsing a simple Jira issue key."""
        result = parse_development_identifier("PROJ-123")
        assert result.type == "jira"
        assert result.issue_key == "PROJ-123"
        assert result.project_key is None
        assert result.repo_slug is None
        assert result.pr_id is None

    def test_parse_jira_issue_with_underscore(self):
        """Test parsing Jira key with underscore in project."""
        result = parse_development_identifier("MY_PROJECT-456")
        assert result.type == "jira"
        assert result.issue_key == "MY_PROJECT-456"

    def test_parse_jira_issue_lowercase_input(self):
        """Test that lowercase Jira keys are uppercased."""
        result = parse_development_identifier("proj-123")
        assert result.type == "jira"
        assert result.issue_key == "PROJ-123"

    def test_parse_bitbucket_pr(self):
        """Test parsing a Bitbucket PR reference."""
        result = parse_development_identifier("PROJ/my-repo#456")
        assert result.type == "bitbucket"
        assert result.project_key == "PROJ"
        assert result.repo_slug == "my-repo"
        assert result.pr_id == 456
        assert result.issue_key is None

    def test_parse_bitbucket_repo_only(self):
        """Test parsing a Bitbucket repo without PR."""
        result = parse_development_identifier("PROJ/my-repo")
        assert result.type == "bitbucket"
        assert result.project_key == "PROJ"
        assert result.repo_slug == "my-repo"
        assert result.pr_id is None

    def test_parse_bitbucket_with_dots_in_repo(self):
        """Test parsing repo slug with dots."""
        result = parse_development_identifier("PROJ/my.repo.name#123")
        assert result.type == "bitbucket"
        assert result.repo_slug == "my.repo.name"
        assert result.pr_id == 123

    def test_parse_bitbucket_with_underscores_in_repo(self):
        """Test parsing repo slug with underscores."""
        result = parse_development_identifier("PROJ/my_repo_name#789")
        assert result.type == "bitbucket"
        assert result.repo_slug == "my_repo_name"

    def test_empty_identifier_raises(self):
        """Test that empty identifier raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            parse_development_identifier("")

    def test_whitespace_only_raises(self):
        """Test that whitespace-only identifier raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            parse_development_identifier("   ")

    def test_invalid_format_raises(self):
        """Test that unrecognized format raises ValueError."""
        with pytest.raises(ValueError, match="Unrecognized identifier format"):
            parse_development_identifier("not-a-valid-identifier")

    def test_invalid_jira_format_raises(self):
        """Test that invalid Jira-like format raises ValueError."""
        with pytest.raises(ValueError, match="Unrecognized identifier format"):
            parse_development_identifier("123-PROJ")  # Numbers first

    def test_bitbucket_case_normalization(self):
        """Test that Bitbucket project key is uppercased, repo slug lowercased."""
        result = parse_development_identifier("proj/My-Repo#123")
        assert result.project_key == "PROJ"
        assert result.repo_slug == "my-repo"


class TestGetJiraKeysFromText:
    """Tests for the get_jira_keys_from_text utility function."""

    def test_extract_multiple_keys(self):
        """Test extracting multiple keys from text."""
        text = "Fix PROJ-123, related to ABC-456 and DEF-789"
        keys = get_jira_keys_from_text(text)
        assert sorted(keys) == ["ABC-456", "DEF-789", "PROJ-123"]

    def test_deduplicate_repeated_keys(self):
        """Test that repeated keys are deduplicated."""
        text = "PROJ-123 mentioned here and PROJ-123 mentioned again"
        keys = get_jira_keys_from_text(text)
        assert keys == ["PROJ-123"]

    def test_empty_text(self):
        """Test with empty text."""
        assert get_jira_keys_from_text("") == []
        assert get_jira_keys_from_text(None) == []

    def test_no_keys(self):
        """Test with text containing no keys."""
        keys = get_jira_keys_from_text("Just some regular text with no issue keys")
        assert keys == []

    def test_sorted_output(self):
        """Test that output is sorted alphabetically."""
        text = "ZZZ-999 AAA-111 MMM-555"
        keys = get_jira_keys_from_text(text)
        assert keys == ["AAA-111", "MMM-555", "ZZZ-999"]


class TestJiraKeyMatchDataclass:
    """Tests for the JiraKeyMatch dataclass."""

    def test_create_jira_key_match(self):
        """Test creating a JiraKeyMatch instance."""
        match = JiraKeyMatch(key="PROJ-123", source="title", confidence=1.0)
        assert match.key == "PROJ-123"
        assert match.source == "title"
        assert match.confidence == 1.0

    def test_jira_key_match_equality(self):
        """Test JiraKeyMatch equality."""
        match1 = JiraKeyMatch(key="PROJ-123", source="title", confidence=1.0)
        match2 = JiraKeyMatch(key="PROJ-123", source="title", confidence=1.0)
        assert match1 == match2


class TestDevelopmentIdentifierDataclass:
    """Tests for the DevelopmentIdentifier dataclass."""

    def test_create_jira_identifier(self):
        """Test creating a Jira-type identifier."""
        ident = DevelopmentIdentifier(type="jira", issue_key="PROJ-123")
        assert ident.type == "jira"
        assert ident.issue_key == "PROJ-123"
        assert ident.project_key is None
        assert ident.repo_slug is None
        assert ident.pr_id is None

    def test_create_bitbucket_identifier(self):
        """Test creating a Bitbucket-type identifier."""
        ident = DevelopmentIdentifier(
            type="bitbucket",
            project_key="PROJ",
            repo_slug="my-repo",
            pr_id=456,
        )
        assert ident.type == "bitbucket"
        assert ident.project_key == "PROJ"
        assert ident.repo_slug == "my-repo"
        assert ident.pr_id == 456
        assert ident.issue_key is None
