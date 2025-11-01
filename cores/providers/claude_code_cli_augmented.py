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

        # Store agent's instruction for context (safe access)
        self.instruction = getattr(agent, "instruction", None) if agent else None

        # Session management (Phase 4: use_history support)
        self.current_session_id: Optional[str] = None
        self.use_history: bool = False

        logger.info(
            f"Initialized ClaudeCodeCLIAugmentedLLM for agent: "
            f"{agent.name if agent else 'None'}"
        )

    def _build_prompt_with_directives(
        self,
        base_prompt: str,
        parallel_tool_calls: bool = False
    ) -> str:
        """
        Add system directives to prompt based on request params.

        Args:
            base_prompt: Original prompt
            parallel_tool_calls: Whether to enable parallel tool calls

        Returns:
            Modified prompt with directives
        """
        directives = []

        # Phase 3: Add parallel processing directive
        if parallel_tool_calls:
            directives.append(
                "SYSTEM DIRECTIVE: When using the Task tool, process independent "
                "tasks in parallel when possible for better efficiency."
            )

        if directives:
            directive_text = "\n".join(directives)
            return f"{directive_text}\n\n{base_prompt}"

        return base_prompt

    def clear_history(self):
        """
        Clear conversation history and session.

        Call this method to start a fresh conversation without history.
        """
        self.current_session_id = None
        self.use_history = False
        logger.info("Conversation history cleared")

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
            request_params: Request parameters (model, tokens, max_iterations, etc.)

        Returns:
            str: The generated response text

        Raises:
            Exception: If generation fails
        """
        # Extract all parameters from request_params
        model = None
        max_tokens = None
        temperature = None
        max_turns = None
        parallel_tool_calls = False
        use_history = False

        if request_params:
            model = getattr(request_params, "model", None)
            max_tokens = getattr(request_params, "maxTokens", None)
            temperature = getattr(request_params, "temperature", None)

            # Phase 1: Map max_iterations to max_turns
            max_iterations = getattr(request_params, "max_iterations", None)
            if max_iterations is not None:
                max_turns = max_iterations
                logger.debug(f"Mapped max_iterations={max_iterations} to max_turns={max_turns}")

            # Phase 3: Extract parallel_tool_calls
            parallel_tool_calls = getattr(request_params, "parallel_tool_calls", False)

            # Phase 4: Extract use_history
            use_history = getattr(request_params, "use_history", False)

        # Phase 4: Activate history if requested
        if use_history:
            self.use_history = True

        # Build the full prompt including agent instruction
        full_prompt = message
        if self.instruction:
            full_prompt = f"""SYSTEM INSTRUCTION:
{self.instruction}

USER MESSAGE:
{message}
"""

        # Phase 3: Add parallel processing directive if requested
        full_prompt = self._build_prompt_with_directives(
            base_prompt=full_prompt,
            parallel_tool_calls=parallel_tool_calls
        )

        # Phase 4: Determine if we should resume a session
        resume_session = None
        if self.use_history and self.current_session_id:
            resume_session = self.current_session_id
            logger.debug(f"Resuming session: {resume_session}")

        logger.debug(
            f"Generating response: model={model}, max_tokens={max_tokens}, "
            f"max_turns={max_turns}, parallel={parallel_tool_calls}, "
            f"use_history={use_history}"
        )

        # Phase 4: If using history, get full metadata to extract session_id
        if self.use_history:
            # Get full metadata including session_id
            result = await self.provider.generate_with_metadata(
                prompt=full_prompt,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                max_turns=max_turns,
                resume_session=resume_session,
                enable_session_tracking=True
            )

            # Update session if available
            if "session_id" in result:
                self.current_session_id = result["session_id"]
                logger.debug(f"Session ID updated: {self.current_session_id}")

            # Extract content
            content = result.get("content", "")
            logger.info(f"Generated response: {len(content)} chars")
            return content
        else:
            # No history needed, just get the text
            content = await self.provider.generate_str(
                prompt=full_prompt,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                max_turns=max_turns,
                resume_session=resume_session,
                enable_session_tracking=False
            )
            logger.info(f"Generated response: {len(content)} chars")
            return content

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
            Dict with 'content', 'usage', and optional 'error', 'session_id' keys

        Raises:
            Exception: If generation fails
        """
        # Extract all parameters from request_params
        model = None
        max_tokens = None
        temperature = None
        max_turns = None
        parallel_tool_calls = False
        use_history = False

        if request_params:
            model = getattr(request_params, "model", None)
            max_tokens = getattr(request_params, "maxTokens", None)
            temperature = getattr(request_params, "temperature", None)

            # Phase 1: Map max_iterations to max_turns
            max_iterations = getattr(request_params, "max_iterations", None)
            if max_iterations is not None:
                max_turns = max_iterations
                logger.debug(f"Mapped max_iterations={max_iterations} to max_turns={max_turns}")

            # Phase 3: Extract parallel_tool_calls
            parallel_tool_calls = getattr(request_params, "parallel_tool_calls", False)

            # Phase 4: Extract use_history
            use_history = getattr(request_params, "use_history", False)

        # Phase 4: Activate history if requested
        if use_history:
            self.use_history = True

        # Add system instruction as first message if available
        if self.instruction:
            messages = [
                {"role": "system", "content": self.instruction},
                *messages
            ]

        # Phase 3: Add parallel processing directive to first user message
        if parallel_tool_calls and messages:
            # Find first user message and add directive
            for msg in messages:
                if msg.get("role") == "user":
                    original_content = msg.get("content", "")
                    msg["content"] = self._build_prompt_with_directives(
                        base_prompt=original_content,
                        parallel_tool_calls=True
                    )
                    break

        # Phase 4: Determine if we should resume a session
        resume_session = None
        if self.use_history and self.current_session_id:
            resume_session = self.current_session_id
            logger.debug(f"Resuming session: {resume_session}")

        logger.debug(
            f"Generating response: model={model}, max_tokens={max_tokens}, "
            f"max_turns={max_turns}, parallel={parallel_tool_calls}, "
            f"use_history={use_history}"
        )

        # Call the underlying provider
        # generate() always returns Dict, so no need for special handling
        result = await self.provider.generate(
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            max_turns=max_turns,
            resume_session=resume_session,
            enable_session_tracking=self.use_history
        )

        # Phase 4: Update session if available
        if "session_id" in result:
            self.current_session_id = result["session_id"]
            logger.debug(f"Session ID updated: {self.current_session_id}")

        # Raise exception if error occurred (consistent with generate_str)
        if "error" in result and result["error"]:
            raise Exception(result["error"])

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
