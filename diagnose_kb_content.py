#!/usr/bin/env python3
"""
Diagnose knowledge base content and citations.
"""

import boto3
import json
from config import Config

def main():
    config = Config()
    
    print("Knowledge Base Content Diagnosis")
    print("="*50)
    
    bedrock_client = boto3.client('bedrock-agent-runtime', region_name=config.aws_region)
    
    test_queries = [
        "test query",
        "Scottish Power",
        "energy",
        "electricity",
        "help",
        "information",
        "customer service"
    ]
    
    for query in test_queries:
        print(f"\nTesting query: '{query}'")
        print("-" * 30)
        
        try:
            response = bedrock_client.retrieve_and_generate(
                input={'text': query},
                retrieveAndGenerateConfiguration={
                    'type': 'KNOWLEDGE_BASE',
                    'knowledgeBaseConfiguration': {
                        'knowledgeBaseId': config.knowledge_base_id,
                        'modelArn': config.knowledge_base_model_arn
                    }
                }
            )
            
            output = response.get('output', {})
            generated_text = output.get('text', '')
            citations = response.get('citations', [])
            
            print(f"Generated text: {generated_text}")
            print(f"Number of citations: {len(citations)}")
            
            if citations:
                print("Citations details:")
                for i, citation in enumerate(citations):
                    print(f"  Citation {i+1}:")
                    print(f"    Full citation: {json.dumps(citation, indent=6, default=str)}")
                    
                    # Extract references
                    references = citation.get('retrievedReferences', [])
                    print(f"    References: {len(references)}")
                    
                    for j, ref in enumerate(references):
                        print(f"      Reference {j+1}:")
                        print(f"        Content: {ref.get('content', {}).get('text', 'No text')[:200]}...")
                        print(f"        Location: {ref.get('location', 'No location')}")
                        print(f"        Metadata: {ref.get('metadata', 'No metadata')}")
            else:
                print("    No citations found")
                
        except Exception as e:
            print(f"Error testing query '{query}': {str(e)}")

if __name__ == "__main__":
    main()