import { useEffect, useState } from 'react';

const API_BASE = 'http://163.18.26.230:8000';

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

const steps = [
  '資料來源',
  'Schema',
  'Entity Mapping',
  'Relation Mapping',
  'Preview',
  'Build',
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

function Input({ label, value, onChange, disabled = false }) {
  return (
    <label style={{ display: 'block', marginBottom: 14 }}>
      <div style={{ fontSize: 13, color: '#555', marginBottom: 6 }}>
        {label}
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

export default function BuildPage() {
  const [step, setStep] = useState(0);

  const [knowledgeName, setKnowledgeName] = useState('實驗室知識庫');
  const [sourceType, setSourceType] = useState('sqlite');
  const [sourcePath, setSourcePath] = useState('backend/data/lab.db');
  const [schema, setSchema] = useState(null);
  const [schemaLoading, setSchemaLoading] = useState(false);
  const [schemaError, setSchemaError] = useState(null);

  const [selectedTables, setSelectedTables] = useState([]);
  const [entities, setEntities] = useState([]);

  const [jobId, setJobId] = useState(null);
  const [job, setJob] = useState(null);
  const [buildError, setBuildError] = useState(null);

    async function loadSchema() {
    setSchemaLoading(true);
    setSchemaError(null);

    try {
        const res = await fetch(
        `${API_BASE}/builder/source/schema`,
        {
            method: 'POST',
            headers: {
            'Content-Type': 'application/json',
            },
            body: JSON.stringify({
            source_type: sourceType,
            path: sourceType === 'sqlite'
                ? sourcePath
                : null,
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

        setSelectedTables(
        data.tables.map(
            (table) => table.name
        )
        );

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
            `${API_BASE}/builder/build/${jobId}`
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
        }
        } catch (err) {
        setBuildError(err.message);

        clearInterval(timer);
        }
    }, 1200);

    return () => clearInterval(timer);
    }, [jobId]);

async function startBuild() {
  setBuildError(null);
  setJob(null);
  setJobId(null);

  try {
    const selectedEntities = entities.filter(
      (entity) =>
        selectedTables.includes(
          entity.sourceTable
        )
    );

    if (selectedEntities.length === 0) {
      throw new Error(
        '沒有選擇任何資料表'
      );
    }

    // ==========================================
    // 1. Save Mapping
    // ==========================================

    for (const entity of selectedEntities) {
      const mapping = {
        entity: entity.entity,

        label: entity.label,

        source: {
          node_label:
            entity.nodeLabel,
        },

        ingestion: {
          source_type:
            entity.sourceType,

          source_table:
            entity.sourceTable,

          primary_key:
            entity.primaryKey,
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

      const mappingRes = await fetch(
        `${API_BASE}/builder/mapping`,
        {
          method: 'POST',

          headers: {
            'Content-Type':
              'application/json',
          },

          body: JSON.stringify(
            mapping
          ),
        }
      );

      if (!mappingRes.ok) {
        const text =
          await mappingRes.text();

        throw new Error(
          `儲存 ${entity.entity} Mapping 失敗：${text}`
        );
      }
    }

    // ==========================================
    // 2. Start Build
    // ==========================================

    const buildRes = await fetch(
      `${API_BASE}/builder/build`,
      {
        method: 'POST',
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
            <Input
            label="Knowledge Name"
            value={knowledgeName}
            onChange={setKnowledgeName}
            />

            <div
            style={{
                fontSize: 13,
                color: '#555',
                marginBottom: 8,
            }}
            >
            Data Source
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
                onClick={() => setSourceType(type)}
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
            <Input
                label="SQLite Path"
                value={sourcePath}
                onChange={setSourcePath}
            />
            )}

            {/* 尚未支援的資料來源 */}
            {sourceType !== 'sqlite' && (
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
                sourceType !== 'sqlite'
            }
            style={{
                background:
                sourceType === 'sqlite'
                    ? '#185fa5'
                    : '#aaa',

                color: '#fff',
                border: 'none',
                borderRadius: 8,
                padding: '10px 16px',

                cursor:
                sourceType === 'sqlite'
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
                    checked={selectedTables.includes(table.name)}
                    onChange={(e) => {
                    if (e.target.checked) {
                        setSelectedTables((prev) => [
                        ...prev,
                        table.name,
                        ]);
                    } else {
                        setSelectedTables((prev) =>
                        prev.filter(
                            (name) => name !== table.name
                        )
                        );
                    }
                    }}
                />

                使用此資料表
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
                    Foreign Keys
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
                    Sample Data
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
        selectedTables.includes(entity.sourceTable)
    );

    if (selectedEntities.length === 0) {
        return (
        <Card title="Entity Mapping">
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
        <Card title="Entity Mapping">
        {selectedEntities.map((entity) => {
            const entityIndex = entities.findIndex(
            (item) =>
                item.sourceTable === entity.sourceTable
            );

            return (
            <div
                key={entity.sourceTable}
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
                    label="Entity Name"
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
                    label="Entity Label"
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
                    label="Node Label"
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
                    label="Primary Key"
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
                Property Mapping
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
                    Semantic Property
                </div>

                <div
                    style={{
                    fontSize: 12,
                    color: '#777',
                    }}
                >
                    Type
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
        selectedTables.includes(entity.sourceTable)
    );

    if (selectedEntities.length === 0) {
        return (
        <Card title="Relation Mapping">
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

    const entitiesWithRelations = selectedEntities.filter(
        (entity) =>
        entity.relations &&
        entity.relations.length > 0
    );

    if (entitiesWithRelations.length === 0) {
        return (
        <Card title="Relation Mapping">
            <div
            style={{
                padding: 14,
                background: '#f7f7f7',
                borderRadius: 8,
                color: '#777',
            }}
            >
            目前選擇的資料表沒有 Foreign Key，因此沒有自動產生 Relation。
            </div>
        </Card>
        );
    }

    return (
        <Card title="Relation Mapping">
        <div
            style={{
            marginBottom: 16,
            fontSize: 13,
            color: '#666',
            }}
        >
            系統會根據 SQLite Foreign Key 自動建立初始 Relation Mapping，
            你可以再修改 Relationship Type、Target Entity 等設定。
        </div>

        {entitiesWithRelations.map((entity) => {
            const entityIndex = entities.findIndex(
            (item) =>
                item.sourceTable === entity.sourceTable
            );

            return (
            <div
                key={entity.sourceTable}
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
                </div>

                {entity.relations.map(
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
                    <div
                        style={{
                        display: 'grid',
                        gridTemplateColumns: '1fr 1fr',
                        gap: 12,
                        }}
                    >
                        <Input
                        label="Relation Name"
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
                        label="Relation Label"
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
                        label="Relationship Type"
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
                        label="Foreign Key"
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

                        <div>
                        <div
                            style={{
                            fontSize: 13,
                            color: '#555',
                            marginBottom: 6,
                            }}
                        >
                            Target Entity
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
                        label="Target Key"
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
                        label="Display Property"
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
                        <strong>Preview</strong>

                        <div
                        style={{
                            marginTop: 8,
                            color: '#666',
                        }}
                        >
                        {entity.entity}
                        {' --['}
                        {relation.relationshipType}
                        {']→ '}
                        {relation.targetEntity}
                        </div>

                        <div
                        style={{
                            marginTop: 4,
                            color: '#999',
                            fontSize: 12,
                        }}
                        >
                        FK: {relation.foreignKey}
                        {' → '}
                        {relation.targetEntity}.
                        {relation.targetKey}
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
        selectedTables.includes(entity.sourceTable)
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
        {/* ==========================================
            Graph Structure Preview
        ========================================== */}
        <Card title="Knowledge Graph Preview">
            <div
            style={{
                fontSize: 13,
                color: '#666',
                marginBottom: 18,
            }}
            >
            以下是目前設定預計建立到 Neo4j 的 Entity 與 Relation。
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
                key={entity.sourceTable}
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
                key={entity.sourceTable}
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
        <Card title="Generated Mapping">
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
                key={entity.sourceTable}
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
        selectedTables.includes(entity.sourceTable)
    );

    return (
        <Card title="Build to Neo4j">
        <div
            style={{
            marginBottom: 16,
            fontSize: 13,
            color: '#666',
            }}
        >
            將儲存目前 Mapping，然後建立 Knowledge Graph 到 Neo4j。
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
            Build Summary
            </div>

            <div style={{ fontSize: 13, marginBottom: 4 }}>
            Knowledge Name：{knowledgeName}
            </div>

            <div style={{ fontSize: 13, marginBottom: 4 }}>
            Source：{sourceType}
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
                ? '建置中...'
                : '開始建置'}
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
                ✓ Knowledge Graph 建置完成
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
                ✕ Knowledge Graph 建置失敗
                </div>
            )}
            </>
        )}
        </Card>
    );
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
            Data Source → Mapping → Neo4j Knowledge Graph
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