"""
LLM Interface Module for Mycelium.

Provides a unified interface to LLM providers via LiteLLM.
Supports Anthropic, OpenAI, and Google via environment variables:
  - ANTHROPIC_API_KEY
  - OPENAI_API_KEY  
  - GOOGLE_API_KEY (or GEMINI_API_KEY)
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

import litellm

# Configure litellm logging
litellm.set_verbose = False

logger = logging.getLogger(__name__)

# Default model to use (Claude claude-sonnet-4-20250514)
DEFAULT_MODEL = "anthropic/claude-sonnet-4-20250514"

# Retry configuration per CONTRACT.md orchestration rules
MAX_RETRIES = 3
INITIAL_BACKOFF_SECONDS = 1.0
BACKOFF_MULTIPLIER = 2.0


@dataclass
class UsageMetadata:
    """Token usage and cost metadata from LLM completion."""
    
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    model: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "cost_usd": round(self.cost_usd, 6),
            "model": self.model,
        }


@dataclass
class CompletionResponse:
    """Response from LLM completion with content and usage metadata."""
    
    content: str = ""
    usage: UsageMetadata = field(default_factory=UsageMetadata)
    success: bool = True
    error: str | None = None
    tool_calls: list[dict[str, Any]] | None = None  # List of {id, name, arguments}
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for YAML serialization."""
        result = {
            "content": self.content,
            "usage": self.usage.to_dict(),
            "success": self.success,
            "error": self.error,
        }
        if self.tool_calls:
            result["tool_calls"] = self.tool_calls
        return result


def _calculate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """
    Calculate estimated USD cost for token usage.
    
    Uses LiteLLM's cost calculation when available, falls back to estimates.
    Note: These are estimates and may differ from actual provider billing.
    """
    try:
        # LiteLLM provides cost calculation for many models
        cost = litellm.completion_cost(
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        return cost if cost else 0.0
    except Exception:
        # Fallback: rough estimates based on common pricing
        # These are approximate and should be treated as estimates only
        logger.warning(f"Could not calculate exact cost for {model}, using estimate")
        
        # Default pricing estimates (per 1M tokens)
        # Updated to reflect cheaper modern models (Gemini 1.5/Flash, Claude Haiku)
        input_cost_per_1m = 0.50   # $0.50 per 1M input tokens
        output_cost_per_1m = 2.00  # $2.00 per 1M output tokens
        
        input_cost = (prompt_tokens / 1_000_000) * input_cost_per_1m
        output_cost = (completion_tokens / 1_000_000) * output_cost_per_1m
        
        return input_cost + output_cost


def _verify_api_keys() -> list[str]:
    """
    Verify which API keys are available.
    
    Returns list of available providers.
    """
    available = []
    
    if os.environ.get("ANTHROPIC_API_KEY"):
        available.append("anthropic")
    if os.environ.get("OPENAI_API_KEY"):
        available.append("openai")
    if os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"):
        available.append("google")
    
    return available


def complete(
    messages: list[dict[str, Any]],
    model: str = DEFAULT_MODEL,
    agent_role: str = "",
    temperature: float = 0.0,
    max_tokens: int = 8192,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: str | None = None,
) -> CompletionResponse:
    """
    Execute LLM completion via LiteLLM with retry logic.
    
    Args:
        messages: List of message dicts with 'role' and 'content' keys.
        model: Model identifier (e.g., 'anthropic/claude-sonnet-4-20250514').
        agent_role: Role of the calling agent (for logging: scientist/implementer/verifier/maintainer).
        temperature: Sampling temperature (0.0 = deterministic).
        max_tokens: Maximum tokens in response.
    
    Returns:
        CompletionResponse with content, usage metadata, and success status.
    
    Raises:
        No exceptions raised - errors are captured in response.error field.
    
    Example:
        >>> response = complete(
        ...     messages=[{"role": "user", "content": "Hello"}],
        ...     model="anthropic/claude-sonnet-4-20250514",
        ...     agent_role="scientist"
        ... )
        >>> print(response.content)
        >>> print(response.usage.total_tokens)
    """
    available_providers = _verify_api_keys()
    
    if not available_providers:
        return CompletionResponse(
            success=False,
            error="No API keys found. Set ANTHROPIC_API_KEY, OPENAI_API_KEY, or GOOGLE_API_KEY.",
        )
    
    # Check if the requested model's provider is available
    model_provider = model.split("/")[0] if "/" in model else "openai"
    
    # Map common aliases
    provider_aliases = {
        "claude": "anthropic",
        "gpt": "openai", 
        "gemini": "google",
    }
    
    for alias, provider in provider_aliases.items():
        if model.startswith(alias):
            model_provider = provider
            break
    
    if model_provider not in available_providers:
        logger.warning(
            f"Provider {model_provider} not available (no API key). "
            f"Available: {available_providers}"
        )
    
    # Retry loop with exponential backoff
    last_error: str | None = None
    backoff = INITIAL_BACKOFF_SECONDS
    
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(
                f"LLM call: model={model}, agent={agent_role}, attempt={attempt}/{MAX_RETRIES}"
            )
            
            # Build completion kwargs
            completion_kwargs = {
                "model": model,
                "messages": messages,
                "messages": messages,
                "max_tokens": max_tokens,
            }
            
            # Adjust temperature for specific models that require it
            # Gemini models often fail/warn with temp < 1.0
            if "gemini" in model.lower() and temperature == 0.0:
                logger.info(f"Adjusting temperature to 1.0 for Gemini model: {model}")
                completion_kwargs["temperature"] = 1.0
            else:
                completion_kwargs["temperature"] = temperature
            
            # Add tools if provided
            if tools:
                completion_kwargs["tools"] = tools
                if tool_choice:
                    completion_kwargs["tool_choice"] = tool_choice
            
            response = litellm.completion(**completion_kwargs)
            
            # Extract response content
            message = response.choices[0].message
            content = message.content or ""
            
            # Extract tool calls if present
            extracted_tool_calls = None
            if hasattr(message, "tool_calls") and message.tool_calls:
                extracted_tool_calls = []
                for tc in message.tool_calls:
                    tool_call_data = {
                        "id": tc.id,
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,  # JSON string
                    }
                    extracted_tool_calls.append(tool_call_data)
                logger.info(f"LLM returned {len(extracted_tool_calls)} tool call(s)")
            
            # Extract usage metadata
            usage_data = response.usage
            prompt_tokens = getattr(usage_data, "prompt_tokens", 0) or 0
            completion_tokens = getattr(usage_data, "completion_tokens", 0) or 0
            total_tokens = prompt_tokens + completion_tokens
            
            # Calculate cost
            cost_usd = _calculate_cost(model, prompt_tokens, completion_tokens)
            
            usage = UsageMetadata(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                cost_usd=cost_usd,
                model=model,
            )
            
            logger.info(
                f"LLM success: tokens={total_tokens}, cost=${cost_usd:.6f}"
            )
            
            return CompletionResponse(
                content=content,
                usage=usage,
                success=True,
                tool_calls=extracted_tool_calls,
            )
            
        except litellm.RateLimitError as e:
            last_error = f"Rate limit exceeded: {e}"
            logger.warning(f"Rate limit hit, attempt {attempt}/{MAX_RETRIES}: {e}")
            
        except litellm.AuthenticationError as e:
            # Don't retry auth errors
            return CompletionResponse(
                success=False,
                error=f"Authentication failed: {e}. Check your API key.",
            )
            
        except litellm.BadRequestError as e:
            # Don't retry bad request errors
            return CompletionResponse(
                success=False,
                error=f"Bad request: {e}",
            )
            
        except Exception as e:
            last_error = f"LLM error: {e}"
            logger.warning(f"LLM call failed, attempt {attempt}/{MAX_RETRIES}: {e}")
        
        # Exponential backoff before retry
        if attempt < MAX_RETRIES:
            logger.info(f"Retrying in {backoff:.1f}s...")
            time.sleep(backoff)
            backoff *= BACKOFF_MULTIPLIER
    
    # All retries exhausted
    return CompletionResponse(
        success=False,
        error=f"Failed after {MAX_RETRIES} retries. Last error: {last_error}",
    )
