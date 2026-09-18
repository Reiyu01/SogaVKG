import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { apiUrl } from '../config';
export default function ProjectOverviewPage() {
  const { projectId } = useParams(); const [data, setData] = useState(null); const [graphStats, setGraphStats] = useState(null);
  useEffect(() => { fetch(apiUrl(`/builder/projects/${projectId}/overview`)).then((r) => r.json()).then(setData); fetch(apiUrl(`/query/graph/stats?project_id=${projectId}`)).then((r) => r.ok ? r.json() : null).then(setGraphStats).catch(() => setGraphStats(null)); }, [projectId]);
  if (!data) return <div style={{ padding: 32 }}>載入中...</div>;
  const draftLabel = { no_draft: '尚未建立草稿', unpublished: '有未發布變更', published: '草稿已同步' }[data.draft_status];
  const cards = [['資料來源', data.source_count], ['Entities', data.entity_count], ['Relations', data.relation_count], ['圖譜節點', graphStats?.nodes ?? '—'], ['圖譜關係', graphStats?.edges ?? '—'], ['最新 Mapping', data.latest_mapping_version ? `v${data.latest_mapping_version.version}` : '尚未發布'], ['草稿狀態', draftLabel]];
  return <div style={{ padding: '32px 40px' }}><h2 style={{ marginTop: 0 }}>{data.project.name}</h2><p style={{ color: '#777' }}>{data.project.description || '尚未設定描述'}</p><div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', margin: '24px 0' }}>{cards.map(([label, value]) => <div key={label} style={{ minWidth: 150, padding: 18, border: '1px solid #e5e7eb', borderRadius: 10 }}><div style={{ color: '#777', fontSize: 13 }}>{label}</div><strong style={{ fontSize: 22 }}>{value}</strong></div>)}</div><h3>最近建置</h3>{data.builds.length ? data.builds.map((job) => <div key={job.id} style={{ padding: '8px 0', borderBottom: '1px solid #eee' }}>{job.status} · {job.started_at}</div>) : <p style={{ color: '#777' }}>尚無紀錄</p>}<Link to={`/projects/${projectId}/build`}>開始建置資料 →</Link></div>;
}
