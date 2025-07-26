function Departments() {
  const [data, setData] = React.useState([]);

  React.useEffect(() => {
    fetch("http://localhost:8000/departments")
      .then(res => res.json())
      .then(setData)
      .catch(console.error);
  }, []);

  const grouped = {};
  data.forEach(item => {
    if (!grouped[item.department_name]) {
      grouped[item.department_name] = [];
    }
    grouped[item.department_name].push(item.doctor_name);
  });

  return (
    <div className="departments">
      {Object.entries(grouped).map(([dept, docs]) => (
        <div key={dept} className="department">
          <h3>{dept}</h3>
          <ul>
            {docs.map((d, i) => <li key={i}>{d}</li>)}
          </ul>
        </div>
      ))}
    </div>
  );
}
