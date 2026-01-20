"""Static metadata enhancements for tools.

Additional use cases and examples for tools.
These enhance the base tool descriptions for better discovery.
"""

TOOL_ENHANCEMENTS: dict[str, dict[str, list[str] | set[str]]] = {
    # =========================================================================
    # Jira Tools
    # =========================================================================
    "jira_get_user_profile": {
        "use_cases": [
            "Look up user information",
            "Find user by email",
            "Get user details",
            "Check who someone is",
        ],
        "examples": [
            "Who is john@example.com?",
            "Get user profile for this email",
            "Look up user details",
        ],
        "keywords": {"user", "profile", "email", "account", "person", "member"},
    },
    "jira_get_issue": {
        "use_cases": [
            "Look up issue details",
            "Check issue status",
            "See who is assigned to an issue",
            "Get issue description",
            "View ticket information",
            "Read bug details",
        ],
        "examples": [
            "What's the status of PROJ-123?",
            "Who is working on this ticket?",
            "Show me the details of bug PROJ-456",
            "Get issue PROJ-789",
        ],
        "keywords": {
            "ticket",
            "bug",
            "story",
            "task",
            "status",
            "details",
            "issue",
            "epic",
        },
    },
    "jira_search": {
        "use_cases": [
            "Find issues by criteria",
            "Search for bugs in a project",
            "Find my assigned issues",
            "List open issues",
            "Query issues with JQL",
            "Find tickets by status",
        ],
        "examples": [
            "Find all open bugs in project PROJ",
            "What issues are assigned to me?",
            "Search for issues updated this week",
            "Find high priority tickets",
        ],
        "keywords": {"find", "search", "query", "jql", "filter", "list", "issues"},
    },
    "jira_search_fields": {
        "use_cases": [
            "Find custom field names",
            "Discover available fields",
            "Look up field IDs",
        ],
        "examples": [
            "What fields are available?",
            "Find the story points field",
            "Get custom field ID",
        ],
        "keywords": {"field", "custom", "schema", "metadata"},
    },
    "jira_get_project_issues": {
        "use_cases": [
            "List all issues in a project",
            "Get project backlog",
            "View project tickets",
        ],
        "examples": [
            "Show all issues in PROJ",
            "List project backlog",
            "Get tickets for this project",
        ],
        "keywords": {"project", "issues", "list", "backlog"},
    },
    "jira_get_transitions": {
        "use_cases": [
            "See available status changes",
            "Check workflow transitions",
            "Find how to move an issue",
        ],
        "examples": [
            "What statuses can I move this to?",
            "Show available transitions",
            "How do I close this issue?",
        ],
        "keywords": {"transition", "status", "workflow", "move", "change"},
    },
    "jira_get_comments": {
        "use_cases": [
            "Read issue comments",
            "View discussion on a ticket",
            "Get comment history",
        ],
        "examples": [
            "Show comments on PROJ-123",
            "What's been discussed on this ticket?",
            "Read the conversation",
        ],
        "keywords": {"comment", "discussion", "conversation", "notes"},
    },
    "jira_get_worklog": {
        "use_cases": [
            "See time logged",
            "Check work entries",
            "View time tracking",
        ],
        "examples": [
            "How much time was logged?",
            "Show worklog for PROJ-123",
            "Get time entries",
        ],
        "keywords": {"worklog", "time", "hours", "logged", "tracking"},
    },
    "jira_download_attachments": {
        "use_cases": [
            "Download files from an issue",
            "Get attachments",
            "Save attached documents",
        ],
        "examples": [
            "Download attachments from PROJ-123",
            "Get the files attached to this issue",
        ],
        "keywords": {"attachment", "file", "download", "document"},
    },
    "jira_get_agile_boards": {
        "use_cases": [
            "Find scrum or kanban boards",
            "List project boards",
            "Get board information",
        ],
        "examples": [
            "Show me the scrum boards",
            "Find the kanban board for PROJ",
            "List all boards",
        ],
        "keywords": {"board", "scrum", "kanban", "agile"},
    },
    "jira_get_board_issues": {
        "use_cases": [
            "Get issues on a board",
            "View board backlog",
            "List sprint items",
        ],
        "examples": [
            "What issues are on this board?",
            "Show board backlog",
        ],
        "keywords": {"board", "issues", "backlog", "sprint"},
    },
    "jira_get_sprints_from_board": {
        "use_cases": [
            "List sprints for a board",
            "Find active sprint",
            "Get sprint history",
        ],
        "examples": [
            "What sprints are on this board?",
            "Show the active sprint",
            "List all sprints",
        ],
        "keywords": {"sprint", "iteration", "active", "future", "closed"},
    },
    "jira_get_sprint_issues": {
        "use_cases": [
            "Get issues in a sprint",
            "View sprint backlog",
            "List sprint work items",
        ],
        "examples": [
            "What's in sprint 123?",
            "Show sprint issues",
            "Get sprint backlog",
        ],
        "keywords": {"sprint", "issues", "backlog", "iteration"},
    },
    "jira_get_link_types": {
        "use_cases": [
            "See available link types",
            "Find how to link issues",
            "Get relationship types",
        ],
        "examples": [
            "What link types are available?",
            "How can I link issues?",
        ],
        "keywords": {"link", "relationship", "blocks", "relates"},
    },
    "jira_create_issue": {
        "use_cases": [
            "Create a new ticket",
            "File a bug report",
            "Add a new task",
            "Create a story",
        ],
        "examples": [
            "Create a new bug in PROJ",
            "Add a task for this work",
            "File a new ticket",
        ],
        "keywords": {"create", "new", "add", "ticket", "bug", "task", "story"},
    },
    "jira_batch_create_issues": {
        "use_cases": [
            "Create multiple issues at once",
            "Bulk create tickets",
            "Add several tasks",
        ],
        "examples": [
            "Create these 5 issues",
            "Bulk add tickets",
        ],
        "keywords": {"batch", "bulk", "multiple", "create"},
    },
    "jira_batch_get_changelogs": {
        "use_cases": [
            "Get history for multiple issues",
            "View changes across tickets",
            "Audit issue modifications",
        ],
        "examples": [
            "Get changelog for PROJ-1, PROJ-2, PROJ-3",
            "Show history for these issues",
        ],
        "keywords": {"changelog", "history", "audit", "batch", "changes"},
    },
    "jira_update_issue": {
        "use_cases": [
            "Modify an existing issue",
            "Change issue fields",
            "Update ticket details",
            "Edit issue description",
        ],
        "examples": [
            "Update the summary of PROJ-123",
            "Change the assignee",
            "Edit the description",
        ],
        "keywords": {"update", "edit", "modify", "change"},
    },
    "jira_delete_issue": {
        "use_cases": [
            "Remove an issue",
            "Delete a ticket",
            "Permanently remove",
        ],
        "examples": [
            "Delete PROJ-123",
            "Remove this ticket",
        ],
        "keywords": {"delete", "remove", "destroy"},
    },
    "jira_add_comment": {
        "use_cases": [
            "Add a comment to an issue",
            "Reply to a ticket",
            "Post a note",
        ],
        "examples": [
            "Add a comment to PROJ-123",
            "Post this update on the ticket",
        ],
        "keywords": {"comment", "add", "post", "reply", "note"},
    },
    "jira_add_worklog": {
        "use_cases": [
            "Log time on an issue",
            "Record work hours",
            "Track time spent",
        ],
        "examples": [
            "Log 2 hours on PROJ-123",
            "Record time spent today",
        ],
        "keywords": {"worklog", "time", "log", "hours", "track"},
    },
    "jira_link_to_epic": {
        "use_cases": [
            "Link an issue to an epic",
            "Add to epic",
            "Associate with epic",
        ],
        "examples": [
            "Link PROJ-123 to epic PROJ-100",
            "Add this to the epic",
        ],
        "keywords": {"epic", "link", "parent", "associate"},
    },
    "jira_create_issue_link": {
        "use_cases": [
            "Link two issues together",
            "Create issue relationship",
            "Connect related tickets",
        ],
        "examples": [
            "Link PROJ-123 blocks PROJ-456",
            "Create a 'relates to' link",
        ],
        "keywords": {"link", "relationship", "blocks", "relates", "connect"},
    },
    "jira_create_remote_issue_link": {
        "use_cases": [
            "Add a web link to an issue",
            "Link to external resource",
            "Add Confluence link",
        ],
        "examples": [
            "Add this URL to the issue",
            "Link to documentation",
        ],
        "keywords": {"link", "url", "web", "external", "remote"},
    },
    "jira_remove_issue_link": {
        "use_cases": [
            "Remove a link between issues",
            "Delete issue relationship",
        ],
        "examples": [
            "Remove the link to PROJ-456",
            "Unlink these issues",
        ],
        "keywords": {"unlink", "remove", "delete", "relationship"},
    },
    "jira_transition_issue": {
        "use_cases": [
            "Change issue status",
            "Move issue to done",
            "Progress through workflow",
            "Close an issue",
        ],
        "examples": [
            "Move PROJ-123 to Done",
            "Close this ticket",
            "Mark as in progress",
        ],
        "keywords": {"transition", "status", "move", "close", "done", "progress"},
    },
    "jira_create_sprint": {
        "use_cases": [
            "Create a new sprint",
            "Set up next iteration",
        ],
        "examples": [
            "Create Sprint 10",
            "Set up the next sprint",
        ],
        "keywords": {"sprint", "create", "iteration", "new"},
    },
    "jira_update_sprint": {
        "use_cases": [
            "Modify sprint details",
            "Change sprint dates",
            "Update sprint goal",
        ],
        "examples": [
            "Update the sprint goal",
            "Change sprint dates",
        ],
        "keywords": {"sprint", "update", "modify", "dates", "goal"},
    },
    "jira_get_project_versions": {
        "use_cases": [
            "List fix versions",
            "Get releases for project",
            "View version list",
        ],
        "examples": [
            "What versions exist in PROJ?",
            "List fix versions",
        ],
        "keywords": {"version", "release", "fix", "milestone"},
    },
    "jira_get_development_information": {
        "use_cases": [
            "Get linked PRs and branches",
            "View development activity",
            "See commits for an issue",
        ],
        "examples": [
            "What PRs are linked to PROJ-123?",
            "Show development info",
            "Are there any branches for this issue?",
        ],
        "keywords": {"development", "pr", "branch", "commit", "code"},
    },
    "jira_get_all_projects": {
        "use_cases": [
            "List all Jira projects",
            "See available projects",
            "Find project keys",
        ],
        "examples": [
            "What projects exist?",
            "List all Jira projects",
        ],
        "keywords": {"project", "list", "all"},
    },
    "jira_create_version": {
        "use_cases": [
            "Create a fix version",
            "Add a release",
            "Set up a milestone",
        ],
        "examples": [
            "Create version 2.0 in PROJ",
            "Add a new release",
        ],
        "keywords": {"version", "release", "create", "milestone"},
    },
    "jira_batch_create_versions": {
        "use_cases": [
            "Create multiple versions",
            "Bulk add releases",
        ],
        "examples": [
            "Create versions 2.0, 2.1, and 2.2",
        ],
        "keywords": {"version", "batch", "bulk", "release"},
    },
    # =========================================================================
    # Confluence Tools
    # =========================================================================
    "confluence_search": {
        "use_cases": [
            "Find documentation",
            "Search for pages about a topic",
            "Locate technical docs",
            "Find wiki content",
        ],
        "examples": [
            "Find documentation about authentication",
            "Search for architecture docs",
            "Look for API documentation",
        ],
        "keywords": {"documentation", "docs", "wiki", "page", "article", "search"},
    },
    "confluence_get_page": {
        "use_cases": [
            "Read a specific page",
            "Get page content",
            "View documentation",
        ],
        "examples": [
            "Show me the API documentation page",
            "Get the content of page 12345",
            "Read this wiki page",
        ],
        "keywords": {"read", "view", "content", "page", "wiki"},
    },
    "confluence_get_page_children": {
        "use_cases": [
            "List child pages",
            "Get subpages",
            "View page hierarchy",
        ],
        "examples": [
            "What pages are under this one?",
            "Show child pages",
            "List subpages",
        ],
        "keywords": {"children", "subpage", "hierarchy", "nested"},
    },
    "confluence_get_comments": {
        "use_cases": [
            "Read page comments",
            "View discussion on a page",
            "Get feedback on documentation",
        ],
        "examples": [
            "Show comments on this page",
            "What's the discussion?",
        ],
        "keywords": {"comment", "discussion", "feedback"},
    },
    "confluence_get_labels": {
        "use_cases": [
            "Get page labels/tags",
            "See how a page is categorized",
        ],
        "examples": [
            "What labels does this page have?",
            "Show page tags",
        ],
        "keywords": {"label", "tag", "category"},
    },
    "confluence_add_label": {
        "use_cases": [
            "Add a label to a page",
            "Tag a page",
            "Categorize content",
        ],
        "examples": [
            "Add the 'api' label to this page",
            "Tag this as documentation",
        ],
        "keywords": {"label", "tag", "add", "categorize"},
    },
    "confluence_create_page": {
        "use_cases": [
            "Create new documentation",
            "Add a wiki page",
            "Write new content",
        ],
        "examples": [
            "Create a new page in DEV space",
            "Add documentation for this feature",
        ],
        "keywords": {"create", "new", "page", "wiki", "documentation"},
    },
    "confluence_update_page": {
        "use_cases": [
            "Edit a page",
            "Update documentation",
            "Modify page content",
        ],
        "examples": [
            "Update the API docs",
            "Edit this page content",
        ],
        "keywords": {"update", "edit", "modify", "change"},
    },
    "confluence_delete_page": {
        "use_cases": [
            "Remove a page",
            "Delete documentation",
        ],
        "examples": [
            "Delete this outdated page",
            "Remove the old docs",
        ],
        "keywords": {"delete", "remove", "page"},
    },
    "confluence_add_comment": {
        "use_cases": [
            "Comment on a page",
            "Add feedback",
            "Post a note",
        ],
        "examples": [
            "Add a comment to this page",
            "Post feedback on the docs",
        ],
        "keywords": {"comment", "add", "feedback", "note"},
    },
    "confluence_search_user": {
        "use_cases": [
            "Find Confluence users",
            "Search for a person",
            "Look up user",
        ],
        "examples": [
            "Find user John Doe",
            "Search for this person",
        ],
        "keywords": {"user", "person", "search", "find"},
    },
    # =========================================================================
    # Bitbucket Tools
    # =========================================================================
    "bitbucket_list_projects": {
        "use_cases": [
            "List all Bitbucket projects",
            "See available projects",
            "Find project keys",
        ],
        "examples": [
            "What Bitbucket projects exist?",
            "List all projects",
        ],
        "keywords": {"project", "list", "bitbucket"},
    },
    "bitbucket_get_project": {
        "use_cases": [
            "Get project details",
            "View project info",
        ],
        "examples": [
            "Get details for project PROJ",
            "Show project information",
        ],
        "keywords": {"project", "details", "info"},
    },
    "bitbucket_list_repositories": {
        "use_cases": [
            "List repos in a project",
            "See available repositories",
        ],
        "examples": [
            "What repos are in PROJ?",
            "List repositories",
        ],
        "keywords": {"repository", "repo", "list"},
    },
    "bitbucket_get_repository": {
        "use_cases": [
            "Get repository details",
            "View repo info",
        ],
        "examples": [
            "Get details for my-repo",
            "Show repo information",
        ],
        "keywords": {"repository", "repo", "details"},
    },
    "bitbucket_get_file_content": {
        "use_cases": [
            "Read a file from a repo",
            "Get file contents",
            "View source code",
        ],
        "examples": [
            "Show me the README.md",
            "Get the content of src/main.py",
        ],
        "keywords": {"file", "content", "read", "source"},
    },
    "bitbucket_list_branches": {
        "use_cases": [
            "List branches in a repo",
            "See available branches",
        ],
        "examples": [
            "What branches exist?",
            "List all branches",
        ],
        "keywords": {"branch", "list", "ref"},
    },
    "bitbucket_list_pull_requests": {
        "use_cases": [
            "List PRs in a repo",
            "See open pull requests",
            "Find merge requests",
        ],
        "examples": [
            "What PRs are open?",
            "List pull requests",
        ],
        "keywords": {"pr", "pull request", "list", "merge"},
    },
    "bitbucket_get_pull_request": {
        "use_cases": [
            "Get PR details",
            "View pull request",
            "See merge request info",
        ],
        "examples": [
            "Show PR #123",
            "Get pull request details",
        ],
        "keywords": {"pr", "pull request", "details"},
    },
    "bitbucket_get_pull_request_diff": {
        "use_cases": [
            "See PR changes",
            "View diff",
            "See what changed",
        ],
        "examples": [
            "Show the diff for PR #123",
            "What changed in this PR?",
        ],
        "keywords": {"diff", "changes", "pr", "pull request"},
    },
    "bitbucket_get_pull_request_comments": {
        "use_cases": [
            "Read PR comments",
            "See code review feedback",
        ],
        "examples": [
            "Show comments on PR #123",
            "What feedback is there?",
        ],
        "keywords": {"comment", "pr", "review", "feedback"},
    },
    "bitbucket_add_pull_request_comment": {
        "use_cases": [
            "Comment on a PR",
            "Add review feedback",
        ],
        "examples": [
            "Add a comment to PR #123",
            "Post review feedback",
        ],
        "keywords": {"comment", "add", "pr", "review"},
    },
    "bitbucket_create_repository": {
        "use_cases": [
            "Create a new repository",
            "Set up a new repo",
        ],
        "examples": [
            "Create a new repo called my-app",
            "Set up a new repository",
        ],
        "keywords": {"create", "repository", "repo", "new"},
    },
}
