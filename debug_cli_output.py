#!/usr/bin/env python3
"""
Debug script to test Claude CLI provider with detailed logging.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Force DEBUG level for claude_code_cli logger
claude_cli_logger = logging.getLogger('cores.providers.claude_code_cli')
claude_cli_logger.setLevel(logging.DEBUG)

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Load environment (optional)
try:
    from dotenv import load_dotenv
    load_dotenv(project_root / ".env")
except ImportError:
    print("dotenv not available, skipping .env loading")
    pass

from cores.providers.claude_code_cli_augmented import ClaudeCodeCLIAugmentedLLM
from mcp_agent.workflows.llm.augmented_llm import RequestParams


async def main():
    print("=" * 80)
    print("DEBUGGING CLAUDE CLI OUTPUT")
    print("=" * 80)

    # Create a simple test prompt
    test_prompt = "Hello! Please respond with 'TEST SUCCESSFUL' to confirm you're working."

    print(f"\nTest prompt: {test_prompt}\n")

    # Create provider (no agent needed for basic test)
    provider = ClaudeCodeCLIAugmentedLLM(
        agent=None,
        model="sonnet",
        timeout=60
    )

    try:
        print("Calling Claude CLI...")
        result = await provider.generate_str(
            message=test_prompt,
            request_params=RequestParams(
                model="sonnet",
                max_iterations=1
            )
        )

        print("\n" + "=" * 80)
        print("RESULT")
        print("=" * 80)
        print(f"Content length: {len(result)} characters")
        print(f"Content: {result}")
        print("=" * 80)

        if not result or len(result) == 0:
            print("\n❌ ERROR: Got empty response!")
            return 1
        else:
            print("\n✅ SUCCESS: Got non-empty response")
            return 0

    except Exception as e:
        print(f"\n❌ EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
