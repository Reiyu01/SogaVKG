"""Read-only Google Sheets implementation of the shared source contract."""

from __future__ import annotations

import json
import os
from collections import Counter
from typing import Any

from app.adapters.source_adapter import SourceAdapter


class GoogleSheetsSourceAdapter(SourceAdapter):
    source_type = "google_sheets"

    def __init__(self, config: dict[str, Any], spreadsheet: Any | None = None):
        self.config = config
        self.spreadsheet = spreadsheet or self._open_spreadsheet()

    def _open_spreadsheet(self):
        try:
            import gspread
            from google.oauth2.service_account import Credentials
        except ImportError as error:
            raise RuntimeError("Google Sheets support requires gspread and google-auth; install backend requirements first") from error
        credential_ref = self.config.get("credential_ref")
        encoded_credentials = os.getenv(credential_ref or "")
        if not credential_ref or not encoded_credentials:
            raise ValueError("Google Sheets credential_ref must name an environment variable containing service-account JSON")
        try:
            service_account = json.loads(encoded_credentials)
        except json.JSONDecodeError as error:
            raise ValueError("Google Sheets credential_ref does not contain valid JSON") from error
        credentials = Credentials.from_service_account_info(
            service_account,
            scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
        )
        return gspread.authorize(credentials).open_by_key(self.config["spreadsheet_id"])

    def _worksheet(self, table: str):
        return self.spreadsheet.worksheet(table)

    def _rows(self, table: str) -> list[dict[str, Any]]:
        return [dict(row) for row in self._worksheet(table).get_all_records()]

    @staticmethod
    def _column_type(values: list[Any]) -> str:
        non_empty = [value for value in values if value not in (None, "")]
        if non_empty and all(isinstance(value, bool) for value in non_empty):
            return "boolean"
        if non_empty and all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in non_empty):
            return "number"
        return "string"

    def inspect_schema(self) -> dict[str, Any]:
        tables = []
        for worksheet in self.spreadsheet.worksheets():
            name = worksheet.title
            rows = self._rows(name)
            headers = worksheet.row_values(1)
            columns = [{
                "name": header,
                "type": self._column_type([row.get(header) for row in rows]),
                "nullable": any(row.get(header) in (None, "") for row in rows),
                "default": None,
                "primary_key": False,
            } for header in headers if header]
            tables.append({"name": name, "row_count": len(rows), "columns": columns, "foreign_keys": [], "sample_rows": rows[:5]})
        return {"source_type": self.source_type, "spreadsheet_id": self.config["spreadsheet_id"], "tables": tables}

    def table_columns(self, table: str) -> set[str]:
        return set(self._worksheet(table).row_values(1))

    def read_rows(self, table: str) -> list[dict[str, Any]]:
        return self._rows(table)

    def values(self, table: str, column: str) -> set[Any]:
        return {row.get(column) for row in self._rows(table)}

    def find_rows(self, table: str, column: str | None = None, value: Any = None, limit: int = 300) -> list[dict[str, Any]]:
        rows = self._rows(table)
        if column is not None:
            rows = [row for row in rows if row.get(column) == value]
        return rows[:limit]

    def duplicate_keys(self, table: str, primary_key: str) -> dict[str, Any]:
        counts = Counter(row.get(primary_key) for row in self._rows(table) if row.get(primary_key) not in (None, ""))
        duplicates = [(value, occurrences) for value, occurrences in counts.items() if occurrences > 1]
        duplicates.sort(key=lambda item: (-item[1], str(item[0])))
        return {
            "duplicate_key_count": len(duplicates),
            "duplicate_row_count": sum(occurrences - 1 for _, occurrences in duplicates),
            "samples": [{"primary_key": value, "occurrences": occurrences} for value, occurrences in duplicates[:20]],
        }
