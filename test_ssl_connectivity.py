#!/usr/bin/env python3
"""
SSL Configuration Test Script

This script tests SSL connectivity to various AWS services used by the application
to ensure that SSL bypass is working correctly in the development environment.
"""

import os
import sys
import asyncio
import ssl
import socket
import urllib.request
from urllib.error import URLError

def setup_ssl_bypass():
    """Setup SSL bypass configuration."""
    os.environ['ENVIRONMENT'] = 'development'
    os.environ['PYTHONHTTPSVERIFY'] = '0'
    os.environ['AWS_CA_BUNDLE'] = ''
    os.environ['SSL_CERT_FILE'] = ''
    os.environ['COGNITO_DISABLE_SSL_VERIFICATION'] = 'true'
    
    # Configure SSL context to skip verification
    ssl._create_default_https_context = ssl._create_unverified_context
    
    print("✅ SSL bypass configuration applied")

def test_basic_connectivity():
    """Test basic connectivity to AWS services."""
    print("\n=== Testing Basic Connectivity ===")
    
    test_endpoints = [
        "https://bedrock-runtime.us-east-1.amazonaws.com",
        "https://cognito-idp.us-east-1.amazonaws.com",
        "https://httpbin.org/get",
        "https://my-domain-sl4iryr8.auth.us-east-1.amazoncognito.com"
    ]
    
    for endpoint in test_endpoints:
        try:
            response = urllib.request.urlopen(endpoint, timeout=10)
            status = response.getcode()
            print(f"✅ {endpoint} - HTTP {status}")
        except URLError as e:
            if "CERTIFICATE_VERIFY_FAILED" in str(e):
                print(f"❌ {endpoint} - SSL Certificate Error: {e}")
            else:
                print(f"⚠️  {endpoint} - Connection Error: {e}")
        except Exception as e:
            print(f"⚠️  {endpoint} - Error: {e}")

def test_dns_resolution():
    """Test DNS resolution for AWS endpoints."""
    print("\n=== Testing DNS Resolution ===")
    
    hostnames = [
        "bedrock-runtime.us-east-1.amazonaws.com",
        "cognito-idp.us-east-1.amazonaws.com",
        "my-domain-sl4iryr8.auth.us-east-1.amazoncognito.com",
        "gateway-da9314-0gu1psl2vv.gateway.bedrock-agentcore.us-east-1.amazonaws.com"
    ]
    
    for hostname in hostnames:
        try:
            ip = socket.gethostbyname(hostname)
            print(f"✅ {hostname} -> {ip}")
        except socket.gaierror as e:
            print(f"❌ {hostname} - DNS Error: {e}")

async def test_cognito_token_manager():
    """Test the Cognito Token Manager with SSL bypass."""
    print("\n=== Testing Cognito Token Manager ===")
    
    try:
        # Import and test the CognitoTokenManager
        sys.path.append('/Users/vijay.mallajosulavenkata/ML Projects/Client Projects/SP Hackathon/future-of-search')
        from tools.cognito_token_manager import CognitoTokenManager
        
        # Create token manager with test configuration
        token_manager = CognitoTokenManager(
            user_pool_id="us-east-1_oCnQhXPhD",
            client_id="4ik5mjjm46lert89sqe1obdvib",
            client_secret="l59v4tkdp7g5006miluinadibsf6u73v0el07ob5s6d87t4r418",
            region="us-east-1",
            domain="my-domain-sl4iryr8"
        )
        
        # Validate endpoints
        validation_results = await token_manager.validate_endpoints()
        
        print(f"DNS Resolution: {'✅' if validation_results['dns_resolution'] else '❌'}")
        print(f"Token Endpoint: {'✅' if validation_results['token_endpoint_reachable'] else '❌'}")
        print(f"Discovery Endpoint: {'✅' if validation_results['discovery_endpoint_reachable'] else '❌'}")
        
        if validation_results['errors']:
            print("Errors:")
            for error in validation_results['errors']:
                print(f"  - {error}")
        
        # Try to get access token
        try:
            access_token = await token_manager.get_access_token()
            print("✅ Successfully obtained access token")
            print(f"Token starts with: {access_token[:20]}...")
        except Exception as e:
            print(f"❌ Failed to get access token: {e}")
            
    except ImportError as e:
        print(f"❌ Could not import CognitoTokenManager: {e}")
    except Exception as e:
        print(f"❌ Error testing CognitoTokenManager: {e}")

def main():
    """Main test function."""
    print("=== SSL Configuration Test Script ===")
    print("Testing SSL connectivity for Future of Search application")
    
    setup_ssl_bypass()
    test_dns_resolution()
    test_basic_connectivity()
    
    # Run async test
    try:
        asyncio.run(test_cognito_token_manager())
    except Exception as e:
        print(f"❌ Error running async tests: {e}")
    
    print("\n=== Test Complete ===")
    print("If all tests pass, SSL bypass is working correctly.")

if __name__ == "__main__":
    main()