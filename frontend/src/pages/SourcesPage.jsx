import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { apiUrl } from '../config';

export default function SourcesPage() {
  const { projectId } = useParams();
  const [sources, setSources] = useState([]);
  const [editing, setEditing] = useState(null);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const load = () => fetch(apiUrl(`/builder/sources?project_id=${projectId}`)).then((r) => r.json()).then((d) => setSources(d.sources || []));
  useEffect(() => { load(); }, [projectId]);
  const remove = async (source) => { if (!window.confirm(`刪除資料來源「${source.name}」？這不會刪除原始資料庫。`)) return; await fetch(apiUrl(`/builder/sources/${source.id}`), { method: 'DELETE' }); load(); };
  const toggle = async (source) => { await fetch(apiUrl(`/builder/sources/${source.id}/active?active=${!source.active}`), { method: 'POST' }); load(); };
  const save = async (event) => {
    event.preventDefault(); setError(''); setSaving(true);
    try {
      const response = await fetch(apiUrl(`/builder/sources/${editing.id}`), { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ project_id: projectId, name: editing.name, source_type: 'sqlite', config: { path: editing.path } }) });
      if (!response.ok) { const body = await response.json().catch(() => null); throw new Error(body?.detail || '儲存失敗'); }
      setEditing(null); load();
    } catch (err) { setError(err instanceof Error ? err.message : '儲存失敗'); } finally { setSaving(false); }
  };
  return <div style={{ padding: '32px 40px' }}><h2>資料來源</h2><p style={{ color: '#667085' }}>VKG 直接從啟用的來源資料庫投影圖譜；不會複製資料到另一套圖資料庫。</p>{sources.length === 0 ? <p style={{ color: '#777' }}>尚無資料來源。請到資料模型頁新增。</p> : sources.map((source) => <div key={source.id} style={{ border: '1px solid #e5e7eb', borderRadius: 9, padding: 16, marginBottom: 10, opacity: source.active ? 1 : .55 }}><strong>{source.name}</strong><div style={{ color: '#777', fontSize: 13, margin: '6px 0' }}>{source.source_type} · {source.config.path || '已設定'} · {source.active ? '啟用中' : '已停用'}</div><button onClick={() => setEditing({ id: source.id, name: source.name, path: source.config.path || '' })} style={{ border: 0, color: '#185fa5', background: 'transparent', padding: 0, marginRight: 14 }}>編輯</button><button onClick={() => toggle(source)} style={{ border: 0, color: '#185fa5', background: 'transparent', padding: 0, marginRight: 14 }}>{source.active ? '停用' : '啟用'}</button><button onClick={() => remove(source)} style={{ border: 0, color: '#993c1d', background: 'transparent', padding: 0 }}>刪除</button></div>)}{editing && <form onSubmit={save} style={{ marginTop: 24, maxWidth: 640, padding: 18, border: '1px solid #d0d5dd', borderRadius: 9 }}><h3 style={{ marginTop: 0 }}>編輯 SQLite 資料來源</h3><label style={{ display: 'block', marginBottom: 12 }}>名稱<input required value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })} style={{ display: 'block', boxSizing: 'border-box', width: '100%', marginTop: 5, padding: 9 }} /></label><label style={{ display: 'block', marginBottom: 12 }}>資料庫路徑<input required value={editing.path} onChange={(e) => setEditing({ ...editing, path: e.target.value })} style={{ display: 'block', boxSizing: 'border-box', width: '100%', marginTop: 5, padding: 9 }} /></label>{error && <p role="alert" style={{ color: '#b42318' }}>{error}</p>}<button disabled={saving} style={{ border: 0, borderRadius: 7, padding: '9px 14px', background: '#185fa5', color: '#fff' }}>{saving ? '儲存中…' : '儲存變更'}</button><button type="button" onClick={() => { setEditing(null); setError(''); }} style={{ marginLeft: 10, border: 0, background: 'transparent' }}>取消</button></form>}</div>;
}
