"""
Retry utilities for handling timeout and connection issues.
"""

import asyncio
import logging
from typing import Callable, Any, Optional
from functools import wraps

logger = logging.getLogger(__name__)

class RetryConfig:
    """Configuration for retry behavior."""
    
    def __init__(self, 
                 max_attempts: int = 3,
                 base_delay: float = 1.0,
                 max_delay: float = 30.0,
                 exponential_backoff: bool = True):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_backoff = exponential_backoff

async def retry_with_timeout(
    func: Callable, 
    timeout: float,
    retry_config: RetryConfig = RetryConfig(),
    *args, 
    **kwargs
) -> Any:
    """
    Execute a function with retry logic and timeout handling.
    
    Args:
        func: The async function to execute
        timeout: Timeout for each attempt
        retry_config: Retry configuration
        *args, **kwargs: Arguments for the function
        
    Returns:
        Result of the function
        
    Raises:
        The last exception encountered
    """
    last_exception = None
    
    for attempt in range(retry_config.max_attempts):
        try:
            logger.info(f"Attempt {attempt + 1}/{retry_config.max_attempts}")
            result = await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
            logger.info(f"Success on attempt {attempt + 1}")
            return result
            
        except asyncio.TimeoutError as e:
            last_exception = e
            logger.warning(f"Timeout on attempt {attempt + 1}: {str(e)}")
            
        except Exception as e:
            last_exception = e
            logger.warning(f"Error on attempt {attempt + 1}: {str(e)}")
        
        # Don't wait after the last attempt
        if attempt < retry_config.max_attempts - 1:
            if retry_config.exponential_backoff:
                delay = min(retry_config.base_delay * (2 ** attempt), retry_config.max_delay)
            else:
                delay = retry_config.base_delay
            
            logger.info(f"Waiting {delay:.1f}s before retry...")
            await asyncio.sleep(delay)
    
    logger.error(f"All {retry_config.max_attempts} attempts failed")
    raise last_exception

def with_retry_and_timeout(timeout: float, retry_config: RetryConfig = RetryConfig()):
    """
    Decorator to add retry and timeout logic to async functions.
    
    Args:
        timeout: Timeout for each attempt
        retry_config: Retry configuration
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await retry_with_timeout(func, timeout, retry_config, *args, **kwargs)
        return wrapper
    return decorator

# Example usage:
# @with_retry_and_timeout(timeout=30.0, retry_config=RetryConfig(max_attempts=3))
# async def my_function():
#     # Your code here
#     pass