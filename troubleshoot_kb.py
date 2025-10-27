#!/usr/bin/env python3
"""
Create sample documents to test knowledge base functionality.
"""

import boto3
import json
from config import Config

def get_data_source_details():
    """Get details about the current data source configuration."""
    config = Config()
    
    try:
        bedrock_agent = boto3.client('bedrock-agent', region_name=config.aws_region)
        
        # Get data sources
        data_sources_response = bedrock_agent.list_data_sources(knowledgeBaseId=config.knowledge_base_id)
        data_sources = data_sources_response.get('dataSourceSummaries', [])
        
        for source in data_sources:
            print(f"Data Source: {source['name']}")
            print(f"ID: {source['dataSourceId']}")
            print(f"Status: {source['status']}")
            
            # Get detailed configuration
            source_details = bedrock_agent.get_data_source(
                knowledgeBaseId=config.knowledge_base_id,
                dataSourceId=source['dataSourceId']
            )
            
            ds_config = source_details.get('dataSource', {}).get('dataSourceConfiguration', {})
            print(f"Type: {ds_config.get('type', 'Unknown')}")
            
            if 'webConfiguration' in ds_config:
                web_config = ds_config['webConfiguration']
                print("Web crawling configuration:")
                print(f"  Crawler limits: {web_config.get('crawlerLimits', {})}")
                print(f"  Inclusion filters: {web_config.get('inclusionFilters', [])}")
                print(f"  Exclusion filters: {web_config.get('exclusionFilters', [])}")
                
                if 'sourceConfiguration' in web_config:
                    source_config = web_config['sourceConfiguration']
                    if 'urlConfiguration' in source_config:
                        url_config = source_config['urlConfiguration']
                        print(f"  Seed URLs: {url_config.get('seedUrls', [])}")
            
    except Exception as e:
        print(f"Error getting data source details: {e}")

def create_troubleshooting_guide():
    """Create a troubleshooting guide for knowledge base issues."""
    
    guide = """
# Knowledge Base Troubleshooting Guide

## Problem: Knowledge base returns "Sorry, I am unable to assist you with this request"

## Root Cause
The knowledge base exists and is active, but no content has been successfully indexed. 
Current status:
- Knowledge Base: ✅ Active
- Data Source: ✅ Configured (Web crawling)
- Ingestion Job: ✅ Completed 
- Documents Indexed: ❌ 0 documents

## Solutions

### 1. Check Data Source Configuration
1. Go to AWS Console > Amazon Bedrock > Knowledge bases
2. Select your knowledge base: hackathon_KB
3. Click on "Data sources" tab
4. Review the web crawling configuration:
   - Check seed URLs are accessible
   - Verify inclusion/exclusion filters
   - Ensure crawler limits are appropriate

### 2. Add Test Content via S3
1. Create an S3 bucket with some test documents
2. Add a new S3 data source to your knowledge base
3. Upload sample content (PDFs, text files, etc.)
4. Start a new ingestion job

### 3. Manual Content Addition
1. Create simple text files with Scottish Power information
2. Upload to S3 bucket
3. Configure S3 as data source
4. Re-run ingestion

### 4. Web Crawling Debugging
- Check if the target websites are accessible
- Verify the websites have crawlable content (not just images/videos)
- Check robots.txt files on target sites
- Ensure proper authentication if required

### 5. Test with Sample Data
Create sample documents with Scottish Power content like:
- Energy tariff information
- Customer service details
- Billing information
- Energy efficiency tips

## Next Steps
1. Check the current web crawling configuration
2. Consider adding S3-based content as a backup
3. Test with minimal sample data
4. Monitor ingestion jobs for success metrics

## Expected Results After Fix
Once content is properly indexed, queries should return:
- Meaningful summaries with citations
- retrievedReferences with actual content
- Relevant source links
"""
    
    print(guide)

def main():
    print("Knowledge Base Content Issue - Troubleshooting")
    print("=" * 60)
    
    print("\n1. Current Data Source Configuration:")
    print("-" * 40)
    get_data_source_details()
    
    print("\n2. Troubleshooting Guide:")
    print("-" * 40)
    create_troubleshooting_guide()

if __name__ == "__main__":
    main()