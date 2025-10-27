"""
Enhanced Cognito Token Manager for AWS Bedrock AgentCore Gateway Authentication

This module provides OAuth token management for Cognito User Pool client credentials flow,
enabling secure authentication with AgentCore Gateway MCP endpoints.
Includes comprehensive validation, error handling, and DNS resolution testing.
"""

import httpx
import base64
import json
import logging
import socket
import ssl
import certifi
import os
from datetime import datetime, timedelta
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class CognitoTokenManager:
    """Enhanced Cognito Token Manager with validation and error handling"""
    
    def __init__(self, user_pool_id: str, client_id: str, client_secret: str, 
                 region: str, domain: str, scope: str = ""):
        """
        Initialize the Enhanced Cognito Token Manager.
        
        Args:
            user_pool_id: Cognito User Pool ID (e.g., 'us-east-1_XXXXXXXXX')
            client_id: App Client ID from the User Pool
            client_secret: App Client Secret from the User Pool
            region: AWS region where the User Pool is located
            domain: Cognito domain prefix (without .auth.region.amazoncognito.com)
            scope: OAuth scopes to request (empty string for no scopes)
        """
        self.user_pool_id = user_pool_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.region = region
        self.domain = domain
        self.scope = scope
        
        # Validate configuration
        self._validate_configuration()
        
        # Construct endpoints
        self.token_endpoint_host = f"{domain}.auth.{region}.amazoncognito.com"
        self.token_endpoint = f"https://{self.token_endpoint_host}/oauth2/token"
        self.discovery_endpoint = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/openid-configuration"
        
        # Configure SSL context for proper certificate handling
        self._setup_ssl_context()
        
        # Token storage
        self._access_token: Optional[str] = None
        self._expires_at: Optional[datetime] = None
        
        logger.info(f"Initialized Enhanced CognitoTokenManager for User Pool: {user_pool_id}")
        logger.debug(f"Token endpoint: {self.token_endpoint}")
        logger.debug(f"Discovery endpoint: {self.discovery_endpoint}")
    
    def _validate_configuration(self):
        """Validate the configuration parameters."""
        
        # Validate User Pool ID format
        if not self.user_pool_id or not self.user_pool_id.startswith(f"{self.region}_"):
            raise ValueError(f"Invalid User Pool ID format. Expected format: {self.region}_XXXXXXXXX")
        
        # Validate region
        valid_regions = [
            'us-east-1', 'us-east-2', 'us-west-1', 'us-west-2',
            'eu-west-1', 'eu-west-2', 'eu-central-1', 'ap-southeast-1',
            'ap-southeast-2', 'ap-northeast-1', 'ca-central-1'
        ]
        if self.region not in valid_regions:
            logger.warning(f"Region '{self.region}' might not support Cognito. Common regions: {valid_regions}")
        
        # Validate domain format
        if not self.domain or len(self.domain) < 3 or len(self.domain) > 63:
            raise ValueError("Domain must be between 3 and 63 characters")
        
        # Check for reserved words
        reserved_words = ['aws', 'amazon', 'cognito']
        if any(word in self.domain.lower() for word in reserved_words):
            raise ValueError(f"Domain cannot contain reserved words: {reserved_words}")
    
    def _setup_ssl_context(self):
        """Setup SSL context for proper certificate handling on macOS and other platforms."""
        try:
            # Check for development environment or explicit SSL bypass first
            is_development = os.getenv('ENVIRONMENT', 'development') == 'development'
            ssl_bypass = os.getenv('COGNITO_DISABLE_SSL_VERIFICATION', 'false').lower() == 'true'
            
            if is_development or ssl_bypass:
                logger.warning("SSL verification disabled for development environment - NOT SAFE FOR PRODUCTION")
                self._http_verify = False  # Disable SSL verification for development
                self._allow_unverified_ssl = True
                return
            
            # Create SSL context with proper certificate verification for production
            self._ssl_context = ssl.create_default_context()
            
            # Try to use certifi bundle if available
            try:
                self._ssl_context.load_verify_locations(certifi.where())
                logger.debug("Using certifi certificate bundle for SSL verification")
            except Exception as e:
                logger.debug(f"Could not load certifi bundle: {e}, using system defaults")
            
            # Configure HTTPX to use our SSL context
            self._http_verify = self._ssl_context
            self._allow_unverified_ssl = False
            
        except Exception as e:
            logger.warning(f"SSL context setup failed: {e}, falling back to default verification")
            # Fallback to default verification
            self._http_verify = True
            self._allow_unverified_ssl = False
    
    def _test_dns_resolution(self) -> Tuple[bool, Optional[str]]:
        """Test if the token endpoint hostname can be resolved."""
        try:
            socket.gethostbyname(self.token_endpoint_host)
            return True, None
        except socket.gaierror as e:
            return False, str(e)
    
    async def validate_endpoints(self) -> dict:
        """Validate that endpoints are accessible."""
        results = {
            'dns_resolution': False,
            'token_endpoint_reachable': False,
            'discovery_endpoint_reachable': False,
            'errors': []
        }
        
        # Test DNS resolution
        can_resolve, dns_error = self._test_dns_resolution()
        results['dns_resolution'] = can_resolve
        if not can_resolve:
            results['errors'].append(f"DNS resolution failed for {self.token_endpoint_host}: {dns_error}")
            return results
        
        # Test HTTP connectivity
        verify_setting = False if self._allow_unverified_ssl else self._http_verify
        async with httpx.AsyncClient(timeout=10.0, verify=verify_setting) as client:
            # Test token endpoint (expect 405 for GET)
            try:
                response = await client.get(self.token_endpoint)
                results['token_endpoint_reachable'] = True
                logger.debug(f"Token endpoint returned HTTP {response.status_code}")
            except Exception as e:
                results['errors'].append(f"Token endpoint unreachable: {str(e)}")
            
            # Test discovery endpoint
            try:
                response = await client.get(self.discovery_endpoint)
                results['discovery_endpoint_reachable'] = response.status_code == 200
                if response.status_code != 200:
                    results['errors'].append(f"Discovery endpoint returned HTTP {response.status_code}")
            except Exception as e:
                results['errors'].append(f"Discovery endpoint unreachable: {str(e)}")
        
        return results
    
    async def get_access_token(self) -> str:
        """
        Get a valid access token, refreshing if needed.
        
        Returns:
            Valid access token string
            
        Raises:
            Exception: If token request fails
        """
        
        # Return cached token if still valid (with 5-minute buffer)
        if (self._access_token and self._expires_at and 
            self._expires_at > datetime.now() + timedelta(minutes=5)):
            logger.debug("Using cached access token")
            return self._access_token
        
        # Validate endpoints before attempting token request
        validation_results = await self.validate_endpoints()
        if not validation_results['dns_resolution']:
            error_msg = f"Cannot resolve Cognito domain. Errors: {validation_results['errors']}"
            logger.error(error_msg)
            raise Exception(error_msg)
        
        # Request new token using client credentials flow
        logger.info("Requesting new access token from Cognito")
        await self._refresh_token()
        return self._access_token
    
    async def _refresh_token(self):
        """
        Request a new access token using client credentials flow.
        
        Raises:
            Exception: If token request fails
        """
        
        # Prepare Basic Auth header
        credentials = f"{self.client_id}:{self.client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "AWS-Cognito-Client/1.0"
        }
        
        # Prepare request data
        data = {
            "grant_type": "client_credentials"
        }
        
        # Only add scope if it's not empty
        if self.scope and self.scope.strip():
            data["scope"] = self.scope.strip()
        
        logger.debug(f"Making token request to: {self.token_endpoint}")
        logger.debug(f"Request data: {data}")
        
        try:
            # Use the configured SSL context or bypass if requested
            verify_setting = False if self._allow_unverified_ssl else self._http_verify
            async with httpx.AsyncClient(timeout=30.0, verify=verify_setting) as client:
                response = await client.post(
                    self.token_endpoint,
                    headers=headers,
                    data=data
                )
                
                logger.debug(f"Token response status: {response.status_code}")
                logger.debug(f"Token response headers: {dict(response.headers)}")
                
                if response.status_code != 200:
                    error_details = {
                        'status_code': response.status_code,
                        'response_text': response.text,
                        'endpoint': self.token_endpoint,
                        'client_id': self.client_id
                    }
                    
                    # Parse error response if possible
                    try:
                        error_json = response.json()
                        error_details['error'] = error_json.get('error', 'unknown')
                        error_details['error_description'] = error_json.get('error_description', 'No description')
                    except:
                        pass
                    
                    error_msg = f"Token request failed: {response.status_code} - {response.text}"
                    logger.error(f"{error_msg}. Details: {error_details}")
                    raise Exception(error_msg)
                
                token_data = response.json()
                
                self._access_token = token_data["access_token"]
                expires_in = token_data.get("expires_in", 3600)  # Default 1 hour
                self._expires_at = datetime.now() + timedelta(seconds=expires_in)
                
                logger.info(f"✓ New access token obtained, expires in {expires_in} seconds")
                logger.debug(f"Token type: {token_data.get('token_type', 'Bearer')}")
                logger.debug(f"Scope: {token_data.get('scope', 'none')}")
                
        except httpx.RequestError as e:
            error_msg = f"Network error during token request: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error during token request: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
    
    def is_token_valid(self) -> bool:
        """Check if the current token is valid (not expired)."""
        return (self._access_token is not None and 
                self._expires_at is not None and 
                self._expires_at > datetime.now())
    
    def get_token_info(self) -> dict:
        """Get information about the current token."""
        return {
            "has_token": self._access_token is not None,
            "is_valid": self.is_token_valid(),
            "expires_at": self._expires_at.isoformat() if self._expires_at else None,
            "expires_in_seconds": (
                int((self._expires_at - datetime.now()).total_seconds()) 
                if self._expires_at else None
            ),
            "token_endpoint": self.token_endpoint,
            "discovery_endpoint": self.discovery_endpoint
        }


class CognitoTokenManagerError(Exception):
    """Custom exception for Cognito Token Manager errors"""
    pass