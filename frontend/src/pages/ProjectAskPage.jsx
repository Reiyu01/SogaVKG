import { useParams } from 'react-router-dom';
import AskPage from './AskPage';
export default function ProjectAskPage() { const { projectId } = useParams(); return <AskPage projectId={projectId} />; }
