#!/usr/bin/env python3
"""
Nginx Log Watcher for Blue/Green Deployment Monitoring
Monitors Nginx access logs and sends Slack alerts on:
- Failover events (pool changes)
- High error rates (5xx responses)
"""

import os
import re
import time
import requests
from collections import deque
from datetime import datetime, timedelta

# Configuration from environment variables
SLACK_WEBHOOK_URL = os.getenv('SLACK_WEBHOOK_URL', '')
ERROR_RATE_THRESHOLD = float(os.getenv('ERROR_RATE_THRESHOLD', '2.0'))  # percentage
WINDOW_SIZE = int(os.getenv('WINDOW_SIZE', '200'))  # number of requests
ALERT_COOLDOWN_SEC = int(os.getenv('ALERT_COOLDOWN_SEC', '300'))  # 5 minutes
LOG_FILE = '/var/log/nginx/access_detailed.log'

# State tracking
last_pool = None
request_window = deque(maxlen=WINDOW_SIZE)
last_failover_alert = None
last_error_rate_alert = None

# Updated regex pattern to handle multiple upstream_status values
LOG_PATTERN = re.compile(
    r'pool=(?P<pool>[^\s]+)\s+'
    r'release=(?P<release>[^\s]+)\s+'
    r'upstream_status=(?P<upstream_status>[\d, ]+)'
)

def send_slack_alert(message, alert_type="info"):
    """Send alert to Slack webhook"""
    if not SLACK_WEBHOOK_URL:
        print(f"[WARNING] No Slack webhook configured. Alert: {message}")
        return False
    
    emoji_map = {
        "failover": "🔄",
        "error": "🚨",
        "recovery": "✅",
        "info": "ℹ️"
    }
    
    emoji = emoji_map.get(alert_type, "📢")
    
    payload = {
        "text": f"{emoji} *Blue/Green Deployment Alert*",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{emoji} *Blue/Green Deployment Alert*\n\n{message}"
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"
                    }
                ]
            }
        ]
    }
    
    try:
        response = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)
        print(f"[DEBUG] Slack response status: {response.status_code}")
        print(f"[DEBUG] Slack response body: {response.text}")
        if response.status_code == 200:
            print(f"[ALERT SENT] {message}")
            return True
        else:
            print(f"[ERROR] Slack webhook failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"[ERROR] Failed to send Slack alert: {e}")
        return False

def check_failover(current_pool):
    global last_pool, last_failover_alert
    
    if last_pool is None:
        last_pool = current_pool
        print(f"[INFO] Initial pool detected: {current_pool}")
        return
    
    if current_pool != last_pool:
        now = datetime.now()
        if last_failover_alert and (now - last_failover_alert).total_seconds() < ALERT_COOLDOWN_SEC:
            print(f"[INFO] Failover detected ({last_pool} → {current_pool}) but in cooldown period")
            last_pool = current_pool
            return
        
        message = (
            f"*Failover Detected!*\n"
            f"Pool changed: *{last_pool}* → *{current_pool}*\n\n"
            f"*Action Required:*\n"
            f"• Check health of `{last_pool}` container\n"
            f"• Review `{last_pool}` logs for errors\n"
            f"• Verify `{current_pool}` is handling traffic correctly\n\n"
            f"See runbook for detailed response steps."
        )
        
        send_slack_alert(message, alert_type="failover")
        last_failover_alert = now
        last_pool = current_pool

def check_error_rate():
    global last_error_rate_alert
    
    if len(request_window) < WINDOW_SIZE:
        return
    
    error_count = sum(1 for status in request_window if status >= 500)
    error_rate = (error_count / WINDOW_SIZE) * 100
    
    if error_rate > ERROR_RATE_THRESHOLD:
        now = datetime.now()
        if last_error_rate_alert and (now - last_error_rate_alert).total_seconds() < ALERT_COOLDOWN_SEC:
            print(f"[INFO] High error rate ({error_rate:.2f}%) but in cooldown period")
            return
        
        message = (
            f"*High Error Rate Detected!*\n"
            f"Error rate: *{error_rate:.2f}%* (threshold: {ERROR_RATE_THRESHOLD}%)\n"
            f"Errors: {error_count}/{WINDOW_SIZE} requests returned 5xx\n\n"
            f"*Action Required:*\n"
            f"• Check upstream application logs\n"
            f"• Verify database connectivity\n"
            f"• Consider manual pool toggle if issues persist\n"
            f"• Review resource usage (CPU, memory)\n\n"
            f"See runbook for detailed response steps."
        )
        
        send_slack_alert(message, alert_type="error")
        last_error_rate_alert = now

def parse_log_line(line):
    match = LOG_PATTERN.search(line)
    if match:
        pool = match.group('pool')
        release = match.group('release')
        upstream_status_str = match.group('upstream_status').strip()
        first_status = int(upstream_status_str.split(',')[0])
        return pool, release, first_status
    return None, None, None

def tail_log_file():
    print(f"[INFO] Starting log watcher...")
    print(f"[INFO] Monitoring: {LOG_FILE}")
    print(f"[INFO] Error rate threshold: {ERROR_RATE_THRESHOLD}%")
    print(f"[INFO] Window size: {WINDOW_SIZE} requests")
    print(f"[INFO] Alert cooldown: {ALERT_COOLDOWN_SEC} seconds")
    print(f"[INFO] Slack webhook configured: {bool(SLACK_WEBHOOK_URL)}")

    while not os.path.exists(LOG_FILE):
        print(f"[INFO] Waiting for log file to be created: {LOG_FILE}")
        time.sleep(2)

    with open(LOG_FILE, 'r') as f:
        print("[INFO] Watching for new log entries...")
        
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.1)
                continue
            
            pool, release, upstream_status = parse_log_line(line)
            print(f"[DEBUG] Parsed log line - pool: {pool}, release: {release}, upstream_status: {upstream_status}")

            if pool and upstream_status:
                request_window.append(upstream_status)
                check_failover(pool)
                check_error_rate()

def main():
    print("=" * 60)
    print("Blue/Green Deployment Log Watcher")
    print("=" * 60)

    if not SLACK_WEBHOOK_URL:
        print("[WARNING] SLACK_WEBHOOK_URL not set - alerts will only be logged")
    
    try:
        tail_log_file()
    except KeyboardInterrupt:
        print("\n[INFO] Shutting down gracefully...")
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        raise

if __name__ == "__main__":
    main()