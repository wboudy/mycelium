"""
LLM Interface Module for Mycelium.

Provides a unified interface to LLM providers via LiteLLM.
Supports Anthropic, OpenAI, and Google via environment variables:
  - ANTHROPIC_API_KEY
  - OPENAI_API_KEY  
  - GOOGLE_API_KEY (or GEMINI_API_KEY)
"""

from __future__ import annotations

import json
import logging
import math
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


def _coerce_non_negative_int(value: Any) -> int:
    """Coerce int/float-like values to non-negative ints."""
    if value is None or isinstance(value, bool):
        return 0

    if isinstance(value, (int, float)):
        parsed = float(value)
    elif isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return 0
        try:
            parsed = float(stripped)
        except ValueError:
            return 0
    else:
        return 0

    if not math.isfinite(parsed) or parsed < 0:
        return 0
    return int(parsed)


def _normalize_tool_call(raw_tool_call: Any, fallback_index: int) -> dict[str, Any] | None:
    """Normalize a single provider tool-call payload."""
    if isinstance(raw_tool_call, dict):
        raw_id = raw_tool_call.get("id")
        raw_function = raw_tool_call.get("function")
    else:
        raw_id = getattr(raw_tool_call, "id", None)
        raw_function = getattr(raw_tool_call, "function", None)

    if isinstance(raw_function, dict):
        raw_name = raw_function.get("name")
        raw_arguments = raw_function.get("arguments")
    else:
        raw_name = getattr(raw_function, "name", None)
        raw_arguments = getattr(raw_function, "arguments", None)

    if not isinstance(raw_name, str):
        return None
    name = raw_name.strip()
    if not name:
        return None

    call_id = str(raw_id).strip() if raw_id is not None else ""
    if not call_id:
        call_id = f"tool_call_{fallback_index}"

    if raw_arguments is None:
        arguments = "{}"
    elif isinstance(raw_arguments, str):
        arguments = raw_arguments
    else:
        try:
            arguments = json.dumps(raw_arguments)
        except (TypeError, ValueError):
            arguments = str(raw_arguments)

    return {"id": call_id, "name": name, "arguments": arguments}


def _normalize_message_content(raw_content: Any) -> str:
    """Normalize provider message content to plain text."""
    if raw_content is None:
        return ""
    if isinstance(raw_content, str):
        return raw_content

    if isinstance(raw_content, list):
        normalized_parts: list[str] = []
        for part in raw_content:
            text_value: str | None = None
            if isinstance(part, dict):
                if isinstance(part.get("text"), str):
                    text_value = part["text"]
                elif isinstance(part.get("content"), str):
                    text_value = part["content"]
            else:
                candidate_text = getattr(part, "text", None)
                if isinstance(candidate_text, str):
                    text_value = candidate_text

            if text_value is None:
                part_text = str(part).strip()
                if part_text:
                    normalized_parts.append(part_text)
            elif text_value.strip():
                normalized_parts.append(text_value.strip())

        return "\n".join(normalized_parts).strip()

    return str(raw_content)


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
            content = _normalize_message_content(getattr(message, "content", ""))
            
            # Extract tool calls if present
            extracted_tool_calls = None
            raw_tool_calls = getattr(message, "tool_calls", None)
            if raw_tool_calls:
                if isinstance(raw_tool_calls, list):
                    tool_call_items = raw_tool_calls
                else:
                    tool_call_items = [raw_tool_calls]

                normalized_tool_calls = []
                for idx, raw_tool_call in enumerate(tool_call_items, start=1):
                    normalized = _normalize_tool_call(raw_tool_call, idx)
                    if normalized:
                        normalized_tool_calls.append(normalized)
                    else:
                        logger.warning(f"Skipping malformed tool call payload: {raw_tool_call!r}")

                if normalized_tool_calls:
                    extracted_tool_calls = normalized_tool_calls
                    logger.info(f"LLM returned {len(extracted_tool_calls)} tool call(s)")
            
            # Extract usage metadata
            usage_data = getattr(response, "usage", None)
            prompt_tokens = _coerce_non_negative_int(getattr(usage_data, "prompt_tokens", 0))
            completion_tokens = _coerce_non_negative_int(getattr(usage_data, "completion_tokens", 0))
            reported_total_tokens = _coerce_non_negative_int(getattr(usage_data, "total_tokens", 0))
            total_tokens = reported_total_tokens or (prompt_tokens + completion_tokens)
            
            # Calculate cost
            try:
                cost_usd = _calculate_cost(model, prompt_tokens, completion_tokens)
            except Exception as e:
                logger.warning(f"Cost calculation failed for {model}: {e}")
                cost_usd = 0.0

            if not isinstance(cost_usd, (int, float)) or not math.isfinite(cost_usd) or cost_usd < 0:
                cost_usd = 0.0
            
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
