"""Base client module for Bitbucket Server/Data Center API interactions."""

import logging
import os
from typing import Any

from atlassian import Bitbucket
from requests import Session

from mcp_atlassian.exceptions import MCPAtlassianAuthenticationError
from mcp_atlassian.utils.auth import configure_server_pat_auth
from mcp_atlassian.utils.logging import (
    get_masked_session_headers,
    log_config_param,
    mask_sensitive,
)
from mcp_atlassian.utils.rate_limit import configure_rate_limiting
from mcp_atlassian.utils.ssl import configure_ssl_verification

from .config import BitbucketConfig

# Configure logging
logger = logging.getLogger("mcp-bitbucket")


class BitbucketClient:
    """Base client for Bitbucket Server/Data Center API interactions."""

    config: BitbucketConfig

    def __init__(self, config: BitbucketConfig | None = None) -> None:
        """Initialize the Bitbucket client with configuration options.

        Args:
            config: Optional configuration object (will use env vars if not provided)

        Raises:
            ValueError: If configuration is invalid or required credentials are missing
            MCPAtlassianAuthenticationError: If authentication fails
        """
        # Load configuration from environment variables if not provided
        self.config = config or BitbucketConfig.from_env()

        # Initialize the Bitbucket client based on auth type
        if self.config.auth_type == "pat":
            logger.debug(
                f"Initializing Bitbucket client with PAT auth. "
                f"URL: {self.config.url}, "
                f"Token (masked): {mask_sensitive(str(self.config.personal_token))}"
            )

            # Server/DC instances need Bearer authentication for PATs
            session = Session()
            configure_server_pat_auth(session, self.config.personal_token)

            # Initialize Bitbucket with the pre-configured session
            self.bitbucket = Bitbucket(
                url=self.config.url,
                session=session,
                cloud=False,
            )

            logger.debug(
                f"Bitbucket Server/DC client initialized with Bearer auth. "
                f"Session headers (Authorization masked): "
                f"{get_masked_session_headers(dict(self.bitbucket._session.headers))}"
            )
        else:  # basic auth
            logger.debug(
                f"Initializing Bitbucket client with Basic auth. "
                f"URL: {self.config.url}, Username: {self.config.username}, "
                f"API Token present: {bool(self.config.api_token)}"
            )
            self.bitbucket = Bitbucket(
                url=self.config.url,
                username=self.config.username,
                password=self.config.api_token,
                cloud=False,
            )
            headers = get_masked_session_headers(dict(self.bitbucket._session.headers))
            logger.debug(f"Bitbucket client initialized. Headers: {headers}")

        # Configure SSL verification
        configure_ssl_verification(
            service_name="Bitbucket",
            url=self.config.url,
            session=self.bitbucket._session,
            ssl_verify=self.config.ssl_verify,
        )

        # Proxy configuration
        proxies = {}
        if self.config.http_proxy:
            proxies["http"] = self.config.http_proxy
        if self.config.https_proxy:
            proxies["https"] = self.config.https_proxy
        if self.config.socks_proxy:
            proxies["socks"] = self.config.socks_proxy
        if proxies:
            self.bitbucket._session.proxies.update(proxies)
            for k, v in proxies.items():
                log_config_param(
                    logger, "Bitbucket", f"{k.upper()}_PROXY", v, sensitive=True
                )
        if self.config.no_proxy and isinstance(self.config.no_proxy, str):
            os.environ["NO_PROXY"] = self.config.no_proxy
            log_config_param(logger, "Bitbucket", "NO_PROXY", self.config.no_proxy)

        # Configure rate limiting
        configure_rate_limiting(self.bitbucket._session, "bitbucket")
        logger.debug("Rate limiting configured for Bitbucket session")

        # Apply custom headers if configured
        if self.config.custom_headers:
            self._apply_custom_headers()

        # Test authentication during initialization (in debug mode only)
        if logger.isEnabledFor(logging.DEBUG):
            try:
                self._validate_authentication()
            except MCPAtlassianAuthenticationError:
                logger.warning(
                    "Authentication validation failed during client initialization - "
                    "continuing anyway"
                )

    def _validate_authentication(self) -> None:
        """Validate authentication by making a simple API call."""
        try:
            logger.debug("Testing Bitbucket authentication by retrieving projects...")
            # Use project_list as a simple auth check
            projects = list(self.bitbucket.project_list(limit=1))
            if projects is not None:
                logger.info(
                    f"Bitbucket authentication successful. "
                    f"Found {len(projects)} project(s) accessible."
                )
            else:
                logger.warning(
                    "Bitbucket authentication test returned empty response - "
                    "this may indicate an issue"
                )
        except Exception as e:
            error_msg = f"Bitbucket authentication validation failed: {e}"
            logger.error(error_msg)
            logger.debug(
                f"Authentication headers during failure: "
                f"{get_masked_session_headers(dict(self.bitbucket._session.headers))}"
            )
            raise MCPAtlassianAuthenticationError(error_msg) from e

    def _apply_custom_headers(self) -> None:
        """Apply custom headers to the Bitbucket session."""
        if not self.config.custom_headers:
            return

        header_count = len(self.config.custom_headers)
        logger.debug(f"Applying {header_count} custom headers to Bitbucket session")
        for header_name, header_value in self.config.custom_headers.items():
            self.bitbucket._session.headers[header_name] = header_value
            logger.debug(f"Applied custom header: {header_name}")

    def _get_paged_results(
        self,
        fetch_func,
        limit: int | None = None,
        start: int = 0,
        **kwargs,
    ) -> list[Any]:
        """Helper to collect all results from a paged Bitbucket API call.

        Args:
            fetch_func: The function to call that returns paged results
            limit: Maximum number of results to return
            start: Starting index for pagination
            **kwargs: Additional arguments to pass to the fetch function

        Returns:
            List of all results
        """
        results = []
        for item in fetch_func(start=start, limit=limit, **kwargs):
            results.append(item)
            if limit and len(results) >= limit:
                break
        return results
