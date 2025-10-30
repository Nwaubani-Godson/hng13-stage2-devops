#!/bin/bash

echo "=== Testing Alert Watcher Setup ==="

# Check if containers are running
echo -e "\n1. Checking containers..."
docker compose ps

# Check watcher logs
echo -e "\n2. Checking watcher logs..."
docker logs alert_watcher --tail 20

# Check if SLACK_WEBHOOK_URL is set
echo -e "\n3. Checking environment variables..."
docker exec alert_watcher env | grep SLACK_WEBHOOK_URL

# Check nginx log file exists and has content
echo -e "\n4. Checking Nginx logs..."
docker exec nginx_lb ls -la /var/log/nginx/
docker exec nginx_lb tail -5 /var/log/nginx/access.log

# Make a test request
echo -e "\n5. Making test request..."
curl -s http://localhost:8080/version | head -5

# Check latest watcher output
echo -e "\n6. Latest watcher output..."
docker logs alert_watcher --tail 10

# Test Slack webhook
echo -e "\n7. Testing Slack webhook..."
WEBHOOK_URL=$(docker exec alert_watcher env | grep SLACK_WEBHOOK_URL | cut -d'=' -f2-)
if [ -n "$WEBHOOK_URL" ]; then
    echo "Webhook URL is set, testing..."
    curl -X POST "$WEBHOOK_URL" \
        -H 'Content-Type: application/json' \
        -d '{"text":"🧪 Test alert from watcher debugging script"}'
    echo ""
else
    echo "ERROR: SLACK_WEBHOOK_URL not set!"
fi

echo -e "\n=== Test Complete ==="
echo "If Slack test worked but alerts don't, check watcher logs for parsing issues"