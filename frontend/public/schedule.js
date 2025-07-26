function Schedule() {
  const [data, setData] = React.useState([]);

  React.useEffect(() => {
    fetch("http://localhost:8000/doctor_schedule")
      .then(res => res.json())
      .then(setData)
      .catch(console.error);
  }, []);

  const dayNames = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

  return (
    <table className="data-table">
      <thead>
        <tr>
          <th>Doctor</th>
          <th>Day</th>
          <th>Start</th>
          <th>End</th>
        </tr>
      </thead>
      <tbody>
        {data.map((slot, idx) => (
          <tr key={idx} className="table-row">
            <td>{slot.doctor_name}</td>
            <td>{dayNames[slot.day_of_week]}</td>
            <td>{slot.start_time}</td>
            <td>{slot.end_time}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

