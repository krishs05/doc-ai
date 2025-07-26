function Patients() {
  const [patients, setPatients] = React.useState([]);

  React.useEffect(() => {
    fetch("http://localhost:8000/patients")
      .then(res => res.json())
      .then(setPatients)
      .catch(console.error);
  }, []);

  return (
    <table className="data-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>Name</th>
          <th>Email</th>
          <th>Phone</th>
        </tr>
      </thead>
      <tbody>
        {patients.map(p => (
          <tr key={p.id} className="table-row">
            <td>{p.id}</td>
            <td>{p.first_name} {p.last_name}</td>
            <td>{p.email}</td>
            <td>{p.phone}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

