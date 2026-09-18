import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { apiUrl } from '../config';
export default function SourcesPage() {
  const { projectId } = useParams(); const [sources, setSources] = useState([]);
  const load = () => fetch(apiUrl(`/builder/sources?project_id=${projectId}`)).then((r) => r.json()).then((d) => setSources(d.sources || []));
  useEffect(() => { load(); }, [projectId]);
  const remove = async (source) => { if (!window.confirm(`刪除資料來源「${source.name}」？這不會刪除原始資料庫。`)) return; await fetch(apiUrl(`/builder/sources/${source.id}`), { method: 'DELETE' }); load(); };
  const toggle = async (source) => { await fetch(apiUrl(`/builder/sources/${source.id}/active?active=${!source.active}`), { method: 'POST' }); load(); };
  return <div style={{ padding: '32px 40px' }}><h2>資料來源</h2>{sources.length === 0 ? <p style={{ color: '#777' }}>尚無資料來源。請到建置資料頁新增。</p> : sources.map((source) => <div key={source.id} style={{ border: '1px solid #e5e7eb', borderRadius: 9, padding: 16, marginBottom: 10, opacity: source.active ? 1 : .55 }}><strong>{source.name}</strong><div style={{ color: '#777', fontSize: 13, margin: '6px 0' }}>{source.source_type} · {source.config.path || '已設定'} · {source.active ? '啟用中' : '已停用'}</div><button onClick={() => toggle(source)} style={{ border: 0, color: '#185fa5', background: 'transparent', padding: 0, marginRight: 14 }}>{source.active ? '停用' : '啟用'}</button><button onClick={() => remove(source)} style={{ border: 0, color: '#993c1d', background: 'transparent', padding: 0 }}>刪除</button></div>)}</div>;
}
