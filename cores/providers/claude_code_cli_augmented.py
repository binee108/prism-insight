"""
MCP-Agent compatible wrapper for Claude Code CLI Provider.

This module provides a wrapper that integrates ClaudeCodeCLIProvider
with the mcp-agent framework, making it usable as a drop-in replacement
for OpenAIAugmentedLLM or AnthropicAugmentedLLM.
"""

import logging
from typing import Optional, Any

from .claude_code_cli import ClaudeCodeCLIProvider

try:
    from mcp_agent.workflows.llm.augmented_llm import RequestParams
except ImportError:
    # Fallback if mcp-agent is not installed
    class RequestParams:
        """Fallback RequestParams for development/testing."""
        def __init__(
            self,
            model: Optional[str] = None,
            maxTokens: Optional[int] = None,
            temperature: Optional[float] = None,
            max_iterations: Optional[int] = None,
            parallel_tool_calls: Optional[bool] = None,
            use_history: Optional[bool] = None,
            **kwargs
        ):
            self.model = model
            self.maxTokens = maxTokens
            self.temperature = temperature
            self.max_iterations = max_iterations
            self.parallel_tool_calls = parallel_tool_calls
            self.use_history = use_history
            self.extra = kwargs


logger = logging.getLogger(__name__)


class ClaudeCodeCLIAugmentedLLM:
    """
    MCP-Agent compatible wrapper for Claude Code CLI.

    This class mimics the interface of OpenAIAugmentedLLM and AnthropicAugmentedLLM,
    allowing it to be used with the mcp-agent framework's attach_llm() method.

    Usage:
        agent = Agent(name="my_agent", instruction="...")
        llm = await agent.attach_llm(ClaudeCodeCLIAugmentedLLM)
        response = await llm.generate_str(
            message="Your prompt",
            request_params=RequestParams(model="claude-3-5-sonnet-20241022")
        )
    """

    def __init__(
        self,
        agent: Optional[Any] = None,
        cli_path: Optional[str] = None,
        project_path: Optional[str] = None,
        model: Optional[str] = None,
        extra_args: Optional[str] = None,
        timeout: int = 180,
    ):
        """
        Initialize the augmented LLM wrapper.

        Args:
            agent: MCP Agent instance (provided by attach_llm)
            cli_path: Path to claude executable
            project_path: Project path for -p option
            model: Default model name
            extra_args: Additional CLI arguments
            timeout: Timeout in seconds
        """
        self.agent = agent
        self.provider = ClaudeCodeCLIProvider(
            cli_path=cli_path,
            project_path=project_path,
            model=model,
            extra_args=extra_args,
            timeout=timeout,
        )

        # Store agent's instruction for context
        self.instruction = agent.instruction if agent else None

        logger.info(
            f"Initialized ClaudeCodeCLIAugmentedLLM for agent: "
            f"{agent.name if agent else 'None'}"
        )

    async def generate_str(
        self,
        message: str,
        request_params: Optional[RequestParams] = None,
    ) -> str:
        """
        Generate a response from Claude Code CLI.

        This method matches the interface of mcp-agent's AugmentedLLM classes.

        Args:
            message: The user prompt/message
            request_params: Request parameters (model, tokens, etc.)

        Returns:
            str: The generated response text

        Raises:
            Exception: If generation fails
        """
        # Extract model from request_params if provided
        model = None
        max_tokens = None
        temperature = None

        if request_params:
            model = getattr(request_params, "model", None)
            max_tokens = getattr(request_params, "maxTokens", None)
            temperature = getattr(request_params, "temperature", None)

        # Build the full prompt including agent instruction
        full_prompt = message
        if self.instruction:
            full_prompt = f"""SYSTEM INSTRUCTION:
{self.instruction}

USER MESSAGE:
{message}
"""

        logger.debug(f"Generating response with model={model}, max_tokens={max_tokens}")

        # Call the underlying provider
        response = await self.provider.generate_str(
            prompt=full_prompt,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        logger.info(f"Generated response: {len(response)} chars")
        return response

    async def generate(
        self,
        messages: list,
        request_params: Optional[RequestParams] = None,
    ) -> dict:
        """
        Generate a response from Claude Code CLI (message-based interface).

        Args:
            messages: List of message dicts with 'role' and 'content'
            request_params: Request parameters

        Returns:
            Dict with 'content', 'usage', and optional 'error' keys
        """
        # Extract parameters
        model = None
        max_tokens = None
        temperature = None

        if request_params:
            model = getattr(request_params, "model", None)
            max_tokens = getattr(request_params, "maxTokens", None)
            temperature = getattr(request_params, "temperature", None)

        # Add system instruction as first message if available
        if self.instruction:
            messages = [
                {"role": "system", "content": self.instruction},
                *messages
            ]

        # Call the underlying provider
        result = await self.provider.generate(
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        return result

    @classmethod
    async def create(cls, agent: Any, **kwargs):
        """
        Factory method for mcp-agent compatibility.

        This method may be called by the attach_llm framework.

        Args:
            agent: MCP Agent instance
            **kwargs: Additional configuration

        Returns:
            ClaudeCodeCLIAugmentedLLM instance
        """
        return cls(agent=agent, **kwargs)


# Alias for easier imports
ClaudeCodeCLI = ClaudeCodeCLIAugmentedLLM
