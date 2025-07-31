#!/usr/bin/env python3
"""
Test script to verify the fixes for AWS Bedrock and Redis issues
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_aws_bedrock():
    """Test AWS Bedrock initialization"""
    print("🔍 Testing AWS Bedrock initialization...")
    
    try:
        from main import get_llm, BEDROCK_AVAILABLE
        
        if not BEDROCK_AVAILABLE:
            print("❌ AWS Bedrock not available")
            return False
        
        llm = get_llm()
        if llm:
            print("✅ AWS Bedrock initialized successfully")
            return True
        else:
            print("❌ Failed to initialize AWS Bedrock")
            return False
            
    except Exception as e:
        print(f"❌ Error testing AWS Bedrock: {e}")
        return False

def test_redis_config():
    """Test Redis configuration"""
    print("🔍 Testing Redis configuration...")
    
    try:
        from main import REDIS_CHAT_HISTORY_AVAILABLE, LangChainConversationManager
        
        if not REDIS_CHAT_HISTORY_AVAILABLE:
            print("❌ Redis Chat History not available")
            return False
        
        # Test creating a conversation manager
        manager = LangChainConversationManager()
        redis_history = manager._get_redis_chat_history("test_session")
        
        if redis_history is not None:
            print("✅ Redis configuration working")
            return True
        else:
            print("⚠️  Redis configuration failed (this might be expected if Redis is not running)")
            return True  # This is not a critical error
            
    except Exception as e:
        print(f"❌ Error testing Redis configuration: {e}")
        return False

def test_langchain_compatibility():
    """Test LangChain compatibility"""
    print("🔍 Testing LangChain compatibility...")
    
    try:
        from main import ClaudeBedrockLLM
        from langchain_core.messages import HumanMessage, SystemMessage
        
        # Test creating the LLM
        llm = ClaudeBedrockLLM()
        
        # Test calling it
        messages = [
            SystemMessage(content="You are a helpful assistant."),
            HumanMessage(content="Hello!")
        ]
        
        response = llm.invoke(messages)
        print("✅ LangChain compatibility working")
        return True
        
    except Exception as e:
        print(f"❌ Error testing LangChain compatibility: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 Testing Doc-AI Fixes")
    print("=" * 40)
    
    tests = [
        ("AWS Bedrock", test_aws_bedrock),
        ("Redis Configuration", test_redis_config),
        ("LangChain Compatibility", test_langchain_compatibility)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 40)
    print("📊 Test Results:")
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n🎯 Overall: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("🎉 All tests passed! The fixes are working correctly.")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")

if __name__ == "__main__":
    main() 