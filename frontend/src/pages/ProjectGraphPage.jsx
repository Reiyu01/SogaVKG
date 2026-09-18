import { useParams } from 'react-router-dom';
import SemanticGraph from '../SemanticGraph';

export default function ProjectGraphPage() {
  const { projectId } = useParams();
  return <div style={{ flex: 1, height: '100vh', overflow: 'hidden' }}><SemanticGraph projectId={projectId} /></div>;
}
