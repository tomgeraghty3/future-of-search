"""Main entry point for Customer Search Agent on AWS AgentCore Runtime."""

import logging
import uuid
from typing import Dict, Any, Optional

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from strands.models import BedrockModel

from config import Config
from tools.knowledge_tool import knowledge_tool
from tools.personalisation_tool import personalisation_tool
from tools.guardrails_tool import guardrails_tool


# Initialize the AgentCore Runtime application
app = BedrockAgentCoreApp()

# Global configuration instance
config = Config()

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CustomerSearchAgent:
    """Customer Search Agent implementation."""
    
    def __init__(self, config: Config):
        """Initialize the Customer Search Agent.
        
        Args:
            config: Configuration instance containing environment variables
        """
        self.config = config
        self.agent = None
        self._initialize_agent()
    
    def _initialize_agent(self):
        """Initialize the Strands Agent with system prompt and tools."""
        # System prompt defining agent role and capabilities
        system_prompt = """You are an intelligent customer search agent that uses reasoning to help users find information. You have the ability to think through each request and decide the best approach to fulfill it.

You have access to three tools that you can use strategically:
1. knowledge_tool: Search the company knowledge base for general information
2. personalisation_tool: Get personalized information for logged-in users (requires user_id)
3. guardrails_tool: Validate content for safety and coherence

Your reasoning process should be:
1. Analyze the user's search request and determine what information they need
2. Decide which tools to use based on the context (anonymous vs logged-in user)
3. Use the knowledge_tool to get general information about the topic
4. If a user_id is provided, use personalisation_tool to get user-specific information
5. Compose a comprehensive response combining the information
6. Use guardrails_tool to validate your final response before returning it
7. Format the final response as JSON

Your final response must be in this exact JSON format:
{
    "personalised": "User-specific information or empty string if not available",
    "summary": "General information summary with citations", 
    "links": ["list", "of", "source", "urls"]
}

Important guidelines:
- Think through each request and adapt your approach based on the user's needs
- Always search the knowledge base for general information first
- Only attempt personalization if user_id is provided
- Always validate your final composed response with guardrails before returning
- If no knowledge base results exist, return "No AI summary could be found for the specified query"
- Never fabricate facts, policies, or prices - only use information from your tools
- Always include source citations and links when available
- Be helpful and comprehensive while staying accurate and safe"""

        # Configure Claude 3.7 Sonnet model
        model_config = BedrockModel(
            model_id="anthropic.claude-3-sonnet-20240229-v1:0",
            region=self.config.aws_region
        )
        
        # Configure available tools
        tools = [knowledge_tool, personalisation_tool, guardrails_tool]
        
        # Create the agent
        self.agent = Agent(
            model=model_config,
            tools=tools,
            name=self.config.agent_name,
            system_prompt=system_prompt
        )
        
        logger.info(f"Initialized Customer Search Agent: {self.config.agent_name}")
    
    async def search(self, search_topic: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Process search request and return structured response.
        
        Args:
            search_topic: Natural language search query
            user_id: Optional user identifier for personalization
            
        Returns:
            Dict containing personalised, summary, and links fields
        """
        try:
            # Generate correlation ID for request tracing
            request_id = str(uuid.uuid4())
            
            # Log the incoming request
            user_context = f"logged-in user {user_id}" if user_id else "anonymous visitor"
            logger.info(f"Processing search request [{request_id}] from {user_context}: {search_topic}")
            
            # Create invocation state with configuration for tools
            invocation_state = {
                **self.config.to_dict(),
                "user_id": user_id,
                "request_id": request_id
            }
            
            # Construct prompt for the agent with reasoning context
            prompt = f"""A {user_context} is searching for: "{search_topic}"

Please analyze this request and use your reasoning to provide the best possible response:

1. First, think about what information this user needs for their search topic
2. Use the knowledge_tool to search for general information about "{search_topic}"
3. {"If you find relevant information, also use the personalisation_tool to get user-specific details for user_id: " + user_id if user_id else "Since this is an anonymous user, skip personalization"}
4. Compose a comprehensive response combining all the information you gathered
5. Use the guardrails_tool to validate your composed response for safety and coherence
6. Return the final validated response in the required JSON format

Remember to think through each step and adapt your approach based on what you learn from each tool."""

            # Let the agent reason about how to fulfill the request
            response = await self.agent.invoke_async(
                prompt,
                **invocation_state
            )
            
            # Parse and return the agent response
            result = self._parse_agent_response(response)
            logger.info(f"Successfully processed search request [{request_id}]")
            return result
            
        except Exception as e:
            logger.error(f"Error processing search request [{request_id}]: {str(e)}")
            return {
                "personalised": "",
                "summary": "An error occurred while processing your search request. Please try again.",
                "links": []
            }
    
    def _parse_agent_response(self, response) -> Dict[str, Any]:
        """Parse agent response into structured format.
        
        Args:
            response: Raw agent response from Strands Agent
            
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
            elif isinstance(response, str):
                content = response
            elif isinstance(response, dict):
                # If response is already a dict, try to use it directly
                if all(key in response for key in ["personalised", "summary", "links"]):
                    return response
                content = response.get('content') or response.get('text') or str(response)
            
            if not content:
                logger.warning("No content found in agent response")
                return result
            
            # Try to extract JSON from the response content
            import json
            import re
            
            # Look for JSON structure with our required fields
            # More flexible pattern to handle various JSON formatting
            json_patterns = [
                # Complete JSON with all three fields
                r'\{[^{}]*"personalised"[^{}]*"summary"[^{}]*"links"[^{}]*\}',
                # JSON that might have the fields in different order
                r'\{[^{}]*(?:"personalised"|"summary"|"links")[^{}]*(?:"personalised"|"summary"|"links")[^{}]*(?:"personalised"|"summary"|"links")[^{}]*\}',
                # Any JSON-like structure
                r'\{[^{}]*"[^"]*"[^{}]*:[^{}]*\}'
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
                                    result["links"] = [str(link) for link in links]
                                elif isinstance(links, str):
                                    # Handle case where links might be a string
                                    result["links"] = [links] if links else []
                            
                            # If we found a complete response, return it
                            if result["summary"]:  # At minimum we need a summary
                                return result
                                
                    except json.JSONDecodeError:
                        continue
            
            # If no valid JSON found, try to extract information from plain text
            logger.info("No valid JSON found, parsing as plain text response")
            
            # Use the entire content as summary if no JSON structure found
            result["summary"] = content.strip()
            
            # Try to extract any URLs from the content for links
            url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
            urls = re.findall(url_pattern, content)
            if urls:
                result["links"] = list(set(urls))  # Remove duplicates
            
            return result
            
        except Exception as e:
            logger.error(f"Error parsing agent response: {str(e)}")
            return {
                "personalised": "",
                "summary": "An error occurred while processing the response.",
                "links": []
            }


# Initialize global agent instance
customer_agent = CustomerSearchAgent(config)


@app.entrypoint
async def handler(event: Dict[str, Any]) -> Dict[str, Any]:
    """AgentCore Runtime entrypoint for handling search requests.
    
    Args:
        event: Request event containing search_topic and optional user_id
        
    Returns:
        Dict containing search results in JSON format
    """
    try:
        # Extract parameters from event
        search_topic = event.get("search_topic")
        user_id = event.get("user_id")
        
        # Validate required parameters
        if not search_topic:
            return {
                "error": "search_topic is required",
                "personalised": "",
                "summary": "",
                "links": []
            }
        
        # Process the search request
        result = await customer_agent.search(search_topic, user_id)
        return result
        
    except Exception as e:
        logger.error(f"Handler error: {str(e)}")
        return {
            "error": "Internal server error",
            "personalised": "",
            "summary": "An unexpected error occurred. Please try again.",
            "links": []
        }


if __name__ == "__main__":
    """Local development entry point."""
    logger.info("Starting Customer Search Agent in local development mode")
    app.run()