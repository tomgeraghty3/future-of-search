"""Main entry point for Customer Search Agent on AWS AgentCore Runtime."""

import logging
import uuid
from typing import Dict, Any, Optional

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from strands.models import BedrockModel

from config import Config


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
        system_prompt = """You are a customer search agent that helps users find information.

You have access to three tools:
1. knowledge_tool: Search the company knowledge base for general information
2. personalisation_tool: Get personalized information for logged-in users (requires user_id)
3. guardrails_tool: Validate content for safety and coherence

Your goal is to provide helpful search results in this exact JSON format:
{
    "personalised": "User-specific information or empty string if not available",
    "summary": "General information summary with citations", 
    "links": ["list", "of", "source", "urls"]
}

Guidelines:
- Always search the knowledge base for general information
- Only use personalization if user_id is provided
- Always validate your final response with guardrails
- If no knowledge base results exist, return "No AI summary could be found for the specified query"
- Never fabricate facts, policies, or prices
- Always cite your sources"""

        # Configure Claude 3.7 Sonnet model
        model_config = BedrockModel(
            model_id="anthropic.claude-3-sonnet-20240229-v1:0",
            region=self.config.aws_region
        )
        
        # Tools will be imported and configured in subsequent tasks
        tools = []  # Will be populated when tools are implemented
        
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
            
            # Construct prompt for the agent
            prompt = f"""A {user_context} is searching for: "{search_topic}"

Please help them by:
1. Searching for relevant information in the knowledge base
2. Getting personalized information if they are logged in
3. Ensuring the response is safe and appropriate
4. Returning the results in the required JSON format"""

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
            response: Raw agent response
            
        Returns:
            Dict with personalised, summary, and links fields
        """
        # This will be implemented when tools are available
        # For now, return a basic structure
        return {
            "personalised": "",
            "summary": "Agent response parsing will be implemented with tools",
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