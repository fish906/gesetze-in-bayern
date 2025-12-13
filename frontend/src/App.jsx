import React, { useEffect, useState } from 'react';
import './App.css';

function App() {
  const [laws, setLaws] = useState([]);
  const [norms, setNorms] = useState([]);
  const [selectedLaw, setSelectedLaw] = useState(null);
  const [selectedNorm, setSelectedNorm] = useState(null);
  const [loading, setLoading] = useState(true);

  // Load laws on mount
  useEffect(() => {
    fetch('/api/laws')
      .then((res) => res.json())
      .then((data) => {
        setLaws(data.sort((a, b) => a.name.localeCompare(b.name)));
        setLoading(false);
      })
      .catch((err) => console.error('Fehler beim Laden der Gesetze:', err));
  }, []);

  const loadNorms = (law) => {
    setSelectedLaw(law);
    setSelectedNorm(null);
    setLoading(true);
    fetch(`/api/laws/${law.id}/norms`)
      .then((res) => res.json())
      .then((data) => {
        setNorms(data);
        setLoading(false);
      })
      .catch((err) => console.error('Fehler beim Laden der Normen:', err));
  };

  const loadNormContent = (normId) => {
    setLoading(true);
    fetch(`/api/norms/${normId}`)
      .then((res) => res.json())
      .then((data) => {
        setSelectedNorm(data);
        setLoading(false);
      })
      .catch((err) => console.error('Fehler beim Laden des Inhalts:', err));
  };

  if (loading) return <p className="loading">Lade...</p>;

  return (
    <div className="app">
      {!selectedLaw && (
        <div className="law-list">
          <h1>Gesetze</h1>
          <ul>
            {laws.map((law) => (
              <li key={law.id}>
                <button onClick={() => loadNorms(law)}>{law.name}</button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {selectedLaw && !selectedNorm && (
        <div className="norm-list">
          <h2>{selectedLaw.name}</h2>
          <button onClick={() => setSelectedLaw(null)}>← Zurück</button>
          <ul>
            {norms.map((norm) => (
              <li key={norm.id}>
                <button onClick={() => loadNormContent(norm.id)}>
                  {norm.number} – {norm.title}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {selectedNorm && (
        <div className="norm-container">
          <button onClick={() => setSelectedNorm(null)}>← Zurück</button>
          <h1 className="norm-heading">{selectedNorm.number} – {selectedNorm.title}</h1>
          <div
            className="norm-content"
            dangerouslySetInnerHTML={{ __html: selectedNorm.content }}
          />
        </div>
      )}
    </div>
  );
}

export default App;