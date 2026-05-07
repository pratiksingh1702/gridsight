import React from 'react';

const Home = () => {
  return (
    <div style={{ width: '100%', height: '100vh', overflow: 'hidden' }}>
      <iframe 
        src="/landing_standalone.html" 
        style={{ width: '100%', height: '100%', border: 'none' }}
        title="GridSight Home"
      />
    </div>
  );
};

export default Home;
