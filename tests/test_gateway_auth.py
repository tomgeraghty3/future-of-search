#!/usr/bin/env python3
"""
Standalone test script for Gateway MCP connection with Cognito authentication.

This script tests the Gateway connection independently of the main agent,
making it easier to debug authentication issues.
"""

import asyncio
import logging
import os
import sys
from dotenv import load_dotenv

# Add the project root to the path so we can import our modules
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from tools.cognito_token_manager import CognitoTokenManager, CognitoTokenManagerError
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client

# Load environment variables from project root
load_dotenv(os.path.join(project_root, '.env'))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def create_authenticated_mcp_client(gateway_url: str, token_manager: CognitoTokenManager):
    """Create MCP client with Cognito authentication."""
    
    # Get access token
    access_token = await token_manager.get_access_token()
    
    # Create MCP client with Authorization header
    mcp_client = MCPClient(lambda: streamablehttp_client(
        url=gateway_url,
        headers={"Authorization": f"Bearer {access_token}"}
    ))
    
    return mcp_client


async def test_cognito_token_manager():
    """Test the Cognito Token Manager independently."""
    
    logger.info("=== Testing Cognito Token Manager ===")
    
    # Get configuration from environment
    config = {
        'user_pool_id': os.environ.get('COGNITO_USER_POOL_ID'),
        'client_id': os.environ.get('COGNITO_CLIENT_ID'),
        'client_secret': os.environ.get('COGNITO_CLIENT_SECRET'),
        'domain': os.environ.get('COGNITO_DOMAIN'),
        'region': os.environ.get('COGNITO_REGION', os.environ.get('AWS_REGION', 'us-east-1')),
        'scope': os.environ.get('COGNITO_SCOPE', '')
    }
    
    # Check for missing configuration
    missing_config = [k for k, v in config.items() if not v and k != 'scope']
    if missing_config:
        logger.error(f"Missing required Cognito configuration: {missing_config}")
        logger.info("Please set the following environment variables:")
        for key in missing_config:
            logger.info(f"  {key.upper()}")
        return None
    
    logger.info("Cognito configuration found:")
    for key, value in config.items():
        if key == 'client_secret':
            logger.info(f"  {key}: {'*' * len(value) if value else 'None'}")
        else:
            logger.info(f"  {key}: {value}")
    
    try:
        # Create token manager
        token_manager = CognitoTokenManager(
            user_pool_id=config['user_pool_id'],
            client_id=config['client_id'],
            client_secret=config['client_secret'],
            region=config['region'],
            domain=config['domain'],
            scope=config['scope']
        )
        
        # Test token retrieval
        logger.info("Requesting access token...")
        access_token = await token_manager.get_access_token()
        
        logger.info("✓ Successfully obtained access token")
        logger.info(f"Token info: {token_manager.get_token_info()}")
        
        return token_manager
        
    except CognitoTokenManagerError as e:
        logger.error(f"❌ Cognito authentication failed: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"❌ Unexpected error: {str(e)}")
        return None


async def test_gateway_connection():
    """Test Gateway MCP connection with authentication."""
    
    logger.info("\n=== Testing Gateway MCP Connection ===")
    
    gateway_url = os.environ.get('GATEWAY_MCP_URL')
    if not gateway_url:
        logger.error("❌ GATEWAY_MCP_URL not configured")
        return False
    
    logger.info(f"Gateway URL: {gateway_url}")
    
    # First test Cognito authentication
    token_manager = await test_cognito_token_manager()
    if not token_manager:
        logger.error("❌ Cannot test Gateway connection without valid authentication")
        return False
    
    try:
        # Create authenticated MCP client
        logger.info("Creating authenticated MCP client...")
        mcp_client = await create_authenticated_mcp_client(gateway_url, token_manager)
        
        # Test the connection
        logger.info("Testing MCP connection...")
        with mcp_client:
            logger.info("✓ MCP session established")
            
            # List available tools
            logger.info("Discovering available tools...")
            tools = mcp_client.list_tools_sync()
            
            logger.info(f"✓ Successfully discovered {len(tools)} tools:")
            for i, tool in enumerate(tools, 1):
                tool_name = getattr(tool, 'tool_name', getattr(tool, 'name', 'Unknown'))
                tool_description = getattr(tool, 'description', 'No description')
                logger.info(f"  {i}. {tool_name}: {tool_description}")
            
            return True
            
    except Exception as e:
        logger.error(f"❌ Gateway connection failed: {str(e)}")
        if "401" in str(e) or "Unauthorized" in str(e):
            logger.error("This appears to be an authentication error.")
            logger.info("Please check:")
            logger.info("  1. Your Cognito User Pool configuration")
            logger.info("  2. App client has 'client_credentials' grant enabled")
            logger.info("  3. App client has appropriate OAuth scopes")
            logger.info("  4. Gateway is configured to accept your Cognito User Pool")
        return False


async def main():
    """Main test function."""
    
    logger.info("🚀 Starting Gateway Authentication Test")
    logger.info("=" * 50)
    
    # Test Cognito token manager
    token_manager = await test_cognito_token_manager()
    
    if token_manager:
        # Test Gateway connection
        success = await test_gateway_connection()
        
        if success:
            logger.info("\n🎉 All tests passed! Gateway authentication is working correctly.")
        else:
            logger.error("\n❌ Gateway connection test failed.")
            sys.exit(1)
    else:
        logger.error("\n❌ Cognito authentication test failed.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())