#!/bin/bash

# System monitoring script for EzyagoTrading
set -e

echo "📊 EzyagoTrading System Monitor"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
API_URL=${1:-"http://localhost:8000"}
CHECK_INTERVAL=${2:-30}

echo -e "${BLUE}📋 Monitor Configuration:${NC}"
echo -e "   API URL: ${YELLOW}$API_URL${NC}"
echo -e "   Check interval: ${YELLOW}${CHECK_INTERVAL}s${NC}"
echo -e "   Press Ctrl+C to stop monitoring"
echo

# Function to check API health
check_health() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    # Health check
    if curl -s -f "$API_URL/health" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ [$timestamp] API Health: OK${NC}"
        
        # Get detailed health info
        health_response=$(curl -s "$API_URL/health" 2>/dev/null)
        if [ $? -eq 0 ]; then
            echo -e "${CYAN}   Status: $(echo "$health_response" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)${NC}"
            echo -e "${CYAN}   Version: $(echo "$health_response" | grep -o '"version":"[^"]*"' | cut -d'"' -f4)${NC}"
        fi
    else
        echo -e "${RED}❌ [$timestamp] API Health: FAILED${NC}"
        return 1
    fi
}

# Function to check metrics
check_metrics() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    if curl -s -f "$API_URL/metrics" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ [$timestamp] Metrics: Available${NC}"
        
        # Extract some key metrics
        metrics_response=$(curl -s "$API_URL/metrics" 2>/dev/null)
        if [ $? -eq 0 ]; then
            # Active bots
            active_bots=$(echo "$metrics_response" | grep "active_bots " | tail -1 | awk '{print $2}')
            if [ ! -z "$active_bots" ]; then
                echo -e "${CYAN}   Active bots: $active_bots${NC}"
            fi
            
            # Total API requests
            api_requests=$(echo "$metrics_response" | grep "api_requests_total " | tail -1 | awk '{print $2}')
            if [ ! -z "$api_requests" ]; then
                echo -e "${CYAN}   Total API requests: $api_requests${NC}"
            fi
        fi
    else
        echo -e "${YELLOW}⚠️  [$timestamp] Metrics: Not available${NC}"
    fi
}

# Function to check system resources (if running locally)
check_system_resources() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    echo -e "${PURPLE}📊 [$timestamp] System Resources:${NC}"
    
    # CPU usage
    if command -v top > /dev/null; then
        cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
        echo -e "${CYAN}   CPU Usage: ${cpu_usage}%${NC}"
    fi
    
    # Memory usage
    if command -v free > /dev/null; then
        memory_info=$(free -h | grep "Mem:")
        memory_used=$(echo $memory_info | awk '{print $3}')
        memory_total=$(echo $memory_info | awk '{print $2}')
        echo -e "${CYAN}   Memory: $memory_used / $memory_total${NC}"
    fi
    
    # Disk usage
    if command -v df > /dev/null; then
        disk_usage=$(df -h / | tail -1 | awk '{print $5}')
        echo -e "${CYAN}   Disk Usage: $disk_usage${NC}"
    fi
    
    # Load average
    if [ -f "/proc/loadavg" ]; then
        load_avg=$(cat /proc/loadavg | awk '{print $1, $2, $3}')
        echo -e "${CYAN}   Load Average: $load_avg${NC}"
    fi
}

# Function to check process status
check_process_status() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    # Check if uvicorn process is running
    if pgrep -f "uvicorn.*app.main:app" > /dev/null; then
        echo -e "${GREEN}✅ [$timestamp] Uvicorn process: Running${NC}"
        
        # Get process info
        pid=$(pgrep -f "uvicorn.*app.main:app" | head -1)
        if [ ! -z "$pid" ]; then
            cpu_percent=$(ps -p $pid -o %cpu --no-headers 2>/dev/null || echo "N/A")
            mem_percent=$(ps -p $pid -o %mem --no-headers 2>/dev/null || echo "N/A")
            echo -e "${CYAN}   PID: $pid, CPU: ${cpu_percent}%, Memory: ${mem_percent}%${NC}"
        fi
    else
        echo -e "${RED}❌ [$timestamp] Uvicorn process: Not running${NC}"
    fi
}

# Function to run all checks
run_checks() {
    echo -e "${BLUE}🔍 Running system checks...${NC}"
    echo
    
    check_health
    echo
    
    check_metrics
    echo
    
    check_process_status
    echo
    
    check_system_resources
    echo
    
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo
}

# Trap Ctrl+C
trap 'echo -e "\n${YELLOW}👋 Monitoring stopped${NC}"; exit 0' INT

# Main monitoring loop
echo -e "${GREEN}🚀 Starting monitoring...${NC}"
echo

while true; do
    run_checks
    sleep $CHECK_INTERVAL
done
