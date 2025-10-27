#!/usr/bin/env python3
"""
Check knowledge base data sources and sync status.
"""

import boto3
import json
from dotenv import load_dotenv
from config import Config

# Load environment variables
load_dotenv()

def main():
    config = Config()
    
    print("Checking Knowledge Base Data Sources...")
    print("="*60)
    
    try:
        # Initialize bedrock agent client
        bedrock_agent = boto3.client(
            'bedrock-agent',
            region_name=config.aws_region
        )
        
        # Get knowledge base details
        kb_response = bedrock_agent.get_knowledge_base(knowledgeBaseId=config.knowledge_base_id)
        kb_details = kb_response.get('knowledgeBase', {})
        
        print(f"Knowledge Base: {kb_details.get('name', 'N/A')}")
        print(f"Status: {kb_details.get('status', 'N/A')}")
        print(f"Description: {kb_details.get('description', 'N/A')}")
        print(f"Created: {kb_details.get('createdAt', 'N/A')}")
        print(f"Updated: {kb_details.get('updatedAt', 'N/A')}")
        
        # Get data sources
        print(f"\nData Sources:")
        print("-" * 40)
        
        data_sources_response = bedrock_agent.list_data_sources(knowledgeBaseId=config.knowledge_base_id)
        data_sources = data_sources_response.get('dataSourceSummaries', [])
        
        if not data_sources:
            print("❌ NO DATA SOURCES FOUND!")
            print("\nThis explains why searches return 'Sorry, I am unable to assist you with this request.'")
            print("\nTo fix this issue:")
            print("1. Go to AWS Console > Amazon Bedrock > Knowledge bases")
            print(f"2. Select your knowledge base: {config.knowledge_base_id}")
            print("3. Add data sources (S3 buckets, web crawling, etc.)")
            print("4. Wait for data ingestion to complete")
            print("5. Test again")
            return
            
        print(f"Found {len(data_sources)} data source(s):")
        
        for i, source in enumerate(data_sources, 1):
            print(f"\n{i}. Data Source:")
            print(f"   ID: {source['dataSourceId']}")
            print(f"   Name: {source['name']}")
            print(f"   Status: {source['status']}")
            print(f"   Updated: {source.get('updatedAt', 'N/A')}")
            
            # Get detailed information about this data source
            try:
                source_details = bedrock_agent.get_data_source(
                    knowledgeBaseId=config.knowledge_base_id,
                    dataSourceId=source['dataSourceId']
                )
                
                ds_info = source_details.get('dataSource', {})
                data_source_config = ds_info.get('dataSourceConfiguration', {})
                
                print(f"   Type: {data_source_config.get('type', 'Unknown')}")
                
                # Check if it's S3 data source
                if 's3Configuration' in data_source_config:
                    s3_config = data_source_config['s3Configuration']
                    print(f"   S3 Bucket: {s3_config.get('bucketArn', 'N/A')}")
                    if 'inclusionPrefixes' in s3_config:
                        print(f"   Inclusion Prefixes: {s3_config['inclusionPrefixes']}")
                
                # Check ingestion jobs
                print(f"   \n   Checking ingestion jobs...")
                
                ingestion_jobs = bedrock_agent.list_ingestion_jobs(
                    knowledgeBaseId=config.knowledge_base_id,
                    dataSourceId=source['dataSourceId'],
                    maxResults=5
                )
                
                jobs = ingestion_jobs.get('ingestionJobSummaries', [])
                
                if not jobs:
                    print(f"   ❌ NO INGESTION JOBS FOUND!")
                    print(f"   The data source exists but no ingestion has been started.")
                else:
                    print(f"   Found {len(jobs)} ingestion job(s):")
                    for j, job in enumerate(jobs, 1):
                        print(f"     {j}. Job ID: {job['ingestionJobId']}")
                        print(f"        Status: {job['status']}")
                        print(f"        Started: {job.get('startedAt', 'N/A')}")
                        print(f"        Updated: {job.get('updatedAt', 'N/A')}")
                        
                        if 'statistics' in job:
                            stats = job['statistics']
                            print(f"        Documents Processed: {stats.get('numberOfDocumentsScanned', 0)}")
                            print(f"        Documents Indexed: {stats.get('numberOfDocumentsIndexed', 0)}")
                            print(f"        Documents Failed: {stats.get('numberOfDocumentsFailed', 0)}")
                
            except Exception as e:
                print(f"   ❌ Error getting data source details: {str(e)}")
        
        # Check vector store
        print(f"\nVector Store Configuration:")
        print("-" * 40)
        
        vector_config = kb_details.get('storageConfiguration', {})
        if 'type' in vector_config:
            print(f"Vector Store Type: {vector_config['type']}")
            
            if vector_config['type'] == 'OPENSEARCH_SERVERLESS':
                opensearch_config = vector_config.get('opensearchServerlessConfiguration', {})
                print(f"Collection ARN: {opensearch_config.get('collectionArn', 'N/A')}")
                print(f"Vector Index Name: {opensearch_config.get('vectorIndexName', 'N/A')}")
            elif vector_config['type'] == 'PINECONE':
                pinecone_config = vector_config.get('pineconeConfiguration', {})
                print(f"Connection String: {pinecone_config.get('connectionString', 'N/A')}")
        
    except Exception as e:
        print(f"❌ Error checking knowledge base: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()