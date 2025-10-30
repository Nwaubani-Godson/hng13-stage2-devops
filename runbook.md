# Blue/Green Deployment Runbook

## Overview

This runbook provides operational guidance for responding to alerts from the Blue/Green deployment monitoring system. Alerts are sent to Slack when failovers occur or when error rates exceed configured thresholds.

---

## Alert Types

### 1. Failover Detected

**Alert Message:**
```
🔄 Failover Detected!
Pool changed: blue → green
```

**What This Means:**
The system has automatically switched traffic from the primary pool (blue) to the backup pool (green). This typically happens when:
- The primary pool is unhealthy or unresponsive
- The primary pool is returning 5xx errors
- The primary pool has exceeded connection timeouts

**Immediate Actions:**

1. **Check Primary Pool Health**
   ```bash
   # Check if blue container is running
   docker ps | grep app_blue
   
   # View blue container logs
   docker logs app_blue --tail 100
   ```

2. **Verify Backup Pool is Healthy**
   ```bash
   # Test green endpoint
   curl -i http://localhost:8082/version
   
   # Should return 200 OK with X-App-Pool: green
   ```

3. **Investigate Root Cause**
   ```bash
   # Check Nginx logs
   docker logs nginx_lb --tail 50
   
   # Check for application errors in blue
   docker logs app_blue | grep -i error
   ```

4. **Check Resource Usage**
   ```bash
   # Check container resource usage
   docker stats --no-stream
   ```

**Resolution Steps:**

If primary pool (blue) has issues:
```bash
# Option 1: Restart the container
docker-compose restart app_blue

# Option 2: Stop chaos if testing
curl -X POST http://localhost:8081/chaos/stop

# Wait for recovery, then verify
curl -i http://localhost:8081/version
```

If primary pool is healthy and you want to switch back:
```bash
# No action needed - Nginx will automatically switch back after fail_timeout (5s)
# Monitor logs to confirm:
docker logs alert_watcher --tail 20
```

**When to Escalate:**
- If failovers happen frequently (>3 times in 10 minutes)
- If both pools show errors
- If application consistently fails after restart

---

### 2. High Error Rate Detected

**Alert Message:**
```
🚨 High Error Rate Detected!
Error rate: 5.5% (threshold: 2.0%)
Errors: 11/200 requests returned 5xx
```

**What This Means:**
The active pool is returning too many 5xx errors (server-side errors). This indicates:
- Application bugs or crashes
- Database connectivity issues
- Resource exhaustion (CPU, memory, disk)
- Dependency failures (external APIs, services)

**Immediate Actions:**

1. **Identify Active Pool**
   ```bash
   # Check which pool is currently serving traffic
   curl -i http://localhost:8080/version | grep X-App-Pool
   ```

2. **Check Application Logs**
   ```bash
   # If blue is active
   docker logs app_blue --tail 100 | grep -E "error|Error|ERROR"
   
   # If green is active
   docker logs app_green --tail 100 | grep -E "error|Error|ERROR"
   ```

3. **Verify Database/Dependencies**
   ```bash
   # Check if any env vars are misconfigured
   docker exec app_blue env | grep -E "DATABASE|API|SERVICE"
   
   # Test database connectivity (if applicable)
   docker exec app_blue ping -c 3 database_host
   ```

4. **Check Resource Limits**
   ```bash
   # Check if container is hitting resource limits
   docker stats --no-stream app_blue app_green
   
   # Check system resources
   free -h
   df -h
   ```

**Resolution Steps:**

If error rate is temporary (spike):
```bash
# Monitor for recovery - alert has cooldown period
# Check if error rate drops below threshold
docker logs alert_watcher --tail 50
```

If error rate persists:
```bash
# Option 1: Restart the problematic container
docker-compose restart app_blue  # or app_green

# Option 2: Manual pool toggle (switch to healthy pool)
# Edit .env and change ACTIVE_POOL
nano .env  # Change ACTIVE_POOL=blue to ACTIVE_POOL=green
docker-compose restart nginx

# Option 3: Check and fix application code/config
# Review recent deployments, rollback if needed
```

**When to Escalate:**
- If error rate >10% for more than 5 minutes
- If both pools show high error rates
- If errors correlate with database or external service outages
- If application restart doesn't resolve the issue

---

### 3. Recovery Detected

**Alert Message:**
```
✅ Recovery Detected
Pool blue is now serving traffic again
```

**What This Means:**
The previously failed primary pool has recovered and is now healthy. Traffic has been restored to the primary pool. This is normal after:
- Application restart
- Chaos testing cleanup
- Temporary resource constraints resolved

**Actions:**
- **No immediate action required**
- Monitor system for stability over next 15 minutes
- Review logs to understand what caused the initial failure

**Verification:**
```bash
# Confirm primary pool is stable
curl -i http://localhost:8080/version | grep X-App-Pool
# Should show primary pool (blue)

# Monitor for a few minutes
watch -n 5 'curl -s http://localhost:8080/version | grep X-App-Pool'
```

---

## Maintenance Mode

### Suppressing Alerts During Planned Work

When performing planned maintenance or testing (e.g., intentional chaos tests):

**Option 1: Temporarily Disable Watcher**
```bash
# Stop the watcher container
docker-compose stop alert_watcher

# Perform maintenance
# ...

# Restart watcher when done
docker-compose start alert_watcher
```

**Option 2: Use Long Cooldown**
```bash
# Edit .env before maintenance
ALERT_COOLDOWN_SEC=3600  # 1 hour

# Restart watcher to pick up new config
docker-compose restart alert_watcher

# Perform maintenance
# ...

# Restore original cooldown
ALERT_COOLDOWN_SEC=300  # 5 minutes
docker-compose restart alert_watcher
```

**Best Practice:**
- Announce maintenance window in Slack before starting
- Use maintenance mode during chaos testing
- Re-enable alerts immediately after maintenance

---

## Common Scenarios

### Scenario 1: Chaos Testing
**Expected Behavior:**
- One failover alert when chaos starts
- Possible error rate alert if chaos mode is aggressive
- Recovery alert when chaos stops

**Actions:** Monitor alerts, no intervention needed unless unexpected behavior occurs

### Scenario 2: Deployment
**Expected Behavior:**
- Brief failover during rolling update
- Quick recovery to new version

**Actions:** Verify new version is healthy after deployment completes

### Scenario 3: Resource Exhaustion
**Symptoms:**
- Frequent failovers
- High error rates
- Slow response times

**Actions:**
```bash
# Check system resources
docker stats
free -h
df -h

# Scale up if needed (add resources or replicas)
# Check application for memory leaks or resource-intensive operations
```

### Scenario 4: Cascading Failure
**Symptoms:**
- Both pools failing
- Continuous alerts despite restarts

**Actions:**
```bash
# Check external dependencies
# - Database connectivity
# - External API availability
# - Network connectivity

# Review recent changes
# - Code deployments
# - Configuration changes
# - Infrastructure modifications

# Consider full system restart
docker-compose down
docker-compose up -d
```

---

## Monitoring Commands

### Check Alert Watcher Status
```bash
# View watcher logs
docker logs alert_watcher --tail 50 -f

# Check watcher is running
docker ps | grep alert_watcher

# Restart if needed
docker-compose restart alert_watcher
```

### Check Nginx Logs
```bash
# View structured logs
docker exec nginx_lb tail -f /var/log/nginx/access.log

# Count errors in last 200 requests
docker exec nginx_lb tail -200 /var/log/nginx/access.log | grep upstream_status=5
```

### Manual Failover Test
```bash
# Trigger chaos on blue
curl -X POST http://localhost:8081/chaos/start?mode=error

# Wait for alert (should arrive within seconds)

# Stop chaos
curl -X POST http://localhost:8081/chaos/stop

# Verify recovery
curl -i http://localhost:8080/version
```

---

## Alert Configuration

### Tuning Thresholds

**Error Rate Threshold:**
```bash
# Default: 2% (2 errors per 100 requests)
# Increase for less sensitive alerting:
ERROR_RATE_THRESHOLD=5.0

# Decrease for more sensitive alerting:
ERROR_RATE_THRESHOLD=1.0
```

**Window Size:**
```bash
# Default: 200 requests
# Larger window = more stable, slower to detect:
WINDOW_SIZE=500

# Smaller window = faster detection, more volatile:
WINDOW_SIZE=100
```

**Alert Cooldown:**
```bash
# Default: 300 seconds (5 minutes)
# Longer cooldown = fewer alerts:
ALERT_COOLDOWN_SEC=600

# Shorter cooldown = more alerts:
ALERT_COOLDOWN_SEC=120
```

After changing configuration:
```bash
# Update .env file
nano .env

# Restart watcher
docker-compose restart alert_watcher
```

---

## Troubleshooting

### Alerts Not Arriving in Slack

**Check webhook configuration:**
```bash
# Verify SLACK_WEBHOOK_URL is set
docker exec alert_watcher env | grep SLACK_WEBHOOK_URL

# Check watcher logs for errors
docker logs alert_watcher | grep -i "error\|failed"
```

**Test webhook manually:**
```bash
curl -X POST ${SLACK_WEBHOOK_URL} \
  -H 'Content-Type: application/json' \
  -d '{"text":"Test alert from Blue/Green deployment"}'
```

### False Positive Alerts

**If getting too many alerts:**
- Increase ERROR_RATE_THRESHOLD
- Increase ALERT_COOLDOWN_SEC
- Increase WINDOW_SIZE for more stable measurements

**If missing important alerts:**
- Decrease ERROR_RATE_THRESHOLD
- Decrease ALERT_COOLDOWN_SEC
- Check watcher is running: `docker ps | grep alert_watcher`

---

## Contact Information

**For Immediate Issues:**
- Check #devops-alerts Slack channel
- Review this runbook
- Check application logs

**For Escalation:**
- DevOps Team Lead: [Contact Info]
- Platform Engineer: [Contact Info]
- On-call Engineer: [Pager Duty / On-call System]

---

## References

- Stage 2 Documentation: README.md
- Docker Compose Configuration: docker-compose.yml
- Nginx Configuration: nginx.conf.template
- Alert Watcher Source: watcher.py
- Environment Variables: .env.example

---

**Last Updated:** October 30, 2025  
**Version:** 1.0  
**Maintained By:** DevOps Team