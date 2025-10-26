# Gateway Authentication Setup Guide

This guide walks you through setting up Cognito authentication for your AgentCore Gateway MCP connection.

## Prerequisites

1. **Existing Cognito User Pool**: You mentioned you already have one
2. **AgentCore Gateway**: Already deployed and configured
3. **Python Environment**: With required dependencies installed

## Step 1: Configure Your Cognito User Pool App Client

Your User Pool needs an app client configured for **client credentials flow** (machine-to-machine authentication).

### Option A: AWS Console

1. Go to **Amazon Cognito** → **User Pools** → **Your Pool**
2. Navigate to **App Integration** → **App Clients**
3. Create a new app client or edit existing one with these settings:
   - **App client name**: `gateway-mcp-client` (or your preferred name)
   - **Generate client secret**: ✅ **Yes** (required for client credentials)
   - **Authentication flows**: Enable **Client credentials**
   - **OAuth 2.0 grant types**: Enable **Client credentials**
   - **OAuth 2.0 scopes**: Enable scopes you need (e.g., `openid`, `profile`, `email`)

### Option B: AWS CLI

```bash
# Create new app client with client credentials flow
aws cognito-idp create-user-pool-client \
  --user-pool-id YOUR_USER_POOL_ID \
  --client-name "gateway-mcp-client" \
  --generate-secret \
  --explicit-auth-flows "ALLOW_CLIENT_CREDENTIALS" \
  --supported-identity-providers "COGNITO" \
  --allowed-o-auth-flows "client_credentials" \
  --allowed-o-auth-scopes "openid" "profile" "email"

# Or update existing app client
aws cognito-idp update-user-pool-client \
  --user-pool-id YOUR_USER_POOL_ID \
  --client-id YOUR_CLIENT_ID \
  --generate-secret \
  --explicit-auth-flows "ALLOW_CLIENT_CREDENTIALS" \
  --supported-identity-providers "COGNITO" \
  --allowed-o-auth-flows "client_credentials" \
  --allowed-o-auth-scopes "openid" "profile" "email"
```

## Step 2: Set Up Cognito Domain (if not already done)

Your User Pool needs a domain for OAuth endpoints:

### Option A: AWS Console
1. Go to **App Integration** → **Domain**
2. Create a domain: `your-domain-prefix` (will become `your-domain-prefix.auth.region.amazoncognito.com`)

### Option B: AWS CLI
```bash
aws cognito-idp create-user-pool-domain \
  --domain your-domain-prefix \
  --user-pool-id YOUR_USER_POOL_ID
```

## Step 3: Configure Environment Variables

Update your `.env` file with the Cognito configuration:

```env
# Existing configuration...
GATEWAY_MCP_URL=https://your-gateway-id.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp

# Add Cognito configuration
COGNITO_USER_POOL_ID=us-east-1_XXXXXXXXX
COGNITO_CLIENT_ID=your_app_client_id
COGNITO_CLIENT_SECRET=your_app_client_secret
COGNITO_DOMAIN=your-domain-prefix
COGNITO_REGION=us-east-1
COGNITO_SCOPE=openid
```

### Finding Your Values:

- **COGNITO_USER_POOL_ID**: In Cognito console → User Pools → Your Pool → General Settings
- **COGNITO_CLIENT_ID**: In App Integration → App Clients → Your Client → Client ID
- **COGNITO_CLIENT_SECRET**: In App Integration → App Clients → Your Client → Show Details
- **COGNITO_DOMAIN**: The prefix you created (without `.auth.region.amazoncognito.com`)
- **COGNITO_REGION**: AWS region where your User Pool is located

## Step 4: Test the Authentication

Run the standalone test script to verify everything is working:

```bash
python test_gateway_auth.py
```

This will:
1. Test Cognito token retrieval
2. Test Gateway MCP connection with authentication
3. List available tools from the Gateway

### Expected Output:
```
🚀 Starting Gateway Authentication Test
=== Testing Cognito Token Manager ===
Cognito configuration found:
  user_pool_id: us-east-1_XXXXXXXXX
  client_id: your_client_id
  ...
✓ Successfully obtained access token

=== Testing Gateway MCP Connection ===
✓ MCP session established
✓ Successfully discovered X tools:
  1. tool_name: description
  ...
🎉 All tests passed! Gateway authentication is working correctly.
```

## Step 5: Test with Main Application

Once the standalone test passes, test with your main application:

```bash
python main.py
```

The main application will now use Cognito authentication when connecting to the Gateway.

## Troubleshooting

### 401 Unauthorized Error
- **Check App Client Configuration**: Ensure client credentials flow is enabled
- **Verify Scopes**: Make sure your app client has the required OAuth scopes
- **Check Domain**: Ensure your User Pool has a domain configured
- **Validate Credentials**: Double-check client ID and secret

### Token Request Fails
- **Network Connectivity**: Ensure you can reach `*.auth.region.amazoncognito.com`
- **Client Secret**: Verify the client secret is correct (regenerate if needed)
- **Region Mismatch**: Ensure COGNITO_REGION matches your User Pool's region

### Gateway Still Returns 401
- **Gateway Configuration**: The Gateway must be configured to accept your Cognito User Pool
- **Discovery URL**: Gateway needs the correct discovery URL for your User Pool
- **Token Validation**: Gateway validates tokens using your User Pool's public keys

## Gateway Configuration

If you control the Gateway configuration, ensure it's set up with your Cognito User Pool:

```python
# When creating the Gateway, use your existing Cognito User Pool
authorizer_config = {
    "customJWTAuthorizer": {
        "allowedClients": ["YOUR_CLIENT_ID"], 
        "discoveryUrl": "https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/openid-configuration"
    }
}
```

## Security Notes

- **Client Secret**: Keep your client secret secure and never commit it to version control
- **Token Expiry**: Tokens are automatically refreshed by the token manager
- **Scopes**: Only request the minimum scopes needed for your application
- **Network Security**: Use HTTPS for all communications

## Next Steps

Once authentication is working:
1. The personalisation_tool will automatically use authenticated connections
2. All Gateway MCP calls will include proper Bearer tokens
3. You can focus on building your agent functionality

For questions or issues, check the logs for detailed error messages and refer to the AWS Cognito documentation.