# Customer Search Agent

A customer-facing search agent built with the Strands Framework and deployed on AWS AgentCore Runtime. The agent provides intelligent information retrieval for both authenticated customers and anonymous visitors.

## Features

- Natural language search using AWS Bedrock Knowledge Base
- Personalised results for authenticated users via AgentCore Gateway
- Content safety validation with AWS Bedrock Guardrails
- Structured JSON responses with summaries, personalisation, and citations
- Serverless deployment on AgentCore Runtime

## Architecture

The agent leverages:
- **Strands Framework**: AI agent development framework
- **AWS Bedrock Knowledge Base**: Vector database for content retrieval
- **AgentCore Runtime**: Serverless deployment platform
- **AgentCore Gateway**: MCP server for external tool integration
- **AWS Bedrock Guardrails**: Content safety and validation

## Project Structure

```
src/
├── customer_search_agent/
│   ├── __init__.py
│   ├── main.py              # Main agent entry point
│   ├── config.py            # Configuration management
│   ├── models/
│   │   ├── __init__.py
│   │   └── data_models.py   # Pydantic data models
│   └── services/            # Service implementations (to be added)
│       └── __init__.py
├── pyproject.toml           # Project configuration
├── requirements.txt         # Dependencies
├── agentcore.yaml          # AgentCore deployment config
└── README.md               # This file
```

## Environment Variables

Required environment variables for deployment:

- `KNOWLEDGE_BASE_ID`: AWS Bedrock Knowledge Base identifier
- `GATEWAY_MCP_URL`: AgentCore Gateway MCP endpoint
- `GUARDRAILS_ID`: Bedrock Guardrails configuration ID
- `AWS_REGION`: AWS region for service calls (default: us-east-1)

Optional configuration:

- `AI_MODEL`: AI model to use (default: claude-3-7-sonnet)
- `LOG_LEVEL`: Logging level (default: INFO)
- `GATEWAY_AUTH_REQUIRED`: Enable Gateway authentication (default: false)

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables in your deployment environment.

3. Deploy to AgentCore Runtime:
```bash
agentcore deploy agentcore.yaml
```

## Local Development

For local testing:

```bash
cd src
python -m customer_search_agent.main
```

## API

### Input Format
```json
{
    "search_query": "Natural language search query",
    "user_id": "optional-user-identifier"
}
```

### Output Format
```json
{
    "personalised": "User-specific content or empty string",
    "summary": "General summary from knowledge base",
    "links": ["source-url-1", "source-url-2"]
}
```

## Development

This project uses:
- **Black** for code formatting
- **isort** for import sorting
- **mypy** for type checking
- **pytest** for testing

Run formatting:
```bash
black src/
isort src/
```

Run type checking:
```bash
mypy src/
```

## License

This project is part of the customer search system implementation.