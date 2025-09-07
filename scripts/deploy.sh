#!/bin/bash

# Deployment script for EzyagoTrading
set -e

echo "🚀 EzyagoTrading Deployment Script"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT=${1:-"production"}
BRANCH=${2:-"main"}

echo -e "${BLUE}📋 Deployment Configuration:${NC}"
echo -e "   Environment: ${YELLOW}$ENVIRONMENT${NC}"
echo -e "   Branch: ${YELLOW}$BRANCH${NC}"

# Pre-deployment checks
echo -e "${BLUE}🔍 Running pre-deployment checks...${NC}"

# Check if we're in the right directory
if [ ! -f "app/main.py" ]; then
    echo -e "${RED}❌ Error: Please run this script from the project root directory${NC}"
    exit 1
fi

# Check if required files exist
required_files=("requirements.txt" "runtime.txt" "render.yaml" "Procfile")
for file in "${required_files[@]}"; do
    if [ ! -f "$file" ]; then
        echo -e "${RED}❌ Error: Required file $file not found${NC}"
        exit 1
    fi
done

# Check environment variables (for local testing)
if [ "$ENVIRONMENT" = "production" ]; then
    echo -e "${YELLOW}⚠️  Make sure these environment variables are set in your deployment platform:${NC}"
    echo "   - FIREBASE_CREDENTIALS_JSON"
    echo "   - FIREBASE_DATABASE_URL"
    echo "   - FIREBASE_WEB_API_KEY"
    echo "   - FIREBASE_WEB_AUTH_DOMAIN"
    echo "   - FIREBASE_WEB_PROJECT_ID"
    echo "   - FIREBASE_WEB_STORAGE_BUCKET"
    echo "   - FIREBASE_WEB_MESSAGING_SENDER_ID"
    echo "   - FIREBASE_WEB_APP_ID"
    echo "   - ENCRYPTION_KEY"
    echo "   - ADMIN_EMAIL"
    echo "   - PAYMENT_TRC20_ADDRESS"
fi

# Run tests before deployment
echo -e "${BLUE}🧪 Running tests before deployment...${NC}"
if [ -f "scripts/run_tests.sh" ]; then
    bash scripts/run_tests.sh
else
    pytest tests/ -v --tb=short
fi

# Check requirements.txt for security issues (optional)
echo -e "${BLUE}🔒 Checking for security vulnerabilities...${NC}"
if command -v safety > /dev/null; then
    safety check -r requirements.txt
else
    echo -e "${YELLOW}⚠️  'safety' not installed. Skipping security check.${NC}"
    echo -e "${YELLOW}   Install with: pip install safety${NC}"
fi

# Validate configuration files
echo -e "${BLUE}📝 Validating configuration files...${NC}"

# Check Python version in runtime.txt
if grep -q "python-3.11" runtime.txt; then
    echo -e "${GREEN}✅ Python version looks good${NC}"
else
    echo -e "${YELLOW}⚠️  Warning: Python version might not be optimal for deployment${NC}"
fi

# Check if critical dependencies are present
critical_deps=("fastapi" "uvicorn" "firebase-admin" "python-binance")
for dep in "${critical_deps[@]}"; do
    if grep -q "$dep" requirements.txt; then
        echo -e "${GREEN}✅ $dep found in requirements.txt${NC}"
    else
        echo -e "${RED}❌ Critical dependency $dep not found in requirements.txt${NC}"
        exit 1
    fi
done

# Git operations (if in a git repository)
if [ -d ".git" ]; then
    echo -e "${BLUE}📦 Preparing Git repository...${NC}"
    
    # Check if there are uncommitted changes
    if [ -n "$(git status --porcelain)" ]; then
        echo -e "${YELLOW}⚠️  Warning: You have uncommitted changes${NC}"
        echo -e "${YELLOW}   Consider committing them before deployment${NC}"
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo -e "${RED}❌ Deployment cancelled${NC}"
            exit 1
        fi
    fi
    
    # Show current branch and commit
    echo -e "${BLUE}📍 Current branch: ${YELLOW}$(git branch --show-current)${NC}"
    echo -e "${BLUE}📍 Latest commit: ${YELLOW}$(git log -1 --oneline)${NC}"
fi

# Deployment instructions
echo -e "${GREEN}✅ Pre-deployment checks passed!${NC}"
echo -e "${BLUE}🚀 Ready for deployment!${NC}"
echo
echo -e "${YELLOW}📋 Next steps for Render.com deployment:${NC}"
echo "1. Push your code to GitHub"
echo "2. Connect your GitHub repository to Render.com"
echo "3. Set environment variables in Render.com dashboard"
echo "4. Deploy!"
echo
echo -e "${YELLOW}📋 For manual deployment:${NC}"
echo "1. Make sure all environment variables are set"
echo "2. Run: uvicorn app.main:app --host 0.0.0.0 --port \$PORT"
echo
echo -e "${GREEN}🎉 Deployment script completed successfully!${NC}"
