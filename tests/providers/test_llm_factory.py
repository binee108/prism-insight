"""
Unit tests for LLM Factory.

These tests verify provider selection logic and configuration.
"""

import os
import pytest
from unittest.mock import patch, Mock
from cores.llm_factory import (
    get_llm_provider_class,
    get_default_llm_provider,
    is_cli_provider,
    get_provider_info,
)


class TestLLMFactory:
    """Test suite for LLM factory functions."""

    def test_get_llm_provider_openai(self):
        """Test selecting OpenAI provider."""
        with patch.dict(os.environ, {"PRISM_LLM_PROVIDER": "openai"}):
            with patch('cores.llm_factory.OpenAIAugmentedLLM', Mock()) as mock_provider:
                provider_class = get_llm_provider_class()
                # Note: This will try to import, which may fail in test environment
                # In real usage, mcp-agent would be installed

    def test_get_llm_provider_cli(self):
        """Test selecting CLI provider."""
        provider_class = get_llm_provider_class("claude-code-cli")

        # Verify it returns the CLI provider class
        assert provider_class.__name__ == "ClaudeCodeCLIAugmentedLLM"

    def test_get_llm_provider_invalid(self):
        """Test error handling for invalid provider."""
        with pytest.raises(ValueError) as exc_info:
            get_llm_provider_class("invalid-provider")

        assert "Unknown provider" in str(exc_info.value)

    def test_get_default_llm_provider(self):
        """Test getting default provider."""
        with patch.dict(os.environ, {"PRISM_LLM_PROVIDER": "claude-code-cli"}):
            provider_class = get_default_llm_provider()
            assert provider_class.__name__ == "ClaudeCodeCLIAugmentedLLM"

    def test_is_cli_provider_true(self):
        """Test is_cli_provider returns True for CLI."""
        with patch.dict(os.environ, {"PRISM_LLM_PROVIDER": "claude-code-cli"}):
            assert is_cli_provider() is True

    def test_is_cli_provider_false(self):
        """Test is_cli_provider returns False for API providers."""
        with patch.dict(os.environ, {"PRISM_LLM_PROVIDER": "openai"}):
            assert is_cli_provider() is False

    def test_get_provider_info_cli(self):
        """Test getting provider info for CLI."""
        with patch.dict(os.environ, {
            "PRISM_LLM_PROVIDER": "claude-code-cli",
            "CLAUDE_CLI_PATH": "/usr/bin/claude",
            "CLAUDE_CLI_PROJECT": "/home/user/project",
            "CLAUDE_CLI_MODEL": "claude-3-5-sonnet-20241022",
            "CLAUDE_CLI_TIMEOUT": "300"
        }):
            info = get_provider_info()

            assert info["provider"] == "claude-code-cli"
            assert info["is_cli"] is True
            assert info["cli_path"] == "/usr/bin/claude"
            assert info["cli_project"] == "/home/user/project"
            assert info["cli_model"] == "claude-3-5-sonnet-20241022"
            assert info["cli_timeout"] == "300"

    def test_get_provider_info_api(self):
        """Test getting provider info for API provider."""
        with patch.dict(os.environ, {"PRISM_LLM_PROVIDER": "openai"}):
            info = get_provider_info()

            assert info["provider"] == "openai"
            assert info["is_cli"] is False
            assert "cli_path" not in info


class TestProviderAliases:
    """Test provider name aliases."""

    def test_claude_cli_alias(self):
        """Test 'claude-cli' alias."""
        provider_class = get_llm_provider_class("claude-cli")
        assert provider_class.__name__ == "ClaudeCodeCLIAugmentedLLM"

    def test_cli_alias(self):
        """Test 'cli' alias."""
        provider_class = get_llm_provider_class("cli")
        assert provider_class.__name__ == "ClaudeCodeCLIAugmentedLLM"


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
