"""
Simulate Razorpay Webhook Events
Sends signed Razorpay webhook payloads to http://localhost:8000/webhook/razorpay
"""
import hashlib
import hmac
import json
import time
import uuid
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from backend.config import settings

TARGET_URL = "http://localhost:8000/webhook/razorpay"
SECRET = (settings.razorpay_webhook_secret or settings.razorpay_key_secret or "6jaF3nYTZca5ZIsZ7st4Xbqt").strip()

def send_test_webhook(event_type="payment.authorized", card_bin="411111", ip="103.21.58.42", amount_paise=500):
    payment_id = f"pay_test_{uuid.uuid4().hex[:10]}"
    order_id = f"order_test_{uuid.uuid4().hex[:8]}"

    payload = {
        "entity": "event",
        "account_id": "acc_guardpay_test",
        "event": event_type,
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": payment_id,
                    "entity": "payment",
                    "amount": amount_paise,
                    "currency": "INR",
                    "status": "authorized",
                    "order_id": order_id,
                    "method": "card",
                    "ip_address": ip,
                    "card": {
                        "id": f"card_{uuid.uuid4().hex[:8]}",
                        "entity": "card",
                        "name": "Test User",
                        "last4": "1111",
                        "network": "Visa",
                        "type": "debit",
                        "bin": card_bin,
                        "sub_type": "consumer"
                    },
                    "notes": {
                        "ip_address": ip
                    },
                    "created_at": int(time.time())
                }
            }
        },
        "created_at": int(time.time())
    }

    body_bytes = json.dumps(payload).encode("utf-8")
    signature = hmac.new(SECRET.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "X-Razorpay-Signature": signature
    }

    try:
        response = httpx.post(TARGET_URL, content=body_bytes, headers=headers, timeout=5.0)
        print(f"[{response.status_code}] Webhook event '{event_type}' sent successfully for Payment {payment_id}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error sending webhook: {e}")

if __name__ == "__main__":
    print("Sending sample Razorpay payment.authorized webhook to GuardPay...")
    send_test_webhook()
