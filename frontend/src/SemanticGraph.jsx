import { useEffect, useState, useCallback, useMemo } from 'react';
import {
  ReactFlow,
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';


const API_BASE = 'http://163.18.26.230:8000';

const GRAPH_API_URL = `${API_BASE}/query/graph`;
const DATA_GRAPH_API_URL = `${API_BASE}/query/graph/data`;
const QUERY_API_URL = `${API_BASE}/query/`;


// ======================================================
// 佈局：圓形排版
// ======================================================

function layoutNodes(entities, edges) {
  const radius = 250;
  const centerX = 400;
  const centerY = 300;

  // 被其他 entity 指向的，視為「被關聯方」，上不同顏色
  const targetIds = new Set(edges.map((e) => e.target));

  return entities.map((entity, index) => {
    const angle = (index / entities.length) * 2 * Math.PI;
    const isTarget = targetIds.has(entity.id);

    return {
      id: entity.id,
      position: {
        x: centerX + radius * Math.cos(angle),
        y: centerY + radius * Math.sin(angle),
      },
      data: {
        label: (
          <div style={{ textAlign: 'left' }}>
            <div style={{ fontWeight: 600, fontSize: '13px' }}>{entity.label}</div>
            <div style={{ fontSize: '11px', color: '#888', marginTop: '2px' }}>
              {entity.properties.join(', ')}
            </div>
          </div>
        ),
      },
      style: {
        border: isTarget ? '1.5px solid #0f6e56' : '1.5px solid #185fa5',
        borderRadius: 10,
        padding: 10,
        background: isTarget ? '#e1f5ee' : '#e6f1fb',
        width: 210,
        cursor: 'pointer',
        boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
      },
    };
  });
}

// ======================================================
// Spinner
// ======================================================

function Spinner() {
  return (
    <div
      style={{
        width: 20,
        height: 20,
        border: '2px solid #ddd',
        borderTopColor: '#185fa5',
        borderRadius: '50%',
        animation: 'spin 0.6s linear infinite',
      }}
    />
  );
}

// ======================================================
// 側邊面板
// ======================================================

function DataPanel({ entityId, onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [keyword, setKeyword] = useState('');
  const [sortCol, setSortCol] = useState(null);
  const [sortDir, setSortDir] = useState('asc');

  const runQuery = useCallback(
    (searchKeyword) => {
      setLoading(true);
      setError(null);

      const body = {
        entity: entityId,
        limit: 50,
      };

      // 有輸入關鍵字時，對所有欄位做簡單 LIKE 過濾（用第一個欄位示範，
      // 實務上可依 searchable 欄位清單動態組出多個 filter）
      if (searchKeyword) {
        body.filters = [{ field: 'name', operator: 'LIKE', value: searchKeyword }];
      }

      fetch(QUERY_API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
        .then((res) => {
          if (!res.ok) throw new Error(`HTTP ${res.status}`);
          return res.json();
        })
        .then((result) => {
          setData(result);
          setLoading(false);
        })
        .catch((err) => {
          setError(err.message);
          setLoading(false);
        });
    },
    [entityId]
  );

  useEffect(() => {
    runQuery('');
  }, [runQuery]);

  // ESC 關閉
  useEffect(() => {
    const handleKey = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [onClose]);

  const columns = useMemo(
    () => (data && data.data.length > 0 ? Object.keys(data.data[0]) : []),
    [data]
  );

  const sortedRows = useMemo(() => {
    if (!data) return [];
    if (!sortCol) return data.data;

    return [...data.data].sort((a, b) => {
      const av = a[sortCol];
      const bv = b[sortCol];
      if (av === null) return 1;
      if (bv === null) return -1;
      if (av < bv) return sortDir === 'asc' ? -1 : 1;
      if (av > bv) return sortDir === 'asc' ? 1 : -1;
      return 0;
    });
  }, [data, sortCol, sortDir]);

  const toggleSort = (col) => {
    if (sortCol === col) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortCol(col);
      setSortDir('asc');
    }
  };

  return (
    <>
      {/* 背景遮罩，點擊關閉 */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(0,0,0,0.15)',
          zIndex: 999,
        }}
      />

      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          position: 'fixed',
          top: 0,
          right: 0,
          width: '460px',
          height: '100vh',
          background: 'white',
          boxShadow: '-4px 0 16px rgba(0,0,0,0.12)',
          padding: '20px',
          overflowY: 'auto',
          zIndex: 1000,
        }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginBottom: '12px',
          }}
        >
          <h3 style={{ margin: 0, fontSize: '18px' }}>{entityId}</h3>
          <button
            onClick={onClose}
            style={{
              cursor: 'pointer',
              border: 'none',
              background: '#f1efe8',
              borderRadius: 6,
              padding: '4px 10px',
              fontSize: '13px',
            }}
          >
            關閉 (Esc)
          </button>
        </div>

        <input
          type="text"
          placeholder="輸入關鍵字搜尋 name 欄位..."
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') runQuery(keyword);
          }}
          style={{
            width: '100%',
            padding: '8px 10px',
            marginBottom: '12px',
            border: '1px solid #ddd',
            borderRadius: 6,
            fontSize: '13px',
            boxSizing: 'border-box',
          }}
        />

        {loading && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '20px 0' }}>
            <Spinner />
            <span style={{ color: '#888', fontSize: '13px' }}>載入中...</span>
          </div>
        )}

        {error && (
          <div
            style={{
              color: '#993c1d',
              background: '#faece7',
              padding: '10px',
              borderRadius: 6,
              fontSize: '13px',
            }}
          >
            錯誤：{error}
          </div>
        )}

        {data && !loading && (
          <>
            <div style={{ marginBottom: '10px', color: '#888', fontSize: '13px' }}>
              共 {data.count} 筆
            </div>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
                <thead>
                  <tr>
                    {columns.map((col) => (
                      <th
                        key={col}
                        onClick={() => toggleSort(col)}
                        style={{
                          textAlign: 'left',
                          borderBottom: '1.5px solid #ddd',
                          padding: '6px 8px',
                          background: '#fafafa',
                          cursor: 'pointer',
                          whiteSpace: 'nowrap',
                          userSelect: 'none',
                        }}
                      >
                        {col}
                        {sortCol === col && (sortDir === 'asc' ? ' ▲' : ' ▼')}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {sortedRows.map((row, i) => (
                    <tr key={i}>
                      {columns.map((col) => (
                        <td
                          key={col}
                          style={{
                            borderBottom: '1px solid #eee',
                            padding: '6px 8px',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {row[col] === null ? (
                            <span style={{ color: '#ccc' }}>—</span>
                          ) : (
                            String(row[col])
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </>
  );
}

// ======================================================
// 主元件
// ======================================================

export default function SemanticGraph() {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedEntity, setSelectedEntity] = useState(null);

  useEffect(() => {
    fetch(GRAPH_API_URL)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data) => {
        const graphNodes = layoutNodes(data.nodes, data.edges);

        const graphEdges = data.edges.map((edge, index) => ({
          id: `e-${index}`,
          source: edge.source,
          target: edge.target,
          label: edge.label,
          animated: false,
          style: { stroke: '#ccc' },
        }));

        setNodes(graphNodes);
        setEdges(graphEdges);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, [setNodes, setEdges]);

  const onNodeClick = useCallback(
    (event, node) => {
      setSelectedEntity(node.id);

      // 高亮跟這個節點相關的連線
      setEdges((eds) =>
        eds.map((e) => {
          const related = e.source === node.id || e.target === node.id;
          return {
            ...e,
            animated: related,
            style: { stroke: related ? '#185fa5' : '#ccc', strokeWidth: related ? 2 : 1 },
          };
        })
      );
    },
    [setEdges]
  );

  if (loading)
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: 24 }}>
        <Spinner />
        <span>載入中...</span>
      </div>
    );

  if (error) return <div style={{ padding: 24, color: 'red' }}>錯誤：{error}</div>;

  return (
    <div style={{ width: '100%', height: '100%' }}>
      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>

      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        fitView
      >
        <MiniMap />
        <Controls />
        <Background />
      </ReactFlow>

      {selectedEntity && (
        <DataPanel entityId={selectedEntity} onClose={() => setSelectedEntity(null)} />
      )}
    </div>
  );
}




// import { useEffect, useState, useCallback } from 'react';
// import {
//   ReactFlow,
//   MiniMap,
//   Controls,
//   Background,
//   useNodesState,
//   useEdgesState,
// } from '@xyflow/react';
// import '@xyflow/react/dist/style.css';

// const GRAPH_API_URL = 'http://127.0.0.1:8000/query/graph';
// const QUERY_API_URL = 'http://127.0.0.1:8000/query/';

// // 簡單的圓形排版：把 entity 節點排成一圈
// function layoutNodes(entities) {
//   const radius = 250;
//   const centerX = 400;
//   const centerY = 300;

//   return entities.map((entity, index) => {
//     const angle = (index / entities.length) * 2 * Math.PI;
//     return {
//       id: entity.id,
//       position: {
//         x: centerX + radius * Math.cos(angle),
//         y: centerY + radius * Math.sin(angle),
//       },
//       data: {
//         label: (
//           <div style={{ textAlign: 'left' }}>
//             <div style={{ fontWeight: 'bold' }}>{entity.label}</div>
//             <div style={{ fontSize: '11px', color: '#666' }}>
//               {entity.properties.join(', ')}
//             </div>
//           </div>
//         ),
//       },
//       style: {
//         border: '1px solid #999',
//         borderRadius: 8,
//         padding: 10,
//         background: 'white',
//         width: 200,
//         cursor: 'pointer',
//       },
//     };
//   });
// }

// // ======================================================
// // 側邊面板：顯示某個 entity 的真實資料
// // ======================================================

// function DataPanel({ entityId, onClose }) {
//   const [data, setData] = useState(null);
//   const [loading, setLoading] = useState(true);
//   const [error, setError] = useState(null);

//   useEffect(() => {
//     setLoading(true);
//     setError(null);

//     fetch(QUERY_API_URL, {
//       method: 'POST',
//       headers: { 'Content-Type': 'application/json' },
//       body: JSON.stringify({
//         entity: entityId,
//         limit: 20,
//       }),
//     })
//       .then((res) => {
//         if (!res.ok) throw new Error(`HTTP ${res.status}`);
//         return res.json();
//       })
//       .then((result) => {
//         setData(result);
//         setLoading(false);
//       })
//       .catch((err) => {
//         setError(err.message);
//         setLoading(false);
//       });
//   }, [entityId]);

//   const columns =
//     data && data.data.length > 0 ? Object.keys(data.data[0]) : [];

//   return (
//     <div
//       style={{
//         position: 'fixed',
//         top: 0,
//         right: 0,
//         width: '420px',
//         height: '100vh',
//         background: 'white',
//         borderLeft: '1px solid #ddd',
//         boxShadow: '-2px 0 8px rgba(0,0,0,0.1)',
//         padding: '20px',
//         overflowY: 'auto',
//         zIndex: 1000,
//       }}
//     >
//       <div
//         style={{
//           display: 'flex',
//           justifyContent: 'space-between',
//           alignItems: 'center',
//           marginBottom: '16px',
//         }}
//       >
//         <h3 style={{ margin: 0 }}>{entityId}</h3>
//         <button onClick={onClose} style={{ cursor: 'pointer' }}>
//           關閉
//         </button>
//       </div>

//       {loading && <div>載入中...</div>}
//       {error && <div style={{ color: 'red' }}>錯誤：{error}</div>}

//       {data && (
//         <>
//           <div style={{ marginBottom: '12px', color: '#666', fontSize: '13px' }}>
//             共 {data.count} 筆（顯示前 20 筆）
//           </div>
//           <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
//             <thead>
//               <tr>
//                 {columns.map((col) => (
//                   <th
//                     key={col}
//                     style={{
//                       textAlign: 'left',
//                       borderBottom: '1px solid #ddd',
//                       padding: '6px 4px',
//                       background: '#fafafa',
//                     }}
//                   >
//                     {col}
//                   </th>
//                 ))}
//               </tr>
//             </thead>
//             <tbody>
//               {data.data.map((row, i) => (
//                 <tr key={i}>
//                   {columns.map((col) => (
//                     <td
//                       key={col}
//                       style={{
//                         borderBottom: '1px solid #eee',
//                         padding: '6px 4px',
//                       }}
//                     >
//                       {row[col] === null ? (
//                         <span style={{ color: '#ccc' }}>—</span>
//                       ) : (
//                         String(row[col])
//                       )}
//                     </td>
//                   ))}
//                 </tr>
//               ))}
//             </tbody>
//           </table>
//         </>
//       )}
//     </div>
//   );
// }

// // ======================================================
// // 主元件
// // ======================================================

// export default function SemanticGraph() {
//   const [nodes, setNodes, onNodesChange] = useNodesState([]);
//   const [edges, setEdges, onEdgesChange] = useEdgesState([]);
//   const [loading, setLoading] = useState(true);
//   const [error, setError] = useState(null);
//   const [selectedEntity, setSelectedEntity] = useState(null);

//   useEffect(() => {
//     fetch(GRAPH_API_URL)
//       .then((res) => {
//         if (!res.ok) throw new Error(`HTTP ${res.status}`);
//         return res.json();
//       })
//       .then((data) => {
//         const graphNodes = layoutNodes(data.nodes);

//         const graphEdges = data.edges.map((edge, index) => ({
//           id: `e-${index}`,
//           source: edge.source,
//           target: edge.target,
//           label: edge.label,
//           animated: false,
//         }));

//         setNodes(graphNodes);
//         setEdges(graphEdges);
//         setLoading(false);
//       })
//       .catch((err) => {
//         setError(err.message);
//         setLoading(false);
//       });
//   }, [setNodes, setEdges]);

//   const onNodeClick = useCallback((event, node) => {
//     setSelectedEntity(node.id);
//   }, []);

//   if (loading) return <div style={{ padding: 24 }}>載入中...</div>;
//   if (error) return <div style={{ padding: 24, color: 'red' }}>錯誤：{error}</div>;

//   return (
//     <div style={{ width: '100vw', height: '100vh' }}>
//       <ReactFlow
//         nodes={nodes}
//         edges={edges}
//         onNodesChange={onNodesChange}
//         onEdgesChange={onEdgesChange}
//         onNodeClick={onNodeClick}
//         fitView
//       >
//         <MiniMap />
//         <Controls />
//         <Background />
//       </ReactFlow>

//       {selectedEntity && (
//         <DataPanel
//           entityId={selectedEntity}
//           onClose={() => setSelectedEntity(null)}
//         />
//       )}
//     </div>
//   );
// }

// import { useEffect, useState } from 'react';
// import {
//   ReactFlow,
//   MiniMap,
//   Controls,
//   Background,
//   useNodesState,
//   useEdgesState,
// } from '@xyflow/react';
// import '@xyflow/react/dist/style.css';

// const API_URL = 'http://127.0.0.1:8000/query/graph';

// // 簡單的圓形排版：把 entity 節點排成一圈
// function layoutNodes(entities) {
//   const radius = 250;
//   const centerX = 400;
//   const centerY = 300;

//   return entities.map((entity, index) => {
//     const angle = (index / entities.length) * 2 * Math.PI;
//     return {
//       id: entity.id,
//       position: {
//         x: centerX + radius * Math.cos(angle),
//         y: centerY + radius * Math.sin(angle),
//       },
//       data: {
//         label: (
//           <div style={{ textAlign: 'left' }}>
//             <div style={{ fontWeight: 'bold' }}>{entity.label}</div>
//             <div style={{ fontSize: '11px', color: '#666' }}>
//               {entity.properties.join(', ')}
//             </div>
//           </div>
//         ),
//       },
//       style: {
//         border: '1px solid #999',
//         borderRadius: 8,
//         padding: 10,
//         background: 'white',
//         width: 200,
//       },
//     };
//   });
// }

// export default function SemanticGraph() {
//   const [nodes, setNodes, onNodesChange] = useNodesState([]);
//   const [edges, setEdges, onEdgesChange] = useEdgesState([]);
//   const [loading, setLoading] = useState(true);
//   const [error, setError] = useState(null);

//   useEffect(() => {
//     fetch(API_URL)
//       .then((res) => {
//         if (!res.ok) throw new Error(`HTTP ${res.status}`);
//         return res.json();
//       })
//       .then((data) => {
//         const graphNodes = layoutNodes(data.nodes);

//         const graphEdges = data.edges.map((edge, index) => ({
//           id: `e-${index}`,
//           source: edge.source,
//           target: edge.target,
//           label: edge.label,
//           animated: false,
//         }));

//         setNodes(graphNodes);
//         setEdges(graphEdges);
//         setLoading(false);
//       })
//       .catch((err) => {
//         setError(err.message);
//         setLoading(false);
//       });
//   }, [setNodes, setEdges]);

//   if (loading) return <div style={{ padding: 24 }}>載入中...</div>;
//   if (error) return <div style={{ padding: 24, color: 'red' }}>錯誤：{error}</div>;

//   return (
//     <div style={{ width: '100vw', height: '100vh' }}>
//       <ReactFlow
//         nodes={nodes}
//         edges={edges}
//         onNodesChange={onNodesChange}
//         onEdgesChange={onEdgesChange}
//         fitView
//       >
//         <MiniMap />
//         <Controls />
//         <Background />
//       </ReactFlow>
//     </div>
//   );
// }