#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== Blue/Green Failover Test Script ===${NC}\n"

# Function to test endpoint and extract headers
test_endpoint() {
    local url=$1
    echo -e "${YELLOW}Testing: $url${NC}"
    response=$(curl -s -i "$url")
    
    pool=$(echo "$response" | grep -i "X-App-Pool:" | awk '{print $2}' | tr -d '\r')
    release=$(echo "$response" | grep -i "X-Release-Id:" | awk '{print $2}' | tr -d '\r')
    status=$(echo "$response" | grep "HTTP" | awk '{print $2}')
    
    echo -e "  Status: $status"
    echo -e "  Pool: $pool"
    echo -e "  Release: $release"
    echo ""
}

# Step 1: Test normal state (should be Blue)
echo -e "${GREEN}Step 1: Testing Normal State (Blue should be active)${NC}"
test_endpoint "http://localhost:8080/version"

# Step 2: Test multiple requests to ensure consistency
echo -e "${GREEN}Step 2: Testing Consistency (5 requests)${NC}"
for i in {1..5}; do
    pool=$(curl -s -i http://localhost:8080/version | grep -i "X-App-Pool:" | awk '{print $2}' | tr -d '\r')
    echo "  Request $i: Pool = $pool"
done
echo ""

# Step 3: Induce chaos on Blue
echo -e "${RED}Step 3: Inducing Chaos on Blue (error mode)${NC}"
curl -X POST http://localhost:8081/chaos/start?mode=error
echo "  Chaos started on Blue"
sleep 2
echo ""

# Step 4: Verify automatic failover to Green
echo -e "${GREEN}Step 4: Verifying Automatic Failover to Green${NC}"
test_endpoint "http://localhost:8080/version"

# Step 5: Test consistency during failure (should all be Green)
echo -e "${GREEN}Step 5: Testing Stability During Failure (10 requests)${NC}"
green_count=0
other_count=0
error_count=0

for i in {1..10}; do
    response=$(curl -s -i http://localhost:8080/version)
    status=$(echo "$response" | grep "HTTP" | head -1 | awk '{print $2}')
    pool=$(echo "$response" | grep -i "X-App-Pool:" | awk '{print $2}' | tr -d '\r' | tr -d '\n')
    
    if [ "$status" = "200" ]; then
        if [ "$pool" = "green" ]; then
            ((green_count++))
            echo -e "  Request $i: ${GREEN}✓ Green (200)${NC}"
        elif [ "$pool" = "blue" ]; then
            ((other_count++))
            echo -e "  Request $i: ${YELLOW}○ Blue (200)${NC}"
        else
            ((other_count++))
            echo -e "  Request $i: ${YELLOW}○ Unknown pool: '$pool' (200)${NC}"
        fi
    else
        ((error_count++))
        echo -e "  Request $i: ${RED}✗ Error ($status)${NC}"
    fi
    sleep 0.5
done

echo ""
echo -e "${YELLOW}Results:${NC}"
echo "  Green responses: $green_count/10"
echo "  Other pool: $other_count/10"
echo "  Errors (non-200): $error_count/10"

if [ $error_count -eq 0 ]; then
    echo -e "  ${GREEN}✓ Zero errors - PASS${NC}"
else
    echo -e "  ${RED}✗ Had errors - FAIL${NC}"
fi

if [ $green_count -ge 9 ]; then
    echo -e "  ${GREEN}✓ ≥90% Green responses - PASS${NC}"
else
    echo -e "  ${RED}✗ <90% Green responses - FAIL${NC}"
fi
echo ""

# Step 6: Stop chaos
echo -e "${GREEN}Step 6: Stopping Chaos on Blue${NC}"
curl -X POST http://localhost:8081/chaos/stop
echo "  Chaos stopped"
sleep 2
echo ""

# Step 7: Verify Blue recovery (optional - may still be on Green due to fail_timeout)
echo -e "${GREEN}Step 7: Testing After Recovery${NC}"
echo "  (Note: May still be Green due to fail_timeout=5s)"
test_endpoint "http://localhost:8080/version"

# Step 8: Test timeout mode
echo -e "${RED}Step 8: Testing Timeout Mode${NC}"
curl -X POST http://localhost:8081/chaos/start?mode=timeout
echo "  Timeout chaos started on Blue"
sleep 2
echo ""

echo -e "${GREEN}Step 9: Verifying Failover with Timeout${NC}"
test_endpoint "http://localhost:8080/version"

# Stop chaos again
echo -e "${GREEN}Step 10: Final Cleanup${NC}"
curl -X POST http://localhost:8081/chaos/stop
echo "  Chaos stopped"
echo ""

echo -e "${YELLOW}=== Test Complete ===${NC}"
echo -e "Review the results above. Key requirements:"
echo -e "  1. ${GREEN}Zero non-200 responses during chaos${NC}"
echo -e "  2. ${GREEN}≥95% responses from Green during failure${NC}"
echo -e "  3. ${GREEN}Headers correctly show pool and release ID${NC}"