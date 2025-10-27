#!/usr/bin/env python3
"""
Direct test script for the knowledge base functionality.
This will help us debug why searches aren't finding information.
"""

import asyncio
import logging
import boto3
import json
from dotenv import load_dotenv
from config import Config
from tools.knowledge_tool import knowledge_tool
from strands import ToolContext

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class MockToolContext:
    """Mock ToolContext for testing the knowledge tool."""
    
    def __init__(self, config: Config):
        self.config = config
        self.invocation_state = config.to_dict()
        self.tool_use = {"toolUseId": "test-tool-use-123"}


async def test_bedrock_knowledge_base_directly():
    """Test the Bedrock Knowledge Base directly with boto3."""
    config = Config()
    
    print("Testing Bedrock Knowledge Base directly...")
    print(f"Knowledge Base ID: {config.knowledge_base_id}")
    print(f"AWS Region: {config.aws_region}")
    
    # Initialize Bedrock Agent Runtime client
    bedrock_client = boto3.client(
        'bedrock-agent-runtime',
        region_name=config.aws_region
    )
    
    # Test queries
    test_queries = [
        "Scottish Power energy tariffs",
        "electricity bills",
        "customer service",
        "renewable energy",
        "smart meters",
        "How do I pay my bill?",
        "What are your opening hours?",
        "Energy efficiency tips"
    ]
    
    for query in test_queries:
        print(f"\n{'='*50}")
        print(f"Testing query: '{query}'")
        print(f"{'='*50}")
        
        try:
            # Prepare the retrieve and generate request
            request_params = {
                'input': {
                    'text': query
                },
                'retrieveAndGenerateConfiguration': {
                    'type': 'KNOWLEDGE_BASE',
                    'knowledgeBaseConfiguration': {
                        'knowledgeBaseId': config.knowledge_base_id
                    }
                }
            }
            
            # Add model configuration if provided
            if config.knowledge_base_model_arn:
                request_params['retrieveAndGenerateConfiguration']['knowledgeBaseConfiguration']['modelArn'] = config.knowledge_base_model_arn
            
            print(f"Request params: {json.dumps(request_params, indent=2)}")
            
            # Call the RetrieveAndGenerate API
            response = bedrock_client.retrieve_and_generate(**request_params)
            
            # Extract the generated output and citations
            output = response.get('output', {})
            generated_text = output.get('text', '')
            citations = response.get('citations', [])
            
            print(f"\nGenerated text: {generated_text}")
            print(f"Number of citations: {len(citations)}")
            
            if citations:
                print("\nCitations:")
                for i, citation in enumerate(citations):
                    print(f"  Citation {i+1}:")
                    print(f"    {json.dumps(citation, indent=4)}")
            else:
                print("\nNo citations found")
            
            # Check if we got meaningful results
            if not generated_text or generated_text.strip() == '':
                print("❌ No content generated!")
            else:
                print("✅ Content generated successfully")
                
        except Exception as e:
            print(f"❌ Error testing query '{query}': {str(e)}")
            import traceback
            traceback.print_exc()


async def test_knowledge_tool():
    """Test the knowledge tool wrapper."""
    config = Config()
    tool_context = MockToolContext(config)
    
    print("\n" + "="*60)
    print("Testing knowledge_tool wrapper...")
    print("="*60)
    
    test_queries = [
        "Scottish Power energy tariffs",
        "How do I pay my bill?",
        "customer service hours",
        "renewable energy options"
    ]
    
    for query in test_queries:
        print(f"\nTesting query: '{query}'")
        print("-" * 40)
        
        try:
            result = await knowledge_tool(query, tool_context)
            print(f"Result: {json.dumps(result, indent=2)}")
            
            if result.get('success'):
                print("✅ Knowledge tool returned success")
            else:
                print("❌ Knowledge tool returned failure")
                
        except Exception as e:
            print(f"❌ Error in knowledge tool: {str(e)}")
            import traceback
            traceback.print_exc()


async def check_knowledge_base_configuration():
    """Check knowledge base configuration and contents."""
    config = Config()
    
    print("\n" + "="*60)
    print("Checking Knowledge Base Configuration...")
    print("="*60)
    
    try:
        # Check if we can list knowledge bases
        bedrock_agent = boto3.client(
            'bedrock-agent',
            region_name=config.aws_region
        )
        
        response = bedrock_agent.list_knowledge_bases()
        knowledge_bases = response.get('knowledgeBaseSummaries', [])
        
        print(f"Found {len(knowledge_bases)} knowledge bases:")
        for kb in knowledge_bases:
            print(f"  - ID: {kb['knowledgeBaseId']}")
            print(f"    Name: {kb['name']}")
            print(f"    Status: {kb['status']}")
            
            # Get more details about our specific knowledge base
            if kb['knowledgeBaseId'] == config.knowledge_base_id:
                print(f"    ✅ This is our configured knowledge base")
                
                # Get detailed information
                try:
                    details = bedrock_agent.get_knowledge_base(knowledgeBaseId=kb['knowledgeBaseId'])
                    kb_details = details.get('knowledgeBase', {})
                    
                    print(f"    Description: {kb_details.get('description', 'N/A')}")
                    print(f"    Created: {kb_details.get('createdAt', 'N/A')}")
                    print(f"    Updated: {kb_details.get('updatedAt', 'N/A')}")
                    
                    # Check data sources
                    data_sources = bedrock_agent.list_data_sources(knowledgeBaseId=kb['knowledgeBaseId'])
                    sources = data_sources.get('dataSourceSummaries', [])
                    print(f"    Data sources: {len(sources)}")
                    
                    for source in sources:
                        print(f"      - ID: {source['dataSourceId']}")
                        print(f"        Name: {source['name']}")
                        print(f"        Status: {source['status']}")
                        
                except Exception as e:
                    print(f"    ❌ Error getting KB details: {str(e)}")
        
    except Exception as e:
        print(f"❌ Error checking knowledge base configuration: {str(e)}")
        import traceback
        traceback.print_exc()


async def main():
    """Main test function."""
    print("Knowledge Base Testing Tool")
    print("="*60)
    
    # Test 1: Check configuration
    await check_knowledge_base_configuration()
    
    # Test 2: Test Bedrock directly
    await test_bedrock_knowledge_base_directly()
    
    # Test 3: Test our knowledge tool wrapper
    await test_knowledge_tool()
    
    print("\n" + "="*60)
    print("Testing completed!")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())