import unittest

from app.adapters.google_sheets_source_adapter import GoogleSheetsSourceAdapter


class FakeWorksheet:
    def __init__(self, title, headers, rows):
        self.title, self.headers, self.rows = title, headers, rows
    def row_values(self, index):
        assert index == 1
        return self.headers
    def get_all_records(self):
        return self.rows


class FakeSpreadsheet:
    def __init__(self, sheets):
        self.sheets = {sheet.title: sheet for sheet in sheets}
    def worksheets(self):
        return list(self.sheets.values())
    def worksheet(self, title):
        return self.sheets[title]


class GoogleSheetsSourceAdapterTests(unittest.TestCase):
    def setUp(self):
        self.adapter = GoogleSheetsSourceAdapter(
            {"spreadsheet_id": "sheet-id", "credential_ref": "VKG_GOOGLE_SERVICE_ACCOUNT_JSON"},
            FakeSpreadsheet([FakeWorksheet("Assets", ["id", "name", "quantity"], [
                {"id": 1, "name": "Camera", "quantity": 2},
                {"id": 1, "name": "Camera backup", "quantity": 3},
                {"id": "", "name": "Unkeyed", "quantity": ""},
            ])]),
        )

    def test_inspects_worksheet_and_reads_rows(self):
        schema = self.adapter.inspect_schema()
        self.assertEqual(schema["tables"][0]["name"], "Assets")
        self.assertEqual(schema["tables"][0]["columns"][2]["type"], "number")
        self.assertEqual(self.adapter.find_rows("Assets", "id", 1, 1)[0]["name"], "Camera")

    def test_detects_duplicate_non_empty_keys(self):
        duplicates = self.adapter.duplicate_keys("Assets", "id")
        self.assertEqual(duplicates["duplicate_key_count"], 1)
        self.assertEqual(duplicates["duplicate_row_count"], 1)
        self.assertEqual(duplicates["samples"], [{"primary_key": 1, "occurrences": 2}])


if __name__ == "__main__":
    unittest.main()
