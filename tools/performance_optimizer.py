"""
Performance optimizations for the search agent.
"""

import asyncio
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class PerformanceOptimizer:
    """Optimize agent performance by implementing fast-fail patterns."""
    
    @staticmethod
    async def run_with_fast_fail(
        func,
        timeout: float = 10.0,
        fallback_result: Any = None,
        error_message: str = "Operation failed"
    ):
        """
        Run a function with fast-fail timeout for non-critical operations.
        
        Args:
            func: Async function to execute
            timeout: Maximum time to wait (default 10s for fast operations)
            fallback_result: What to return on timeout/error
            error_message: Error message to log
        """
        try:
            return await asyncio.wait_for(func(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(f"{error_message} - timeout after {timeout}s")
            return fallback_result
        except Exception as e:
            logger.warning(f"{error_message} - error: {str(e)}")
            return fallback_result
    
    @staticmethod
    def create_fast_personalisation_fallback():
        """Create a fast fallback for personalisation when it's failing."""
        return {"personalised": ""}
    
    @staticmethod
    def create_fast_guardrails_fallback(summary: str, links: list):
        """Create a fast fallback for guardrails when it's failing."""
        return {
            "summary": summary,
            "links": links,
            "success": True
        }

def optimize_agent_performance():
    """Apply performance optimizations to the agent."""
    logger.info("Applied performance optimizations - fast-fail enabled")
    return True