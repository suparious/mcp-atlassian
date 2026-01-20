"""Tests for the rate limiting utilities module."""

import time
from unittest.mock import MagicMock, patch

import pytest
from requests import PreparedRequest, Response, Session

from mcp_atlassian.utils.rate_limit import (
    RateLimitConfig,
    RateLimitedAdapter,
    RateLimiterRegistry,
    TokenBucket,
    configure_rate_limiting,
    get_config_from_env,
    get_rate_limiter_registry,
)


class TestRateLimitConfig:
    """Test the RateLimitConfig dataclass."""

    def test_default_values(self):
        """Test that default values are set correctly."""
        config = RateLimitConfig()
        assert config.requests_per_second == 10.0
        assert config.burst_capacity == 20
        assert config.backoff_base == 1.0
        assert config.max_retries == 5

    def test_custom_values(self):
        """Test that custom values are set correctly."""
        config = RateLimitConfig(
            requests_per_second=5.0,
            burst_capacity=10,
            backoff_base=2.0,
            max_retries=3,
        )
        assert config.requests_per_second == 5.0
        assert config.burst_capacity == 10
        assert config.backoff_base == 2.0
        assert config.max_retries == 3


class TestGetConfigFromEnv:
    """Test the get_config_from_env function."""

    def test_default_values_no_env(self, monkeypatch):
        """Test default values when no environment variables are set."""
        # Clear any existing env vars
        for var in [
            "ATLASSIAN_RATE_LIMIT_RPS",
            "ATLASSIAN_RATE_LIMIT_BURST",
            "ATLASSIAN_RATE_LIMIT_BACKOFF_BASE",
            "ATLASSIAN_RATE_LIMIT_MAX_RETRIES",
        ]:
            monkeypatch.delenv(var, raising=False)

        config = get_config_from_env()
        assert config.requests_per_second == 10.0
        assert config.burst_capacity == 20
        assert config.backoff_base == 1.0
        assert config.max_retries == 5

    def test_global_env_vars(self, monkeypatch):
        """Test that global environment variables are read correctly."""
        monkeypatch.setenv("ATLASSIAN_RATE_LIMIT_RPS", "5.0")
        monkeypatch.setenv("ATLASSIAN_RATE_LIMIT_BURST", "15")
        monkeypatch.setenv("ATLASSIAN_RATE_LIMIT_BACKOFF_BASE", "2.5")
        monkeypatch.setenv("ATLASSIAN_RATE_LIMIT_MAX_RETRIES", "3")

        config = get_config_from_env()
        assert config.requests_per_second == 5.0
        assert config.burst_capacity == 15
        assert config.backoff_base == 2.5
        assert config.max_retries == 3

    def test_service_specific_env_vars(self, monkeypatch):
        """Test that service-specific environment variables override globals."""
        monkeypatch.setenv("ATLASSIAN_RATE_LIMIT_RPS", "10.0")
        monkeypatch.setenv("JIRA_RATE_LIMIT_RPS", "5.0")
        monkeypatch.setenv("JIRA_RATE_LIMIT_BURST", "25")

        config = get_config_from_env("jira")
        assert config.requests_per_second == 5.0
        assert config.burst_capacity == 25
        # Should use global default for other values
        assert config.backoff_base == 1.0
        assert config.max_retries == 5

    def test_invalid_env_values_use_default(self, monkeypatch):
        """Test that invalid environment values fall back to defaults."""
        monkeypatch.setenv("ATLASSIAN_RATE_LIMIT_RPS", "invalid")
        monkeypatch.setenv("ATLASSIAN_RATE_LIMIT_BURST", "not_a_number")

        with patch("mcp_atlassian.utils.rate_limit.logger") as mock_logger:
            config = get_config_from_env()
            assert config.requests_per_second == 10.0
            assert config.burst_capacity == 20
            # Should have logged warnings
            assert mock_logger.warning.call_count >= 2


class TestTokenBucket:
    """Test the TokenBucket class."""

    def test_initialization(self):
        """Test that token bucket initializes with burst capacity."""
        config = RateLimitConfig(burst_capacity=10)
        bucket = TokenBucket(config)
        assert bucket.tokens == 10.0

    def test_try_acquire_success(self):
        """Test successful token acquisition."""
        config = RateLimitConfig(burst_capacity=5)
        bucket = TokenBucket(config)

        assert bucket.try_acquire() is True
        assert bucket.tokens == 4.0

    def test_try_acquire_depleted(self):
        """Test that try_acquire returns False when tokens are depleted."""
        config = RateLimitConfig(burst_capacity=2)
        bucket = TokenBucket(config)

        assert bucket.try_acquire() is True
        assert bucket.try_acquire() is True
        assert bucket.try_acquire() is False

    def test_get_wait_time_with_tokens(self):
        """Test that wait time is 0 when tokens are available."""
        config = RateLimitConfig(burst_capacity=5)
        bucket = TokenBucket(config)

        assert bucket.get_wait_time() == 0.0

    def test_get_wait_time_depleted(self):
        """Test that wait time is positive when tokens are depleted."""
        config = RateLimitConfig(burst_capacity=1, requests_per_second=10.0)
        bucket = TokenBucket(config)

        bucket.try_acquire()  # Deplete tokens
        wait_time = bucket.get_wait_time()
        assert wait_time > 0
        assert wait_time <= 0.1  # Should be about 0.1s for 10 RPS

    def test_refill_over_time(self):
        """Test that tokens refill based on elapsed time."""
        config = RateLimitConfig(burst_capacity=5, requests_per_second=100.0)
        bucket = TokenBucket(config)

        # Deplete all tokens
        for _ in range(5):
            bucket.try_acquire()
        # Tokens should be very close to 0 (might have tiny refill during loop)
        assert bucket.tokens < 0.1

        # Wait a bit for refill
        time.sleep(0.05)  # 50ms should add ~5 tokens at 100 RPS

        # Check refill occurred
        bucket._refill()
        assert bucket.tokens >= 4.0  # Should have refilled most tokens

    def test_tokens_capped_at_burst_capacity(self):
        """Test that tokens don't exceed burst capacity."""
        config = RateLimitConfig(burst_capacity=5, requests_per_second=100.0)
        bucket = TokenBucket(config)

        # Wait for more tokens than capacity
        time.sleep(0.1)
        bucket._refill()

        assert bucket.tokens == 5.0  # Capped at burst_capacity

    def test_acquire_blocks_until_token_available(self):
        """Test that acquire blocks until a token is available."""
        config = RateLimitConfig(burst_capacity=1, requests_per_second=50.0)
        bucket = TokenBucket(config)

        bucket.try_acquire()  # Deplete tokens

        start_time = time.monotonic()
        bucket.acquire()  # Should block
        elapsed = time.monotonic() - start_time

        # Should have waited approximately 0.02s (1/50 RPS)
        assert elapsed >= 0.01
        assert elapsed < 0.1

    @pytest.mark.asyncio
    async def test_acquire_async(self):
        """Test async token acquisition."""
        config = RateLimitConfig(burst_capacity=1, requests_per_second=50.0)
        bucket = TokenBucket(config)

        bucket.try_acquire()  # Deplete tokens

        start_time = time.monotonic()
        await bucket.acquire_async()
        elapsed = time.monotonic() - start_time

        # Should have waited approximately 0.02s
        assert elapsed >= 0.01


class TestRateLimitedAdapter:
    """Test the RateLimitedAdapter class."""

    def test_successful_request(self):
        """Test that successful requests pass through."""
        config = RateLimitConfig(burst_capacity=5)
        bucket = TokenBucket(config)
        adapter = RateLimitedAdapter(bucket, config)

        # Create mock request and response
        request = MagicMock(spec=PreparedRequest)
        request.url = "https://example.com/api"

        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200

        with patch.object(
            adapter.__class__.__bases__[0], "send", return_value=mock_response
        ):
            response = adapter.send(request)

        assert response.status_code == 200

    def test_429_with_retry_after_header(self):
        """Test that 429 responses with Retry-After header are handled."""
        config = RateLimitConfig(burst_capacity=10, max_retries=3)
        bucket = TokenBucket(config)
        adapter = RateLimitedAdapter(bucket, config)

        request = MagicMock(spec=PreparedRequest)
        request.url = "https://example.com/api"

        # Create responses: first 429, then 200
        rate_limit_response = MagicMock(spec=Response)
        rate_limit_response.status_code = 429
        rate_limit_response.headers = {"Retry-After": "0.01"}

        success_response = MagicMock(spec=Response)
        success_response.status_code = 200

        with patch.object(
            adapter.__class__.__bases__[0],
            "send",
            side_effect=[rate_limit_response, success_response],
        ):
            with patch("mcp_atlassian.utils.rate_limit.time.sleep") as mock_sleep:
                response = adapter.send(request)

        assert response.status_code == 200
        mock_sleep.assert_called_once()

    def test_429_with_exponential_backoff(self):
        """Test exponential backoff when no Retry-After header."""
        config = RateLimitConfig(burst_capacity=10, backoff_base=0.01, max_retries=3)
        bucket = TokenBucket(config)
        adapter = RateLimitedAdapter(bucket, config)

        request = MagicMock(spec=PreparedRequest)
        request.url = "https://example.com/api"

        rate_limit_response = MagicMock(spec=Response)
        rate_limit_response.status_code = 429
        rate_limit_response.headers = {}  # No Retry-After

        success_response = MagicMock(spec=Response)
        success_response.status_code = 200

        with patch.object(
            adapter.__class__.__bases__[0],
            "send",
            side_effect=[rate_limit_response, rate_limit_response, success_response],
        ):
            with patch("mcp_atlassian.utils.rate_limit.time.sleep") as mock_sleep:
                response = adapter.send(request)

        assert response.status_code == 200
        assert mock_sleep.call_count == 2
        # Check exponential backoff: 0.01, 0.02
        calls = mock_sleep.call_args_list
        assert calls[0][0][0] == pytest.approx(0.01)
        assert calls[1][0][0] == pytest.approx(0.02)

    def test_429_max_retries_exceeded(self):
        """Test that max retries is respected."""
        config = RateLimitConfig(burst_capacity=10, max_retries=2, backoff_base=0.001)
        bucket = TokenBucket(config)
        adapter = RateLimitedAdapter(bucket, config)

        request = MagicMock(spec=PreparedRequest)
        request.url = "https://example.com/api"

        rate_limit_response = MagicMock(spec=Response)
        rate_limit_response.status_code = 429
        rate_limit_response.headers = {}

        with patch.object(
            adapter.__class__.__bases__[0], "send", return_value=rate_limit_response
        ):
            with patch("mcp_atlassian.utils.rate_limit.time.sleep"):
                response = adapter.send(request)

        # Should return the 429 response after max retries
        assert response.status_code == 429

    def test_parse_retry_after_seconds(self):
        """Test parsing Retry-After header as seconds."""
        config = RateLimitConfig()
        bucket = TokenBucket(config)
        adapter = RateLimitedAdapter(bucket, config)

        response = MagicMock(spec=Response)
        response.headers = {"Retry-After": "30"}

        assert adapter._parse_retry_after(response) == 30.0

    def test_parse_retry_after_missing(self):
        """Test handling missing Retry-After header."""
        config = RateLimitConfig()
        bucket = TokenBucket(config)
        adapter = RateLimitedAdapter(bucket, config)

        response = MagicMock(spec=Response)
        response.headers = {}

        assert adapter._parse_retry_after(response) is None

    def test_parse_retry_after_invalid(self):
        """Test handling invalid Retry-After header."""
        config = RateLimitConfig()
        bucket = TokenBucket(config)
        adapter = RateLimitedAdapter(bucket, config)

        response = MagicMock(spec=Response)
        response.headers = {"Retry-After": "invalid"}

        assert adapter._parse_retry_after(response) is None


class TestRateLimiterRegistry:
    """Test the RateLimiterRegistry singleton."""

    def setup_method(self):
        """Reset the registry before each test."""
        registry = get_rate_limiter_registry()
        registry.reset()

    def test_singleton_behavior(self):
        """Test that registry is a singleton."""
        registry1 = RateLimiterRegistry()
        registry2 = RateLimiterRegistry()
        assert registry1 is registry2

    def test_get_limiter_creates_new(self):
        """Test that get_limiter creates a new limiter if not exists."""
        registry = get_rate_limiter_registry()
        limiter = registry.get_limiter("jira")
        assert isinstance(limiter, TokenBucket)

    def test_get_limiter_returns_same(self):
        """Test that get_limiter returns the same limiter for same service."""
        registry = get_rate_limiter_registry()
        limiter1 = registry.get_limiter("jira")
        limiter2 = registry.get_limiter("jira")
        assert limiter1 is limiter2

    def test_get_limiter_case_insensitive(self):
        """Test that service names are case-insensitive."""
        registry = get_rate_limiter_registry()
        limiter1 = registry.get_limiter("JIRA")
        limiter2 = registry.get_limiter("jira")
        assert limiter1 is limiter2

    def test_different_services_different_limiters(self):
        """Test that different services get different limiters."""
        registry = get_rate_limiter_registry()
        jira_limiter = registry.get_limiter("jira")
        confluence_limiter = registry.get_limiter("confluence")
        assert jira_limiter is not confluence_limiter

    def test_configure_service(self):
        """Test configuring a service with custom config."""
        registry = get_rate_limiter_registry()
        config = RateLimitConfig(requests_per_second=5.0, burst_capacity=10)
        registry.configure("jira", config)

        limiter = registry.get_limiter("jira")
        assert limiter.config.requests_per_second == 5.0
        assert limiter.config.burst_capacity == 10

    def test_configure_replaces_existing(self):
        """Test that configure replaces an existing limiter."""
        registry = get_rate_limiter_registry()

        # Create initial limiter
        limiter1 = registry.get_limiter("jira")

        # Configure with new config
        new_config = RateLimitConfig(requests_per_second=1.0)
        registry.configure("jira", new_config)

        limiter2 = registry.get_limiter("jira")
        assert limiter1 is not limiter2
        assert limiter2.config.requests_per_second == 1.0

    def test_reset_clears_limiters(self):
        """Test that reset clears all limiters."""
        registry = get_rate_limiter_registry()
        limiter1 = registry.get_limiter("jira")
        registry.reset()
        limiter2 = registry.get_limiter("jira")
        assert limiter1 is not limiter2


class TestConfigureRateLimiting:
    """Test the configure_rate_limiting function."""

    def setup_method(self):
        """Reset the registry before each test."""
        registry = get_rate_limiter_registry()
        registry.reset()

    def test_mounts_adapter_on_session(self):
        """Test that the adapter is mounted on the session."""
        session = MagicMock(spec=Session)

        configure_rate_limiting(session, "jira")

        assert session.mount.call_count == 2
        calls = session.mount.call_args_list
        prefixes = [call[0][0] for call in calls]
        assert "https://" in prefixes
        assert "http://" in prefixes

    def test_mounted_adapter_type(self):
        """Test that mounted adapter is RateLimitedAdapter."""
        session = Session()

        configure_rate_limiting(session, "jira")

        # Check that RateLimitedAdapter is mounted
        https_adapter = session.get_adapter("https://example.com")
        http_adapter = session.get_adapter("http://example.com")
        assert isinstance(https_adapter, RateLimitedAdapter)
        assert isinstance(http_adapter, RateLimitedAdapter)

    def test_uses_registry_limiter(self):
        """Test that configure_rate_limiting uses the registry limiter."""
        registry = get_rate_limiter_registry()
        session = MagicMock(spec=Session)

        configure_rate_limiting(session, "jira")

        # Verify that a limiter was created in the registry
        limiter = registry.get_limiter("jira")
        assert limiter is not None
