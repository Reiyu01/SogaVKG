from neo4j import GraphDatabase

from app.adapters.base import DatabaseAdapter


class Neo4jAdapter(DatabaseAdapter):
    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def execute(self, cypher: str, params: dict) -> list[dict]:
        with self.driver.session() as session:
            result = session.run(cypher, params)
            return [dict(record) for record in result]

    def close(self):
        self.driver.close()