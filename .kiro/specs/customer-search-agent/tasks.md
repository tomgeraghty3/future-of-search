# Implementation Plan

- [x] 1. Set up project structure and core configuration
  - Create directory structure for AgentCore Runtime deployment
  - Implement configuration management class for environment variables
  - Set up requirements.txt with all necessary dependencies
  - Create main.py with BedrockAgentCoreApp wrapper and entrypoint decorator
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 2. Implement Knowledge Tool for Bedrock Knowledge Base integration
  - Create knowledge_tool.py with @tool decorator and ToolContext support
  - Implement AWS Bedrock Knowledge Base client using boto3
  - Add RetrieveAndGenerate API integration for semantic search
  - Implement citation extraction and link parsing from response metadata
  - Add error handling for no results found, service unavailable, and invalid queries
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 3. Implement Guardrails Tool for content validation
  - Create guardrails_tool.py with @tool decorator and ToolContext support
  - Implement AWS Bedrock Guardrails client using boto3
  - Add ApplyGuardrail API integration for safety and coherence validation
  - Implement error handling for content blocked, service unavailable, and timeout scenarios
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [x] 4. Implement Personalisation Tool with MCP Gateway integration
  - Create personalisation_tool.py with @tool decorator and ToolContext support
  - Implement MCP client using Strands MCPClient and streamablehttp_client
  - Add tool discovery functionality using list_tools_sync method
  - Implement semantic tool matching logic for search topics
  - Add MCP tool invocation with user_id and search query parameters
  - Implement error handling for gateway unavailable, no matching tools, and tool execution failures
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [x] 5. Create main Customer Search Agent class
  - Implement CustomerSearchAgent class with true agent reasoning capabilities
  - Create comprehensive system prompt defining agent role, tools, and response format
  - Implement search method with dynamic tool usage based on agent reasoning
  - Add invocation_state management for passing configuration to tools
  - Implement response parsing and JSON formatting logic
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4, 2.5_

- [x] 6. Integrate all components and implement AgentCore Runtime deployment structure
  - Wire together all tools in the main agent configuration
  - Implement proper error handling and logging throughout the application
  - Create deployment-ready main.py with @app.entrypoint decorator
  - Ensure proper MCP session management within AgentCore Runtime context
  - Add correlation ID generation for request tracing
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 6.1, 6.2, 6.3, 6.4, 6.5_

- [ ]* 7. Create basic validation and testing utilities
  - Implement input validation for search topics and user IDs
  - Create mock implementations for local development and testing
  - Add basic response format validation
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_