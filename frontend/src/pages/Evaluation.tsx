// src/pages/Evaluation.tsx
import React from 'react';
import { useNavigate } from 'react-router-dom';

const Evaluation: React.FC = () => {
  const navigate = useNavigate();
  const job = sessionStorage.getItem('lastJob');
  const data = job ? JSON.parse(job) : null;

  if (!data) {
    return (
      <div className="page evaluation-page">
        <h2>No recent evaluation data</h2>
        <button onClick={() => navigate('/process')}>Process a file</button>
      </div>
    );
  }

  const { metrics, audio_base64 } = data;

  return (
    <div className="page evaluation-page">
      <h2>Evaluation Results</h2>
      <pre>{JSON.stringify(metrics, null, 2)}</pre>
      {/* Simple audio playback */}
      <audio controls src={`data:audio/wav;base64,${audio_base64}`} />
    </div>
  );
};

export default Evaluation;
