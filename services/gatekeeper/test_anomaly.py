#!/usr/bin/env python3
"""
Test script to trigger anomaly detection in the gatekeeper.

This simulates bot-like behavior by sending events with very short time gaps.
"""

import requests
import time
from datetime import datetime

API_URL = "http://localhost:8000/predict"

def send_event(user_id: str, timestamp_ms: int):
    """Send a prediction request."""
    response = requests.post(
        API_URL,
        json={"visitorid": user_id, "timestamp": timestamp_ms}
    )
    return response.json()

def test_normal_user():
    """Test a normal user with reasonable gaps between events."""
    print("\n" + "="*60)
    print("TEST 1: Normal User Behavior")
    print("="*60)

    user_id = "normal-user-456"
    base_time = int(datetime(2023, 1, 1, 12, 0, 0).timestamp() * 1000)

    events = [
        ("First event (baseline)", base_time),
        ("Second event (+5 seconds)", base_time + 5000),
        ("Third event (+10 seconds)", base_time + 10000),
        ("Fourth event (+30 seconds)", base_time + 30000),
    ]

    for description, timestamp in events:
        result = send_event(user_id, timestamp)
        print(f"\n{description}:")
        print(f"  Timestamp: {timestamp}")
        print(f"  Time since last: {result.get('time_since_last_event_sec', 'N/A'):.2f}s")
        print(f"  Is anomaly: {result.get('is_anomaly', 'N/A')}")
        print(f"  Detection method: {result.get('detection_method', 'N/A')}")
        time.sleep(0.5)  # Small delay for readability

def test_bot_user():
    """Test a bot user with very rapid events."""
    print("\n" + "="*60)
    print("TEST 2: Bot User Behavior (Rapid Fire)")
    print("="*60)

    user_id = "bot-user-789"
    base_time = int(datetime(2023, 1, 1, 12, 0, 0).timestamp() * 1000)

    events = [
        ("First event (baseline)", base_time),
        ("Second event (+50ms) 🤖", base_time + 50),
        ("Third event (+100ms total) 🤖", base_time + 100),
        ("Fourth event (+150ms total) 🤖", base_time + 150),
        ("Fifth event (+200ms total) 🤖", base_time + 200),
    ]

    for description, timestamp in events:
        result = send_event(user_id, timestamp)
        print(f"\n{description}:")
        print(f"  Timestamp: {timestamp}")
        print(f"  Time since last: {result.get('time_since_last_event_sec', 'N/A'):.6f}s")
        print(f"  Is anomaly: {result.get('is_anomaly', 'N/A')}")
        print(f"  Detection method: {result.get('detection_method', 'N/A')}")

        if result.get('is_anomaly'):
            print("  ⚠️  ANOMALY DETECTED! User should be banned!")

        time.sleep(0.5)

def test_various_speeds():
    """Test different event speeds to see threshold."""
    print("\n" + "="*60)
    print("TEST 3: Finding the Anomaly Threshold")
    print("="*60)

    user_base = "speed-test"
    base_time = int(datetime(2023, 1, 1, 12, 0, 0).timestamp() * 1000)

    # Test different time gaps
    time_gaps = [0.01, 0.05, 0.1, 0.5, 1, 2, 5, 10]  # seconds

    for gap_seconds in time_gaps:
        user_id = f"{user_base}-{gap_seconds}"
        gap_ms = int(gap_seconds * 1000)

        # First event (baseline)
        send_event(user_id, base_time)

        # Second event with specific gap
        result = send_event(user_id, base_time + gap_ms)

        print(f"\nGap: {gap_seconds:>6.2f}s → Is anomaly: {result.get('is_anomaly', 'N/A')}")
        time.sleep(0.3)

def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("Gatekeeper Anomaly Detection Test Suite")
    print("="*60)
    print(f"API: {API_URL}")

    try:
        # Check if API is running
        response = requests.get("http://localhost:8000/health")
        if response.status_code != 200:
            print("❌ API is not healthy!")
            return
        print("✓ API is healthy")

        # Run tests
        test_normal_user()
        test_bot_user()
        test_various_speeds()

        print("\n" + "="*60)
        print("All tests completed!")
        print("="*60)

        print("\nTo check banned users in Redis:")
        print("  docker compose exec redis redis-cli ZRANGE banned_users_with_ttl 0 -1 WITHSCORES")

    except requests.exceptions.ConnectionError:
        print("\n❌ Error: Could not connect to API at http://localhost:8000")
        print("Make sure the gatekeeper API is running:")
        print("  cd services/gatekeeper")
        print("  ./run-api.sh")
    except Exception as e:
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    main()
