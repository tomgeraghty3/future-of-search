"""
Token cache for improving Cognito authentication performance.
"""

import asyncio
import time
import logging
from typing import Optional, Dict
from tools.cognito_token_manager import CognitoTokenManager

logger = logging.getLogger(__name__)

class TokenCache:
    """Cache for Cognito access tokens to avoid repeated authentication."""
    
    def __init__(self):
        self._cache: Dict[str, Dict] = {}
        self._lock = asyncio.Lock()
    
    def _get_cache_key(self, user_pool_id: str, client_id: str) -> str:
        """Generate cache key for token."""
        return f"{user_pool_id}:{client_id}"
    
    async def get_token(self, cognito_manager: CognitoTokenManager) -> Optional[str]:
        """Get cached token or fetch new one if expired."""
        cache_key = self._get_cache_key(
            cognito_manager.user_pool_id,
            cognito_manager.client_id
        )
        
        async with self._lock:
            # Check if we have a valid cached token
            if cache_key in self._cache:
                token_data = self._cache[cache_key]
                current_time = time.time()
                
                # Check if token is still valid (with 5 minute buffer)
                if current_time < (token_data['expires_at'] - 300):
                    logger.debug(f"Using cached token (expires in {token_data['expires_at'] - current_time:.0f}s)")
                    return token_data['access_token']
                else:
                    logger.debug("Cached token expired, removing from cache")
                    del self._cache[cache_key]
            
            # Get new token
            try:
                access_token = await cognito_manager.get_access_token()
                if access_token:
                    # Cache the token (assume 1 hour expiry with 5 min buffer)
                    self._cache[cache_key] = {
                        'access_token': access_token,
                        'expires_at': time.time() + 3300  # 55 minutes
                    }
                    logger.debug("New token cached successfully")
                    return access_token
            except Exception as e:
                logger.error(f"Failed to get new token: {str(e)}")
                return None
    
    def clear_cache(self):
        """Clear all cached tokens."""
        self._cache.clear()
        logger.info("Token cache cleared")

# Global token cache instance
_token_cache = TokenCache()

def get_token_cache() -> TokenCache:
    """Get the global token cache instance."""
    return _token_cache