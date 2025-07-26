function Admin() {
  const [data, setData] = React.useState([]);

  React.useEffect(() => {
    fetch("http://localhost:8000/admin/appointments")
      .then(res => res.json())
      .then(setData)
      .catch(console.error);
  }, []);

  return (
    <div>
      <h2>Admin Dashboard</h2>
      <table className="admin-table data-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>Patient</th>
            <th>Doctor</th>
            <th>Date</th>
            <th>Time</th>
            <th>Status</th>
            <th>Reason</th>
          </tr>
        </thead>
        <tbody>
          {data.map((a, idx) => (
            <tr key={idx} className="table-row">
              <td>{a.appointment_id}</td>
              <td>{a.patient_id} - {a.patient_name}</td>
              <td>{a.doctor_id} - {a.doctor_name}</td>
              <td>{a.appointment_date}</td>
              <td>{a.appointment_time}</td>
              <td>{a.status}</td>
              <td>{a.reason_for_visit}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

