"""Configuration management for Customer Search Agent."""

import os
from typing import Optional

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Configuration management class for environment variables."""
    
    def __init__(self):
        """Initialize configuration from environment variables."""
        # AWS Bedrock Knowledge Base configuration
        self.knowledge_base_id = self._get_required_env("KNOWLEDGE_BASE_ID")
        self.knowledge_base_model_arn = self._get_required_env("KNOWLEDGE_BASE_MODEL_ARN")
        
        # AWS Bedrock Guardrails configuration
        self.guardrail_id = self._get_required_env("GUARDRAIL_ID")
        self.guardrail_version = os.environ.get("GUARDRAIL_VERSION", "DRAFT")
        
        # AWS AgentCore Gateway configuration
        self.gateway_mcp_url = self._get_required_env("GATEWAY_MCP_URL")
        
        # Cognito Authentication configuration (optional)
        self.cognito_user_pool_id = os.environ.get("COGNITO_USER_POOL_ID")
        self.cognito_client_id = os.environ.get("COGNITO_CLIENT_ID")
        self.cognito_client_secret = os.environ.get("COGNITO_CLIENT_SECRET")
        self.cognito_domain = os.environ.get("COGNITO_DOMAIN")
        self.cognito_region = os.environ.get("COGNITO_REGION")
        self.cognito_scope = os.environ.get("COGNITO_SCOPE", "openid")
        
        # AWS Region configuration
        self.aws_region = os.environ.get("AWS_REGION", "us-east-1")
        
        # Runtime configuration
        self.response_timeout = int(os.environ.get("RESPONSE_TIMEOUT", "8"))
        self.agent_name = os.environ.get("AGENT_NAME", "customer-search-agent")
        self.log_level = os.environ.get("LOG_LEVEL", "INFO")
        
        # Optional configuration for development/testing
        self.mock_services = os.environ.get("MOCK_SERVICES", "false").lower() == "true"
        self.debug_mode = os.environ.get("DEBUG_MODE", "false").lower() == "true"
    
    def _get_required_env(self, key: str) -> str:
        """Get required environment variable or raise error if missing."""
        value = os.environ.get(key)
        if not value:
            raise ValueError(f"Required environment variable {key} is not set")
        return value
    
    def to_dict(self) -> dict:
        """Convert configuration to dictionary for tool invocation state."""
        return {
            "knowledge_base_id": self.knowledge_base_id,
            "knowledge_base_model_arn": self.knowledge_base_model_arn,
            "guardrail_id": self.guardrail_id,
            "guardrail_version": self.guardrail_version,
            "gateway_mcp_url": self.gateway_mcp_url,
            "cognito_user_pool_id": self.cognito_user_pool_id,
            "cognito_client_id": self.cognito_client_id,
            "cognito_client_secret": self.cognito_client_secret,
            "cognito_domain": self.cognito_domain,
            "cognito_region": self.cognito_region,
            "cognito_scope": self.cognito_scope,
            "aws_region": self.aws_region,
            "response_timeout": self.response_timeout,
            "agent_name": self.agent_name,
            "log_level": self.log_level,
            "mock_services": self.mock_services,
            "debug_mode": self.debug_mode
        }