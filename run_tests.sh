#!/bin/bash
# Setup and run JDECo API tests

echo "=========================================="
echo "JDECo API Test Suite Setup & Runner"
echo "=========================================="

# Check Python version
python_version=$(python3 --version 2>&1)
echo "Python version: $python_version"

# Install dependencies
echo ""
echo "Installing required dependencies..."
pip install -q aiohttp pycryptodome 2>/dev/null || pip3 install -q aiohttp pycryptodome

echo "✓ Dependencies installed"
echo ""

# Test 1: Dummy credentials
echo "=========================================="
echo "TEST 1: Running with DUMMY credentials"
echo "=========================================="
python3 test_api.py testuser testpass
test1_exit=$?

echo ""
echo "=========================================="
echo "TEST 1 COMPLETED"
echo "=========================================="

# Show instructions for real credentials
echo ""
echo "=========================================="
echo "TEST 2: Real Credentials (if available)"
echo "=========================================="
echo ""
echo "To run with real credentials, use:"
echo "  python3 test_api.py <username> <password> [agreement_number]"
echo ""
echo "Example:"
echo "  python3 test_api.py user@example.com mypassword A123456"
echo ""
echo "=========================================="
