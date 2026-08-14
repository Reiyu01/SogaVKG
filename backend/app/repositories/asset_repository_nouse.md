from app.adapters.base import DatabaseAdapter


class SQLiteAssetRepository:

    def __init__(self, db: DatabaseAdapter):
        self.db = db

    def get_all(self):
        return self.db.execute(
            """
            SELECT
                a.asset_code,
                a.name,
                a.quantity,
                a.status,
                c.name AS category,
                l.name AS location
            FROM assets a
            LEFT JOIN categories c
                ON a.category_id = c.id
            LEFT JOIN locations l
                ON a.location_id = l.id
            """
        )

    def get_by_code(self, asset_code: str):
        return self.db.execute_one(
            """
            SELECT
                a.asset_code,
                a.name,
                a.quantity,
                a.status,
                c.name AS category,
                l.name AS location
            FROM assets a
            LEFT JOIN categories c
                ON a.category_id = c.id
            LEFT JOIN locations l
                ON a.location_id = l.id
            WHERE a.asset_code = :asset_code
            """,
            {
                "asset_code": asset_code
            }
        )

    def search(self, keyword: str):
        return self.db.execute(
            """
            SELECT
                a.asset_code,
                a.name,
                a.quantity,
                a.status,
                c.name AS category,
                l.name AS location
            FROM assets a
            LEFT JOIN categories c
                ON a.category_id = c.id
            LEFT JOIN locations l
                ON a.location_id = l.id
            WHERE a.name LIKE :keyword
               OR a.asset_code LIKE :keyword
               OR a.note LIKE :keyword
            """,
            {
                "keyword": f"%{keyword}%"
            }
        )