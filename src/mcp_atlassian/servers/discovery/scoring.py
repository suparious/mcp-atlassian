"""Relevance scoring for tool discovery."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from thefuzz import fuzz

if TYPE_CHECKING:
    from .types import ToolIndexEntry

# Action verb synonyms - maps canonical verbs to their synonyms
ACTION_SYNONYMS: dict[str, list[str]] = {
    "get": ["fetch", "retrieve", "read", "find", "lookup", "show", "display", "view"],
    "create": ["add", "new", "make", "insert", "write", "post"],
    "update": ["edit", "modify", "change", "set", "patch", "alter"],
    "delete": ["remove", "destroy", "clear", "erase", "drop"],
    "search": ["find", "query", "lookup", "filter", "browse", "discover"],
    "list": ["show", "display", "enumerate", "fetch", "get"],
    "link": ["connect", "associate", "attach", "relate"],
    "transition": ["move", "change", "update", "progress"],
    "download": ["fetch", "get", "retrieve", "export"],
}

# Entity synonyms - maps canonical entities to their synonyms
ENTITY_SYNONYMS: dict[str, list[str]] = {
    "issue": ["ticket", "bug", "story", "task", "epic", "item", "work"],
    "page": ["document", "article", "doc", "content", "wiki"],
    "comment": ["note", "reply", "response", "remark", "feedback"],
    "pr": ["pull request", "merge request", "code review"],
    "pull_request": ["pr", "merge request", "code review"],
    "repo": ["repository", "project", "codebase"],
    "repository": ["repo", "project", "codebase"],
    "branch": ["ref", "version", "line"],
    "sprint": ["iteration", "cycle", "milestone"],
    "board": ["kanban", "scrum", "project board"],
    "label": ["tag", "category", "marker"],
    "attachment": ["file", "upload", "document"],
    "worklog": ["time", "hours", "time entry", "work log"],
    "transition": ["status", "workflow", "state change"],
    "version": ["release", "fix version", "milestone"],
    "user": ["person", "member", "assignee", "author"],
    "project": ["workspace", "space", "team"],
}

# Build reverse lookup for efficiency
# First pass: set all canonical keys to themselves (priority)
_ACTION_REVERSE: dict[str, str] = {}
for canonical in ACTION_SYNONYMS.keys():
    _ACTION_REVERSE[canonical] = canonical

# Second pass: add synonyms only if not already a canonical key
for canonical, synonyms in ACTION_SYNONYMS.items():
    for syn in synonyms:
        if syn not in _ACTION_REVERSE:
            _ACTION_REVERSE[syn] = canonical

# Same for entities
_ENTITY_REVERSE: dict[str, str] = {}
for canonical in ENTITY_SYNONYMS.keys():
    _ENTITY_REVERSE[canonical] = canonical

for canonical, synonyms in ENTITY_SYNONYMS.items():
    for syn in synonyms:
        if syn not in _ENTITY_REVERSE:
            _ENTITY_REVERSE[syn] = canonical


def _normalize_text(text: str) -> str:
    """Normalize text for comparison - lowercase and strip."""
    return text.lower().strip()


def _extract_words(text: str) -> set[str]:
    """Extract words from text, handling underscores and camelCase."""
    # Replace underscores with spaces
    text = text.replace("_", " ")
    # Insert spaces before capitals for camelCase
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    # Split on whitespace and punctuation
    words = re.findall(r"[a-zA-Z]+", text.lower())
    return set(words)


def _get_canonical_action(word: str) -> str | None:
    """Get the canonical action verb for a word, if it's an action."""
    return _ACTION_REVERSE.get(word.lower())


def _get_canonical_entity(word: str) -> str | None:
    """Get the canonical entity for a word, if it's an entity."""
    return _ENTITY_REVERSE.get(word.lower())


def score_tool_relevance(
    query: str,
    tool: ToolIndexEntry,
    weights: dict[str, float] | None = None,
) -> tuple[float, list[str]]:
    """Score how relevant a tool is to a query.

    Args:
        query: Natural language task description
        tool: Tool to score
        weights: Optional custom weights for scoring factors

    Returns:
        Tuple of (score 0.0-1.0, list of match reasons)
    """
    default_weights = {
        "keyword": 0.25,
        "action": 0.20,
        "entity": 0.25,
        "fuzzy": 0.20,
        "use_case": 0.10,
    }
    weights = weights or default_weights

    score = 0.0
    reasons: list[str] = []

    query_normalized = _normalize_text(query)
    query_words = _extract_words(query)

    # Extract words from tool name and description
    tool_name_words = _extract_words(tool.name)
    tool_desc_words = _extract_words(tool.description)
    all_tool_words = tool_name_words | tool_desc_words | tool.keywords

    # 1. Keyword matching (direct keyword hits)
    keyword_hits = query_words & all_tool_words
    if keyword_hits:
        keyword_score = min(1.0, len(keyword_hits) / max(1, len(query_words) / 2))
        score += weights["keyword"] * keyword_score
        if keyword_hits:
            reasons.append(f"keyword match: {', '.join(sorted(keyword_hits)[:3])}")

    # Also check for keyword matches with tool's explicit keywords
    explicit_keyword_hits = query_words & tool.keywords
    if explicit_keyword_hits:
        bonus = 0.1 * min(1.0, len(explicit_keyword_hits) / 2)
        score += bonus

    # 2. Action verb matching (with synonyms)
    query_actions = {
        _get_canonical_action(w) for w in query_words if _get_canonical_action(w)
    }
    tool_actions = {
        _get_canonical_action(w) for w in tool_name_words if _get_canonical_action(w)
    }

    action_matches = query_actions & tool_actions
    if action_matches:
        action_score = min(1.0, len(action_matches))
        score += weights["action"] * action_score
        reasons.append(f"action match: {', '.join(sorted(action_matches))}")

    # 3. Entity matching (with synonyms)
    query_entities = {
        _get_canonical_entity(w) for w in query_words if _get_canonical_entity(w)
    }
    tool_entities = {
        _get_canonical_entity(w)
        for w in (tool_name_words | tool_desc_words)
        if _get_canonical_entity(w)
    }
    # Also include service as an entity
    tool_entities.add(tool.service)

    entity_matches = query_entities & tool_entities
    if entity_matches:
        entity_score = min(1.0, len(entity_matches))
        score += weights["entity"] * entity_score
        reasons.append(f"entity match: {', '.join(sorted(entity_matches))}")

    # 4. Fuzzy description matching using thefuzz
    # Compare query to tool description
    fuzzy_ratio = fuzz.partial_ratio(query_normalized, tool.description.lower())
    if fuzzy_ratio > 60:  # Only count significant fuzzy matches
        fuzzy_score = (fuzzy_ratio - 60) / 40.0  # Normalize 60-100 to 0-1
        score += weights["fuzzy"] * fuzzy_score
        if fuzzy_ratio > 75:
            reasons.append(f"description similarity: {fuzzy_ratio}%")

    # Also check tool name fuzzy match
    name_fuzzy = fuzz.ratio(query_normalized, tool.name.lower().replace("_", " "))
    if name_fuzzy > 50:
        name_bonus = (name_fuzzy - 50) / 100.0  # Small bonus for name match
        score += name_bonus * 0.1

    # 5. Use case matching
    if tool.use_cases:
        best_use_case_score = 0.0
        best_use_case = ""
        for use_case in tool.use_cases:
            use_case_ratio = fuzz.partial_ratio(query_normalized, use_case.lower())
            if use_case_ratio > best_use_case_score:
                best_use_case_score = use_case_ratio
                best_use_case = use_case

        if best_use_case_score > 70:
            use_case_score = (best_use_case_score - 70) / 30.0
            score += weights["use_case"] * use_case_score
            if best_use_case_score > 80:
                reasons.append(f"use case: '{best_use_case}'")

    # 6. Example matching (bonus)
    if tool.examples:
        for example in tool.examples:
            example_ratio = fuzz.partial_ratio(query_normalized, example.lower())
            if example_ratio > 80:
                score += 0.05  # Small bonus for example match
                reasons.append(f"similar to example: '{example[:40]}...'")
                break

    return min(1.0, score), reasons
