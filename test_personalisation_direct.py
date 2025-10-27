#!/usr/bin/env python3
"""
Direct testing script for the personalisation tool.

This script allows you to test the personalisation_tool directly without 
going through the full E2E agent flow. It sets up the necessary context
and calls the tool with your test parameters.
"""

import asyncio
import logging
import sys
from typing import Dict, Any, Optional
from config import Config
from tools.personalisation_tool import personalisation_tool, PersonalisationError
from strands import ToolContext
from strands.models import BedrockModel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MockToolContext:
    """Mock ToolContext for direct testing of the personalisation tool."""
    
    def __init__(self, config: Config):
        self.config = config
        self.invocation_state = config.to_dict()
        self.tool_use = {"toolUseId": "test-tool-use-123"}
        
        # Initialize LLM for tool matching
        self.llm = BedrockModel(
            model_id="anthropic.claude-3-sonnet-20240229-v1:0",
            temperature=0.1,
            max_tokens=1000
        )


async def test_personalisation_tool(search_topic: str, user_id: Optional[str] = None):
    """
    Test the personalisation tool directly with given parameters.
    
    Args:
        search_topic: The search query to test
        user_id: Optional user ID for personalization
    """
    try:
        logger.info(f"Testing personalisation tool with:")
        logger.info(f"  Search topic: {search_topic}")
        logger.info(f"  User ID: {user_id or 'None (anonymous)'}")
        
        # Load configuration
        config = Config()
        
        # Create mock tool context
        tool_context = MockToolContext(config)
        
        # Add request ID for tracking
        tool_context.invocation_state["request_id"] = "direct-test-123"
        
        logger.info("Calling personalisation_tool...")
        
        # Call the personalisation tool directly
        result = await personalisation_tool(
            search_topic=search_topic,
            user_id=user_id or "",
            tool_context=tool_context
        )
        
        logger.info("Personalisation tool completed successfully!")
        logger.info(f"Result: {result}")
        
        return result
        
    except PersonalisationError as e:
        logger.error(f"Personalisation tool error: {str(e)}")
        return {"personalised": "", "error": str(e)}
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return {"personalised": "", "error": f"Unexpected error: {str(e)}"}


async def test_gateway_tools_discovery():
    """Test just the Gateway tools discovery without personalization."""
    try:
        logger.info("Testing Gateway tools discovery...")
        
        # Load configuration
        config = Config()
        
        # Import required modules
        from tools.cognito_token_manager import CognitoTokenManager, CognitoTokenManagerError
        from strands.tools.mcp import MCPClient
        from mcp.client.streamable_http import streamablehttp_client
        
        gateway_url = config.gateway_mcp_url
        if not gateway_url:
            logger.error("Gateway MCP URL not configured")
            return None
            
        logger.info(f"Connecting to Gateway at: {gateway_url}")
        
        # Check Cognito configuration
        cognito_config = {
            'user_pool_id': getattr(config, 'cognito_user_pool_id', None),
            'client_id': getattr(config, 'cognito_client_id', None),
            'client_secret': getattr(config, 'cognito_client_secret', None),
            'domain': getattr(config, 'cognito_domain', None),
            'region': getattr(config, 'cognito_region', config.aws_region)
        }
        
        missing_config = [k for k, v in cognito_config.items() if not v]
        if missing_config:
            logger.error(f"Missing Cognito config: {missing_config}")
            return None
        
        # Create token manager
        token_manager = CognitoTokenManager(
            user_pool_id=cognito_config['user_pool_id'],
            client_id=cognito_config['client_id'],
            client_secret=cognito_config['client_secret'],
            region=cognito_config['region'],
            domain=cognito_config['domain']
        )
        
        # Get access token
        access_token = await token_manager.get_access_token()
        logger.info("Successfully obtained access token")
        
        # Create MCP client
        gateway_mcp_client = MCPClient(lambda: streamablehttp_client(
            url=gateway_url,
            headers={"Authorization": f"Bearer {access_token}"}
        ))
        
        # Test tools discovery
        with gateway_mcp_client:
            logger.info("MCP session established")
            
            available_tools = gateway_mcp_client.list_tools_sync()
            logger.info(f"Found {len(available_tools)} tools:")
            
            for i, tool in enumerate(available_tools):
                tool_name = getattr(tool, 'tool_name', 'Unknown')
                tool_spec = getattr(tool, 'tool_spec')
                
                # Extract description from tool_spec dictionary
                if isinstance(tool_spec, dict):
                    tool_description = tool_spec.get('description', 'No description')
                else:
                    # Fallback for other types
                    tool_description = 'No description'
                
                logger.info(f"  {i+1}. {tool_name}: {tool_description}")
            
            return available_tools
            
    except Exception as e:
        logger.error(f"Gateway discovery failed: {str(e)}")
        return None


async def test_tool_with_specific_tool(search_topic: str, user_id: str, tool_name: str):
    """Test calling a specific tool from the Gateway."""
    try:
        logger.info(f"Testing specific tool: {tool_name}")
        
        # Load configuration
        config = Config()
        
        # Import required modules
        from tools.cognito_token_manager import CognitoTokenManager
        from strands.tools.mcp import MCPClient
        from mcp.client.streamable_http import streamablehttp_client
        
        gateway_url = config.gateway_mcp_url
        
        # Create token manager
        cognito_config = {
            'user_pool_id': getattr(config, 'cognito_user_pool_id', None),
            'client_id': getattr(config, 'cognito_client_id', None),
            'client_secret': getattr(config, 'cognito_client_secret', None),
            'domain': getattr(config, 'cognito_domain', None),
            'region': getattr(config, 'cognito_region', config.aws_region)
        }
        
        token_manager = CognitoTokenManager(**cognito_config)
        access_token = await token_manager.get_access_token()
        
        # Create MCP client
        gateway_mcp_client = MCPClient(lambda: streamablehttp_client(
            url=gateway_url,
            headers={"Authorization": f"Bearer {access_token}"}
        ))
        
        # Call specific tool
        with gateway_mcp_client:
            logger.info(f"Calling tool: {tool_name}")
            
            result = gateway_mcp_client.call_tool_sync(
                tool_use_id="direct-test-tool-call",
                name=tool_name,
                arguments={
                    "user_id": user_id,
                    "query": search_topic
                }
            )
            
            logger.info(f"Tool result: {result}")
            return result
            
    except Exception as e:
        logger.error(f"Tool call failed: {str(e)}")
        return None


def main():
    """Main function for interactive testing."""
    print("=== Direct Personalisation Tool Testing ===")
    print()
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python test_personalisation_direct.py <command> [args...]")
        print()
        print("Commands:")
        print("  test <search_topic> [user_id]     - Test personalisation tool")
        print("  discover                          - Discover available Gateway tools")
        print("  call <tool_name> <search_topic> <user_id> - Call specific Gateway tool")
        print()
        print("Examples:")
        print("  python test_personalisation_direct.py test 'laptop recommendations'")
        print("  python test_personalisation_direct.py test 'laptop recommendations' 'user123'")
        print("  python test_personalisation_direct.py discover")
        print("  python test_personalisation_direct.py call 'user_preferences' 'laptops' 'user123'")
        return
    
    command = sys.argv[1].lower()
    
    if command == "test":
        if len(sys.argv) < 3:
            print("Error: search_topic required for test command")
            return
        
        search_topic = sys.argv[2]
        user_id = sys.argv[3] if len(sys.argv) > 3 else None
        
        print(f"Testing personalisation tool...")
        result = asyncio.run(test_personalisation_tool(search_topic, user_id))
        print(f"\nResult: {result}")
        
    elif command == "discover":
        print("Discovering Gateway tools...")
        tools = asyncio.run(test_gateway_tools_discovery())
        if tools:
            print(f"\nFound {len(tools)} tools successfully!")
        else:
            print("\nFailed to discover tools.")
            
    elif command == "call":
        if len(sys.argv) < 5:
            print("Error: call command requires tool_name, search_topic, and user_id")
            return
        
        tool_name = sys.argv[2]
        search_topic = sys.argv[3]
        user_id = sys.argv[4]
        
        print(f"Calling specific tool: {tool_name}")
        result = asyncio.run(test_tool_with_specific_tool(search_topic, user_id, tool_name))
        print(f"\nResult: {result}")
        
    else:
        print(f"Unknown command: {command}")
        print("Use 'test', 'discover', or 'call'")


if __name__ == "__main__":
    main()
