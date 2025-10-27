#!/usr/bin/env python3
"""
Monitor knowledge base ingestion progress.
"""

import boto3
import time
import json
from dotenv import load_dotenv
from config import Config

# Load environment variables
load_dotenv()

def check_ingestion_status():
    config = Config()
    
    try:
        # Initialize bedrock agent client
        bedrock_agent = boto3.client(
            'bedrock-agent',
            region_name=config.aws_region
        )
        
        # Get data sources
        data_sources_response = bedrock_agent.list_data_sources(knowledgeBaseId=config.knowledge_base_id)
        data_sources = data_sources_response.get('dataSourceSummaries', [])
        
        if not data_sources:
            print("❌ No data sources found!")
            return False
            
        all_complete = True
        
        for source in data_sources:
            print(f"\nData Source: {source['name']} ({source['dataSourceId']})")
            print(f"Status: {source['status']}")
            
            # Get recent ingestion jobs
            ingestion_jobs = bedrock_agent.list_ingestion_jobs(
                knowledgeBaseId=config.knowledge_base_id,
                dataSourceId=source['dataSourceId'],
                maxResults=3
            )
            
            jobs = ingestion_jobs.get('ingestionJobSummaries', [])
            
            if not jobs:
                print("❌ No ingestion jobs found!")
                all_complete = False
                continue
                
            # Check the latest job
            latest_job = jobs[0]
            job_status = latest_job['status']
            
            print(f"Latest Ingestion Job: {latest_job['ingestionJobId']}")
            print(f"Status: {job_status}")
            print(f"Started: {latest_job.get('startedAt', 'N/A')}")
            print(f"Updated: {latest_job.get('updatedAt', 'N/A')}")
            
            if 'statistics' in latest_job:
                stats = latest_job['statistics']
                print(f"Documents Scanned: {stats.get('numberOfDocumentsScanned', 0)}")
                print(f"Documents Indexed: {stats.get('numberOfDocumentsIndexed', 0)}")
                print(f"Documents Failed: {stats.get('numberOfDocumentsFailed', 0)}")
                
                if stats.get('numberOfDocumentsIndexed', 0) > 0:
                    print("✅ Some documents have been indexed!")
                else:
                    print("⏳ No documents indexed yet...")
            
            # Check if job is still running
            if job_status in ['STARTING', 'IN_PROGRESS']:
                print(f"⏳ Job is still {job_status.lower()}...")
                all_complete = False
            elif job_status == 'COMPLETE':
                print("✅ Ingestion completed successfully!")
            elif job_status == 'FAILED':
                print("❌ Ingestion failed!")
                
                # Get failure details
                try:
                    job_details = bedrock_agent.get_ingestion_job(
                        knowledgeBaseId=config.knowledge_base_id,
                        dataSourceId=source['dataSourceId'],
                        ingestionJobId=latest_job['ingestionJobId']
                    )
                    
                    job_info = job_details.get('ingestionJob', {})
                    if 'failureReasons' in job_info:
                        print(f"Failure reasons: {job_info['failureReasons']}")
                        
                except Exception as e:
                    print(f"Could not get job details: {str(e)}")
                    
                all_complete = False
        
        return all_complete
        
    except Exception as e:
        print(f"❌ Error checking ingestion status: {str(e)}")
        return False

def main():
    print("Knowledge Base Ingestion Monitor")
    print("="*50)
    print("Monitoring ingestion progress... (Press Ctrl+C to stop)")
    
    try:
        while True:
            print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Checking ingestion status...")
            
            if check_ingestion_status():
                print("\n🎉 All ingestion jobs completed successfully!")
                print("Your knowledge base should now be able to find information.")
                print("\nYou can test it by running:")
                print("python test_knowledge_base.py")
                break
            else:
                print("\n⏳ Ingestion still in progress. Waiting 30 seconds...")
                time.sleep(30)
                
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped by user.")
        print("You can run this script again to check the status.")

if __name__ == "__main__":
    main()