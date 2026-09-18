import { BrowserRouter, Routes, Route } from 'react-router-dom';

import Sidebar from './Sidebar';
import GraphPage from './pages/GraphPage';
import AskPage from './pages/AskPage';
import BuildPage from './pages/BuildPage';
import ProjectGraphPage from './pages/ProjectGraphPage';
import ProjectsPage from './pages/ProjectsPage';
import ProjectWorkspace from './pages/ProjectWorkspace';
import ProjectBuildPage from './pages/ProjectBuildPage';
import ProjectAskPage from './pages/ProjectAskPage';
import ProjectOverviewPage from './pages/ProjectOverviewPage';
import MappingVersionsPage from './pages/MappingVersionsPage';
import SourcesPage from './pages/SourcesPage';

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
          <Route path="/" element={<ProjectsPage />} />
          <Route path="/ask" element={<AskPage />} />
          <Route path="/build" element={<BuildPage />} />
          <Route path="/projects/:projectId" element={<ProjectWorkspace />}>
            <Route index element={<ProjectOverviewPage />} />
            <Route path="mappings" element={<MappingVersionsPage />} />
            <Route path="sources" element={<SourcesPage />} />
            <Route path="build" element={<ProjectBuildPage />} />
            <Route path="graph" element={<ProjectGraphPage />} />
            <Route path="ask" element={<ProjectAskPage />} />
          </Route>
        </Routes>
      </div>
    </BrowserRouter>
  );
}

export default App;
