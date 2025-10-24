"""Data models for the Customer Search Agent."""

from typing import List, Optional
from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """Input model for search requests."""
    search_query: str = Field(..., description="Natural language search query")
    user_id: Optional[str] = Field(None, description="User identifier for personalisation")


class SearchResponse(BaseModel):
    """Output model for search responses."""
    personalised: str = Field("", description="User-specific content or empty string")
    summary: str = Field("", description="General summary from knowledge base")
    links: List[str] = Field(default_factory=list, description="Source URLs and citations")


class RetrievalResult(BaseModel):
    """Result from knowledge base retrieval."""
    summary: str = Field("", description="Generated summary from knowledge base")
    citations: List[str] = Field(default_factory=list, description="Source citations")
    confidence_score: float = Field(0.0, description="Confidence score of the result")


class PersonalisationResult(BaseModel):
    """Result from personalisation service."""
    content: str = Field("", description="Personalised content for the user")
    tool_used: str = Field("", description="Name of the tool used for personalisation")
    success: bool = Field(False, description="Whether personalisation was successful")


class ValidationResult(BaseModel):
    """Result from safety validation."""
    approved: bool = Field(False, description="Whether content passed validation")
    violations: List[str] = Field(default_factory=list, description="List of safety violations")
    filtered_content: str = Field("", description="Content after safety filtering")