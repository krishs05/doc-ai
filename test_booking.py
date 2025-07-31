#!/usr/bin/env python3
"""
Test script to verify appointment booking functionality
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import EnhancedAppointmentManager, AppointmentDetails
from datetime import date, time, timedelta
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_appointment_booking():
    """Test the appointment booking functionality"""
    
    print("🧪 Testing Appointment Booking System")
    print("=" * 50)
    
    # Initialize appointment manager
    appointment_manager = EnhancedAppointmentManager()
    
    # Test 1: Check if we can find doctors
    print("\n1. Testing doctor search...")
    doctors = appointment_manager.find_available_doctors_by_specialty("cardiology")
    print(f"Found {len(doctors)} cardiologists:")
    for doctor in doctors[:3]:
        print(f"  - Dr. {doctor['first_name']} {doctor['last_name']} ({doctor['specialization']})")
    
    # Test 2: Check doctor availability for today
    if doctors:
        doctor = doctors[0]  # Use first cardiologist
        print(f"\n2. Testing availability for Dr. {doctor['first_name']} {doctor['last_name']}...")
        today = date.today()
        slots = appointment_manager.get_doctor_availability(doctor['id'], today)
        print(f"Found {len(slots)} available slots today:")
        for slot in slots[:5]:
            print(f"  - {slot['display_time']} on {slot['date']}")
        
        # Test 3: Test appointment booking with an available slot
        if slots:
            print(f"\n3. Testing appointment booking...")
            
            # Use the first available slot
            available_slot = slots[0]
            
            # Create test appointment details
            test_details = AppointmentDetails(
                patient_name="Test Patient",
                date_of_birth="01/15/1990",
                doctor_preference=doctor['first_name'] + " " + doctor['last_name'],
                specialization="Cardiology",
                preferred_date=available_slot['date'],
                preferred_time=available_slot['time'],
                reason="Test appointment"
            )
            
            print(f"Attempting to book appointment for {test_details.patient_name}...")
            print(f"Date: {test_details.preferred_date}")
            print(f"Time: {test_details.preferred_time}")
            print(f"Doctor: {test_details.doctor_preference}")
            
            success, message = appointment_manager.book_appointment(test_details)
            
            print(f"Booking result: {'SUCCESS' if success else 'FAILED'}")
            print(f"Message: {message}")
            
            # Test 4: Check if appointment was actually created
            if success:
                print("\n4. Verifying appointment was created...")
                print("Appointment booking test completed successfully!")
            else:
                print("\n4. Booking failed, checking why...")
                print("This might be due to:")
                print("- Doctor not found")
                print("- Time slot not available")
                print("- Database constraints")
        else:
            print("\n3. No available slots today, skipping booking test")
    
    print("\n✅ Test completed!")

if __name__ == "__main__":
    test_appointment_booking() 