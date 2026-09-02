from app.adapters.sqlite_adapter import SQLiteAdapter
from app.adapters.google_sheets_adapter import (
    GoogleSheetsAdapter,
)


class AdapterFactory:

    @staticmethod
    def create(
        source_type: str,
        **kwargs,
    ):

        if source_type == "sqlite":
            return SQLiteAdapter(
                kwargs["db_path"]
            )

        if source_type == "google_sheet":
            return GoogleSheetsAdapter(
                credentials_path=kwargs[
                    "credentials_path"
                ],
                spreadsheet_id=kwargs[
                    "spreadsheet_id"
                ],
            )

        raise ValueError(
            f"Unsupported data source: "
            f"{source_type}"
        )