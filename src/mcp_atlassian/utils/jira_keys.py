"""Utilities for extracting and parsing Jira issue keys."""

import re
from dataclasses import dataclass

# Pattern matches: PROJ-123, ABC-1, A-1, TEAM_NAME-9999
# Jira project keys must start with a letter, optionally followed by letters, digits, or underscores
JIRA_KEY_PATTERN = re.compile(r'\b([A-Z][A-Z0-9_]*-\d+)\b')


@dataclass
class JiraKeyMatch:
    """A matched Jira issue key with confidence score."""

    key: str
    source: str  # "title", "description", "branch"
    confidence: float  # 0.0 to 1.0


def extract_jira_keys(
    title: str | None = None,
    description: str | None = None,
    branch_name: str | None = None,
) -> list[JiraKeyMatch]:
    """Extract Jira keys from PR title, description, and branch name.

    Keys found in title have highest confidence (1.0).
    Keys in branch name have high confidence (0.9).
    Keys in description have lower confidence (0.7).

    Returns deduplicated list sorted by confidence (highest first).

    Args:
        title: PR or commit title
        description: PR or commit description
        branch_name: Git branch name

    Returns:
        List of JiraKeyMatch objects sorted by confidence (highest first).
    """
    matches: dict[str, JiraKeyMatch] = {}

    # Extract from title (highest confidence)
    if title:
        for match in JIRA_KEY_PATTERN.finditer(title.upper()):
            key = match.group(1)
            if key not in matches or matches[key].confidence < 1.0:
                matches[key] = JiraKeyMatch(key=key, source="title", confidence=1.0)

    # Extract from branch name (high confidence)
    if branch_name:
        # Normalize branch name: replace common separators with spaces for matching
        normalized_branch = branch_name.upper().replace("/", " ").replace("-", " ")
        # Also try the original format as Jira keys can appear as feature/PROJ-123
        for text in [branch_name.upper(), normalized_branch]:
            for match in JIRA_KEY_PATTERN.finditer(text):
                key = match.group(1)
                if key not in matches or matches[key].confidence < 0.9:
                    matches[key] = JiraKeyMatch(
                        key=key, source="branch", confidence=0.9
                    )

    # Extract from description (lower confidence)
    if description:
        for match in JIRA_KEY_PATTERN.finditer(description.upper()):
            key = match.group(1)
            if key not in matches or matches[key].confidence < 0.7:
                matches[key] = JiraKeyMatch(
                    key=key, source="description", confidence=0.7
                )

    # Sort by confidence (highest first), then by key for deterministic order
    return sorted(
        matches.values(), key=lambda m: (-m.confidence, m.key)
    )


@dataclass
class DevelopmentIdentifier:
    """Parsed development identifier."""

    type: str  # "jira" or "bitbucket"
    # For Jira: issue_key
    # For Bitbucket: project_key, repo_slug, pr_id
    issue_key: str | None = None
    project_key: str | None = None
    repo_slug: str | None = None
    pr_id: int | None = None


def parse_development_identifier(identifier: str) -> DevelopmentIdentifier:
    """Parse smart identifier into structured format.

    Examples:
    - "PROJ-123" -> Jira issue
    - "PROJ/my-repo#456" -> Bitbucket PR
    - "PROJ/my-repo" -> Bitbucket repo (no PR)

    Args:
        identifier: Smart identifier string

    Returns:
        DevelopmentIdentifier with parsed components

    Raises:
        ValueError: If the identifier format is not recognized
    """
    identifier = identifier.strip()

    if not identifier:
        raise ValueError("Identifier cannot be empty")

    # Check for Bitbucket PR format: PROJECT/repo#123 or PROJECT/repo
    bitbucket_pattern = re.compile(
        r'^([A-Z][A-Z0-9_]*)/([a-z0-9][a-z0-9._-]*)(?:#(\d+))?$',
        re.IGNORECASE
    )
    bb_match = bitbucket_pattern.match(identifier)
    if bb_match:
        project_key = bb_match.group(1).upper()
        repo_slug = bb_match.group(2).lower()
        pr_id_str = bb_match.group(3)
        pr_id = int(pr_id_str) if pr_id_str else None
        return DevelopmentIdentifier(
            type="bitbucket",
            project_key=project_key,
            repo_slug=repo_slug,
            pr_id=pr_id,
        )

    # Check for Jira issue format: PROJ-123
    jira_match = JIRA_KEY_PATTERN.match(identifier.upper())
    if jira_match and jira_match.group(0) == identifier.upper():
        return DevelopmentIdentifier(
            type="jira",
            issue_key=identifier.upper(),
        )

    raise ValueError(
        f"Unrecognized identifier format: '{identifier}'. "
        "Expected 'PROJ-123' for Jira or 'PROJECT/repo#456' for Bitbucket PR."
    )


def get_jira_keys_from_text(text: str) -> list[str]:
    """Extract all Jira issue keys from arbitrary text.

    This is a simpler utility function that just returns the keys
    without confidence scores or source tracking.

    Args:
        text: Any text that may contain Jira issue keys

    Returns:
        List of unique Jira issue keys found in the text
    """
    if not text:
        return []

    keys = set()
    for match in JIRA_KEY_PATTERN.finditer(text.upper()):
        keys.add(match.group(1))

    return sorted(keys)
