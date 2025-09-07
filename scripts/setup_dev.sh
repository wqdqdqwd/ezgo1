#!/bin/bash

# Development environment setup script for EzyagoTrading
set -e

echo "🛠️  EzyagoTrading Development Environment Setup"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if we're in the right directory
if [ ! -f "app/main.py" ]; then
    echo -e "${RED}❌ Error: Please run this script from the project root directory${NC}"
    exit 1
fi

# Check Python version
echo -e "${BLUE}🐍 Checking Python version...${NC}"
python_version=$(python3 --version 2>&1 | cut -d' ' -f2)
echo -e "${GREEN}✅ Python version: $python_version${NC}"

# Check if Python 3.11+ is available
if python3 -c "import sys; exit(0 if sys.version_info >= (3, 11) else 1)" 2>/dev/null; then
    echo -e "${GREEN}✅ Python 3.11+ detected${NC}"
else
    echo -e "${YELLOW}⚠️  Warning: Python 3.11+ recommended for best compatibility${NC}"
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo -e "${BLUE}📦 Creating virtual environment...${NC}"
    python3 -m venv venv
    echo -e "${GREEN}✅ Virtual environment created${NC}"
else
    echo -e "${GREEN}✅ Virtual environment already exists${NC}"
fi

# Activate virtual environment
echo -e "${BLUE}🔄 Activating virtual environment...${NC}"
source venv/bin/activate

# Upgrade pip
echo -e "${BLUE}⬆️  Upgrading pip...${NC}"
pip install --upgrade pip

# Install dependencies
echo -e "${BLUE}📦 Installing dependencies...${NC}"
pip install -r requirements.txt

# Install development dependencies
echo -e "${BLUE}🛠️  Installing development dependencies...${NC}"
pip install pytest pytest-asyncio pytest-cov pytest-mock black flake8 isort

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo -e "${BLUE}📝 Creating .env file from template...${NC}"
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "${YELLOW}⚠️  Please edit .env file with your actual configuration${NC}"
    else
        cat > .env << EOF
# Firebase Configuration (Required)
FIREBASE_CREDENTIALS_JSON={"type": "service_account", "project_id": "your-project"}
FIREBASE_DATABASE_URL=https://your-project.firebaseio.com
FIREBASE_WEB_API_KEY=your-web-api-key
FIREBASE_WEB_AUTH_DOMAIN=your-project.firebaseapp.com
FIREBASE_WEB_PROJECT_ID=your-project
FIREBASE_WEB_STORAGE_BUCKET=your-project.appspot.com
FIREBASE_WEB_MESSAGING_SENDER_ID=123456789
FIREBASE_WEB_APP_ID=1:123456789:web:abcdef

# Security (Required)
ENCRYPTION_KEY=your-32-byte-base64-encoded-key
ADMIN_EMAIL=admin@yourdomain.com

# Payment (Optional)
PAYMENT_TRC20_ADDRESS=your-trc20-wallet-address

# Application Settings
ENVIRONMENT=DEVELOPMENT
LOG_LEVEL=INFO
BOT_PRICE_USD=\$29.99
SERVER_IPS=18.156.158.53,18.156.42.200,52.59.103.54
EOF
        echo -e "${GREEN}✅ .env file created${NC}"
        echo -e "${YELLOW}⚠️  Please edit .env file with your actual configuration${NC}"
    fi
else
    echo -e "${GREEN}✅ .env file already exists${NC}"
fi

# Create necessary directories
echo -e "${BLUE}📁 Creating necessary directories...${NC}"
mkdir -p logs
mkdir -p reports
mkdir -p static
echo -e "${GREEN}✅ Directories created${NC}"

# Run tests to verify setup
echo -e "${BLUE}🧪 Running tests to verify setup...${NC}"
if python -m pytest tests/ -v --tb=short; then
    echo -e "${GREEN}✅ All tests passed!${NC}"
else
    echo -e "${YELLOW}⚠️  Some tests failed, but setup is complete${NC}"
fi

# Setup pre-commit hooks (optional)
echo -e "${BLUE}🔧 Setting up code formatting...${NC}"
cat > .pre-commit-config.yaml << EOF
repos:
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
        language_version: python3
  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort
        args: ["--profile", "black"]
  - repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
        args: [--max-line-length=88, --extend-ignore=E203]
EOF

# Install pre-commit if available
if command -v pre-commit > /dev/null; then
    pre-commit install
    echo -e "${GREEN}✅ Pre-commit hooks installed${NC}"
else
    echo -e "${YELLOW}⚠️  pre-commit not available. Install with: pip install pre-commit${NC}"
fi

# Final instructions
echo -e "${GREEN}🎉 Development environment setup completed!${NC}"
echo
echo -e "${BLUE}📋 Next steps:${NC}"
echo "1. Edit .env file with your Firebase configuration"
echo "2. Run the application: uvicorn app.main:app --reload"
echo "3. Open http://localhost:8000 in your browser"
echo "4. Run tests: bash scripts/run_tests.sh"
echo
echo -e "${BLUE}🔧 Useful commands:${NC}"
echo "  Start development server: uvicorn app.main:app --reload"
echo "  Run tests: pytest tests/"
echo "  Format code: black app/ tests/"
echo "  Check code style: flake8 app/ tests/"
echo "  Sort imports: isort app/ tests/"
echo
echo -e "${GREEN}✅ Happy coding! 🚀${NC}"
