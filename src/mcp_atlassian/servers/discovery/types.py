"""Data types for tool discovery."""

from dataclasses import dataclass, field


@dataclass
class ToolIndexEntry:
    """Indexed tool information for discovery."""

    name: str
    description: str
    service: str  # "jira", "confluence", "bitbucket", "composite"
    is_write: bool
    tags: set[str]
    parameters: list[str]
    use_cases: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    keywords: set[str] = field(default_factory=set)


@dataclass
class ToolRecommendation:
    """A recommended tool with relevance score."""

    name: str
    description: str
    relevance_score: float
    match_reasons: list[str]
    service: str
    is_write: bool
