import { useCallback, useEffect, useState } from 'react';
import { Background, Controls, ReactFlow, useEdgesState, useNodesState } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { apiUrl } from './config';

const color = '#185fa5';

function Icon({ type }) {
  const common = { width: 18, height: 18, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.9, strokeLinecap: 'round', strokeLinejoin: 'round' };
  if (type === 'tree') return <svg {...common}><circle cx="5" cy="5" r="2" /><circle cx="19" cy="5" r="2" /><circle cx="12" cy="19" r="2" /><path d="M5 7v4h14V7M12 11v6" /></svg>;
  if (type === 'radial') return <svg {...common}><circle cx="12" cy="12" r="3" /><circle cx="5" cy="5" r="2" /><circle cx="19" cy="5" r="2" /><circle cx="5" cy="19" r="2" /><circle cx="19" cy="19" r="2" /><path d="m10 10-4-4m8 4 4-4m-8 4-4 4m8-4 4 4" /></svg>;
  if (type === 'list') return <svg {...common}><path d="M8 6h12M8 12h12M8 18h12" /><circle cx="4" cy="6" r=".7" fill="currentColor" /><circle cx="4" cy="12" r=".7" fill="currentColor" /><circle cx="4" cy="18" r=".7" fill="currentColor" /></svg>;
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

function highlightMatch(value, keyword) {
  const text = value == null ? '—' : String(value);
  if (!keyword) return text;
  const escaped = keyword.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const parts = text.split(new RegExp(`(${escaped})`, 'ig'));
  return parts.map((part, index) => part.toLowerCase() === keyword.toLowerCase()
    ? <mark key={index} style={{ background: '#fef08a', padding: 0 }}>{part}</mark>
    : part);
}

function InstancePanel({ node, onClose }) {
  if (!node) return null;
  return <><div onClick={onClose} style={{ position: 'fixed', inset: 0, zIndex: 10, background: 'rgba(0,0,0,.12)' }} /><aside style={{ position: 'fixed', top: 0, right: 0, zIndex: 11, width: 380, height: '100vh', overflowY: 'auto', padding: 22, boxSizing: 'border-box', background: '#fff', boxShadow: '-4px 0 18px rgba(0,0,0,.16)' }}><button onClick={onClose} style={{ float: 'right', border: 0, borderRadius: 6, padding: '5px 10px', cursor: 'pointer', background: '#f2f4f7' }}>關閉</button><h3 style={{ margin: '0 50px 5px 0' }}>{node.data.label}</h3><div style={{ color: '#667085', fontSize: 13, marginBottom: 18 }}>{node.data.entity}</div>{Object.entries(node.data.properties || {}).map(([key, value]) => <div key={key} style={{ padding: '10px 0', borderBottom: '1px solid #eaecf0' }}><div style={{ color: '#667085', fontSize: 12, marginBottom: 3 }}>{key}</div><div style={{ overflowWrap: 'anywhere' }}>{value === null || value === '' ? '—' : String(value)}</div></div>)}</aside></>;
}

export default function LazyProjectedGraph({ projectId }) {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [status, setStatus] = useState('載入最上層語義模型…');
  const [error, setError] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [activeLayout, setActiveLayout] = useState('network');
  const [flow, setFlow] = useState(null);
  const [selectedInstance, setSelectedInstance] = useState(null);
  const [tableOpen, setTableOpen] = useState(false);
  const [listMode, setListMode] = useState(false);
  const [tableEntity, setTableEntity] = useState(null);
  const [tableData, setTableData] = useState({ data: [] });
  const [keyword, setKeyword] = useState('');
  const [tableHeight, setTableHeight] = useState(255);
  const changeLayout = (kind) => { setActiveLayout(kind); setListMode(false); setTableOpen(false); setNodes((current) => layout(kind, current, edges, selectedId)); };
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
  useEffect(() => {
    if (!tableOpen || !tableEntity) return;
    const params = new URLSearchParams({ project_id: projectId, entity: tableEntity, limit: '50' });
    if (keyword) params.set('keyword', keyword);
    fetch(apiUrl(`/query/graph/projection/records?${params}`)).then(async (r) => { const body = await r.json(); if (!r.ok) throw new Error(body.detail || `HTTP ${r.status}`); return body; }).then(setTableData).catch((e) => setError(e.message));
  }, [keyword, projectId, tableEntity, tableOpen]);

  const click = useCallback((_, node) => {
    if (listMode) {
      setTableEntity(node.data.entity);
      setKeyword('');
      setStatus(`列表視圖：顯示 ${node.data.entity} 的 Mapping 實例資料。`);
      setTableOpen(true);
      return;
    }
    setSelectedId(node.id);
    const entity = node.data.entity;
    if (node.data.kind === 'entity') {
      setTableEntity(entity);
      fetch(apiUrl(`/query/graph/projection/entity?project_id=${encodeURIComponent(projectId)}&entity=${encodeURIComponent(entity)}`)).then((r) => r.json()).then((graph) => { addGraph(graph, node.id); setStatus(`已展開 ${entity} 的前 ${graph.nodes.length} 筆資料。`); }).catch((e) => setError(e.message));
    } else {
      setSelectedInstance(node);
      const sourceId = node.id.slice(node.id.indexOf(':') + 1);
      fetch(apiUrl(`/query/graph/projection/neighbors?project_id=${encodeURIComponent(projectId)}&entity=${encodeURIComponent(entity)}&source_id=${encodeURIComponent(sourceId)}`)).then((r) => r.json()).then((graph) => { addGraph(graph); setStatus(`已展開 ${node.data.entity} 的 ${graph.edges.length} 條關係。`); }).catch((e) => setError(e.message));
    }
  }, [addGraph, projectId, listMode]);
  const selectRow = (row) => {
    const nodeId = `${tableEntity}:${row[tableData.primary_key]}`;
    setNodes((items) => items.map((node) => ({ ...node, style: { ...node.style, boxShadow: node.id === nodeId ? '0 0 0 4px #fdb022, 0 1px 4px #0002' : node.style.boxShadow } })));
    setSelectedInstance(nodes.find((node) => node.id === nodeId) || null);
  };
  const toggleTable = () => {
    if (!listMode) {
      setNodes((items) => items.filter((node) => node.data.kind === 'entity'));
      setEdges([]);
      setSelectedInstance(null);
      setStatus(tableEntity ? `列表視圖：${tableEntity} 的 Mapping 實例資料。` : '列表視圖：請點選一個 Entity 節點以顯示實例資料。');
      setListMode(true);
    }
    setTableOpen(true);
  };
  const startResize = (event) => {
    event.preventDefault();
    const startY = event.clientY; const startHeight = tableHeight;
    const move = (moveEvent) => setTableHeight(Math.max(170, Math.min(window.innerHeight * 0.72, startHeight + startY - moveEvent.clientY)));
    const stop = () => { window.removeEventListener('mousemove', move); window.removeEventListener('mouseup', stop); };
    window.addEventListener('mousemove', move); window.addEventListener('mouseup', stop);
  };
  const iconButton = (kind, title) => <button key={kind} title={title} onClick={() => changeLayout(kind)} style={{ width: 34, height: 34, display: 'grid', placeItems: 'center', border: 0, borderRadius: 7, cursor: 'pointer', color: activeLayout === kind ? '#fff' : '#344054', background: activeLayout === kind ? '#185fa5' : '#fff' }}><Icon type={kind} /></button>;
  const columns = tableData.data?.length ? Object.keys(tableData.data[0]) : [];
  return <div style={{ width: '100%', height: '100%', position: 'relative' }}><div style={{ position: 'absolute', zIndex: 3, top: 16, left: 16, background: '#fffffff0', padding: 10, borderRadius: 8, fontSize: 13 }}><b>資料圖譜</b> · {status}</div><div style={{ position: 'absolute', zIndex: 3, top: 16, right: 16, display: 'flex', gap: 4, padding: 4, borderRadius: 9, background: '#f8fafc', boxShadow: '0 2px 8px #0002' }}>{iconButton('network', '網路圖')}{iconButton('tree', '樹狀圖')}{iconButton('radial', '放射狀圖')}<button title="實例列表" onClick={toggleTable} style={{ width: 34, height: 34, display: 'grid', placeItems: 'center', border: 0, borderRadius: 7, cursor: 'pointer', color: listMode ? '#fff' : '#344054', background: listMode ? '#185fa5' : '#fff' }}><Icon type="list" /></button></div>{error ? <div style={{ padding: 28, color: '#b42318' }}>{error}</div> : <ReactFlow nodes={nodes} edges={edges} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onNodeClick={click} onInit={setFlow} fitView><Controls /><Background /></ReactFlow>}{selectedInstance && <InstancePanel node={selectedInstance} onClose={() => setSelectedInstance(null)} />}{tableOpen && <section style={{ position: 'absolute', zIndex: 4, bottom: 0, left: 0, right: 0, height: tableHeight, padding: '14px 20px', boxSizing: 'border-box', background: '#fff', borderTop: '1px solid #d0d5dd', boxShadow: '0 -3px 12px #0001' }}><div onMouseDown={startResize} style={{ position: 'absolute', top: -5, left: 0, right: 0, height: 10, cursor: 'ns-resize' }} /><div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 10 }}><b>{tableEntity ? `${tableEntity} 實例列表` : '實例列表'}</b><input value={keyword} onChange={(e) => setKeyword(e.target.value)} placeholder="搜尋資料" disabled={!tableEntity} style={{ padding: '6px 9px', border: '1px solid #d0d5dd', borderRadius: 6 }} /><span style={{ color: '#667085', fontSize: 13 }}>{tableData.count ?? 0} 筆</span><button onClick={() => setTableOpen(false)} style={{ marginLeft: 'auto', border: 0, background: '#f2f4f7', borderRadius: 6, padding: '5px 10px', cursor: 'pointer' }}>關閉</button></div>{!tableEntity ? <div style={{ color: '#667085', padding: 20 }}>請點選上方任一 Entity 節點。</div> : <div style={{ overflow: 'auto', height: `calc(100% - 45px)` }}><table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}><thead><tr>{columns.map((column) => <th key={column} style={{ textAlign: 'left', padding: 7, background: '#f9fafb', borderBottom: '1px solid #eaecf0' }}>{column}</th>)}</tr></thead><tbody>{tableData.data?.map((row, index) => <tr key={index} onClick={() => selectRow(row)} style={{ cursor: 'pointer', background: '#fff' }}>{columns.map((column) => <td key={column} style={{ padding: 7, borderBottom: '1px solid #f2f4f7', whiteSpace: 'nowrap' }}>{highlightMatch(row[column], keyword)}</td>)}</tr>)}</tbody></table></div>}</section>}</div>;
}
