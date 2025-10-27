#!/usr/bin/env python3
"""Check available knowledge bases in AWS account."""

import boto3
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def main():
    # Set up AWS credentials from environment
    session = boto3.Session(
        aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
        region_name=os.environ.get('AWS_REGION', 'us-east-1')
    )

    # Create bedrock agent client with SSL verification disabled for development
    import ssl
    import urllib3
    
    # Disable SSL warnings
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    # Create SSL context that doesn't verify certificates
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    bedrock_agent = session.client(
        'bedrock-agent',
        verify=False  # Disable SSL verification for development
    )

    try:
        # List knowledge bases
        print("Checking for knowledge bases in your AWS account...")
        response = bedrock_agent.list_knowledge_bases()
        
        print("\nAvailable Knowledge Bases:")
        print("=" * 50)
        
        knowledge_bases = response.get('knowledgeBaseSummaries', [])
        
        if knowledge_bases:
            for i, kb in enumerate(knowledge_bases, 1):
                print(f"{i}. ID: {kb['knowledgeBaseId']}")
                print(f"   Name: {kb['name']}")
                print(f"   Status: {kb['status']}")
                if 'description' in kb:
                    print(f"   Description: {kb['description']}")
                print("   " + "-" * 40)
        else:
            print("❌ No knowledge bases found in your account!")
            print("\nTo create a knowledge base:")
            print("1. Go to AWS Console > Amazon Bedrock > Knowledge bases")
            print("2. Create a new knowledge base")
            print("3. Update your .env file with the correct KNOWLEDGE_BASE_ID")
            
        print(f"\nCurrent configuration in .env:")
        print(f"KNOWLEDGE_BASE_ID={os.environ.get('KNOWLEDGE_BASE_ID')}")
        print(f"AWS_REGION={os.environ.get('AWS_REGION')}")
        
    except Exception as e:
        print(f"❌ Error listing knowledge bases: {e}")
        print("\nPossible issues:")
        print("1. AWS credentials are incorrect")
        print("2. IAM permissions are insufficient")
        print("3. Region is incorrect")
        print("4. Bedrock service is not available in this region")

if __name__ == "__main__":
    main()