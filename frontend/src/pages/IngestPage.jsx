import { useState, useRef, useEffect } from 'react';

const INGEST_START_URL = 'http://127.0.0.1:8000/query/ingest';
const INGEST_STATUS_URL = (jobId) => `http://127.0.0.1:8000/query/ingest/${jobId}`;

export default function IngestPage() {
  const [status, setStatus] = useState('idle'); // idle | running | done | failed
  const [logs, setLogs] = useState([]);
  const [error, setError] = useState(null);
  const pollRef = useRef(null);
  const logEndRef = useRef(null);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  useEffect(() => {
    return () => clearInterval(pollRef.current);
  }, []);

  const startIngestion = async () => {
    setStatus('running');
    setLogs([]);
    setError(null);

    try {
      const res = await fetch(INGEST_START_URL, { method: 'POST' });
      const { job_id } = await res.json();

      pollRef.current = setInterval(async () => {
        const statusRes = await fetch(INGEST_STATUS_URL(job_id));
        const data = await statusRes.json();

        setLogs(data.logs);

        if (data.status === 'done') {
          setStatus('done');
          clearInterval(pollRef.current);
        } else if (data.status === 'failed') {
          setStatus('failed');
          setError(data.error);
          clearInterval(pollRef.current);
        }
      }, 1000);
    } catch (err) {
      setStatus('failed');
      setError(err.message);
    }
  };

  return (
    <div style={{ flex: 1, height: '100%', padding: '32px 40px', boxSizing: 'border-box', overflowY: 'auto' }}>
      <h2 style={{ marginTop: 0 }}>資料建置</h2>
      <p style={{ color: '#888', fontSize: '14px', marginBottom: '24px' }}>
        將來源資料（SQLite / Google Sheets）依語義映射建置進 Neo4j 知識圖譜。
      </p>

      <button
        onClick={startIngestion}
        disabled={status === 'running'}
        style={{
          padding: '10px 24px',
          border: 'none',
          borderRadius: 8,
          background: status === 'running' ? '#ccc' : '#185fa5',
          color: 'white',
          fontSize: '14px',
          cursor: status === 'running' ? 'default' : 'pointer',
          marginBottom: '20px',
        }}
      >
        {status === 'running' ? '建置中...' : '開始建置'}
      </button>

      {status === 'done' && (
        <div style={{ color: '#0f6e56', background: '#e1f5ee', padding: '10px 14px', borderRadius: 8, marginBottom: '16px', fontSize: '14px' }}>
          ✓ 建置完成
        </div>
      )}

      {status === 'failed' && (
        <div style={{ color: '#993c1d', background: '#faece7', padding: '10px 14px', borderRadius: 8, marginBottom: '16px', fontSize: '14px' }}>
          建置失敗：{error}
        </div>
      )}

      <div
        style={{
          background: '#1e1e1e',
          color: '#d4d4d4',
          fontFamily: 'ui-monospace, monospace',
          fontSize: '13px',
          borderRadius: 8,
          padding: '16px',
          height: '400px',
          overflowY: 'auto',
        }}
      >
        {logs.length === 0 && <div style={{ color: '#666' }}>尚未開始建置...</div>}
        {logs.map((log, i) => (
          <div key={i} style={{ marginBottom: '4px' }}>
            <span style={{ color: '#569cd6' }}>[{log.step}]</span> {log.message}
          </div>
        ))}
        <div ref={logEndRef} />
      </div>
    </div>
  );
}