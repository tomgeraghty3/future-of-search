#!/usr/bin/env python3
"""
Timeout configuration test script.
This script helps test and validate timeout settings for the search agent.
"""

import os
import asyncio
import time
from config import Config

def test_timeout_configuration():
    """Test and display current timeout configuration."""
    print("=== Timeout Configuration Test ===\n")
    
    # Load configuration
    config = Config()
    
    print("Current Timeout Settings:")
    print(f"  Response Timeout: {config.response_timeout} seconds")
    print(f"  MCP Timeout: {config.mcp_timeout} seconds") 
    print(f"  HTTP Timeout: {config.http_timeout} seconds")
    print()
    
    # Environment variables
    print("Environment Variables:")
    print(f"  RESPONSE_TIMEOUT: {os.environ.get('RESPONSE_TIMEOUT', 'Not set')}")
    print(f"  MCP_TIMEOUT: {os.environ.get('MCP_TIMEOUT', 'Not set')}")
    print(f"  HTTP_TIMEOUT: {os.environ.get('HTTP_TIMEOUT', 'Not set')}")
    print()
    
    # Recommendations
    print("Recommended Settings for Different Scenarios:")
    print("  Development: RESPONSE_TIMEOUT=120, MCP_TIMEOUT=60, HTTP_TIMEOUT=120")
    print("  Testing: RESPONSE_TIMEOUT=60, MCP_TIMEOUT=30, HTTP_TIMEOUT=60") 
    print("  Production: RESPONSE_TIMEOUT=45, MCP_TIMEOUT=20, HTTP_TIMEOUT=45")
    print()

async def test_asyncio_timeout():
    """Test asyncio timeout functionality."""
    print("=== Asyncio Timeout Test ===")
    
    async def slow_operation(delay: int):
        """Simulate a slow operation."""
        print(f"Starting slow operation ({delay}s)...")
        await asyncio.sleep(delay)
        return f"Completed after {delay}s"
    
    # Test successful operation within timeout
    try:
        result = await asyncio.wait_for(slow_operation(2), timeout=5)
        print(f"✓ Success: {result}")
    except asyncio.TimeoutError:
        print("✗ Unexpected timeout for fast operation")
    
    # Test timeout handling
    try:
        result = await asyncio.wait_for(slow_operation(10), timeout=3)
        print(f"✗ Unexpected success: {result}")
    except asyncio.TimeoutError:
        print("✓ Correctly caught timeout for slow operation")
    
    print()

def create_env_file_example():
    """Create an example .env file with timeout settings."""
    env_content = """# Timeout Configuration for Future of Search
# All timeouts are in seconds

# Agent response timeout (total time for agent to respond)
RESPONSE_TIMEOUT=120

# MCP client timeout (time for MCP operations)
MCP_TIMEOUT=60

# HTTP client timeout (time for HTTP requests)
HTTP_TIMEOUT=120

# Other useful settings
LOG_LEVEL=INFO
ENVIRONMENT=development
"""
    
    print("=== Example .env Configuration ===")
    print(env_content)
    
    # Optionally save to file
    save = input("Save this configuration to .env.example? (y/n): ").lower().strip()
    if save == 'y':
        with open('.env.example', 'w') as f:
            f.write(env_content)
        print("✓ Saved to .env.example")

if __name__ == "__main__":
    print("Customer Search Agent - Timeout Configuration Tool\n")
    
    # Test configuration
    test_timeout_configuration()
    
    # Test asyncio timeout functionality
    asyncio.run(test_asyncio_timeout())
    
    # Create example configuration
    create_env_file_example()
    
    print("\n=== Quick Fixes for Timeout Issues ===")
    print("1. Increase RESPONSE_TIMEOUT environment variable")
    print("2. Increase MCP_TIMEOUT for Gateway operations")
    print("3. Increase HTTP_TIMEOUT for slow network requests")
    print("4. Check network connectivity to AWS services")
    print("5. Monitor logs for specific timeout sources")
    print("6. Consider implementing retry logic for failed operations")