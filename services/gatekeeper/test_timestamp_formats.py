#!/usr/bin/env python3
"""
Test script to verify timestamp format handling in the gatekeeper.

Tests both integer milliseconds and ISO datetime string formats.
"""

import requests
from datetime import datetime, timedelta

API_URL = "http://localhost:8000/predict"

def test_timestamp_formats():
    """Test both timestamp formats are accepted."""
    print("\n" + "="*70)
    print("Testing Timestamp Format Handling")
    print("="*70)

    # Current time
    now = datetime.now()

    test_cases = [
        {
            "name": "Integer milliseconds (original format)",
            "payload": {
                "visitorid": "test-user-ms",
                "timestamp": int(now.timestamp() * 1000)
            }
        },
        {
            "name": "ISO datetime string (new format)",
            "payload": {
                "visitorid": "test-user-iso",
                "timestamp": now.isoformat()
            }
        },
        {
            "name": "ISO datetime with microseconds",
            "payload": {
                "visitorid": "test-user-iso-micro",
                "timestamp": "2025-12-02T19:23:01.860023"
            }
        },
        {
            "name": "Integer as string",
            "payload": {
                "visitorid": "test-user-str",
                "timestamp": str(int(now.timestamp() * 1000))
            }
        }
    ]

    for test in test_cases:
        print(f"\n{test['name']}:")
        print(f"  Payload: {test['payload']}")

        try:
            response = requests.post(API_URL, json=test['payload'])

            if response.status_code == 200:
                result = response.json()

                if "error" in result:
                    print(f"  ✗ Error: {result['error']}")
                else:
                    print(f"  ✓ Success!")
                    print(f"    Time since last: {result.get('time_since_last_event_sec', 'N/A'):.2f}s")
                    print(f"    Is anomaly: {result.get('is_anomaly', 'N/A')}")
                    print(f"    Detection method: {result.get('detection_method', 'N/A')}")
            else:
                print(f"  ✗ HTTP {response.status_code}: {response.text}")

        except Exception as e:
            print(f"  ✗ Exception: {e}")

    print("\n" + "="*70)


def test_rapid_fire_with_iso_format():
    """Test bot detection with ISO datetime format."""
    print("\n" + "="*70)
    print("Testing Bot Detection with ISO Datetime Format")
    print("="*70)

    now = datetime.now()
    user_id = "bot-test-iso"

    events = [
        ("Event 1 (baseline)", now),
        ("Event 2 (+50ms) - RAPID FIRE", now + timedelta(milliseconds=50)),
        ("Event 3 (+500ms)", now + timedelta(milliseconds=500)),
        ("Event 4 (+2s) - Normal", now + timedelta(seconds=2)),
    ]

    for description, event_time in events:
        payload = {
            "visitorid": user_id,
            "timestamp": event_time.isoformat()
        }

        response = requests.post(API_URL, json=payload)

        if response.status_code == 200:
            result = response.json()
            print(f"\n{description}:")
            print(f"  Timestamp: {event_time.isoformat()}")
            print(f"  Time since last: {result.get('time_since_last_event_sec', 0):.4f}s")
            print(f"  Detection method: {result.get('detection_method', 'unknown')}")

            if result.get('is_anomaly'):
                print(f"  ⚠️  BOT DETECTED!")
            else:
                print(f"  ✓ Normal user")

    print("\n" + "="*70)


if __name__ == "__main__":
    print("\n" + "="*70)
    print("Gatekeeper Timestamp Format Test Suite")
    print("="*70)
    print(f"API: {API_URL}")

    try:
        # Check if API is running
        response = requests.get("http://localhost:8000/health")
        if response.status_code != 200:
            print("❌ API is not healthy!")
            exit(1)
        print("✓ API is healthy\n")

        # Run tests
        test_timestamp_formats()
        test_rapid_fire_with_iso_format()

        print("\n" + "="*70)
        print("All tests completed!")
        print("="*70)

    except requests.exceptions.ConnectionError:
        print("\n❌ Error: Could not connect to API at http://localhost:8000")
        print("Make sure the gatekeeper API is running:")
        print("  cd services/gatekeeper")
        print("  ./run-api.sh")
    except Exception as e:
        print(f"\n❌ Error: {e}")
