"""
Guardrails Tool for AWS Bedrock Guardrails integration.

This tool validates content for safety and coherence using AWS Bedrock Guardrails
before responses are returned to users.
"""

import boto3
import logging
from typing import Dict, Any
from strands.tools import tool, ToolContext
from botocore.exceptions import ClientError, BotoCoreError
import json

logger = logging.getLogger(__name__)


@tool(context=True)
async def guardrails_tool(response_content: str, tool_context: ToolContext) -> Dict[str, Any]:
    """
    Validate response content using AWS Bedrock Guardrails for safety and coherence.
    
    This tool ensures all agent responses meet safety standards and content quality
    requirements before being returned to users.
    
    Args:
        response_content: The generated response content to validate
        tool_context: Provides access to agent context and invocation state
                     - tool_context.invocation_state: Contains guardrail configuration
                     - tool_context.tool_use: Current tool invocation details
    
    Returns:
        Dict containing:
        - is_valid: Boolean indicating if content passed validation
        - validated_content: The approved content (may be filtered)
        - validation_message: Human-readable validation result
    
    Raises:
        Exception: For unrecoverable validation errors
    """
    try:
        # Extract configuration from invocation state
        guardrail_id = tool_context.invocation_state.get("guardrail_id")
        guardrail_version = tool_context.invocation_state.get("guardrail_version", "DRAFT")
        request_id = tool_context.invocation_state.get("request_id", "unknown")
        
        if not guardrail_id:
            logger.error(f"Request {request_id}: Missing guardrail_id in invocation state")
            raise ValueError("Guardrail configuration not found")
        
        # Initialize Bedrock Runtime client
        bedrock_runtime = boto3.client('bedrock-runtime')
        
        logger.info(f"Request {request_id}: Validating content with guardrail {guardrail_id}")
        
        # Apply guardrail validation
        response = bedrock_runtime.apply_guardrail(
            guardrailIdentifier=guardrail_id,
            guardrailVersion=guardrail_version,
            source='OUTPUT',  # We're validating agent output
            content=[
                {
                    'text': {
                        'text': response_content
                    }
                }
            ]
        )
        
        # Parse guardrail response
        action = response.get('action', 'NONE')
        outputs = response.get('outputs', [])
        assessments = response.get('assessments', [])
        
        if action == 'GUARDRAIL_INTERVENED':
            # Content was blocked by guardrails
            logger.warning(f"Request {request_id}: Content blocked by guardrails")
            
            # Extract policy violations for logging
            violations = _extract_policy_violations(assessments)
            logger.warning(f"Request {request_id}: Policy violations: {violations}")
            
            return {
                "is_valid": False,
                "validated_content": "",
                "validation_message": "Content blocked due to safety policy violations"
            }
        
        elif action == 'NONE':
            # Content passed validation
            validated_content = response_content
            
            # Check if content was modified (filtered)
            if outputs and len(outputs) > 0:
                output_text = outputs[0].get('text', response_content)
                if output_text != response_content:
                    validated_content = output_text
                    logger.info(f"Request {request_id}: Content was filtered by guardrails")
            
            logger.info(f"Request {request_id}: Content validation successful")
            
            return {
                "is_valid": True,
                "validated_content": validated_content,
                "validation_message": "Content approved"
            }
        
        else:
            # Unexpected action
            logger.error(f"Request {request_id}: Unexpected guardrail action: {action}")
            return {
                "is_valid": False,
                "validated_content": "",
                "validation_message": "Validation failed due to unexpected response"
            }
    
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_message = e.response.get('Error', {}).get('Message', str(e))
        
        logger.error(f"Request {request_id}: AWS ClientError - {error_code}: {error_message}")
        
        if error_code == 'ThrottlingException':
            return {
                "is_valid": False,
                "validated_content": "",
                "validation_message": "Service temporarily unavailable due to high demand"
            }
        elif error_code == 'ValidationException':
            return {
                "is_valid": False,
                "validated_content": "",
                "validation_message": "Invalid content format for validation"
            }
        elif error_code == 'ResourceNotFoundException':
            logger.error(f"Request {request_id}: Guardrail {guardrail_id} not found")
            return {
                "is_valid": False,
                "validated_content": "",
                "validation_message": "Validation service configuration error"
            }
        elif error_code == 'AccessDeniedException':
            logger.error(f"Request {request_id}: Access denied to guardrail {guardrail_id}")
            return {
                "is_valid": False,
                "validated_content": "",
                "validation_message": "Validation service access denied"
            }
        else:
            return {
                "is_valid": False,
                "validated_content": "",
                "validation_message": "Validation service temporarily unavailable"
            }
    
    except BotoCoreError as e:
        logger.error(f"Request {request_id}: BotoCoreError - {str(e)}")
        return {
            "is_valid": False,
            "validated_content": "",
            "validation_message": "Network error during validation"
        }
    
    except Exception as e:
        logger.error(f"Request {request_id}: Unexpected error during guardrail validation: {str(e)}")
        return {
            "is_valid": False,
            "validated_content": "",
            "validation_message": "Validation service temporarily unavailable"
        }


def _extract_policy_violations(assessments: list) -> list:
    """
    Extract policy violation details from guardrail assessments.
    
    Args:
        assessments: List of assessment objects from guardrail response
    
    Returns:
        List of violation descriptions
    """
    violations = []
    
    for assessment in assessments:
        # Topic policy violations
        if 'topicPolicy' in assessment:
            topics = assessment['topicPolicy'].get('topics', [])
            for topic in topics:
                topic_name = topic.get('name', 'Unknown Topic')
                action = topic.get('action', 'BLOCKED')
                violations.append(f"Topic Policy: {topic_name} ({action})")
        
        # Content policy violations (hate, violence, etc.)
        if 'contentPolicy' in assessment:
            filters = assessment['contentPolicy'].get('filters', [])
            for filter_item in filters:
                filter_type = filter_item.get('type', 'Unknown')
                action = filter_item.get('action', 'BLOCKED')
                confidence = filter_item.get('confidence', 'UNKNOWN')
                violations.append(f"Content Policy: {filter_type} (confidence: {confidence}, action: {action})")
        
        # Word policy violations (custom blocked words)
        if 'wordPolicy' in assessment:
            custom_words = assessment['wordPolicy'].get('customWords', [])
            managed_word_lists = assessment['wordPolicy'].get('managedWordLists', [])
            
            for word in custom_words:
                violations.append(f"Word Policy: Custom word blocked")
            
            for word_list in managed_word_lists:
                violations.append(f"Word Policy: Managed word list violation")
        
        # Sensitive information policy violations (PII)
        if 'sensitiveInformationPolicy' in assessment:
            pii_entities = assessment['sensitiveInformationPolicy'].get('piiEntities', [])
            regexes = assessment['sensitiveInformationPolicy'].get('regexes', [])
            
            for pii in pii_entities:
                pii_type = pii.get('type', 'Unknown')
                action = pii.get('action', 'BLOCKED')
                violations.append(f"PII Policy: {pii_type} ({action})")
            
            for regex in regexes:
                name = regex.get('name', 'Custom Pattern')
                action = regex.get('action', 'BLOCKED')
                violations.append(f"Regex Policy: {name} ({action})")
    
    return violations