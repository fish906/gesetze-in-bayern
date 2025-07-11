import React, { useEffect, useState } from 'react';
import './App.css';

function App() {
  const [norm, setNorm] = useState(null);

  useEffect(() => {
    fetch('/api/article-one')
      .then((res) => res.json())
      .then((data) => setNorm(data))
      .catch((err) => console.error('Fehler beim Laden:', err));
  }, []);

  if (!norm) return <p className="loading">Lade...</p>;

  return (
    <div className="app">
      <div className="norm-container">
        <h1 className="norm-heading">{norm.number} – {norm.title}</h1>
        <div
          className="norm-content"
          dangerouslySetInnerHTML={{ __html: norm.content }}
        />
      </div>
    </div>
  );
}

export default App;
