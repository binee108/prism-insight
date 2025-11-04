"""
LLM Provider Factory for prism-insight.

This module provides helper functions to select and instantiate LLM providers
based on agent.config.yaml and environment variables, making it easy to switch
between different providers without code changes.
"""

import os
import logging
from typing import Type, Optional, Any

from cores.agent_config import get_agent_config

logger = logging.getLogger(__name__)


def get_llm_provider_class(
    provider_name: Optional[str] = None,
    agent_name: Optional[str] = None
) -> Type[Any]:
    """
    Get the LLM provider class based on agent config, name, or environment variable.

    This function returns the appropriate AugmentedLLM class for use
    with mcp-agent's attach_llm() method.

    Priority order:
        1. provider_name argument (explicit override)
        2. agent.config.yaml (agent-specific or default)
        3. PRISM_LLM_PROVIDER environment variable
        4. Default: 'openai'

    Args:
        provider_name: Override provider name (highest priority)
        agent_name: Agent name to lookup in agent.config.yaml

    Returns:
        LLM provider class (e.g., OpenAIAugmentedLLM, ClaudeCodeCLIAugmentedLLM)

    Raises:
        ValueError: If provider name is invalid
        ImportError: If provider module is not available

    Example:
        # Using agent config
        provider_class = get_llm_provider_class(agent_name="price_volume_analysis_agent")

        # Override with specific provider
        provider_class = get_llm_provider_class("claude-code-cli")

        # Default (env var)
        provider_class = get_llm_provider_class()
    """
    # Priority 1: Explicit provider_name argument
    if provider_name:
        provider = provider_name
        logger.info(f"Using explicit provider: {provider}")
    # Priority 2: Agent config
    elif agent_name:
        agent_cfg = get_agent_config(agent_name)
        provider = agent_cfg.get("provider")
        if provider:
            logger.info(f"Using provider from agent.config.yaml for '{agent_name}': {provider}")
        else:
            # Fall back to env var
            provider = os.getenv("PRISM_LLM_PROVIDER", "openai")
            logger.info(f"Agent '{agent_name}' has no provider config, using env var: {provider}")
    # Priority 3: Environment variable
    else:
        provider = os.getenv("PRISM_LLM_PROVIDER", "openai")
        logger.info(f"Using provider from PRISM_LLM_PROVIDER env var: {provider}")

    provider = provider.lower().strip()

    if provider == "openai":
        try:
            from mcp_agent.workflows.llm.augmented_llm_openai import OpenAIAugmentedLLM
            logger.debug("Loaded OpenAIAugmentedLLM")
            return OpenAIAugmentedLLM
        except ImportError as e:
            logger.error(f"Failed to import OpenAIAugmentedLLM: {e}")
            raise ImportError(
                "OpenAI provider not available. "
                "Install with: pip install openai mcp-agent"
            ) from e

    elif provider == "anthropic":
        try:
            from mcp_agent.workflows.llm.augmented_llm_anthropic import AnthropicAugmentedLLM
            logger.debug("Loaded AnthropicAugmentedLLM")
            return AnthropicAugmentedLLM
        except ImportError as e:
            logger.error(f"Failed to import AnthropicAugmentedLLM: {e}")
            raise ImportError(
                "Anthropic provider not available. "
                "Install with: pip install anthropic mcp-agent"
            ) from e

    elif provider in ("claude-code-cli", "claude-cli", "cli"):
        try:
            from cores.providers.claude_code_cli_augmented import ClaudeCodeCLIAugmentedLLM
            logger.debug("Loaded ClaudeCodeCLIAugmentedLLM")
            return ClaudeCodeCLIAugmentedLLM
        except ImportError as e:
            logger.error(f"Failed to import ClaudeCodeCLIAugmentedLLM: {e}")
            raise ImportError(
                "Claude Code CLI provider not available. "
                "Check that cores/providers/claude_code_cli_augmented.py exists"
            ) from e

    else:
        raise ValueError(
            f"Unknown provider: {provider}. "
            f"Valid options: 'openai', 'anthropic', 'claude-code-cli'"
        )


def get_default_llm_provider() -> Type:
    """
    Get the default LLM provider class from environment.

    This is a convenience function that calls get_llm_provider_class()
    with no arguments.

    Returns:
        LLM provider class

    Example:
        provider_class = get_default_llm_provider()
        llm = await agent.attach_llm(provider_class)
    """
    return get_llm_provider_class()


async def create_llm_from_agent(agent, provider_name: Optional[str] = None):
    """
    Convenience function to attach LLM to agent using configured provider.

    Args:
        agent: MCP Agent instance
        provider_name: Override provider name

    Returns:
        LLM instance attached to agent

    Example:
        agent = Agent(name="my_agent", instruction="...")
        llm = await create_llm_from_agent(agent)
        response = await llm.generate_str(message="Hello")
    """
    provider_class = get_llm_provider_class(provider_name)
    llm = await agent.attach_llm(provider_class)
    return llm


# Configuration helpers

def is_cli_provider() -> bool:
    """
    Check if the current default provider is CLI-based.

    Returns:
        True if default provider is Claude Code CLI
    """
    provider = os.getenv("PRISM_LLM_PROVIDER", "openai").lower()
    return provider in ("claude-code-cli", "claude-cli", "cli")


def get_provider_info() -> dict:
    """
    Get information about the current provider configuration.

    Returns:
        Dict with provider configuration details

    Example:
        info = get_provider_info()
        print(f"Using provider: {info['provider']}")
        print(f"Is CLI-based: {info['is_cli']}")
    """
    provider = os.getenv("PRISM_LLM_PROVIDER", "openai")

    info = {
        "provider": provider,
        "is_cli": is_cli_provider(),
    }

    # Add CLI-specific info if applicable
    if is_cli_provider():
        info.update({
            "cli_path": os.getenv("CLAUDE_CLI_PATH", "claude"),
            "cli_project": os.getenv("CLAUDE_CLI_PROJECT"),
            "cli_model": os.getenv("CLAUDE_CLI_MODEL"),
            "cli_timeout": os.getenv("CLAUDE_CLI_TIMEOUT", "180"),
        })

    return info


# Logging helper

def log_provider_config():
    """
    Log the current provider configuration.

    Useful for debugging and startup diagnostics.
    """
    info = get_provider_info()
    logger.info("=" * 60)
    logger.info("LLM Provider Configuration")
    logger.info("=" * 60)
    logger.info(f"Provider: {info['provider']}")
    logger.info(f"Is CLI-based: {info['is_cli']}")

    if info['is_cli']:
        logger.info(f"CLI Path: {info['cli_path']}")
        logger.info(f"CLI Project: {info['cli_project']}")
        logger.info(f"CLI Model: {info['cli_model']}")
        logger.info(f"CLI Timeout: {info['cli_timeout']}s")

    logger.info("=" * 60)
