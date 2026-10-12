import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiUrl } from '../config';

function toPascalCase(value) {
  return value
    .replace(/[_\-\s]+(.)?/g, (_, chr) =>
      chr ? chr.toUpperCase() : ''
    )
    .replace(/^(.)/, (chr) =>
      chr.toUpperCase()
    );
}

function mapColumnType(type = '') {
  const value = type.toUpperCase();

  if (
    value.includes('INT') ||
    value.includes('REAL') ||
    value.includes('NUM') ||
    value.includes('DECIMAL') ||
    value.includes('FLOAT') ||
    value.includes('DOUBLE')
  ) {
    return 'number';
  }

  if (
    value.includes('BOOL')
  ) {
    return 'boolean';
  }

  return 'string';
}

function mappingKey(entity) {
  // A Builder run represents one source-backed model, so table name is enough.
  // Keeping sourceId in this UI key caused the checkbox state to drift when a
  // saved source was selected after schema discovery.
  return entity.sourceTable;
}

const steps = [
  '選擇資料來源',
  '選擇要使用的資料',
  '命名資料類型與欄位',
  '確認資料關係',
  '檢查模型',
  '發布並探索',
];



function Card({ title, children }) {
  return (
    <div
      style={{
        background: '#fff',
        border: '1px solid #e5e7eb',
        borderRadius: 12,
        padding: 20,
        marginBottom: 18,
      }}
    >
      <h3 style={{ margin: '0 0 16px', fontSize: 16 }}>{title}</h3>
      {children}
    </div>
  );
}

function HelpTip({ children }) {
  const [open, setOpen] = useState(false);
  return (
    <span
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      style={{ position: 'relative', display: 'inline-flex', marginLeft: 5, verticalAlign: 'middle' }}
    >
      <span aria-label="說明" style={{ width: 15, height: 15, borderRadius: '50%', background: '#667085', color: '#fff', fontSize: 11, lineHeight: '15px', textAlign: 'center', cursor: 'help' }}>?</span>
      {open && <span role="tooltip" style={{ position: 'absolute', zIndex: 5, top: 21, left: -8, width: 230, padding: '9px 10px', borderRadius: 7, background: '#1f2937', color: '#fff', fontSize: 12, fontWeight: 400, lineHeight: 1.45, boxShadow: '0 4px 12px rgba(0,0,0,.2)' }}>{children}</span>}
    </span>
  );
}

function StepIntro({ title, children }) {
  return <div style={{ margin: '-2px 0 18px', padding: '12px 14px', borderLeft: '3px solid #185fa5', borderRadius: 6, background: '#eef6ff', color: '#344054', fontSize: 13, lineHeight: 1.55 }}><strong>{title}</strong><div style={{ marginTop: 3 }}>{children}</div></div>;
}

function Input({ label, help, value, onChange, disabled = false, containerStyle }) {
  return (
    <label style={{ display: 'block', marginBottom: 14, ...containerStyle }}>
      <div style={{ fontSize: 13, color: '#555', marginBottom: 6 }}>
        {label}{help && <HelpTip>{help}</HelpTip>}
      </div>

      <input
        value={value}
        disabled={disabled}
        onChange={(e) => onChange?.(e.target.value)}
        style={{
          width: '100%',
          boxSizing: 'border-box',
          padding: '9px 11px',
          border: '1px solid #d8d8d8',
          borderRadius: 7,
          background: disabled ? '#f7f7f7' : '#fff',
        }}
      />
    </label>
  );
}

export default function BuildPage({ projectId: fixedProjectId }) {
  const navigate = useNavigate();
  const [step, setStep] = useState(0);

  const [knowledgeName, setKnowledgeName] = useState('未命名知識圖譜');
  const [sourceType, setSourceType] = useState('sqlite');
  const [sourcePath, setSourcePath] = useState('');
  const [postgresConfig, setPostgresConfig] = useState({ host: '', port: '5432', database: '', username: '', credential_ref: '' });
  const [googleSheetsConfig, setGoogleSheetsConfig] = useState({ spreadsheet_id: '', credential_ref: '' });
  const [sourceId, setSourceId] = useState(null);
  const [sources, setSources] = useState([]);
  const [projects, setProjects] = useState([]);
  const [projectId, setProjectId] = useState(fixedProjectId || null);
  const [sourceSaving, setSourceSaving] = useState(false);
  const [schema, setSchema] = useState(null);
  const [schemaLoading, setSchemaLoading] = useState(false);
  const [schemaError, setSchemaError] = useState(null);

  const [selectedTables, setSelectedTables] = useState([]);
  const [entities, setEntities] = useState([]);

  const [jobId, setJobId] = useState(null);
  const [job, setJob] = useState(null);
  const [buildError, setBuildError] = useState(null);
  const [validation, setValidation] = useState(null);
  const [preview, setPreview] = useState(null);

  useEffect(() => {
    fetch(apiUrl('/builder/projects'))
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error(`HTTP ${res.status}`))))
      .then((data) => setProjects(data.projects))
      .catch(() => setProjects([]));
  }, []);

  useEffect(() => {
    if (!projectId) {
      setSources([]);
      return;
    }
    fetch(apiUrl(`/builder/sources?project_id=${encodeURIComponent(projectId)}`))
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error(`HTTP ${res.status}`))))
      .then((data) => setSources(data.sources))
      .catch(() => setSources([]));
  }, [projectId]);

  async function saveSourceProfile() {
    if (sourceType === 'sqlite' && !sourcePath.trim()) {
      setSchemaError('請先輸入 SQLite Path 才能儲存資料來源。');
      return;
    }
    setSourceSaving(true);
    setSchemaError(null);
    try {
      const res = await fetch(apiUrl('/builder/sources'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: knowledgeName.trim() || '未命名資料來源',
          project_id: projectId,
          source_type: sourceType,
          config: sourceType === 'sqlite' ? { path: sourcePath } : sourceType === 'postgresql' ? { ...postgresConfig, port: Number(postgresConfig.port) } : { ...googleSheetsConfig },
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const source = await res.json();
      setSources((items) => [source, ...items.filter((item) => item.id !== source.id)]);
      setSourceId(source.id);
      if (source.source_type === 'sqlite') setSourcePath(source.config.path);
      return source;
    } catch (err) {
      setSchemaError(err.message);
      return null;
    } finally {
      setSourceSaving(false);
    }
  }

    async function loadSchema() {
    setSchemaLoading(true);
    setSchemaError(null);

    try {
        const res = await fetch(
        apiUrl('/builder/source/schema'),
        {
            method: 'POST',
            headers: {
            'Content-Type': 'application/json',
            },
            body: JSON.stringify({
            source_type: sourceType,
            path: sourceType === 'sqlite' ? sourcePath : null,
            config: sourceType === 'postgresql' ? { ...postgresConfig, port: Number(postgresConfig.port) } : sourceType === 'google_sheets' ? { ...googleSheetsConfig } : {},
            }),
        }
        );

        if (!res.ok) {
        const text = await res.text();
        throw new Error(
            text || `HTTP ${res.status}`
        );
        }

        const data = await res.json();

        setSchema(data);

        const autoEntities = data.tables.map(
        (table) => {
            const primaryKey =
            table.columns.find(
                (column) => column.primary_key
            )?.name || 'id';

            return {
            entity: toPascalCase(table.name),
            label: table.name,
            sourceType: sourceType,
            sourceId,
            sourceTable: table.name,
            nodeLabel: toPascalCase(table.name),
            primaryKey,

            properties: table.columns.map(
                (column) => ({
                column: column.name,
                property: column.name,
                type: mapColumnType(column.type),
                primaryKey: column.primary_key,
                })
            ),

            relations: table.foreign_keys.map(
                (fk) => ({
                name: fk.column.replace(
                    /_id$/i,
                    ''
                ),

                label: fk.column,

                relationshipType:
                    `HAS_${fk.target_table
                    .toUpperCase()
                    .replace(/[^A-Z0-9]/g, '_')}`,

                foreignKey: fk.column,

                targetEntity:
                    toPascalCase(
                    fk.target_table
                    ),

                targetKey:
                    fk.target_column || 'id',

                displayProperty: 'name',
                })
            ),
            };
        }
        );

        setEntities(autoEntities);
        setSelectedTables(autoEntities.map(mappingKey));

    } catch (err) {
        setSchemaError(err.message);
    } finally {
        setSchemaLoading(false);
    }
    }
  
    useEffect(() => {
    if (!jobId) return;

    const timer = setInterval(async () => {
        try {
        const res = await fetch(
            apiUrl(`/builder/build/${jobId}`)
        );

        if (!res.ok) {
            const text = await res.text();

            throw new Error(
            text || `HTTP ${res.status}`
            );
        }

        const result = await res.json();

        setJob(result);

        if (
            result.status === 'done' ||
            result.status === 'failed'
        ) {
            clearInterval(timer);
            if (result.status === 'done' && fixedProjectId) {
              navigate(`/projects/${fixedProjectId}/graph`);
            }
        }
        } catch (err) {
        setBuildError(err.message);

        clearInterval(timer);
        }
    }, 1200);

    return () => clearInterval(timer);
    }, [jobId, fixedProjectId, navigate]);

async function startBuild() {
  setBuildError(null);
  setValidation(null);
  setPreview(null);
  setJob(null);
  setJobId(null);

  try {
    // SQLite may be used once with an ad-hoc file path. Other adapters need a
    // durable source profile so validation, preview, and graph projection can
    // reopen the connection after this browser session.
    let activeSourceId = sourceId;
    if (!activeSourceId && sourceType !== 'sqlite') {
      const savedSource = await saveSourceProfile();
      if (!savedSource) throw new Error('無法儲存資料來源，請確認連線設定後再發布。');
      activeSourceId = savedSource.id;
    }

    const selectedEntities = entities.filter(
      (entity) => selectedTables.includes(mappingKey(entity))
    );

    if (selectedEntities.length === 0) {
      throw new Error('沒有選擇任何資料表');
    }
    for (const entity of selectedEntities) {
      for (const relation of entity.relations || []) {
        if (!relation.foreignKey?.trim()) {
          throw new Error(`「${entity.label || entity.entity}」的關係「${relation.label || relation.name}」尚未選擇來源欄位。請在「確認資料關係」填入用來連結目標資料的欄位，或刪除此關係。`);
        }
        if (!relation.targetEntity || !relation.targetKey?.trim()) {
          throw new Error(`「${entity.label || entity.entity}」的關係「${relation.label || relation.name}」尚未完成目標資料類型或唯一編號欄位。`);
        }
      }
    }

    // Mapping 必須在驗證與預覽之前儲存；並以本次選取的資料表完整
    // 取代舊 draft，避免切換資料來源後留下過期的 table Mapping。
    const mappings = selectedEntities.map((entity) => ({
        project_id: projectId,
        entity: entity.entity,
        label: entity.label,
        source: { node_label: entity.nodeLabel },
        ingestion: {
          source_type: entity.sourceType,
          source_table: entity.sourceTable,
          primary_key: entity.primaryKey,
          ...(entity.sourceId || activeSourceId ? { source_id: entity.sourceId || activeSourceId } : {}),
        },
        properties: Object.fromEntries(entity.properties.map((property) => [
          property.property,
          { column: property.column, type: property.type },
        ])),
        relations: Object.fromEntries((entity.relations || []).map((relation) => [
          relation.name,
          {
            label: relation.label,
            relationship_type: relation.relationshipType,
            ingestion: {
              foreign_key: relation.foreignKey,
              target_key: relation.targetKey,
            },
            target: { entity: relation.targetEntity },
            display: { property: relation.displayProperty },
          },
        ])),
      }));

    const mappingRes = await fetch(apiUrl('/builder/mappings'), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_id: projectId, mappings }),
    });

    if (!mappingRes.ok) {
      throw new Error(`儲存 Mapping 失敗：${await mappingRes.text() || `HTTP ${mappingRes.status}`}`);
    }

    const validationRes = await fetch(apiUrl(`/builder/projects/${projectId}/validate-mappings`), {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source_path: sourcePath || null, source_id: activeSourceId, project_id: projectId }),
    });
    if (!validationRes.ok) {
      throw new Error(await validationRes.text() || `驗證 Mapping 失敗（HTTP ${validationRes.status}）`);
    }
    const validationResult = await validationRes.json();
    setValidation(validationResult);
    if (!validationRes.ok || !validationResult.valid) {
      throw new Error('Mapping 驗證失敗，請先修正錯誤。');
    }
    const previewRes = await fetch(apiUrl(`/builder/projects/${projectId}/build-preview`), {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source_path: sourcePath || null, source_id: activeSourceId, project_id: projectId }),
    });
    if (!previewRes.ok) throw new Error(await previewRes.text());
    const previewResult = await previewRes.json();
    setPreview(previewResult);
    if (!window.confirm(`預覽完成：將建立 ${previewResult.entities.reduce((sum, item) => sum + item.nodes, 0)} 個節點。是否繼續？`)) return;
    // ==========================================
    // 2. Start Build
    // ==========================================

    const buildRes = await fetch(
      apiUrl('/builder/build'),
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          source_path: sourcePath || null,
          source_id: activeSourceId,
          project_id: projectId,
        }),
      }
    );

    if (!buildRes.ok) {
      const text =
        await buildRes.text();

      throw new Error(
        text ||
        `HTTP ${buildRes.status}`
      );
    }

    const result =
      await buildRes.json();

    setJobId(
      result.job_id
    );

    setJob({
      status:
        result.status ||
        'pending',

      logs: [],
    });

  } catch (err) {
    setBuildError(
      err.message
    );
  }
}

  function renderStep() {
    if (step === 0) {
    return (
        <>
        <Card title="基本設定">
            <StepIntro title="先決定資料從哪裡來">
              資料來源是「可重複使用的連線設定」。選取後，這次建立的資料類型、關係與之後的圖譜查詢都會使用同一份資料。
            </StepIntro>
            <Input
            label="這份資料模型的名稱"
            help="用來辨識這次建模工作；不會修改原始資料。"
            value={knowledgeName}
            onChange={setKnowledgeName}
            />

            {!fixedProjectId && <label style={{ display: 'block', marginBottom: 14, fontSize: 13, color: '#555' }}>
              專案
              <select value={projectId || ''} onChange={(event) => { setProjectId(event.target.value || null); setSourceId(null); }} style={{ display: 'block', width: '100%', marginTop: 6, padding: '9px 11px', border: '1px solid #d8d8d8', borderRadius: 7 }}>
                <option value="">請先選擇專案</option>
                {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
              </select>
            </label>}
            {sources.length > 0 && (
              <label style={{ display: 'block', marginBottom: 18, fontSize: 13, color: '#555' }}>
                使用已儲存的資料來源
                <HelpTip>已儲存來源可重複用於這個專案。選取它會讓這次建立的資料模型綁定到該資料庫或試算表。</HelpTip>
                <select value={sourceId || ''} onChange={(event) => {
                  const source = sources.find((item) => item.id === event.target.value);
                  setSourceId(source?.id || null);
                  if (!source) return;
                  setSourceType(source.source_type);
                  setSourcePath(source.config.path || '');
                  if (source.source_type === 'postgresql') setPostgresConfig({ host: source.config.host || '', port: String(source.config.port || 5432), database: source.config.database || '', username: source.config.username || '', credential_ref: source.config.credential_ref || '' });
                  if (source.source_type === 'google_sheets') setGoogleSheetsConfig({ spreadsheet_id: source.config.spreadsheet_id || '', credential_ref: source.config.credential_ref || '' });
                }} style={{ display: 'block', width: '100%', marginTop: 6, padding: '9px 11px', border: '1px solid #d8d8d8', borderRadius: 7 }}>
                  <option value="">新增或本次臨時使用資料來源</option>
                  {sources.filter((source) => source.active).map((source) => <option key={source.id} value={source.id}>{source.name}（{source.source_type}）</option>)}
                </select>
                <div style={{ marginTop: 5, color: '#667085', fontSize: 12 }}>選擇後按「連線並讀取結構」，再選擇要建模的資料表。</div>
              </label>
            )}

            <div
            style={{
                fontSize: 13,
                color: '#555',
                marginBottom: 8,
            }}
            >
            新增資料來源
            <HelpTip>只有在尚未選擇已儲存來源時需要設定。憑證不會儲存於 Mapping 或瀏覽器。</HelpTip>
            </div>

            <div
            style={{
                display: 'flex',
                gap: 12,
                marginBottom: 18,
            }}
            >
            {[
                'sqlite',
                'google_sheets',
                'mysql',
                'postgresql',
            ].map((type) => (
                <button
                key={type}
                onClick={() => { setSourceType(type); setSourceId(null); setSchema(null); }}
                style={{
                    border:
                    sourceType === type
                        ? '1px solid #185fa5'
                        : '1px solid #ddd',

                    background:
                    sourceType === type
                        ? '#e6f1fb'
                        : '#fff',

                    color:
                    sourceType === type
                        ? '#185fa5'
                        : '#444',

                    borderRadius: 8,
                    padding: '9px 14px',
                    cursor: 'pointer',
                }}
                >
                {type}
                </button>
            ))}
            </div>

            {/* SQLite 設定 */}
            {sourceType === 'sqlite' && (
            <>
            <Input
                label="SQLite 檔案路徑"
                help="本機或伺服器可讀取的 .db 檔路徑。若只是測試，可不儲存來源直接繼續。"
                value={sourcePath}
                onChange={(value) => {
                setSourcePath(value);
                setSourceId(null);
                }}
            />
            <button
                onClick={saveSourceProfile}
                disabled={sourceSaving || !sourcePath.trim()}
                style={{ marginTop: -4, marginBottom: 16, border: '1px solid #185fa5', borderRadius: 8, padding: '8px 12px', color: '#185fa5', background: '#fff', cursor: 'pointer' }}
            >
                {sourceSaving ? '儲存中...' : '儲存為資料來源'}
            </button>
            </>
            )}

            {sourceType === 'postgresql' && <>
            <Input label="PostgreSQL Host" value={postgresConfig.host} onChange={(value) => setPostgresConfig({ ...postgresConfig, host: value })} />
            <Input label="Port" value={postgresConfig.port} onChange={(value) => setPostgresConfig({ ...postgresConfig, port: value })} />
            <Input label="Database" value={postgresConfig.database} onChange={(value) => setPostgresConfig({ ...postgresConfig, database: value })} />
            <Input label="Username" value={postgresConfig.username} onChange={(value) => setPostgresConfig({ ...postgresConfig, username: value })} />
            <Input label="Credential reference" value={postgresConfig.credential_ref} onChange={(value) => setPostgresConfig({ ...postgresConfig, credential_ref: value })} />
            <p style={{ marginTop: -6, color: '#667085', fontSize: 12 }}>填入存放密碼的環境變數名稱，例如 <code>VKG_POSTGRES_PASSWORD</code>；不輸入密碼。</p>
            <button onClick={saveSourceProfile} disabled={sourceSaving || !postgresConfig.host || !postgresConfig.database || !postgresConfig.username || !postgresConfig.credential_ref} style={{ marginTop: -4, marginBottom: 16, border: '1px solid #185fa5', borderRadius: 8, padding: '8px 12px', color: '#185fa5', background: '#fff', cursor: 'pointer' }}>{sourceSaving ? '儲存中...' : '儲存為資料來源'}</button>
            </>}

            {sourceType === 'google_sheets' && <>
            <Input label="Spreadsheet ID" value={googleSheetsConfig.spreadsheet_id} onChange={(value) => setGoogleSheetsConfig({ ...googleSheetsConfig, spreadsheet_id: value })} />
            <Input label="Credential reference" value={googleSheetsConfig.credential_ref} onChange={(value) => setGoogleSheetsConfig({ ...googleSheetsConfig, credential_ref: value })} />
            <p style={{ marginTop: -6, color: '#667085', fontSize: 12 }}>填入含 service-account JSON 的伺服器環境變數名稱，例如 <code>VKG_GOOGLE_SERVICE_ACCOUNT_JSON</code>。請將試算表分享給該 service account 的 email。</p>
            <button onClick={saveSourceProfile} disabled={sourceSaving || !googleSheetsConfig.spreadsheet_id || !googleSheetsConfig.credential_ref} style={{ marginTop: -4, marginBottom: 16, border: '1px solid #185fa5', borderRadius: 8, padding: '8px 12px', color: '#185fa5', background: '#fff', cursor: 'pointer' }}>{sourceSaving ? '儲存中...' : '儲存為資料來源'}</button>
            </>}

            {/* 尚未支援的資料來源 */}
            {sourceType !== 'sqlite' && sourceType !== 'postgresql' && sourceType !== 'google_sheets' && (
            <div
                style={{
                padding: 12,
                background: '#f7f7f7',
                borderRadius: 8,
                color: '#777',
                fontSize: 13,
                marginBottom: 16,
                }}
            >
                此資料來源目前尚未接入 Adapter。
            </div>
            )}

            {/* Schema Discovery Error */}
            {schemaError && (
            <div
                style={{
                marginTop: 12,
                marginBottom: 12,
                padding: 12,
                borderRadius: 8,
                background: '#faece7',
                color: '#993c1d',
                }}
            >
                {schemaError}
            </div>
            )}

            {/* 連線 + Schema Discovery */}
            <button
            onClick={async () => {
                await loadSchema();
            }}
            disabled={
                schemaLoading ||
                sourceType !== 'sqlite' && sourceType !== 'postgresql' && sourceType !== 'google_sheets'
            }
            style={{
                background:
                sourceType === 'sqlite' || sourceType === 'google_sheets'
                    ? '#185fa5'
                    : '#aaa',

                color: '#fff',
                border: 'none',
                borderRadius: 8,
                padding: '10px 16px',

                cursor:
                sourceType === 'sqlite' || sourceType === 'google_sheets'
                    ? 'pointer'
                    : 'not-allowed',

                fontWeight: 600,
            }}
            >
            {schemaLoading
                ? '讀取中...'
                : '連線並讀取 Schema'}
            </button>

            {/* 成功 */}
            {schema && (
            <div
                style={{
                marginTop: 14,
                padding: 12,
                background: '#eaf7ef',
                borderRadius: 8,
                fontSize: 13,
                }}
            >
                ✓ 連線成功，共發現{' '}
                <strong>
                {schema.tables?.length || 0}
                </strong>{' '}
                個資料表
            </div>
            )}
        </Card>
        </>
    );
    }

    if (step === 1) {
    return (
        <Card title="Source Schema">
        <StepIntro title="選擇要放進知識圖譜的資料">
          系統已預設選取全部資料表。勾選的資料表會成為後續可命名、可連結與可查詢的資料類型；只要取消不想納入的表即可。
        </StepIntro>
        {!schema && (
            <div
            style={{
                padding: 14,
                borderRadius: 8,
                background: '#f7f7f7',
                color: '#777',
            }}
            >
            尚未載入 Schema，請先回到「資料來源」步驟連線。
            </div>
        )}

        {schema?.tables?.map((table) => (
            <div
            key={table.name}
            style={{
                border: '1px solid #eee',
                borderRadius: 10,
                padding: 16,
                marginBottom: 16,
                background: '#fff',
            }}
            >
            <div
                style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: 12,
                }}
            >
                <div>
                <div
                    style={{
                    fontWeight: 700,
                    fontSize: 15,
                    }}
                >
                    {table.name}
                </div>

                <div
                    style={{
                    fontSize: 12,
                    color: '#888',
                    marginTop: 3,
                    }}
                >
                    {table.row_count} rows
                </div>
                </div>

                <label
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    fontSize: 13,
                }}
                >
                <input
                    type="checkbox"
                    checked={selectedTables.includes(mappingKey({ sourceId, sourceTable: table.name }))}
                    onChange={(e) => {
                    if (e.target.checked) {
                        setSelectedTables((prev) => [
                        ...prev,
                        mappingKey({ sourceId, sourceTable: table.name }),
                        ]);
                    } else {
                        setSelectedTables((prev) =>
                        prev.filter((name) => name !== mappingKey({ sourceId, sourceTable: table.name }))
                        );
                    }
                    }}
                />

                納入這份資料模型
                <HelpTip>讀取結構後會預設選取全部資料表。取消勾選代表忽略此表；不會複製或修改原始資料。</HelpTip>
                </label>
            </div>

            <table
                style={{
                width: '100%',
                borderCollapse: 'collapse',
                fontSize: 13,
                }}
            >
                <thead>
                <tr
                    style={{
                    background: '#f7f7f7',
                    textAlign: 'left',
                    }}
                >
                    <th style={{ padding: 8 }}>
                    Column
                    </th>

                    <th style={{ padding: 8 }}>
                    Type
                    </th>

                    <th style={{ padding: 8 }}>
                    PK
                    </th>

                    <th style={{ padding: 8 }}>
                    Nullable
                    </th>
                </tr>
                </thead>

                <tbody>
                {table.columns.map((column) => (
                    <tr
                    key={column.name}
                    style={{
                        borderTop: '1px solid #eee',
                    }}
                    >
                    <td style={{ padding: 8 }}>
                        {column.name}
                    </td>

                    <td style={{ padding: 8 }}>
                        {column.type || '-'}
                    </td>

                    <td style={{ padding: 8 }}>
                        {column.primary_key ? '✓' : ''}
                    </td>

                    <td style={{ padding: 8 }}>
                        {column.nullable ? 'Yes' : 'No'}
                    </td>
                    </tr>
                ))}
                </tbody>
            </table>

            {table.foreign_keys?.length > 0 && (
                <div
                style={{
                    marginTop: 14,
                    paddingTop: 12,
                    borderTop: '1px solid #eee',
                }}
                >
                <div
                    style={{
                    fontWeight: 600,
                    fontSize: 13,
                    marginBottom: 8,
                    }}
                >
                    系統偵測到的資料關聯
                    <HelpTip>這些是資料庫已宣告的欄位對應，下一步會用它們預填關係。Google Sheets 可稍後手動建立關係。</HelpTip>
                </div>

                {table.foreign_keys.map((fk, index) => (
                    <div
                    key={`${fk.column}-${index}`}
                    style={{
                        fontSize: 13,
                        color: '#666',
                        marginBottom: 5,
                    }}
                    >
                    {fk.column}
                    {' → '}
                    {fk.target_table}.{fk.target_column}
                    </div>
                ))}
                </div>
            )}

            {table.sample_rows?.length > 0 && (
                <div
                style={{
                    marginTop: 14,
                    paddingTop: 12,
                    borderTop: '1px solid #eee',
                }}
                >
                <div
                    style={{
                    fontWeight: 600,
                    fontSize: 13,
                    marginBottom: 8,
                    }}
                >
                    範例資料
                    <HelpTip>僅供你確認欄位內容與格式，最多顯示少量資料列。</HelpTip>
                </div>

                <div
                    style={{
                    overflowX: 'auto',
                    }}
                >
                    <table
                    style={{
                        width: '100%',
                        borderCollapse: 'collapse',
                        fontSize: 12,
                    }}
                    >
                    <thead>
                        <tr
                        style={{
                            background: '#fafafa',
                            textAlign: 'left',
                        }}
                        >
                        {Object.keys(
                            table.sample_rows[0]
                        ).map((key) => (
                            <th
                            key={key}
                            style={{
                                padding: 7,
                                borderBottom:
                                '1px solid #eee',
                            }}
                            >
                            {key}
                            </th>
                        ))}
                        </tr>
                    </thead>

                    <tbody>
                        {table.sample_rows.map(
                        (row, rowIndex) => (
                            <tr key={rowIndex}>
                            {Object.keys(
                                table.sample_rows[0]
                            ).map((key) => (
                                <td
                                key={key}
                                style={{
                                    padding: 7,
                                    borderBottom:
                                    '1px solid #eee',
                                    whiteSpace: 'nowrap',
                                }}
                                >
                                {String(
                                    row[key] ?? ''
                                )}
                                </td>
                            ))}
                            </tr>
                        )
                        )}
                    </tbody>
                    </table>
                </div>
                </div>
            )}
            </div>
        ))}
        </Card>
    );
    }

    if (step === 2) {
    const selectedEntities = entities.filter(
        (entity) =>
        selectedTables.includes(mappingKey(entity))
    );

    if (selectedEntities.length === 0) {
        return (
        <Card title="資料類型與欄位">
        <StepIntro title="替資料表取一個容易理解的名稱">
          例如資料表 <code>asset_records</code> 可以叫做「資產」。接著確認每筆資料的唯一編號，並決定哪些欄位要顯示在圖譜中。
        </StepIntro>
            <div
            style={{
                padding: 14,
                background: '#f7f7f7',
                borderRadius: 8,
                color: '#777',
            }}
            >
            尚未選擇任何資料表，請回到 Schema 步驟至少選擇一個 table。
            </div>
        </Card>
        );
    }

    return (
        <Card title="資料類型與欄位">
        <StepIntro title="替資料表取一個容易理解的名稱">
          例如資料表 <code>asset_records</code> 可以叫做「資產」。接著確認每筆資料的唯一編號，並決定哪些欄位要顯示在圖譜中。
        </StepIntro>
        <div style={{ margin: '-4px 0 18px', padding: '10px 12px', borderRadius: 7, background: '#f7f7f7', color: '#475467', fontSize: 13 }}>
          本次資料模型固定使用：<strong>{sourceId ? (sources.find((source) => source.id === sourceId)?.name || sourceType) : `${sourceType}（本次使用）`}</strong>。
          若要使用另一個來源，請回到第一步重新開始一份資料模型。
        </div>
        {selectedEntities.map((entity) => {
            const entityIndex = entities.findIndex(
            (item) =>
                mappingKey(item) === mappingKey(entity)
            );

            return (
            <div
                key={mappingKey(entity)}
                style={{
                border: '1px solid #eee',
                borderRadius: 10,
                padding: 16,
                marginBottom: 18,
                }}
            >
                <div
                style={{
                    fontWeight: 700,
                    fontSize: 15,
                    marginBottom: 14,
                }}
                >
                {entity.sourceTable}
                </div>

                <div
                style={{
                    display: 'grid',
                    gridTemplateColumns:
                    'repeat(2, minmax(0, 1fr))',
                    gap: 12,
                    marginBottom: 18,
                }}
                >
                <Input
                    label="資料類型代號"
                    help="供系統與 API 使用的英文代號，例如 Asset。建議不要有空格。"
                    value={entity.entity}
                    onChange={(value) => {
                    const next = structuredClone(
                        entities
                    );

                    next[entityIndex].entity =
                        value;

                    setEntities(next);
                    }}
                />

                <Input
                    label="顯示名稱"
                    help="介面上顯示給使用者看的名稱，例如「資產」。"
                    value={entity.label}
                    onChange={(value) => {
                    const next = structuredClone(
                        entities
                    );

                    next[entityIndex].label =
                        value;

                    setEntities(next);
                    }}
                />

                <Input
                    label="圖譜節點標籤"
                    help="進階設定：圖譜中的技術標籤。一般可沿用資料類型代號。"
                    value={entity.nodeLabel}
                    onChange={(value) => {
                    const next = structuredClone(
                        entities
                    );

                    next[entityIndex].nodeLabel =
                        value;

                    setEntities(next);
                    }}
                />

                <Input
                    label="唯一編號欄位"
                    help="用來辨識每一筆資料。不可為空，且應避免重複；例如 id、asset_code。"
                    value={entity.primaryKey}
                    onChange={(value) => {
                    const next = structuredClone(
                        entities
                    );

                    next[entityIndex].primaryKey =
                        value;

                    setEntities(next);
                    }}
                />
                </div>

                <div
                style={{
                    fontWeight: 600,
                    fontSize: 13,
                    marginBottom: 8,
                }}
                >
                要顯示的欄位
                <HelpTip>左側是原始欄位；中間是它在知識圖譜中的名稱。名稱可調整，但原始欄位不會被修改。</HelpTip>
                </div>

                <div
                style={{
                    display: 'grid',
                    gridTemplateColumns:
                    '1fr 50px 1fr 130px',
                    gap: 8,
                    alignItems: 'center',
                }}
                >
                <div
                    style={{
                    fontSize: 12,
                    color: '#777',
                    }}
                >
                    Source Column
                </div>

                <div />

                <div
                    style={{
                    fontSize: 12,
                    color: '#777',
                    }}
                >
                    圖譜欄位名稱
                </div>

                <div
                    style={{
                    fontSize: 12,
                    color: '#777',
                    }}
                >
                    資料格式
                </div>

                {entity.properties.map(
                    (property, propertyIndex) => (
                    <div
                        key={`${entity.sourceTable}-${property.column}`}
                        style={{
                        display: 'contents',
                        }}
                    >
                        <div
                        style={{
                            padding: 9,
                            border: '1px solid #ddd',
                            borderRadius: 7,
                            background: '#fafafa',
                        }}
                        >
                        {property.column}

                        {property.primaryKey && (
                            <span
                            style={{
                                marginLeft: 6,
                                fontSize: 11,
                                color: '#185fa5',
                            }}
                            >
                            PK
                            </span>
                        )}
                        </div>

                        <div
                        style={{
                            textAlign: 'center',
                            color: '#999',
                        }}
                        >
                        →
                        </div>

                        <input
                        value={property.property}
                        onChange={(e) => {
                            const next =
                            structuredClone(
                                entities
                            );

                            next[
                            entityIndex
                            ].properties[
                            propertyIndex
                            ].property =
                            e.target.value;

                            setEntities(next);
                        }}
                        style={{
                            padding: 9,
                            border:
                            '1px solid #ddd',
                            borderRadius: 7,
                        }}
                        />

                        <select
                        value={property.type}
                        onChange={(e) => {
                            const next =
                            structuredClone(
                                entities
                            );

                            next[
                            entityIndex
                            ].properties[
                            propertyIndex
                            ].type =
                            e.target.value;

                            setEntities(next);
                        }}
                        style={{
                            padding: 9,
                            border:
                            '1px solid #ddd',
                            borderRadius: 7,
                            background: '#fff',
                        }}
                        >
                        <option value="string">
                            string
                        </option>

                        <option value="number">
                            number
                        </option>

                        <option value="boolean">
                            boolean
                        </option>
                        </select>
                    </div>
                    )
                )}
                </div>
            </div>
            );
        })}
        </Card>
    );
    }

    if (step === 3) {
    const selectedEntities = entities.filter(
        (entity) =>
        selectedTables.includes(mappingKey(entity))
    );

    if (selectedEntities.length === 0) {
        return (
        <Card title="資料之間的關係">
            <div
            style={{
                padding: 14,
                background: '#f7f7f7',
                borderRadius: 8,
                color: '#777',
            }}
            >
            尚未選擇任何資料表，請先回到 Schema 步驟。
            </div>
        </Card>
        );
    }

    const entitiesWithRelations = selectedEntities;

    return (
        <Card title="資料之間的關係">
        <StepIntro title="確認「哪個欄位連到哪一筆資料」">
          系統已依資料庫關聯預填。你主要只需要確認來源欄位、目標資料類型與目標的唯一編號；其他命名設定可保留預設值。
        </StepIntro>
        <div
            style={{
            marginBottom: 16,
            fontSize: 13,
            color: '#666',
            }}
        >
            系統會根據資料庫關聯自動預填。若沒有偵測到關係（例如 Google Sheets），請按「新增關係」後選擇兩側要比對的欄位。
        </div>

        {entitiesWithRelations.map((entity) => {
            const entityIndex = entities.findIndex(
            (item) =>
                mappingKey(item) === mappingKey(entity)
            );

            return (
            <div
                key={mappingKey(entity)}
                style={{
                border: '1px solid #eee',
                borderRadius: 10,
                padding: 16,
                marginBottom: 18,
                }}
            >
                <div
                style={{
                    fontWeight: 700,
                    fontSize: 16,
                    marginBottom: 16,
                }}
                >
                {entity.entity}
                <span
                    style={{
                    fontWeight: 400,
                    color: '#888',
                    fontSize: 12,
                    marginLeft: 8,
                    }}
                >
                    ({entity.sourceTable})
                </span>
                <button
                  onClick={() => {
                    const next = structuredClone(entities);
                    next[entityIndex].relations = [...(next[entityIndex].relations || []), {
                      name: 'related_to', label: '關聯到', relationshipType: 'RELATED_TO',
                      foreignKey: '', targetEntity: selectedEntities.find((item) => item.entity !== entity.entity)?.entity || entity.entity,
                      targetKey: 'id', displayProperty: 'name',
                    }];
                    setEntities(next);
                  }}
                  style={{ float: 'right', border: '1px solid #185fa5', borderRadius: 7, padding: '6px 9px', color: '#185fa5', background: '#fff', cursor: 'pointer', fontSize: 12 }}
                >
                  ＋ 新增關係
                </button>
                </div>

                {entity.relations?.length === 0 && <div style={{ padding: 12, borderRadius: 7, background: '#f7f7f7', color: '#667085', fontSize: 13 }}>尚未設定關係。若這個資料類型需要連到其他資料，請按右上角「新增關係」。</div>}

                {entity.relations?.map(
                (relation, relationIndex) => (
                    <div
                    key={`${entity.sourceTable}-${relationIndex}`}
                    style={{
                        border: '1px solid #eee',
                        borderRadius: 8,
                        padding: 14,
                        marginBottom: 14,
                        background: '#fafafa',
                    }}
                    >
                    <div style={{ position: 'relative', marginBottom: 12, padding: '10px 36px 10px 12px', borderRadius: 7, background: '#eef6ff', color: '#344054', fontSize: 13 }}>
                      <strong>目前的對應：</strong> {entity.entity}.<code>{relation.foreignKey || '來源欄位'}</code> → {relation.targetEntity || '目標資料類型'}.<code>{relation.targetKey || '唯一編號欄位'}</code>
                      <button
                        onClick={() => {
                          const next = structuredClone(entities);
                          next[entityIndex].relations.splice(relationIndex, 1);
                          setEntities(next);
                        }}
                        aria-label="刪除這個關係"
                        title="刪除這個關係"
                        style={{ position: 'absolute', top: 7, right: 7, width: 24, height: 24, border: 0, borderRadius: '50%', color: '#b42318', background: 'transparent', cursor: 'pointer', fontSize: 19, lineHeight: '22px' }}
                      >
                        ×
                      </button>
                    </div>
                    <div
                        style={{
                        display: 'grid',
                        gridTemplateColumns: '1fr 1fr',
                        gap: 12,
                        }}
                    >
                        <Input
                        label="關係代號"
                        help="進階設定：供系統識別關係的英文名稱，例如 belongs_to。通常可沿用預設值。"
                        containerStyle={{ order: 5 }}
                        value={relation.name}
                        onChange={(value) => {
                            const next =
                            structuredClone(entities);

                            next[
                            entityIndex
                            ].relations[
                            relationIndex
                            ].name = value;

                            setEntities(next);
                        }}
                        />

                        <Input
                        label="關係顯示名稱"
                        help="在圖譜上顯示的關係名稱，例如「屬於」。通常可沿用預設值。"
                        containerStyle={{ order: 6 }}
                        value={relation.label}
                        onChange={(value) => {
                            const next =
                            structuredClone(entities);

                            next[
                            entityIndex
                            ].relations[
                            relationIndex
                            ].label = value;

                            setEntities(next);
                        }}
                        />

                        <Input
                        label="圖譜關係類型"
                        help="進階設定：圖譜內部使用的技術名稱，例如 BELONGS_TO。通常不需要修改。"
                        containerStyle={{ order: 7 }}
                        value={relation.relationshipType}
                        onChange={(value) => {
                            const next =
                            structuredClone(entities);

                            next[
                            entityIndex
                            ].relations[
                            relationIndex
                            ].relationshipType =
                            value;

                            setEntities(next);
                        }}
                        />

                        <Input
                        label="來源欄位"
                        help="目前資料表中，用來存放「目標資料唯一編號」的欄位，例如 Asset.category_id。"
                        containerStyle={{ order: 1 }}
                        value={relation.foreignKey}
                        onChange={(value) => {
                            const next =
                            structuredClone(entities);

                            next[
                            entityIndex
                            ].relations[
                            relationIndex
                            ].foreignKey =
                            value;

                            setEntities(next);
                        }}
                        />

                        <div style={{ order: 2 }}>
                        <div
                            style={{
                            fontSize: 13,
                            color: '#555',
                            marginBottom: 6,
                            }}
                        >
                            要連到的資料類型
                            <HelpTip>選擇來源欄位指向的資料類型，例如 Asset.category_id 指向 Category。</HelpTip>
                        </div>

                        <select
                            value={relation.targetEntity}
                            onChange={(e) => {
                            const next =
                                structuredClone(entities);

                            next[
                                entityIndex
                            ].relations[
                                relationIndex
                            ].targetEntity =
                                e.target.value;

                            setEntities(next);
                            }}
                            style={{
                            width: '100%',
                            boxSizing: 'border-box',
                            padding: '9px 11px',
                            border: '1px solid #d8d8d8',
                            borderRadius: 7,
                            background: '#fff',
                            }}
                        >
                            {selectedEntities.map(
                            (targetEntity) => (
                                <option
                                key={
                                    targetEntity.sourceTable
                                }
                                value={
                                    targetEntity.entity
                                }
                                >
                                {
                                    targetEntity.entity
                                }
                                </option>
                            )
                            )}
                        </select>
                        </div>

                        <Input
                        label="目標的唯一編號欄位"
                        help="目標資料類型中用來比對的欄位，通常是 id。來源欄位的值必須能在這個欄位找到。"
                        containerStyle={{ order: 3 }}
                        value={relation.targetKey}
                        onChange={(value) => {
                            const next =
                            structuredClone(entities);

                            next[
                            entityIndex
                            ].relations[
                            relationIndex
                            ].targetKey =
                            value;

                            setEntities(next);
                        }}
                        />

                        <Input
                        label="關係顯示欄位"
                        help="展開關係時，目標資料要顯示哪個欄位，例如名稱 name。"
                        containerStyle={{ order: 4 }}
                        value={
                            relation.displayProperty
                        }
                        onChange={(value) => {
                            const next =
                            structuredClone(entities);

                            next[
                            entityIndex
                            ].relations[
                            relationIndex
                            ].displayProperty =
                            value;

                            setEntities(next);
                        }}
                        />
                    </div>

                    <div
                        style={{
                        marginTop: 14,
                        padding: 12,
                        borderRadius: 8,
                        background: '#fff',
                        fontSize: 13,
                        }}
                    >
                        <strong>使用者看到的關係</strong>

                        <div
                        style={{
                            marginTop: 8,
                            color: '#666',
                        }}
                        >
                        每筆 {entity.entity} 的 <code>{relation.foreignKey}</code> 會連到 {relation.targetEntity} 的 <code>{relation.targetKey}</code>。
                        </div>

                        <div
                        style={{
                            marginTop: 4,
                            color: '#999',
                            fontSize: 12,
                        }}
                        >
                        圖譜會顯示為「{entity.entity} {relation.label || relation.name} {relation.targetEntity}」。
                        </div>
                    </div>
                    </div>
                )
                )}
            </div>
            );
        })}
        </Card>
    );
    }

    if (step === 4) {
    const selectedEntities = entities.filter(
        (entity) =>
        selectedTables.includes(mappingKey(entity))
    );

    if (selectedEntities.length === 0) {
        return (
        <Card title="Preview">
            <div
            style={{
                padding: 14,
                background: '#f7f7f7',
                borderRadius: 8,
                color: '#777',
            }}
            >
            尚未選擇任何資料表，請回到 Schema 步驟。
            </div>
        </Card>
        );
    }

    return (
        <>
        <StepIntro title="最後確認模型會如何讀取資料">
          這裡會顯示資料類型、欄位與關係的摘要。發布前仍會檢查唯一編號、欄位與關係是否能在來源資料中找到。
        </StepIntro>
        {/* ==========================================
            Graph Structure Preview
        ========================================== */}
        <Card title="資料模型預覽">
            <div
            style={{
                fontSize: 13,
                color: '#666',
                marginBottom: 18,
            }}
            >
            以下是目前設定預計投影到知識圖譜的資料類型與關係，不會複製或修改原始資料。
            </div>

            {/* Entities */}
            <div
            style={{
                display: 'flex',
                flexWrap: 'wrap',
                gap: 12,
                marginBottom: 24,
            }}
            >
            {selectedEntities.map((entity) => (
                <div
                key={mappingKey(entity)}
                style={{
                    minWidth: 160,
                    padding: 14,
                    border: '1px solid #185fa5',
                    borderRadius: 10,
                    background: '#e6f1fb',
                }}
                >
                <div
                    style={{
                    fontWeight: 700,
                    color: '#185fa5',
                    }}
                >
                    {entity.entity}
                </div>

                <div
                    style={{
                    fontSize: 12,
                    color: '#666',
                    marginTop: 4,
                    }}
                >
                    Table: {entity.sourceTable}
                </div>

                <div
                    style={{
                    fontSize: 12,
                    color: '#666',
                    marginTop: 3,
                    }}
                >
                    PK: {entity.primaryKey}
                </div>

                <div
                    style={{
                    marginTop: 10,
                    paddingTop: 8,
                    borderTop: '1px solid #cbdceb',
                    fontSize: 12,
                    color: '#555',
                    }}
                >
                    {entity.properties.length} properties
                </div>
                </div>
            ))}
            </div>

            {/* Relations */}
            <div
            style={{
                fontWeight: 600,
                fontSize: 13,
                marginBottom: 10,
            }}
            >
            Relations
            </div>

            {selectedEntities.every(
            (entity) =>
                !entity.relations ||
                entity.relations.length === 0
            ) && (
            <div
                style={{
                color: '#888',
                fontSize: 13,
                }}
            >
                沒有 Relation。
            </div>
            )}

            {selectedEntities.flatMap((entity) =>
            (entity.relations || []).map(
                (relation, relationIndex) => (
                <div
                    key={`${entity.sourceTable}-${relationIndex}`}
                    style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                    padding: 12,
                    marginBottom: 8,
                    background: '#fafafa',
                    border: '1px solid #eee',
                    borderRadius: 8,
                    }}
                >
                    <strong>
                    {entity.entity}
                    </strong>

                    <span style={{ color: '#888' }}>
                    ──[
                    {relation.relationshipType}
                    ]──→
                    </span>

                    <strong>
                    {relation.targetEntity}
                    </strong>

                    <span
                    style={{
                        marginLeft: 'auto',
                        color: '#999',
                        fontSize: 12,
                    }}
                    >
                    {relation.foreignKey}
                    {' → '}
                    {relation.targetKey}
                    </span>
                </div>
                )
            )
            )}
        </Card>

        {/* ==========================================
            Mapping Detail Preview
        ========================================== */}
        <Card title="Mapping Preview">
            {selectedEntities.map((entity) => (
            <div
                key={mappingKey(entity)}
                style={{
                border: '1px solid #eee',
                borderRadius: 10,
                marginBottom: 16,
                overflow: 'hidden',
                }}
            >
                <div
                style={{
                    padding: 12,
                    background: '#f7f7f7',
                    fontWeight: 700,
                }}
                >
                {entity.sourceTable}
                {' → '}
                {entity.entity}
                </div>

                <table
                style={{
                    width: '100%',
                    borderCollapse: 'collapse',
                    fontSize: 13,
                }}
                >
                <thead>
                    <tr
                    style={{
                        textAlign: 'left',
                    }}
                    >
                    <th style={{ padding: 9 }}>
                        Source Column
                    </th>

                    <th style={{ padding: 9 }}>
                        Semantic Property
                    </th>

                    <th style={{ padding: 9 }}>
                        Type
                    </th>
                    </tr>
                </thead>

                <tbody>
                    {entity.properties.map(
                    (property) => (
                        <tr
                        key={property.column}
                        style={{
                            borderTop:
                            '1px solid #eee',
                        }}
                        >
                        <td style={{ padding: 9 }}>
                            {property.column}
                        </td>

                        <td style={{ padding: 9 }}>
                            {property.property}
                        </td>

                        <td style={{ padding: 9 }}>
                            {property.type}
                        </td>
                        </tr>
                    )
                    )}
                </tbody>
                </table>
            </div>
            ))}
        </Card>

        {/* ==========================================
            YAML Preview
        ========================================== */}
        <Card title="進階設定預覽">
        <StepIntro title="這是系統使用的 Mapping 設定">
          一般不需要直接修改；它用來讓平台日後以相同方式讀取資料。上方的可讀摘要才是主要確認內容。
        </StepIntro>
            {selectedEntities.map((entity) => {
            const preview = {
                entity: entity.entity,

                label: entity.label,

                source: {
                node_label: entity.nodeLabel,
                },

                ingestion: {
                source_type: entity.sourceType,
                source_table: entity.sourceTable,
                primary_key: entity.primaryKey,
                ...(entity.sourceId ? { source_id: entity.sourceId } : {}),
                },

                properties:
                Object.fromEntries(
                    entity.properties.map(
                    (property) => [
                        property.property,
                        {
                        column:
                            property.column,
                        type:
                            property.type,
                        },
                    ]
                    )
                ),

                relations:
                Object.fromEntries(
                    (entity.relations || []).map(
                    (relation) => [
                        relation.name,
                        {
                        label:
                            relation.label,

                        relationship_type:
                            relation.relationshipType,

                        ingestion: {
                            foreign_key:
                            relation.foreignKey,

                            target_key:
                            relation.targetKey,
                        },

                        target: {
                            entity:
                            relation.targetEntity,
                        },

                        display: {
                            property:
                            relation.displayProperty,
                        },
                        },
                    ]
                    )
                ),
            };

            return (
                <div
                key={mappingKey(entity)}
                style={{
                    marginBottom: 18,
                }}
                >
                <div
                    style={{
                    fontWeight: 600,
                    marginBottom: 8,
                    }}
                >
                    {entity.entity}.yaml
                </div>

                <pre
                    style={{
                    margin: 0,
                    padding: 14,
                    overflowX: 'auto',
                    background: '#111827',
                    color: '#e5e7eb',
                    borderRadius: 8,
                    fontSize: 12,
                    lineHeight: 1.5,
                    }}
                >
                    {JSON.stringify(
                    preview,
                    null,
                    2
                    )}
                </pre>
                </div>
            );
            })}
        </Card>
        </>
    );
    }

    if (step === 5) {
    const selectedEntities = entities.filter(
        (entity) =>
        selectedTables.includes(mappingKey(entity))
    );

    return (
        <Card title="確認並發布資料模型">
        <StepIntro title="發布不會修改原始資料">
          系統只會儲存這份模型設定，並從來源即時投影圖譜。發布前會檢查欄位、唯一編號、重複資料與關係是否可對應。
        </StepIntro>
        <div
            style={{
            marginBottom: 16,
            fontSize: 13,
            color: '#666',
            }}
        >
            將儲存並發布目前設定。圖譜會從來源即時投影，不會複製或修改原始資料。
        </div>

        <div
            style={{
            marginBottom: 18,
            padding: 14,
            background: '#f7f7f7',
            borderRadius: 8,
            }}
        >
            <div
            style={{
                fontWeight: 600,
                marginBottom: 8,
            }}
            >
            你即將建立的資料模型
            </div>

            <div style={{ fontSize: 13, marginBottom: 4 }}>
            名稱：{knowledgeName}
            </div>

            <div style={{ fontSize: 13, marginBottom: 4 }}>
            資料來源：{sourceId ? (sources.find((source) => source.id === sourceId)?.name || sourceType) : `${sourceType}（本次使用）`}
            </div>

            <div style={{ fontSize: 13, marginBottom: 4 }}>
            模式：唯讀圖譜投影（不修改原始資料）
            </div>

            <div style={{ fontSize: 13 }}>
            Entities：{selectedEntities.length}
            </div>
        </div>

        <div
            style={{
            display: 'flex',
            gap: 10,
            marginBottom: 16,
            }}
        >
            <button
            onClick={startBuild}
            disabled={
                job?.status === 'running' ||
                job?.status === 'pending'
            }
            style={{
                background:
                job?.status === 'running' ||
                job?.status === 'pending'
                    ? '#aaa'
                    : '#185fa5',

                color: 'white',
                border: 'none',
                borderRadius: 8,
                padding: '10px 18px',

                cursor:
                job?.status === 'running' ||
                job?.status === 'pending'
                    ? 'not-allowed'
                    : 'pointer',

                fontWeight: 600,
            }}
            >
            {job?.status === 'running' ||
            job?.status === 'pending'
                ? '發布中...'
                : '驗證並發布'}
            </button>
        </div>

        {buildError && (
            <div
            style={{
                background: '#faece7',
                color: '#993c1d',
                padding: 12,
                borderRadius: 8,
                marginBottom: 14,
            }}
            >
            {buildError}
            </div>
        )}
        {validation && (
          <div style={{ marginBottom: 16, padding: 12, borderRadius: 8, background: validation.valid ? '#eaf7ef' : '#faece7', color: validation.valid ? '#0f6e56' : '#993c1d', fontSize: 13 }}>
            <strong>{validation.valid ? '✓ Mapping 驗證通過' : 'Mapping 驗證失敗'}</strong>
            {validation.errors?.map((item) => <div key={item}>• {item}</div>)}
            {validation.warnings?.map((item) => <div key={item} style={{ color: '#8a5a00' }}>⚠ {item}</div>)}
          </div>
        )}
        {preview && <div style={{ marginBottom: 16, padding: 12, border: '1px solid #d8d8d8', borderRadius: 8, fontSize: 13 }}><strong>投影預覽</strong>{preview.entities.map((item) => { const duplicates = item.duplicate_primary_keys; const hasQualityIssues = item.missing_primary_key_samples.length > 0 || item.relations.some((relation) => relation.unmatched_samples.length) || duplicates?.duplicate_key_count; return <div key={item.entity} style={{ marginTop: 8 }}><b>{item.entity}</b>：可投影 {item.nodes} 節點，跳過 {item.skipped_missing_primary_key}；{duplicates?.duplicate_key_count > 0 && <span style={{ color: '#8a5a00' }}> ⚠ 重複主鍵 {duplicates.duplicate_key_count} 組（多出 {duplicates.duplicate_row_count} 筆）</span>}{item.relations.map((relation) => <span key={relation.name}> {relation.name} {relation.matched}/{relation.candidates}（未匹配 {relation.unmatched}）</span>)}{hasQualityIssues && <details><summary>查看資料品質問題樣本</summary><pre style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify({ missing_primary_key: item.missing_primary_key_samples, duplicate_primary_keys: duplicates?.samples || [], unmatched_relations: item.relations.filter((relation) => relation.unmatched_samples.length).map((relation) => ({ relation: relation.name, rows: relation.unmatched_samples })) }, null, 2)}</pre></details>}</div>; })}</div>}

        {job && (
            <>
            <div
                style={{
                marginBottom: 12,
                padding: 12,
                borderRadius: 8,
                background:
                    job.status === 'done'
                    ? '#eaf7ef'
                    : job.status === 'failed'
                    ? '#faece7'
                    : '#eef4fb',
                }}
            >
                Status：
                <strong style={{ marginLeft: 6 }}>
                {job.status}
                </strong>
            </div>

            {job.logs?.length > 0 && (
                <div
                style={{
                    background: '#111827',
                    color: '#e5e7eb',
                    borderRadius: 8,
                    padding: 14,
                }}
                >
                <div
                    style={{
                    fontWeight: 600,
                    marginBottom: 10,
                    }}
                >
                    Build Logs
                </div>

                {job.logs.map(
                    (log, index) => (
                    <div
                        key={index}
                        style={{
                        fontSize: 13,
                        padding: '6px 0',
                        borderBottom:
                            index === job.logs.length - 1
                            ? 'none'
                            : '1px solid #374151',
                        }}
                    >
                        <strong>
                        {log.step}
                        </strong>

                        {' — '}

                        {log.message}
                    </div>
                    )
                )}
                </div>
            )}

            {job.status === 'done' && job.result && (
                <div style={{ marginTop: 14, padding: 14, border: '1px solid #b7dfc5', borderRadius: 8, fontSize: 13 }}>
                    <strong>發布報告（{job.result.mode === 'projection' ? '唯讀圖譜投影' : job.result.mode}）</strong>
                    {job.result.entities?.map((item) => <div key={item.entity} style={{ marginTop: 7 }}>{item.entity}：新增 {item.created}，更新 {item.updated}，未變更 {item.unchanged}，跳過 {item.skipped_missing_primary_key}{item.deletion_candidates ? `，清理候選 ${item.deletion_candidates}` : ''}</div>)}
                    {job.result.relations?.map((item, index) => <div key={`${item.entity}-${item.relation}-${index}`} style={{ marginTop: 4, color: '#555' }}>{item.entity}.{item.relation}：處理 {item.processed} 筆</div>)}
                    {job.result.data_quality?.filter((item) => item.duplicate_primary_keys?.duplicate_key_count).map((item) => <div key={item.entity} style={{ marginTop: 4, color: '#8a5a00' }}>⚠ {item.entity}：重複主鍵 {item.duplicate_primary_keys.duplicate_key_count} 組（多出 {item.duplicate_primary_keys.duplicate_row_count} 筆）</div>)}
                </div>
            )}

            {job.status === 'done' && (
                <div
                style={{
                    marginTop: 14,
                    padding: 14,
                    background: '#eaf7ef',
                    borderRadius: 8,
                    color: '#23633c',
                }}
                >
                ✓ Mapping 已發布，可前往知識圖譜探索資料
                </div>
            )}

            {job.status === 'failed' && (
                <div
                style={{
                    marginTop: 14,
                    padding: 14,
                    background: '#faece7',
                    borderRadius: 8,
                    color: '#993c1d',
                }}
                >
                ✕ Mapping 發布失敗
                </div>
            )}
            </>
        )}
        </Card>
    );
    }
  }
  return (
    <div
      style={{
        flex: 1,
        height: '100vh',
        overflowY: 'auto',
        background: '#fafafa',
      }}
    >
      <div
        style={{
          maxWidth: 980,
          margin: '0 auto',
          padding: '30px 28px 60px',
        }}
      >
        <div style={{ marginBottom: 24 }}>
          <h1 style={{ margin: 0, fontSize: 24 }}>Knowledge Builder</h1>
          <div style={{ color: '#777', marginTop: 6, fontSize: 14 }}>
            Data Source → Mapping → Visual Knowledge Graph
          </div>
        </div>

        <div
          style={{
            display: 'flex',
            gap: 8,
            marginBottom: 24,
            flexWrap: 'wrap',
          }}
        >
          {steps.map((label, index) => (
            <button
              key={label}
              onClick={() => setStep(index)}
              style={{
                border:
                  step === index
                    ? '1px solid #185fa5'
                    : '1px solid #ddd',
                background:
                  step === index ? '#e6f1fb' : '#fff',
                color: step === index ? '#185fa5' : '#555',
                borderRadius: 20,
                padding: '7px 12px',
                cursor: 'pointer',
                fontSize: 13,
              }}
            >
              {index + 1}. {label}
            </button>
          ))}
        </div>

        {renderStep()}

        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            marginTop: 12,
          }}
        >
          <button
            onClick={() => setStep((s) => Math.max(0, s - 1))}
            disabled={step === 0}
            style={{
              border: '1px solid #ddd',
              background: '#fff',
              borderRadius: 8,
              padding: '9px 15px',
              cursor: step === 0 ? 'default' : 'pointer',
            }}
          >
            上一步
          </button>

          {step < steps.length - 1 && (
            <button
              onClick={() =>
                setStep((s) => Math.min(steps.length - 1, s + 1))
              }
              style={{
                border: 'none',
                background: '#185fa5',
                color: 'white',
                borderRadius: 8,
                padding: '9px 16px',
                cursor: 'pointer',
              }}
            >
              下一步
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
