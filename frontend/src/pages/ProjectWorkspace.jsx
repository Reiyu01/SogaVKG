import { NavLink, Outlet, useParams } from 'react-router-dom';

export default function ProjectWorkspace() {
  const { projectId } = useParams();
  const link = ({ isActive }) => ({ padding: '8px 12px', borderRadius: 6, textDecoration: 'none', color: isActive ? '#185fa5' : '#555', background: isActive ? '#e6f1fb' : 'transparent' });
  return <div style={{ flex: 1, minWidth: 0 }}>
    <nav style={{ padding: '14px 28px', borderBottom: '1px solid #eee', display: 'flex', gap: 8 }}>
      <NavLink to={`/projects/${projectId}`} end style={link}>概覽</NavLink>
      <NavLink to={`/projects/${projectId}/mappings`} style={link}>Mapping 版本</NavLink>
      <NavLink to={`/projects/${projectId}/sources`} style={link}>資料來源</NavLink>
      <NavLink to={`/projects/${projectId}/build`} style={link}>建置資料</NavLink>
      <NavLink to={`/projects/${projectId}/graph`} style={link}>知識圖譜</NavLink>
      <NavLink to={`/projects/${projectId}/ask`} style={link}>AI 檢索</NavLink>
    </nav>
    <Outlet />
  </div>;
}
