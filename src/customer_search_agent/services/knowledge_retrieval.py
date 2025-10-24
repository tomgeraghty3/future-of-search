"""Knowledge retrieval service for AWS Bedrock Knowledge Base integration."""

import logging
import asyncio
from typing import List, Dict, Any
import boto3
from botocore.exceptions import ClientError

try:
    # Try relative imports first (when running as package)
    from ..config import config
    from ..models.data_models import RetrievalResult
except ImportError:
    # Fall back to absolute imports (when running directly)
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config import config
    from models.data_models import RetrievalResult

logger = logging.getLogger(__name__)


class KnowledgeRetrievalService:
    """Service for retrieving information from AWS Bedrock Knowledge Base."""
    
    def __init__(self):
        """Initialize the knowledge retrieval service."""
        self.knowledge_base_id = config.KNOWLEDGE_BASE_ID
        self.aws_region = config.AWS_REGION
        
        # Initialize Bedrock Agent Runtime client
        self.bedrock_agent_runtime = boto3.client(
            'bedrock-agent-runtime',
            region_name=self.aws_region
        )
        
        logger.info(f"KnowledgeRetrievalService initialized with Knowledge Base ID: {self.knowledge_base_id}")
    
    async def retrieve_and_generate(self, query: str) -> RetrievalResult:
        """
        Query knowledge base and generate response using RetrieveAndGenerate API.
        
        Args:
            query: Natural language search query
            
        Returns:
            RetrievalResult containing summary and citations
        """
        if not query or not query.strip():
            logger.warning("Empty query provided to retrieve_and_generate")
            return RetrievalResult(
                summary="No AI summary could be found for the specified query",
                citations=[],
                confidence_score=0.0
            )
        
        query = query.strip()
        logger.info(f"Retrieving information for query: '{query[:100]}{'...' if len(query) > 100 else ''}'")
        
        try:
            # Call RetrieveAndGenerate API
            response = await self._call_retrieve_and_generate_api(query)
            
            # Process the response
            result = self._process_retrieval_response(response)
            
            logger.info("Successfully retrieved information for query")
            return result
                
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            
            logger.error(f"AWS ClientError: {error_code} - {error_message}")
            return RetrievalResult(
                summary="No AI summary could be found for the specified query",
                citations=[],
                confidence_score=0.0
            )
                
        except Exception as e:
            logger.error(f"Unexpected error during knowledge base query: {str(e)}")
            return RetrievalResult(
                summary="No AI summary could be found for the specified query",
                citations=[],
                confidence_score=0.0
            )
    
    async def _call_retrieve_and_generate_api(self, query: str) -> Dict[str, Any]:
        """
        Make the actual API call to Bedrock RetrieveAndGenerate.
        
        Args:
            query: Search query
            
        Returns:
            API response dictionary
        """
        # Prepare the request
        request_params = {
            'input': {
                'text': query
            },
            'retrieveAndGenerateConfiguration': {
                'type': 'KNOWLEDGE_BASE',
                'knowledgeBaseConfiguration': {
                    'knowledgeBaseId': self.knowledge_base_id,
                    'modelArn': f'arn:aws:bedrock:{self.aws_region}::foundation-model/{config.AI_MODEL}',
                    'retrievalConfiguration': {
                        'vectorSearchConfiguration': {
                            'numberOfResults': 10  # Get more results for better citations
                        }
                    }
                }
            }
        }
        
        # Make the API call in a thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.bedrock_agent_runtime.retrieve_and_generate(**request_params)
        )
        
        return response
    
    def _process_retrieval_response(self, response: Dict[str, Any]) -> RetrievalResult:
        """
        Process the API response and extract summary and citations.
        
        Args:
            response: Raw API response
            
        Returns:
            Processed RetrievalResult
        """
        try:
            # Extract the generated output
            output = response.get('output', {})
            generated_text = output.get('text', '').strip()
            
            # Check if we got a meaningful response
            if not generated_text or generated_text.lower() in [
                'no information found',
                'no relevant information',
                'i don\'t have information',
                'no data available'
            ]:
                logger.info("No relevant content found in knowledge base")
                return RetrievalResult(
                    summary="No AI summary could be found for the specified query",
                    citations=[],
                    confidence_score=0.0
                )
            
            # Extract citations from the response
            citations = self._extract_citations(response)
            
            # Calculate confidence score based on number of citations and response length
            confidence_score = self._calculate_confidence_score(generated_text, citations)
            
            # Clean up the generated text
            cleaned_summary = self._clean_summary_text(generated_text)
            
            logger.info(f"Processed retrieval response: {len(cleaned_summary)} chars, {len(citations)} citations")
            
            return RetrievalResult(
                summary=cleaned_summary,
                citations=citations,
                confidence_score=confidence_score
            )
            
        except Exception as e:
            logger.error(f"Error processing retrieval response: {str(e)}")
            return RetrievalResult(
                summary="No AI summary could be found for the specified query",
                citations=[],
                confidence_score=0.0
            )
    
    def _extract_citations(self, response: Dict[str, Any]) -> List[str]:
        """
        Extract and format citations from the API response.
        
        Args:
            response: Raw API response
            
        Returns:
            List of formatted citation URLs
        """
        citations = []
        
        try:
            # Look for citations in the response
            citations_data = response.get('citations', [])
            
            for citation in citations_data:
                # Extract retrieved references
                retrieved_refs = citation.get('retrievedReferences', [])
                
                for ref in retrieved_refs:
                    # Extract location information
                    location = ref.get('location', {})
                    
                    # Try different location types
                    if 's3Location' in location:
                        s3_location = location['s3Location']
                        uri = s3_location.get('uri', '')
                        if uri and uri not in citations:
                            citations.append(uri)
                    
                    elif 'webLocation' in location:
                        web_location = location['webLocation']
                        url = web_location.get('url', '')
                        if url and url not in citations:
                            citations.append(url)
                    
                    elif 'confluenceLocation' in location:
                        confluence_location = location['confluenceLocation']
                        url = confluence_location.get('url', '')
                        if url and url not in citations:
                            citations.append(url)
                    
                    # Also check for content metadata that might contain URLs
                    metadata = ref.get('metadata', {})
                    if isinstance(metadata, dict):
                        for key, value in metadata.items():
                            if key.lower() in ['url', 'uri', 'link', 'source'] and isinstance(value, str):
                                if value.startswith(('http://', 'https://')) and value not in citations:
                                    citations.append(value)
            
            # Remove duplicates while preserving order
            unique_citations = []
            seen = set()
            for citation in citations:
                if citation not in seen:
                    unique_citations.append(citation)
                    seen.add(citation)
            
            logger.info(f"Extracted {len(unique_citations)} unique citations")
            return unique_citations
            
        except Exception as e:
            logger.warning(f"Error extracting citations: {str(e)}")
            return []
    
    def _calculate_confidence_score(self, text: str, citations: List[str]) -> float:
        """
        Calculate a confidence score based on response quality indicators.
        
        Args:
            text: Generated summary text
            citations: List of citations
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        if not text or not text.strip():
            return 0.0
        
        score = 0.0
        
        # Base score for having content
        score += 0.3
        
        # Score based on text length (longer responses generally more informative)
        text_length = len(text.strip())
        if text_length > 100:
            score += 0.2
        if text_length > 300:
            score += 0.1
        
        # Score based on number of citations
        citation_count = len(citations)
        if citation_count > 0:
            score += 0.2
        if citation_count > 2:
            score += 0.1
        if citation_count > 5:
            score += 0.1
        
        # Ensure score is between 0.0 and 1.0
        return min(1.0, max(0.0, score))
    
    def _clean_summary_text(self, text: str) -> str:
        """
        Clean and format the summary text.
        
        Args:
            text: Raw generated text
            
        Returns:
            Cleaned summary text
        """
        if not text:
            return ""
        
        # Remove common unwanted phrases
        unwanted_phrases = [
            "search results",
            "based on the search results",
            "according to the search results",
            "from the search results"
        ]
        
        cleaned = text.strip()
        
        for phrase in unwanted_phrases:
            # Case-insensitive replacement
            import re
            pattern = re.compile(re.escape(phrase), re.IGNORECASE)
            cleaned = pattern.sub("", cleaned)
        
        # Clean up extra whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        # Remove leading/trailing punctuation that might be left over
        cleaned = cleaned.strip('.,;: ')
        
        return cleaned
    
    async def health_check(self) -> bool:
        """
        Perform a health check on the knowledge base service.
        
        Returns:
            True if service is healthy, False otherwise
        """
        try:
            # Try a simple query to check if the service is working
            test_query = "test"
            result = await self.retrieve_and_generate(test_query)
            logger.debug("During test got result: " + str(result))
            
            # Consider it healthy if we get any response (even "no content found")
            return True
            
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return False
