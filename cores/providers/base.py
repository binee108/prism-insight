"""
Base abstract interface for LLM providers.

This module defines the common interface that all LLM providers must implement,
whether they are API-based (HTTP) or CLI-based (subprocess).
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class BaseLLMProvider(ABC):
    """
    Abstract base class for all LLM providers.

    This interface allows prism-insight to treat different LLM sources
    (OpenAI API, Anthropic API, Claude Code CLI, etc.) uniformly.
    """

    @abstractmethod
    async def generate(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate a response from the LLM.

        Args:
            messages: List of message dicts with 'role' and 'content' keys
                     e.g., [{'role': 'user', 'content': 'Hello'}]
            model: Model name/identifier (provider-specific)
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0.0 - 1.0)
            **kwargs: Additional provider-specific parameters

        Returns:
            Dict with keys:
                - content: str - The generated response text
                - usage: dict - Token usage information
                - error: str (optional) - Error message if generation failed
        """
        pass

    @abstractmethod
    async def generate_str(
        self,
        prompt: str,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> str:
        """
        Simplified interface that takes a single prompt string.

        Args:
            prompt: Single prompt string
            model: Model name/identifier (provider-specific)
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature (0.0 - 1.0)
            **kwargs: Additional provider-specific parameters

        Returns:
            str: The generated response text

        Raises:
            Exception: If generation fails
        """
        pass
