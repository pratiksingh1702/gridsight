import React from 'react';

const Dashboard = () => {
  return (
    <div style={{ width: '100%', height: '100vh', overflow: 'hidden' }}>
      <iframe 
        src="/demo_standalone.html" 
        style={{ width: '100%', height: '100%', border: 'none' }}
        title="GridSight Demo"
      />
    </div>
  );
};

export default Dashboard;
