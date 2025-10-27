#!/bin/bash

# Startup script for Future of Search with SSL fixes
# This script ensures all SSL bypass settings are configured before starting the application

echo "=== Future of Search - Development Startup ==="
echo "Configuring SSL bypass for development environment..."

# Source the SSL configuration
source dev_ssl_config.sh

# Additional Python SSL configuration
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

echo ""
echo "Environment configured with the following SSL bypass settings:"
echo "- ENVIRONMENT: $ENVIRONMENT"
echo "- PYTHONHTTPSVERIFY: $PYTHONHTTPSVERIFY"
echo "- AWS_CA_BUNDLE: $AWS_CA_BUNDLE"
echo "- SSL_CERT_FILE: $SSL_CERT_FILE"
echo "- COGNITO_DISABLE_SSL_VERIFICATION: $COGNITO_DISABLE_SSL_VERIFICATION"
echo ""

# Start the application
echo "Starting the application..."
if [ "$1" = "test" ]; then
    echo "Running in test mode..."
    "/Users/vijay.mallajosulavenkata/ML Projects/Client Projects/SP Hackathon/.venv/bin/python" test_personalisation_direct.py
else
    echo "Starting main application..."
    "/Users/vijay.mallajosulavenkata/ML Projects/Client Projects/SP Hackathon/.venv/bin/python" main.py
fi