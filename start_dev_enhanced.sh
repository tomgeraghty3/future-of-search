#!/bin/bash

# Enhanced development startup script for Customer Search Agent
# This script sets up the proper environment and starts the application

echo "🚀 Starting Customer Search Agent Development Environment"
echo "================================================="

# Set development environment variables
export ENVIRONMENT=development
export PYTHONHTTPSVERIFY=0
export AWS_CA_BUNDLE=""
export REQUESTS_CA_BUNDLE=""
export CURL_CA_BUNDLE=""

# Disable SSL verification for development
export COGNITO_DISABLE_SSL_VERIFICATION=true

echo "✓ Environment variables set for development"
echo "  ENVIRONMENT: $ENVIRONMENT"
echo "  PYTHONHTTPSVERIFY: $PYTHONHTTPSVERIFY"
echo "  SSL verification disabled for development"

# Check if we're in the correct directory
if [ ! -f "main.py" ]; then
    echo "❌ Error: main.py not found. Please run this script from the future-of-search directory."
    exit 1
fi

# Check if pipenv is available
if ! command -v pipenv &> /dev/null; then
    echo "❌ Error: pipenv not found. Please install pipenv first:"
    echo "  pip install pipenv"
    exit 1
fi

# Install dependencies if needed
if [ ! -f "Pipfile.lock" ]; then
    echo "📦 Installing dependencies..."
    pipenv install
fi

echo "🔧 Applying SSL fixes for development environment..."

# Start the application
echo "🚀 Starting Customer Search Agent..."
echo "   Application will be available at: http://localhost:8080"
echo "   Health check endpoint: http://localhost:8080/health"
echo ""
echo "Press Ctrl+C to stop the application"
echo "================================================="

pipenv run python main.py