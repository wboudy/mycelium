"""
Tests for the mycelium.llm module.

Test mode: SMOKE
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from mycelium.llm import (
    CompletionResponse,
    UsageMetadata,
    _calculate_cost,
    _verify_api_keys,
    complete,
)


class TestUsageMetadata:
    """Tests for UsageMetadata dataclass."""

    def test_to_dict(self):
        """Usage metadata converts to dict correctly."""
        usage = UsageMetadata(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            cost_usd=0.001234,
            model="anthropic/claude-sonnet-4-20250514",
        )
        
        result = usage.to_dict()
        
        assert result["prompt_tokens"] == 100
        assert result["completion_tokens"] == 50
        assert result["total_tokens"] == 150
        assert result["cost_usd"] == 0.001234
        assert result["model"] == "anthropic/claude-sonnet-4-20250514"

    def test_default_values(self):
        """Usage metadata has sensible defaults."""
        usage = UsageMetadata()
        
        assert usage.prompt_tokens == 0
        assert usage.completion_tokens == 0
        assert usage.total_tokens == 0
        assert usage.cost_usd == 0.0
        assert usage.model == ""


class TestCompletionResponse:
    """Tests for CompletionResponse dataclass."""

    def test_to_dict(self):
        """Completion response converts to dict correctly."""
        usage = UsageMetadata(total_tokens=100)
        response = CompletionResponse(
            content="Hello, world!",
            usage=usage,
            success=True,
            error=None,
        )
        
        result = response.to_dict()
        
        assert result["content"] == "Hello, world!"
        assert result["success"] is True
        assert result["error"] is None
        assert result["usage"]["total_tokens"] == 100

    def test_error_response(self):
        """Error response captures error message."""
        response = CompletionResponse(
            success=False,
            error="API key not found",
        )
        
        assert response.success is False
        assert response.error == "API key not found"
        assert response.content == ""


class TestVerifyApiKeys:
    """Tests for _verify_api_keys helper."""

    def test_no_keys(self):
        """Returns empty list when no keys are set."""
        with patch.dict("os.environ", {}, clear=True):
            result = _verify_api_keys()
            assert result == []

    def test_anthropic_key(self):
        """Detects Anthropic key."""
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}, clear=True):
            result = _verify_api_keys()
            assert "anthropic" in result

    def test_openai_key(self):
        """Detects OpenAI key."""
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-test"}, clear=True):
            result = _verify_api_keys()
            assert "openai" in result

    def test_google_key(self):
        """Detects Google key."""
        with patch.dict("os.environ", {"GOOGLE_API_KEY": "test"}, clear=True):
            result = _verify_api_keys()
            assert "google" in result

    def test_gemini_key_alias(self):
        """Detects GEMINI_API_KEY alias."""
        with patch.dict("os.environ", {"GEMINI_API_KEY": "test"}, clear=True):
            result = _verify_api_keys()
            assert "google" in result

    def test_multiple_keys(self):
        """Detects multiple providers."""
        env = {
            "ANTHROPIC_API_KEY": "sk-test",
            "OPENAI_API_KEY": "sk-test",
        }
        with patch.dict("os.environ", env, clear=True):
            result = _verify_api_keys()
            assert "anthropic" in result
            assert "openai" in result


class TestCalculateCost:
    """Tests for _calculate_cost helper."""

    def test_fallback_estimate(self):
        """Falls back to estimate when litellm cost calc fails."""
        # Use a fake model to trigger fallback
        cost = _calculate_cost("fake/model", 1000, 500)
        
        # Should return some non-zero estimate
        assert cost > 0
        assert isinstance(cost, float)


class TestComplete:
    """Tests for complete() function."""

    def test_no_api_keys_error(self):
        """Returns error when no API keys are set."""
        with patch.dict("os.environ", {}, clear=True):
            response = complete(
                messages=[{"role": "user", "content": "Hello"}],
            )
            
            assert response.success is False
            assert "No API keys found" in response.error

    def test_returns_structured_response(self):
        """Returns CompletionResponse with usage metadata."""
        # Mock litellm.completion
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50
        
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}):
            with patch("mycelium.llm.litellm.completion", return_value=mock_response):
                with patch("mycelium.llm._calculate_cost", return_value=0.005):
                    response = complete(
                        messages=[{"role": "user", "content": "Hello"}],
                        agent_role="scientist",
                    )
        
        assert response.success is True
        assert response.content == "Test response"
        assert response.usage.prompt_tokens == 100
        assert response.usage.completion_tokens == 50
        assert response.usage.total_tokens == 150
        assert response.usage.cost_usd == 0.005

    def test_retry_on_rate_limit(self):
        """Retries on rate limit errors."""
        import litellm
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Success after retry"
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50
        
        # Fail twice, then succeed
        call_count = [0]
        
        def mock_completion(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] < 3:
                raise litellm.RateLimitError(
                    message="Rate limit exceeded",
                    llm_provider="anthropic",
                    model="claude",
                    response=MagicMock(),
                )
            return mock_response
        
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}):
            with patch("mycelium.llm.litellm.completion", side_effect=mock_completion):
                with patch("mycelium.llm._calculate_cost", return_value=0.005):
                    with patch("time.sleep"):  # Skip actual sleep
                        response = complete(
                            messages=[{"role": "user", "content": "Hello"}],
                        )
        
        assert response.success is True
        assert call_count[0] == 3  # Two failures + one success

    def test_no_retry_on_auth_error(self):
        """Does not retry on authentication errors."""
        import litellm
        
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}):
            with patch(
                "mycelium.llm.litellm.completion",
                side_effect=litellm.AuthenticationError(
                    message="Invalid API key",
                    llm_provider="anthropic",
                    model="claude",
                    response=MagicMock(),
                ),
            ):
                response = complete(
                    messages=[{"role": "user", "content": "Hello"}],
                )
        
        assert response.success is False
        assert "Authentication failed" in response.error

    def test_exhausted_retries(self):
        """Returns error after all retries exhausted."""
        import litellm
        
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}):
            with patch(
                "mycelium.llm.litellm.completion",
                side_effect=litellm.RateLimitError(
                    message="Rate limit exceeded",
                    llm_provider="anthropic",
                    model="claude",
                    response=MagicMock(),
                ),
            ):
                with patch("time.sleep"):  # Skip actual sleep
                    response = complete(
                        messages=[{"role": "user", "content": "Hello"}],
                    )
        
        assert response.success is False
        assert "Failed after 3 retries" in response.error
