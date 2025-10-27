"""Main entry point for Customer Search Agent on AWS AgentCore Runtime."""

import logging
import uuid
import json
import asyncio
from typing import Dict, Any, Optional, List
from contextlib import asynccontextmanager
from pydantic import BaseModel

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from strands.models import BedrockModel

from config import Config
from tools.knowledge_tool import knowledge_tool
from tools.personalisation_tool import personalisation_tool, PersonalisationError
from tools.cognito_token_manager import CognitoTokenManager, CognitoTokenManagerError
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client
import httpx
from tools.guardrails_tool import guardrails_tool


class SearchResponse(BaseModel):
    """Structured response model for search results."""
    personalised: str = ""
    summary: str
    links: List[str] = []


# Initialize the AgentCore Runtime application
app = BedrockAgentCoreApp()

# Global configuration instance - initialized lazily
config = None


def get_config() -> Config:
    """Get or initialize the global configuration instance."""
    global config
    if config is None:
        config = Config()
    return config

# Configure structured logging with correlation ID support
logging.basicConfig(
    level=logging.INFO,  # Default level, will be updated when config is loaded
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Correlation ID tracking for request tracing
_current_correlation_id = None

def set_correlation_id(correlation_id: str):
    """Set the current correlation ID for logging."""
    global _current_correlation_id
    _current_correlation_id = correlation_id

def get_correlation_id() -> str:
    """Get the current correlation ID."""
    return _current_correlation_id or 'unknown'


class CustomerSearchAgent:
    """Customer Search Agent implementation with proper error handling and MCP session management."""
    
    def __init__(self, config: Config):
        # Update logging level based on config
        logging.getLogger().setLevel(getattr(logging, config.log_level))
        """Initialize the Customer Search Agent.
        
        Args:
            config: Configuration instance containing environment variables
        """
        self.config = config
        self.agent = None
        self._mcp_sessions = {}  # Track MCP sessions for proper cleanup
        self._initialize_agent()
    
    def _initialize_agent(self):
        """Initialize the Strands Agent with system prompt and tools."""
        # System prompt defining agent role and capabilities with enhanced reasoning
        system_prompt = """## Role
You are an intelligent customer search agent working for Scottish Power (SP), powered by Claude 3.7 Sonnet. You use advanced reasoning to understand customer intent and efficiently provide accurate information.
 
## Goal
Help SP customers find the most accurate, relevant, and trustworthy information. Use tools efficiently - if one fails, continue with available information.
 
## Tools you have
Knowledge Tool – Search the official SP knowledge base for authoritative, approved information.
Personalisation Tool – Retrieve personalized details for authenticated customers (optional, fail gracefully if unavailable).
Guardrail Tool – Validate responses for safety and accuracy (use once at the end).
 
## Efficient Process
1. Always start with the Knowledge Tool to get factual information
2. Try Personalisation Tool only if user_id is provided (skip if it fails quickly)
3. Use Guardrails Tool once at the end to validate your final response
4. If any tool fails, continue with available information rather than retrying
5. Provide a helpful response even if some tools fail
 
## Response Format
Always respond in this exact JSON format:
{
  "personalised": "Any personalized information from personalisation tool, or empty string if unavailable",
  "summary": "Comprehensive answer based on knowledge base information",
  "links": ["list", "of", "relevant", "URLs"]
}
 
## Important Guidelines
- Prioritize speed and accuracy over completeness
- Don't retry failed tools - fail fast and continue
- Always include knowledge base information in your summary
- Provide helpful responses even when personalization fails
- Include source links when available
- Keep responses factual and based on official SP information"""

        # Configure Claude 3.7 Sonnet model with optimal settings
        model_config = BedrockModel(
            model_id="anthropic.claude-3-sonnet-20240229-v1:0",
            temperature=0.1,  # Lower temperature for more consistent responses
            max_tokens=4000   # Sufficient for comprehensive responses
        )
        
        # Configure available tools
        tools = [knowledge_tool, personalisation_tool, guardrails_tool]
        
        # Create the agent with enhanced configuration
        self.agent = Agent(
            model=model_config,
            tools=tools,
            name=self.config.agent_name,
            system_prompt=system_prompt
        )
        
        logger.info(f"Initialized Customer Search Agent: {self.config.agent_name} with Claude 3.7 Sonnet")
    
    @asynccontextmanager
    async def _correlation_context(self, correlation_id: str):
        """Context manager for correlation ID tracking in logs."""
        set_correlation_id(correlation_id)
        try:
            yield
        finally:
            set_correlation_id(None)
    
    async def search(self, search_topic: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Process search request with comprehensive error handling and correlation tracking.
        
        Args:
            search_topic: Natural language search query
            user_id: Optional user identifier for personalization
            
        Returns:
            Dict containing personalised, summary, and links fields
        """
        # Generate correlation ID for request tracing
        correlation_id = str(uuid.uuid4())
        
        async with self._correlation_context(correlation_id):
            try:
                # Input validation
                if not search_topic or not search_topic.strip():
                    logger.warning("Empty search topic provided")
                    return {
                        "personalised": "",
                        "summary": "Please provide a search topic to get information.",
                        "links": []
                    }
                
                # Sanitize inputs
                search_topic = search_topic.strip()[:500]  # Limit length for safety
                if user_id:
                    user_id = user_id.strip()[:100]  # Limit user_id length
                
                # Log the incoming request
                user_context = f"logged-in user {user_id}" if user_id else "anonymous visitor"
                logger.info(f"Processing search request from {user_context}: {search_topic}")
                
                # Create invocation state with configuration for tools
                invocation_state = {
                    **self.config.to_dict(),
                    "user_id": user_id,
                    "request_id": correlation_id
                }
                
                # Construct enhanced prompt for the agent with reasoning context
                prompt = f"""A {user_context} is searching for: "{search_topic}"

Use your advanced reasoning capabilities to provide the most helpful response:

REASONING STEPS:
1. Analyze what specific information this user needs for their search topic
2. Use knowledge_tool to search for authoritative information about "{search_topic}"
3. {"Consider using personalisation_tool to enhance the response with user-specific information for user_id: " + user_id if user_id else "Skip personalization since this is an anonymous user"}
4. Synthesize all gathered information into a comprehensive, accurate response
5. Use guardrails_tool to validate your final response for safety and coherence
6. Format the validated response in the required JSON structure

QUALITY REQUIREMENTS:
- Prioritize accuracy and cite sources when available
- Provide comprehensive coverage of the topic
- Include relevant links and citations
- Ensure response is safe and appropriate
- Handle any tool failures gracefully

Return your final response in the exact JSON format specified in your system prompt."""

                # Execute agent reasoning with timeout protection
                try:
                    # First, run the agent to gather information and perform reasoning
                    await asyncio.wait_for(
                        self.agent.invoke_async(prompt, **invocation_state),
                        timeout=self.config.response_timeout
                    )
                    
                    # Then use structured output to extract the final response
                    structured_response = await asyncio.wait_for(
                        self.agent.structured_output_async(
                            SearchResponse,
                            "Based on our conversation and research, provide the final structured response."
                        ),
                        timeout=self.config.response_timeout
                    )
                    
                    result = {
                        "personalised": structured_response.personalised,
                        "summary": structured_response.summary,
                        "links": structured_response.links
                    }
                    logger.info("Successfully processed search request with structured output")
                    return result
                    
                except asyncio.TimeoutError:
                    logger.error("Agent response timeout exceeded")
                    return {
                        "personalised": "",
                        "summary": "Request timeout. Please try again with a more specific search topic.",
                        "links": []
                    }
                except Exception as e:
                    logger.warning(f"Structured output failed: {str(e)}, falling back to parsing")
                    # Fallback to the original approach
                    try:
                        response = await asyncio.wait_for(
                            self.agent.invoke_async(prompt, **invocation_state),
                            timeout=self.config.response_timeout
                        )
                        
                        result = self._parse_agent_response(response, correlation_id)
                        
                        # Final validation of response structure
                        if not self._validate_response_structure(result):
                            logger.error("Invalid response structure from agent")
                            return {
                                "personalised": "",
                                "summary": "An error occurred while formatting the response. Please try again.",
                                "links": []
                            }
                        
                        logger.info("Successfully processed search request with fallback parsing")
                        return result
                    except Exception as fallback_error:
                        logger.error(f"Both structured output and fallback failed: {str(fallback_error)}")
                        return {
                            "personalised": "",
                            "summary": "An error occurred while processing your search request. Please try again.",
                            "links": []
                        }
                
            except PersonalisationError as e:
                logger.warning(f"Personalization service error: {str(e)}")
                # Continue without personalization
                return await self._fallback_search(search_topic, correlation_id)
                
            except Exception as e:
                logger.error(f"Unexpected error processing search request: {str(e)}")
                return {
                    "personalised": "",
                    "summary": "An unexpected error occurred while processing your search request. Please try again.",
                    "links": []
                }
    
    async def _fallback_search(self, search_topic: str, correlation_id: str) -> Dict[str, Any]:
        """Fallback search without personalization when services are unavailable."""
        try:
            logger.info("Executing fallback search without personalization")
            
            # Simplified invocation state for fallback
            invocation_state = {
                **self.config.to_dict(),
                "user_id": None,
                "request_id": correlation_id
            }
            
            # Simplified prompt for knowledge-only search
            prompt = f"""Search for information about: "{search_topic}"

Use only the knowledge_tool to find relevant information and return a response in JSON format:
{{
    "personalised": "",
    "summary": "Information summary with citations",
    "links": ["source", "urls"]
}}"""
            
            # Run the agent to gather information
            await asyncio.wait_for(
                self.agent.invoke_async(prompt, **invocation_state),
                timeout=self.config.response_timeout
            )
            
            # Use structured output to get the final response
            try:
                structured_response = await asyncio.wait_for(
                    self.agent.structured_output_async(
                        SearchResponse,
                        "Provide the structured response based on the knowledge search results."
                    ),
                    timeout=self.config.response_timeout
                )
                
                return {
                    "personalised": "",  # Ensure no personalization in fallback
                    "summary": structured_response.summary,
                    "links": structured_response.links
                }
            except Exception as e:
                logger.warning(f"Structured output failed in fallback: {str(e)}")
                # Final fallback to parsing
                response = await asyncio.wait_for(
                    self.agent.invoke_async(prompt, **invocation_state),
                    timeout=self.config.response_timeout
                )
                result = self._parse_agent_response(response, correlation_id)
                result["personalised"] = ""  # Ensure no personalization in fallback
                return result
            
        except Exception as e:
            logger.error(f"Fallback search failed: {str(e)}")
            return {
                "personalised": "",
                "summary": "No AI summary could be found for the specified query",
                "links": []
            }
    
    def _parse_agent_response(self, response, correlation_id: str) -> Dict[str, Any]:
        """Parse agent response into structured format with enhanced error handling.
        
        Args:
            response: Raw agent response from Strands Agent
            correlation_id: Request correlation ID for logging
            
        Returns:
            Dict with personalised, summary, and links fields
        """
        try:
            # Initialize default response structure
            result = {
                "personalised": "",
                "summary": "",
                "links": []
            }
            
            # Handle different response formats from Strands Agent
            content = None
            
            if hasattr(response, 'content'):
                content = response.content
            elif hasattr(response, 'text'):
                content = response.text
            elif hasattr(response, 'message'):
                # Check if it's a message object with content
                message = response.message
                if isinstance(message, dict) and 'content' in message:
                    message_content = message['content']
                    # Handle list of content blocks (common in Strands Agent responses)
                    if isinstance(message_content, list) and len(message_content) > 0:
                        # Extract text from the first content block
                        first_block = message_content[0]
                        if isinstance(first_block, dict) and 'text' in first_block:
                            content = first_block['text']
                        else:
                            content = str(first_block)
                    elif isinstance(message_content, str):
                        content = message_content
                    else:
                        content = str(message_content)
                elif hasattr(message, 'content'):
                    # Fallback for object-style access
                    message_content = message.content
                    if isinstance(message_content, list) and len(message_content) > 0:
                        first_block = message_content[0]
                        if isinstance(first_block, dict) and 'text' in first_block:
                            content = first_block['text']
                        else:
                            content = str(first_block)
                    else:
                        content = str(message_content)
                elif isinstance(message, str):
                    content = message
            elif isinstance(response, str):
                content = response
            elif isinstance(response, dict):
                # If response is already a dict, try to use it directly
                if all(key in response for key in ["personalised", "summary", "links"]):
                    return self._sanitize_response(response)
                content = response.get('content') or response.get('text') or response.get('message') or str(response)
            
            # Try to extract content from nested structures
            if not content and hasattr(response, '__dict__'):
                response_dict = response.__dict__
                content = response_dict.get('content') or response_dict.get('text') or response_dict.get('message')
            
            if not content:
                logger.warning("No content found in agent response")
                return result
            
            # Try to extract JSON from the response content with multiple strategies
            import json
            import re
            
            # Strategy 1: Look for complete JSON blocks
            json_patterns = [
                # Complete JSON with all three fields (most specific)
                r'\{[^{}]*"personalised"[^{}]*"summary"[^{}]*"links"[^{}]*\}',
                # JSON with fields in any order
                r'\{[^{}]*(?:"personalised"|"summary"|"links")[^{}]*(?:"personalised"|"summary"|"links")[^{}]*(?:"personalised"|"summary"|"links")[^{}]*\}',
                # Any valid JSON object
                r'\{(?:[^{}]|{[^{}]*})*\}'
            ]
            
            for pattern in json_patterns:
                json_matches = re.findall(pattern, content, re.DOTALL)
                for json_match in json_matches:
                    try:
                        parsed_json = json.loads(json_match)
                        if isinstance(parsed_json, dict):
                            # Update result with any matching fields
                            if "personalised" in parsed_json:
                                result["personalised"] = str(parsed_json["personalised"])
                            if "summary" in parsed_json:
                                result["summary"] = str(parsed_json["summary"])
                            if "links" in parsed_json:
                                links = parsed_json["links"]
                                if isinstance(links, list):
                                    result["links"] = [str(link) for link in links if link]
                                elif isinstance(links, str) and links:
                                    result["links"] = [links]
                            
                            # If we found a complete response, return it
                            if result["summary"]:
                                return self._sanitize_response(result)
                                
                    except json.JSONDecodeError as e:
                        logger.debug(f"JSON parsing failed for pattern: {str(e)}")
                        continue
            
            # Strategy 2: Try to parse the entire content as JSON
            try:
                parsed_content = json.loads(content)
                if isinstance(parsed_content, dict):
                    return self._extract_fields_from_dict(parsed_content)
            except json.JSONDecodeError:
                pass
            
            # Strategy 2.5: Try to clean and parse content as JSON
            try:
                # Only try this if content is a string
                if isinstance(content, str):
                    # Remove markdown code blocks if present
                    cleaned_content = re.sub(r'```json\s*|\s*```', '', content, flags=re.IGNORECASE)
                    cleaned_content = cleaned_content.strip()
                    
                    parsed_content = json.loads(cleaned_content)
                    if isinstance(parsed_content, dict):
                        return self._extract_fields_from_dict(parsed_content)
            except (json.JSONDecodeError, TypeError):
                pass
            
            # Strategy 3: Extract structured information from plain text
            
            # Look for structured sections in the text
            sections = self._extract_text_sections(content)
            if sections:
                result.update(sections)
            else:
                # Use the entire content as summary if no structure found
                result["summary"] = content.strip()
            
            # Extract URLs from the content for links
            url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
            urls = re.findall(url_pattern, content)
            if urls:
                result["links"] = list(set(urls))  # Remove duplicates
            
            return self._sanitize_response(result)
            
        except Exception as e:
            logger.error(f"Error parsing agent response: {str(e)}")
            return {
                "personalised": "",
                "summary": "An error occurred while processing the response.",
                "links": []
            }
    
    def _extract_fields_from_dict(self, data: dict) -> Dict[str, Any]:
        """Extract required fields from a dictionary response."""
        result = {
            "personalised": "",
            "summary": "",
            "links": []
        }
        
        # Direct field mapping
        if "personalised" in data:
            result["personalised"] = str(data["personalised"])
        if "summary" in data:
            result["summary"] = str(data["summary"])
        if "links" in data:
            links = data["links"]
            if isinstance(links, list):
                result["links"] = [str(link) for link in links if link]
            elif isinstance(links, str) and links:
                result["links"] = [links]
        
        # Alternative field names
        if not result["summary"]:
            for alt_key in ["content", "text", "response", "answer"]:
                if alt_key in data and data[alt_key]:
                    result["summary"] = str(data[alt_key])
                    break
        
        return result
    
    def _extract_text_sections(self, content: str) -> Dict[str, Any]:
        """Extract structured sections from plain text response."""
        result = {
            "personalised": "",
            "summary": "",
            "links": []
        }
        
        # Look for section headers or structured content
        lines = content.split('\n')
        current_section = None
        section_content = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Check for section headers
            lower_line = line.lower()
            if any(keyword in lower_line for keyword in ['personalized', 'personalised', 'personal']):
                if section_content and current_section == 'summary':
                    result['summary'] = '\n'.join(section_content).strip()
                current_section = 'personalised'
                section_content = []
            elif any(keyword in lower_line for keyword in ['summary', 'information', 'details']):
                current_section = 'summary'
                section_content = []
            elif any(keyword in lower_line for keyword in ['links', 'sources', 'references']):
                if section_content and current_section:
                    result[current_section] = '\n'.join(section_content).strip()
                current_section = 'links'
                section_content = []
            else:
                section_content.append(line)
        
        # Add remaining content
        if section_content and current_section:
            if current_section == 'links':
                # Extract URLs from links section
                url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
                urls = []
                for line in section_content:
                    urls.extend(re.findall(url_pattern, line))
                result['links'] = list(set(urls))
            else:
                result[current_section] = '\n'.join(section_content).strip()
        
        # If no structured sections found, use entire content as summary
        if not any(result.values()):
            result['summary'] = content.strip()
        
        return result
    
    def _sanitize_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize and validate response fields."""
        sanitized = {
            "personalised": "",
            "summary": "",
            "links": []
        }
        
        # Sanitize personalised field
        if response.get("personalised"):
            sanitized["personalised"] = str(response["personalised"]).strip()[:2000]
        
        # Sanitize summary field
        if response.get("summary"):
            sanitized["summary"] = str(response["summary"]).strip()[:5000]
        
        # Sanitize links field
        if response.get("links"):
            links = response["links"]
            if isinstance(links, list):
                sanitized["links"] = [str(link).strip() for link in links if link and str(link).strip()][:10]
            elif isinstance(links, str) and links.strip():
                sanitized["links"] = [links.strip()]
        
        return sanitized
    
    def _validate_response_structure(self, response: Dict[str, Any]) -> bool:
        """Validate that response has the correct structure."""
        if not isinstance(response, dict):
            return False
        
        required_fields = ["personalised", "summary", "links"]
        if not all(field in response for field in required_fields):
            return False
        
        if not isinstance(response["personalised"], str):
            return False
        
        if not isinstance(response["summary"], str):
            return False
        
        if not isinstance(response["links"], list):
            return False
        
        return True


# Global agent instance - initialized lazily for better error handling
customer_agent = None


def get_agent() -> CustomerSearchAgent:
    """Get or initialize the global agent instance with proper error handling."""
    global customer_agent
    if customer_agent is None:
        try:
            config = get_config()
            customer_agent = CustomerSearchAgent(config)
            logger.info("Customer Search Agent initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Customer Search Agent: {str(e)}")
            raise
    return customer_agent


@app.entrypoint
async def handler(event: Dict[str, Any]) -> Dict[str, Any]:
    """AgentCore Runtime entrypoint for handling search requests with comprehensive error handling.
    
    This is the main entry point for the Customer Search Agent deployed on AWS AgentCore Runtime.
    It handles request validation, agent initialization, and response formatting.
    
    Args:
        event: Request event containing search_topic and optional user_id
        
    Returns:
        Dict containing search results in standardized JSON format
    """
    # Generate correlation ID for this request
    correlation_id = str(uuid.uuid4())
    
    try:
        # Log incoming request
        logger.info(f"Handler invoked with correlation_id: {correlation_id}")
        logger.debug(f"Event payload: {json.dumps(event, default=str)}")
        
        # Extract and validate parameters from event
        search_topic = event.get("search_topic")
        user_id = event.get("user_id")
        
        # Input validation
        if not search_topic:
            logger.warning("Missing required parameter: search_topic")
            return {
                "error": "search_topic is required",
                "personalised": "",
                "summary": "Please provide a search topic to get information.",
                "links": [],
                "correlation_id": correlation_id
            }
        
        # Validate search_topic format
        if not isinstance(search_topic, str) or len(search_topic.strip()) == 0:
            logger.warning("Invalid search_topic format")
            return {
                "error": "search_topic must be a non-empty string",
                "personalised": "",
                "summary": "Please provide a valid search topic.",
                "links": [],
                "correlation_id": correlation_id
            }
        
        # Validate user_id format if provided
        if user_id is not None and (not isinstance(user_id, str) or len(user_id.strip()) == 0):
            logger.warning("Invalid user_id format")
            user_id = None  # Treat as anonymous user
        
        # Get or initialize the agent
        try:
            agent = get_agent()
        except Exception as e:
            logger.error(f"Agent initialization failed: {str(e)}")
            return {
                "error": "Service initialization error",
                "personalised": "",
                "summary": "The search service is temporarily unavailable. Please try again later.",
                "links": [],
                "correlation_id": correlation_id
            }
        
        # Process the search request
        logger.info(f"Processing search request for topic: {search_topic[:100]}...")
        result = await agent.search(search_topic, user_id)
        
        # Add correlation ID to response for tracing
        result["correlation_id"] = correlation_id
        
        # Log successful completion
        logger.info(f"Search request completed successfully")
        return result
        
    except asyncio.TimeoutError:
        logger.error("Request processing timeout")
        return {
            "error": "Request timeout",
            "personalised": "",
            "summary": "The request took too long to process. Please try again with a more specific search topic.",
            "links": [],
            "correlation_id": correlation_id
        }
        
    except PersonalisationError as e:
        logger.warning(f"Personalization service error: {str(e)}")
        # Continue with basic search functionality
        try:
            agent = get_agent()
            result = await agent._fallback_search(search_topic, correlation_id)
            result["correlation_id"] = correlation_id
            return result
        except Exception as fallback_error:
            logger.error(f"Fallback search failed: {str(fallback_error)}")
            return {
                "error": "Service partially unavailable",
                "personalised": "",
                "summary": "Search service is experiencing issues. Please try again later.",
                "links": [],
                "correlation_id": correlation_id
            }
        
    except Exception as e:
        logger.error(f"Unexpected handler error: {str(e)}")
        return {
            "error": "Internal server error",
            "personalised": "",
            "summary": "An unexpected error occurred while processing your search request. Please try again.",
            "links": [],
            "correlation_id": correlation_id
        }


# Health check endpoint for AgentCore Runtime
@app.route("/health")
async def health_check():
    """Health check endpoint for monitoring and load balancing."""
    try:
        # Basic configuration validation
        config = get_config()
        config_valid = all([
            config.knowledge_base_id,
            config.guardrail_id,
            config.gateway_mcp_url
        ])
        
        if not config_valid:
            return {"status": "unhealthy", "reason": "Invalid configuration"}
        
        # Try to initialize agent if not already done
        try:
            get_agent()
            agent_status = "healthy"
        except Exception as e:
            agent_status = f"initialization_error: {str(e)}"
        
        return {
            "status": "healthy" if agent_status == "healthy" else "degraded",
            "agent": agent_status,
            "configuration": "valid",
            "timestamp": str(uuid.uuid4())
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {"status": "unhealthy", "error": str(e)}


async def create_authenticated_mcp_client(gateway_url: str, token_manager: CognitoTokenManager):
    """
    Create MCP client with Cognito authentication.
    
    Args:
        gateway_url: Gateway MCP endpoint URL
        token_manager: Configured CognitoTokenManager instance
        
    Returns:
        Authenticated MCPClient instance
    """
    
    # Get access token
    access_token = await token_manager.get_access_token()
    
    # Create MCP client with Authorization header
    mcp_client = MCPClient(lambda: streamablehttp_client(
        url=gateway_url,
        headers={"Authorization": f"Bearer {access_token}"}
    ))
    
    return mcp_client


async def test_gateway_connection():
    """Test Gateway MCP connection with Cognito authentication and list available tools for debugging."""
    try:
        config = get_config()
        gateway_url = config.gateway_mcp_url
        
        if not gateway_url:
            logger.error("Gateway MCP URL not configured")
            return
            
        logger.info(f"Testing Gateway connection at: {gateway_url}")
        
        # Check if we have Cognito configuration
        cognito_config = {
            'user_pool_id': getattr(config, 'cognito_user_pool_id', None),
            'client_id': getattr(config, 'cognito_client_id', None),
            'client_secret': getattr(config, 'cognito_client_secret', None),
            'domain': getattr(config, 'cognito_domain', None),
            'region': getattr(config, 'cognito_region', config.aws_region)
        }
        
        # Check if all required Cognito config is present
        missing_config = [k for k, v in cognito_config.items() if not v and k != 'scope']
        if missing_config:
            error_msg = f"Missing required Cognito configuration for Gateway authentication: {missing_config}"
            logger.error(error_msg)
            logger.error("Gateway connection requires authentication. Please configure:")
            for key in missing_config:
                logger.error(f"  {key.upper()}")
            return None
        
        # Create token manager with Cognito configuration
        logger.info("Creating Cognito token manager...")
        try:
            token_manager = CognitoTokenManager(
                user_pool_id=cognito_config['user_pool_id'],
                client_id=cognito_config['client_id'],
                client_secret=cognito_config['client_secret'],
                region=cognito_config['region'],
                domain=cognito_config['domain']
            )
            
            # Create authenticated MCP client
            gateway_mcp_client = await create_authenticated_mcp_client(gateway_url, token_manager)
            logger.info("Authenticated MCP client created successfully")
            
        except CognitoTokenManagerError as e:
            logger.error(f"Cognito authentication failed: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Failed to create authenticated MCP client: {str(e)}")
            return None
            
        # Test MCP session and tool discovery
        try:
            with gateway_mcp_client:
                logger.info("MCP session established with Gateway")
                
                # Discover available tools
                available_tools = gateway_mcp_client.list_tools_sync()
                logger.info(f"Successfully discovered {len(available_tools)} tools from Gateway")
                
                # Log details of each tool
                for i, tool in enumerate(available_tools):
                    tool_name = getattr(tool, 'tool_name', getattr(tool, 'name', 'Unknown'))
                    tool_description = getattr(tool, 'description', 'No description')
                    logger.info(f"Tool {i+1}: {tool_name}")
                    logger.info(f"  Description: {tool_description}")
                    
                    # Log the full tool structure for debugging
                    logger.debug(f"  Full tool data: {tool}")
                
                return available_tools
                
        except Exception as e:
            logger.error(f"MCP session error: {str(e)}")
            if "401" in str(e) or "Unauthorized" in str(e):
                logger.error("Authentication failed - check your Cognito configuration")
            return None
            
    except httpx.ConnectError as e:
        logger.error(f"Gateway connection failed: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error testing Gateway: {str(e)}")
        return None


async def test_personalisation_direct(search_topic: str, user_id: str = None):
    """
    Direct test function for personalisation tool - can be called from main().
    
    Args:
        search_topic: The search query to test
        user_id: Optional user ID for personalization
    """
    try:
        logger.info(f"=== DIRECT PERSONALISATION TEST ===")
        logger.info(f"Search topic: {search_topic}")
        logger.info(f"User ID: {user_id or 'None (anonymous)'}")
        
        # Load configuration
        config = get_config()
        
        # Create a minimal tool context for testing
        class TestToolContext:
            def __init__(self, config):
                self.invocation_state = config.to_dict()
                self.invocation_state["request_id"] = "direct-test-123"
                self.tool_use = {"toolUseId": "test-tool-use-123"}
                
                # Initialize LLM for tool matching
                self.llm = BedrockModel(
                    model_id="anthropic.claude-3-sonnet-20240229-v1:0",
                    temperature=0.1,
                    max_tokens=1000
                )
        
        tool_context = TestToolContext(config)
        
        logger.info("Calling personalisation_tool directly...")
        
        # Import and call the personalisation tool
        from tools.personalisation_tool import personalisation_tool, PersonalisationError
        
        result = await personalisation_tool(
            search_topic=search_topic,
            user_id=user_id or "",
            tool_context=tool_context
        )
        
        logger.info("=== PERSONALISATION TEST COMPLETED ===")
        logger.info(f"Result: {result}")
        
        return result
        
    except PersonalisationError as e:
        logger.error(f"Personalisation tool error: {str(e)}")
        return {"personalised": "", "error": str(e)}
    except Exception as e:
        logger.error(f"Unexpected error in direct test: {str(e)}")
        return {"personalised": "", "error": f"Unexpected error: {str(e)}"}


if __name__ == "__main__":
    """Local development entry point with enhanced logging."""
    import sys
    
    # Check if we want to run a direct test
    if len(sys.argv) > 1 and sys.argv[1] == "test-personalisation":
        if len(sys.argv) < 3:
            print("Usage: python main.py test-personalisation <search_topic> [user_id]")
            print("Example: python main.py test-personalisation 'laptop recommendations' 'user123'")
            sys.exit(1)
        
        search_topic = sys.argv[2]
        user_id = sys.argv[3] if len(sys.argv) > 3 else None
        
        print(f"Running direct personalisation test...")
        result = asyncio.run(test_personalisation_direct(search_topic, user_id))
        print(f"\nFinal result: {result}")
        sys.exit(0)
    
    try:
        logger.info("Starting Customer Search Agent in local development mode")
        
        # Load configuration
        config = get_config()
        logger.info(f"Configuration: Agent={config.agent_name}, Region={config.aws_region}")
        logger.info(f"Knowledge Base ID: {config.knowledge_base_id}")
        logger.info(f"Guardrail ID: {config.guardrail_id}")
        logger.info(f"Gateway URL: {config.gateway_mcp_url}")
        
        # Test Gateway connection before starting the agent
        logger.info("Testing Gateway connection...");
        tools = asyncio.run(test_gateway_connection())
        if tools:
            logger.info("Gateway connection test successful")
        else:
            logger.warning("Gateway connection test failed - continuing anyway")

        # Initialize agent to validate configuration
        get_agent()
        logger.info("Agent initialization successful")
        
        # Start the AgentCore Runtime application
        app.run(port=8080)
        
    except Exception as e:
        logger.error(f"Failed to start application: {str(e)}")
        raise
