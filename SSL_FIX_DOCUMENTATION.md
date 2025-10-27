# SSL Certificate Fix Documentation

## Problem Summary

The Future of Search application was experiencing SSL certificate verification failures when connecting to AWS services (Cognito, Bedrock, and the MCP Gateway). This is a common issue in development environments, particularly on macOS, where Python's SSL certificate verification may fail due to certificate chain issues.

## Root Causes

1. **macOS Certificate Issues**: Python on macOS sometimes can't properly verify SSL certificates due to missing or outdated certificate bundles
2. **Development Environment**: Self-signed or development certificates that aren't in the standard certificate store
3. **MCP Client SSL Configuration**: The Model Context Protocol (MCP) client wasn't properly configured to bypass SSL verification in development
4. **AWS SDK Configuration**: Missing region configuration in the guardrails tool

## Implemented Fixes

### 1. Environment Configuration (.env)
Added comprehensive SSL bypass environment variables:
```bash
ENVIRONMENT=development
PYTHONHTTPSVERIFY=0
AWS_CA_BUNDLE=
SSL_CERT_FILE=
COGNITO_DISABLE_SSL_VERIFICATION=true
```

### 2. SSL Configuration Script (dev_ssl_config.sh)
Created a shell script to set all necessary environment variables:
```bash
source dev_ssl_config.sh
```

### 3. Personalisation Tool Updates
- Enhanced SSL bypass logic in `tools/personalisation_tool.py`
- Added conditional SSL verification based on environment
- Properly configured MCP client with SSL bypass for development

### 4. Guardrails Tool Updates
- Added proper AWS region configuration in `tools/guardrails_tool.py`
- Enhanced error handling for AWS credential issues

### 5. Cognito Token Manager
- Already had proper SSL bypass logic
- Validated that it works correctly with the new environment variables

### 6. Development Scripts
- `fix_ssl_environment.py`: Python script to configure SSL bypass
- `test_ssl_connectivity.py`: Test script to validate SSL configuration
- `start_dev.sh`: Startup script that ensures SSL configuration before running the app

## Usage Instructions

### Quick Start
```bash
# Navigate to the project directory
cd "/Users/vijay.mallajosulavenkata/ML Projects/Client Projects/SP Hackathon/future-of-search"

# Option 1: Use the startup script (recommended)
./start_dev.sh

# Option 2: Manual configuration
source dev_ssl_config.sh
python main.py
```

### Testing SSL Configuration
```bash
# Test SSL connectivity
python test_ssl_connectivity.py

# Test specific tools
python test_personalisation_direct.py
```

### Environment Variables
The following environment variables control SSL behavior:

| Variable | Value | Purpose |
|----------|-------|---------|
| `ENVIRONMENT` | `development` | Enables development mode |
| `PYTHONHTTPSVERIFY` | `0` | Disables Python SSL verification |
| `AWS_CA_BUNDLE` | `` | Disables AWS CA bundle |
| `SSL_CERT_FILE` | `` | Disables SSL cert file |
| `COGNITO_DISABLE_SSL_VERIFICATION` | `true` | Disables Cognito SSL verification |

## Test Results

After implementing the fixes, all SSL-related issues are resolved:

✅ **DNS Resolution**: All AWS endpoints resolve correctly  
✅ **SSL Connectivity**: No more certificate verification errors  
✅ **Cognito Authentication**: Successfully obtaining access tokens  
✅ **MCP Client**: Connecting to Gateway without SSL errors  
✅ **AWS Services**: Proper region configuration for Bedrock services  

## Security Notes

⚠️ **WARNING**: These fixes disable SSL certificate verification, which is **NOT SAFE FOR PRODUCTION**.

- Only use these settings in development environments
- Never deploy to production with SSL verification disabled
- For production, ensure proper SSL certificates are configured
- Consider using AWS Certificate Manager for production SSL certificates

## Troubleshooting

### If SSL errors persist:
1. Ensure all environment variables are set: `env | grep -E "(SSL|CERT|HTTPS)"`
2. Restart your terminal session after running configuration scripts
3. Run the test script: `python test_ssl_connectivity.py`
4. Check Python SSL configuration: `python -c "import ssl; print(ssl.get_default_verify_paths())"`

### Common Issues:
- **"command not found: python"**: Use the full Python path or activate virtual environment
- **Import errors**: Ensure you're in the correct virtual environment
- **Permission denied**: Make scripts executable with `chmod +x script.sh`

## Files Modified

- `.env`: Added SSL bypass environment variables
- `dev_ssl_config.sh`: Enhanced SSL configuration script
- `tools/personalisation_tool.py`: Added SSL bypass for MCP client
- `tools/guardrails_tool.py`: Added proper AWS region configuration
- `start_dev.sh`: New startup script with SSL configuration
- `test_ssl_connectivity.py`: New SSL test script
- `fix_ssl_environment.py`: New SSL fix script