import unittest

from analise_semantica import (
    aggregate_by_month_and_category,
    combine_description_fields,
    normalize_text,
)


class SemanticAnalysisTests(unittest.TestCase):
    def test_normalize_text_removes_accents_and_standardizes_separators(self):
        self.assertEqual(
            normalize_text("Problema da Geladeira: Ruído/Barulho!"),
            "problema da geladeira ruido barulho",
        )

    def test_aggregate_counts_categories_by_month(self):
        rows = [
            {"CreatedAt": "24/04/2026 10:00", "semantic_category": "ruido"},
            {"CreatedAt": "25/04/2026 10:00", "semantic_category": "ruido"},
            {"CreatedAt": "01/05/2026 10:00", "semantic_category": "lampada"},
        ]
        result = aggregate_by_month_and_category(rows)
        self.assertEqual(result["04/2026"]["ruido"], 2)
        self.assertEqual(result["05/2026"]["lampada"], 1)

    def test_combines_ticket_status_detail_with_descriptions(self):
        row = {
            "Descriptions": "problem_with_refrigerator_do_not_freeze",
            "Description": "Nao gela",
            "TicketStatusDetail": "REPAIRED_WITH_GUIDANCE",
        }
        combined = combine_description_fields(row)
        self.assertIn("repaired with guidance", combined)
        self.assertIn("nao gela", combined)


if __name__ == "__main__":
    unittest.main()
