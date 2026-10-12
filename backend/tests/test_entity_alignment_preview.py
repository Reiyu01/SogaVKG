import unittest

from app.services.entity_alignment import preview_entity_alignment


class RowsAdapter:
    def __init__(self, rows): self.rows = rows
    def read_rows(self, table): return self.rows


class EntityAlignmentPreviewTests(unittest.TestCase):
    def test_reports_matches_unmatched_nulls_and_duplicate_keys(self):
        preview = preview_entity_alignment(
            {"ingestion": {"source_table": "left"}}, {"ingestion": {"source_table": "right"}},
            RowsAdapter([{"code": "A"}, {"code": "B"}, {"code": "B"}, {"code": None}]),
            RowsAdapter([{"external_code": "A"}, {"external_code": "C"}, {"external_code": ""}]),
            "code", "external_code",
        )
        self.assertEqual(preview["exact_match_count"], 1)
        self.assertEqual(preview["source_unmatched_count"], 1)
        self.assertEqual(preview["target_unmatched_count"], 1)
        self.assertEqual(preview["source"]["null_key_count"], 1)
        self.assertEqual(preview["target"]["null_key_count"], 1)
        self.assertEqual(preview["source"]["duplicate_key_count"], 1)
        self.assertFalse(preview["one_to_one_valid"])

    def test_allows_unique_keys_even_when_some_are_unmatched(self):
        preview = preview_entity_alignment(
            {"ingestion": {"source_table": "left"}}, {"ingestion": {"source_table": "right"}},
            RowsAdapter([{"code": "A"}, {"code": "B"}]), RowsAdapter([{"code": "A"}, {"code": "C"}]),
            "code", "code",
        )
        self.assertTrue(preview["one_to_one_valid"])
        self.assertEqual(preview["exact_match_count"], 1)

    def test_normalization_can_match_case_and_whitespace(self):
        preview = preview_entity_alignment(
            {"ingestion": {"source_table": "left"}}, {"ingestion": {"source_table": "right"}},
            RowsAdapter([{"code": " A-001 "}]), RowsAdapter([{"code": "a-001"}]),
            "code", "code", "trim_casefold",
        )
        self.assertEqual(preview["exact_match_count"], 1)


if __name__ == "__main__":
    unittest.main()
