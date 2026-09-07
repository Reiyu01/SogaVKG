from pathlib import Path
from typing import Any

import gspread
from google.oauth2.service_account import Credentials


class GoogleSheetsAdapter:

    def __init__(
        self,
        credentials_path: str,
        spreadsheet_id: str,
    ):
        self.credentials_path = (
            Path(credentials_path)
        )

        self.spreadsheet_id = (
            spreadsheet_id
        )

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets.readonly"
        ]

        credentials = (
            Credentials.from_service_account_file(
                self.credentials_path,
                scopes=scopes,
            )
        )

        self.client = gspread.authorize(
            credentials
        )

        self.spreadsheet = (
            self.client.open_by_key(
                self.spreadsheet_id
            )
        )

    def get_sheet(
        self,
        sheet_name: str,
    ):

        return self.spreadsheet.worksheet(
            sheet_name
        )

    def get_records(
        self,
        sheet_name: str,
    ) -> list[dict[str, Any]]:

        sheet = self.get_sheet(
            sheet_name
        )

        return sheet.get_all_records()

    def execute(
        self,
        query: dict[str, Any],
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:

        sheet_name = query["sheet"]

        records = self.get_records(
            sheet_name
        )

        filters = query.get(
            "filters",
            {},
        )

        result = []

        for record in records:

            matched = True

            for field, value in filters.items():

                record_value = record.get(
                    field
                )

                if value is None:
                    continue

                if (
                    str(value).lower()
                    not in str(
                        record_value
                    ).lower()
                ):
                    matched = False
                    break

            if matched:
                result.append(record)

        return result