# Development SSL Configuration
# WARNING: This configuration disables SSL verification
# Only use in development environments!

export ENVIRONMENT=development
export PYTHONHTTPSVERIFY=0
export AWS_CA_BUNDLE=""
export SSL_CERT_FILE=""
export COGNITO_DISABLE_SSL_VERIFICATION=true
export REQUESTS_CA_BUNDLE=""
export CURL_CA_BUNDLE=""

echo "✅ SSL bypass environment variables configured for development"
echo "⚠️  WARNING: SSL verification is disabled - NOT SAFE FOR PRODUCTION"
