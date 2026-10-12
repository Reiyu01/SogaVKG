import { useCallback, useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { apiUrl } from '../config';

const inputStyle = { display: 'block', boxSizing: 'border-box', width: '100%', marginTop: 6, padding: '9px 10px', border: '1px solid #d0d5dd', borderRadius: 7, background: '#fff' };
const primaryButton = { border: 0, borderRadius: 7, padding: '9px 14px', background: '#185fa5', color: '#fff', cursor: 'pointer' };

function fieldsFor(mapping) {
  if (!mapping) return [];
  const fields = Object.values(mapping.properties || {}).map((property) => property?.column).filter(Boolean);
  const primaryKey = mapping.ingestion?.primary_key || 'id';
  return [...new Set([primaryKey, ...fields])];
}

export default function IdentityMappingsPage() {
  const { projectId } = useParams();
  const [mappings, setMappings] = useState([]);
  const [alignments, setAlignments] = useState([]);
  const [auditEvents, setAuditEvents] = useState([]);
  const [form, setForm] = useState({ source_entity: '', target_entity: '', source_column: '', target_column: '', label: '同一概念', normalization_rule: 'exact' });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const [mappingsResponse, alignmentsResponse, auditResponse] = await Promise.all([
        fetch(apiUrl(`/builder/mappings?project_id=${encodeURIComponent(projectId)}`)),
        fetch(apiUrl(`/builder/entity-alignments?project_id=${encodeURIComponent(projectId)}`)),
        fetch(apiUrl(`/builder/entity-alignments/audit-events?project_id=${encodeURIComponent(projectId)}`)),
      ]);
      const mappingsBody = await mappingsResponse.json();
      const alignmentsBody = await alignmentsResponse.json();
      const auditBody = await auditResponse.json();
      if (!mappingsResponse.ok) throw new Error(mappingsBody.detail || '無法載入資料模型');
      if (!alignmentsResponse.ok) throw new Error(alignmentsBody.detail || '無法載入 Identity Mappings');
      if (!auditResponse.ok) throw new Error(auditBody.detail || '無法載入 Identity Mapping 歷史');
      setMappings(mappingsBody.mappings || []);
      setAlignments(alignmentsBody.alignments || []);
      setAuditEvents(auditBody.events || []);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : '載入失敗');
    } finally { setLoading(false); }
  }, [projectId]);

  useEffect(() => { load(); }, [load]);

  const entities = useMemo(() => mappings.map((mapping) => ({ value: mapping.entity, label: mapping.label || mapping.entity })), [mappings]);
  const sourceMapping = mappings.find((mapping) => mapping.entity === form.source_entity);
  const targetMapping = mappings.find((mapping) => mapping.entity === form.target_entity);
  const resetPreview = () => setPreview(null);
  const updateEntity = (key, value) => {
    resetPreview();
    setForm((current) => ({ ...current, [key]: value, [key === 'source_entity' ? 'source_column' : 'target_column']: '' }));
  };

  const previewAlignment = async () => {
    setError(''); setPreview(null);
    if (!form.source_entity || !form.target_entity || !form.source_column || !form.target_column) { setError('請先選擇兩個 Entity 與比對欄位。'); return null; }
    if (form.source_entity === form.target_entity) { setError('請選擇兩個不同的 Entity。'); return null; }
    setPreviewing(true);
    try {
      const response = await fetch(apiUrl('/builder/entity-alignments/preview'), {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_id: projectId, ...form }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || '無法預覽 Identity Mapping');
      setPreview(body);
      return body;
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : '預覽失敗');
      return null;
    } finally { setPreviewing(false); }
  };

  const save = async (event) => {
    event.preventDefault(); setError('');
    if (form.source_entity === form.target_entity) { setError('請選擇兩個不同的 Entity。'); return; }
    setSaving(true);
    try {
      const response = await fetch(apiUrl('/builder/entity-alignments'), {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_id: projectId, ...form }),
      });
      const body = await response.json();
      if (!response.ok) {
        if (body.detail?.preview) setPreview(body.detail.preview);
        throw new Error(body.detail?.message || body.detail || '儲存失敗');
      }
      setAlignments((current) => {
        const withoutSamePair = current.filter((alignment) => !(alignment.source_entity === body.source_entity && alignment.target_entity === body.target_entity));
        return [...withoutSamePair, body];
      });
      setForm({ source_entity: '', target_entity: '', source_column: '', target_column: '', label: '同一概念', normalization_rule: 'exact' }); setPreview(null);
      load();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : '儲存失敗');
    } finally { setSaving(false); }
  };

  const remove = async (alignment) => {
    if (!window.confirm(`移除 ${alignment.source_entity} 與 ${alignment.target_entity} 的 Identity Mapping？`)) return;
    setError('');
    try {
      const response = await fetch(apiUrl(`/builder/entity-alignments/${encodeURIComponent(alignment.id)}?project_id=${encodeURIComponent(projectId)}`), { method: 'DELETE' });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || '刪除失敗');
      setAlignments((current) => current.filter((item) => item.id !== alignment.id));
      load();
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : '刪除失敗'); }
  };

  return <div style={{ padding: '32px 40px', overflow: 'auto', width: '100%', boxSizing: 'border-box' }}>
    <h2 style={{ marginTop: 0 }}>Identity Mappings</h2>
    <p style={{ color: '#667085', maxWidth: 760 }}>將兩個來源的 Entity 視為同一概念。這只建立概念層連結，不會複製資料或建立逐筆資料的 identity edges。</p>
    {error && <p role="alert" style={{ color: '#b42318', padding: '10px 12px', background: '#fef3f2', borderRadius: 7 }}>{error}</p>}
    <section style={{ maxWidth: 820, marginTop: 24, padding: 20, border: '1px solid #d0d5dd', borderRadius: 10 }}>
      <h3 style={{ marginTop: 0 }}>新增 Identity Mapping</h3>
      {loading ? <p style={{ color: '#667085' }}>載入資料模型中…</p> : mappings.length < 2 ? <p style={{ color: '#667085' }}>至少需要兩個已建立的 Entity；請先在「資料模型」新增 Mapping。</p> : <form onSubmit={save}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 14 }}>
          <label>來源 Entity<select required value={form.source_entity} onChange={(event) => updateEntity('source_entity', event.target.value)} style={inputStyle}><option value="">請選擇</option>{entities.map((entity) => <option key={entity.value} value={entity.value}>{entity.label} ({entity.value})</option>)}</select></label>
          <label>來源比對欄位<select required disabled={!sourceMapping} value={form.source_column} onChange={(event) => { resetPreview(); setForm((current) => ({ ...current, source_column: event.target.value })); }} style={inputStyle}><option value="">請選擇</option>{fieldsFor(sourceMapping).map((field) => <option key={field} value={field}>{field}</option>)}</select></label>
          <label>目標 Entity<select required value={form.target_entity} onChange={(event) => updateEntity('target_entity', event.target.value)} style={inputStyle}><option value="">請選擇</option>{entities.map((entity) => <option key={entity.value} value={entity.value}>{entity.label} ({entity.value})</option>)}</select></label>
          <label>目標比對欄位<select required disabled={!targetMapping} value={form.target_column} onChange={(event) => { resetPreview(); setForm((current) => ({ ...current, target_column: event.target.value })); }} style={inputStyle}><option value="">請選擇</option>{fieldsFor(targetMapping).map((field) => <option key={field} value={field}>{field}</option>)}</select></label>
        </div>
        <label style={{ display: 'block', maxWidth: 340, marginTop: 14 }}>顯示名稱<input required value={form.label} onChange={(event) => setForm((current) => ({ ...current, label: event.target.value }))} style={inputStyle} /></label>
        <label style={{ display: 'block', maxWidth: 340, marginTop: 14 }}>鍵值正規化<select value={form.normalization_rule} onChange={(event) => { resetPreview(); setForm((current) => ({ ...current, normalization_rule: event.target.value })); }} style={inputStyle}><option value="exact">不處理（完全相同）</option><option value="trim">去除前後空白</option><option value="trim_casefold">去除空白並忽略英文大小寫</option></select></label>
        <div style={{ display: 'flex', gap: 10, marginTop: 18 }}>
          <button type="button" disabled={previewing || saving} onClick={previewAlignment} style={{ ...primaryButton, background: '#475467', opacity: previewing ? .65 : 1 }}>{previewing ? '比對中…' : '預覽比對結果'}</button>
          <button disabled={saving || previewing} style={{ ...primaryButton, opacity: saving ? .65 : 1 }}>{saving ? '儲存中…' : '建立 Mapping'}</button>
        </div>
      </form>}
      {preview && <div style={{ marginTop: 18, padding: 14, borderRadius: 8, background: preview.one_to_one_valid ? '#ecfdf3' : '#fef3f2', color: preview.one_to_one_valid ? '#067647' : '#b42318' }}>
        <strong>{preview.one_to_one_valid ? '可建立：非空比對鍵符合一對一規則。' : '不可建立：發現重複的非空比對鍵。'}</strong>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 10, marginTop: 10, color: '#344054' }}>
          <span>精確匹配：{preview.exact_match_count}</span><span>來源未匹配：{preview.source_unmatched_count}</span><span>目標未匹配：{preview.target_unmatched_count}</span><span>來源空值：{preview.source.null_key_count}</span><span>目標空值：{preview.target.null_key_count}</span><span>來源重複鍵：{preview.source.duplicate_key_count}</span><span>目標重複鍵：{preview.target.duplicate_key_count}</span>
        </div>
        {(!preview.one_to_one_valid || preview.source_unmatched_count || preview.target_unmatched_count) && <details style={{ marginTop: 10, color: '#344054' }}><summary>查看鍵值樣本</summary><div style={{ marginTop: 6 }}>來源未匹配：{preview.source_unmatched_samples.map((item) => String(item.key)).join(', ') || '無'}<br />目標未匹配：{preview.target_unmatched_samples.map((item) => String(item.key)).join(', ') || '無'}<br />來源重複：{preview.source.duplicate_key_samples.map((item) => `${item.key} (${item.occurrences})`).join(', ') || '無'}<br />目標重複：{preview.target.duplicate_key_samples.map((item) => `${item.key} (${item.occurrences})`).join(', ') || '無'}</div></details>}
      </div>}
    </section>
    <section style={{ maxWidth: 820, marginTop: 28 }}>
      <h3>目前的 Identity Mappings</h3>
      {!loading && alignments.length === 0 ? <p style={{ color: '#667085' }}>尚未建立任何 Identity Mapping。</p> : alignments.map((alignment) => <article key={alignment.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, padding: 16, marginBottom: 10, border: '1px solid #e5e7eb', borderRadius: 9 }}>
        <div><strong>{alignment.source_entity}</strong><span style={{ margin: '0 10px', color: '#667085' }}>↔</span><strong>{alignment.target_entity}</strong><div style={{ marginTop: 7, color: '#667085', fontSize: 14 }}>{alignment.source_column} = {alignment.target_column} · {alignment.label} · {{ exact: '完全相同', trim: '去除空白', trim_casefold: '去除空白＋忽略大小寫' }[alignment.normalization_rule || 'exact']}</div></div>
        <button onClick={() => remove(alignment)} style={{ border: 0, color: '#b42318', background: 'transparent', cursor: 'pointer', whiteSpace: 'nowrap' }}>移除</button>
      </article>)}
    </section>
    <section style={{ maxWidth: 820, marginTop: 28 }}>
      <h3>異動紀錄</h3>
      {!loading && auditEvents.length === 0 ? <p style={{ color: '#667085' }}>尚無異動紀錄。</p> : auditEvents.map((event) => <div key={event.id} style={{ padding: '9px 0', borderBottom: '1px solid #e5e7eb', fontSize: 14 }}><strong>{{ created: '建立', updated: '更新', deleted: '刪除' }[event.action] || event.action}</strong> · {event.alignment.source_entity} ↔ {event.alignment.target_entity}<div style={{ color: '#667085', fontSize: 12, marginTop: 3 }}>{event.created_at}</div></div>)}
    </section>
  </div>;
}
