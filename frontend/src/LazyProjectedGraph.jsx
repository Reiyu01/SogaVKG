import { useCallback, useEffect, useState } from 'react';
import { Background, Controls, ReactFlow, useEdgesState, useNodesState } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { apiUrl } from './config';

const color = '#185fa5';

function Icon({ type }) {
  const common = { width: 18, height: 18, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.9, strokeLinecap: 'round', strokeLinejoin: 'round' };
  if (type === 'tree') return <svg {...common}><circle cx="5" cy="5" r="2" /><circle cx="19" cy="5" r="2" /><circle cx="12" cy="19" r="2" /><path d="M5 7v4h14V7M12 11v6" /></svg>;
  if (type === 'radial') return <svg {...common}><circle cx="12" cy="12" r="3" /><circle cx="5" cy="5" r="2" /><circle cx="19" cy="5" r="2" /><circle cx="5" cy="19" r="2" /><circle cx="19" cy="19" r="2" /><path d="m10 10-4-4m8 4 4-4m-8 4-4 4m8-4 4 4" /></svg>;
  return <svg {...common}><circle cx="5" cy="12" r="2" /><circle cx="12" cy="5" r="2" /><circle cx="19" cy="12" r="2" /><circle cx="12" cy="19" r="2" /><path d="m7 12 3-5m4-1 3 5m0 2-3 5m-4 0-3-5" /></svg>;
}

function layout(kind, nodes, edges, rootId) {
  if (kind === 'network') return nodes.map((node, index) => ({ ...node, position: { x: 80 + (index % 4) * 240, y: 90 + Math.floor(index / 4) * 130 } }));
  const root = rootId || nodes[0]?.id;
  const levels = new Map([[root, 0]]); const queue = [root];
  while (queue.length) { const current = queue.shift(); for (const edge of edges.filter((item) => item.source === current)) if (!levels.has(edge.target)) { levels.set(edge.target, levels.get(current) + 1); queue.push(edge.target); } }
  const grouped = new Map(); nodes.forEach((node) => { const level = levels.get(node.id) ?? 0; grouped.set(level, [...(grouped.get(level) || []), node]); });
  return nodes.map((node) => { const level = levels.get(node.id) ?? 0; const row = grouped.get(level); const index = row.indexOf(node); if (kind === 'radial') { const angle = row.length === 1 ? -Math.PI / 2 : (index / row.length) * Math.PI * 2; const radius = level * 260; return { ...node, position: { x: 520 + Math.cos(angle) * radius, y: 360 + Math.sin(angle) * radius } }; } return { ...node, position: { x: 80 + level * 280, y: 80 + index * 120 } }; });
}

export default function LazyProjectedGraph({ projectId }) {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [status, setStatus] = useState('載入最上層語義模型…');
  const [error, setError] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [activeLayout, setActiveLayout] = useState('network');
  const [flow, setFlow] = useState(null);
  const changeLayout = (kind) => { setActiveLayout(kind); setNodes((current) => layout(kind, current, edges, selectedId)); };
  useEffect(() => {
    if (!flow || nodes.length === 0) return;
    const frame = requestAnimationFrame(() => flow.fitView({ padding: 0.18, duration: 260, maxZoom: 1.1 }));
    return () => cancelAnimationFrame(frame);
  }, [edges.length, flow, nodes.length]);
  const addGraph = useCallback((graph, parentId = null, relation = 'records') => {
    setNodes((old) => {
      const known = new Set(old.map((node) => node.id));
      const additions = graph.nodes.filter((node) => !known.has(node.id)).map((node, index) => ({
        id: node.id, position: { x: parentId ? 260 + (old.length % 4) * 230 : 100, y: parentId ? 100 + (old.length + index) * 90 : 80 },
        data: { ...node, kind: 'record', label: <div><strong>{node.label}</strong><div style={{ fontSize: 11, color: '#667085' }}>{node.entity}</div></div> },
        style: { width: 190, border: `2px solid ${color}`, borderRadius: 9, padding: 10, background: '#fff' },
      }));
      return [...old, ...additions];
    });
    setEdges((old) => {
      const explicit = graph.edges.map((edge) => ({ ...edge, label: edge.type, style: { stroke: '#98a2b3' } }));
      const recordEdges = parentId ? graph.nodes.map((node) => ({ id: `${parentId}:records:${node.id}`, source: parentId, target: node.id, label: relation, style: { stroke: '#d0d5dd' } })) : [];
      const known = new Set(old.map((edge) => edge.id));
      return [...old, ...[...explicit, ...recordEdges].filter((edge) => !known.has(edge.id))];
    });
  }, [setEdges, setNodes]);

  useEffect(() => {
    fetch(apiUrl(`/query/graph?project_id=${encodeURIComponent(projectId)}`)).then((r) => r.json()).then((graph) => {
      setNodes(graph.nodes.map((entity, index) => ({ id: `entity:${entity.id}`, position: { x: 80 + (index % 4) * 240, y: 90 + Math.floor(index / 4) * 150 }, data: { kind: 'entity', entity: entity.id, label: <div><strong>{entity.label}</strong><div style={{ fontSize: 11, color: '#667085' }}>{entity.id}</div></div> }, style: { width: 190, border: '2px solid #0f6e56', borderRadius: 10, padding: 12, background: '#ecfdf3' } })));
      setStatus('選擇一個 Entity，才會載入資料節點。');
    }).catch((e) => setError(e.message));
  }, [projectId, setNodes]);

  const click = useCallback((_, node) => {
    setSelectedId(node.id);
    const entity = node.data.entity;
    if (node.data.kind === 'entity') {
      fetch(apiUrl(`/query/graph/projection/entity?project_id=${encodeURIComponent(projectId)}&entity=${encodeURIComponent(entity)}`)).then((r) => r.json()).then((graph) => { addGraph(graph, node.id); setStatus(`已展開 ${entity} 的前 ${graph.nodes.length} 筆資料。`); }).catch((e) => setError(e.message));
    } else {
      const sourceId = node.id.slice(node.id.indexOf(':') + 1);
      fetch(apiUrl(`/query/graph/projection/neighbors?project_id=${encodeURIComponent(projectId)}&entity=${encodeURIComponent(entity)}&source_id=${encodeURIComponent(sourceId)}`)).then((r) => r.json()).then((graph) => { addGraph(graph); setStatus(`已展開 ${node.data.entity} 的 ${graph.edges.length} 條關係。`); }).catch((e) => setError(e.message));
    }
  }, [addGraph, projectId]);
  const iconButton = (kind, title) => <button key={kind} title={title} onClick={() => changeLayout(kind)} style={{ width: 34, height: 34, display: 'grid', placeItems: 'center', border: 0, borderRadius: 7, cursor: 'pointer', color: activeLayout === kind ? '#fff' : '#344054', background: activeLayout === kind ? '#185fa5' : '#fff' }}><Icon type={kind} /></button>;
  return <div style={{ width: '100%', height: '100%', position: 'relative' }}><div style={{ position: 'absolute', zIndex: 3, top: 16, left: 16, background: '#fffffff0', padding: 10, borderRadius: 8, fontSize: 13 }}><b>資料圖譜</b> · {status}</div><div style={{ position: 'absolute', zIndex: 3, top: 16, right: 16, display: 'flex', gap: 4, padding: 4, borderRadius: 9, background: '#f8fafc', boxShadow: '0 2px 8px #0002' }}>{iconButton('network', '網路圖')}{iconButton('tree', '樹狀圖')}{iconButton('radial', '放射狀圖')}</div>{error ? <div style={{ padding: 28, color: '#b42318' }}>{error}</div> : <ReactFlow nodes={nodes} edges={edges} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onNodeClick={click} onInit={setFlow} fitView><Controls /><Background /></ReactFlow>}</div>;
}
