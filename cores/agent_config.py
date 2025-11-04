"""
Agent Configuration Loader.

This module loads agent-specific LLM provider and model settings from
agent.config.yaml, allowing different agents to use different providers
and models without code changes.
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import yaml

logger = logging.getLogger(__name__)

# Cache for loaded config
_config_cache: Optional[Dict[str, Any]] = None


def load_agent_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load agent configuration from YAML file.

    Args:
        config_path: Path to agent.config.yaml (defaults to project root)

    Returns:
        Dict with config structure:
        {
            "default": {"provider": "...", "model": "..."},
            "agents": {
                "agent_name": {"provider": "...", "model": "..."},
                ...
            }
        }

    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If YAML is invalid
    """
    global _config_cache

    # Return cached config if available
    if _config_cache is not None:
        return _config_cache

    # Determine config path
    if config_path is None:
        # Default: project root / agent.config.yaml
        project_root = Path(__file__).parent.parent
        config_path = project_root / "agent.config.yaml"
    else:
        config_path = Path(config_path)

    # Check if file exists
    if not config_path.exists():
        logger.warning(
            f"Agent config file not found: {config_path}. "
            "Using default settings from environment variables."
        )
        # Return empty config (will use defaults)
        _config_cache = {"default": {}, "agents": {}}
        return _config_cache

    # Load YAML
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        if not isinstance(config, dict):
            logger.error(f"Invalid config format in {config_path}, expected dict")
            config = {}

        # Ensure required keys exist
        if "default" not in config:
            config["default"] = {}
        if "agents" not in config:
            config["agents"] = {}

        logger.info(f"Loaded agent config from {config_path}")
        logger.debug(f"Config: {config}")

        _config_cache = config
        return config

    except yaml.YAMLError as e:
        logger.error(f"Failed to parse YAML config: {e}")
        # Return empty config on error
        _config_cache = {"default": {}, "agents": {}}
        return _config_cache


def get_agent_config(
    agent_name: str,
    config_path: Optional[str] = None
) -> Dict[str, Optional[str]]:
    """
    Get provider and model configuration for a specific agent.

    Args:
        agent_name: Name of the agent (e.g., "price_volume_analysis_agent")
        config_path: Path to config file (optional)

    Returns:
        Dict with keys:
            - provider: Provider name or None (use env var default)
            - model: Model name or None (use env var default)

    Examples:
        >>> get_agent_config("price_volume_analysis_agent")
        {"provider": "claude-code-cli", "model": "sonnet"}

        >>> get_agent_config("unknown_agent")
        {"provider": None, "model": None}  # Uses env vars
    """
    config = load_agent_config(config_path)

    # Try agent-specific config first
    agent_cfg = config.get("agents", {}).get(agent_name, {})

    # Fall back to default config
    default_cfg = config.get("default", {})

    # Build result (agent config overrides default)
    result = {
        "provider": agent_cfg.get("provider") or default_cfg.get("provider"),
        "model": agent_cfg.get("model") or default_cfg.get("model"),
    }

    logger.debug(
        f"Agent '{agent_name}' config: "
        f"provider={result['provider']}, model={result['model']}"
    )

    return result


def clear_config_cache():
    """
    Clear the cached configuration.

    Useful for testing or reloading config without restarting the application.
    """
    global _config_cache
    _config_cache = None
    logger.debug("Agent config cache cleared")


def log_agent_config(agent_name: str):
    """
    Log the effective configuration for an agent.

    Useful for debugging which provider/model an agent will use.

    Args:
        agent_name: Name of the agent
    """
    config = get_agent_config(agent_name)

    logger.info("=" * 60)
    logger.info(f"Agent Configuration: {agent_name}")
    logger.info("=" * 60)

    if config["provider"]:
        logger.info(f"Provider: {config['provider']} (from agent.config.yaml)")
    else:
        env_provider = os.getenv("PRISM_LLM_PROVIDER", "openai")
        logger.info(f"Provider: {env_provider} (from PRISM_LLM_PROVIDER env var)")

    if config["model"]:
        logger.info(f"Model: {config['model']} (from agent.config.yaml)")
    else:
        logger.info("Model: (using provider default or RequestParams)")

    logger.info("=" * 60)
