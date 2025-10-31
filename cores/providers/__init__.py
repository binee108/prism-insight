"""
LLM Provider abstraction layer for prism-insight.

This module provides a unified interface for different LLM providers,
including API-based providers (OpenAI, Anthropic) and CLI-based providers (Claude Code CLI).
"""

from .base import BaseLLMProvider
from .claude_code_cli import ClaudeCodeCLIProvider

__all__ = [
    'BaseLLMProvider',
    'ClaudeCodeCLIProvider',
]
