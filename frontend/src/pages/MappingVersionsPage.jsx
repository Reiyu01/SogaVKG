import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { apiUrl } from '../config';
export default function MappingVersionsPage() {
  const { projectId } = useParams(); const [versions, setVersions] = useState([]); const [selected, setSelected] = useState(null);
  useEffect(() => { fetch(apiUrl(`/builder/projects/${projectId}/mapping-versions`)).then((r) => r.json()).then((d) => setVersions(d.versions || [])); }, [projectId]);
  const open = async (version) => setSelected(await (await fetch(apiUrl(`/builder/projects/${projectId}/mapping-versions/${version}`))).json());
  const restore = async () => { if (!window.confirm(`將 v${selected.version} 複製為目前草稿？目前未發布的草稿會被取代。`)) return; await fetch(apiUrl(`/builder/projects/${projectId}/mapping-versions/${selected.version}/restore`), { method: 'POST' }); window.alert(`已回復 v${selected.version} 為草稿。`); };
  return <div style={{ padding: '32px 40px' }}><h2>Mapping 版本</h2>{versions.length === 0 ? <p style={{ color: '#777' }}>尚未發布版本。第一次成功建置時會建立 v1。</p> : <div>{versions.map((item) => <button key={item.id} onClick={() => open(item.version)} style={{ display: 'block', width: '100%', textAlign: 'left', margin: '8px 0', padding: 14, border: '1px solid #ddd', borderRadius: 8, background: '#fff' }}>v{item.version}　{item.created_at}</button>)}</div>}{selected && <><button onClick={restore} style={{ marginTop: 20, padding: '9px 14px', border: 0, borderRadius: 7, background: '#185fa5', color: '#fff' }}>回復 v{selected.version} 為草稿</button><pre style={{ marginTop: 12, padding: 16, background: '#f7f7f7', overflow: 'auto' }}>{JSON.stringify(selected.mappings, null, 2)}</pre></>}</div>;
}
