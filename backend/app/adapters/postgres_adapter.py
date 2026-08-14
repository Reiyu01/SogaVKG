from .base import DatabaseAdapter


class PostgreSQLAdapter(DatabaseAdapter):

    def execute(self, query, params=None):
        raise NotImplementedError

    def execute_one(self, query, params=None):
        raise NotImplementedError

    def execute_write(self, query, params=None):
        raise NotImplementedError