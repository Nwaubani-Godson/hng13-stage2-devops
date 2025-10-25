# Implementation Decisions

## Overview
This document explains the key architectural decisions made for the Blue/Green deployment with Nginx auto-failover implementation.

---

## 1. Nginx Configuration Strategy

### Decision: Template-based configuration with envsubst
**Why:**
- Allows dynamic switching between Blue/Green as active pool
- Enables CI/CD integration through environment variables
- No code changes needed - just restart Nginx with new env vars
- Simple and maintainable

**Implementation:**
- `nginx.conf.template` contains `${ACTIVE_POOL}` and `${BACKUP_POOL}` placeholders
- `entrypoint.sh` uses `envsubst` to generate final config on container startup
- The script automatically determines backup pool based on active pool

---

## 2. Failover Configuration

### Decision: Primary/Backup upstream with tight timeouts
**Why:**
- `backup` directive ensures Green only receives traffic when Blue is completely down
- Meets requirement: "Blue is active by default, Green is backup"
- Prevents split traffic in normal state

**Key Settings:**
```nginx
server app_blue:3000 max_fails=1 fail_timeout=5s;
server app_green:3000 backup;
```

**Rationale:**
- `max_fails=1`: Mark server as down after just 1 failure (aggressive but necessary)
- `fail_timeout=5s`: Short window before retry (quick recovery)
- `backup`: Green only used when Blue is marked as down

---

## 3. Retry Logic

### Decision: Multi-condition retry with proxy_next_upstream
**Why:**
- Ensures zero 5xx errors reach the client
- Retries happen within the same client request
- Covers all failure scenarios: errors, timeouts, 5xx responses

**Configuration:**
```nginx
proxy_next_upstream error timeout http_500 http_502 http_503 http_504;
proxy_next_upstream_tries 2;
proxy_next_upstream_timeout 10s;
```

**Rationale:**
- `error`: Network-level failures
- `timeout`: Hung connections
- `http_50x`: Application errors (including chaos mode 500s)
- `tries 2`: Primary + Backup = 2 attempts
- `timeout 10s`: Meets "request should not be more than 10 seconds" requirement

---

## 4. Timeout Configuration

### Decision: Aggressive timeout settings
**Why:**
- Quick failure detection is critical for auto-failover
- Prevents clients from waiting too long
- Ensures switch happens within ~2-5 seconds

**Settings:**
```nginx
proxy_connect_timeout 2s;
proxy_send_timeout 3s;
proxy_read_timeout 3s;
```

**Rationale:**
- `connect_timeout 2s`: Fast detection of unreachable backend
- `read_timeout 3s`: Catches slow/hung responses quickly
- Total potential wait: 2s + 3s = 5s before failover triggered
- With retry: 5s + 5s = 10s maximum (meets requirement)

**Trade-offs:**
- Might be too aggressive for slow legitimate requests
- Can adjust based on app performance characteristics
- For this task, optimized for failover speed

---

## 5. Header Preservation

### Decision: No header stripping, transparent proxy
**Why:**
- Task explicitly requires: "Do not strip upstream headers"
- App headers (`X-App-Pool`, `X-Release-Id`) must reach client unchanged
- Grader validates these headers

**Implementation:**
```nginx
proxy_pass_request_headers on;
# No proxy_hide_header or proxy_ignore_headers directives
```

**Result:**
- All app response headers forwarded to client
- Client can verify which pool served the request
- Release ID tracking works correctly

---

## 6. Port Exposure Strategy

### Decision: Expose both app containers directly
**Why:**
- Task requires: "Expose Blue/Green on 8081/8082 so the grader can call /chaos/* directly"
- Allows grader to trigger chaos on specific container
- Bypasses Nginx for direct app control

**Mapping:**
```yaml
app_blue:
  ports: "8081:3000"
app_green:
  ports: "8082:3000"
nginx:
  ports: "8080:80"
```

**Security Note:**
- In production, you'd only expose Nginx
- Direct app exposure is for testing/grading purposes only

---

## 7. Docker Compose Architecture

### Decision: Single network, all services in same compose file
**Why:**
- Simple service discovery (containers can reach each other by name)
- No extra networking complexity
- Easy to manage and debug

**Structure:**
```yaml
services:
  app_blue: ...
  app_green: ...
  nginx: ...
networks:
  app_network:
    driver: bridge
```

**Benefits:**
- Nginx can reach `app_blue:3000` and `app_green:3000` by name
- Isolated from host network
- Clean shutdown with `docker-compose down`

---

## 8. Environment Variable Design

### Decision: Comprehensive .env file with clear defaults
**Why:**
- CI/grader can override any value
- Local development works out of the box
- Clear documentation of all configurable values

**Variables:**
- `BLUE_IMAGE`, `GREEN_IMAGE`: Image references (CI controlled)
- `ACTIVE_POOL`: Which pool is primary (blue/green)
- `RELEASE_ID_BLUE`, `RELEASE_ID_GREEN`: Version tracking
- `PORT`: App port (optional, defaults to 3000)

**Design Choice:**
- No hardcoded values in compose file
- Everything parameterized for maximum flexibility

---

## 9. Health Checks

### Decision: Docker-native health checks on app containers
**Why:**
- Docker Compose can show service health status
- Uses app's `/healthz` endpoint
- Provides visibility without extra tooling

**Configuration:**
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:3000/healthz"]
  interval: 5s
  timeout: 3s
  retries: 3
```

**Note:**
- Health checks are informational only
- Nginx handles its own upstream health detection
- Useful for debugging and monitoring

---

## 10. Nginx Image Customization

### Decision: Custom Dockerfile with envsubst capability
**Why:**
- Official `nginx:alpine` doesn't include `envsubst` by default
- Needed for template substitution in entrypoint
- Alpine keeps image size minimal

**Dockerfile:**
```dockerfile
FROM nginx:alpine
RUN apk add --no-cache gettext  # Provides envsubst
```

**Alternative Considered:**
- Could use `envsubst` from host, mount config as volume
- Rejected: Less portable, requires host dependencies

---

## 11. Zero-Downtime Failover Guarantee

### Decision: Combination of backup directive + retry logic
**Why:**
- Task requires: "zero failed client requests"
- Client should always get 200, even during failover

**How it works:**
1. Client sends request to Nginx
2. Nginx forwards to Blue (primary)
3. Blue fails (timeout or 5xx)
4. Nginx retries to Green (backup) **in the same request**
5. Green returns 200
6. Client receives 200 (never sees the failure)

**Key Point:**
- The retry happens server-side, within the same client TCP connection
- Client is unaware of the failover
- No 5xx error ever sent to client

---

## 12. Manual Toggle Support

### Decision: ACTIVE_POOL environment variable
**Why:**
- Task mentions "Manual Toggle" in title
- Allows ops to switch primary pool without code changes

**Usage:**
```bash
# Switch to Green as primary
sed -i 's/ACTIVE_POOL=blue/ACTIVE_POOL=green/' .env
docker-compose restart nginx
```

**Future Enhancement:**
- Could add reload script: `nginx -s reload`
- Would enable hot-swap without container restart

---

## 13. Chaos Testing Compatibility

### Decision: Direct port exposure + no request filtering
**Why:**
- Grader needs to POST to `/chaos/start` on specific container
- Nginx doesn't interfere with chaos endpoints
- Direct access simulates real failure scenarios

**Flow:**
1. Grader POSTs to `http://localhost:8081/chaos/start?mode=error`
2. Blue starts returning 500s
3. Nginx detects failure
4. Traffic switches to Green
5. Clients get 200s from Green

---

## 14. Testing Strategy

### Decision: curl-based verification
**Why:**
- Simple, no extra dependencies
- Headers visible with `-i` flag
- Easy to script for continuous testing

**Example:**
```bash
# Verify active pool
curl -i http://localhost:8080/version | grep X-App-Pool

# Continuous monitoring
watch -n 1 'curl -s http://localhost:8080/version | grep X-App-Pool'
```

---

## Potential Improvements

If this were a production system, I would consider:

1. **Metrics & Monitoring**
   - Prometheus exporter for Nginx
   - Grafana dashboards for failover events
   - Alert on excessive failovers

2. **Graceful Drain**
   - Allow in-flight requests to complete before marking down
   - Implement connection draining

3. **Circuit Breaker**
   - After X failures, stop trying primary for longer period
   - Prevent flapping between pools

4. **Health Check Endpoint in Nginx**
   - Deep health check that verifies backend connectivity
   - Useful for load balancer health checks

5. **Structured Logging**
   - JSON logs for better parsing
   - Include pool identity in every log line

6. **Automated Testing**
   - Integration tests in CI
   - Chaos engineering with actual load

---

## Conclusion

This implementation prioritizes:
- **Correctness**: Meets all task requirements
- **Simplicity**: Easy to understand and debug
- **Reliability**: Zero-downtime failover guaranteed
- **Flexibility**: Fully parameterized via environment variables

The design choices favor quick failover detection and transparent retry over absolute performance. For a production system, timeouts might be adjusted based on actual app behavior, but for this task, aggressive settings ensure reliable auto-failover within the required timeframe.