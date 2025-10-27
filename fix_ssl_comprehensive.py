#!/usr/bin/env python3
"""
Comprehensive SSL fix for development environment.
This script addresses SSL certificate verification issues across all HTTP clients.
"""

import os
import ssl
import warnings
import urllib3
from urllib3.exceptions import InsecureRequestWarning

def apply_ssl_fixes():
    """Apply comprehensive SSL fixes for development environment."""
    
    # 1. Set environment variables to disable SSL verification
    os.environ['PYTHONHTTPSVERIFY'] = '0'
    os.environ['AWS_CA_BUNDLE'] = ''
    os.environ['REQUESTS_CA_BUNDLE'] = ''
    os.environ['CURL_CA_BUNDLE'] = ''
    
    # 2. Disable SSL warnings
    urllib3.disable_warnings(InsecureRequestWarning)
    warnings.filterwarnings('ignore', message='Unverified HTTPS request')
    warnings.filterwarnings('ignore', category=urllib3.exceptions.InsecureRequestWarning)
    
    # 3. Patch SSL context creation
    # Store the original function before replacing it
    _original_create_default_context = ssl.create_default_context
    
    def create_unverified_context(*args, **kwargs):
        context = _original_create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context
    
    ssl._create_default_https_context = create_unverified_context
    # Don't override ssl.create_default_context to avoid recursion
    
    # 4. Patch httpx for MCP client
    try:
        import httpx
        # Create a custom transport with SSL verification disabled
        # Increase default timeout for HTTP requests
        default_timeout = int(os.environ.get("HTTP_TIMEOUT", "120"))  # Default 120 seconds
        httpx._config.DEFAULT_TIMEOUT_CONFIG = httpx.Timeout(default_timeout)
        
        # Monkey patch httpx to use unverified SSL
        original_init = httpx.Client.__init__
        def patched_init(self, *args, **kwargs):
            kwargs['verify'] = False
            return original_init(self, *args, **kwargs)
        httpx.Client.__init__ = patched_init
        
        original_async_init = httpx.AsyncClient.__init__
        def patched_async_init(self, *args, **kwargs):
            kwargs['verify'] = False
            return original_async_init(self, *args, **kwargs)
        httpx.AsyncClient.__init__ = patched_async_init
        
        print("✓ Applied httpx SSL bypass")
    except ImportError:
        print("! httpx not found, skipping httpx patches")
    
    # 5. Patch requests library if available
    try:
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        class InsecureHTTPAdapter(HTTPAdapter):
            def init_poolmanager(self, *args, **kwargs):
                kwargs['ssl_context'] = create_unverified_context()
                return super().init_poolmanager(*args, **kwargs)
        
        # Monkey patch requests
        original_request = requests.Session.request
        def patched_request(self, *args, **kwargs):
            kwargs['verify'] = False
            return original_request(self, *args, **kwargs)
        requests.Session.request = patched_request
        
        print("✓ Applied requests SSL bypass")
    except ImportError:
        print("! requests not found, skipping requests patches")
    
    print("✓ Comprehensive SSL fixes applied for development environment")
    print("⚠️  WARNING: SSL verification is DISABLED - NOT FOR PRODUCTION!")

if __name__ == "__main__":
    apply_ssl_fixes()