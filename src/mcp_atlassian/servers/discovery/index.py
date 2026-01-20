"""Tool index for discovery."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from .metadata import TOOL_ENHANCEMENTS
from .scoring import score_tool_relevance
from .types import ToolIndexEntry, ToolRecommendation

if TYPE_CHECKING:
    from fastmcp import FastMCP

logger = logging.getLogger("mcp-atlassian.discovery")


class ToolDiscoveryIndex:
    """Singleton index of all available tools."""

    _instance: ToolDiscoveryIndex | None = None
    _tools: dict[str, ToolIndexEntry]
    _built: bool

    def __new__(cls) -> ToolDiscoveryIndex:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._tools = {}
            cls._instance._built = False
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance. Useful for testing."""
        cls._instance = None

    @property
    def is_built(self) -> bool:
        """Check if the index has been built."""
        return self._built

    def _extract_keywords_from_description(self, description: str) -> set[str]:
        """Extract meaningful keywords from a tool description."""
        # Common words to filter out
        stop_words = {
            "the",
            "a",
            "an",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "must",
            "shall",
            "can",
            "to",
            "of",
            "in",
            "for",
            "on",
            "with",
            "at",
            "by",
            "from",
            "as",
            "into",
            "through",
            "during",
            "before",
            "after",
            "above",
            "below",
            "between",
            "under",
            "again",
            "further",
            "then",
            "once",
            "here",
            "there",
            "when",
            "where",
            "why",
            "how",
            "all",
            "each",
            "few",
            "more",
            "most",
            "other",
            "some",
            "such",
            "no",
            "nor",
            "not",
            "only",
            "own",
            "same",
            "so",
            "than",
            "too",
            "very",
            "just",
            "and",
            "or",
            "but",
            "if",
            "because",
            "while",
            "although",
            "this",
            "that",
            "these",
            "those",
            "it",
            "its",
            "they",
            "them",
            "their",
            "which",
            "who",
            "whom",
            "whose",
            "what",
            "e",
            "g",
            "eg",
            "ie",
            "etc",
            "args",
            "ctx",
            "returns",
            "raises",
            "optional",
            "default",
            "none",
            "true",
            "false",
            "string",
            "json",
            "object",
            "list",
            "dict",
            "int",
            "float",
            "bool",
            "representing",
            "specified",
            "specific",
            "fastmcp",
            "context",
        }

        # Extract words
        words = re.findall(r"[a-zA-Z]+", description.lower())

        # Filter and return meaningful keywords
        return {w for w in words if len(w) > 2 and w not in stop_words}

    def _determine_service(self, tags: set[str]) -> str:
        """Determine the service from tool tags."""
        if "jira" in tags:
            return "jira"
        elif "confluence" in tags:
            return "confluence"
        elif "bitbucket" in tags:
            return "bitbucket"
        elif "meta" in tags:
            return "meta"
        else:
            return "composite"

    async def build_index(self, mcp_server: FastMCP) -> None:
        """Build index from MCP server's registered tools.

        Args:
            mcp_server: The FastMCP server instance to index tools from.
        """
        if self._built:
            logger.debug("Index already built, skipping rebuild")
            return

        logger.info("Building tool discovery index...")

        # Get all tools from the server (includes mounted sub-servers)
        all_tools = await mcp_server.get_tools()

        for registered_name, tool_obj in all_tools.items():
            tags = tool_obj.tags or set()
            description = tool_obj.description or ""

            # Determine service and write status
            service = self._determine_service(tags)
            is_write = "write" in tags

            # Extract parameter names
            parameters = []
            if tool_obj.parameters:
                # FastMCP tool parameters are in JSON schema format
                schema = tool_obj.parameters
                if isinstance(schema, dict) and "properties" in schema:
                    parameters = list(schema["properties"].keys())

            # Get enhancement metadata if available
            enhancement = TOOL_ENHANCEMENTS.get(registered_name, {})
            use_cases = list(enhancement.get("use_cases", []))
            examples = list(enhancement.get("examples", []))
            extra_keywords = set(enhancement.get("keywords", set()))

            # Extract keywords from description
            keywords = self._extract_keywords_from_description(description)
            keywords |= extra_keywords

            # Create the index entry
            entry = ToolIndexEntry(
                name=registered_name,
                description=description,
                service=service,
                is_write=is_write,
                tags=tags,
                parameters=parameters,
                use_cases=use_cases,
                examples=examples,
                keywords=keywords,
            )

            self._tools[registered_name] = entry

        self._built = True
        logger.info(f"Tool discovery index built with {len(self._tools)} tools")

    def search(
        self,
        query: str,
        service_filter: str | None = None,
        include_write: bool = True,
        limit: int = 7,
    ) -> list[ToolRecommendation]:
        """Search for tools matching a query.

        Args:
            query: Natural language description of task
            service_filter: Filter by service ("jira", "confluence", "bitbucket")
            include_write: Include tools that modify data
            limit: Maximum results to return

        Returns:
            List of tool recommendations sorted by relevance
        """
        if not self._built:
            logger.warning("Index not built, returning empty results")
            return []

        results: list[tuple[float, ToolRecommendation]] = []

        for name, tool in self._tools.items():
            # Apply filters
            if service_filter and tool.service != service_filter.lower():
                continue

            if not include_write and tool.is_write:
                continue

            # Skip the discover_tools itself to avoid recursion
            if name == "discover_tools":
                continue

            # Score the tool
            score, reasons = score_tool_relevance(query, tool)

            # Only include tools with some relevance
            if score > 0.1:
                recommendation = ToolRecommendation(
                    name=name,
                    description=tool.description,
                    relevance_score=score,
                    match_reasons=reasons,
                    service=tool.service,
                    is_write=tool.is_write,
                )
                results.append((score, recommendation))

        # Sort by score descending
        results.sort(key=lambda x: x[0], reverse=True)

        # Return top N recommendations
        return [rec for _, rec in results[:limit]]

    def get_tool(self, name: str) -> ToolIndexEntry | None:
        """Get a specific tool by name.

        Args:
            name: The tool name to look up

        Returns:
            The tool entry if found, None otherwise
        """
        return self._tools.get(name)

    def get_all_tools(self) -> dict[str, ToolIndexEntry]:
        """Get all indexed tools.

        Returns:
            Dictionary of all indexed tools
        """
        return self._tools.copy()
