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
        CLAUDE_CLI_OUTPUT_FORMAT: Output format - "json" or "stream-json" (default: "json")
        CLAUDE_CLI_EXTRA_ARGS: Additional CLI arguments (default: "--print")
        CLAUDE_CLI_TIMEOUT: Timeout in seconds (default: 180)
    """

    def __init__(
        self,
        cli_path: Optional[str] = None,
        project_path: Optional[str] = None,
        model: Optional[str] = None,
        extra_args: Optional[str] = None,
        timeout: int = 180,
        output_format: str = "json",
    ):
        """
        Initialize the Claude Code CLI provider.

        Args:
            cli_path: Path to claude executable (overrides CLAUDE_CLI_PATH)
            project_path: Project path for -p option (overrides CLAUDE_CLI_PROJECT)
            model: Model name (overrides CLAUDE_CLI_MODEL)
            extra_args: Additional CLI arguments (overrides CLAUDE_CLI_EXTRA_ARGS)
            timeout: Timeout in seconds (overrides CLAUDE_CLI_TIMEOUT)
            output_format: CLI output format - "json" or "stream-json" (default: "json")
        """
        self.cli_path = cli_path or os.getenv("CLAUDE_CLI_PATH", "claude")
        self.project_path = project_path or os.getenv("CLAUDE_CLI_PROJECT")
        self.model = model or os.getenv("CLAUDE_CLI_MODEL")
        self.extra_args = extra_args or os.getenv(
            "CLAUDE_CLI_EXTRA_ARGS",
            "--print"
        )
        self.timeout = int(os.getenv("CLAUDE_CLI_TIMEOUT", str(timeout)))
        self.output_format = os.getenv("CLAUDE_CLI_OUTPUT_FORMAT", output_format)

        logger.info(
            f"Initialized ClaudeCodeCLIProvider: "
            f"cli_path={self.cli_path}, "
            f"project_path={self.project_path}, "
            f"model={self.model}, "
            f"output_format={self.output_format}, "
            f"timeout={self.timeout}s"
        )

    def _build_command(
        self,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        max_turns: Optional[int] = None,
        resume_session: Optional[str] = None,
        enable_session_tracking: bool = False
    ) -> List[str]:
        """
        Build the CLI command array.

        Args:
            model: Override default model
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            max_turns: Maximum agent turns (maps to --max-turns)
            resume_session: Session ID to resume (maps to --resume)
            enable_session_tracking: Use json output format for session tracking

        Returns:
            List of command arguments
        """
        cmd = [self.cli_path]

        # Resume session if provided
        if resume_session:
            cmd += ["--resume", resume_session]

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

        # Add max_turns if specified (for max_iterations support)
        if max_turns is not None and max_turns > 0:
            cmd += ["--max-turns", str(max_turns)]

        # Add project path if specified (this is the -p option)
        if self.project_path:
            cmd += ["-p", self.project_path]

        # Handle extra arguments and output format
        if self.extra_args:
            # Filter out --output-format from extra_args to avoid conflicts
            args = shlex.split(self.extra_args)
            filtered_args = []
            skip_next = False
            for i, arg in enumerate(args):
                if skip_next:
                    skip_next = False
                    continue
                if arg == "--output-format":
                    skip_next = True  # Skip the next argument too
                    continue
                if arg.startswith("--output-format="):
                    continue
                filtered_args.append(arg)
            cmd += filtered_args

        # Add output format
        cmd += ["--output-format", self.output_format]

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

    def _parse_output(self, raw_output: str, output_format: str = "json") -> Dict[str, Any]:
        """
        Parse CLI output (JSON or plain text).

        Args:
            raw_output: Raw stdout from CLI
            output_format: Format of the output ("json" or "stream-json")

        Returns:
            Dict with 'content', 'usage', and optionally 'session_id', 'cost', 'num_turns'
        """
        content = None
        usage = {}
        session_id = None
        total_cost_usd = None
        num_turns = None

        try:
            if output_format == "json":
                # Parse full JSON output from --output-format json
                data = json.loads(raw_output)

                # Check for errors
                if data.get("is_error"):
                    return {
                        "content": "",
                        "error": data.get("result", "Unknown error"),
                        "session_id": data.get("session_id")
                    }

                # Extract content from "result" key
                content = data.get("result", "")

                # Extract session metadata
                session_id = data.get("session_id")
                total_cost_usd = data.get("total_cost_usd")
                num_turns = data.get("num_turns")

                # Extract usage information
                usage_data = data.get("usage", {})
                usage = {
                    "input_tokens": usage_data.get("input_tokens", 0),
                    "output_tokens": usage_data.get("output_tokens", 0),
                    "cache_read_tokens": usage_data.get("cache_read_input_tokens", 0),
                    "cache_creation_tokens": usage_data.get("cache_creation_input_tokens", 0),
                }

                logger.debug(
                    f"Parsed JSON output: {len(content)} chars, "
                    f"session_id={session_id}, cost=${total_cost_usd}, turns={num_turns}"
                )

            else:
                # Parse stream-json (last line should be JSON)
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

                logger.debug(f"Parsed stream-json output: {len(str(content))} chars, usage={usage}")

        except (json.JSONDecodeError, IndexError) as e:
            # Fallback to plain text
            content = raw_output.strip()
            logger.debug(f"Using plain text output: {len(content)} chars (JSON parse failed: {e})")

        result = {
            "content": content,
            "usage": usage,
        }

        # Add session metadata if available
        if session_id:
            result["session_id"] = session_id
        if total_cost_usd is not None:
            result["total_cost_usd"] = total_cost_usd
        if num_turns is not None:
            result["num_turns"] = num_turns

        return result

    async def _run_cli(self, cmd: List[str], prompt: str, output_format: str = "json") -> Dict[str, Any]:
        """
        Execute the CLI command asynchronously.

        Args:
            cmd: Command array
            prompt: Prompt to send via stdin
            output_format: Format of CLI output ("json" or "stream-json")

        Returns:
            Dict with 'content', 'usage', and optional 'error' keys
        """
        logger.info(f"Running CLI command: {' '.join(cmd)}")
        logger.debug(f"Prompt length: {len(prompt)} chars, output_format: {output_format}")

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
            result = self._parse_output(raw_output, output_format=output_format)

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
        max_turns: Optional[int] = None,
        resume_session: Optional[str] = None,
        enable_session_tracking: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate a response from Claude Code CLI.

        Args:
            messages: List of message dicts
            model: Model name override
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0 - 1.0)
            max_turns: Maximum agent turns for tool calling
            resume_session: Session ID to resume conversation
            enable_session_tracking: Enable session tracking (returns session_id)
            **kwargs: Additional parameters (ignored)

        Returns:
            Dict with 'content', 'usage', and optional 'error', 'session_id', 'cost' keys
        """
        # Build command with parameters
        cmd = self._build_command(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            max_turns=max_turns,
            resume_session=resume_session,
            enable_session_tracking=enable_session_tracking
        )

        # Render messages to prompt
        prompt = self._render_messages(messages)

        # Always use json format
        output_format = "json"

        # Execute CLI
        result = await self._run_cli(cmd, prompt, output_format=output_format)

        return result

    async def generate_str(
        self,
        prompt: str,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        max_turns: Optional[int] = None,
        resume_session: Optional[str] = None,
        enable_session_tracking: bool = False,
        **kwargs
    ) -> str:
        """
        Simplified interface that takes a single prompt string.

        This method always returns a string (content only). For metadata
        like session_id and usage, use generate_with_metadata() instead.

        Args:
            prompt: Single prompt string
            model: Model name override
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0 - 1.0)
            max_turns: Maximum agent turns for tool calling
            resume_session: Session ID to resume conversation
            enable_session_tracking: Enable session tracking (deprecated, use generate_with_metadata)
            **kwargs: Additional parameters (ignored)

        Returns:
            str: The generated response text

        Raises:
            Exception: If generation fails
        """
        # Use generate_with_metadata and extract content
        result = await self.generate_with_metadata(
            prompt=prompt,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            max_turns=max_turns,
            resume_session=resume_session,
            enable_session_tracking=enable_session_tracking,
            **kwargs
        )

        return result.get("content", "")

    async def generate_with_metadata(
        self,
        prompt: str,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        max_turns: Optional[int] = None,
        resume_session: Optional[str] = None,
        enable_session_tracking: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate response with full metadata (session_id, usage, cost, etc.).

        Args:
            prompt: Single prompt string
            model: Model name override
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0 - 1.0)
            max_turns: Maximum agent turns for tool calling
            resume_session: Session ID to resume conversation
            enable_session_tracking: Enable session tracking (returns session_id)
            **kwargs: Additional parameters (ignored)

        Returns:
            Dict with keys:
                - content: str - The generated response text
                - usage: dict - Token usage information
                - session_id: str (optional) - Session identifier
                - total_cost_usd: float (optional) - Cost in USD
                - num_turns: int (optional) - Number of turns
                - error: str (optional) - Error message if failed

        Raises:
            Exception: If generation fails
        """
        # Build command with parameters
        cmd = self._build_command(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            max_turns=max_turns,
            resume_session=resume_session,
            enable_session_tracking=enable_session_tracking
        )

        # Execute CLI
        result = await self._run_cli(cmd, prompt, output_format=self.output_format)

        # Check for errors
        if "error" in result and result["error"]:
            raise Exception(result["error"])

        return result
