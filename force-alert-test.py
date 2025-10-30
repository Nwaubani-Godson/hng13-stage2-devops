#!/usr/bin/env python3
"""
Force send a test alert to verify Slack webhook is working
"""

import os
import requests
from datetime import datetime

SLACK_WEBHOOK_URL = os.getenv('SLACK_WEBHOOK_URL', '')

if not SLACK_WEBHOOK_URL:
    print("ERROR: SLACK_WEBHOOK_URL environment variable not set!")
    print("Usage: SLACK_WEBHOOK_URL='your-webhook' python3 force-alert-test.py")
    exit(1)

print(f"Testing Slack webhook: {SLACK_WEBHOOK_URL[:50]}...")

payload = {
    "text": "🧪 *Test Alert*",
    "blocks": [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "🧪 *Manual Test Alert*\n\nThis is a test to verify Slack integration is working."
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
    print(f"Response status: {response.status_code}")
    print(f"Response body: {response.text}")
    
    if response.status_code == 200:
        print("\n✅ SUCCESS! Check your Slack channel for the test message.")
    else:
        print(f"\n❌ FAILED! Status code: {response.status_code}")
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()