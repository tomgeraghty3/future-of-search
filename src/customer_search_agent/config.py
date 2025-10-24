"""Configuration settings for the Customer Search Agent."""

import os
from typing import Optional


class Config:
    """Configuration class for environment variables and settings."""
    
    # AWS Configuration
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    KNOWLEDGE_BASE_ID: str = os.getenv("KNOWLEDGE_BASE_ID", "")
    GUARDRAILS_ID: str = os.getenv("GUARDRAILS_ID", "")
    
    # AgentCore Gateway Configuration
    GATEWAY_MCP_URL: str = os.getenv("GATEWAY_MCP_URL", "")
    GATEWAY_AUTH_REQUIRED: bool = os.getenv("GATEWAY_AUTH_REQUIRED", "false").lower() == "true"
    
    # AI Model Configuration
    AI_MODEL: str = os.getenv("AI_MODEL", "claude-3-7-sonnet")
    
    # Performance Configuration
    MAX_TOKENS: int = int(os.getenv("MAX_TOKENS", "4096"))
    TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.1"))
    RESPONSE_TIMEOUT: int = int(os.getenv("RESPONSE_TIMEOUT", "30"))
    
    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    

    
    @classmethod
    def validate_required_config(cls) -> None:
        """Validate that required configuration is present."""
        required_vars = [
            ("KNOWLEDGE_BASE_ID", cls.KNOWLEDGE_BASE_ID),
            ("GATEWAY_MCP_URL", cls.GATEWAY_MCP_URL),
            ("GUARDRAILS_ID", cls.GUARDRAILS_ID)
        ]
        
        missing_vars = [var_name for var_name, var_value in required_vars if not var_value]
        
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")


# Global config instance
config = Config()