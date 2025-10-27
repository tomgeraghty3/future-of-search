#!/usr/bin/env python3
"""
Comprehensive SSL Environment Fix Script

This script sets up the development environment to bypass SSL verification issues
that are common on macOS and other development environments.
"""

import os
import sys
import logging

def setup_ssl_bypass_environment():
    """Configure environment variables for SSL bypass in development."""
    
    print("=== Setting up SSL Bypass Environment ===")
    print("⚠️  WARNING: This disables SSL verification for development only!")
    print("⚠️  DO NOT use in production environments!")
    
    # Set environment variables for SSL bypass
    ssl_bypass_vars = {
        'ENVIRONMENT': 'development',
        'PYTHONHTTPSVERIFY': '0',
        'AWS_CA_BUNDLE': '',
        'SSL_CERT_FILE': '',
        'COGNITO_DISABLE_SSL_VERIFICATION': 'true',
        'REQUESTS_CA_BUNDLE': '',
        'CURL_CA_BUNDLE': ''
    }
    
    for var, value in ssl_bypass_vars.items():
        os.environ[var] = value
        print(f"✅ Set {var}={value}")
    
    # Also configure SSL context globally
    try:
        import ssl
        ssl._create_default_https_context = ssl._create_unverified_context
        print("✅ Configured global SSL context to skip verification")
    except Exception as e:
        print(f"❌ Could not configure SSL context: {e}")
    
    # Configure urllib3 to disable SSL warnings
    try:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        print("✅ Disabled urllib3 SSL warnings")
    except ImportError:
        print("ℹ️  urllib3 not available, skipping warning suppression")
    
    print("\n=== SSL Bypass Environment Setup Complete ===")
    print("The environment is now configured to bypass SSL verification.")
    print("Restart your application for changes to take effect.")

if __name__ == "__main__":
    setup_ssl_bypass_environment()