# Blue/Green Deployment with Observability & Alerts

This repository implements a Blue/Green deployment strategy with automatic failover, real-time monitoring, and Slack alerting (Stage 2 + Stage 3).

## Features

### Stage 2 (Base Deployment)
- Blue/Green deployment with Nginx reverse proxy
- Automatic failover on service failures
- Zero downtime during failover
- Health-based routing

### Stage 3 (Observability & Alerts)
- Real-time log monitoring
- Slack alerts for failover events
- Slack alerts for high error rates
- Structured Nginx logging
- Operator runbook for incident response

---

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Slack workspace with incoming webhook

### 1. Clone and Setup

```bash
git clone https://github.com/Nwaubani-Godson/hng13-stage2-devops.git
cd hng13-stage2-devops
```

### 2. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env and add your Slack webhook URL
nano .env
```

**Required configuration:**
```env
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
ACTIVE_POOL=blue
ERROR_RATE_THRESHOLD=2.0
WINDOW_SIZE=200
ALERT_COOLDOWN_SEC=300
```

### 3. Start Services

```bash
# Start all services
docker-compose up -d

# Verify all containers are running
docker-compose ps

# Should show 4 containers:
# - nginx_lb
# - app_blue
# - app_green
# - alert_watcher
```

### 4. Test Basic Functionality

```bash
# Test main endpoint (should return Blue)
curl -i http://localhost:8080/version

# Expected response:
# HTTP/1.1 200 OK
# X-App-Pool: blue
# X-Release-Id: blue-v1.0.0
```

---

## Testing Failover & Alerts

### Test 1: Failover Alert

```bash
# 1. Trigger chaos on Blue
curl -X POST http://localhost:8081/chaos/start?mode=error

# 2. Make requests to see failover
curl -i http://localhost:8080/version

# Expected: X-App-Pool: green

# 3. Check Slack for failover alert (arrives within seconds)
# Alert should say: "Failover Detected! Pool changed: blue → green"

# 4. Stop chaos
curl -X POST http://localhost:8081/chaos/stop
```

### Test 2: Error Rate Alert

```bash
# 1. Trigger chaos with high error rate
curl -X POST http://localhost:8081/chaos/start?mode=error

# 2. Generate traffic to exceed threshold
for i in {1..50}; do
  curl -s http://localhost:8080/version > /dev/null
  sleep 0.1
done

# 3. Check Slack for error rate alert
# Alert should say: "High Error Rate Detected! Error rate: X%"

# 4. Stop chaos
curl -X POST http://localhost:8081/chaos/stop
```

---

## Monitoring

### View Logs

```bash
# View all logs
docker-compose logs -f

# View alert watcher logs
docker logs alert_watcher -f

# View Nginx access logs with structured data
docker exec nginx_lb tail -f /var/log/nginx/access.log

# View specific service logs
docker logs app_blue -f
docker logs app_green -f
```

### Check Service Status

```bash
# Check container status
docker-compose ps

# Check resource usage
docker stats

# Test endpoints
curl http://localhost:8080/version  # Main endpoint
curl http://localhost:8081/version  # Blue directly
curl http://localhost:8082/version  # Green directly
```

---

## Architecture

### System Components

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       ▼
┌─────────────────────┐
│  Nginx (Port 8080)  │  ← Custom logging format
│  - Routes traffic   │
│  - Auto-failover    │
└──────┬──────────────┘
       │
       ├─────────────┬──────────────┐
       ▼             ▼              ▼
┌───────────┐ ┌───────────┐  ┌──────────────┐
│    Blue   │ │   Green   │  │ Alert Watcher│
│ (Primary) │ │  (Backup) │  │  (Python)    │
│  :8081    │ │   :8082   │  │  - Monitors  │
└───────────┘ └───────────┘  │  - Alerts    │
                              └──────┬───────┘
                                     │
                                     ▼
                              ┌────────────┐
                              │   Slack    │
                              └────────────┘
```

### Log Flow

```
Nginx Request → Custom Log Format → Shared Volume → Alert Watcher → Slack
```

**Nginx Log Format:**
```
pool=blue release=blue-v1.0.0 upstream_status=200 upstream=172.18.0.2:3000 request_time=0.010
```

---

## Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `SLACK_WEBHOOK_URL` | Slack incoming webhook URL | - | Yes |
| `ACTIVE_POOL` | Initial active pool (blue/green) | blue | Yes |
| `ERROR_RATE_THRESHOLD` | Error rate % to trigger alert | 2.0 | No |
| `WINDOW_SIZE` | Number of requests for error rate calculation | 200 | No |
| `ALERT_COOLDOWN_SEC` | Seconds between duplicate alerts | 300 | No |
| `BLUE_IMAGE` | Docker image for Blue service | - | Yes |
| `GREEN_IMAGE` | Docker image for Green service | - | Yes |
| `RELEASE_ID_BLUE` | Release identifier for Blue | - | Yes |
| `RELEASE_ID_GREEN` | Release identifier for Green | - | Yes |

### Alert Types

**1. Failover Alert**
- Triggered when traffic switches between pools
- Includes: old pool → new pool
- Cooldown: Configured in `ALERT_COOLDOWN_SEC`

**2. Error Rate Alert**
- Triggered when 5xx error rate exceeds threshold
- Calculation: (5xx count / window size) × 100
- Window: Last N requests (configured in `WINDOW_SIZE`)

---

## Runbook

For detailed operational procedures and incident response, see [runbook.md](runbook.md).

**Quick Links:**
- [Responding to Failover Alerts](runbook.md#1-failover-detected)
- [Responding to Error Rate Alerts](runbook.md#2-high-error-rate-detected)
- [Maintenance Mode](runbook.md#maintenance-mode)
- [Troubleshooting](runbook.md#troubleshooting)

---

## File Structure

```
.
├── docker-compose.yml          # Service orchestration
├── Dockerfile.nginx            # Nginx container
├── Dockerfile.watcher          # Alert watcher container
├── nginx.conf.template         # Nginx config with custom logging
├── entrypoint.sh              # Nginx startup script
├── watcher.py                 # Python log monitoring script
├── requirements.txt           # Python dependencies
├── .env.example              # Environment template
├── .env                      # Your configuration (git-ignored)
├── .gitignore               # Git ignore rules
├── README.md                # This file
├── runbook.md               # Operator runbook
├── DECISION.md              # Implementation decisions
└── test-failover.sh         # Automated testing script
```

---

## Troubleshooting

### Alerts Not Arriving

```bash
# 1. Check webhook URL is set
docker exec alert_watcher env | grep SLACK_WEBHOOK_URL

# 2. Check watcher logs
docker logs alert_watcher

# 3. Test webhook manually
curl -X POST $SLACK_WEBHOOK_URL \
  -H 'Content-Type: application/json' \
  -d '{"text":"Test alert"}'
```

### Nginx Container Exits

```bash
# 1. Make entrypoint.sh executable
chmod +x entrypoint.sh

# 2. Fix line endings (if on Windows/WSL)
sed -i 's/\r$//' entrypoint.sh

# 3. Rebuild
docker-compose down
docker-compose up -d --build
```

### No Logs in Watcher

```bash
# 1. Check shared volume
docker volume ls | grep nginx_logs

# 2. Check Nginx is writing logs
docker exec nginx_lb ls -la /var/log/nginx/

# 3. Restart watcher
docker-compose restart alert_watcher
```

---

## Screenshots

### 1. Failover Alert in Slack
![Failover Alert](screenshots/failover-alert.png)

### 2. Error Rate Alert in Slack
![Error Rate Alert](screenshots/error-rate-alert.png)

### 3. Nginx Structured Logs
![Nginx Logs](screenshots/nginx-logs.png)

---

## Development

### Local Testing

```bash
# Start services
docker-compose up

# In another terminal, trigger chaos
curl -X POST http://localhost:8081/chaos/start?mode=error

# Watch logs
docker logs alert_watcher -f

# Stop chaos
curl -X POST http://localhost:8081/chaos/stop
```

### Adjusting Alert Sensitivity

Edit `.env`:

```env
# More sensitive (alert on 1% errors)
ERROR_RATE_THRESHOLD=1.0

# Less sensitive (alert on 5% errors)
ERROR_RATE_THRESHOLD=5.0

# Smaller window (faster detection, more volatile)
WINDOW_SIZE=100

# Larger window (slower detection, more stable)
WINDOW_SIZE=500
```

Then restart:
```bash
docker-compose restart alert_watcher
```

---

## Production Deployment

### GCP/Cloud Setup

```bash
# 1. Provision VM
# 2. Clone repository
# 3. Configure .env with your Slack webhook
# 4. Start services
docker-compose up -d

# 5. Test from external IP
curl http://YOUR_VM_IP:8080/version

# 6. Monitor alerts in Slack
```

### Security Considerations

- Never commit `.env` with secrets
- Use environment-specific Slack channels
- Set appropriate `ALERT_COOLDOWN_SEC` for production
- Monitor alert watcher resource usage

---

## Support

- **Issues**: Open a GitHub issue
- **Questions**: Check [runbook.md](runbook.md)
- **Alerts**: See [runbook.md](runbook.md) for response procedures

---
