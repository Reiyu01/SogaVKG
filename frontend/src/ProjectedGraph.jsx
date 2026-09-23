import { useCallback, useEffect, useMemo, useState } from 'react';
import { Background, Controls, MiniMap, ReactFlow, useEdgesState, useNodesState } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { apiUrl } from './config';

const colors = ['#185fa5', '#0f6e56', '#854f0b', '#993c1d', '#5f3dc4'];

function positionNodes(items) {
  const groups = [...new Set(items.map((item) => item.entity))];
  return items.map((item, index) => {
    const groupIndex = groups.indexOf(item.entity);
    const groupItems = items.filter((candidate) => candidate.entity === item.entity);
    const withinGroup = groupItems.indexOf(item);
    return {
      id: item.id,
      position: { x: 80 + groupIndex * 290 + (withinGroup % 2) * 18, y: 70 + Math.floor(withinGroup / 2) * 105 },
      data: { label: <div><strong>{item.label}</strong><div style={{ fontSize: 11, color: '#667085', marginTop: 3 }}>{item.entity}</div></div> },
      style: { width: 190, border: `2px solid ${colors[groupIndex % colors.length]}`, borderRadius: 9, padding: 10, background: '#fff', boxShadow: '0 1px 4px #00000012' },
    };
  });
}

function DetailPanel({ node, onClose }) {
  const fields = Object.entries(node.properties || {});
  return <aside style={{ position: 'absolute', top: 20, right: 20, width: 340, maxHeight: 'calc(100% - 40px)', overflowY: 'auto', zIndex: 5, background: '#fff', boxShadow: '0 6px 24px #0002', borderRadius: 12, padding: 20 }}>
    <button onClick={onClose} style={{ float: 'right', border: 0, background: '#f2f4f7', borderRadius: 6, padding: '5px 9px', cursor: 'pointer' }}>關閉</button>
    <h3 style={{ marginTop: 0, marginBottom: 4 }}>{node.label}</h3>
    <div style={{ color: '#667085', fontSize: 13, marginBottom: 16 }}>{node.entity} · 來源資料列</div>
    {fields.map(([key, value]) => <div key={key} style={{ padding: '9px 0', borderBottom: '1px solid #eaecf0' }}><div style={{ color: '#667085', fontSize: 12 }}>{key}</div><div style={{ wordBreak: 'break-word' }}>{value === null ? '—' : String(value)}</div></div>)}
  </aside>;
}

export default function ProjectedGraph({ projectId }) {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [rawNodes, setRawNodes] = useState([]);
  const [selected, setSelected] = useState(null);
  const [status, setStatus] = useState('載入 Mapping 投影圖譜…');
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    setStatus('載入 Mapping 投影圖譜…'); setError(null);
    fetch(apiUrl(`/query/graph/projection?project_id=${encodeURIComponent(projectId)}&limit=120`))
      .then(async (response) => { const body = await response.json(); if (!response.ok) throw new Error(body.detail || `HTTP ${response.status}`); return body; })
      .then((graph) => {
        setRawNodes(graph.nodes);
        setNodes(positionNodes(graph.nodes));
        setEdges(graph.edges.map((edge) => ({ ...edge, label: edge.type, style: { stroke: '#98a2b3' }, labelStyle: { fill: '#475467', fontSize: 11 } })));
        setStatus(`${graph.count.nodes} 個節點 · ${graph.count.edges} 條關係`);
      })
      .catch((loadError) => setError(loadError.message));
  }, [projectId, setEdges, setNodes]);

  useEffect(() => { load(); }, [load]);
  const selectedNode = useMemo(() => rawNodes.find((node) => node.id === selected), [rawNodes, selected]);
  const onNodeClick = useCallback((_, node) => {
    setSelected(node.id);
    setEdges((items) => items.map((edge) => ({ ...edge, animated: edge.source === node.id || edge.target === node.id, style: { stroke: edge.source === node.id || edge.target === node.id ? '#185fa5' : '#d0d5dd', strokeWidth: edge.source === node.id || edge.target === node.id ? 2 : 1 } })));
  }, [setEdges]);

  return <div style={{ position: 'relative', width: '100%', height: '100%' }}>
    <div style={{ position: 'absolute', zIndex: 4, top: 16, left: 18, padding: '9px 12px', background: '#fffffff0', border: '1px solid #eaecf0', borderRadius: 8, fontSize: 13 }}><strong>資料圖譜</strong><span style={{ color: '#667085' }}> · {status}</span><button onClick={load} style={{ marginLeft: 10, border: 0, color: '#185fa5', background: 'transparent', cursor: 'pointer' }}>重新投影</button></div>
    {error ? <div style={{ padding: 28, color: '#b42318' }}>無法顯示圖譜：{error}</div> : <ReactFlow nodes={nodes} edges={edges} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onNodeClick={onNodeClick} fitView><MiniMap /><Controls /><Background /></ReactFlow>}
    {selectedNode && <DetailPanel node={selectedNode} onClose={() => setSelected(null)} />}
  </div>;
}
