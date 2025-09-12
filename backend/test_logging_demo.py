#!/usr/bin/env python3
"""
Demo script to test the enhanced logging system.
This will make API calls to demonstrate the detailed logging.
"""

import requests
import json
import time

def test_logging_demo():
    """Test the enhanced logging by making API calls."""
    base_url = "http://localhost:8000"

    # Test data
    test_messages = [
        "show me my calendar events today",
        "delete the Nabulu event"
    ]

    session_id = "logging-demo-session"

    for i, message in enumerate(test_messages, 1):
        print(f"\n{'='*60}")
        print(f"🧪 TEST {i}: {message}")
        print(f"{'='*60}")

        payload = {
            "message": message,
            "session_id": session_id
        }

        try:
            response = requests.post(
                f"{base_url}/api/v1/personal-assistant/chat",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                print(f"✅ Response: {result['response'][:100]}...")
                print(f"🔧 Tools used: {result.get('tools_used', [])}")
            else:
                print(f"❌ Error: {response.status_code}")
                print(f"Error details: {response.text}")

        except Exception as e:
            print(f"❌ Request failed: {str(e)}")

        # Wait a bit between requests
        time.sleep(2)
    
    print(f"\n{'='*60}")
    print("🎯 Check the server logs to see the detailed agent context!")
    print("Look for these log patterns:")
    print("  🆕 SESSION MANAGER: Creating NEW agent")
    print("  ♻️  SESSION MANAGER: Reusing EXISTING agent")
    print("  🧠 AGENT CONTEXT BEFORE PROCESSING")
    print("  🔍 CONTEXT RESOLVER: Enhancing parameters")
    print("  🔧 TOOL EXECUTION")
    print("  🎯 AGENT CONTEXT AFTER PROCESSING")
    print(f"{'='*60}")

if __name__ == "__main__":
    print("🚀 Starting Enhanced Logging Demo...")
    print("This will make API calls to demonstrate the detailed logging system.")
    print("Make sure the server is running on http://localhost:8000")

    try:
        test_logging_demo()
    except KeyboardInterrupt:
        print("\n⏹️  Demo interrupted by user")
    except Exception as e:
        print(f"❌ Demo failed: {str(e)}")
