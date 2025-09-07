#!/bin/bash

# Firebase Realtime Database backup script for EzyagoTrading
set -e

echo "💾 EzyagoTrading Database Backup Script"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BACKUP_DIR="backups"
DATE=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="ezyago_backup_$DATE.json"

# Check if Firebase CLI is installed
if ! command -v firebase &> /dev/null; then
    echo -e "${RED}❌ Firebase CLI not found${NC}"
    echo -e "${YELLOW}📦 Install Firebase CLI:${NC}"
    echo "   npm install -g firebase-tools"
    echo "   or visit: https://firebase.google.com/docs/cli"
    exit 1
fi

# Check if logged in to Firebase
if ! firebase projects:list &> /dev/null; then
    echo -e "${YELLOW}🔐 Please login to Firebase CLI:${NC}"
    firebase login
fi

# Create backup directory
mkdir -p "$BACKUP_DIR"

echo -e "${BLUE}📋 Backup Configuration:${NC}"
echo -e "   Backup directory: ${YELLOW}$BACKUP_DIR${NC}"
echo -e "   Backup file: ${YELLOW}$BACKUP_FILE${NC}"
echo -e "   Timestamp: ${YELLOW}$DATE${NC}"

# Get Firebase project ID from environment or prompt
if [ -z "$FIREBASE_PROJECT_ID" ]; then
    echo -e "${YELLOW}🔧 Firebase project ID not found in environment${NC}"
    read -p "Enter your Firebase project ID: " FIREBASE_PROJECT_ID
fi

echo -e "${BLUE}🔄 Starting backup process...${NC}"

# Export users data
echo -e "${BLUE}👥 Backing up users data...${NC}"
firebase database:get /users --project "$FIREBASE_PROJECT_ID" --pretty > "$BACKUP_DIR/users_$DATE.json"
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Users data backed up successfully${NC}"
else
    echo -e "${RED}❌ Failed to backup users data${NC}"
fi

# Export trades data
echo -e "${BLUE}💹 Backing up trades data...${NC}"
firebase database:get /trades --project "$FIREBASE_PROJECT_ID" --pretty > "$BACKUP_DIR/trades_$DATE.json"
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Trades data backed up successfully${NC}"
else
    echo -e "${RED}❌ Failed to backup trades data${NC}"
fi

# Export complete database
echo -e "${BLUE}🗄️  Backing up complete database...${NC}"
firebase database:get / --project "$FIREBASE_PROJECT_ID" --pretty > "$BACKUP_DIR/$BACKUP_FILE"
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Complete database backed up successfully${NC}"
else
    echo -e "${RED}❌ Failed to backup complete database${NC}"
    exit 1
fi

# Create compressed archive
echo -e "${BLUE}🗜️  Creating compressed archive...${NC}"
tar -czf "$BACKUP_DIR/ezyago_backup_$DATE.tar.gz" -C "$BACKUP_DIR" \
    "users_$DATE.json" \
    "trades_$DATE.json" \
    "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Compressed archive created${NC}"
    
    # Remove individual JSON files to save space
    rm "$BACKUP_DIR/users_$DATE.json" \
       "$BACKUP_DIR/trades_$DATE.json" \
       "$BACKUP_DIR/$BACKUP_FILE"
    
    echo -e "${GREEN}✅ Cleanup completed${NC}"
else
    echo -e "${RED}❌ Failed to create compressed archive${NC}"
fi

# Calculate backup size
BACKUP_SIZE=$(du -h "$BACKUP_DIR/ezyago_backup_$DATE.tar.gz" | cut -f1)

# Backup summary
echo -e "${GREEN}🎉 Backup completed successfully!${NC}"
echo -e "${BLUE}📊 Backup Summary:${NC}"
echo -e "   File: ${YELLOW}$BACKUP_DIR/ezyago_backup_$DATE.tar.gz${NC}"
echo -e "   Size: ${YELLOW}$BACKUP_SIZE${NC}"
echo -e "   Date: ${YELLOW}$(date)${NC}"

# Cleanup old backups (keep last 7 days)
echo -e "${BLUE}🧹 Cleaning up old backups (keeping last 7 days)...${NC}"
find "$BACKUP_DIR" -name "ezyago_backup_*.tar.gz" -mtime +7 -delete
echo -e "${GREEN}✅ Old backups cleaned up${NC}"

# Optional: Upload to cloud storage
echo -e "${YELLOW}💡 Tip: Consider uploading backups to cloud storage for extra safety${NC}"
echo -e "${YELLOW}   Examples: Google Drive, AWS S3, Dropbox, etc.${NC}"

echo -e "${GREEN}✅ Backup process completed!${NC}"
