# Blue/Green Deployment with Nginx Auto-Failover

This repository implements a Blue/Green deployment strategy for a Node.js application with automatic failover using Nginx as a reverse proxy.

## Overview

The setup includes:
- **Blue Service**: Primary active service (port 8081)
- **Green Service**: Backup service (port 8082)
- **Nginx**: Reverse proxy with auto-failover (port 8080)

### Key Features
- Automatic failover from Blue to Green on failures
- Zero downtime during failover
- Proper header forwarding (`X-App-Pool`, `X-Release-Id`)
- Quick failure detection with tight timeouts
- Retry logic for transparent failover

## Prerequisites

- Docker (version 20.10+)
- Docker Compose (version 2.0+)
- Git

## Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/Nwaubani-Godson/hng13-stage2-devops
cd hng13-stage2-devops
```

### 2. Set Up Environment Variables
```bash
# Copy the example .env file
cp .env.example .env

# Edit .env if needed (defaults works for testing)
nano .env
```

### 3. Start the Services
```bash
# Build and start all services
docker-compose up -d

# Check service status
docker-compose ps

# View logs
docker-compose logs -f
```

### 4. Verify Deployment
```bash
# Test the main endpoint (should return Blue)
curl -i http://localhost:8080/version

# Check Blue directly
curl -i http://localhost:8081/version

# Check Green directly
curl -i http://localhost:8082/version
```

## Testing Failover

### Test Automatic Failover

1. **Normal State**: All traffic goes to Blue
```bash
curl -i http://localhost:8080/version
# Expected: X-App-Pool: blue
```

2. **Induce Chaos**: Trigger failure on Blue
```bash
# Simulate errors on Blue
curl -X POST http://localhost:8081/chaos/start?mode=error

# Or simulate timeout
curl -X POST http://localhost:8081/chaos/start?mode=timeout
```

3. **Verify Failover**: Traffic automatically switches to Green
```bash
# Should now return Green
curl -i http://localhost:8080/version
# Expected: X-App-Pool: green
```

4. **Stop Chaos**: Restore Blue
```bash
curl -X POST http://localhost:8081/chaos/stop
```

### Continuous Testing
```bash
# Run continuous requests to observe failover
watch -n 1 'curl -s http://localhost:8080/version | grep -E "X-App-Pool|X-Release-Id"'
```

## Configuration

### Environment Variables (.env)

| Variable | Description | Example |
|----------|-------------|---------|
| `BLUE_IMAGE` | Docker image for Blue service | `yimikaade/wonderful:devops-stage-two` |
| `GREEN_IMAGE` | Docker image for Green service | `yimikaade/wonderful:devops-stage-two` |
| `ACTIVE_POOL` | Active service (blue/green) | `blue` |
| `RELEASE_ID_BLUE` | Release identifier for Blue | `blue-v1.0.0` |
| `RELEASE_ID_GREEN` | Release identifier for Green | `green-v1.0.0` |
| `PORT` | Application port (optional) | `3000` |

### Nginx Failover Settings

The Nginx configuration includes:
- **max_fails**: 1 (mark server as down after 1 failure)
- **fail_timeout**: 5s (retry after 5 seconds)
- **proxy_connect_timeout**: 2s
- **proxy_read_timeout**: 3s
- **proxy_next_upstream**: Retry on error, timeout, and 5xx errors

## Project Structure

```
.
├── docker-compose.yml          # Service orchestration
├── Dockerfile.nginx            # Custom Nginx image with envsubst
├── nginx.conf.template         # Nginx configuration template
├── entrypoint.sh              # Nginx startup script with env substitution
├── .env.example               # Environment variables template
├── .env                       # Your local environment variables (git-ignored)
├── README.md                  # This file
└── DECISION.md                # Implementation decisions (optional)
```

## Maintenance

### Switching Active Pool

To manually switch the active pool:

1. Update `.env`:
```bash
ACTIVE_POOL=green  # Change from blue to green
```

2. Restart Nginx:
```bash
docker-compose restart nginx
```

### Viewing Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f nginx
docker-compose logs -f app_blue
docker-compose logs -f app_green
```

### Stopping Services
```bash
# Stop all services
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

## Troubleshooting

### Issue: Nginx not starting
```bash
# Check Nginx configuration
docker-compose exec nginx nginx -t

# View Nginx logs
docker-compose logs nginx
```

### Issue: Services not responding
```bash
# Check service health
docker-compose ps

# Check individual service logs
docker-compose logs app_blue
docker-compose logs app_green
```

### Issue: Headers not showing
```bash
# Use verbose curl
curl -v http://localhost:8080/version

# Check if headers are being forwarded
docker-compose logs nginx | grep -i "x-app-pool"
```

## Expected Behavior

### Normal Operation (Blue Active)
- All requests to `http://localhost:8080/version` return 200
- Headers show `X-App-Pool: blue`
- Headers show `X-Release-Id: <RELEASE_ID_BLUE>`

### After Chaos (Auto-Failover)
- Requests switch to Green within ~2-5 seconds
- **Zero 5xx errors** to clients (retry within same request)
- Headers show `X-App-Pool: green`
- ≥95% of responses from Green

## Learning Resources

- [Nginx Upstream Documentation](http://nginx.org/en/docs/http/ngx_http_upstream_module.html)
- [Blue/Green Deployment Pattern](https://martinfowler.com/bliki/BlueGreenDeployment.html)
- [Docker Compose Documentation](https://docs.docker.com/compose/)

## Notes

- Direct access to Blue (8081) and Green (8082) is intentional for chaos testing
- Nginx uses tight timeouts for quick failure detection
- The backup directive ensures Green only receives traffic when Blue is down
- All app headers are forwarded unchanged to clients
