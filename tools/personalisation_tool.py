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
from .cognito_token_manager import CognitoTokenManager, CognitoTokenManagerError
import asyncio
import httpx
import json

logger = logging.getLogger(__name__)


class PersonalisationError(Exception):
    """Custom exception for personalisation tool errors"""
    pass


class ToolMatcher:
    """Handles semantic matching of search topics to available MCP tools using LLM"""
    
    @staticmethod
    async def find_relevant_tool(available_tools: List[Dict], search_topic: str, tool_context: ToolContext) -> Optional[Dict]:
        """
        Find the most relevant tool for a given search topic using LLM semantic matching.
        
        Args:
            available_tools: List of available MCP tools from Gateway
            search_topic: User's search query
            tool_context: ToolContext to access the LLM for semantic matching
            
        Returns:
            Most relevant tool dict or None if no match found
        """
        if not available_tools:
            return None
            
        # Prepare tool descriptions for LLM analysis
        tools_summary = []
        for i, tool in enumerate(available_tools):
            tool_info = {
                "index": i,
                "name": tool.get('name', ''),
                "description": tool.get('description', '')
            }
            tools_summary.append(tool_info)
        
        # Create prompt for LLM to select the most relevant tool
        selection_prompt = f"""Given the user's search topic: "{search_topic}"

Available personalization tools:
{json.dumps(tools_summary, indent=2)}

Task: Select the most relevant tool for personalizing the search results based on the user's topic.

Requirements:
- The tool should be able to provide personalized information related to the search topic
- Consider tools that can access user-specific data like preferences, history, or account information
- If no tool is clearly relevant for personalization, respond with "NONE"

Respond with ONLY the index number of the most relevant tool, or "NONE" if no tool is suitable for personalization."""

        try:
            # Use the LLM to make the selection
            response = await tool_context.llm.generate_text(selection_prompt)
            response_text = response.strip()
            
            # Parse the response
            if response_text.upper() == "NONE":
                return None
                
            try:
                selected_index = int(response_text)
                if 0 <= selected_index < len(available_tools):
                    return available_tools[selected_index]
                else:
                    logger.warning(f"LLM returned invalid tool index: {selected_index}")
                    return None
            except ValueError:
                logger.warning(f"LLM returned non-numeric response: {response_text}")
                return None
                
        except Exception as e:
            logger.error(f"Error using LLM for tool selection: {str(e)}")
            # Fallback to simple keyword matching if LLM fails
            return ToolMatcher._fallback_keyword_matching(available_tools, search_topic)
    
    @staticmethod
    def _fallback_keyword_matching(available_tools: List[Dict], search_topic: str) -> Optional[Dict]:
        """
        Fallback keyword-based matching when LLM is unavailable.
        
        Args:
            available_tools: List of available MCP tools from Gateway
            search_topic: User's search query
            
        Returns:
            Most relevant tool dict or None if no match found
        """
        search_topic_lower = search_topic.lower()
        best_match = None
        best_score = 0
        
        for tool in available_tools:
            tool_name = tool.get('name', '').lower()
            tool_description = tool.get('description', '').lower()
            
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
            
        # Create MCP client for Gateway connection with authentication
        logger.debug(f"[{request_id}] Connecting to Gateway at {gateway_url}")
        
        try:
            # Check if we have Cognito configuration for authentication
            cognito_config = {
                'user_pool_id': tool_context.invocation_state.get("cognito_user_pool_id"),
                'client_id': tool_context.invocation_state.get("cognito_client_id"),
                'client_secret': tool_context.invocation_state.get("cognito_client_secret"),
                'domain': tool_context.invocation_state.get("cognito_domain"),
                'region': tool_context.invocation_state.get("cognito_region")
            }
            
            # Check if all required Cognito config is present
            missing_config = [k for k, v in cognito_config.items() if not v and k != 'scope']
            
            if missing_config:
                error_msg = f"Missing required Cognito configuration for Gateway authentication: {missing_config}"
                logger.error(f"[{request_id}] {error_msg}")
                raise PersonalisationError(f"Gateway authentication not configured: missing {', '.join(missing_config)}")
            
            # Create authenticated MCP client
            logger.info(f"[{request_id}] Creating authenticated Gateway connection")
            token_manager = CognitoTokenManager(
                user_pool_id=cognito_config['user_pool_id'],
                client_id=cognito_config['client_id'],
                client_secret=cognito_config['client_secret'],
                region=cognito_config['region'],
                domain=cognito_config['domain']
            )
            
            # Get access token
            access_token = await token_manager.get_access_token()
            
            # Create MCP client with Authorization header
            gateway_mcp_client = MCPClient(lambda: streamablehttp_client(
                url=gateway_url,
                headers={"Authorization": f"Bearer {access_token}"}
            ))
                
        except CognitoTokenManagerError as e:
            logger.error(f"[{request_id}] Cognito authentication failed: {str(e)}")
            raise PersonalisationError("Gateway authentication failed")
        except Exception as e:
            logger.error(f"[{request_id}] Failed to create MCP client: {str(e)}")
            raise PersonalisationError("Failed to connect to Gateway")
            
        # Use context manager for MCP session with enhanced error handling
        mcp_session = None
        try:
            # Initialize MCP session with timeout
            mcp_session = gateway_mcp_client
            
            # Use timeout wrapper for MCP operations
            async def _execute_mcp_operations():
                with mcp_session:
                    logger.debug(f"[{request_id}] MCP session established with Gateway")
                    
                    # Discover available tools
                    try:
                        available_tools = gateway_mcp_client.list_tools_sync()
                        logger.info(f"[{request_id}] Found {len(available_tools)} available tools")
                    except Exception as e:
                        logger.error(f"[{request_id}] Tool discovery failed: {str(e)}")
                        raise PersonalisationError("Failed to discover tools from Gateway")
                    
                    if not available_tools:
                        logger.info(f"[{request_id}] No tools available from Gateway")
                        return {"personalised": ""}
                    
                    # Find relevant tool for search topic (LLM-based semantic matching)
                    relevant_tool = await ToolMatcher.find_relevant_tool(available_tools, search_topic, tool_context)
                    
                    if not relevant_tool:
                        logger.info(f"[{request_id}] No relevant personalization tool found for topic: {search_topic}")
                        return {"personalised": ""}
                    
                    tool_name = relevant_tool.get('name')
                    logger.info(f"[{request_id}] Found relevant tool: {tool_name}")
                    
                    # Invoke the tool with user_id and search query
                    try:
                        logger.debug(f"[{request_id}] Invoking tool {tool_name}")
                        
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
                        raise PersonalisationError(f"Failed to execute personalization tool: {str(e)}")
                    
                    return {"personalised": ""}
            
            # Execute MCP operations with timeout
            return await asyncio.wait_for(_execute_mcp_operations(), timeout=10.0)
                    
        except asyncio.TimeoutError:
            logger.error(f"[{request_id}] MCP session timeout")
            raise PersonalisationError("Gateway request timeout")
        except Exception as e:
            logger.error(f"[{request_id}] MCP session error: {str(e)}")
            raise PersonalisationError("MCP session failed")
        finally:
            # Ensure proper cleanup of MCP session
            if mcp_session:
                try:
                    # MCP client cleanup is handled by context manager
                    logger.debug(f"[{request_id}] MCP session cleanup completed")
                except Exception as cleanup_error:
                    logger.warning(f"[{request_id}] MCP session cleanup error: {str(cleanup_error)}")
            
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
