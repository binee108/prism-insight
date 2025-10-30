"""
Claude Code CLI Provider implementation.

This provider wraps the Claude Code CLI tool to make it callable
as if it were an HTTP API, allowing seamless integration with prism-insight.
"""

import asyncio
import json
import os
import shlex
import subprocess
from typing import List, Dict, Any, Optional
import logging

from .base import BaseLLMProvider


logger = logging.getLogger(__name__)


class ClaudeCodeCLIProvider(BaseLLMProvider):
    """
    LLM Provider that calls the Claude Code CLI as a subprocess.

    This allows using Claude Code's local execution capabilities
    within prism-insight's existing LLM abstraction framework.

    Environment Variables:
        CLAUDE_CLI_PATH: Path to claude executable (default: "claude")
        CLAUDE_CLI_PROJECT: Project path for -p option
        CLAUDE_CLI_MODEL: Model name (e.g., "claude-3-5-sonnet-20241022")
        CLAUDE_CLI_EXTRA_ARGS: Additional CLI arguments (default: "--output-format stream-json --print")
        CLAUDE_CLI_TIMEOUT: Timeout in seconds (default: 180)
    """

    def __init__(
        self,
        cli_path: Optional[str] = None,
        project_path: Optional[str] = None,
        model: Optional[str] = None,
        extra_args: Optional[str] = None,
        timeout: int = 180,
    ):
        """
        Initialize the Claude Code CLI provider.

        Args:
            cli_path: Path to claude executable (overrides CLAUDE_CLI_PATH)
            project_path: Project path for -p option (overrides CLAUDE_CLI_PROJECT)
            model: Model name (overrides CLAUDE_CLI_MODEL)
            extra_args: Additional CLI arguments (overrides CLAUDE_CLI_EXTRA_ARGS)
            timeout: Timeout in seconds (overrides CLAUDE_CLI_TIMEOUT)
        """
        self.cli_path = cli_path or os.getenv("CLAUDE_CLI_PATH", "claude")
        self.project_path = project_path or os.getenv("CLAUDE_CLI_PROJECT")
        self.model = model or os.getenv("CLAUDE_CLI_MODEL")
        self.extra_args = extra_args or os.getenv(
            "CLAUDE_CLI_EXTRA_ARGS",
            "--output-format stream-json --print"
        )
        self.timeout = int(os.getenv("CLAUDE_CLI_TIMEOUT", str(timeout)))

        logger.info(
            f"Initialized ClaudeCodeCLIProvider: "
            f"cli_path={self.cli_path}, "
            f"project_path={self.project_path}, "
            f"model={self.model}, "
            f"timeout={self.timeout}s"
        )

    def _build_command(
        self,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None
    ) -> List[str]:
        """
        Build the CLI command array.

        Args:
            model: Override default model
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            List of command arguments
        """
        cmd = [self.cli_path]

        # Add model if specified
        effective_model = model or self.model
        if effective_model:
            cmd += ["--model", effective_model]

        # Add max_tokens if specified
        if max_tokens is not None:
            cmd += ["--max-tokens", str(max_tokens)]

        # Add temperature if specified
        if temperature is not None:
            cmd += ["--temperature", str(temperature)]

        # Add project path if specified (this is the -p option)
        if self.project_path:
            cmd += ["-p", self.project_path]

        # Add extra arguments
        if self.extra_args:
            cmd += shlex.split(self.extra_args)

        return cmd

    def _render_messages(self, messages: List[Dict[str, Any]]) -> str:
        """
        Convert message list to a single prompt string.

        Args:
            messages: List of message dicts with 'role' and 'content'

        Returns:
            Single prompt string
        """
        parts = []
        for msg in messages:
            role = msg.get("role", "user").upper()
            content = msg.get("content", "")
            parts.append(f"{role}:\n{content}\n")
        return "\n".join(parts)

    def _parse_output(self, raw_output: str) -> Dict[str, Any]:
        """
        Parse CLI output (JSON or plain text).

        Args:
            raw_output: Raw stdout from CLI

        Returns:
            Dict with 'content' and 'usage' keys
        """
        content = None
        usage = {}

        try:
            # Try to parse as stream-json (last line should be JSON)
            lines = [line for line in raw_output.splitlines() if line.strip()]
            if not lines:
                return {"content": "", "usage": {}}

            last_line = lines[-1]
            data = json.loads(last_line)

            # Extract content (try different keys)
            content = (
                data.get("content") or
                data.get("text") or
                data.get("response")
            )

            # If no content found in expected keys, log warning and use raw output
            if not content:
                logger.warning(
                    f"JSON parsed successfully but no content found. "
                    f"Available keys: {list(data.keys())}. Using raw output."
                )
                content = raw_output.strip()

            # Extract usage if available
            usage = data.get("usage") or {}

            logger.debug(f"Parsed JSON output: {len(str(content))} chars, usage={usage}")

        except (json.JSONDecodeError, IndexError) as e:
            # Fallback to plain text
            content = raw_output.strip()
            logger.debug(f"Using plain text output: {len(content)} chars (JSON parse failed: {e})")

        return {
            "content": content,
            "usage": usage,
        }

    async def _run_cli(self, cmd: List[str], prompt: str) -> Dict[str, Any]:
        """
        Execute the CLI command asynchronously.

        Args:
            cmd: Command array
            prompt: Prompt to send via stdin

        Returns:
            Dict with 'content', 'usage', and optional 'error' keys
        """
        logger.info(f"Running CLI command: {' '.join(cmd)}")
        logger.debug(f"Prompt length: {len(prompt)} chars")

        try:
            # Run subprocess with asyncio
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Send prompt and wait for completion with timeout
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(input=prompt.encode("utf-8")),
                    timeout=self.timeout
                )
            except asyncio.TimeoutError:
                proc.kill()
                try:
                    # Wait for process to terminate, with a short timeout
                    await asyncio.wait_for(proc.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    logger.error("Process did not terminate after kill signal")
                logger.error(f"CLI execution timeout after {self.timeout}s")
                return {
                    "content": "",
                    "error": f"[claude-code-cli] Timeout after {self.timeout}s"
                }

            # Check return code
            if proc.returncode != 0:
                stderr_text = stderr.decode("utf-8", errors="ignore")
                logger.error(f"CLI execution failed (exit code {proc.returncode}): {stderr_text}")
                return {
                    "content": "",
                    "error": f"[claude-code-cli] Exit code {proc.returncode}: {stderr_text}"
                }

            # Parse output
            raw_output = stdout.decode("utf-8", errors="ignore")
            result = self._parse_output(raw_output)

            logger.info(f"CLI execution successful: {len(result.get('content', ''))} chars")
            return result

        except FileNotFoundError:
            logger.error(f"CLI executable not found: {self.cli_path}")
            return {
                "content": "",
                "error": f"[claude-code-cli] Executable not found: {self.cli_path}"
            }
        except Exception as e:
            logger.error(f"CLI execution error: {e}", exc_info=True)
            return {
                "content": "",
                "error": f"[claude-code-cli] Execution error: {str(e)}"
            }

    async def generate(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate a response from Claude Code CLI.

        Args:
            messages: List of message dicts
            model: Model name override
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0 - 1.0)
            **kwargs: Additional parameters (ignored)

        Returns:
            Dict with 'content', 'usage', and optional 'error' keys
        """
        # Build command with parameters
        cmd = self._build_command(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature
        )

        # Render messages to prompt
        prompt = self._render_messages(messages)

        # Execute CLI
        result = await self._run_cli(cmd, prompt)

        return result

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
            model: Model name override
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0 - 1.0)
            **kwargs: Additional parameters (ignored)

        Returns:
            str: The generated response text

        Raises:
            Exception: If generation fails
        """
        # Build command with parameters
        cmd = self._build_command(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature
        )

        # Execute CLI
        result = await self._run_cli(cmd, prompt)

        # Check for errors
        if "error" in result and result["error"]:
            raise Exception(result["error"])

        return result.get("content", "")
