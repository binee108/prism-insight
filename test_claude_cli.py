#!/usr/bin/env python3
"""
Test script for Claude Code CLI provider.
This script tests the CLI provider in isolation with detailed logging.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Setup project root
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Try to load .env file if dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv(project_root / ".env")
except ImportError:
    print("Warning: dotenv not available, using existing environment variables")

# Setup detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_basic_cli_call():
    """Test 1: Basic CLI call with minimal parameters"""
    logger.info("=" * 80)
    logger.info("TEST 1: Basic CLI call with minimal parameters")
    logger.info("=" * 80)

    from cores.providers.claude_code_cli import ClaudeCodeCLIProvider

    provider = ClaudeCodeCLIProvider()

    logger.info(f"Provider initialized:")
    logger.info(f"  - cli_path: {provider.cli_path}")
    logger.info(f"  - project_path: {provider.project_path}")
    logger.info(f"  - model: {provider.model}")
    logger.info(f"  - extra_args: {provider.extra_args}")
    logger.info(f"  - timeout: {provider.timeout}")
    logger.info(f"  - output_format: {provider.output_format}")

    simple_prompt = "Say 'Hello, World!' and nothing else."

    logger.info(f"\nSending prompt: {simple_prompt}")

    try:
        result = await provider.generate_str(
            prompt=simple_prompt,
            model=None,  # Use default
            max_tokens=None,
            temperature=None,
            max_turns=None
        )
        logger.info(f"\n✅ SUCCESS!")
        logger.info(f"Response: {result}")
        return True
    except Exception as e:
        logger.error(f"\n❌ FAILED!")
        logger.error(f"Error: {e}", exc_info=True)
        return False


async def test_with_model():
    """Test 2: CLI call with specific model"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 2: CLI call with specific model")
    logger.info("=" * 80)

    from cores.providers.claude_code_cli import ClaudeCodeCLIProvider

    provider = ClaudeCodeCLIProvider()

    simple_prompt = "What is 2+2? Answer with just the number."

    logger.info(f"Sending prompt with model='sonnet': {simple_prompt}")

    try:
        result = await provider.generate_str(
            prompt=simple_prompt,
            model="sonnet",
            max_tokens=None,
            temperature=None,
            max_turns=None
        )
        logger.info(f"\n✅ SUCCESS!")
        logger.info(f"Response: {result}")
        return True
    except Exception as e:
        logger.error(f"\n❌ FAILED!")
        logger.error(f"Error: {e}", exc_info=True)
        return False


async def test_with_max_turns():
    """Test 3: CLI call with max_turns"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 3: CLI call with max_turns")
    logger.info("=" * 80)

    from cores.providers.claude_code_cli import ClaudeCodeCLIProvider

    provider = ClaudeCodeCLIProvider()

    simple_prompt = "Count from 1 to 3."

    logger.info(f"Sending prompt with max_turns=2: {simple_prompt}")

    try:
        result = await provider.generate_str(
            prompt=simple_prompt,
            model=None,
            max_tokens=None,
            temperature=None,
            max_turns=2
        )
        logger.info(f"\n✅ SUCCESS!")
        logger.info(f"Response: {result}")
        return True
    except Exception as e:
        logger.error(f"\n❌ FAILED!")
        logger.error(f"Error: {e}", exc_info=True)
        return False


async def test_augmented_wrapper():
    """Test 4: Test the augmented LLM wrapper"""
    logger.info("\n" + "=" * 80)
    logger.info("TEST 4: Test augmented LLM wrapper")
    logger.info("=" * 80)

    from cores.providers.claude_code_cli_augmented import ClaudeCodeCLIAugmentedLLM
    from mcp_agent.workflows.llm.augmented_llm import RequestParams

    # Create a mock agent
    class MockAgent:
        def __init__(self):
            self.name = "test_agent"
            self.instruction = "You are a helpful assistant."

    mock_agent = MockAgent()

    llm = ClaudeCodeCLIAugmentedLLM(agent=mock_agent)

    logger.info(f"Wrapper initialized for agent: {mock_agent.name}")

    simple_prompt = "What is the capital of France? Answer with just the city name."

    logger.info(f"Sending prompt: {simple_prompt}")

    try:
        result = await llm.generate_str(
            message=simple_prompt,
            request_params=RequestParams(
                model="sonnet",
                maxTokens=100,  # Should be ignored
                temperature=0.7,  # Should be ignored
                max_iterations=2,
                parallel_tool_calls=False,
                use_history=False
            )
        )
        logger.info(f"\n✅ SUCCESS!")
        logger.info(f"Response: {result}")
        return True
    except Exception as e:
        logger.error(f"\n❌ FAILED!")
        logger.error(f"Error: {e}", exc_info=True)
        return False


async def main():
    """Run all tests"""
    logger.info("Starting Claude Code CLI Provider Tests")
    logger.info(f"PRISM_LLM_PROVIDER: {os.getenv('PRISM_LLM_PROVIDER', 'NOT SET')}")
    logger.info(f"CLAUDE_CLI_PATH: {os.getenv('CLAUDE_CLI_PATH', 'claude')}")
    logger.info(f"CLAUDE_CLI_MODEL: {os.getenv('CLAUDE_CLI_MODEL', 'NOT SET')}")
    logger.info(f"CLAUDE_CLI_PROJECT: {os.getenv('CLAUDE_CLI_PROJECT', 'NOT SET')}")
    logger.info(f"CLAUDE_CLI_OUTPUT_FORMAT: {os.getenv('CLAUDE_CLI_OUTPUT_FORMAT', 'json')}")

    results = []

    # Test 1: Basic call
    results.append(("Basic CLI call", await test_basic_cli_call()))

    # Test 2: With model
    results.append(("CLI with model", await test_with_model()))

    # Test 3: With max_turns
    results.append(("CLI with max_turns", await test_with_max_turns()))

    # Test 4: Augmented wrapper
    results.append(("Augmented wrapper", await test_augmented_wrapper()))

    # Print summary
    logger.info("\n" + "=" * 80)
    logger.info("TEST SUMMARY")
    logger.info("=" * 80)

    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        logger.info(f"{status}: {test_name}")

    total = len(results)
    passed = sum(1 for _, p in results if p)
    logger.info(f"\nTotal: {passed}/{total} tests passed")

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
