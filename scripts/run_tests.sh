#!/bin/bash

# Test runner script
set -e

echo "🧪 Running EzyagoTrading Tests..."

# Install test dependencies
pip install pytest pytest-asyncio pytest-cov

# Run tests with coverage
pytest tests/ \
    --cov=app \
    --cov-report=html \
    --cov-report=term-missing \
    --cov-fail-under=70 \
    -v

echo "✅ Tests completed successfully!"
echo "📊 Coverage report generated in htmlcov/"