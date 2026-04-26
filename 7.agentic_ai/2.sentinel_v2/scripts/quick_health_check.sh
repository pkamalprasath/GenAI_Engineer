#!/bin/bash
# SENTINEL Quick Health Check
# Run this to diagnose issues quickly
# Usage: bash scripts/quick_health_check.sh [investigation_id]

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

INV_ID="${1:-}"
API_URL="${SENTINEL_API_URL:-http://localhost:8003}"
TENANT_ID="${DEMO_TENANT_ID:-bank-acme}"
DB_URL="${DATABASE_URL}"

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}SENTINEL Health Check${NC}"
echo -e "${BLUE}============================================${NC}\n"

# 1. API Health
echo -e "${BLUE}[1] API Server${NC}"
if curl -s "$API_URL/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ API running at $API_URL${NC}"
else
    echo -e "${RED}✗ API not responding at $API_URL${NC}"
    echo "  Start API with: uvicorn sentinel.api.main:app --port 8003"
    exit 1
fi

# 2. Database
echo -e "\n${BLUE}[2] Database${NC}"
if psql "$DB_URL" -c "SELECT 1" > /dev/null 2>&1; then
    COUNT=$(psql "$DB_URL" -t -c "SELECT COUNT(*) FROM investigations")
    echo -e "${GREEN}✓ Database connected${NC}"
    echo "  Investigations: $COUNT"
else
    echo -e "${RED}✗ Database not responding${NC}"
    exit 1
fi

# 3. Decision Records
echo -e "\n${BLUE}[3] Decision Records${NC}"
DR_COUNT=$(psql "$DB_URL" -t -c "SELECT COUNT(*) FROM decision_records WHERE tenant_id='$TENANT_ID'")
echo "  Count: $DR_COUNT"
if [ "$DR_COUNT" -eq 0 ]; then
    echo -e "${YELLOW}⚠ No decision records found${NC}"
    echo "  Run: python scripts/verify_system.py --seed"
else
    echo -e "${GREEN}✓ Decision records exist${NC}"
fi

# 4. Specific Investigation (if provided)
if [ -n "$INV_ID" ]; then
    echo -e "\n${BLUE}[4] Investigation: $INV_ID${NC}"

    # Check exists
    STATUS=$(psql "$DB_URL" -t -c "SELECT status FROM investigations WHERE investigation_id='$INV_ID'" | xargs)
    if [ -z "$STATUS" ]; then
        echo -e "${RED}✗ Investigation not found${NC}"
        exit 1
    fi
    echo "  Status: $STATUS"

    # Check state_snapshot
    HAS_SNAPSHOT=$(psql "$DB_URL" -t -c "SELECT state_snapshot IS NOT NULL FROM investigations WHERE investigation_id='$INV_ID'" | xargs)
    if [ "$HAS_SNAPSHOT" = "t" ]; then
        echo -e "${GREEN}✓ State snapshot exists${NC}"
        VERDICT=$(psql "$DB_URL" -t -c "SELECT state_snapshot->>'compliance_verdict' FROM investigations WHERE investigation_id='$INV_ID'" | xargs)
        echo "  Verdict: $VERDICT"
    else
        echo -e "${YELLOW}⚠ State snapshot is NULL${NC}"
    fi

    # Check provenance nodes
    NODE_COUNT=$(psql "$DB_URL" -t -c "SELECT COUNT(*) FROM provenance_nodes WHERE content->>'investigation_id' = '$INV_ID'")
    echo "  Provenance nodes: $NODE_COUNT"
    if [ "$NODE_COUNT" -eq 0 ]; then
        echo -e "${YELLOW}⚠ No provenance nodes found${NC}"
    fi

    # Check case IDs
    CASE_COUNT=$(psql "$DB_URL" -t -c "SELECT jsonb_array_length(state_snapshot->'relevant_case_ids') FROM investigations WHERE investigation_id='$INV_ID'" | xargs)
    echo "  Relevant cases: $CASE_COUNT"
fi

# 5. System Resources (optional, for local runs)
echo -e "\n${BLUE}[5] System Health${NC}"

# Check Ollama
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Ollama running${NC}"
else
    echo -e "${YELLOW}⚠ Ollama not accessible at localhost:11434${NC}"
fi

# Check common processes
PROCS=0
if pgrep -f "uvicorn" > /dev/null; then
    PROCS=$((PROCS + 1))
    echo -e "${GREEN}✓ API process running${NC}"
fi

if pgrep -f "postgres" > /dev/null; then
    PROCS=$((PROCS + 1))
    echo -e "${GREEN}✓ PostgreSQL running${NC}"
fi

# 6. Summary
echo -e "\n${BLUE}============================================${NC}"
if [ $PROCS -gt 0 ]; then
    echo -e "${GREEN}System appears healthy${NC}"
else
    echo -e "${YELLOW}Some services may not be running${NC}"
fi
echo -e "${BLUE}============================================${NC}\n"

# Guidance
if [ -n "$INV_ID" ]; then
    if [ "$STATUS" = "queued" ]; then
        echo -e "${YELLOW}Investigation is queued. Run:${NC}"
        echo "  curl -X POST http://localhost:8003/api/v1/investigations/$INV_ID/execute-sync"
    elif [ "$STATUS" = "complete" ] && [ "$VERDICT" = "null" ]; then
        echo -e "${YELLOW}Investigation completed but no verdict. Run:${NC}"
        echo "  python scripts/verify_system.py"
        echo "  python scripts/verify_system.py --seed"
    fi
fi
