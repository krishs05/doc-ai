#!/usr/bin/env python3
"""
Test script to verify the conversation flow and appointment booking process
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import EnhancedConversationManager
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_conversation_flow():
    """Test the conversation flow with the specific conversation from the user"""
    
    print("🧪 Testing Conversation Flow and Appointment Booking")
    print("=" * 60)
    
    # Initialize conversation manager
    conversation_manager = EnhancedConversationManager()
    session_id = "test_session_123"
    
    # Test the exact conversation from the user's issue
    messages = [
        "Can i get an appointment Dr Karen Lee at june 12th at 3:15pm",
        "Krish Sawhney, 5th feb 2004, Dr karen lee",
        "june 12th at 2:00 pm"
    ]
    
    print("\n📝 Testing conversation flow:")
    print("-" * 40)
    
    for i, message in enumerate(messages, 1):
        print(f"\n{i}. User: {message}")
        
        # Process the message
        result = conversation_manager.process_message(message, session_id)
        
        print(f"   AI Response: {result['response'][:200]}...")
        print(f"   Success: {result['success']}")
        
        if 'appointment_booked' in result:
            print(f"   Appointment Booked: {result['appointment_booked']}")
        if 'needs_more_info' in result:
            print(f"   Needs More Info: {result['needs_more_info']}")
        if 'booking_attempted' in result:
            print(f"   Booking Attempted: {result['booking_attempted']}")
    
    print("\n" + "=" * 60)
    print("✅ Conversation flow test completed!")
    
    # Test appointment lookup
    print("\n🔍 Testing appointment lookup for Krish Sawhney...")
    appointments = conversation_manager.get_upcoming_appointments("Krish Sawhney", "02/05/2004")
    
    if appointments:
        print(f"Found {len(appointments)} appointments for Krish Sawhney:")
        for apt in appointments:
            print(f"  - {apt['appointment_date']} at {apt['appointment_time']} with Dr. {apt['doctor_name']}")
    else:
        print("No appointments found for Krish Sawhney")
    
    print("\n✅ All tests completed!")

if __name__ == "__main__":
    test_conversation_flow() 