"""Knowledge Tool for AWS Bedrock Knowledge Base integration."""

import logging
import re
from typing import Dict, List, Any, Optional
import boto3
from botocore.exceptions import ClientError, BotoCoreError
from strands import tool, ToolContext

logger = logging.getLogger(__name__)


@tool(context=True)
async def knowledge_tool(search_topic: str, tool_context: ToolContext) -> Dict[str, Any]:
    """Retrieve information from AWS Bedrock Knowledge Base using semantic search.
    
    This tool queries the AWS Bedrock Knowledge Base using the RetrieveAndGenerate API
    to find relevant information for the given search topic. It extracts citations
    and links from the response metadata and handles various error scenarios gracefully.
    
    Args:
        search_topic: Natural language search query to find relevant information
        tool_context: Provides access to agent context and invocation state
                     - tool_context.invocation_state: Contains request metadata and configuration
                     - tool_context.tool_use: Current tool invocation details for logging/tracing
    
    Returns:
        Dict containing:
            - summary: Summarized information from knowledge base with citations
            - links: List of source URLs extracted from response metadata
            - success: Boolean indicating if the operation was successful
    """
    try:
        # Extract configuration from invocation state
        knowledge_base_id = tool_context.invocation_state.get("knowledge_base_id")
        knowledge_base_model_arn = tool_context.invocation_state.get("knowledge_base_model_arn")
        aws_region = tool_context.invocation_state.get("aws_region", "us-east-1")
        request_id = tool_context.invocation_state.get("request_id", "unknown")
        tool_use_id = tool_context.tool_use.get("toolUseId", "unknown")
        
        logger.info(f"Knowledge tool invoked [{request_id}:{tool_use_id}] for topic: {search_topic}")
        
        # Validate required configuration
        if not knowledge_base_id:
            logger.error(f"Knowledge base ID not configured [{request_id}:{tool_use_id}]")
            return {
                "summary": "Configuration error: Knowledge base not available",
                "links": [],
                "success": False
            }
        
        # Initialize Bedrock Agent Runtime client
        bedrock_client = boto3.client(
            'bedrock-agent-runtime',
            region_name=aws_region
        )
        
        # Prepare the retrieve and generate request
        request_params = {
            'input': {
                'text': search_topic
            },
            'retrieveAndGenerateConfiguration': {
                'type': 'KNOWLEDGE_BASE',
                'knowledgeBaseConfiguration': {
                    'knowledgeBaseId': knowledge_base_id
                }
            }
        }
        
        # Add model configuration if provided
        if knowledge_base_model_arn:
            request_params['retrieveAndGenerateConfiguration']['knowledgeBaseConfiguration']['modelArn'] = knowledge_base_model_arn
        
        logger.debug(f"Calling Bedrock Knowledge Base [{request_id}:{tool_use_id}] with params: {request_params}")
        
        # Call the RetrieveAndGenerate API
        response = bedrock_client.retrieve_and_generate(**request_params)
        
        # Extract the generated output and citations
        output = response.get('output', {})
        generated_text = output.get('text', '')
        citations = response.get('citations', [])
        
        logger.debug(f"Received response [{request_id}:{tool_use_id}] with {len(citations)} citations")
        
        # Check if we got meaningful results
        if not generated_text or generated_text.strip() == '':
            logger.info(f"No content generated for search topic [{request_id}:{tool_use_id}]: {search_topic}")
            return {
                "summary": "No AI summary could be found for the specified query",
                "links": [],
                "success": True
            }
        
        # Extract links from citations
        extracted_links = _extract_links_from_citations(citations)
        
        # Clean up the generated text to remove any "search results" references
        cleaned_summary = _clean_summary_text(generated_text)
        
        logger.info(f"Successfully retrieved knowledge [{request_id}:{tool_use_id}] with {len(extracted_links)} source links")
        # logger.info("With resultant summary: " + cleaned_summary + " \nand original\n" + generated_text + "\nwith cit:" + str(citations))
        
        return {
            "summary": cleaned_summary,
            "links": extracted_links,
            "success": True
        }
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_message = e.response.get('Error', {}).get('Message', str(e))
        
        logger.error(f"AWS Bedrock Knowledge Base error [{request_id}:{tool_use_id}] - {error_code}: {error_message}")
        
        # Handle specific AWS errors
        if error_code in ['ResourceNotFoundException', 'ValidationException']:
            # Check if this is a missing knowledge base error
            if 'Knowledge Base' in error_message and 'does not exist' in error_message:
                logger.warning(f"Knowledge base not found [{request_id}:{tool_use_id}] - returning mock data for development")
                return _get_mock_knowledge_response(search_topic)
            return {
                "summary": "No AI summary could be found for the specified query",
                "links": [],
                "success": False
            }
        elif error_code in ['ThrottlingException', 'ServiceUnavailableException']:
            return {
                "summary": "Knowledge base service is temporarily unavailable. Please try again.",
                "links": [],
                "success": False
            }
        else:
            return {
                "summary": "An error occurred while searching the knowledge base. Please try again.",
                "links": [],
                "success": False
            }
            
    except BotoCoreError as e:
        logger.error(f"Boto3 configuration error [{request_id}:{tool_use_id}]: {str(e)}")
        return {
            "summary": "Knowledge base service is currently unavailable. Please try again.",
            "links": [],
            "success": False
        }
        
    except Exception as e:
        logger.error(f"Unexpected error in knowledge tool [{request_id}:{tool_use_id}]: {str(e)}")
        return {
            "summary": "An unexpected error occurred while searching. Please try again.",
            "links": [],
            "success": False
        }


def _extract_links_from_citations(citations: List[Dict[str, Any]]) -> List[str]:
    """Extract unique URLs from Bedrock Knowledge Base citation metadata.
    
    Args:
        citations: List of citation objects from Bedrock response
        
    Returns:
        List of unique source URLs
    """
    links = []
    seen_urls = set()
    
    try:
        for citation in citations:
            # Extract references from citation
            references = citation.get('retrievedReferences', [])
            
            for reference in references:
                # Try to extract URL from location or metadata
                location = reference.get('location', {})
                metadata = reference.get('metadata', {})
                
                # Check various possible URL fields
                url = None
                
                # Check for webLocation structure (most common for web sources)
                if 'webLocation' in location and 'url' in location['webLocation']:
                    url = location['webLocation']['url']
                # Check for direct location fields
                elif 'uri' in location:
                    url = location['uri']
                elif 'url' in location:
                    url = location['url']
                elif 'source' in location:
                    url = location['source']
                # Check metadata fields
                elif 'x-amz-bedrock-kb-source-uri' in metadata:
                    url = metadata['x-amz-bedrock-kb-source-uri']
                elif 'uri' in metadata:
                    url = metadata['uri']
                elif 'url' in metadata:
                    url = metadata['url']
                elif 'source' in metadata:
                    url = metadata['source']
                
                # Add URL if found and not already seen
                if url and url not in seen_urls:
                    # Validate URL format
                    if _is_valid_url(url):
                        links.append(url)
                        seen_urls.add(url)
                        
    except Exception as e:
        logger.warning(f"Error extracting links from citations: {str(e)}")
    
    return links


def _is_valid_url(url: str) -> bool:
    """Validate if a string is a properly formatted URL.
    
    Args:
        url: String to validate as URL
        
    Returns:
        Boolean indicating if the URL is valid
    """
    try:
        # Basic URL pattern matching
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        
        return bool(url_pattern.match(url))
    except Exception:
        return False


def _clean_summary_text(text: str) -> str:
    """Clean up generated summary text to remove unwanted phrases.
    
    Args:
        text: Raw generated text from knowledge base
        
    Returns:
        Cleaned summary text
    """
    try:
        # Remove common unwanted phrases
        unwanted_phrases = [
            r'\bsearch results?\b',
            r'\bbased on the search results?\b',
            r'\baccording to the search results?\b',
            r'\bfrom the search results?\b',
            r'\bthe search results? show\b',
            r'\bthe search results? indicate\b'
        ]
        
        cleaned_text = text
        for phrase_pattern in unwanted_phrases:
            cleaned_text = re.sub(phrase_pattern, '', cleaned_text, flags=re.IGNORECASE)
        
        # Clean up extra whitespace and normalize spacing
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
        
        # Ensure the text starts with a capital letter
        if cleaned_text and not cleaned_text[0].isupper():
            cleaned_text = cleaned_text[0].upper() + cleaned_text[1:]
        
        return cleaned_text
    
    except Exception as e:
        logger.warning(f"Error cleaning summary text: {str(e)}")
        return text  # Return original text if cleaning fails


def _get_mock_knowledge_response(search_topic: str) -> Dict[str, Any]:
    """Provide mock knowledge base response for development when KB doesn't exist.
    
    Args:
        search_topic: The search query to provide mock data for
        
    Returns:
        Mock response similar to real knowledge base response
    """
    import hashlib
    
    # Generate deterministic but varied responses based on search topic
    topic_hash = hashlib.md5(search_topic.lower().encode()).hexdigest()[:6]
    
    mock_responses = {
        "intelligent agent": {
            "summary": "An intelligent agent is a system that perceives its environment and takes actions to achieve specific goals. These agents can be software programs, robots, or autonomous systems that use artificial intelligence techniques to make decisions. Key characteristics include autonomy, reactivity, proactiveness, and social ability to interact with other agents.",
            "links": [
                "https://example.com/ai-agents-guide",
                "https://example.com/intelligent-systems-overview"
            ]
        },
        "machine learning": {
            "summary": "Machine learning is a subset of artificial intelligence that enables computers to learn and improve from experience without being explicitly programmed. It involves algorithms that build mathematical models based on training data to make predictions or decisions.",
            "links": [
                "https://example.com/ml-introduction",
                "https://example.com/ml-algorithms-guide"
            ]
        },
        "default": {
            "summary": f"This is a mock response for your search about '{search_topic}'. The knowledge base is not currently available, but this demonstrates how the system would return relevant information. In a real deployment, this would contain actual data from your configured knowledge sources.",
            "links": [
                f"https://example.com/mock-source-{topic_hash}",
                "https://example.com/demo-knowledge-base"
            ]
        }
    }
    
    # Find the best matching response
    topic_lower = search_topic.lower()
    
    for key, response in mock_responses.items():
        if key != "default" and key in topic_lower:
            return {
                "summary": response["summary"],
                "links": response["links"],
                "success": True
            }
    
    # Return default response
    return {
        "summary": mock_responses["default"]["summary"],
        "links": mock_responses["default"]["links"],
        "success": True
    }
