import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { apiUrl } from '../config';

export default function ProjectsPage() {
  const [projects, setProjects] = useState([]);
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const [isCreating, setIsCreating] = useState(false);

  const load = async () => {
    const response = await fetch(apiUrl('/builder/projects'));
    if (!response.ok) throw new Error('無法讀取專案列表');
    const data = await response.json();
    setProjects(data.projects || []);
  };
  useEffect(() => { load(); }, []);
  const create = async () => {
    if (!name.trim()) return;
    setError('');
    setIsCreating(true);
    try {
      const res = await fetch(apiUrl('/builder/projects'), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name: name.trim() }) });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail || '建立專案失敗');
      }
      const project = await res.json();
      setProjects((items) => [project, ...items]);
      setName('');
    } catch (err) {
      setError(err instanceof Error ? err.message : '建立專案失敗，請確認後端服務已啟動。');
    } finally {
      setIsCreating(false);
    }
  };

  return <div style={{ flex: 1, padding: '32px 40px' }}>
    <h2 style={{ marginTop: 0 }}>知識圖譜專案</h2>
    <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
      <input value={name} onChange={(e) => setName(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && create()} placeholder="新專案名稱" style={{ padding: '9px 11px', border: '1px solid #ddd', borderRadius: 7 }} />
      <button type="button" onClick={create} disabled={isCreating} style={{ border: 0, borderRadius: 7, padding: '9px 14px', background: '#185fa5', color: '#fff', cursor: isCreating ? 'wait' : 'pointer', opacity: isCreating ? 0.7 : 1 }}>{isCreating ? '建立中…' : '建立專案'}</button>
    </div>
    {error && <p role="alert" style={{ marginTop: -16, marginBottom: 24, color: '#b42318' }}>{error}</p>}
    {projects.length === 0 ? <p style={{ color: '#777' }}>尚無專案。建立第一個專案後即可加入資料來源與 Mapping。</p> : <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 16 }}>
      {projects.map((project) => <div key={project.id} style={{ border: '1px solid #e5e7eb', borderRadius: 10, padding: 18 }}><h3 style={{ marginTop: 0 }}>{project.name}</h3><p style={{ minHeight: 20, color: '#777', fontSize: 13 }}>{project.description || '尚未設定描述'}</p><Link to={`/projects/${project.id}`}>進入專案</Link></div>)}
    </div>}
  </div>;
}
