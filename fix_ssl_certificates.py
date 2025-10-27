#!/usr/bin/env python3
"""
SSL Certificate Fix Script for macOS Development Environment

This script helps resolve SSL certificate verification issues commonly encountered
on macOS when using Python applications that make HTTPS requests to AWS services.
"""

import os
import sys
import subprocess
import ssl
import certifi
import urllib.request
from pathlib import Path

def check_python_ssl_setup():
    """Check the current SSL setup in Python."""
    print("=== Python SSL Configuration ===")
    print(f"Python version: {sys.version}")
    print(f"SSL module version: {ssl.OPENSSL_VERSION}")
    print(f"SSL default verify paths: {ssl.get_default_verify_paths()}")
    print(f"Certifi bundle location: {certifi.where()}")
    
    # Test SSL connectivity
    print("\n=== Testing SSL Connectivity ===")
    test_urls = [
        "https://bedrock-runtime.us-east-1.amazonaws.com",
        "https://cognito-idp.us-east-1.amazonaws.com",
        "https://httpbin.org/get"
    ]
    
    for url in test_urls:
        try:
            response = urllib.request.urlopen(url, timeout=10)
            print(f"✅ {url} - SSL OK (status: {response.getcode()})")
        except Exception as e:
            print(f"❌ {url} - SSL Error: {e}")

def fix_python_certificates_macos():
    """Apply macOS-specific Python certificate fixes."""
    print("\n=== Applying macOS Certificate Fixes ===")
    
    # Check if we're on macOS
    if sys.platform != 'darwin':
        print("This fix is specifically for macOS. Skipping...")
        return
    
    # Method 1: Run the Install Certificates.command
    python_path = Path(sys.executable).parent.parent
    cert_command = python_path / "Install Certificates.command"
    
    if cert_command.exists():
        print(f"Found certificate installer: {cert_command}")
        try:
            result = subprocess.run([str(cert_command)], capture_output=True, text=True)
            if result.returncode == 0:
                print("✅ Successfully ran Install Certificates.command")
            else:
                print(f"❌ Install Certificates.command failed: {result.stderr}")
        except Exception as e:
            print(f"❌ Could not run Install Certificates.command: {e}")
    else:
        print("Install Certificates.command not found")
    
    # Method 2: Update certificates using pip
    print("\nUpdating certificates using pip...")
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "certifi"], check=True)
        print("✅ Successfully updated certifi package")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to update certifi: {e}")
    
    # Method 3: Set REQUESTS_CA_BUNDLE environment variable
    print("\nSetting certificate bundle environment variables...")
    ca_bundle_path = certifi.where()
    os.environ['REQUESTS_CA_BUNDLE'] = ca_bundle_path
    os.environ['SSL_CERT_FILE'] = ca_bundle_path
    print(f"✅ Set SSL_CERT_FILE and REQUESTS_CA_BUNDLE to: {ca_bundle_path}")

def install_development_ssl_bypass():
    """Install development SSL bypass configuration."""
    print("\n=== Installing Development SSL Bypass ===")
    print("⚠️  WARNING: This disables SSL verification for development only!")
    print("⚠️  DO NOT use in production environments!")
    
    # Create a development configuration file
    config_content = '''# Development SSL Configuration
# WARNING: This configuration disables SSL verification
# Only use in development environments!

export ENVIRONMENT=development
export PYTHONHTTPSVERIFY=0
export AWS_CA_BUNDLE=""
export COGNITO_DISABLE_SSL_VERIFICATION=true
'''
    
    config_file = Path("dev_ssl_config.sh")
    with open(config_file, 'w') as f:
        f.write(config_content)
    
    print(f"✅ Created development SSL configuration: {config_file}")
    print(f"To use: source {config_file}")
    
    # Set environment variables for current session
    os.environ['ENVIRONMENT'] = 'development'
    os.environ['PYTHONHTTPSVERIFY'] = '0'
    os.environ['AWS_CA_BUNDLE'] = ''
    os.environ['COGNITO_DISABLE_SSL_VERIFICATION'] = 'true'
    print("✅ Set environment variables for current Python session")

def main():
    """Main function to run all SSL fixes."""
    print("🔧 SSL Certificate Fix Script for macOS")
    print("=" * 50)
    
    # Check current SSL setup
    check_python_ssl_setup()
    
    # Ask user what they want to do
    print("\nChoose an option:")
    print("1. Try to fix SSL certificates properly (recommended for production)")
    print("2. Install development SSL bypass (quick fix for development)")
    print("3. Both (try fix first, then bypass if needed)")
    print("4. Just test current setup")
    
    choice = input("\nEnter your choice (1-4): ").strip()
    
    if choice in ['1', '3']:
        fix_python_certificates_macos()
        print("\n" + "="*50)
        check_python_ssl_setup()
    
    if choice in ['2', '3']:
        install_development_ssl_bypass()
    
    if choice == '4':
        print("Current setup tested above.")
    
    print("\n🎉 SSL configuration complete!")
    print("\nIf you still have SSL issues:")
    print("1. Restart your Python application")
    print("2. Try running: source dev_ssl_config.sh")
    print("3. Check that ENVIRONMENT=development is set")

if __name__ == "__main__":
    main()