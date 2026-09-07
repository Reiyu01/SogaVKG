from app.semantic.mapper import SemanticMapper
from app.semantic.cypher_query_builder import CypherQueryBuilder
from app.schemas.semantic_query import SemanticQuery, QueryFilter
from app.adapters.neo4j_adapter import Neo4jAdapter

# ---- 建立 mapper / builder ----
mapper = SemanticMapper("../semantic/mappings")
builder = CypherQueryBuilder(mapper)

# ---- 組查詢 ----
query = SemanticQuery(
    entity="Asset",
    fields=["name", "category", "location"],
    filters=[QueryFilter(field="location", operator="LIKE", value="C217")],
)

result = builder.build(query)
print("=== Cypher ===")
print(result.cypher)
print("=== Params ===")
print(result.params)

# ---- 連線 Neo4j 並執行 ----
db = Neo4jAdapter(
    uri="bolt://localhost:7687",
    user="neo4j",
    password="your_password",  # <-- 記得改成你啟動 Docker 時設定的密碼
)

rows = db.execute(result.cypher, result.params)

print(f"=== 查詢結果（共 {len(rows)} 筆） ===")
for row in rows[:5]:
    print(row)

db.close()
