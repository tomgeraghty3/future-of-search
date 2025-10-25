"""Personalisation service for AgentCore Gateway integration using Strands Agent with MCP tools."""

import logging
import asyncio
from typing import Optional
from mcp.client.streamable_http import streamablehttp_client
from strands.tools.mcp import MCPClient
from strands import Agent

try:
    # Try relative imports first (when running as package)
    from ..config import config
    from ..models.data_models import PersonalisationResult
except ImportError:
    # Fall back to absolute imports (when running directly)
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config import config
    from models.data_models import PersonalisationResult

logger = logging.getLogger(__name__)


class PersonalisationService:
    """Service for personalising search results using Strands Agent with AgentCore Gateway MCP tools.
    
    This service creates a dedicated Strands Agent with MCP tools from AgentCore Gateway,
    allowing the LLM to intelligently select and use the appropriate personalisation tools.
    """
    
    def __init__(self):
        """Initialize the personalisation service."""
        self.gateway_url = config.GATEWAY_MCP_URL
        self.auth_required = config.GATEWAY_AUTH_REQUIRED
        
        # Initialize MCP client for Gateway connection
        if self.gateway_url:
            if self.auth_required:
                # For authenticated connections, we'd add headers here
                # For now, using basic connection without auth
                self.mcp_client = MCPClient(
                    lambda: streamablehttp_client(self.gateway_url)
                )
            else:
                self.mcp_client = MCPClient(
                    lambda: streamablehttp_client(self.gateway_url)
                )
        else:
            self.mcp_client = None
            logger.warning("No Gateway MCP URL configured - personalisation will be disabled")
        
        logger.info(f"PersonalisationService initialized with Gateway URL: {self.gateway_url}")
        logger.info(f"Authentication required: {self.auth_required}")
    
    async def get_personalised_content(self, user_id: str, search_topic: str) -> PersonalisationResult:
        """
        Retrieve personalised content using Strands Agent with MCP tools from AgentCore Gateway.
        
        The Agent will intelligently select and use the appropriate personalisation tools
        based on the user query and available tools.
        
        Args:
            user_id: User identifier for personalisation
            search_topic: Search query or topic for personalisation
            
        Returns:
            PersonalisationResult with content and metadata
        """
        if not user_id or not user_id.strip():
            logger.warning("Empty user_id provided to get_personalised_content")
            return PersonalisationResult(
                content="",
                tool_used="",
                success=False
            )
        
        if not search_topic or not search_topic.strip():
            logger.warning("Empty search_topic provided to get_personalised_content")
            return PersonalisationResult(
                content="",
                tool_used="",
                success=False
            )
        
        if not self.mcp_client:
            logger.warning("No MCP client configured - personalisation disabled")
            return PersonalisationResult(
                content="",
                tool_used="",
                success=False
            )
        
        user_id = user_id.strip()
        search_topic = search_topic.strip()
        
        logger.info(f"Getting personalised content for user: {user_id}, topic: '{search_topic[:50]}{'...' if len(search_topic) > 50 else ''}'")
        
        try:
            # Use MCP client within context manager as required by Strands
            with self.mcp_client:
                # Get MCP tools and create Agent
                tools = self.mcp_client.list_tools_sync()
                
                if not tools:
                    logger.info("No MCP tools available from Gateway")
                    return PersonalisationResult(
                        content="",
                        tool_used="",
                        success=False
                    )
                
                logger.info(f"Found {len(tools)} MCP tools from Gateway, creating personalisation agent")
                
                # Create personalisation agent with MCP tools
                personalisation_agent = Agent(
                    tools=tools,
                    system_prompt=f"""You are a personalisation assistant that helps provide personalized content for users.

User ID: {user_id}
Search Topic: {search_topic}

Your task is to use the available tools to find personalized information, recommendations, or content relevant to this user and their search topic. 

Guidelines:
- Use the user ID to access user-specific data when available
- Focus on the search topic to provide relevant personalized content
- If multiple tools are available, choose the most appropriate one for the query
- Provide helpful, personalized responses based on the user's context
- If no personalized content is available, clearly state that

Available tools will help you access user preferences, history, recommendations, or other personalized data."""
                )
                
                # Let the Agent decide which tools to use and how to use them
                response = personalisation_agent(
                    f"Please provide personalized content for user {user_id} related to: {search_topic}"
                )
                
                if response and response.strip():
                    logger.info("Successfully retrieved personalised content using Strands Agent")
                    return PersonalisationResult(
                        content=response.strip(),
                        tool_used="strands_agent_with_mcp_tools",
                        success=True
                    )
                else:
                    logger.info("Agent returned empty response")
                    return PersonalisationResult(
                        content="",
                        tool_used="strands_agent_with_mcp_tools",
                        success=False
                    )
            
        except Exception as e:
            logger.error(f"Error getting personalised content with Agent: {str(e)}")
            return PersonalisationResult(
                content="",
                tool_used="",
                success=False
            )
    
    async def health_check(self) -> bool:
        """
        Perform a health check on the personalisation service using Strands MCP Client.
        
        Returns:
            True if service is healthy, False otherwise
        """
        if not self.mcp_client:
            logger.warning("No MCP client configured - health check failed")
            return False
        
        try:
            # Try to connect and list tools to check if Gateway is accessible
            with self.mcp_client:
                tools = self.mcp_client.list_tools_sync()
                logger.debug(f"Personalisation service health check passed - found {len(tools)} tools")
                return True
            
        except Exception as e:
            logger.error(f"Personalisation service health check failed: {str(e)}")
            return False