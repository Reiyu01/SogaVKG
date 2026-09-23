import { useParams } from 'react-router-dom';
import LazyProjectedGraph from '../LazyProjectedGraph';

export default function ProjectGraphPage() {
  const { projectId } = useParams();
  return <div style={{ flex: 1, height: '100vh', overflow: 'hidden' }}><LazyProjectedGraph projectId={projectId} /></div>;
}
