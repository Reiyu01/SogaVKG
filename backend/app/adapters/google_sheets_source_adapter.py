"""Read-only Google Sheets implementation of the shared source contract."""

from __future__ import annotations

import json
import os
import time
from collections import Counter
from threading import Lock
from typing import Any

from app.adapters.source_adapter import SourceAdapter


class GoogleSheetsSourceAdapter(SourceAdapter):
    source_type = "google_sheets"
    # The builder deliberately performs validation, preview, then publishing as
    # separate HTTP requests.  Retain a brief snapshot between those requests:
    # otherwise every request reads every tab again and quickly hits the Sheets
    # per-minute read quota.
    _snapshot_ttl_seconds = 120
    _snapshot_cache: dict[tuple[str, str], tuple[float, dict[str, tuple[list[str], list[dict[str, Any]]]]]] = {}
    _snapshot_lock = Lock()

    def __init__(self, config: dict[str, Any], spreadsheet: Any | None = None):
        self.config = config
        self._injected_spreadsheet = spreadsheet is not None
        self.spreadsheet = spreadsheet or self._open_spreadsheet()
        self._schema: dict[str, Any] | None = None
        self._tables: dict[str, tuple[list[str], list[dict[str, Any]]]] = {}

    def _cache_key(self) -> tuple[str, str]:
        return (self.config["spreadsheet_id"], self.config.get("credential_ref", ""))

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

    @staticmethod
    def _is_rate_limited(error: Exception) -> bool:
        response = getattr(error, "response", None)
        return getattr(response, "status_code", None) == 429 or "429" in str(error) or "RESOURCE_EXHAUSTED" in str(error)

    @classmethod
    def _read_with_retry(cls, reader):
        # Google recommends truncated exponential backoff for 429 responses.
        for attempt in range(4):
            try:
                return reader()
            except Exception as error:
                if not cls._is_rate_limited(error) or attempt == 3:
                    if cls._is_rate_limited(error):
                        raise ValueError("Google Sheets 讀取額度暫時用盡；請稍候約一分鐘後重試。") from error
                    raise
                time.sleep(2 ** attempt)

    def _load_table(self, table: str) -> tuple[list[str], list[dict[str, Any]]]:
        if table in self._tables:
            return self._tables[table]
        worksheet = self._worksheet(table)
        rows = [dict(row) for row in self._read_with_retry(worksheet.get_all_records)]
        # get_all_records already reads the header row. Only fetch it separately
        # for an empty worksheet, where there is no record from which to infer it.
        headers = list(rows[0]) if rows else list(self._read_with_retry(lambda: worksheet.row_values(1)))
        self._tables[table] = (headers, rows)
        return self._tables[table]

    def _restore_snapshot(self) -> bool:
        if self._injected_spreadsheet:
            return False
        with self._snapshot_lock:
            cached = self._snapshot_cache.get(self._cache_key())
            if not cached or cached[0] <= time.monotonic():
                return False
            self._tables = cached[1]
            return True

    def _store_snapshot(self) -> None:
        if self._injected_spreadsheet:
            return
        with self._snapshot_lock:
            self._snapshot_cache[self._cache_key()] = (time.monotonic() + self._snapshot_ttl_seconds, self._tables)

    def _rows(self, table: str) -> list[dict[str, Any]]:
        return self._load_table(table)[1]

    @staticmethod
    def _column_type(values: list[Any]) -> str:
        non_empty = [value for value in values if value not in (None, "")]
        if non_empty and all(isinstance(value, bool) for value in non_empty):
            return "boolean"
        if non_empty and all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in non_empty):
            return "number"
        return "string"

    def inspect_schema(self) -> dict[str, Any]:
        # Schema discovery reads every worksheet. The builder calls this during
        # source resolution and validation, so cache it for the request-local
        # adapter to avoid rapidly exhausting the Sheets read quota.
        if self._schema is not None:
            return self._schema
        self._restore_snapshot()
        tables = []
        for worksheet in self.spreadsheet.worksheets():
            name = worksheet.title
            rows = self._rows(name)
            headers = self._load_table(name)[0]
            columns = [{
                "name": header,
                "type": self._column_type([row.get(header) for row in rows]),
                "nullable": any(row.get(header) in (None, "") for row in rows),
                "default": None,
                "primary_key": False,
            } for header in headers if header]
            tables.append({"name": name, "row_count": len(rows), "columns": columns, "foreign_keys": [], "sample_rows": rows[:5]})
        self._schema = {"source_type": self.source_type, "spreadsheet_id": self.config["spreadsheet_id"], "tables": tables}
        self._store_snapshot()
        return self._schema

    def table_columns(self, table: str) -> set[str]:
        return set(self._load_table(table)[0])

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
