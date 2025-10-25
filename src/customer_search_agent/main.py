"""Main entry point for the Customer Search Agent."""

import os
import logging
import traceback
from typing import Dict, Any
from bedrock_agentcore import BedrockAgentCoreApp
from pydantic import ValidationError

try:
    # Try relative imports first (when running as package)
    from .config import config
    from .models.data_models import SearchRequest, SearchResponse
    from .services.knowledge_retrieval import KnowledgeRetrievalService
    from .services.personalisation import PersonalisationService
except ImportError:
    # Fall back to absolute imports (when running directly)
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from config import config
    from models.data_models import SearchRequest, SearchResponse
    from services.knowledge_retrieval import KnowledgeRetrievalService
    from services.personalisation import PersonalisationService

# Configure comprehensive logging
def setup_logging():
    """Set up logging configuration with proper formatting and levels."""
    log_level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    return logging.getLogger(__name__)

# Initialize logging
logger = setup_logging()

# Initialize the Strands Framework app with AgentCore Runtime deployment
app = BedrockAgentCoreApp()

# Initialize services
knowledge_service = None
personalisation_service = None

# Log startup information
logger.info("Customer Search Agent initializing...")
logger.info(f"AI Model: {config.AI_MODEL}")
logger.info(f"AWS Region: {config.AWS_REGION}")
logger.info(f"Log Level: {config.LOG_LEVEL}")


def get_knowledge_service() -> KnowledgeRetrievalService:
    """Get or create the knowledge retrieval service instance."""
    global knowledge_service
    if knowledge_service is None:
        knowledge_service = KnowledgeRetrievalService()
    return knowledge_service


def get_personalisation_service() -> PersonalisationService:
    """Get or create the personalisation service instance."""
    global personalisation_service
    if personalisation_service is None:
        personalisation_service = PersonalisationService()
    return personalisation_service


def validate_search_query(query: str) -> str:
    """
    Validate and sanitize search query input.
    
    Args:
        query: Raw search query string
        
    Returns:
        Sanitized search query
        
    Raises:
        ValueError: If query is invalid
    """
    if not query or not isinstance(query, str):
        raise ValueError("Search query must be a non-empty string")
    
    # Strip whitespace and check length
    query = query.strip()
    if len(query) == 0:
        raise ValueError("Search query cannot be empty")
    
    if len(query) > 1000:  # Reasonable limit for search queries
        raise ValueError("Search query too long (maximum 1000 characters)")
    
    # Basic sanitization - remove control characters
    sanitized = ''.join(char for char in query if ord(char) >= 32 or char in '\t\n\r')
    
    return sanitized


def validate_user_id(user_id: str) -> str:
    """
    Validate user ID format.
    
    Args:
        user_id: User identifier string
        
    Returns:
        Validated user ID
        
    Raises:
        ValueError: If user ID format is invalid
    """
    if not isinstance(user_id, str):
        raise ValueError("User ID must be a string")
    
    user_id = user_id.strip()
    if len(user_id) == 0:
        raise ValueError("User ID cannot be empty")
    
    if len(user_id) > 255:  # Reasonable limit for user IDs
        raise ValueError("User ID too long (maximum 255 characters)")
    
    # Basic format validation - alphanumeric, hyphens, underscores
    if not all(c.isalnum() or c in '-_' for c in user_id):
        raise ValueError("User ID contains invalid characters (only alphanumeric, hyphens, and underscores allowed)")
    
    return user_id


@app.entrypoint
async def invoke(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main entry point for search requests.
    
    Processes search queries for both authenticated and anonymous users,
    returning structured JSON responses with summary, personalisation, and citations.
    
    Args:
        payload: Dictionary containing:
            - search_query (str): Natural language search query
            - user_id (str, optional): User identifier for personalisation
    
    Returns:
        Dictionary with three fields:
            - personalised (str): User-specific content or empty string
            - summary (str): General summary from knowledge base
            - links (List[str]): Source URLs and citations
    """
    request_id = id(payload)  # Simple request tracking
    logger.info(f"[{request_id}] Received search request")
    
    try:
        # Validate configuration on first request
        try:
            config.validate_required_config()
        except ValueError as config_error:
            logger.error(f"[{request_id}] Configuration validation failed: {config_error}")
            return _create_error_response("Service configuration error. Please contact support.")
        
        # Validate and parse input payload
        try:
            request = SearchRequest(**payload)
        except ValidationError as validation_error:
            logger.warning(f"[{request_id}] Input validation failed: {validation_error}")
            return _create_error_response("Invalid request format. Please check your input parameters.")
        except Exception as parse_error:
            logger.error(f"[{request_id}] Unexpected parsing error: {parse_error}")
            return _create_error_response("Request parsing failed. Please try again.")
        
        # Additional input validation and sanitization
        try:
            sanitized_query = validate_search_query(request.search_query)
            validated_user_id = None
            
            if request.user_id:
                validated_user_id = validate_user_id(request.user_id)
                logger.info(f"[{request_id}] Processing authenticated request for user: {validated_user_id}")
            else:
                logger.info(f"[{request_id}] Processing anonymous request")
            
            logger.info(f"[{request_id}] Search query: '{sanitized_query[:100]}{'...' if len(sanitized_query) > 100 else ''}'")
            
        except ValueError as validation_error:
            logger.warning(f"[{request_id}] Input validation failed: {validation_error}")
            return _create_error_response(f"Invalid input: {str(validation_error)}")
        
        # Initialize services
        knowledge_svc = get_knowledge_service()
        personalisation_svc = get_personalisation_service()
        
        # Retrieve information from knowledge base
        logger.info(f"[{request_id}] Querying knowledge base...")
        try:
            retrieval_result = await knowledge_svc.retrieve_and_generate(sanitized_query)
            logger.info(f"[{request_id}] Knowledge base query completed - confidence: {retrieval_result.confidence_score:.2f}")
        except Exception as kb_error:
            logger.error(f"[{request_id}] Knowledge base query failed: {str(kb_error)}")
            retrieval_result = None
        
        # Get personalised content if user is authenticated
        personalised_content = ""
        if validated_user_id:
            logger.info(f"[{request_id}] Getting personalised content for user: {validated_user_id}")
            try:
                personalisation_result = await personalisation_svc.get_personalised_content(
                    validated_user_id, 
                    sanitized_query
                )
                if personalisation_result.success and personalisation_result.content:
                    personalised_content = personalisation_result.content
                    logger.info(f"[{request_id}] Personalisation successful using tool: {personalisation_result.tool_used}")
                else:
                    logger.info(f"[{request_id}] No personalised content available for user")
            except Exception as personalisation_error:
                logger.warning(f"[{request_id}] Personalisation failed, continuing with general response: {str(personalisation_error)}")
        
        # TODO: Implement safety services (Bedrock Guardrails)
        
        # Assemble response
        if retrieval_result and retrieval_result.summary:
            summary = retrieval_result.summary
            links = retrieval_result.citations
        else:
            summary = "No AI summary could be found for the specified query"
            links = []
        
        response = SearchResponse(
            personalised=personalised_content,
            summary=summary,
            links=links
        )
        
        logger.info(f"[{request_id}] Search request processed successfully")
        return response.model_dump()
        
    except Exception as e:
        # Log full error details for debugging
        logger.error(f"[{request_id}] Unexpected error processing search request: {str(e)}")
        logger.error(f"[{request_id}] Error traceback: {traceback.format_exc()}")
        
        # Return user-friendly error response
        return _create_error_response("An unexpected error occurred while processing your request. Please try again.")


def _create_error_response(error_message: str) -> Dict[str, Any]:
    """
    Create a standardized error response in the expected JSON format.
    
    Args:
        error_message: User-friendly error message
        
    Returns:
        Dictionary with error response in standard format
    """
    return {
        "personalised": "",
        "summary": error_message,
        "links": []
    }


if __name__ == "__main__":
    # For local testing and validation
    import asyncio
    
    async def test_local():
        """Test the agent entry point with various scenarios."""
        logger.info("Starting local testing...")
        
        # Test cases for validation
        test_cases = [
            {
                "name": "Valid authenticated request",
                "payload": {
                    "search_query": "What are the benefits of cloud computing?",
                    "user_id": "test-user-123"
                }
            },
            {
                "name": "Valid anonymous request",
                "payload": {
                    "search_query": "How does machine learning work?"
                }
            },
            {
                "name": "Invalid empty query",
                "payload": {
                    "search_query": "",
                    "user_id": "test-user"
                }
            },
            {
                "name": "Invalid missing query",
                "payload": {
                    "user_id": "test-user"
                }
            },
            {
                "name": "Invalid user ID format",
                "payload": {
                    "search_query": "test query",
                    "user_id": "invalid@user#id"
                }
            }
        ]
        
        for test_case in test_cases:
            print(f"\n--- Testing: {test_case['name']} ---")
            try:
                result = await invoke(test_case['payload'])
                print(f"Success: {result}")
            except Exception as e:
                print(f"Error: {e}")
        
        logger.info("Local testing completed")
    
    # Only run if environment variables are set or in development mode
    try:
        asyncio.run(test_local())
    except Exception as e:
        print(f"Local testing failed: {e}")
        print("Note: This is expected if required environment variables are not set")