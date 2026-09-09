import { BrowserRouter, Routes, Route } from 'react-router-dom';

import Sidebar from './Sidebar';
import GraphPage from './pages/GraphPage';
import AskPage from './pages/AskPage';
import BuildPage from './pages/BuildPage';

function App() {
  return (
    <BrowserRouter>
      <div
        style={{
          display: 'flex',
          width: '100%',
          height: '100%',
        }}
      >
        <Sidebar />

        <Routes>
          <Route path="/" element={<GraphPage />} />
          <Route path="/ask" element={<AskPage />} />
          <Route path="/build" element={<BuildPage />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}

export default App;