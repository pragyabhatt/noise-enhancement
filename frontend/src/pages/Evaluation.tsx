import React from 'react';
import { useNavigate } from 'react-router-dom';

const Evaluation: React.FC = () => {
  const navigate = useNavigate();
  const jobData = sessionStorage.getItem('lastJob');
  const data = jobData ? JSON.parse(jobData) : null;

  if (!data) {
    return (
      <div className="page evaluation-page">
        <h2>No recent evaluation data</h2>
        <button onClick={() => navigate('/process')} className="mt-4 px-4 py-2 bg-[#00e5ff] text-[#0f172a] rounded hover:bg-[#00c4e0]">
          Process a file
        </button>
      </div>
    );
  }

  const { metrics, audio_base64 } = data;

  return (
    <div className="page evaluation-page space-y-6">
      <h2 className="text-2xl font-bold text-[#e0e7ff]">Evaluation Results</h2>
      <div className="bg-[#1e293b] bg-opacity-80 backdrop-filter backdrop-blur-md p-4 rounded-lg text-[#e0e7ff]">
        <pre className="whitespace-pre-wrap break-words">{JSON.stringify(metrics, null, 2)}</pre>
      </div>
      <div className="flex items-center space-x-4">
        <audio controls className="w-full" src={`data:audio/wav;base64,${audio_base64}`} />
      </div>
    </div>
  );
};

export default Evaluation;
