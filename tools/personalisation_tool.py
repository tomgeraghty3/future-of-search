"""
Personalisation Tool for Customer Search Agent

This tool integrates with AWS AgentCore Gateway via MCP protocol to provide
personalized information for logged-in users. The Gateway acts as an MCP server
that exposes external tools/APIs as MCP tools.
"""

import logging
import uuid
from typing import Dict, List, Optional, Any
from strands import tool, ToolContext
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client
import asyncio
import httpx

logger = logging.getLogger(__name__)


class PersonalisationError(Exception):
    """Custom exception for personalisation tool errors"""
    pass


class ToolMatcher:
    """Handles semantic matching of search topics to available MCP tools"""
    
    @staticmethod
    def find_relevant_tool(available_tools: List[Dict], search_topic: str) -> Optional[Dict]:
        """
        Find the most relevant tool for a given search topic using semantic matching.
        
        Args:
            available_tools: List of available MCP tools from Gateway
            search_topic: User's search query
            
        Returns:
            Most relevant tool dict or None if no match found
        """
        if not available_tools:
            return None
            
        search_topic_lower = search_topic.lower()
        best_match = None
        best_score = 0
        
        for tool in available_tools:
            tool_name = tool.get('name', '').lower()
            tool_description = tool.get('description', '').lower()
            
            # Simple keyword-based matching - can be enhanced with more sophisticated NLP
            score = 0
            
            # Check for direct keyword matches in tool name
            if any(keyword in tool_name for keyword in search_topic_lower.split()):
                score += 3
                
            # Check for keyword matches in description
            if any(keyword in tool_description for keyword in search_topic_lower.split()):
                score += 2
                
            # Check for common personalization keywords
            personalization_keywords = ['account', 'profile', 'user', 'personal', 'history', 'preference']
            if any(keyword in search_topic_lower for keyword in personalization_keywords):
                if any(keyword in tool_name or keyword in tool_description for keyword in personalization_keywords):
                    score += 1
                    
            if score > best_score:
                best_score = score
                best_match = tool
                
        # Only return a match if we have a reasonable confidence
        return best_match if best_score >= 2 else None


@tool(context=True)
async def personalisation_tool(search_topic: str, user_id: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    Get personalized information via AgentCore Gateway acting as MCP server.
    
    The Gateway exposes external tools/APIs as MCP tools, allowing the agent
    to discover and invoke relevant external services for personalization.
    
    Args:
        search_topic: Natural language search query
        user_id: Authenticated user identifier
        tool_context: Provides access to agent context and invocation state
                     - tool_context.invocation_state: Contains gateway configuration
                     - tool_context.tool_use: Current tool invocation details
    
    Returns:
        dict: Contains personalized information or empty if no relevant external tool found
    """
    request_id = tool_context.invocation_state.get("request_id", str(uuid.uuid4()))
    tool_use_id = tool_context.tool_use.get("toolUseId", str(uuid.uuid4()))
    
    logger.info(f"[{request_id}] Starting personalisation tool for user {user_id}, topic: {search_topic}")
    
    try:
        # Access gateway configuration from invocation state
        gateway_url = tool_context.invocation_state.get("gateway_mcp_url")
        
        if not gateway_url:
            logger.error(f"[{request_id}] Gateway MCP URL not configured")
            raise PersonalisationError("Gateway MCP URL not configured")
            
        if not user_id:
            logger.info(f"[{request_id}] No user_id provided, skipping personalization")
            return {"personalised": ""}
            
        # Create MCP client for Gateway connection
        logger.debug(f"[{request_id}] Connecting to Gateway at {gateway_url}")
        
        try:
            gateway_mcp_client = MCPClient(lambda: streamablehttp_client(gateway_url))
        except Exception as e:
            logger.error(f"[{request_id}] Failed to create MCP client: {str(e)}")
            raise PersonalisationError("Failed to connect to Gateway")
            
        # Use context manager for MCP session
        try:
            with gateway_mcp_client:
                logger.debug(f"[{request_id}] Discovering available tools from Gateway")
                
                # Discover available tools
                try:
                    available_tools = gateway_mcp_client.list_tools_sync()
                    logger.info(f"[{request_id}] Found {len(available_tools)} available tools")
                except Exception as e:
                    logger.error(f"[{request_id}] Failed to list tools from Gateway: {str(e)}")
                    raise PersonalisationError("Failed to discover tools from Gateway")
                
                # Find relevant tool for search topic (semantic matching)
                relevant_tool = ToolMatcher.find_relevant_tool(available_tools, search_topic)
                
                if not relevant_tool:
                    logger.info(f"[{request_id}] No relevant personalization tool found for topic: {search_topic}")
                    return {"personalised": ""}
                
                tool_name = relevant_tool.get('name')
                logger.info(f"[{request_id}] Found relevant tool: {tool_name}")
                
                # Invoke the tool with user_id and search query
                try:
                    logger.debug(f"[{request_id}] Invoking tool {tool_name} with user_id: {user_id}")
                    
                    result = gateway_mcp_client.call_tool_sync(
                        tool_use_id=f"personalization-{tool_use_id}",
                        name=tool_name,
                        arguments={
                            "user_id": user_id,
                            "query": search_topic
                        }
                    )
                    
                    # Extract content from MCP response
                    if result and "content" in result:
                        content_list = result.get("content", [])
                        if content_list and len(content_list) > 0:
                            personalized_content = content_list[0].get("text", "")
                            if personalized_content:
                                logger.info(f"[{request_id}] Successfully retrieved personalized content")
                                return {"personalised": personalized_content}
                    
                    logger.info(f"[{request_id}] Tool returned empty or invalid response")
                    return {"personalised": ""}
                    
                except Exception as e:
                    logger.error(f"[{request_id}] Tool execution failed for {tool_name}: {str(e)}")
                    # Don't raise exception - gracefully degrade to no personalization
                    return {"personalised": ""}
                    
        except Exception as e:
            logger.error(f"[{request_id}] MCP session error: {str(e)}")
            raise PersonalisationError("MCP session failed")
            
    except PersonalisationError:
        # Re-raise our custom errors
        raise
    except httpx.ConnectError as e:
        logger.error(f"[{request_id}] Gateway connection failed: {str(e)}")
        raise PersonalisationError("Gateway unavailable")
    except asyncio.TimeoutError as e:
        logger.error(f"[{request_id}] Gateway request timeout: {str(e)}")
        raise PersonalisationError("Gateway request timeout")
    except Exception as e:
        logger.error(f"[{request_id}] Unexpected error in personalisation tool: {str(e)}")
        raise PersonalisationError("Personalisation service error")


# Helper function for testing and development
def validate_tool_response(response: Dict[str, Any]) -> bool:
    """
    Validate that the tool response has the expected structure.
    
    Args:
        response: Response from personalisation_tool
        
    Returns:
        bool: True if response is valid
    """
    if not isinstance(response, dict):
        return False
        
    if "personalised" not in response:
        return False
        
    personalised_content = response["personalised"]
    return isinstance(personalised_content, str)


# Export the tool for use in the main agent
__all__ = ["personalisation_tool", "PersonalisationError", "ToolMatcher", "validate_tool_response"]