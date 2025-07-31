#!/usr/bin/env python3
"""
Test script to verify chat functionality and database tools
"""

import requests
import json

def test_chat():
    """Test the chat endpoint"""
    url = "http://localhost:8000/api/chat"
    
    # Test messages
    test_messages = [
        "what is the availability in cardiology?",
        "when is karen available?",
        "hi",
        "book me an appointment"
    ]
    
    for message in test_messages:
        print(f"\n{'='*50}")
        print(f"Testing: {message}")
        print('='*50)
        
        try:
            response = requests.post(url, json={'message': message})
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Success: {data.get('success')}")
                print(f"📝 Response: {data.get('response', '')[:200]}...")
                print(f"🔧 Tools used: {data.get('tools_used', [])}")
                print(f"📅 Booking intent: {data.get('booking_intent', False)}")
            else:
                print(f"❌ Error: {response.status_code}")
                print(f"Response: {response.text}")
        except Exception as e:
            print(f"❌ Exception: {e}")

def test_health():
    """Test the health endpoint"""
    url = "http://localhost:8000/api/health"
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            print(f"\n🏥 Health Check:")
            print(f"  Status: {data.get('status')}")
            print(f"  AI Service: {data.get('ai_service')}")
            print(f"  Database: {data.get('database')}")
            print(f"  Bedrock: {data.get('bedrock')}")
            print(f"  LangChain: {data.get('langchain')}")
        else:
            print(f"❌ Health check failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Health check exception: {e}")

if __name__ == "__main__":
    print("🧪 Testing Doc-AI Chat Functionality")
    print("=" * 60)
    
    # Test health first
    test_health()
    
    # Test chat functionality
    test_chat() 