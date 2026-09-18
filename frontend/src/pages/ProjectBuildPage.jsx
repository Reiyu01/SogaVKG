import { useParams } from 'react-router-dom';
import BuildPage from './BuildPage';
export default function ProjectBuildPage() { const { projectId } = useParams(); return <BuildPage projectId={projectId} />; }
