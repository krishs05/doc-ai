function Calendar() {
  const [appointments, setAppointments] = React.useState([]);

  React.useEffect(() => {
    fetch("http://localhost:8000/appointments")
      .then(res => res.json())
      .then(data => setAppointments(data))
      .catch(err => console.error(err));
  }, []);

  return (
    <table>
      <thead>
        <tr>
          <th>Department</th>
          <th>Doctor</th>
          <th>Date</th>
          <th>Time</th>
          <th>Status</th>
        </tr>
      </thead>
      <tbody>
        {appointments.map((appt, idx) => {
          const date = new Date(appt.time_slot);
          const statusClass = appt.status === 'scheduled'
            ? 'busy'
            : (appt.is_available ? 'available' : 'holiday');
          const timeStr = date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
          const dateStr = date.toLocaleDateString();
          return (
            <tr key={idx} className={`table-row ${statusClass}`}>
              <td>{appt.department_name}</td>
              <td>{appt.doctor_name}</td>
              <td>{dateStr}</td>
              <td>{timeStr}</td>
              <td><span className={`status-label ${statusClass}`}>{statusClass}</span></td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
