import requests
import json

def test_chat():
    """Test the chat endpoint"""
    url = "http://localhost:8000/api/chat"
    headers = {"Content-Type": "application/json"}
    
    # Test messages
    test_messages = [
        {"message": "Hello, I want to book an appointment"},
        {"message": "My name is John Smith, DOB 01/15/1985, I need a cardiology appointment"},
        {"message": "Yes, please book it for tomorrow at 2pm"}
    ]
    
    session_id = None
    
    for i, data in enumerate(test_messages):
        if session_id:
            data["session_id"] = session_id
            
        try:
            response = requests.post(url, headers=headers, json=data)
            print(f"\n--- Test {i+1} ---")
            print(f"Message: {data['message']}")
            print(f"Status Code: {response.status_code}")
            result = response.json()
            print(f"Response: {result['response']}")
            print(f"Patient Name: {result.get('patient_name')}")
            print(f"Booking Intent: {result.get('booking_intent')}")
            print(f"Appointment Booked: {result.get('appointment_booked')}")
            print(f"Tools Used: {result.get('tools_used')}")
            
            # Save session ID for next request
            session_id = result.get('session_id')
            
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    test_chat() 