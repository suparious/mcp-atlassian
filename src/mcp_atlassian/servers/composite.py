"""Composite tools that combine data from multiple Atlassian services."""

import json
import logging
from typing import Annotated, Any

from fastmcp import Context, FastMCP
from pydantic import Field

from mcp_atlassian.servers.dependencies import get_bitbucket_fetcher, get_jira_fetcher
from mcp_atlassian.utils.jira_keys import (
    extract_jira_keys,
    parse_development_identifier,
)

logger = logging.getLogger("mcp-atlassian.composite")

composite_mcp = FastMCP(
    name="Atlassian Composite",
    instructions="Provides composite tools that combine data from multiple Atlassian services (Jira, Bitbucket).",
)


@composite_mcp.tool(tags={"composite", "jira", "bitbucket", "read"})
async def get_issue_with_development_context(
    ctx: Context,
    issue_key: Annotated[str, Field(description="Jira issue key (e.g., 'PROJ-123')")],
    include_pr_details: Annotated[
        bool,
        Field(
            description="Whether to include detailed PR information",
            default=True,
        ),
    ] = True,
    include_pr_diff_summary: Annotated[
        bool,
        Field(
            description="Whether to include PR diff summaries (can be large)",
            default=False,
        ),
    ] = False,
    bitbucket_project_key: Annotated[
        str | None,
        Field(
            description="Optional Bitbucket project to search for PRs if development info is unavailable",
            default=None,
        ),
    ] = None,
) -> str:
    """Get Jira issue with linked PRs, branches, and commits.

    This tool combines Jira issue data with development information from
    linked source control systems (Bitbucket, GitHub, GitLab).

    Args:
        ctx: The FastMCP context.
        issue_key: Jira issue key (e.g., 'PROJ-123')
        include_pr_details: Whether to include PR details
        include_pr_diff_summary: Whether to include PR diff summaries
        bitbucket_project_key: Optional Bitbucket project to search in

    Returns:
        JSON with issue data and development context.
    """
    result: dict[str, Any] = {
        "issue_key": issue_key,
        "issue": None,
        "development_info": None,
        "pull_requests": [],
        "errors": [],
    }

    # Get Jira fetcher
    try:
        jira = await get_jira_fetcher(ctx)
    except ValueError as e:
        result["errors"].append(f"Jira not available: {str(e)}")
        return json.dumps(result, indent=2, ensure_ascii=False)

    # Fetch the Jira issue
    try:
        issue = jira.get_issue(
            issue_key=issue_key,
            fields=None,  # Get all fields
            expand="names,renderedFields",
        )
        result["issue"] = issue.to_simplified_dict()
    except Exception as e:
        logger.error(f"Failed to fetch Jira issue {issue_key}: {e}")
        result["errors"].append(f"Failed to fetch issue: {str(e)}")
        return json.dumps(result, indent=2, ensure_ascii=False)

    # Try to get development info from Jira
    dev_info_available = False
    try:
        dev_info = jira.get_development_information(issue_key=issue_key)
        dev_info_dict = dev_info.to_dict()
        result["development_info"] = dev_info_dict

        # Check if we have actual development data
        if dev_info_dict.get("has_development_info"):
            dev_info_available = True

            # Extract PR info from development data
            if dev_info_dict.get("pull_requests"):
                result["pull_requests"] = dev_info_dict["pull_requests"]

    except Exception as e:
        logger.warning(f"Failed to get development info for {issue_key}: {e}")
        result["errors"].append(f"Development info unavailable: {str(e)}")

    # If no development info from Jira and Bitbucket project provided, try Bitbucket search
    if not dev_info_available and bitbucket_project_key and include_pr_details:
        try:
            bitbucket = await get_bitbucket_fetcher(ctx)
            # Search for PRs mentioning this issue key
            repos = bitbucket.get_repositories(bitbucket_project_key)

            for repo in repos:
                repo_slug = repo.slug
                try:
                    # Get open PRs and check for issue key in title/description
                    prs = bitbucket.get_pull_requests(
                        bitbucket_project_key,
                        repo_slug,
                        state="ALL",
                        limit=50,
                    )

                    for pr in prs:
                        pr_dict = pr.to_simplified_dict()
                        title = pr_dict.get("title", "")
                        description = pr_dict.get("description", "")
                        source_branch = pr_dict.get("source_branch", "")

                        # Check if this PR mentions the issue
                        extracted_keys = extract_jira_keys(
                            title=title,
                            description=description,
                            branch_name=source_branch,
                        )

                        if any(m.key == issue_key.upper() for m in extracted_keys):
                            pr_info = {
                                "project_key": bitbucket_project_key,
                                "repository_slug": repo_slug,
                                "id": pr_dict.get("id"),
                                "title": title,
                                "state": pr_dict.get("state"),
                                "author": pr_dict.get("author"),
                                "source_branch": source_branch,
                                "target_branch": pr_dict.get("target_branch"),
                                "url": pr_dict.get("url"),
                            }

                            # Optionally include diff summary
                            if include_pr_diff_summary:
                                try:
                                    changes = bitbucket.get_pull_request_changes(
                                        bitbucket_project_key,
                                        repo_slug,
                                        pr_dict.get("id"),
                                    )
                                    pr_info["changes_summary"] = changes
                                except Exception as diff_err:
                                    pr_info["changes_error"] = str(diff_err)

                            result["pull_requests"].append(pr_info)

                except Exception as repo_err:
                    logger.debug(
                        f"Failed to search PRs in {bitbucket_project_key}/{repo_slug}: {repo_err}"
                    )

        except ValueError as e:
            result["errors"].append(f"Bitbucket search failed: {str(e)}")
        except Exception as e:
            logger.warning(f"Bitbucket search error: {e}")
            result["errors"].append(f"Bitbucket search error: {str(e)}")

    # Add summary
    result["summary"] = {
        "issue_found": result["issue"] is not None,
        "has_development_info": dev_info_available,
        "pr_count": len(result["pull_requests"]),
        "error_count": len(result["errors"]),
    }

    return json.dumps(result, indent=2, ensure_ascii=False)


@composite_mcp.tool(tags={"composite", "bitbucket", "jira", "read"})
async def get_pr_with_jira_context(
    ctx: Context,
    project_key: Annotated[str, Field(description="Bitbucket project key")],
    repository_slug: Annotated[str, Field(description="Repository slug")],
    pull_request_id: Annotated[int, Field(description="PR ID")],
    resolve_jira_issues: Annotated[
        bool,
        Field(
            description="Whether to resolve linked Jira issues",
            default=True,
        ),
    ] = True,
) -> str:
    """Get Bitbucket PR with linked Jira issue details.

    This tool fetches a Bitbucket pull request and automatically extracts
    and resolves any Jira issue keys found in the PR title, description,
    or source branch name.

    Args:
        ctx: The FastMCP context.
        project_key: Bitbucket project key
        repository_slug: Repository slug
        pull_request_id: PR ID
        resolve_jira_issues: Whether to resolve linked Jira issues

    Returns:
        JSON with PR data and resolved Jira issues.
    """
    result: dict[str, Any] = {
        "pull_request": None,
        "linked_jira_issues": [],
        "jira_key_matches": [],
        "errors": [],
    }

    # Get Bitbucket fetcher
    try:
        bitbucket = await get_bitbucket_fetcher(ctx)
    except ValueError as e:
        result["errors"].append(f"Bitbucket not available: {str(e)}")
        return json.dumps(result, indent=2, ensure_ascii=False)

    # Fetch the PR
    try:
        pr = bitbucket.get_pull_request(project_key, repository_slug, pull_request_id)
        pr_dict = pr.to_simplified_dict()
        result["pull_request"] = pr_dict
    except Exception as e:
        logger.error(
            f"Failed to fetch PR {project_key}/{repository_slug}#{pull_request_id}: {e}"
        )
        result["errors"].append(f"Failed to fetch PR: {str(e)}")
        return json.dumps(result, indent=2, ensure_ascii=False)

    # Extract Jira keys from PR
    title = pr_dict.get("title", "")
    description = pr_dict.get("description", "")
    source_branch = pr_dict.get("source_branch", "")

    jira_matches = extract_jira_keys(
        title=title,
        description=description,
        branch_name=source_branch,
    )

    result["jira_key_matches"] = [
        {"key": m.key, "source": m.source, "confidence": m.confidence}
        for m in jira_matches
    ]

    # Resolve Jira issues if requested
    if resolve_jira_issues and jira_matches:
        try:
            jira = await get_jira_fetcher(ctx)

            for match in jira_matches:
                try:
                    issue = jira.get_issue(
                        issue_key=match.key,
                        fields=[
                            "summary",
                            "status",
                            "issuetype",
                            "priority",
                            "assignee",
                            "reporter",
                        ],
                    )
                    issue_dict = issue.to_simplified_dict()
                    result["linked_jira_issues"].append(
                        {
                            "key": match.key,
                            "source": match.source,
                            "confidence": match.confidence,
                            "issue": issue_dict,
                        }
                    )
                except Exception as issue_err:
                    logger.warning(f"Failed to fetch Jira issue {match.key}: {issue_err}")
                    result["linked_jira_issues"].append(
                        {
                            "key": match.key,
                            "source": match.source,
                            "confidence": match.confidence,
                            "error": str(issue_err),
                        }
                    )

        except ValueError as e:
            result["errors"].append(f"Jira not available: {str(e)}")

    # Add summary
    result["summary"] = {
        "pr_found": result["pull_request"] is not None,
        "jira_keys_found": len(jira_matches),
        "jira_issues_resolved": len(
            [i for i in result["linked_jira_issues"] if "issue" in i]
        ),
        "error_count": len(result["errors"]),
    }

    return json.dumps(result, indent=2, ensure_ascii=False)


@composite_mcp.tool(tags={"composite", "read"})
async def resolve_development_links(
    ctx: Context,
    identifier: Annotated[
        str,
        Field(
            description="Smart identifier - 'PROJ-123' for Jira issue, 'PROJECT/repo#456' for Bitbucket PR"
        ),
    ],
    resolve_depth: Annotated[
        int,
        Field(
            description="How deep to resolve links (1 = direct links only)",
            default=1,
            ge=1,
            le=3,
        ),
    ] = 1,
) -> str:
    """Resolve development links from any identifier.

    Accepts either Jira issue keys or Bitbucket PR references and resolves
    all linked development information.

    Args:
        ctx: The FastMCP context.
        identifier: Smart identifier - "PROJ-123" for Jira, "PROJECT/repo#456" for PR
        resolve_depth: How deep to resolve links (1 = direct links only)

    Returns:
        JSON with resolved development context.
    """
    result: dict[str, Any] = {
        "identifier": identifier,
        "resolved_type": None,
        "data": None,
        "errors": [],
    }

    # Parse the identifier
    try:
        parsed = parse_development_identifier(identifier)
        result["resolved_type"] = parsed.type
    except ValueError as e:
        result["errors"].append(str(e))
        return json.dumps(result, indent=2, ensure_ascii=False)

    # Resolve based on type
    if parsed.type == "jira":
        # Call get_issue_with_development_context
        issue_result = await get_issue_with_development_context(
            ctx=ctx,
            issue_key=parsed.issue_key,
            include_pr_details=True,
            include_pr_diff_summary=False,
        )
        result["data"] = json.loads(issue_result)

    elif parsed.type == "bitbucket":
        if parsed.pr_id is not None:
            # Call get_pr_with_jira_context
            pr_result = await get_pr_with_jira_context(
                ctx=ctx,
                project_key=parsed.project_key,
                repository_slug=parsed.repo_slug,
                pull_request_id=parsed.pr_id,
                resolve_jira_issues=True,
            )
            result["data"] = json.loads(pr_result)

            # If resolve_depth > 1, also resolve linked Jira issues' development info
            if resolve_depth > 1:
                pr_data = result["data"]
                linked_issues = pr_data.get("linked_jira_issues", [])
                enhanced_issues = []

                for linked in linked_issues:
                    if "issue" in linked and "error" not in linked:
                        try:
                            issue_dev_result = await get_issue_with_development_context(
                                ctx=ctx,
                                issue_key=linked["key"],
                                include_pr_details=True,
                                include_pr_diff_summary=False,
                            )
                            linked["development_context"] = json.loads(issue_dev_result)
                        except Exception as e:
                            linked["development_context_error"] = str(e)
                    enhanced_issues.append(linked)

                result["data"]["linked_jira_issues"] = enhanced_issues

        else:
            # Just a repo reference, list open PRs
            try:
                bitbucket = await get_bitbucket_fetcher(ctx)
                prs = bitbucket.get_pull_requests(
                    parsed.project_key,
                    parsed.repo_slug,
                    state="OPEN",
                    limit=20,
                )
                result["data"] = {
                    "project_key": parsed.project_key,
                    "repository_slug": parsed.repo_slug,
                    "open_pull_requests": [pr.to_simplified_dict() for pr in prs],
                }
            except Exception as e:
                result["errors"].append(f"Failed to list PRs: {str(e)}")

    return json.dumps(result, indent=2, ensure_ascii=False)
