"""
Unit tests for Claude Code CLI Provider.

These tests verify the basic functionality of the CLI provider
without requiring actual claude CLI installation.
"""

import asyncio
import os
import pytest
from unittest.mock import Mock, patch, AsyncMock
from cores.providers.claude_code_cli import ClaudeCodeCLIProvider


class TestClaudeCodeCLIProvider:
    """Test suite for ClaudeCodeCLIProvider."""

    def test_init_with_defaults(self):
        """Test provider initialization with default values."""
        provider = ClaudeCodeCLIProvider()

        assert provider.cli_path == os.getenv("CLAUDE_CLI_PATH", "claude")
        assert provider.timeout == int(os.getenv("CLAUDE_CLI_TIMEOUT", "180"))

    def test_init_with_custom_values(self):
        """Test provider initialization with custom values."""
        provider = ClaudeCodeCLIProvider(
            cli_path="/usr/bin/claude",
            project_path="/home/user/project",
            model="claude-3-5-sonnet-20241022",
            timeout=300
        )

        assert provider.cli_path == "/usr/bin/claude"
        assert provider.project_path == "/home/user/project"
        assert provider.model == "claude-3-5-sonnet-20241022"
        assert provider.timeout == 300

    def test_build_command_basic(self):
        """Test command building with basic options."""
        provider = ClaudeCodeCLIProvider(cli_path="claude")
        cmd = provider._build_command()

        assert cmd[0] == "claude"
        assert "--output-format" in cmd
        assert "stream-json" in cmd

    def test_build_command_with_model(self):
        """Test command building with model specification."""
        provider = ClaudeCodeCLIProvider(
            cli_path="claude",
            model="claude-3-5-sonnet-20241022"
        )
        cmd = provider._build_command()

        assert "--model" in cmd
        assert "claude-3-5-sonnet-20241022" in cmd

    def test_build_command_with_project(self):
        """Test command building with project path."""
        provider = ClaudeCodeCLIProvider(
            cli_path="claude",
            project_path="/home/user/project"
        )
        cmd = provider._build_command()

        assert "-p" in cmd
        assert "/home/user/project" in cmd

    def test_render_messages_single(self):
        """Test message rendering with single message."""
        provider = ClaudeCodeCLIProvider()
        messages = [
            {"role": "user", "content": "Hello Claude"}
        ]

        prompt = provider._render_messages(messages)

        assert "USER:" in prompt
        assert "Hello Claude" in prompt

    def test_render_messages_multiple(self):
        """Test message rendering with multiple messages."""
        provider = ClaudeCodeCLIProvider()
        messages = [
            {"role": "system", "content": "You are an AI assistant"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
            {"role": "user", "content": "How are you?"}
        ]

        prompt = provider._render_messages(messages)

        assert "SYSTEM:" in prompt
        assert "USER:" in prompt
        assert "ASSISTANT:" in prompt
        assert "You are an AI assistant" in prompt
        assert "Hello" in prompt
        assert "Hi there" in prompt
        assert "How are you?" in prompt

    def test_parse_output_json(self):
        """Test output parsing with JSON format."""
        provider = ClaudeCodeCLIProvider()
        json_output = '{"content": "This is the response", "usage": {"tokens": 100}}'

        result = provider._parse_output(json_output)

        assert result["content"] == "This is the response"
        assert result["usage"]["tokens"] == 100

    def test_parse_output_plain_text(self):
        """Test output parsing with plain text format."""
        provider = ClaudeCodeCLIProvider()
        text_output = "This is a plain text response"

        result = provider._parse_output(text_output)

        assert result["content"] == "This is a plain text response"
        assert result["usage"] == {}

    def test_parse_output_multiline_json(self):
        """Test output parsing with stream-json (last line)."""
        provider = ClaudeCodeCLIProvider()
        stream_output = """line 1
line 2
{"content": "Final response", "usage": {"tokens": 50}}"""

        result = provider._parse_output(stream_output)

        assert result["content"] == "Final response"
        assert result["usage"]["tokens"] == 50

    @pytest.mark.asyncio
    async def test_run_cli_success(self):
        """Test successful CLI execution."""
        provider = ClaudeCodeCLIProvider()

        # Mock subprocess
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(
            b'{"content": "Success response"}',
            b''
        ))

        with patch('asyncio.create_subprocess_exec', return_value=mock_proc):
            result = await provider._run_cli(["claude"], "Test prompt")

        assert result["content"] == "Success response"
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_run_cli_timeout(self):
        """Test CLI execution timeout."""
        provider = ClaudeCodeCLIProvider(timeout=1)

        # Mock subprocess that times out
        mock_proc = AsyncMock()
        mock_proc.kill = Mock()
        mock_proc.wait = AsyncMock()
        mock_proc.communicate = AsyncMock(side_effect=asyncio.TimeoutError())

        with patch('asyncio.create_subprocess_exec', return_value=mock_proc):
            result = await provider._run_cli(["claude"], "Test prompt")

        assert "error" in result
        assert "Timeout" in result["error"]
        mock_proc.kill.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_cli_file_not_found(self):
        """Test CLI execution with missing executable."""
        provider = ClaudeCodeCLIProvider()

        with patch('asyncio.create_subprocess_exec', side_effect=FileNotFoundError()):
            result = await provider._run_cli(["nonexistent"], "Test prompt")

        assert "error" in result
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_run_cli_exit_error(self):
        """Test CLI execution with non-zero exit code."""
        provider = ClaudeCodeCLIProvider()

        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(return_value=(
            b'',
            b'Error: Authentication failed'
        ))

        with patch('asyncio.create_subprocess_exec', return_value=mock_proc):
            result = await provider._run_cli(["claude"], "Test prompt")

        assert "error" in result
        assert "Exit code 1" in result["error"]
        assert "Authentication failed" in result["error"]

    @pytest.mark.asyncio
    async def test_generate_str_success(self):
        """Test generate_str method success case."""
        provider = ClaudeCodeCLIProvider()

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(
            b'Test response content',
            b''
        ))

        with patch('asyncio.create_subprocess_exec', return_value=mock_proc):
            response = await provider.generate_str("Test prompt")

        assert response == "Test response content"

    @pytest.mark.asyncio
    async def test_generate_str_error(self):
        """Test generate_str method error handling."""
        provider = ClaudeCodeCLIProvider()

        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.communicate = AsyncMock(return_value=(
            b'',
            b'Error occurred'
        ))

        with patch('asyncio.create_subprocess_exec', return_value=mock_proc):
            with pytest.raises(Exception) as exc_info:
                await provider.generate_str("Test prompt")

            assert "Exit code 1" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_generate_with_messages(self):
        """Test generate method with message list."""
        provider = ClaudeCodeCLIProvider()

        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.communicate = AsyncMock(return_value=(
            b'{"content": "Generated response"}',
            b''
        ))

        messages = [
            {"role": "user", "content": "Hello"}
        ]

        with patch('asyncio.create_subprocess_exec', return_value=mock_proc):
            result = await provider.generate(messages)

        assert result["content"] == "Generated response"


class TestProviderConfiguration:
    """Test provider configuration via environment variables."""

    def test_env_var_cli_path(self):
        """Test CLI path from environment variable."""
        with patch.dict(os.environ, {"CLAUDE_CLI_PATH": "/custom/path/claude"}):
            provider = ClaudeCodeCLIProvider()
            assert provider.cli_path == "/custom/path/claude"

    def test_env_var_project(self):
        """Test project path from environment variable."""
        with patch.dict(os.environ, {"CLAUDE_CLI_PROJECT": "/custom/project"}):
            provider = ClaudeCodeCLIProvider()
            assert provider.project_path == "/custom/project"

    def test_env_var_model(self):
        """Test model from environment variable."""
        with patch.dict(os.environ, {"CLAUDE_CLI_MODEL": "custom-model"}):
            provider = ClaudeCodeCLIProvider()
            assert provider.model == "custom-model"

    def test_env_var_timeout(self):
        """Test timeout from environment variable."""
        with patch.dict(os.environ, {"CLAUDE_CLI_TIMEOUT": "300"}):
            provider = ClaudeCodeCLIProvider()
            assert provider.timeout == 300


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
