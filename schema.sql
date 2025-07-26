-- Doctor Availability and Appointment Management System
-- PostgreSQL Database Schema

-- Drop tables if they exist (for fresh setup)
DROP TABLE IF EXISTS appointments CASCADE;
DROP TABLE IF EXISTS doctor_availability CASCADE;
DROP TABLE IF EXISTS patients CASCADE;
DROP TABLE IF EXISTS doctors CASCADE;
DROP TABLE IF EXISTS specializations CASCADE;

-- Create Specializations table
CREATE TABLE specializations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create Doctors table
CREATE TABLE doctors (
    id SERIAL PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    phone VARCHAR(20),
    specialization_id INTEGER REFERENCES specializations(id),
    license_number VARCHAR(50) UNIQUE,
    experience_years INTEGER,
    consultation_fee DECIMAL(10,2),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create Patients table
CREATE TABLE patients (
    id SERIAL PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    phone VARCHAR(20),
    date_of_birth DATE,
    gender VARCHAR(10),
    address TEXT,
    emergency_contact_name VARCHAR(100),
    emergency_contact_phone VARCHAR(20),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create Doctor Availability table
CREATE TABLE doctor_availability (
    id SERIAL PRIMARY KEY,
    doctor_id INTEGER REFERENCES doctors(id) ON DELETE CASCADE,
    day_of_week INTEGER NOT NULL CHECK (day_of_week >= 0 AND day_of_week <= 6), -- 0=Sunday, 6=Saturday
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    slot_duration INTEGER DEFAULT 30, -- Duration in minutes
    max_patients_per_slot INTEGER DEFAULT 1,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT valid_time_range CHECK (start_time < end_time)
);

-- Create Appointments table
CREATE TABLE appointments (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER REFERENCES patients(id) ON DELETE CASCADE,
    doctor_id INTEGER REFERENCES doctors(id) ON DELETE CASCADE,
    appointment_date DATE NOT NULL,
    appointment_time TIME NOT NULL,
    duration INTEGER DEFAULT 30, -- Duration in minutes
    status VARCHAR(20) DEFAULT 'scheduled' CHECK (status IN ('scheduled', 'confirmed', 'completed', 'cancelled', 'no_show')),
    reason_for_visit TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(doctor_id, appointment_date, appointment_time)
);

-- Create indexes for better performance
CREATE INDEX idx_doctors_specialization ON doctors(specialization_id);
CREATE INDEX idx_doctor_availability_doctor ON doctor_availability(doctor_id);
CREATE INDEX idx_doctor_availability_day ON doctor_availability(day_of_week);
CREATE INDEX idx_appointments_doctor_date ON appointments(doctor_id, appointment_date);
CREATE INDEX idx_appointments_patient ON appointments(patient_id);
CREATE INDEX idx_appointments_status ON appointments(status);

-- Insert sample data

-- Specializations
INSERT INTO specializations (name, description) VALUES
('Cardiology', 'Heart and cardiovascular system specialist'),
('Dermatology', 'Skin, hair, and nail specialist'),
('Pediatrics', 'Child healthcare specialist'),
('Orthopedics', 'Bone and joint specialist'),
('Neurology', 'Brain and nervous system specialist'),
('General Medicine', 'Primary care and general health');

-- Doctors
INSERT INTO doctors (first_name, last_name, email, phone, specialization_id, license_number, experience_years, consultation_fee) VALUES
('John', 'Smith', 'john.smith@hospital.com', '+1-555-0101', 1, 'MD001', 15, 200.00),
('Sarah', 'Johnson', 'sarah.johnson@hospital.com', '+1-555-0102', 2, 'MD002', 8, 180.00),
('Michael', 'Brown', 'michael.brown@hospital.com', '+1-555-0103', 3, 'MD003', 12, 150.00),
('Emily', 'Davis', 'emily.davis@hospital.com', '+1-555-0104', 4, 'MD004', 10, 220.00),
('David', 'Wilson', 'david.wilson@hospital.com', '+1-555-0105', 5, 'MD005', 18, 250.00),
('Lisa', 'Anderson', 'lisa.anderson@hospital.com', '+1-555-0106', 6, 'MD006', 6, 120.00);

-- Additional Doctors
INSERT INTO doctors (first_name, last_name, email, phone, specialization_id, license_number, experience_years, consultation_fee) VALUES
('Karen', 'Lee', 'karen.lee@hospital.com', '+1-555-0107', 1, 'MD007', 5, 180.00),
('Brian', 'Clark', 'brian.clark@hospital.com', '+1-555-0108', 4, 'MD008', 7, 210.00),
('Sophia', 'Turner', 'sophia.turner@hospital.com', '+1-555-0109', 3, 'MD009', 9, 160.00);

-- Patients
INSERT INTO patients (first_name, last_name, email, phone, date_of_birth, gender, address, emergency_contact_name, emergency_contact_phone) VALUES
('Alice', 'Cooper', 'alice.cooper@email.com', '+1-555-1001', '1985-03-15', 'Female', '123 Main St, City, State 12345', 'Bob Cooper', '+1-555-1002'),
('Robert', 'Taylor', 'robert.taylor@email.com', '+1-555-1003', '1978-07-22', 'Male', '456 Oak Ave, City, State 12345', 'Mary Taylor', '+1-555-1004'),
('Jennifer', 'White', 'jennifer.white@email.com', '+1-555-1005', '1990-11-08', 'Female', '789 Pine Rd, City, State 12345', 'James White', '+1-555-1006'),
('William', 'Harris', 'william.harris@email.com', '+1-555-1007', '1972-05-30', 'Male', '321 Elm St, City, State 12345', 'Susan Harris', '+1-555-1008'),
('Maria', 'Garcia', 'maria.garcia@email.com', '+1-555-1009', '1988-09-12', 'Female', '654 Maple Dr, City, State 12345', 'Carlos Garcia', '+1-555-1010'),
('James', 'Martinez', 'james.martinez@email.com', '+1-555-1011', '1995-01-25', 'Male', '987 Cedar Ln, City, State 12345', 'Rosa Martinez', '+1-555-1012');

-- Additional Patients
INSERT INTO patients (first_name, last_name, email, phone, date_of_birth, gender, address, emergency_contact_name, emergency_contact_phone) VALUES
('Angela', 'Scott', 'angela.scott@email.com', '+1-555-1013', '1992-04-18', 'Female', '111 Cherry St, City, State 12345', 'Mark Scott', '+1-555-1014'),
('Steven', 'Young', 'steven.young@email.com', '+1-555-1015', '1983-12-05', 'Male', '222 Birch Ave, City, State 12345', 'Laura Young', '+1-555-1016'),
('Laura', 'Adams', 'laura.adams@email.com', '+1-555-1017', '1975-09-09', 'Female', '333 Walnut Rd, City, State 12345', 'Peter Adams', '+1-555-1018');

-- Doctor Availability (Monday to Friday, various times)
INSERT INTO doctor_availability (doctor_id, day_of_week, start_time, end_time, slot_duration, max_patients_per_slot) VALUES
-- Dr. John Smith (Cardiology) - Monday to Friday
(1, 1, '09:00:00', '17:00:00', 30, 1), -- Monday
(1, 2, '09:00:00', '17:00:00', 30, 1), -- Tuesday
(1, 3, '09:00:00', '17:00:00', 30, 1), -- Wednesday
(1, 4, '09:00:00', '17:00:00', 30, 1), -- Thursday
(1, 5, '09:00:00', '13:00:00', 30, 1), -- Friday (half day)

-- Dr. Sarah Johnson (Dermatology) - Monday, Wednesday, Friday
(2, 1, '10:00:00', '18:00:00', 45, 1), -- Monday
(2, 3, '10:00:00', '18:00:00', 45, 1), -- Wednesday
(2, 5, '10:00:00', '18:00:00', 45, 1), -- Friday

-- Dr. Michael Brown (Pediatrics) - Monday to Saturday
(3, 1, '08:00:00', '16:00:00', 20, 1), -- Monday
(3, 2, '08:00:00', '16:00:00', 20, 1), -- Tuesday
(3, 3, '08:00:00', '16:00:00', 20, 1), -- Wednesday
(3, 4, '08:00:00', '16:00:00', 20, 1), -- Thursday
(3, 5, '08:00:00', '16:00:00', 20, 1), -- Friday
(3, 6, '09:00:00', '13:00:00', 20, 1), -- Saturday

-- Dr. Emily Davis (Orthopedics) - Tuesday, Thursday, Saturday
(4, 2, '11:00:00', '19:00:00', 60, 1), -- Tuesday
(4, 4, '11:00:00', '19:00:00', 60, 1), -- Thursday
(4, 6, '08:00:00', '14:00:00', 60, 1), -- Saturday

-- Dr. David Wilson (Neurology) - Monday, Wednesday, Friday
(5, 1, '14:00:00', '20:00:00', 45, 1), -- Monday
(5, 3, '14:00:00', '20:00:00', 45, 1), -- Wednesday
(5, 5, '14:00:00', '20:00:00', 45, 1), -- Friday

-- Dr. Lisa Anderson (General Medicine) - Monday to Friday
(6, 1, '08:00:00', '16:00:00', 30, 1), -- Monday
(6, 2, '08:00:00', '16:00:00', 30, 1), -- Tuesday
(6, 3, '08:00:00', '16:00:00', 30, 1), -- Wednesday
(6, 4, '08:00:00', '16:00:00', 30, 1), -- Thursday
(6, 5, '08:00:00', '16:00:00', 30, 1), -- Friday

-- Dr. Karen Lee (Cardiology) - Monday and Wednesday afternoons
(7, 1, '12:00:00', '18:00:00', 30, 1), -- Monday
(7, 3, '12:00:00', '18:00:00', 30, 1), -- Wednesday

-- Dr. Brian Clark (Orthopedics) - Monday, Wednesday, Friday
(8, 1, '09:00:00', '15:00:00', 30, 1), -- Monday
(8, 3, '09:00:00', '15:00:00', 30, 1), -- Wednesday
(8, 5, '09:00:00', '15:00:00', 30, 1), -- Friday

-- Dr. Sophia Turner (Pediatrics) - Tuesday and Thursday
(9, 2, '10:00:00', '18:00:00', 30, 1), -- Tuesday
(9, 4, '10:00:00', '18:00:00', 30, 1); -- Thursday

-- Sample Appointments
INSERT INTO appointments (patient_id, doctor_id, appointment_date, appointment_time, duration, status, reason_for_visit, notes) VALUES
(1, 1, '2025-07-21', '09:30:00', 30, 'scheduled', 'Chest pain evaluation', 'Patient reports intermittent chest pain'),
(2, 2, '2025-07-21', '10:45:00', 45, 'confirmed', 'Skin rash consultation', 'Rash on arms and legs'),
(3, 3, '2025-07-22', '08:20:00', 20, 'scheduled', 'Child wellness check', 'Annual checkup for 5-year-old'),
(4, 4, '2025-07-22', '12:00:00', 60, 'scheduled', 'Knee pain assessment', 'Chronic knee pain, possible arthritis'),
(5, 5, '2025-07-23', '14:45:00', 45, 'confirmed', 'Headache consultation', 'Frequent migraines'),
(6, 6, '2025-07-23', '09:00:00', 30, 'scheduled', 'General health checkup', 'Annual physical examination'),
(1, 6, '2025-07-24', '10:30:00', 30, 'completed', 'Follow-up consultation', 'Blood pressure check'),
(2, 1, '2025-07-25', '11:00:00', 30, 'cancelled', 'Cardiac screening', 'Patient cancelled due to schedule conflict');

-- Additional Appointments
INSERT INTO appointments (patient_id, doctor_id, appointment_date, appointment_time, duration, status, reason_for_visit, notes) VALUES
(7, 7, '2025-07-24', '13:00:00', 30, 'scheduled', 'Consultation', 'New patient visit'),
(8, 8, '2025-07-25', '09:30:00', 60, 'scheduled', 'Back pain', 'Severe back pain for weeks'),
(9, 9, '2025-07-26', '10:00:00', 20, 'confirmed', 'Vaccination', 'Annual flu shot');

-- Example queries for reference

/*
-- Query 1: Get all available slots for a specific doctor on a specific date
-- Example: Get available slots for Dr. John Smith (doctor_id = 1) on July 21, 2025 (Monday)
WITH doctor_slots AS (
    SELECT 
        da.doctor_id,
        da.start_time,
        da.end_time,
        da.slot_duration,
        generate_series(
            da.start_time,
            da.end_time - (da.slot_duration || ' minutes')::INTERVAL,
            (da.slot_duration || ' minutes')::INTERVAL
        )::TIME AS slot_time
    FROM doctor_availability da
    WHERE da.doctor_id = 1 
    AND da.day_of_week = EXTRACT(DOW FROM DATE '2025-07-21')
    AND da.is_active = TRUE
),
booked_slots AS (
    SELECT appointment_time
    FROM appointments
    WHERE doctor_id = 1 
    AND appointment_date = '2025-07-21'
    AND status NOT IN ('cancelled')
)
SELECT ds.slot_time AS available_time
FROM doctor_slots ds
LEFT JOIN booked_slots bs ON ds.slot_time = bs.appointment_time
WHERE bs.appointment_time IS NULL
ORDER BY ds.slot_time;

-- Query 2: Get doctor's schedule with appointments for a specific date
SELECT 
    d.first_name || ' ' || d.last_name AS doctor_name,
    s.name AS specialization,
    a.appointment_time,
    a.duration,
    p.first_name || ' ' || p.last_name AS patient_name,
    a.status,
    a.reason_for_visit
FROM doctors d
JOIN specializations s ON d.specialization_id = s.id
LEFT JOIN appointments a ON d.id = a.doctor_id AND a.appointment_date = '2025-07-21'
LEFT JOIN patients p ON a.patient_id = p.id
WHERE d.id = 1
ORDER BY a.appointment_time;

-- Query 3: Get patient's upcoming appointments
SELECT 
    a.appointment_date,
    a.appointment_time,
    d.first_name || ' ' || d.last_name AS doctor_name,
    s.name AS specialization,
    a.status,
    a.reason_for_visit
FROM appointments a
JOIN doctors d ON a.doctor_id = d.id
JOIN specializations s ON d.specialization_id = s.id
WHERE a.patient_id = 1 
AND a.appointment_date >= CURRENT_DATE
AND a.status NOT IN ('cancelled', 'completed')
ORDER BY a.appointment_date, a.appointment_time;
*/