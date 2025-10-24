"""Main entry point for the Customer Search Agent."""

import os
import logging
from typing import Dict, Any, Optional
from bedrock_agentcore import BedrockAgentCoreApp
from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize the Strands Framework app with AgentCore Runtime deployment
app = BedrockAgentCoreApp()


class SearchRequest(BaseModel):
    """Input model for search requests."""
    search_query: str = Field(..., description="Natural language search query")
    user_id: Optional[str] = Field(None, description="User identifier for personalisation")


class SearchResponse(BaseModel):
    """Output model for search responses."""
    personalised: str = Field("", description="User-specific content or empty string")
    summary: str = Field("", description="General summary from knowledge base")
    links: list[str] = Field(default_factory=list, description="Source URLs and citations")


@app.entrypoint
async def invoke(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main entry point for search requests.
    
    Args:
        payload: Dictionary containing search_query and optional user_id
    
    Returns:
        Dictionary with personalised, summary, and links fields
    """
    try:
        # Validate input
        request = SearchRequest(**payload)
        logger.info(f"Processing search query: {request.search_query[:100]}...")
        
        # TODO: Implement knowledge retrieval, personalisation, and safety services
        # This is a placeholder response for the initial setup
        response = SearchResponse(
            personalised="",
            summary="Service initialization complete. Full implementation pending.",
            links=[]
        )
        
        logger.info("Search request processed successfully")
        return response.model_dump()
        
    except Exception as e:
        logger.error(f"Error processing search request: {str(e)}")
        # Return error response in expected format
        return {
            "personalised": "",
            "summary": "An error occurred while processing your request. Please try again.",
            "links": []
        }


if __name__ == "__main__":
    # For local testing
    import asyncio
    
    async def test_local():
        test_payload = {
            "search_query": "What are the benefits of cloud computing?",
            "user_id": "test-user-123"
        }
        result = await invoke(test_payload)
        print(f"Response: {result}")
    
    asyncio.run(test_local())