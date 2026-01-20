"""Rate limiting utilities for MCP Atlassian.

This module provides token bucket rate limiting with exponential backoff
for handling HTTP 429 responses from Atlassian APIs.
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from threading import Lock
from typing import Any

from requests import PreparedRequest, Response, Session
from requests.adapters import HTTPAdapter

logger = logging.getLogger("mcp-atlassian.rate_limit")


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting behavior.

    Attributes:
        requests_per_second: Rate at which tokens are refilled (default 10.0)
        burst_capacity: Maximum number of tokens in the bucket (default 20)
        backoff_base: Base delay in seconds for exponential backoff (default 1.0)
        max_retries: Maximum number of retry attempts for 429 responses (default 5)
    """

    requests_per_second: float = 10.0
    burst_capacity: int = 20
    backoff_base: float = 1.0
    max_retries: int = 5


def get_config_from_env(service_name: str | None = None) -> RateLimitConfig:
    """Load rate limit configuration from environment variables.

    Supports both global and service-specific environment variables.
    Service-specific variables take precedence over global ones.

    Args:
        service_name: Optional service name (e.g., "JIRA", "CONFLUENCE", "BITBUCKET")
                     for service-specific configuration.

    Returns:
        RateLimitConfig with values from environment or defaults.

    Environment Variables:
        ATLASSIAN_RATE_LIMIT_RPS: Global requests per second (default 10.0)
        ATLASSIAN_RATE_LIMIT_BURST: Global burst capacity (default 20)
        ATLASSIAN_RATE_LIMIT_BACKOFF_BASE: Global backoff base (default 1.0)
        ATLASSIAN_RATE_LIMIT_MAX_RETRIES: Global max retries (default 5)
        {SERVICE}_RATE_LIMIT_RPS: Service-specific requests per second
        {SERVICE}_RATE_LIMIT_BURST: Service-specific burst capacity
        {SERVICE}_RATE_LIMIT_BACKOFF_BASE: Service-specific backoff base
        {SERVICE}_RATE_LIMIT_MAX_RETRIES: Service-specific max retries
    """

    def get_float(
        global_key: str, service_key: str | None, default: float
    ) -> float:
        """Get float value from environment with service override."""
        value = default
        global_val = os.getenv(global_key)
        if global_val:
            try:
                value = float(global_val)
            except ValueError:
                logger.warning(
                    f"Invalid float value for {global_key}: {global_val}, using default"
                )
        if service_key:
            service_val = os.getenv(service_key)
            if service_val:
                try:
                    value = float(service_val)
                except ValueError:
                    logger.warning(
                        f"Invalid float value for {service_key}: {service_val}, "
                        f"using global/default"
                    )
        return value

    def get_int(global_key: str, service_key: str | None, default: int) -> int:
        """Get int value from environment with service override."""
        value = default
        global_val = os.getenv(global_key)
        if global_val:
            try:
                value = int(global_val)
            except ValueError:
                logger.warning(
                    f"Invalid int value for {global_key}: {global_val}, using default"
                )
        if service_key:
            service_val = os.getenv(service_key)
            if service_val:
                try:
                    value = int(service_val)
                except ValueError:
                    logger.warning(
                        f"Invalid int value for {service_key}: {service_val}, "
                        f"using global/default"
                    )
        return value

    # Build service-specific env var names if service name provided
    service_prefix = f"{service_name.upper()}_" if service_name else None

    rps = get_float(
        "ATLASSIAN_RATE_LIMIT_RPS",
        f"{service_prefix}RATE_LIMIT_RPS" if service_prefix else None,
        10.0,
    )
    burst = get_int(
        "ATLASSIAN_RATE_LIMIT_BURST",
        f"{service_prefix}RATE_LIMIT_BURST" if service_prefix else None,
        20,
    )
    backoff = get_float(
        "ATLASSIAN_RATE_LIMIT_BACKOFF_BASE",
        f"{service_prefix}RATE_LIMIT_BACKOFF_BASE" if service_prefix else None,
        1.0,
    )
    max_retries = get_int(
        "ATLASSIAN_RATE_LIMIT_MAX_RETRIES",
        f"{service_prefix}RATE_LIMIT_MAX_RETRIES" if service_prefix else None,
        5,
    )

    return RateLimitConfig(
        requests_per_second=rps,
        burst_capacity=burst,
        backoff_base=backoff,
        max_retries=max_retries,
    )


class TokenBucket:
    """Token bucket rate limiter with async and sync support.

    Implements the token bucket algorithm for rate limiting. Tokens are
    consumed when requests are made and refilled at a constant rate.

    Attributes:
        config: Rate limit configuration
        tokens: Current number of available tokens
        last_refill: Timestamp of last token refill
    """

    def __init__(self, config: RateLimitConfig) -> None:
        """Initialize the token bucket.

        Args:
            config: Rate limit configuration
        """
        self.config = config
        self.tokens: float = float(config.burst_capacity)
        self.last_refill: float = time.monotonic()
        self._lock = Lock()
        self._async_lock: asyncio.Lock | None = None

    def _get_async_lock(self) -> asyncio.Lock:
        """Get or create the async lock (lazy initialization)."""
        if self._async_lock is None:
            self._async_lock = asyncio.Lock()
        return self._async_lock

    def _refill(self) -> None:
        """Refill tokens based on elapsed time since last refill."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        tokens_to_add = elapsed * self.config.requests_per_second
        self.tokens = min(self.config.burst_capacity, self.tokens + tokens_to_add)
        self.last_refill = now

    def get_wait_time(self) -> float:
        """Calculate time to wait for next available token.

        Returns:
            Time in seconds to wait, or 0.0 if a token is available.
        """
        with self._lock:
            self._refill()
            if self.tokens >= 1.0:
                return 0.0
            # Calculate time needed to refill to 1 token
            tokens_needed = 1.0 - self.tokens
            return tokens_needed / self.config.requests_per_second

    def try_acquire(self) -> bool:
        """Attempt to acquire a token without waiting.

        Returns:
            True if a token was acquired, False otherwise.
        """
        with self._lock:
            self._refill()
            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return True
            return False

    def acquire(self) -> None:
        """Acquire a token, blocking if necessary.

        This method will block until a token is available.
        """
        while True:
            wait_time = self.get_wait_time()
            if wait_time <= 0:
                if self.try_acquire():
                    return
            else:
                time.sleep(wait_time)

    async def acquire_async(self) -> None:
        """Acquire a token asynchronously, waiting if necessary.

        This method will await until a token is available.
        """
        async with self._get_async_lock():
            while True:
                wait_time = self.get_wait_time()
                if wait_time <= 0:
                    if self.try_acquire():
                        return
                else:
                    await asyncio.sleep(wait_time)


class RateLimitedAdapter(HTTPAdapter):
    """HTTP adapter that implements rate limiting with retry on 429.

    This adapter wraps requests to enforce rate limiting using a token bucket
    and handles HTTP 429 (Too Many Requests) responses with exponential backoff.

    Attributes:
        rate_limiter: TokenBucket instance for rate limiting
        config: Rate limit configuration
    """

    def __init__(
        self,
        rate_limiter: TokenBucket,
        config: RateLimitConfig | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Initialize the rate limited adapter.

        Args:
            rate_limiter: TokenBucket instance for rate limiting
            config: Optional rate limit configuration (uses rate_limiter's config
                   if None)
            *args: Additional positional arguments for HTTPAdapter
            **kwargs: Additional keyword arguments for HTTPAdapter
        """
        super().__init__(*args, **kwargs)
        self.rate_limiter = rate_limiter
        self.config = config or rate_limiter.config

    def send(
        self,
        request: PreparedRequest,
        stream: bool = False,  # noqa: FBT001, FBT002
        timeout: float | tuple[float, float] | None = None,
        verify: bool | str = True,  # noqa: FBT001, FBT002
        cert: str | tuple[str, str] | None = None,
        proxies: dict[str, str] | None = None,
    ) -> Response:
        """Send a request with rate limiting and retry on 429.

        Args:
            request: The prepared request to send
            stream: Whether to stream the response
            timeout: Request timeout
            verify: SSL verification setting
            cert: Client certificate
            proxies: Proxy settings

        Returns:
            Response from the server

        Raises:
            Exception: If max retries exceeded on 429 responses
        """
        retries = 0
        while True:
            # Acquire rate limit token before sending
            self.rate_limiter.acquire()

            logger.debug(f"Sending request to {request.url}")
            response = super().send(
                request,
                stream=stream,
                timeout=timeout,
                verify=verify,
                cert=cert,
                proxies=proxies,
            )

            if response.status_code != 429:
                return response

            # Handle rate limit response
            retries += 1
            if retries > self.config.max_retries:
                logger.error(
                    f"Max retries ({self.config.max_retries}) exceeded for "
                    f"{request.url}"
                )
                return response

            # Calculate backoff time
            retry_after = self._parse_retry_after(response)
            if retry_after is not None:
                wait_time = retry_after
                logger.warning(
                    f"Rate limited (429), Retry-After: {wait_time}s, "
                    f"attempt {retries}/{self.config.max_retries}"
                )
            else:
                # Exponential backoff
                wait_time = self.config.backoff_base * (2 ** (retries - 1))
                logger.warning(
                    f"Rate limited (429), exponential backoff: {wait_time}s, "
                    f"attempt {retries}/{self.config.max_retries}"
                )

            time.sleep(wait_time)

    def _parse_retry_after(self, response: Response) -> float | None:
        """Parse the Retry-After header from a response.

        Args:
            response: HTTP response to parse

        Returns:
            Retry-After value in seconds, or None if not present/parseable.
        """
        retry_after = response.headers.get("Retry-After")
        if retry_after is None:
            return None

        try:
            # Try parsing as seconds (integer)
            return float(retry_after)
        except ValueError:
            pass

        # Could also try parsing as HTTP-date, but Atlassian typically uses seconds
        logger.debug(f"Could not parse Retry-After header: {retry_after}")
        return None


class RateLimiterRegistry:
    """Singleton registry for per-service rate limiters.

    This class manages rate limiters for different Atlassian services,
    allowing service-specific rate limit configurations while sharing
    rate limiters across multiple sessions for the same service.
    """

    _instance: "RateLimiterRegistry | None" = None
    _lock = Lock()

    def __new__(cls) -> "RateLimiterRegistry":
        """Ensure singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._limiters: dict[str, TokenBucket] = {}
                    cls._instance._configs: dict[str, RateLimitConfig] = {}
        return cls._instance

    def get_limiter(self, service_name: str) -> TokenBucket:
        """Get or create a rate limiter for a service.

        Args:
            service_name: Service name (e.g., "jira", "confluence", "bitbucket")

        Returns:
            TokenBucket rate limiter for the service
        """
        service_key = service_name.lower()
        if service_key not in self._limiters:
            config = self._configs.get(service_key, get_config_from_env(service_key))
            self._limiters[service_key] = TokenBucket(config)
            logger.debug(
                f"Created rate limiter for {service_name}: "
                f"{config.requests_per_second} RPS, burst {config.burst_capacity}"
            )
        return self._limiters[service_key]

    def configure(self, service_name: str, config: RateLimitConfig) -> None:
        """Configure rate limiting for a service.

        If a limiter already exists for the service, it will be replaced.

        Args:
            service_name: Service name (e.g., "jira", "confluence", "bitbucket")
            config: Rate limit configuration for the service
        """
        service_key = service_name.lower()
        self._configs[service_key] = config
        # If limiter already exists, replace it with new config
        if service_key in self._limiters:
            self._limiters[service_key] = TokenBucket(config)
            logger.info(
                f"Reconfigured rate limiter for {service_name}: "
                f"{config.requests_per_second} RPS, burst {config.burst_capacity}"
            )

    def reset(self) -> None:
        """Reset the registry (primarily for testing).

        Clears all configured limiters and configurations.
        """
        self._limiters.clear()
        self._configs.clear()


def get_rate_limiter_registry() -> RateLimiterRegistry:
    """Get the global rate limiter registry.

    Returns:
        The singleton RateLimiterRegistry instance.
    """
    return RateLimiterRegistry()


def configure_rate_limiting(session: Session, service_name: str) -> None:
    """Configure rate limiting for a requests session.

    This is the main integration function that mounts a RateLimitedAdapter
    on the session for both HTTP and HTTPS requests.

    Args:
        session: The requests Session to configure
        service_name: Service name (e.g., "jira", "confluence", "bitbucket")
    """
    registry = get_rate_limiter_registry()
    rate_limiter = registry.get_limiter(service_name)
    config = registry._configs.get(
        service_name.lower(), get_config_from_env(service_name)
    )

    adapter = RateLimitedAdapter(rate_limiter, config)

    # Mount for all URLs (rate limiting is per-service, not per-domain)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    logger.debug(f"Configured rate limiting for {service_name} session")
