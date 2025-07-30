-- Doctor Availability and Appointment Management System
-- PostgreSQL Database Schema - Updated to match current data structure

-- Drop tables if they exist (for fresh setup)
DROP TABLE IF EXISTS appointments CASCADE;
DROP TABLE IF EXISTS doctor_availability CASCADE;
DROP TABLE IF EXISTS patients CASCADE;
DROP TABLE IF EXISTS doctors CASCADE;
DROP TABLE IF EXISTS specializations CASCADE;
DROP TABLE IF EXISTS departments CASCADE;

-- Create Specializations table (primary specializations system)
CREATE TABLE specializations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create Departments table (alternative organization method)
CREATE TABLE departments (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create Doctors table
CREATE TABLE doctors (
    id SERIAL PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    phone VARCHAR(20),
    specialization_id INTEGER REFERENCES specializations(id),
    department_id INTEGER REFERENCES departments(id),
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
    medical_history TEXT,
    allergies TEXT,
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
    prescription TEXT,
    follow_up_required BOOLEAN DEFAULT FALSE,
    follow_up_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(doctor_id, appointment_date, appointment_time)
);

-- Create indexes for better performance
CREATE INDEX idx_doctors_specialization ON doctors(specialization_id);
CREATE INDEX idx_doctors_department ON doctors(department_id);
CREATE INDEX idx_doctor_availability_doctor ON doctor_availability(doctor_id);
CREATE INDEX idx_doctor_availability_day ON doctor_availability(day_of_week);
CREATE INDEX idx_appointments_doctor_date ON appointments(doctor_id, appointment_date);
CREATE INDEX idx_appointments_patient ON appointments(patient_id);
CREATE INDEX idx_appointments_status ON appointments(status);
CREATE INDEX idx_appointments_date ON appointments(appointment_date);
CREATE INDEX idx_patients_email ON patients(email);
CREATE INDEX idx_doctors_email ON doctors(email);

-- Insert Medical Specializations
INSERT INTO specializations (name, description) VALUES
('Cardiology', 'Heart and cardiovascular system disorders'),
('Dermatology', 'Skin, hair, and nail conditions'),
('Pediatrics', 'Medical care for infants, children, and adolescents'),
('Orthopedics', 'Musculoskeletal system disorders'),
('Neurology', 'Nervous system disorders'),
('General Medicine', 'Primary healthcare and general medical conditions'),
('Oncology', 'Cancer diagnosis and treatment'),
('Psychiatry', 'Mental health and behavioral disorders'),
('Gynecology', 'Female reproductive health'),
('Ophthalmology', 'Eye and vision care'),
('ENT', 'Ear, nose, and throat disorders'),
('Gastroenterology', 'Digestive system disorders'),
('Endocrinology', 'Hormone and endocrine system disorders'),
('Pulmonology', 'Respiratory system disorders'),
('Rheumatology', 'Autoimmune and inflammatory conditions');

-- Insert Departments (for organizational purposes)
INSERT INTO departments (name, description) VALUES
('Emergency Medicine', 'Emergency and urgent care services'),
('Internal Medicine', 'Adult comprehensive medical care'),
('Surgery', 'Surgical procedures and interventions'),
('Pediatrics', 'Child and adolescent healthcare'),
('Women''s Health', 'Women''s reproductive and general health'),
('Mental Health', 'Psychiatric and psychological services'),
('Diagnostic Services', 'Laboratory and imaging services'),
('Rehabilitation', 'Physical therapy and rehabilitation services');

-- Insert Sample Doctors
INSERT INTO doctors (first_name, last_name, email, phone, specialization_id, department_id, license_number, experience_years, consultation_fee) VALUES
('John', 'Smith', 'john.smith@docai.com', '555-0101', 1, 2, 'MD001', 15, 250.00),
('Sarah', 'Johnson', 'sarah.johnson@docai.com', '555-0102', 5, 2, 'MD002', 12, 300.00),
('Michael', 'Brown', 'michael.brown@docai.com', '555-0103', 3, 4, 'MD003', 8, 200.00),
('Emily', 'Davis', 'emily.davis@docai.com', '555-0104', 4, 3, 'MD004', 10, 280.00),
('David', 'Wilson', 'david.wilson@docai.com', '555-0105', 6, 2, 'MD005', 20, 180.00),
('Lisa', 'Anderson', 'lisa.anderson@docai.com', '555-0106', 6, 2, 'MD006', 7, 150.00),
('Karen', 'Lee', 'karen.lee@docai.com', '555-0107', 1, 2, 'MD007', 18, 270.00),
('Brian', 'Clark', 'brian.clark@docai.com', '555-0108', 4, 3, 'MD008', 14, 320.00),
('Sophia', 'Turner', 'sophia.turner@docai.com', '555-0109', 3, 4, 'MD009', 9, 220.00),
('Amanda', 'Rodriguez', 'amanda.rodriguez@docai.com', '555-0110', 2, 2, 'MD010', 11, 240.00),
('James', 'Taylor', 'james.taylor@docai.com', '555-0111', 8, 6, 'MD011', 16, 350.00),
('Michelle', 'White', 'michelle.white@docai.com', '555-0112', 9, 5, 'MD012', 13, 290.00);

-- Insert Sample Patients
INSERT INTO patients (first_name, last_name, email, phone, date_of_birth, gender, address, emergency_contact_name, emergency_contact_phone) VALUES
('Alice', 'Johnson', 'alice.johnson@email.com', '555-1001', '1985-03-15', 'Female', '123 Main St, City, State 12345', 'Bob Johnson', '555-1002'),
('Robert', 'Williams', 'robert.williams@email.com', '555-1003', '1978-07-22', 'Male', '456 Oak Ave, City, State 12345', 'Mary Williams', '555-1004'),
('Jennifer', 'Brown', 'jennifer.brown@email.com', '555-1005', '1992-11-08', 'Female', '789 Pine St, City, State 12345', 'Tom Brown', '555-1006'),
('Michael', 'Davis', 'michael.davis@email.com', '555-1007', '1965-04-30', 'Male', '321 Elm St, City, State 12345', 'Susan Davis', '555-1008'),
('Sarah', 'Miller', 'sarah.miller@email.com', '555-1009', '1988-09-12', 'Female', '654 Maple Ave, City, State 12345', 'John Miller', '555-1010'),
('Christopher', 'Wilson', 'christopher.wilson@email.com', '555-1011', '1975-12-05', 'Male', '987 Cedar St, City, State 12345', 'Lisa Wilson', '555-1012'),
('Jessica', 'Garcia', 'jessica.garcia@email.com', '555-1013', '1990-06-18', 'Female', '147 Birch Ave, City, State 12345', 'Carlos Garcia', '555-1014'),
('Daniel', 'Martinez', 'daniel.martinez@email.com', '555-1015', '1982-01-25', 'Male', '258 Spruce St, City, State 12345', 'Maria Martinez', '555-1016'),
('Ashley', 'Anderson', 'ashley.anderson@email.com', '555-1017', '1995-08-14', 'Female', '369 Willow Ave, City, State 12345', 'David Anderson', '555-1018'),
('Matthew', 'Taylor', 'matthew.taylor@email.com', '555-1019', '1972-10-03', 'Male', '741 Poplar St, City, State 12345', 'Nancy Taylor', '555-1020');

-- Insert Doctor Availability (Current Schedule)
INSERT INTO doctor_availability (doctor_id, day_of_week, start_time, end_time, slot_duration, max_patients_per_slot) VALUES
-- Dr. John Smith (Cardiology) - Monday, Wednesday, Friday
(1, 1, '09:00:00', '17:00:00', 45, 1), -- Monday
(1, 3, '09:00:00', '17:00:00', 45, 1), -- Wednesday
(1, 5, '09:00:00', '17:00:00', 45, 1), -- Friday

-- Dr. Sarah Johnson (Neurology) - Tuesday, Thursday
(2, 2, '10:00:00', '18:00:00', 60, 1), -- Tuesday
(2, 4, '10:00:00', '18:00:00', 60, 1), -- Thursday

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

-- Dr. David Wilson (General Medicine) - Monday to Friday
(5, 1, '08:00:00', '16:00:00', 30, 1), -- Monday
(5, 2, '08:00:00', '16:00:00', 30, 1), -- Tuesday
(5, 3, '08:00:00', '16:00:00', 30, 1), -- Wednesday
(5, 4, '08:00:00', '16:00:00', 30, 1), -- Thursday
(5, 5, '08:00:00', '16:00:00', 30, 1), -- Friday

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
(9, 4, '10:00:00', '18:00:00', 30, 1), -- Thursday

-- Dr. Amanda Rodriguez (Dermatology) - Monday, Wednesday, Friday
(10, 1, '09:00:00', '17:00:00', 30, 1), -- Monday
(10, 3, '09:00:00', '17:00:00', 30, 1), -- Wednesday
(10, 5, '09:00:00', '17:00:00', 30, 1), -- Friday

-- Dr. James Taylor (Psychiatry) - Tuesday to Friday
(11, 2, '10:00:00', '18:00:00', 60, 1), -- Tuesday
(11, 3, '10:00:00', '18:00:00', 60, 1), -- Wednesday
(11, 4, '10:00:00', '18:00:00', 60, 1), -- Thursday
(11, 5, '10:00:00', '18:00:00', 60, 1), -- Friday

-- Dr. Michelle White (Gynecology) - Monday, Wednesday, Friday
(12, 1, '09:00:00', '17:00:00', 45, 1), -- Monday
(12, 3, '09:00:00', '17:00:00', 45, 1), -- Wednesday
(12, 5, '09:00:00', '17:00:00', 45, 1); -- Friday

-- Insert Current Appointments (July 2025)
INSERT INTO appointments (patient_id, doctor_id, appointment_date, appointment_time, duration, status, reason_for_visit, notes) VALUES
(1, 1, '2025-07-30', '09:30:00', 45, 'scheduled', 'Chest pain evaluation', 'Patient reports intermittent chest pain'),
(2, 10, '2025-07-30', '10:00:00', 30, 'confirmed', 'Skin rash consultation', 'Rash on arms and legs'),
(3, 3, '2025-07-31', '08:20:00', 20, 'scheduled', 'Child wellness check', 'Annual checkup for 5-year-old'),
(4, 4, '2025-07-31', '12:00:00', 60, 'scheduled', 'Knee pain assessment', 'Chronic knee pain, possible arthritis'),
(5, 2, '2025-08-01', '14:45:00', 60, 'confirmed', 'Headache consultation', 'Frequent migraines'),
(6, 5, '2025-08-01', '09:00:00', 30, 'scheduled', 'General health checkup', 'Annual physical examination'),
(1, 6, '2025-08-02', '10:30:00', 30, 'completed', 'Follow-up consultation', 'Blood pressure check'),
(2, 1, '2025-08-02', '11:00:00', 45, 'cancelled', 'Cardiac screening', 'Patient cancelled due to schedule conflict'),
(7, 7, '2025-08-05', '13:00:00', 30, 'scheduled', 'Heart palpitations', 'New patient visit'),
(8, 8, '2025-08-05', '09:30:00', 30, 'scheduled', 'Back pain', 'Severe back pain for weeks'),
(9, 9, '2025-08-06', '10:00:00', 30, 'confirmed', 'Vaccination', 'Annual flu shot'),
(10, 11, '2025-08-06', '14:00:00', 60, 'scheduled', 'Anxiety consultation', 'Work-related stress and anxiety');

-- Future Appointments (August-December 2025) - Random realistic data
INSERT INTO appointments (patient_id, doctor_id, appointment_date, appointment_time, duration, status, reason_for_visit, notes) VALUES
-- August 2025
(3, 12, '2025-08-07', '10:00:00', 45, 'scheduled', 'Gynecological checkup', 'Annual women''s health exam'),
(4, 10, '2025-08-08', '14:30:00', 30, 'scheduled', 'Mole examination', 'Suspicious mole on back'),
(5, 5, '2025-08-12', '11:15:00', 30, 'scheduled', 'Blood pressure follow-up', 'Hypertension management'),
(6, 3, '2025-08-14', '09:00:00', 20, 'scheduled', 'Child vaccination', '2-year-old immunizations'),
(7, 8, '2025-08-15', '13:30:00', 30, 'scheduled', 'Shoulder pain', 'Sports injury assessment'),
(8, 2, '2025-08-19', '15:00:00', 60, 'scheduled', 'Memory concerns', 'Cognitive assessment'),
(9, 1, '2025-08-21', '10:45:00', 45, 'scheduled', 'Chest X-ray follow-up', 'Review cardiac imaging'),
(10, 11, '2025-08-22', '16:00:00', 60, 'scheduled', 'Depression screening', 'Mental health evaluation'),
(1, 4, '2025-08-26', '11:00:00', 60, 'scheduled', 'Hip pain evaluation', 'Arthritis screening'),
(2, 9, '2025-08-28', '14:00:00', 30, 'scheduled', 'Child behavioral concerns', 'ADHD consultation'),

-- September 2025
(3, 7, '2025-09-02', '12:30:00', 30, 'scheduled', 'Heart murmur check', 'Follow-up cardiology'),
(4, 5, '2025-09-04', '08:30:00', 30, 'scheduled', 'Diabetes management', 'Blood sugar control'),
(5, 12, '2025-09-09', '11:00:00', 45, 'scheduled', 'Prenatal consultation', 'First trimester checkup'),
(6, 10, '2025-09-11', '15:30:00', 30, 'scheduled', 'Acne treatment', 'Dermatology follow-up'),
(7, 3, '2025-09-16', '10:20:00', 20, 'scheduled', 'Growth assessment', 'Pediatric development check'),
(8, 8, '2025-09-18', '14:00:00', 30, 'scheduled', 'Physical therapy referral', 'Post-surgery rehabilitation'),
(9, 11, '2025-09-23', '11:30:00', 60, 'scheduled', 'Couples therapy', 'Relationship counseling'),
(10, 2, '2025-09-25', '13:15:00', 60, 'scheduled', 'Seizure evaluation', 'Neurological assessment'),
(1, 1, '2025-09-30', '09:00:00', 45, 'scheduled', 'Annual cardiac screening', 'Preventive cardiology'),

-- October 2025
(2, 6, '2025-10-03', '10:00:00', 30, 'scheduled', 'Flu vaccination', 'Annual immunization'),
(3, 4, '2025-10-07', '12:00:00', 60, 'scheduled', 'Knee replacement consultation', 'Surgical evaluation'),
(4, 12, '2025-10-10', '14:30:00', 45, 'scheduled', 'Menopause management', 'Hormone therapy discussion'),
(5, 10, '2025-10-14', '09:30:00', 30, 'scheduled', 'Psoriasis treatment', 'Chronic skin condition'),
(6, 9, '2025-10-17', '11:00:00', 30, 'scheduled', 'Learning disability assessment', 'Educational evaluation'),
(7, 5, '2025-10-21', '15:00:00', 30, 'scheduled', 'Cholesterol check', 'Lipid panel review'),
(8, 11, '2025-10-24', '10:30:00', 60, 'scheduled', 'PTSD therapy', 'Trauma counseling'),
(9, 7, '2025-10-28', '13:00:00', 30, 'scheduled', 'Arrhythmia monitoring', 'Heart rhythm check'),
(10, 8, '2025-10-31', '11:30:00', 30, 'scheduled', 'Arthritis management', 'Joint pain treatment'),

-- November 2025
(1, 2, '2025-11-05', '14:00:00', 60, 'scheduled', 'Migraine management', 'Headache specialist'),
(2, 3, '2025-11-08', '08:40:00', 20, 'scheduled', 'Asthma check', 'Respiratory assessment'),
(3, 10, '2025-11-12', '16:00:00', 30, 'scheduled', 'Eczema treatment', 'Skin condition follow-up'),
(4, 11, '2025-11-15', '12:00:00', 60, 'scheduled', 'Anxiety medication review', 'Psychiatric follow-up'),
(5, 1, '2025-11-19', '09:15:00', 45, 'scheduled', 'Stress test', 'Cardiac function evaluation'),
(6, 12, '2025-11-22', '10:45:00', 45, 'scheduled', 'Birth control consultation', 'Contraceptive options'),
(7, 4, '2025-11-26', '13:30:00', 60, 'scheduled', 'Spinal fusion follow-up', 'Post-operative care'),
(8, 5, '2025-11-29', '14:15:00', 30, 'scheduled', 'Thyroid function test', 'Endocrine evaluation'),

-- December 2025
(9, 8, '2025-12-03', '10:00:00', 30, 'scheduled', 'Osteoporosis screening', 'Bone density assessment'),
(10, 9, '2025-12-06', '15:30:00', 30, 'scheduled', 'ADHD medication adjustment', 'Pediatric psychiatry'),
(1, 6, '2025-12-10', '11:00:00', 30, 'scheduled', 'Annual physical', 'Comprehensive health exam'),
(2, 7, '2025-12-13', '12:30:00', 30, 'scheduled', 'Blood pressure medication', 'Hypertension follow-up'),
(3, 11, '2025-12-17', '14:00:00', 60, 'scheduled', 'Seasonal depression', 'Winter blues counseling'),
(4, 2, '2025-12-20', '10:30:00', 60, 'scheduled', 'Parkinson''s evaluation', 'Movement disorder assessment'),
(5, 4, '2025-12-23', '09:00:00', 60, 'scheduled', 'Joint replacement consultation', 'Orthopedic surgery'),
(6, 10, '2025-12-27', '13:45:00', 30, 'scheduled', 'Year-end skin check', 'Melanoma screening'),
(7, 12, '2025-12-30', '11:15:00', 45, 'scheduled', 'Pregnancy planning', 'Preconception counseling');

-- Create a view for easy appointment querying
CREATE VIEW appointment_details AS
SELECT 
    a.id,
    a.appointment_date,
    a.appointment_time,
    a.duration,
    a.status,
    a.reason_for_visit,
    a.notes,
    p.first_name || ' ' || p.last_name as patient_name,
    p.phone as patient_phone,
    p.email as patient_email,
    d.first_name || ' ' || d.last_name as doctor_name,
    d.phone as doctor_phone,
    d.email as doctor_email,
    s.name as specialization,
    dept.name as department,
    d.consultation_fee
FROM appointments a
JOIN patients p ON a.patient_id = p.id
JOIN doctors d ON a.doctor_id = d.id
JOIN specializations s ON d.specialization_id = s.id
LEFT JOIN departments dept ON d.department_id = dept.id
ORDER BY a.appointment_date DESC, a.appointment_time DESC;

-- Create a view for doctor schedules
CREATE VIEW doctor_schedule_view AS
SELECT 
    d.id as doctor_id,
    d.first_name || ' ' || d.last_name as doctor_name,
    s.name as specialization,
    da.day_of_week,
    CASE da.day_of_week
        WHEN 0 THEN 'Sunday'
        WHEN 1 THEN 'Monday'
        WHEN 2 THEN 'Tuesday'
        WHEN 3 THEN 'Wednesday'
        WHEN 4 THEN 'Thursday'
        WHEN 5 THEN 'Friday'
        WHEN 6 THEN 'Saturday'
    END as day_name,
    da.start_time,
    da.end_time,
    da.slot_duration,
    da.max_patients_per_slot,
    d.consultation_fee
FROM doctors d
JOIN specializations s ON d.specialization_id = s.id
JOIN doctor_availability da ON d.id = da.doctor_id
WHERE d.is_active = TRUE AND da.is_active = TRUE
ORDER BY d.last_name, d.first_name, da.day_of_week, da.start_time;

-- Example useful queries for the application

/*
-- Query 1: Get all available slots for a specific doctor on a specific date
SELECT 
    da.start_time,
    da.end_time,
    da.slot_duration,
    COUNT(a.id) as booked_slots
FROM doctor_availability da
LEFT JOIN appointments a ON da.doctor_id = a.doctor_id 
    AND EXTRACT(DOW FROM a.appointment_date) = da.day_of_week
    AND a.appointment_time BETWEEN da.start_time AND da.end_time
    AND a.appointment_date = '2025-08-01'  -- Replace with target date
WHERE da.doctor_id = 1  -- Replace with doctor ID
    AND da.day_of_week = EXTRACT(DOW FROM '2025-08-01'::date)
    AND da.is_active = TRUE
GROUP BY da.start_time, da.end_time, da.slot_duration, da.max_patients_per_slot
HAVING COUNT(a.id) < da.max_patients_per_slot;

-- Query 2: Get upcoming appointments for a patient
SELECT * FROM appointment_details 
WHERE patient_email = 'alice.johnson@email.com' 
    AND appointment_date >= CURRENT_DATE 
ORDER BY appointment_date, appointment_time;

-- Query 3: Get doctor's schedule for this week
SELECT * FROM doctor_schedule_view 
WHERE doctor_id = 1 
ORDER BY day_of_week, start_time;

-- Query 4: Get all appointments for a specific day
SELECT * FROM appointment_details 
WHERE appointment_date = '2025-08-01' 
ORDER BY appointment_time;

-- Query 5: Search doctors by specialization
SELECT d.*, s.name as specialization
FROM doctors d
JOIN specializations s ON d.specialization_id = s.id
WHERE s.name ILIKE '%cardiology%'  -- Replace with desired specialization
    AND d.is_active = TRUE;

-- Query 6: Get appointment statistics by month
SELECT 
    DATE_TRUNC('month', appointment_date) as month,
    COUNT(*) as total_appointments,
    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
    COUNT(CASE WHEN status = 'cancelled' THEN 1 END) as cancelled,
    COUNT(CASE WHEN status = 'no_show' THEN 1 END) as no_shows
FROM appointments
WHERE appointment_date >= '2025-01-01'
GROUP BY DATE_TRUNC('month', appointment_date)
ORDER BY month;

-- Query 7: Find available doctors by specialization and date
SELECT DISTINCT d.id, d.first_name, d.last_name, s.name as specialization
FROM doctors d
JOIN specializations s ON d.specialization_id = s.id
JOIN doctor_availability da ON d.id = da.doctor_id
WHERE s.name = 'Cardiology'  -- Replace with desired specialization
    AND da.day_of_week = EXTRACT(DOW FROM '2025-08-01'::date)  -- Replace with target date
    AND da.is_active = TRUE
    AND d.is_active = TRUE;
*/