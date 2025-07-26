# Doc-AI

Doc-AI is a small demo that uses FastAPI together with AWS Bedrock and Langchain to answer questions about a hospital appointment database. A minimal React frontend is provided for interacting with the backend service.

## Setup

1. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```
   This installs Langchain and other packages required by the backend.
2. **Install frontend dependencies**
   ```bash
   cd frontend
   npm install
   ```
3. **Environment variables**
   The application requires the following variables:
   - AWS credentials with access to Bedrock (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and optional `AWS_REGION`).
   - `DB_USER` – PostgreSQL username (default: `postgres`).
   - `DB_PASS` – PostgreSQL password (default: `postgres`).
   - `DB_HOST` – PostgreSQL host and port, e.g. `127.0.0.1:5432`.
   - `DB_NAME` – Database name (default: `hospital`).

   These may be placed in your shell profile or exported before running the server.

4. **Initialize the database**
   Ensure PostgreSQL is running and then load the schema:
  ```bash
   psql -U $DB_USER -h ${DB_HOST%%:*} -d $DB_NAME -f schema.sql
  ```

This will create all tables defined in `schema.sql` and insert sample data for doctors, patients and appointments. The script now includes a few additional doctors, patients and appointment entries to make testing easier.

## Running the project

1. **Start the FastAPI server**
   ```bash
   python main.py
   ```
   The API will listen on port `8000`.

   Available endpoints include:
   - `POST /ask` – ask a natural language question about the database.
   - `GET /appointments` – list scheduled appointments with doctor and department details.
   - `POST /appointments` – create a new appointment.
   - `DELETE /appointments/{id}` – cancel an appointment.
   - `POST /patients` – register a new patient.
   - `GET /patients` – list all registered patients.
   - `GET /next_appointment` – fetch the next upcoming appointment, optionally filtered by department.
   - `GET /departments` – list departments and their doctors.
   - `GET /admin/appointments` – full appointment details for the admin page.
   - `GET /doctor_schedule` – list the regular availability for all doctors.

2. **Start the frontend**
   The backend's CORS settings expect the frontend to be served from `http://localhost:5500`.
   ```bash
   cd frontend
   npx serve -l 5500 public
   ```
   Then open `http://localhost:5500` in your browser to interact with the app. The navigation bar now includes **Patients**, **Schedule**, and an **Admin** section showing all appointment data.

***
This repository is a simple example and not intended for production use.
